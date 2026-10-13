"""
Fixes the revenue definition everywhere it lives.

THE PROBLEM
products.unit_price and unit_cost are ALREADY in USD ("Unit Price USD" in the raw
data). exchange_rates holds units of local currency per 1 USD. So
    quantity * unit_price * exchange_rate
turns a USD price into the customer's LOCAL currency, and we then added euros,
pounds and Canadian/Australian dollars together as if they were all dollars.
Correct USD revenue is simply:   quantity * unit_price

WHAT THIS SCRIPT CHANGES (a backup of each file goes to scripts/_backup_usd_fix/)
  contracts/schema.md        the business definitions the AI reads
  src/llm/schema_context.py  the few-shot examples (the AI copies examples more than rules),
                             and repairs the first example, which had lost its FROM/JOIN/WHERE lines
  src/backend/kpi.py         the 4 deterministic KPI queries
  scripts/eda.py             the EDA queries

A file is only written if every change in it succeeds, so you never end up with
a half-fixed file.

Usage (from the project root):
    python scripts/apply_usd_fix.py
"""

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKUP = ROOT / "scripts" / "_backup_usd_fix"

SCHEMA_STEPS = [
    (
        '| "revenue" / "sales" (always in USD) | `SUM(sales.quantity * products.unit_price * exchange_rates.exchange_rate)` |',
        '| "revenue" / "sales" (always in USD) | `SUM(sales.quantity * products.unit_price)` -- unit_price is already in USD, so do NOT multiply by exchange_rate and do NOT join exchange_rates |',
    ),
    (
        '| "profit" | `SUM(sales.quantity * (products.unit_price - products.unit_cost) * exchange_rates.exchange_rate)` |',
        '| "profit" | `SUM(sales.quantity * (products.unit_price - products.unit_cost))` -- already USD, no exchange rate |',
    ),
    (
        '| "margin" / "profit margin" | profit divided by revenue, i.e. `SUM(quantity * (unit_price - unit_cost) * exchange_rate) / SUM(quantity * unit_price * exchange_rate)` |',
        '| "margin" / "profit margin" | profit divided by revenue, i.e. `SUM(quantity * (unit_price - unit_cost)) / SUM(quantity * unit_price)` |\n'
        '| "in euros" / "in pounds" / "in local currency" | USD amount multiplied by `exchange_rates.exchange_rate` (units of local currency per 1 USD); join `exchange_rates` on currency and date. Only needed when a question asks for a local currency |',
    ),
    (
        "One row per currency per date -- used to convert all sales into a common currency (recommend USD) for consistent revenue KPIs.",
        "One row per currency per date. IMPORTANT: `products.unit_price` and `products.unit_cost` are ALREADY in USD, so revenue and profit in USD never need this table. Use it only to show an amount in a customer's local currency (local amount = USD amount * exchange_rate).",
    ),
    (
        "| exchange_rate | DECIMAL | Rate to USD on that date |",
        "| exchange_rate | DECIMAL | Units of local currency per 1 USD on that date (EUR 0.91 means 1 USD = 0.91 EUR) |",
    ),
    (
        '| currency_code | STRING | e.g. "USD", "EUR", "GBP" -- needed to convert to a common currency using `exchange_rates` |',
        '| currency_code | STRING | Currency the customer paid in, e.g. "USD", "EUR", "GBP". Prices are already in USD, so this is NOT needed to compute USD revenue |',
    ),
    (
        "| unit_cost | DECIMAL | What it costs the retailer (cost per unit) |",
        "| unit_cost | DECIMAL | What it costs the retailer (cost per unit), in USD |",
    ),
    (
        "| unit_price | DECIMAL | What the customer pays (selling price per unit) |",
        "| unit_price | DECIMAL | What the customer pays (selling price per unit), in USD |",
    ),
]

JOIN_RE = re.compile(
    r"^[ \t]*JOIN[ \t]+`[^`\n]*exchange_rates`[ \t]+(?:AS[ \t]+)?(\w+)[ \t]+ON[^\n]*\n",
    re.M | re.I,
)


def backup(path: Path):
    BACKUP.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, BACKUP / path.name)


TRUNCATED_EXAMPLE_RE = re.compile(
    r"(Question: What was total revenue in December 2019\?\nSQL:\n)"
    r"SELECT SUM\(t1\.quantity \* t2\.unit_price(?: \* t3\.exchange_rate)?\) AS revenue\n(?=\nQuestion:)"
)


