"""
Pillar 3.1 -- FastAPI Core Service Layer

Provides the REST API endpoints defined in contracts/api.md:
- POST /ask: Main entrypoint coordinating UI ↔ LLM ↔ BigQuery pipeline
- GET /health: Liveness / health check endpoint for Cloud Run
"""

import os
import sys
import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.service import process_question

# ---- Basic logging: every question + result gets written to a log file ----
LOG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "logs", "api_requests.log"
)
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

logger = logging.getLogger("talk_to_my_data")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    _handler = logging.FileHandler(LOG_PATH)
    _handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
    logger.addHandler(_handler)

app = FastAPI(
    title="Talk-to-my-data Backend (Pillar 3)",
    description="Natural language BI backend service connecting Streamlit UI, Gemini LLM, and BigQuery",
    version="1.0.0"
)

# Configure CORS to allow Streamlit UI or local client requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic Schemas matching contracts/api.md
class AskRequest(BaseModel):
    question: str = Field(..., description="The user's question in plain English", example="What were total headphone sales in 2025?")
    conversation_id: Optional[str] = Field(None, description="Conversation session ID for grouping context")
    clarification_answer: Optional[str] = Field(None, description="Answer to a previous clarification question")


class ChartConfig(BaseModel):
    type: str = Field(..., description="Chart type: line, bar, pie, donut")
    x_field: str = Field(..., description="Column name for x axis")
    y_field: str = Field(..., description="Column name for y axis")


class AskResponse(BaseModel):
    status: str = Field(..., description="Response status: 'ok', 'needs_clarification', or 'error'")
    sql: Optional[str] = Field(None, description="The generated SQL query")
    summary: Optional[str] = Field(None, description="Plain-English narrative summary")
    table: Optional[List[Dict[str, Any]]] = Field(None, description="Result table rows")
    chart: Optional[ChartConfig] = Field(None, description="Chart visualization schema")
    clarification_question: Optional[str] = Field(None, description="Clarification question if status is needs_clarification")
    message: Optional[str] = Field(None, description="User-friendly error message if status is error")


@app.get("/")
def read_root():
    return {
        "status": "ok",
        "service": "Talk-to-my-data Backend",
        "pillar": "Pillar 3 -- Backend & Analytics Engine"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/ask", response_model=AskResponse)
def ask_question(payload: AskRequest):
    """
    Main endpoint accepting user question and orchestrating Text-to-SQL execution.
    """
    if not payload.question or not payload.question.strip():
        logger.info(f"REJECTED (empty question) | conversation_id={payload.conversation_id}")
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        logger.info(f"REQUEST | question='{payload.question}' | conversation_id={payload.conversation_id}")
        result = process_question(
            question=payload.question,
            conversation_id=payload.conversation_id,
            clarification_answer=payload.clarification_answer
        )
        logger.info(f"RESPONSE | status={result.get('status')}")
        return result
    except Exception as e:
        logger.error(f"EXCEPTION | question='{payload.question}' | error={e}")
        return {
            "status": "error",
            "message": "An unexpected server error occurred while processing your request."
        }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
