"""
Pillar 4.3 -- Golden Benchmark Evaluation Suite (v2)

Runs a fixed set of realistic business questions through the REAL pipeline
(schema-aware prompt -> Gemini -> safety check -> BigQuery -> self-healing)
and scores every answer against a value we verified independently.

What the score means:
  * "Verified" questions have an expected answer with a recorded source
    (EDA, kpi.py cross-check, BigQuery Console, direct SQL read-through).
    Only these are scored.
  * "Management" questions are the kind an executive would ask, but we have
    not verified their answers yet. They are RUN and PRINTED for manual
    review, never counted in the accuracy figure. After you verify one in
    BigQuery Console, add its expected value and it becomes a scored test.

Also reported: how often the first attempt was enough (vs. self-healing),
and response time -- both useful for the final presentation.

Usage (from the project root, venv active):
    python scripts/golden_benchmark.py
"""

import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "golden_benchmark_history.jsonl")


def q(question, category, expect=None, text=None, rows=None, clarify=False, source=""):
    """
    expect : list of (value, tolerance) alternatives for the FIRST number in the
             first result row. Alternatives let a ratio be accepted as either
             0.4281 or 42.81, since the AI may phrase it either way.
    text   : expected FIRST text value in the first row (e.g. top category).
    rows   : expected number of result rows.
    clarify: True if the correct behaviour is to ask a clarifying question.
    """
    return {
        "question": question,
        "category": category,
        "expect": expect,
        "text": text,
        "rows": rows,
        "clarify": clarify,
        "source": source,
        "verified": clarify
        or expect is not None
        or text is not None
        or rows is not None,
    }


BENCHMARK = [
    # ---- Revenue ----
    q(
        "What was total revenue in December 2019?",
        "Revenue",
        expect=[(2477295.85, 1)],
        source="BigQuery recompute (USD formula)",
    ),
    q(
        "What was total revenue in 2019?",
        "Revenue",
        expect=[(18264382.48, 100)],
        source="BigQuery recompute (USD formula)",
    ),
    q(
        "What was total revenue in 2018?",
        "Revenue",
        expect=[(12788960.66, 100)],
        source="BigQuery recompute (USD formula)",
    ),
    q(
        "What was total revenue in 2020?",
        "Revenue",
        expect=[(9294632.14, 100)],
        source="BigQuery recompute (USD formula)",
    ),
    q(
        "What was total revenue in 2016?",
        "Revenue",
        expect=[(6946793.56, 100)],
        source="BigQuery recompute (USD formula)",
    ),
    q(
        "What was the revenue growth from 2018 to 2019?",
        "Revenue",
        expect=[(0.4281, 0.005), (42.81, 0.05)],
        source="derived from the recomputed 2018 and 2019 revenue",
    ),
    # ---- Core KPIs ----
    q(
        "What is our average order value?",
        "KPI",
        expect=[(2117.89, 1)],
        source="BigQuery recompute (USD formula)",
    ),
    q(
        "What are the top 5 product categories by revenue?",
        "KPI",
        text="Computers",
        rows=5,
        source="kpi.py get_top_products",
    ),
    q(
        "Which continent generates the most revenue?",
        "KPI",
        text="North America",
        source="BigQuery recompute (USD formula)",
    ),
    q(
        "What's the profit margin on computers?",
        "KPI",
        expect=[(0.5843, 0.005), (58.43, 0.5)],
        source="BigQuery recompute (USD formula)",
    ),
    # ---- Scale ----
    q(
        "How many customer records are in our database?",
        "Scale",
        expect=[(15266, 1)],
        source="EDA",
    ),
    q(
        "How many physical stores do we have?",
        "Scale",
        expect=[(66, 0)],
        source="stores table: 67 rows incl. online store_key 0",
    ),
    q(
        "How many distinct customers have placed an order?",
        "Scale",
        expect=[(11887, 1)],
        source="EDA",
    ),
    q("How many total orders have we had?", "Scale", expect=[(26326, 1)], source="EDA"),
    # ---- Geography ----
    q(
        "What's the total revenue from GBP transactions?",
        "Geography",
        expect=[(7084088.12, 10)],
        source="BigQuery recompute (revenue by currency, in USD)",
    ),
    q(
        "How many customers live in London?",
        "Geography",
        expect=[(31, 0)],
        source="direct SQL read-through",
    ),
    q(
        "How many stores were opened after 2015?",
        "Geography",
        expect=[(4, 0)],
        source="direct SQL read-through",
    ),
    q(
        "Which store has the largest square footage?",
        "Geography",
        expect=[(8, 0)],
        source="direct SQL read-through (store 8, 2,105 m2)",
    ),
    # ---- Products ----
    q(
        "How many subcategories do we have under the Computers category?",
        "Products",
        expect=[(6, 0)],
        source="direct SQL read-through",
    ),
    q(
        "What's the price difference between our cheapest and most expensive product?",
        "Products",
        expect=[(3199.04, 1)],
        source="EDA (0.95 to 3,199.99)",
    ),
    q(
        "How many products does each brand carry?",
        "Products",
        rows=11,
        source="EDA (11 brands)",
    ),
    # ---- Customers & operations ----
    q(
        "What percentage of our customers are male?",
        "Customers",
        expect=[(50.75, 0.5)],
        source="EDA",
    ),
    q(
        "What's the average age of our customers?",
        "Customers",
        expect=[(57.8, 1)],
        source="EDA",
    ),
    q(
        "What percentage of orders have actually been delivered?",
        "Customers",
        expect=[(21.0, 1.0)],
        source="EDA (79.1% of lines undelivered)",
    ),
    # ---- Ambiguity: the right behaviour is to ask, not to guess ----
    q(
        "What were our sales last month?",
        "Ambiguity",
        clarify=True,
        source="golden set",
    ),
    q("What was revenue by country?", "Ambiguity", clarify=True, source="golden set"),
    # ---- Management-style: RUN and PRINTED for manual review, not scored ----
    q("Which quarter had the highest revenue?", "Management"),
    q("What's our customer retention rate?", "Management"),
    q("Which region underperformed this year compared to last year?", "Management"),
    q("What's our best and worst performing product category?", "Management"),
    q("How does online revenue compare to physical store revenue?", "Management"),
]


