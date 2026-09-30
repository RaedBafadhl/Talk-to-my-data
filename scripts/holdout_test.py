"""
Holdout Test Set -- genuinely new questions, never tuned against

RULE: If a question here fails, do NOT go tweak the prompt specifically to
fix that exact question. That would defeat the entire purpose of this file.

A failure here is honest information about a real gap in how the system
generalizes -- it should inform broader improvements (better instructions,
more few-shot examples), not a patch aimed at one specific phrasing.

Run this occasionally (e.g. once a week, or before a big milestone) to
sanity-check that the system isn't just memorizing previous rounds.

ROTATION LOG:
- Round 1: 8 questions. Found and fixed a real bug (unaliased columns
  breaking on the hyphenated project ID).
- Round 2: 8 questions (3 kept from Round 1, 5 new). Used heavily to debug
  and fix Pillar 2.2 (few-shot prompting) -- found and fixed: case-sensitive
  string matching, missing order-aggregation example, missing age-calculation
  example, and continent/stores confusion. Ended at 8/8 -- but by that point
  had been run 4 times with fixes applied between runs, so it had effectively
  become a second golden set, not a genuine holdout anymore. Retired.
- Round 3 (this version): 8 completely new questions, touching fields and
  patterns never tested in Round 1 or 2 (delivery dates, store open dates,
  subcategories, city-level granularity, currency filtering, brand counts,
  year-over-year comparison, store size). This is the first genuinely
  untouched read on how well Pillar 2.2's fixes generalize.

Usage:
    python scripts/holdout_test.py
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src", "llm"))
from self_healing import execute_with_self_healing

HOLDOUT_QUESTIONS = [
    "How many stores were opened after 2015?",
    "What's the total revenue from GBP transactions?",
    "How many subcategories do we have under the Computers category?",
    "Which store has the largest square footage?",
    "How many customers live in London?",
    "What percentage of orders have actually been delivered?",
    "How many products does each brand carry?",
    "What was the revenue growth from 2018 to 2019?",
]

if __name__ == "__main__":
    print("=" * 70)
    print("HOLDOUT TEST -- Round 3 (genuinely fresh set)")
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
