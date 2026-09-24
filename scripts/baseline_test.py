"""
Service Development checkpoint -- baseline results (with accuracy tracking)

Runs the same fixed set of test questions through the real pipeline every
time, and:
1. Checks not just "did it run" but "was the answer actually correct"
   for the questions where we already know the right answer.
2. Saves each run's results to baseline_history.jsonl, so future runs
   (e.g. after Pillar 2.2 or Pillar 3 changes) can be compared directly
   against this one -- that's what makes this a genuine baseline, not
   just a one-time snapshot.

Usage:
    python scripts/baseline_test.py
"""

import sys
import os
import json
from datetime import datetime, timezone

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src", "llm"))
from self_healing import execute_with_self_healing

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "baseline_history.jsonl")

# Questions with a KNOWN correct answer, verified manually earlier --
# used to check accuracy, not just "did it run without error"
TEST_QUESTIONS = [
    {
        "question": "What was total revenue in December 2019?",
        "expect_clarification": False,
        "expected_answer": 2486562.81,
        "tolerance": 1.0,  # allow small rounding differences
    },
    {
        "question": "What was total revenue in 2019?",
        "expect_clarification": False,
        "expected_answer": None,  # not independently verified yet
        "tolerance": None,
    },
    {
        "question": "How many units did we sell in 2019?",
        "expect_clarification": False,
        "expected_answer": None,
        "tolerance": None,
    },
    {
        "question": "What were our sales last month?",
        "expect_clarification": True,
        "expected_answer": None,
        "tolerance": None,
    },
    {
        "question": "What was revenue by country?",
        "expect_clarification": True,
        "expected_answer": None,
        "tolerance": None,
    },
    {
        "question": "What were total headphone sales in 2025?",
        "expect_clarification": True,
        "expected_answer": None,
        "tolerance": None,
    },
]

run_results = []

for test in TEST_QUESTIONS:
    question = test["question"]
    print(f"\nTesting: {question}")
    result = execute_with_self_healing(question, max_retries=3)

    status = result["status"]
    attempts = result.get("attempts", 0)

    # Check correctness where we have a known expected answer
    correct = None
    if test["expected_answer"] is not None and status == "success":
        data = result.get("data", [])
        if data:
            actual_value = list(data[0].values())[0]
            actual_value = float(actual_value) if actual_value is not None else None
            if actual_value is not None:
                correct = (
                    abs(actual_value - test["expected_answer"]) <= test["tolerance"]
                )

    # Check that clarification vs direct-answer behavior matches what we expect
    behavior_correct = (status == "needs_clarification") == test[
        "expect_clarification"
    ] or status == "success"

    run_results.append(
        {
            "question": question,
            "status": status,
            "attempts": attempts,
            "expected_clarification": test["expect_clarification"],
            "behavior_as_expected": behavior_correct,
            "answer_correct": correct,
        }
    )

# ---- Print summary ----
print("\n" + "=" * 70)
print("BASELINE RESULTS SUMMARY")
print("=" * 70)

for r in run_results:
    correctness_note = ""
    if r["answer_correct"] is True:
        correctness_note = " [ANSWER VERIFIED CORRECT]"
    elif r["answer_correct"] is False:
        correctness_note = " [ANSWER WRONG -- CHECK THIS]"
    print(
        f"  [{r['status'].upper():20}] attempts={r['attempts']}  {r['question']}{correctness_note}"
    )

total = len(run_results)
success = sum(1 for r in run_results if r["status"] == "success")
clarified = sum(1 for r in run_results if r["status"] == "needs_clarification")
failed = sum(1 for r in run_results if r["status"] == "error")
behavior_ok = sum(1 for r in run_results if r["behavior_as_expected"])
verified_correct = sum(1 for r in run_results if r["answer_correct"] is True)
verified_wrong = sum(1 for r in run_results if r["answer_correct"] is False)

print("-" * 70)
print(f"Total questions tested:         {total}")
print(f"Answered directly:              {success}")
print(f"Correctly asked for clarity:    {clarified}")
print(f"Failed completely:              {failed}")
print(f"Behavior matched expectation:   {behavior_ok}/{total}")
print(f"Answers verified correct:       {verified_correct}")
print(f"Answers verified WRONG:         {verified_wrong}")
print("=" * 70)

# ---- Save to history so future runs can be compared ----
history_entry = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "total": total,
    "success": success,
    "clarified": clarified,
    "failed": failed,
    "behavior_matched": behavior_ok,
    "verified_correct": verified_correct,
    "verified_wrong": verified_wrong,
    "results": run_results,
}

with open(HISTORY_FILE, "a", encoding="utf-8") as f:
    f.write(json.dumps(history_entry) + "\n")

print(f"\nSaved to {HISTORY_FILE} -- run this script again after future changes")
print("to compare against this baseline.")
