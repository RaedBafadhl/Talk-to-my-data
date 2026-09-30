from typing import Any
from decimal import Decimal


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

# NOTE: Decimal added here -- BigQuery returns aggregated numeric results
# (SUM, AVG, etc.) as Decimal, not plain int/float. Without this, every
# chart and rich summary silently fails to detect the numeric column.
NUMBER_TYPES = (int, float, Decimal)


def _is_time_field(field_name: str) -> bool:
    """
    Checks if a time-related word appears anywhere in the field name, not
    just an exact match. Real generated SQL often produces names like
    'sales_year' or 'order_month' rather than the bare word -- an exact
    match alone would miss these, and since extracted date parts (e.g.
    EXTRACT(YEAR FROM ...)) are numeric, they'd otherwise never qualify as
    a chart axis at all under the numeric/text fallback below.
    """
    name = field_name.lower()
    return any(keyword in name for keyword in TIME_FIELDS)


def _is_numeric(value: Any) -> bool:
    return isinstance(value, NUMBER_TYPES) and not isinstance(value, bool)


def _find_numeric_field(rows: list[dict], exclude: str | None = None) -> str | None:
    """
    Find the first column containing numeric values.

    `exclude` skips a field already chosen for something else (e.g. the
    x-axis) -- without this, a numeric dimension field like an extracted
    year would get picked AGAIN as the y-axis value, plotting a field
    against itself.
    """

    if not rows:
        return None

    for field in rows[0].keys():
        if field == exclude:
            continue
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
        if _is_time_field(field):
            return field

    # Otherwise find a text/category field
    for field in fields:
        values = [row.get(field) for row in rows if row.get(field) is not None]

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
    y_field = _find_numeric_field(rows, exclude=x_field)

    if not x_field or not y_field:
        return None

    if _is_time_field(x_field):
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

        values = ", ".join(f"{key}: {value}" for key, value in row.items())

        return f"The query returned one result: {values}."

    dimension_field = _find_dimension_field(rows)
    numeric_field = _find_numeric_field(rows, exclude=dimension_field)

    if numeric_field and dimension_field:
        valid_rows = [row for row in rows if _is_numeric(row.get(numeric_field))]

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
