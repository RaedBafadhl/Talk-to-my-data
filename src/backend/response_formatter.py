from typing import Any


TIME_FIELDS = {
    "date",
    "day",
    "week",
    "month",
    "quarter",
    "year",
    "order_date",
    "delivery_date",
}

NUMBER_TYPES = (int, float)


def _is_numeric(value: Any) -> bool:
    return isinstance(value, NUMBER_TYPES) and not isinstance(value, bool)


def _find_numeric_field(rows: list[dict]) -> str | None:
    """
    Find the first column containing numeric values.
    """

    if not rows:
        return None

    for field in rows[0].keys():
        for row in rows:
            value = row.get(field)

            if value is not None and _is_numeric(value):
                return field

    return None


def _find_dimension_field(rows: list[dict]) -> str | None:
    """
    Find a useful non-numeric field for the chart x-axis.
    """

    if not rows:
        return None

    fields = list(rows[0].keys())

    # Prefer date/time fields
    for field in fields:
        if field.lower() in TIME_FIELDS:
            return field

    # Otherwise find a text/category field
    for field in fields:
        values = [
            row.get(field)
            for row in rows
            if row.get(field) is not None
        ]

        if values and not all(_is_numeric(value) for value in values):
            return field

    return None


def build_chart_schema(rows: list[dict]) -> dict | None:
    """
    Decide whether the result should have a chart.

    Returns:
        {
            "type": "line",
            "x_field": "month",
            "y_field": "revenue"
        }

    or None.
    """

    # One value does not need a chart
    if len(rows) < 2:
        return None

    x_field = _find_dimension_field(rows)
    y_field = _find_numeric_field(rows)

    if not x_field or not y_field:
        return None

    if x_field.lower() in TIME_FIELDS:
        chart_type = "line"
    else:
        chart_type = "bar"

    return {
        "type": chart_type,
        "x_field": x_field,
        "y_field": y_field,
    }


def build_summary(
    question: str,
    rows: list[dict],
) -> str:
    """
    Create a simple deterministic summary.

    This can later be replaced or enhanced by an LLM.
    """

    if not rows:
        return "No matching data was found for this question."

    if len(rows) == 1:
        row = rows[0]

        values = ", ".join(
            f"{key}: {value}"
            for key, value in row.items()
        )

        return f"The query returned one result: {values}."

    numeric_field = _find_numeric_field(rows)
    dimension_field = _find_dimension_field(rows)

    if numeric_field and dimension_field:
        valid_rows = [
            row
            for row in rows
            if _is_numeric(row.get(numeric_field))
        ]

        if valid_rows:
            highest = max(
                valid_rows,
                key=lambda row: row[numeric_field],
            )

            return (
                f"The query returned {len(rows)} results. "
                f"The highest {numeric_field.replace('_', ' ')} "
                f"was {highest[numeric_field]:,.2f} "
                f"for {highest.get(dimension_field)}."
            )

    return f"The query returned {len(rows)} results."


def format_response(
    question: str,
    sql: str,
    rows: list[dict],
) -> dict:
    """
    Convert raw SQL results into the API response format.
    """

    return {
        "status": "ok",
        "sql": sql,
        "summary": build_summary(question, rows),
        "table": rows,
        "chart": build_chart_schema(rows),
    }