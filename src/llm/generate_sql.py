"""
Pillar 2.1 -- Dynamic Schema Injection (end-to-end test)

Uses the schema-aware system prompt from schema_context.py to call Google's Gemini model
and generate SQL from a plain-English question.
"""

import os
import sys
from dotenv import load_dotenv
from google import genai
from google.genai import types

sys.path.append(os.path.dirname(__file__))
from schema_context import build_system_prompt

load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "talk-to-my-data-508110")
REGION = os.getenv("GCP_REGION", "europe-west4")
MODEL_NAME = "gemini-2.5-flash"


def get_genai_client() -> genai.Client:
    """
    Returns a configured Google GenAI client instance.
    Prioritizes GEMINI_API_KEY if provided, otherwise defaults to Vertex AI configuration.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        return genai.Client(api_key=api_key)

    if PROJECT_ID:
        try:
            return genai.Client(vertexai=True, project=PROJECT_ID, location=REGION)
        except Exception:
            pass

    return genai.Client()


def generate_sql(question: str) -> str:
    client = get_genai_client()
    system_prompt = build_system_prompt(question)

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
