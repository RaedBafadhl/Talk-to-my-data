"""
Pillar 2.4 -- Ambiguity Resolution & Clarification

Builds on top of 2.1's schema-aware prompt: before generating SQL, the AI
first checks whether the question is genuinely ambiguous (e.g. "sales" could
mean revenue or units sold). If so, it asks a clarifying question instead of
guessing -- matching the "needs_clarification" shape defined in api.md.

Usage:
    python src/llm/clarify_and_generate.py "What were our sales last month?"
    python src/llm/clarify_and_generate.py "What was total revenue in December 2019?"
"""

import os
import sys
from dotenv import load_dotenv
from google import genai
from google.genai import types

sys.path.append(os.path.dirname(__file__))
from schema_context import build_system_prompt

load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
REGION = os.getenv("GCP_REGION", "europe-west4")
MODEL_NAME = "gemini-2.5-flash"

CLARIFY_MARKER = "CLARIFY:"


def build_clarification_prompt() -> str:
    """
    Extends the base schema-aware prompt (from 2.1) with instructions for
    handling ambiguous questions.
    """
    base_prompt = build_system_prompt()

    clarification_instructions = f"""
 
AMBIGUITY CHECK (do this before writing any SQL):
Before generating SQL, check if the question is genuinely ambiguous given the
schema above. Common ambiguous cases:
- "sales" could mean revenue (money) or units sold (quantity) -- these need different SQL
- a time period like "recent" or "this year" with no clear date range
- a metric that could reasonably be calculated more than one way
 
If the question IS ambiguous, respond with EXACTLY this format, nothing else:
{CLARIFY_MARKER} <your clarifying question to the user>
 
If the question is NOT ambiguous, respond with ONLY the SQL query, exactly as
instructed above -- no explanation, no markdown.
"""
    return base_prompt + clarification_instructions


def ask(question: str) -> dict:
    """
    Returns a dict matching the api.md response shape:
    {"needs_clarification": bool, "clarification_question": str|None, "sql": str|None}
    """
    client = genai.Client(vertexai=True, project=PROJECT_ID, location=REGION)
    system_prompt = build_system_prompt(question)

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=question,
        config=types.GenerateContentConfig(system_instruction=system_prompt),
    )
    text = response.text.strip()

    if text.startswith(CLARIFY_MARKER):
        clarification_question = text[len(CLARIFY_MARKER) :].strip()
        return {
            "needs_clarification": True,
            "clarification_question": clarification_question,
            "sql": None,
        }
    else:
        return {
            "needs_clarification": False,
            "clarification_question": None,
            "sql": text,
        }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python src/llm/clarify_and_generate.py "your question here"')
        sys.exit(1)

    question = sys.argv[1]
    print(f"Question: {question}\n")

    result = ask(question)

    if result["needs_clarification"]:
        print("Result: NEEDS CLARIFICATION")
        print("-" * 70)
        print(result["clarification_question"])
        print("-" * 70)
    else:
        print("Result: SQL GENERATED DIRECTLY (no ambiguity detected)")
        print("-" * 70)
        print(result["sql"])
        print("-" * 70)
