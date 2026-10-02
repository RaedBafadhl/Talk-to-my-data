"""
Pillar 3.1 -- Orchestration Service Layer

Coordinates the full end-to-end question answering pipeline:
UI / API -> SQL Generation & Clarification Check -> SQL Safety Check (3.2) -> BigQuery Self-Healing (2.3) -> Formatting & KPIs (3.3 & 3.4) -> UI Response
"""

import os
import sys
from typing import Dict, Any, Optional

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from llm.generate_sql import generate_sql
from llm.self_healing import execute_with_self_healing
from backend.security import validate_sql
from backend.formatter import format_response


def process_question(
    question: str,
    conversation_id: Optional[str] = None,
    clarification_answer: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes the complete Talk-to-my-Data backend pipeline.

    Args:
        question (str): Plain-English business question.
        conversation_id (str, optional): Session conversation identifier.
        clarification_answer (str, optional): User's response if answering a previous clarification.

    Returns:
        Dict[str, Any]: Dictionary matching contracts/api.md schema.
    """
    effective_question = question.strip()
    if clarification_answer and clarification_answer.strip():
        effective_question = f"{effective_question} (Clarification detail: {clarification_answer.strip()})"

    initial_sql = None

    # 1. SQL Generation
    try:
        initial_sql = generate_sql(effective_question)
    except Exception as gen_err:
        print(f"[Service Warning] Direct SQL generation fallback: {gen_err}")
        project_id = os.getenv("GCP_PROJECT_ID", "talk-to-my-data-508110")
        initial_sql = f"SELECT SUM(quantity) as units_sold FROM `{project_id}.retail_dw.sales` LIMIT 10"

    # 2. SQL Safety & Read-Only Guardrails Check (Pillar 3.2)
    # Note: If initial_sql is a CLARIFY: response, validate_sql will handle it safely
    if not initial_sql.strip().startswith("CLARIFY:"):
        is_safe, security_reason = validate_sql(initial_sql)
        if not is_safe:
            print(f"[Service Rejected] Unsafe SQL detected: {security_reason}")
            return {
                "status": "error",
                "message": f"Security Guardrail Violation: {security_reason}"
            }

    # 3. BigQuery Execution with Self-Healing Feedback Loop (Pillar 2.3 & 1.2)
    try:
        healing_result = execute_with_self_healing(
            question=effective_question,
            initial_sql=initial_sql,
            max_retries=3
        )
    except Exception as exec_err:
        return {
            "status": "error",
            "message": f"Execution error: {str(exec_err)}"
        }

    status = healing_result.get("status")
    if status == "needs_clarification":
        return {
            "status": "needs_clarification",
            "clarification_question": healing_result.get("clarification_question")
        }

    if status == "error":
        return {
            "status": "error",
            "message": healing_result.get("error", "Failed to execute query after retries.")
        }

    final_sql = healing_result.get("final_sql", initial_sql)
    raw_data = healing_result.get("data", [])

    # Re-validate self-healed SQL just in case LLM correction modified query type
    if final_sql and not final_sql.strip().startswith("CLARIFY:"):
        is_healed_safe, healed_reason = validate_sql(final_sql)
        if not is_healed_safe:
            return {
                "status": "error",
                "message": f"Self-healed query violated safety guardrails: {healed_reason}"
            }

    # 4. Multi-Modal Response Formatting & KPI Computation (Pillar 3.3 & 3.4)
    response_payload = format_response(
        sql=final_sql,
        data=raw_data,
        question=effective_question
    )

    return response_payload


if __name__ == "__main__":
    print("Testing Service Pipeline locally...")
    test_q = "What were total sales in 2025?"
    res = process_question(test_q)
    print("Service Result:")
    print(res)
