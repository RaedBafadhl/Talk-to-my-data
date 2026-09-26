"""
Pillar 2.1 -- Dynamic Schema Injection

Builds the system prompt that gets sent to the LLM before every question.
This is what makes the assistant "schema-aware" -- it always knows the real
table/column names and business-term meanings, straight from contracts/schema.md,
so it never has to guess.

The schema content is read directly from schema.md at runtime, not copy-pasted
here -- so if the schema ever changes, this stays automatically in sync with
the single source of truth.
"""

from pathlib import Path

SCHEMA_PATH = Path("contracts/schema.md")


def build_system_prompt() -> str:
    """
    Returns the full system prompt: instructions + the real schema content.
    """
    schema_content = SCHEMA_PATH.read_text(encoding="utf-8")

    system_prompt = f"""You are a SQL assistant for The Gadget Store (TGS), a retail company.
Your job is to turn a plain-English business question into a single, correct,
READ-ONLY BigQuery SQL query.
 
RULES (never break these):
1. Only ever write SELECT statements. Never write INSERT, UPDATE, DELETE, DROP, ALTER, or any statement that changes data.
2. Only use the tables and columns described in the schema below. Never invent a column or table name.
3. Use the fully-qualified table names: `tgs-talk-to-data.retail_dw.<table_name>`
4. Return ONLY the SQL query, with no explanation, no markdown formatting, no backticks around the query.
5. If the question is ambiguous (e.g. "sales" could mean revenue or units), do not guess -- that case is handled separately, outside this function.
 
Here is the full database schema, including table structures, relationships,
and the business-terms-to-SQL mapping your team agreed on:
 
{schema_content}
"""
    return system_prompt


if __name__ == "__main__":
    # Quick manual check: print the first 500 characters so you can eyeball
    # that the schema content is being pulled in correctly.
    prompt = build_system_prompt()
    print(f"System prompt built successfully -- {len(prompt)} characters total.\n")
    print("First 500 characters:")
    print("-" * 70)
    print(prompt[:500])
    print("-" * 70)
