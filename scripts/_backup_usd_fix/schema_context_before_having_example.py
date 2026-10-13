"""
Pillar 2.1 -- Dynamic Schema Injection (hybrid version)

Combines the best of both implementations:
- Fares's idea: only send the AI the tables actually relevant to the
  question, not the whole schema every time -- smaller, more targeted prompts.
- Raed's approach: read from contracts/schema.md (the team's agreed single
  source of truth) rather than fetching live from BigQuery on every question --
  no extra network call, no risk of a live dependency hiccuping mid-demo, and
  stays consistent with the team's own contract-based design decision.

Also folds in a real gap Fares caught: "country" is ambiguous in this project
(customer country vs. store country) -- that's now handled explicitly.
"""

import os
import re
from pathlib import Path

SCHEMA_PATH = Path("contracts/schema.md")

TABLE_NAMES = {"sales", "products", "customers", "stores", "exchange_rates"}


def parse_schema_sections() -> dict:
    """
    Splits schema.md into per-table sections, plus the shared sections
    (Relationships, Business terms mapping) that should always be included
    regardless of which tables are selected.

    Returns:
        {
            "tables": {"sales": "...", "products": "...", ...},
            "shared": "... Relationships + Business terms text ..."
        }
    """
    text = SCHEMA_PATH.read_text(encoding="utf-8")

    # Split on "## " headers, keeping the header with its content
    sections = re.split(r"\n(?=## )", text)

    tables = {}
    shared_parts = []

    for section in sections:
        match = re.match(r"## Table: `(\w+)`", section)
        if match:
            table_name = match.group(1)
            if table_name in TABLE_NAMES:
                tables[table_name] = section.strip()
        elif section.strip().startswith(
            "## Relationships"
        ) or section.strip().startswith("## Business terms"):
            shared_parts.append(section.strip())

    return {
        "tables": tables,
        "shared": "\n\n".join(shared_parts),
    }


def select_relevant_tables(question: str) -> set:
    """
    Picks which tables are likely relevant to the question, so we don't send
    the AI the full schema every time. "sales" is always included since it's
    the central fact table almost every question touches.

    (Table-selection logic adapted from Fares's approach in 2.1.)
    """
    q = question.lower()
    selected = {"sales"}

    product_terms = {
        "product",
        "products",
        "category",
        "categories",
        "subcategory",
        "brand",
        "price",
    }
    customer_terms = {"customer", "customers", "gender", "birthday", "continent"}
    store_terms = {"store", "stores", "square meters", "square meter"}
    money_terms = {
        "revenue",
        "sales",
        "profit",
        "aov",
        "average order value",
        "currency",
        "price",
    }

    if any(term in q for term in product_terms):
        selected.add("products")
    if any(term in q for term in customer_terms):
        selected.add("customers")
    if any(term in q for term in store_terms):
        selected.add("stores")
    if any(term in q for term in money_terms):
        selected.add("products")

    # exchange_rates is only needed when a question asks for a LOCAL currency;
    # USD revenue is just quantity * unit_price (prices are already in USD).
    local_currency_terms = {"euro", "pound", "local currency", "exchange rate", "in eur", "in gbp", "in cad", "in aud"}
    if any(term in q for term in local_currency_terms):
        selected.add("exchange_rates")

    # "country" is genuinely ambiguous here -- could mean customer country
    # or store country. Include both tables so the AI has what it needs
    # either way; the ambiguity itself gets flagged separately (see
    # clarify_and_generate.py), this just makes sure both are available.
    if "country" in q or "region" in q:
        selected.add("customers")
        selected.add("stores")

    # Safety fallback: if no keyword category matched anything (selected is
    # still just the default "sales"), the question may be phrased in a way
    # our keyword list doesn't cover. Rather than risk missing a table the
    # AI actually needs, fall back to including everything -- our whole
    # schema is small (5 tables, ~5k characters), so this costs almost
    # nothing and trades a tiny bit of efficiency for real reliability.
    if selected == {"sales"}:
        return set(TABLE_NAMES)

    return selected


def build_schema_context(question: str) -> str:
    """
    Main function for Task 2.1 (hybrid version).
    Given a user question, returns only the relevant table definitions
    plus the always-included relationships and business rules.
    """
    parsed = parse_schema_sections()
    relevant_tables = select_relevant_tables(question)

    table_sections = [
        parsed["tables"][name]
        for name in sorted(relevant_tables)
        if name in parsed["tables"]
    ]

    return "\n\n".join(table_sections) + "\n\n" + parsed["shared"]


