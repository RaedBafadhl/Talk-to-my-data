"""
Golden Dataset -- formal evaluation set with known correct answers

This is the expanded, formal version of baseline_test.py's idea: a proper set
of test questions with pre-verified correct answers (a "golden dataset"),
used to compute a real accuracy percentage -- not just "did it run."

Run this to get: "X out of Y questions answered correctly" as a genuine,
repeatable metric you can quote in presentations and compare over time.

Usage:
    python scripts/golden_dataset.py
"""

import sys
import os
import json
from datetime import datetime, timezone

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src", "llm"))
from self_healing import execute_with_self_healing

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "golden_dataset_history.jsonl")

# The golden dataset: each entry has a question, whether it SHOULD trigger
# clarification, and (if not) the verified correct answer to check against.
# Grow this list over time -- more questions = a more trustworthy accuracy number.
GOLDEN_DATASET = [
    {
        "question": "What was total revenue in December 2019?",
        "expect_clarification": False,
        "expected_answer": 2486562.81,
        "tolerance": 1.0,
    },
    {
        "question": "What was total revenue in 2019?",
        "expect_clarification": False,
        "expected_answer": 18307017.97,
        "tolerance": 100.0,
    },
    {
        "question": "What was total revenue in 2018?",
        "expect_clarification": False,
        "expected_answer": 12543103.18,
        "tolerance": 100.0,
    },
    {
        "question": "What was total revenue in 2020?",
        "expect_clarification": False,
        "expected_answer": 9322165.94,
        "tolerance": 100.0,
    },
    {
        "question": "How many customer records are in our database?",
        "expect_clarification": False,
        "expected_answer": 15266,
        "tolerance": 1,
    },
    {
        "question": "How many physical stores do we have?",
        "expect_clarification": False,
        "expected_answer": 66,
        "tolerance": 0,
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
    {
        "question": "What was our profit last quarter?",
        "expect_clarification": True,
        "expected_answer": None,
        "tolerance": None,
    },
]


def check_result(test: dict, result: dict) -> dict:
    status = result["status"]
    attempts = result.get("attempts", 0)

    behavior_correct = (status == "needs_clarification") == test[
        "expect_clarification"
    ] or status == "success"

    answer_correct = None
    if test["expected_answer"] is not None and status == "success":
        data = result.get("data", [])
        if data:
            actual = list(data[0].values())[0]
            if actual is not None:
                answer_correct = (
                    abs(float(actual) - test["expected_answer"]) <= test["tolerance"]
                )

    return {
        "question": test["question"],
        "status": status,
        "attempts": attempts,
        "behavior_correct": behavior_correct,
        "answer_correct": answer_correct,
    }


if __name__ == "__main__":
    print("=" * 70)
    print(f"GOLDEN DATASET EVALUATION -- {len(GOLDEN_DATASET)} questions")
    print("=" * 70)

    results = []
    for test in GOLDEN_DATASET:
        print(f"\nTesting: {test['question']}")
        result = execute_with_self_healing(test["question"], max_retries=3)
        results.append(check_result(test, result))

    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    for r in results:
        note = ""
        if r["answer_correct"] is True:
            note = " [CORRECT]"
        elif r["answer_correct"] is False:
            note = " [WRONG ANSWER]"
        elif not r["behavior_correct"]:
            note = " [UNEXPECTED BEHAVIOR]"
        print(f"  [{r['status'].upper():20}] {r['question']}{note}")

    total = len(results)
    behavior_ok = sum(1 for r in results if r["behavior_correct"])
    verified = [r for r in results if r["answer_correct"] is not None]
    verified_correct = sum(1 for r in verified if r["answer_correct"])

    print("-" * 70)
    print(f"Total questions:                {total}")
    print(
        f"Behaved as expected:            {behavior_ok}/{total} ({behavior_ok / total * 100:.0f}%)"
    )
    if verified:
        print(
            f"Verified answers, accuracy:     {verified_correct}/{len(verified)} ({verified_correct / len(verified) * 100:.0f}%)"
        )
    print("=" * 70)

    # Save to history
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "behavior_ok": behavior_ok,
        "verified_total": len(verified),
        "verified_correct": verified_correct,
        "results": results,
    }
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"\nSaved to {HISTORY_FILE}")
