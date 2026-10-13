"""
Diagnostic: shows exactly what the AI is told for a question, and how often
it answers vs asks for clarification.

Usage (from the project root, venv active):
    python scripts/debug_prompt.py "What's the profit margin on computers?"
    python scripts/debug_prompt.py "What's the profit margin on computers?" --runs 5

Part 1 is free and instant (just reads your files).
Part 2 (--runs N) calls Gemini N times.
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src", "llm"))
from schema_context import build_system_prompt

args = [a for a in sys.argv[1:] if not a.startswith("--")]
question = args[0] if args else "What's the profit margin on computers?"
runs = 0
if "--runs" in sys.argv:
    runs = int(sys.argv[sys.argv.index("--runs") + 1])
    args = [a for a in args if a != str(runs)]
    question = args[0] if args else question

prompt = build_system_prompt(question)

print("=" * 70)
print(f"QUESTION: {question}")
print(f"Prompt length: {len(prompt):,} characters")
print("=" * 70)

print("\nPART 1 -- what the AI can see")
for term in ["unit_cost", "unit_price", "quantity", "exchange_rate"]:
    print(f"  column '{term}' in prompt: {term in prompt}")
for table in ["sales", "products", "customers", "stores", "exchange_rates"]:
    print(f"  table '{table}' mentioned: {table in prompt}")

print("\n  Lines mentioning profit / margin / unit_cost:")
shown = 0
for line in prompt.splitlines():
    low = line.lower()
    if "profit" in low or "margin" in low or "unit_cost" in low:
        print("   >", line.strip()[:160])
        shown += 1
if shown == 0:
    print("   (none -- the AI is NOT being told what profit or cost means)")

print("\n  Rules that tell the AI to ask instead of answer:")
for line in prompt.splitlines():
    if "CLARIFY" in line:
        print("   >", line.strip()[:160])

if runs:
    from generate_sql import generate_sql

    print(f"\nPART 2 -- asking Gemini {runs} time(s)")
    clarify = 0
    for i in range(1, runs + 1):
        out = generate_sql(question).strip()
        kind = "CLARIFY" if out.startswith("CLARIFY") else "SQL"
        clarify += kind == "CLARIFY"
        print(f"  run {i}: {kind:8} {out[:110].replace(chr(10), ' ')}")
    print(f"\n  Asked for clarification {clarify} of {runs} times")