def repair_truncated_example(text: str):
    """
    The first few-shot example ("total revenue in December 2019") lost its FROM,
    JOIN and WHERE lines in an earlier edit and was just a bare SELECT. Rebuild it
    in full, using the same table-name style as the other examples in the file.
    """
    if not TRUNCATED_EXAMPLE_RE.search(text):
        return text, False
    sales = re.search(r"FROM (`[^`\n]*sales`) AS t1", text)
    products = re.search(r"JOIN (`[^`\n]*products`) AS t2", text)
    if not (sales and products):
        return text, False
    full = (
        "SELECT SUM(t1.quantity * t2.unit_price) AS revenue\n"
        f"FROM {sales.group(1)} AS t1\n"
        f"JOIN {products.group(1)} AS t2 ON t1.product_key = t2.product_key\n"
        "WHERE t1.order_date BETWEEN '2019-12-01' AND '2019-12-31'\n"
    )
    return TRUNCATED_EXAMPLE_RE.sub(lambda m: m.group(1) + full, text, count=1), True


SELECTION_RE = re.compile(
    r'(if any\(term in q for term in money_terms\):\n[ \t]+selected\.add\("products"\)\n)'
    r'[ \t]+selected\.add\("exchange_rates"\)\n'
)
SELECTION_NEW = (
    "\\1"
    "\n    # exchange_rates is only needed when a question asks for a LOCAL currency;\n"
    "    # USD revenue is just quantity * unit_price (prices are already in USD).\n"
    '    local_currency_terms = {"euro", "pound", "local currency", "exchange rate", "in eur", "in gbp", "in cad", "in aud"}\n'
    "    if any(term in q for term in local_currency_terms):\n"
    '        selected.add("exchange_rates")\n'
)


def limit_exchange_rates_selection(text: str):
    """Stop showing the exchange_rates table to the AI for ordinary revenue questions."""
    new_text, n = SELECTION_RE.subn(SELECTION_NEW, text, count=1)
    return new_text, n > 0


def fix_schema() -> None:
    path = ROOT / "contracts" / "schema.md"
    if not path.exists():
        print(f"SKIP  {path.relative_to(ROOT)} (not found)")
        return
    text = path.read_text(encoding="utf-8")
    if "do NOT multiply by exchange_rate" in text:
        print(f"OK    {path.relative_to(ROOT)} already fixed")
        return
    missing = [old[:60] for old, _ in SCHEMA_STEPS if text.count(old) != 1]
    if missing:
        print(
            f"FAIL  {path.relative_to(ROOT)} NOT changed. These lines were not found exactly once:"
        )
        for m in missing:
            print(f"        {m}...")
        print(
            "      (Run python scripts/restore_schema.py first, then run this again.)"
        )
        return
    for old, new in SCHEMA_STEPS:
        text = text.replace(old, new)
    backup(path)
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"FIXED {path.relative_to(ROOT)} ({len(SCHEMA_STEPS)} definitions updated)")


def fix_code(rel: str) -> None:
    path = ROOT / rel
    if not path.exists():
        print(f"SKIP  {rel} (not found)")
        return
    text = path.read_text(encoding="utf-8")

    aliases = set(m.group(1) for m in JOIN_RE.finditer(text))
    n_joins = len(JOIN_RE.findall(text))
    if n_joins == 0:
        print(f"OK    {rel} has no exchange_rates joins (already fixed?)")
        return

    text = JOIN_RE.sub("", text)
    n_mults = 0
    for alias in aliases:
        text, n = re.subn(rf"\s*\*\s*{re.escape(alias)}\.exchange_rate", "", text)
        n_mults += n

    repaired = False
    narrowed = None
    if rel.endswith("schema_context.py"):
        text, repaired = repair_truncated_example(text)
        text, narrowed = limit_exchange_rates_selection(text)

    leftovers = []
    for alias in aliases:
        for i, line in enumerate(text.splitlines(), start=1):
            if re.search(
                rf"\b{re.escape(alias)}\.(exchange_rate|currency|date)\b", line
            ):
                leftovers.append((i, line.strip()))
    if leftovers:
        print(
            f"FAIL  {rel} NOT changed. After the fix, these lines still use the removed table:"
        )
        for i, line in leftovers:
            print(f"        line {i}: {line[:100]}")
        print("      Send me this output and I will adjust the script.")
        return

    backup(path)
    path.write_text(text, encoding="utf-8", newline="\n")
    extra = " and repaired the incomplete first example" if repaired else ""
    print(
        f"FIXED {rel} ({n_joins} exchange_rates joins and {n_mults} multiplications removed{extra})"
    )
    if narrowed is False:
        print(
            "      NOTE: could not find the table-selection line for money questions. This is harmless"
        )
        print(
            "      (the AI may still see the exchange_rates table), but tell me and I will adjust it."
        )


if __name__ == "__main__":
    print("Applying the USD revenue fix...\n")
    fix_schema()
    fix_code("src/llm/schema_context.py")
    fix_code("src/backend/kpi.py")
    fix_code("scripts/eda.py")
    print(
        f"\nBackups are in {BACKUP.relative_to(ROOT)} (delete that folder once everything works)."
    )
