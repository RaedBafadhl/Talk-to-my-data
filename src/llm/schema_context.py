import os
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import bigquery


load_dotenv()

DATASET_ID = "retail_dw"

# These are the business tables defined in contracts/schema.md
BUSINESS_TABLES = {
    "sales",
    "products",
    "customers",
    "stores",
    "exchange_rates",
}


def get_bigquery_client() -> bigquery.Client:
    project_id = os.getenv("GCP_PROJECT_ID")

    if not project_id:
        raise ValueError(
            "GCP_PROJECT_ID is missing. "
            "Make sure your .env file is configured."
        )

    return bigquery.Client(project=project_id)


def fetch_live_schema() -> dict:
    """
    Read the current table schemas directly from BigQuery.

    Returns:
        {
            "sales": [
                {
                    "name": "order_date",
                    "type": "DATE",
                    "mode": "NULLABLE"
                },
                ...
            ],
            ...
        }
    """

    client = get_bigquery_client()

    dataset_ref = f"{client.project}.{DATASET_ID}"

    tables = client.list_tables(dataset_ref)

    schema = {}

    for table_item in tables:

        if table_item.table_id not in BUSINESS_TABLES:
            continue

        table = client.get_table(table_item.reference)

        schema[table.table_id] = [
            {
                "name": field.name,
                "type": field.field_type,
                "mode": field.mode,
            }
            for field in table.schema
        ]

    return schema


def select_relevant_tables(question: str) -> set[str]:
    """
    Select tables likely to be useful for the user's question.

    sales is the central fact table, so it is included by default.
    """

    question = question.lower()

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

    customer_terms = {
        "customer",
        "customers",
        "gender",
        "birthday",
        "continent",
    }

    store_terms = {
        "store",
        "stores",
        "store country",
        "store state",
        "square meters",
    }

    money_terms = {
        "revenue",
        "sales",
        "profit",
        "aov",
        "average order value",
        "currency",
        "price",
    }

    if any(term in question for term in product_terms):
        selected.add("products")

    if any(term in question for term in customer_terms):
        selected.add("customers")

    if any(term in question for term in store_terms):
        selected.add("stores")

    if any(term in question for term in money_terms):
        selected.add("products")
        selected.add("exchange_rates")

    # "country" is ambiguous in this project:
    # it could mean customer country or store country.
    if "country" in question or "region" in question:
        selected.add("customers")
        selected.add("stores")

    return selected


def format_schema(
    schema: dict,
    selected_tables: set[str],
) -> str:
    """
    Convert BigQuery metadata into readable prompt context.
    """

    output = []

    for table_name in sorted(selected_tables):

        if table_name not in schema:
            continue

        output.append(f"Table: {table_name}")

        for field in schema[table_name]:
            output.append(
                f"- {field['name']} "
                f"({field['type']}, {field['mode']})"
            )

        output.append("")

    return "\n".join(output)


def load_contract_rules() -> str:
    """
    Read relationships and business rules directly from
    contracts/schema.md so we do not maintain a second,
    conflicting definition.
    """

    repo_root = Path(__file__).resolve().parents[2]

    schema_file = repo_root / "contracts" / "schema.md"

    text = schema_file.read_text(encoding="utf-8")

    marker = "## Relationships"

    if marker not in text:
        raise ValueError(
            "Could not find Relationships section "
            "in contracts/schema.md"
        )

    return text[text.index(marker):].strip()


def build_schema_context(question: str) -> str:
    """
    Main function for Task 2.1.

    Given a user question, return the relevant database
    schema + relationships + business rules for the LLM.
    """

    full_schema = fetch_live_schema()

    relevant_tables = select_relevant_tables(question)

    schema_text = format_schema(
        full_schema,
        relevant_tables,
    )

    contract_rules = load_contract_rules()

    return f"""
DATABASE SCHEMA
===============

{schema_text}

PROJECT RELATIONSHIPS AND BUSINESS RULES
========================================

{contract_rules}
""".strip()

def build_sql_prompt(question: str) -> str:
    schema_context = build_schema_context(question)

    return f"""
You are a BigQuery SQL assistant for a retail analytics system.

Generate SQL using ONLY the database schema provided below.

Rules:
- Use BigQuery Standard SQL.
- Only use tables and columns shown in the schema.
- Never invent a table or column.
- Use the documented table relationships.
- Follow the documented business rules.
- Generate read-only SELECT queries only.
- Do not generate INSERT, UPDATE, DELETE, DROP, CREATE,
  ALTER, or other modifying statements.
- If the user's question is genuinely ambiguous,
  do not invent an interpretation.

{schema_context}

USER QUESTION
=============

{question}

Return only the SQL query.
""".strip()