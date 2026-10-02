"""
Pillar 3.2 -- SQL Validation & Safety Guardrails

Enforces strict security rules on LLM-generated SQL queries before execution:
1. Enforces read-only SELECT or WITH (CTE) queries only.
2. Rejects any data modification or schema alteration commands (INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, etc.).
3. Rejects multi-statement queries (semicolon injections) and comment-based bypass attempts.
4. Uses AST parsing (sqlparse) alongside pattern detection for defense-in-depth.
"""

import re
from typing import Tuple
import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import DDL, DML, Keyword


FORBIDDEN_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE",
    "REPLACE", "GRANT", "REVOKE", "EXEC", "EXECUTE", "CALL", "MERGE",
    "SHUTDOWN", "INFORMATION_SCHEMA", "PG_SLEEP", "BENCHMARK"
}

FORBIDDEN_PATTERNS = [
    r";\s*\w+",                 # Multiple statements separated by semicolon
    r"--",                      # Single-line comment injection
    r"/\*.*?\*/",               # Multi-line comment injection
    r"\bUNION\b.*?\bSELECT\b",  # Potential UNION injection tricks outside CTE
]


def clean_sql(sql: str) -> str:
    """Removes markdown code blocks and strips leading/trailing whitespace."""
    text = sql.strip()
    if text.startswith("```sql"):
        text = text[6:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def is_read_only_statement(stmt: Statement) -> bool:
    """
    Checks if a parsed sqlparse Statement begins with a read-only keyword (SELECT or WITH).
    """
    first_token = stmt.get_type()
    # sqlparse get_type() returns 'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', etc.
    if first_token == "SELECT":
        return True
    
    # Handle WITH (Common Table Expressions)
    real_tokens = [t for t in stmt.tokens if not t.is_whitespace and not t.is_meta]
    if real_tokens:
        first_real = real_tokens[0].value.upper()
        if first_real in ("SELECT", "WITH"):
            return True

    return False


def validate_sql(sql: str) -> Tuple[bool, str]:
    """
    Validates a SQL query for safety and read-only compliance.

    Args:
        sql (str): Raw SQL string to validate.

    Returns:
        Tuple[bool, str]: (is_safe, error_message)
            - (True, "") if the query passes all security checks.
            - (False, reason) if rejected by guardrails.
    """
    cleaned = clean_sql(sql)
    if not cleaned:
        return False, "SQL query is empty."

    # 1. Check for forbidden pattern regexes (comments, multi-statements)
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, cleaned, re.IGNORECASE | re.DOTALL):
            return False, f"SQL safety violation: forbidden pattern or multi-statement detected ('{pattern}')."

    # 2. Check for forbidden keywords in uppercase
    tokens_upper = set(re.findall(r"\b[A-Z_]+\b", cleaned.upper()))
    intersect = tokens_upper.intersection(FORBIDDEN_KEYWORDS)
    if intersect:
        forbidden_found = ", ".join(sorted(intersect))
        return False, f"SQL safety violation: mutating or administrative keyword detected ({forbidden_found}). Only SELECT queries are permitted."

    # 3. Parse with sqlparse for AST level verification
    parsed = sqlparse.parse(cleaned)
    if not parsed:
        return False, "Failed to parse SQL query structure."

    if len(parsed) > 1:
        return False, "SQL safety violation: Multiple SQL statements in a single query are not allowed."

    stmt = parsed[0]
    if not is_read_only_statement(stmt):
        return False, f"SQL safety violation: Statement type '{stmt.get_type()}' is not permitted. Query must start with SELECT or WITH."

    return True, ""


if __name__ == "__main__":
    # Quick self-test
    test_cases = [
        ("SELECT * FROM `tgs-talk-to-data.retail_dw.sales` LIMIT 10", True),
        ("WITH cte AS (SELECT * FROM sales) SELECT * FROM cte", True),
        ("DELETE FROM sales WHERE 1=1", False),
        ("SELECT * FROM sales; DROP TABLE products", False),
        ("INSERT INTO sales VALUES (1,2,3)", False),
        ("SELECT * FROM sales -- bypass check", False),
    ]

    print("Running SQL Security Guardrail Tests:")
    for query, expected in test_cases:
        safe, msg = validate_sql(query)
        status = "PASSED" if safe == expected else "FAILED"
        print(f"[{status}] Query: '{query[:40]}...' -> Safe: {safe} (Msg: '{msg}')")
