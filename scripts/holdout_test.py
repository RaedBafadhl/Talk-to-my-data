"""
Holdout Test Set -- genuinely new questions, never tuned against

RULE: If a question here fails, do NOT go tweak the prompt specifically to
fix that exact question. That would defeat the entire purpose of this file.

A failure here is honest information about a real gap in how the system
generalizes -- it should inform broader improvements (better instructions,
more few-shot examples), not a patch aimed at one specific phrasing.

Run this occasionally (e.g. once a week, or before a big milestone) to
sanity-check that the system isn't just memorizing the golden set.

ROTATION LOG:
- Round 1 (initial): 8 questions, all new. Found and fixed a real bug
  (unaliased columns breaking on the hyphenated project ID).
- Round 2 (this version): kept 3 questions that were never the direct
  cause of a fix (still "clean"), retired 5 that were heavily analyzed
  during Round 1, added 5 genuinely new ones covering different metrics,
  dimensions, and one deliberate edge case (customer age -- not covered
  in schema.md's business terms yet, worth seeing how it's handled).

Usage:
    python scripts/holdout_test.py
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src", "llm"))
from self_healing import execute_with_self_healing

HOLDOUT_QUESTIONS = [
    # Kept from Round 1 -- never directly drove a fix, still reasonably "clean"
    "What is our average order value?",
    "What percentage of our customers are male?",
    "Which product category has the highest average price?",
    # New for Round 2
    "What's our busiest sales month, historically?",
    "How many products do we carry in the Cell Phones category?",
    "What's the price difference between our cheapest and most expensive product?",
    "Which continent generates the most revenue?",
    "What's the average age of our customers?",  # deliberate edge case -- "age" isn't a stored column, only birthday
]

if __name__ == "__main__":
    print("=" * 70)
    print("HOLDOUT TEST -- Round 2 (rotated set)")
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
