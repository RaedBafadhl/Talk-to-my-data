"""
Adds ONE few-shot example for a general pattern that Holdout Round 4 exposed:

    "How many <things> have <an aggregate condition>?"   e.g. customers with more than 3 orders

The AI counted inside the grouped query, which returns one row per group (2,807 rows
of "1") instead of a single number. The example shows the right shape: GROUP BY in a
subquery, then COUNT(*) around it.

It deliberately uses a DIFFERENT question from the one that failed, so Round 4 stays an
honest measurement. Safe to run twice. Usage (from the project root):
    python scripts/apply_having_example.py
"""

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "src" / "llm" / "schema_context.py"
BACKUP = ROOT / "scripts" / "_backup_usd_fix"

text = PATH.read_text(encoding="utf-8")

if "customers have placed more than 3 orders" in text:
    print("OK    the example is already in schema_context.py")
    raise SystemExit

sales = re.search(r"FROM (`[^`\n]*sales`) AS t1", text)
anchor = re.search(r"(WHERE EXTRACT\(YEAR FROM t1\.open_date\) > 2015\n)(\"\"\")", text)
if not (sales and anchor):
    print("FAIL  could not find the end of the examples block, nothing changed.")
    print("      Send me this output and I will adjust the script.")
    raise SystemExit

example = (
    "\nQuestion: How many customers have placed more than 3 orders?\n"
    "SQL:\n"
    "SELECT COUNT(*) AS customer_count\n"
    "FROM (\n"
    "  SELECT t1.customer_key\n"
    f"  FROM {sales.group(1)} AS t1\n"
    "  GROUP BY t1.customer_key\n"
    "  HAVING COUNT(DISTINCT t1.order_number) > 3\n"
    ") AS qualifying_customers\n"
)

new_text = text[: anchor.end(1)] + example + text[anchor.end(1) :]
BACKUP.mkdir(parents=True, exist_ok=True)
shutil.copy2(PATH, BACKUP / "schema_context_before_having_example.py")
PATH.write_text(new_text, encoding="utf-8", newline="\n")
print(
    "FIXED src/llm/schema_context.py: added the 'count groups that meet a threshold' example"
)
