"""
Holdout Test Set -- genuinely new questions, never tuned against

RULE: If a question here fails, do NOT go tweak the prompt specifically to
fix that exact question. That would defeat the entire purpose of this file.

A failure here is honest information about a real gap in how the system
generalizes -- it should inform broader improvements (better instructions,
more few-shot examples), not a patch aimed at one specific phrasing.

Run this occasionally (e.g. once a week, or before a big milestone) to
sanity-check that the system isn't just memorizing the golden set.

Usage:
    python scripts/holdout_test.py
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src", "llm"))
from self_healing import execute_with_self_healing

# These questions are DELIBERATELY different in phrasing and combination
# from anything in golden_dataset.py or baseline_test.py.
HOLDOUT_QUESTIONS = [
    "What is our average order value?",
    "How many customers do we have in Germany?",
    "Which brand sells the most?",
    "How many orders came from online sales?",
    "What percentage of our customers are male?",
    "What's the profit margin on computers?",
    "Show me units sold by store.",
    "Which product category has the highest average price?",
]

if __name__ == "__main__":
    print("=" * 70)
    print("HOLDOUT TEST -- genuinely new questions, not used to tune the system")
    print("=" * 70)
    print("Reminder: do NOT fix specific failures here by tweaking prompts.")
    print("Use results to spot general patterns worth improving instead.\n")

    for question in HOLDOUT_QUESTIONS:
        print("-" * 70)
        print(f"Question: {question}")
        result = execute_with_self_healing(question, max_retries=3)
        print(f"Status: {result['status']}  (attempts: {result.get('attempts', 0)})")
        if result["status"] == "success":
            print(f"Result: {result.get('data')}")
        elif result["status"] == "needs_clarification":
            print(f"Asked: {result.get('clarification_question')}")
        print()

    print("=" * 70)
    print("Review the results above as a team. Look for PATTERNS across")
    print("multiple failures, not one-off fixes for individual questions.")
    print("=" * 70)
