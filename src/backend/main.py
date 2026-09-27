"""
Pillar 3.1 -- FastAPI Core Service Layer

Builds on top of the minimal deployment stub (health check endpoints, kept
as-is for Muhammed's Cloud Run work) by adding the real /ask endpoint --
wrapping the already-working AI pipeline (schema injection + self-healing +
clarification, from Pillar 2) behind a single HTTP endpoint.

Matches the request/response shape agreed in contracts/api.md.

NOTE: The "summary" field here is a simple placeholder for now -- proper
natural-language summaries and chart generation are Pillar 3.3 (KPI Engine)
and 3.4 (Response Formatter)'s job, built on top of this same endpoint later.

NOTE on conversation_id: this is a deliberately simple, stateless design --
the frontend resends the original question text alongside the clarification
answer, rather than the server remembering conversation state. Reasonable
for this project's scale; a real production system with many concurrent
users would likely want server-side conversation storage instead.

Usage (local development):
    uvicorn src.backend.main:app --reload
    Then test at: http://127.0.0.1:8000/docs

Usage (Cloud Run / production):
    python src/backend/main.py
    (reads the PORT environment variable, same as before)
"""

import sys
import os
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "llm"))
from self_healing import execute_with_self_healing

app = FastAPI(title="Talk-to-my-Data Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Basic logging: every question + result gets written to a log file ----
# Uses a dedicated logger (not the root logger) so we only capture our own
# messages -- not the internal chatter from Google's genai/httpx libraries.
LOG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "logs", "api_requests.log"
)
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

logger = logging.getLogger("talk_to_my_data")
logger.setLevel(logging.INFO)
logger.propagate = False  # don't also send these to the root logger
_handler = logging.FileHandler(LOG_PATH)
_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
logger.addHandler(_handler)


# ---- Kept from the original deployment stub ----


@app.get("/")
def read_root():
    return {"status": "ok", "message": "Talk-to-my-data backend container is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


# ---- The real AI-powered endpoint ----


class AskRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    clarification_answer: Optional[str] = None


class AskResponse(BaseModel):
    status: str  # "ok" | "needs_clarification" | "error"
    sql: Optional[str] = None
    summary: Optional[str] = None
    table: Optional[List[Dict[str, Any]]] = None
    chart: Optional[Dict[str, Any]] = None
    clarification_question: Optional[str] = None
    message: Optional[str] = None


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    # Basic input validation -- don't waste an AI call on an empty question
    if not request.question or not request.question.strip():
        logger.info(
            f"REJECTED (empty question) | conversation_id={request.conversation_id}"
        )
        return AskResponse(status="error", message="Question cannot be empty.")

    full_question = request.question
    if request.clarification_answer:
        full_question = (
            f"{request.question} (clarification: {request.clarification_answer})"
        )

    try:
        result = execute_with_self_healing(full_question, max_retries=3)
    except Exception as e:
        logger.info(f"EXCEPTION | question='{request.question}' | error={e}")
        return AskResponse(status="error", message=f"Unexpected error: {e}")

    status = result["status"]

    if status == "needs_clarification":
        logger.info(f"CLARIFICATION | question='{request.question}'")
        return AskResponse(
            status="needs_clarification",
            clarification_question=result.get("clarification_question"),
        )

    elif status == "success":
        table = result.get("data", [])
        summary = (
            f"Query returned {len(table)} result(s)."
            if table
            else "No results found for this question."
        )
        logger.info(
            f"SUCCESS | question='{request.question}' | attempts={result.get('attempts')} | rows={len(table)}"
        )
        return AskResponse(
            status="ok",
            sql=result.get("final_sql"),
            summary=summary,
            table=table,
            chart=None,  # Pillar 3.4's job to generate this
        )

    else:  # status == "error"
        logger.info(
            f"FAILED | question='{request.question}' | error={result.get('error')}"
        )
        return AskResponse(
            status="error",
            message=result.get(
                "error", "The query could not be completed after multiple attempts."
            ),
        )


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
