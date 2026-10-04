"""
Guards the contract the AI reads.
 
If contracts/schema.md loses its markdown structure (## headings, `backticks`,
| table pipes |) -- e.g. after copy-pasting rendered text -- the parser silently
finds NO tables and the AI is sent no schema, so it starts inventing columns.
These tests fail loudly instead.
 
Run from the project root:
    python -m pytest tests/test_schema_contract.py -v
"""
 
from src.llm.schema_context import parse_schema_sections, build_schema_context
 
EXPECTED_COLUMNS = {
    "sales": ["order_date", "order_number", "product_key", "quantity",
              "customer_key", "store_key", "currency_code", "delivery_date"],
    "products": ["product_key", "brand", "unit_cost", "unit_price", "category", "subcategory"],
    "customers": ["customer_key", "gender", "city", "country", "continent", "birthday"],
    "stores": ["store_key", "country", "state", "square_meters", "open_date"],
    "exchange_rates": ["date", "currency", "exchange_rate"],
}
 
 
def test_all_five_tables_are_parsed():
    tables = parse_schema_sections()["tables"]
    assert set(tables) == set(EXPECTED_COLUMNS), (
        f"Only parsed {sorted(tables)} -- is contracts/schema.md still valid markdown? "
        "Run: python scripts/restore_schema.py"
    )
 
 
def test_every_expected_column_is_listed():
    tables = parse_schema_sections()["tables"]
    for table, columns in EXPECTED_COLUMNS.items():
        section = tables.get(table, "")
        for column in columns:
            assert f"| {column} |" in section, f"{table}.{column} is missing from schema.md"
 
 
def test_business_terms_are_included():
    shared = parse_schema_sections()["shared"]
    assert shared, "No Relationships / Business terms sections were parsed"
    for term in ['"profit"', '"margin"', '"online sales"', "delivered"]:
        assert term in shared, f"business term {term} is missing"
 
 
def test_profit_question_gets_the_cost_column():
    context = build_schema_context("What's the profit margin on computers?")
    assert "unit_cost" in context
    assert "profit" in context.lower()