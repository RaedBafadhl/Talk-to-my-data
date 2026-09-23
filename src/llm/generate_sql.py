"""
Pillar 2.1 -- Dynamic Schema Injection (end-to-end test)

Uses the schema-aware system prompt from prompt_builder.py to actually call
Google's Gemini model (via the Agent Platform / Vertex AI backend) and
generate SQL from a plain-English question.

NOTE: uses the google-genai library (the current, supported one), not the
older google-cloud-aiplatform / vertexai.generative_models module, which
Google fully removed in mid-2026.

This is a MINIMAL first version -- just proves schema injection works.
Few-shot examples (2.2), self-healing retries (2.3), and clarification (2.4)
are separate tasks that build on top of this.

Usage:
    python src/llm/generate_sql.py "What was total revenue last month?"
"""

import os
import sys
from dotenv import load_dotenv
from google import genai
from google.genai import types

sys.path.append(os.path.dirname(__file__))
from prompt_builder import build_system_prompt

load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
REGION = os.getenv("GCP_REGION", "europe-west4")

MODEL_NAME = "gemini-2.5-flash"  # check Model Garden in GCP Console if this errors -- model names change


def generate_sql(question: str) -> str:
    client = genai.Client(vertexai=True, project=PROJECT_ID, location=REGION)

    system_prompt = build_system_prompt()

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=question,
        config=types.GenerateContentConfig(system_instruction=system_prompt),
    )
    return response.text.strip()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python src/llm/generate_sql.py "your question here"')
        sys.exit(1)

    question = sys.argv[1]
    print(f"Question: {question}\n")
    print("Generating SQL...\n")

    sql = generate_sql(question)
    print("Generated SQL:")
    print("-" * 70)
    print(sql)
    print("-" * 70)
    print("\nNOTE: this SQL has NOT been validated or executed yet -- that's")
    print("Pillar 3's job (3.2 SQL Validation). This script only proves the")
    print("schema-aware generation step works.")