# -----------------------------------------------------------------------------
# Scoring (pure functions, no Gemini/BigQuery needed -- easy to test)
# -----------------------------------------------------------------------------
def _to_float(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float, Decimal)):
        return float(v)
    return None


def first_number(rows):
    if not rows:
        return None
    for v in rows[0].values():
        f = _to_float(v)
        if f is not None:
            return f
    return None


def first_text(rows):
    if not rows:
        return None
    for v in rows[0].values():
        if isinstance(v, str):
            return v
    return None


def brief(rows, limit=110):
    if not rows:
        return "(no rows)"
    text = ", ".join(f"{k}={v}" for k, v in rows[0].items())
    if len(rows) > 1:
        text += f"  [+{len(rows) - 1} more rows]"
    return text if len(text) <= limit else text[: limit - 3] + "..."


def check_result(test, result):
    """Returns {"passed": True|False|None, "reason": str, "got": str}. None = not scored."""
    status = result.get("status")
    data = result.get("data") or []
    got = (
        brief(data)
        if status == "success"
        else (result.get("clarification_question") or result.get("error") or "")
    )

    if test["clarify"]:
        ok = status == "needs_clarification"
        return {
            "passed": ok,
            "reason": ""
            if ok
            else f"should have asked a clarifying question, got '{status}'",
            "got": got,
        }

    if not test["verified"]:
        return {"passed": None, "reason": "", "got": got}

    if status != "success":
        what = (
            "asked for clarification instead of answering"
            if status == "needs_clarification"
            else f"status '{status}'"
        )
        return {"passed": False, "reason": what, "got": str(got)[:110]}

    problems = []
    if test["expect"] is not None:
        n = first_number(data)
        if n is None:
            problems.append("no numeric value returned")
        elif not any(abs(n - v) <= tol for v, tol in test["expect"]):
            wanted = " or ".join(
                f"{v:,}" + (f" (+/-{tol})" if tol else "") for v, tol in test["expect"]
            )
            problems.append(f"got {n:,.4f}, expected {wanted}")
    if test["text"] is not None:
        t = first_text(data)
        if t is None or t.strip().lower() != test["text"].lower():
            problems.append(f"got '{t}', expected '{test['text']}'")
    if test["rows"] is not None and len(data) != test["rows"]:
        problems.append(f"got {len(data)} rows, expected {test['rows']}")

    return {"passed": not problems, "reason": "; ".join(problems), "got": got}


