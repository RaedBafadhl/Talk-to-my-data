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

Usage (local development):
    uvicorn src.backend.main:app --reload
    Then test at: http://127.0.0.1:8000/docs

Usage (Cloud Run / production):
    python src/backend/main.py
    (reads the PORT environment variable, same as before)
"""

import sys
import os
from typing import Optional, List, Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "llm"))
from self_healing import execute_with_self_healing

app = FastAPI(title="Talk-to-my-Data Backend")

# Allows the frontend (running on a different port) to call this API.
# Wide open for now since this is an internal capstone project, not public.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Kept from the original deployment stub ----


@app.get("/")
def read_root():
    return {"status": "ok", "message": "Talk-to-my-data backend container is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


# ---- New: the real AI-powered endpoint ----


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
    full_question = request.question
    if request.clarification_answer:
        full_question = (
            f"{request.question} (clarification: {request.clarification_answer})"
        )

    try:
        result = execute_with_self_healing(full_question, max_retries=3)
    except Exception as e:
        return AskResponse(status="error", message=f"Unexpected error: {e}")

    if result["status"] == "needs_clarification":
        return AskResponse(
            status="needs_clarification",
            clarification_question=result.get("clarification_question"),
        )

    elif result["status"] == "success":
        table = result.get("data", [])
        summary = (
            f"Query returned {len(table)} result(s)."
            if table
            else "No results found for this question."
        )
        return AskResponse(
            status="ok",
            sql=result.get("final_sql"),
            summary=summary,
            table=table,
            chart=None,  # Pillar 3.4's job to generate this
        )

    else:
        return AskResponse(
            status="error",
            message=result.get(
                "error", "The query could not be completed after multiple attempts."
            ),
        )


# ---- Kept from the original deployment stub, for Cloud Run compatibility ----

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
