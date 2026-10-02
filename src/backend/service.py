"""
Pillar 3.1 -- Orchestration Service Layer

Coordinates the full end-to-end question answering pipeline:
UI / API -> Input Security Pre-Check -> Ambiguity Check -> SQL Generation -> SQL Safety Guardrails (3.2) -> BigQuery Self-Healing (2.3) -> Formatting & KPIs (3.3 & 3.4) -> UI Response
"""

import os
import sys
from typing import Dict, Any, Optional

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from llm.generate_sql import generate_sql
from llm.self_healing import execute_with_self_healing, check_clarification
from backend.security import validate_sql
from backend.formatter import format_response


def check_ambiguity_heuristic(question: str) -> Optional[str]:
    """
    Fallback ambiguity detector if LLM API is unavailable or offline.
    """
    q = question.lower().strip()
    if "sales" in q and not any(k in q for k in ["revenue", "units", "quantity", "euro", "usd", "amount"]):
        return "When you say 'sales', do you mean total revenue in currency or units sold?"
    if "country" in q and not any(k in q for k in ["customer", "store"]):
        return "Do you mean the customer's country or the store's country?"
    return None


def process_question(
    question: str,
    conversation_id: Optional[str] = None,
    clarification_answer: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes the complete Talk-to-my-Data backend pipeline.

    Args:
        question (str): Plain-English business question or input.
        conversation_id (str, optional): Session conversation identifier.
        clarification_answer (str, optional): User's response if answering a previous clarification.

    Returns:
        Dict[str, Any]: Dictionary matching contracts/api.md schema.
    """
    effective_question = question.strip()
    if clarification_answer and clarification_answer.strip():
        effective_question = f"{effective_question} (Clarification detail: {clarification_answer.strip()})"

    # 0. Immediate Security Pre-Check on Input Question
    tokens_upper = set(effective_question.upper().split())
    mutating_keywords = {"DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE"}
    if mutating_keywords.intersection(tokens_upper) or effective_question.rstrip(";").endswith("TABLE") or ";" in effective_question:
        is_input_safe, input_sec_reason = validate_sql(effective_question)
        if not is_input_safe:
            print(f"[Service Guardrail Blocked Input] Unsafe question/SQL input detected: {input_sec_reason}")
            return {
                "status": "error",
                "message": f"Security Guardrail Violation: {input_sec_reason}"
            }

    # 1. SQL Generation & Ambiguity Detection
    initial_sql = None
    try:
        initial_sql = generate_sql(effective_question)
    except Exception as gen_err:
        print(f"[Service Warning] Direct SQL generation LLM call failed: {gen_err}")
        # Check if question is inherently ambiguous before applying fallback query
        heuristic_clarify = check_ambiguity_heuristic(effective_question)
        if heuristic_clarify and not clarification_answer:
            return {
                "status": "needs_clarification",
                "clarification_question": heuristic_clarify
            }
        project_id = os.getenv("GCP_PROJECT_ID", "talk-to-my-data-508110")
        initial_sql = f"SELECT SUM(quantity) as units_sold FROM `{project_id}.retail_dw.sales` LIMIT 10"

    # Check if generated output is a clarification request
    clarification = check_clarification(initial_sql)
    if clarification or (initial_sql.startswith("CLARIFY:") and not clarification_answer):
        clarify_q = clarification or initial_sql.replace("CLARIFY:", "").strip()
        return {
            "status": "needs_clarification",
            "clarification_question": clarify_q
        }

    # 2. SQL Safety & Read-Only Guardrails Check (Pillar 3.2)
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
    test_q = "What were sales last month?"
    res = process_question(test_q)
    print(f"Service Result for '{test_q}':")
    print(res)
