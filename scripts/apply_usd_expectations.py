"""
Updates the revenue figures we check against, to the corrected USD numbers from
scripts/recompute_usd_numbers.py. Touches only revenue-based numbers:

  scripts/golden_benchmark.py   expected answers + their source labels
  scripts/golden_dataset.py     the four revenue expectations
  src/backend/kpi.py            the "expect ..." text in its demo printout

Works whatever the file's line layout (your editor may reformat on save),
and is safe to run twice. Usage (from the project root):
    python scripts/apply_usd_expectations.py
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# old number -> new number (corrected USD formula)
NUMBERS = {
    "2486562.81": "2477295.85",  # revenue, December 2019
    "18307017.97": "18264382.48",  # revenue 2019
    "12543103.18": "12788960.66",  # revenue 2018
    "9322165.94": "9294632.14",  # revenue 2020
    "6850538.24": "6946793.56",  # revenue 2016
    "5449533.23": "7084088.12",  # revenue paid in GBP, shown in USD
    "2102.46": "2117.89",  # average order value
    "0.4595": "0.4281",  # growth 2018 -> 2019 (as a ratio)
    "45.95": "42.81",  # growth 2018 -> 2019 (as a percent)
    "0.5844": "0.5843",  # profit margin, Computers (ratio)
    "58.44": "58.43",  # profit margin, Computers (percent)
}

SOURCE = "BigQuery recompute (USD formula)"
# after the numbers are updated, refresh the source label that follows them
SOURCE_LABELS = {
    "2477295.85": SOURCE,
    "18264382.48": SOURCE,
    "12788960.66": SOURCE,
    "9294632.14": SOURCE,
    "6946793.56": SOURCE,
    "2117.89": SOURCE,
    "0.5843": SOURCE,
    "0.4281": "derived from the recomputed 2018 and 2019 revenue",
    "7084088.12": "BigQuery recompute (revenue by currency, in USD)",
}

FILES = [
    "scripts/golden_benchmark.py",
    "scripts/golden_dataset.py",
    "src/backend/kpi.py",
]


def replace_number(text: str, old: str, new: str):
    pattern = re.compile(rf"(?<![\d.]){re.escape(old)}(?![\d])")
    return pattern.subn(new, text)


for rel in FILES:
    path = ROOT / rel
    if not path.exists():
        print(f"SKIP    {rel} (not found)")
        continue
    text = path.read_text(encoding="utf-8")
    changed = 0
    for old, new in NUMBERS.items():
        text, n = replace_number(text, old, new)
        changed += n

    relabeled = 0
    if rel.endswith("golden_benchmark.py"):
        for number, label in SOURCE_LABELS.items():
            pattern = re.compile(
                rf'(expect\s*=\s*\[\({re.escape(number)},[^\]]*\]\s*,\s*source\s*=\s*)"[^"]*"',
                re.S,
            )
            counter = [0]

            def swap(m, label=label, counter=counter):
                replacement = f'{m.group(1)}"{label}"'
                if m.group(0) != replacement:
                    counter[0] += 1
                return replacement

            text = pattern.sub(swap, text)
            relabeled += counter[0]

    if changed or relabeled:
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"UPDATED {rel}: {changed} numbers, {relabeled} source labels")
    else:
        print(f"OK      {rel}: nothing to change (already updated)")
