from src.backend.response_formatter import format_response, normalize_group_counts


def test_one_row_per_group_of_ones_becomes_a_single_count():
    # the exact shape Round 4 produced: 2,807 rows, each holding the number 1
    rows = [{"order_count": 1} for _ in range(2807)]
    result = format_response(
        "How many orders were worth more than $5,000?", "SELECT ...", rows
    )
    assert result["table"] == [{"order_count": 2807}]
    assert result["summary"] == "Order count: 2,807"
    assert result["chart"] is None


def test_varied_counts_collapse_for_a_how_many_question_with_many_rows():
    rows = [{"orders": 4 + (i % 9)} for i in range(3000)]
    result = format_response(
        "How many customers have placed more than 3 orders?", "SELECT ...", rows
    )
    assert result["table"] == [{"orders": 3000}]


def test_a_single_row_is_never_touched():
    rows = [{"order_count": 2807}]
    assert (
        normalize_group_counts("How many orders were worth more than $5,000?", rows)
        == rows
    )


def test_small_breakdowns_are_left_alone():
    rows = [{"orders": 120}, {"orders": 95}, {"orders": 310}]
    assert (
        normalize_group_counts(
            "How many orders were placed in 2018, 2019 and 2020?", rows
        )
        == rows
    )


def test_results_with_a_label_column_are_never_touched():
    rows = [{"brand": "A", "n": 1}, {"brand": "B", "n": 1}]
    assert (
        normalize_group_counts("How many products does each brand carry?", rows) == rows
    )


def test_grouped_questions_with_many_rows_are_left_alone():
    rows = [{"orders": i + 2} for i in range(25)]
    assert normalize_group_counts("How many orders per customer?", rows) == rows
    assert normalize_group_counts("How many orders did we get by month?", rows) == rows


def test_text_results_are_never_collapsed():
    rows = [{"city": "London"}, {"city": "Paris"}]
    assert normalize_group_counts("How many cities do we have?", rows) == rows


def test_the_original_formatter_behaviour_is_unchanged():
    rows = [
        {"category": "Computers", "revenue": 120000},
        {"category": "Audio", "revenue": 90000},
    ]
    result = format_response("Revenue by category", "SELECT ...", rows)
    assert result["table"] == rows
    assert result["chart"] == {
        "type": "bar",
        "x_field": "category",
        "y_field": "revenue",
    }