def run(tests, executor):
    records = []
    for i, test in enumerate(tests, start=1):
        started = time.perf_counter()
        try:
            result = executor(test["question"], max_retries=3)
        except Exception as e:  # a crash is a failed answer, not a crashed benchmark
            result = {"status": "error", "error": str(e), "attempts": 0, "data": []}
        seconds = time.perf_counter() - started

        verdict = check_result(test, result)
        mark = {True: "PASS  ", False: "FAIL  ", None: "REVIEW"}[verdict["passed"]]
        print(f"[{i:>2}/{len(tests)}] {mark} {test['question']}  ({seconds:.1f}s)")
        if verdict["passed"] is False:
            print(f"          -> {verdict['reason']}")

        records.append(
            {
                "question": test["question"],
                "category": test["category"],
                "passed": verdict["passed"],
                "reason": verdict["reason"],
                "got": verdict["got"],
                "status": result.get("status"),
                "attempts": result.get("attempts", 0),
                "seconds": round(seconds, 1),
                "source": test["source"],
            }
        )
    return records


def report(records):
    scored = [r for r in records if r["passed"] is not None]
    passed = [r for r in scored if r["passed"]]
    answers = [r for r in scored if r["category"] != "Ambiguity"]
    clarifs = [r for r in scored if r["category"] == "Ambiguity"]

    print("\n" + "=" * 70)
    print("BENCHMARK RESULTS")
    print("=" * 70)
    for cat in sorted({r["category"] for r in records}):
        rs = [r for r in records if r["category"] == cat]
        sc = [r for r in rs if r["passed"] is not None]
        if sc:
            print(f"  {cat:<12} {sum(r['passed'] for r in sc)}/{len(sc)} correct")
        else:
            print(f"  {cat:<12} {len(rs)} run for manual review (not scored)")

    print("-" * 70)
    pct = (len(passed) / len(scored) * 100) if scored else 0.0
    print(f"Verified accuracy:            {len(passed)}/{len(scored)} ({pct:.1f}%)")
    if answers:
        print(
            f"  numeric/text answers:       {sum(r['passed'] for r in answers)}/{len(answers)}"
        )
    if clarifs:
        print(
            f"  asked when it should:       {sum(r['passed'] for r in clarifs)}/{len(clarifs)}"
        )

    ok_answers = [r for r in answers if r["status"] == "success"]
    if ok_answers:
        first = sum(1 for r in ok_answers if r["attempts"] == 1)
        print(
            f"Right on the first attempt:   {first}/{len(ok_answers)} ({first / len(ok_answers) * 100:.0f}%)"
        )
        healed = sum(1 for r in ok_answers if r["attempts"] > 1 and r["passed"])
        print(f"Rescued by self-healing:      {healed}")
    times = [r["seconds"] for r in records if r["seconds"] > 0]
    if times:
        print(
            f"Response time:                avg {statistics.mean(times):.1f}s, max {max(times):.1f}s"
        )

    failures = [r for r in scored if not r["passed"]]
    if failures:
        print("\nFAILURES (look for a shared cause before changing anything):")
        for r in failures:
            print(
                f"  - {r['question']}\n      {r['reason']}\n      returned: {r['got']}"
            )

    review = [r for r in records if r["passed"] is None]
    if review:
        print(
            "\nNEEDS MANUAL REVIEW (run the SQL in BigQuery Console, then add an expected value):"
        )
        for r in review:
            print(f"  - {r['question']}\n      status={r['status']}  {r['got']}")
    print("=" * 70)

    return {"scored": len(scored), "passed": len(passed), "accuracy_pct": round(pct, 1)}


def main():
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src", "llm"))
    from self_healing import execute_with_self_healing

    verified = sum(t["verified"] for t in BENCHMARK)
    print("=" * 70)
    print(
        f"GOLDEN BENCHMARK v2 -- {len(BENCHMARK)} questions ({verified} scored, {len(BENCHMARK) - verified} for manual review)"
    )
    print("=" * 70)

    records = run(BENCHMARK, execute_with_self_healing)
    summary = report(records)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **summary,
        "results": records,
    }
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"\nSaved to {HISTORY_FILE}")


if __name__ == "__main__":
    main()
