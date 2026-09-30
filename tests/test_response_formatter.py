from src.backend.response_formatter import format_response


def test_revenue_over_time():
    rows = [
        {"month": "2026-01", "revenue": 45200},
        {"month": "2026-02", "revenue": 48900},
        {"month": "2026-03", "revenue": 52100},
    ]

    result = format_response(
        question="Show me revenue by month",
        sql="SELECT month, revenue FROM ...",
        rows=rows,
    )

    assert result["status"] == "ok"

    assert result["table"] == rows

    assert result["chart"] == {
        "type": "line",
        "x_field": "month",
        "y_field": "revenue",
    }


def test_category_result():
    rows = [
        {"category": "Computers", "revenue": 120000},
        {"category": "Audio", "revenue": 90000},
        {"category": "Cameras", "revenue": 65000},
    ]

    result = format_response(
        question="Revenue by category",
        sql="SELECT category, revenue FROM ...",
        rows=rows,
    )

    assert result["chart"] == {
        "type": "bar",
        "x_field": "category",
        "y_field": "revenue",
    }


def test_single_value_has_no_chart():
    rows = [
        {"revenue": 425000}
    ]

    result = format_response(
        question="What is total revenue?",
        sql="SELECT SUM(...) AS revenue",
        rows=rows,
    )

    assert result["chart"] is None


def test_empty_result():
    result = format_response(
        question="Sales on Mars",
        sql="SELECT ...",
        rows=[],
    )

    assert result["table"] == []
    assert result["chart"] is None