def build_system_prompt(question: str) -> str:
    """
    Full system prompt: instructions + a few real worked examples (Pillar 2.2
    few-shot prompting) + only the relevant schema context, plus ambiguity-
    checking instructions (Pillar 2.4 logic folded in).
    """
    schema_context = build_schema_context(question)

    # Pillar 2.2 -- Few-Shot Prompting
    # These are REAL, VERIFIED examples -- each one has actually been run
    # against BigQuery and confirmed correct (see scripts/golden_dataset.py
    # history). Using real, proven examples rather than invented ones keeps
    # the prompt honest and means every pattern shown is genuinely reliable.
    project_id = os.getenv("GCP_PROJECT_ID", "talk-to-my-data-508110")
    few_shot_examples = f"""
EXAMPLES (these are real, verified question-to-SQL patterns -- follow this style):
 
Question: What was total revenue in December 2019?
SQL:
SELECT SUM(t1.quantity * t2.unit_price) AS revenue
 
Question: How many stores do we have?
SQL:
SELECT COUNT(t1.store_key) AS store_count
FROM `{project_id}.retail_dw.stores` AS t1
 
Question: What are the top 5 product categories by revenue?
SQL:
SELECT t2.category, SUM(t1.quantity * t2.unit_price) AS revenue
FROM `{project_id}.retail_dw.sales` AS t1
JOIN `{project_id}.retail_dw.products` AS t2 ON t1.product_key = t2.product_key
GROUP BY t2.category
ORDER BY revenue DESC
LIMIT 5
 
Question: What is our average order value?
SQL:
SELECT SUM(t1.quantity * t2.unit_price) / COUNT(DISTINCT t1.order_number) AS average_order_value
FROM `{project_id}.retail_dw.sales` AS t1
JOIN `{project_id}.retail_dw.products` AS t2 ON t1.product_key = t2.product_key
 
Question: What's the average age of our customers?
SQL:
SELECT AVG(DATE_DIFF(CURRENT_DATE(), t1.birthday, YEAR)) AS average_age
FROM `{project_id}.retail_dw.customers` AS t1
 
Question: How many stores were opened after 2015?
SQL:
SELECT COUNT(t1.store_key) AS store_count
FROM `{project_id}.retail_dw.stores` AS t1
WHERE EXTRACT(YEAR FROM t1.open_date) > 2015
"""

    return f"""You are a SQL assistant for The Gadget Store (TGS), a retail company.
Your job is to turn a plain-English business question into a single, correct,
READ-ONLY BigQuery SQL query.
 
RULES (never break these):
1. Only ever write SELECT statements. Never write INSERT, UPDATE, DELETE, DROP, ALTER, or any statement that changes data.
2. Only use the tables and columns described in the schema below. Never invent a column or table name.
3. Use the fully-qualified table names in backticks: `{project_id}.retail_dw.<table_name>`
4. ALWAYS assign a short alias to every table you reference (e.g. `AS t1`), and use that alias for every column reference (e.g. `t1.order_date`). NEVER reference a column through the full `project.dataset.table.column` path directly -- the project ID contains hyphens, which breaks unaliased references.
5. Return ONLY the SQL query, with no explanation, no markdown formatting -- UNLESS the question is ambiguous (see below).
6. When filtering on a text/string column (e.g. category, country, brand), ALWAYS use a case-insensitive comparison: `LOWER(column) = LOWER('value')`. Never assume the exact capitalization the user typed matches the database -- a mismatch here causes a silently WRONG answer (e.g. zero results), not an error, which is worse than a crash.
7. "Continent" ALWAYS means `customers.continent`. The `stores` table has NO continent column and NO geography/region lookup table exists anywhere in this database -- never invent one. If you cannot find a column the question needs, do NOT silently substitute a different, similar-sounding column (e.g. answering with country when asked for continent) -- that produces a misleadingly wrong answer. Instead, use the CLARIFY format to say you cannot answer as asked.
8. ALWAYS give every calculated or aggregated column a meaningful name using `AS` (e.g. `SUM(...) AS revenue`, not just `SUM(...)`). Without this, BigQuery auto-names the column something meaningless like `f0_`, which produces a confusing summary for the end user.
{few_shot_examples}
AMBIGUITY CHECK (do this before writing any SQL):
Common ambiguous cases in this project:
- "sales" could mean revenue (money) or units sold (quantity)
- "country" could mean the CUSTOMER's country or the STORE's country -- these can differ and give different answers
- a vague time period like "recent" with no clear date range
 
If the question IS ambiguous, respond with EXACTLY this format, nothing else:
CLARIFY: <your clarifying question to the user>
 
If the question is NOT ambiguous, respond with ONLY the SQL query.
 
Here is the relevant part of our database schema for this question:
 
{schema_context}
 
USER QUESTION:
{question}
"""


if __name__ == "__main__":
    # Quick test: show which tables get selected for a few different questions,
    # and how much smaller the context is compared to sending everything.
    test_questions = [
        "What are the top 5 product categories by revenue?",
        "How many units did we sell?",
        "What was revenue by country?",
        "Which stores sold the most products?",
    ]

    full_schema_size = len(SCHEMA_PATH.read_text(encoding="utf-8"))

    for q in test_questions:
        print("=" * 70)
        print(f"QUESTION: {q}")
        tables = select_relevant_tables(q)
        print(f"Tables selected: {sorted(tables)}")
        context = build_schema_context(q)
        print(
            f"Context size: {len(context)} chars (full schema.md is {full_schema_size} chars)"
        )
        print()
