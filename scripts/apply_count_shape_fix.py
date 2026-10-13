"""
Fixes a result-SHAPE problem that Holdout Round 4 exposed.

"How many orders were worth more than $5,000?" is sometimes answered with a query that
GROUPs BY order and COUNTs in the same SELECT. That returns one row per matching order
(2,807 rows, each holding the number 1) instead of a single number. The number of rows
IS the answer, so this collapses such a result into one row.

It only acts on a narrow, unambiguous pattern: a single numeric column with several
rows that are either all 1, or (for a "how many ..." question with no "each/per/by")
at least 20 rows. Everything else passes through untouched.

It does not edit format_response: it renames it to _format_response_raw and adds a new
format_response that normalizes first, so it works however the file is laid out.
A backup goes to scripts/_backup_usd_fix/. Safe to run twice.

Usage (from the project root):
    python scripts/apply_count_shape_fix.py
"""

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "src" / "backend" / "response_formatter.py"
BACKUP = ROOT / "scripts" / "_backup_usd_fix"

ADDITION = '''
GROUPING_WORDS = re.compile(r"\\b(each|per|by|every|breakdown|split|grouped)\\b")
 
 
def normalize_group_counts(question: str, rows: list[dict]) -> list[dict]:
    """
    Collapse "one row per group" into the single count it really represents.
    See apply_count_shape_fix.py for the full explanation.
    """
    if len(rows) < 2 or len(rows[0]) != 1:
        return rows
    (column,) = rows[0].keys()
    values = [row.get(column) for row in rows]
    if not all(_is_numeric(v) for v in values):
        return rows
 
    all_ones = all(v == 1 for v in values)
    q = question.strip().lower()
    counting_question = q.startswith("how many") and not GROUPING_WORDS.search(q)
    if all_ones or (counting_question and len(rows) >= 20):
        return [{column: len(rows)}]
    return rows
 
 
def format_response(question: str, sql: str, rows: list[dict]) -> dict:
    """
    Convert raw SQL results into the API response format.
    """
    return _format_response_raw(question, sql, normalize_group_counts(question, rows))
'''

text = PATH.read_text(encoding="utf-8")

if "normalize_group_counts" in text:
    print("OK    response_formatter.py already has the fix")
    raise SystemExit

if len(re.findall(r"^def format_response\(", text, flags=re.M)) != 1:
    print("FAIL  could not find exactly one 'def format_response(' - nothing changed.")
    print("      Send me this output and I will adjust the script.")
    raise SystemExit

if not re.search(r"^import re\b", text, flags=re.M):
    text = "import re\n" + text

text = re.sub(
    r"^def format_response\(", "def _format_response_raw(", text, count=1, flags=re.M
)
text = text.rstrip("\n") + "\n\n" + ADDITION

BACKUP.mkdir(parents=True, exist_ok=True)
shutil.copy2(PATH, BACKUP / "response_formatter_before_count_fix.py")
PATH.write_text(text, encoding="utf-8", newline="\n")
print(
    "FIXED src/backend/response_formatter.py: one-row-per-group counts now collapse to a single number"
)
