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

MONEY_KEYWORDS = {
    "revenue",
    "profit",
    "price",
    "cost",
    "value",
    "margin",
    "aov",
    "order_value",
}

# NOTE: Decimal added -- BigQuery returns aggregated numeric results (SUM,
# AVG, etc.) as Decimal, not plain int/float. Without this, charts and rich
# summaries silently fail to detect the numeric column.
NUMBER_TYPES = (int, float, Decimal)


def _is_numeric(value: Any) -> bool:
    return isinstance(value, NUMBER_TYPES) and not isinstance(value, bool)


def _is_time_field(field_name: str) -> bool:
    """
    Checks if a time-related word appears anywhere in the field name, not
    just an exact match (real SQL often names columns like 'sales_year').
    """
    name = field_name.lower()
    return any(keyword in name for keyword in TIME_FIELDS)


def _is_money_field(field_name: str) -> bool:
    """Checks whether a field name suggests a monetary value (in USD)."""
    name = field_name.lower()
    return any(keyword in name for keyword in MONEY_KEYWORDS)


def _format_value(field_name: str, value: Any) -> str:
    """Formats a value for display, adding a $ prefix for money fields."""
    if _is_money_field(field_name) and _is_numeric(value):
        return f"${value:,.2f}"
    if _is_numeric(value):
        return f"{value:,}" if isinstance(value, int) else f"{value:,.2f}"
    return str(value)


def _find_numeric_field(rows: list[dict], exclude: str | None = None) -> str | None:
    """
    Find the first column containing numeric values.
    `exclude` skips a field already chosen for something else (e.g. the
    x-axis) -- otherwise a numeric dimension field (like an extracted year)
    could get picked again as the y-axis, plotting a field against itself.
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

    # Prefer date/time fields (checked first -- works even if the values
    # are numeric, e.g. an extracted year)
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
    """
    if len(rows) < 2:
        return None

    x_field = _find_dimension_field(rows)
    y_field = _find_numeric_field(rows, exclude=x_field)

    if not x_field or not y_field:
        return None

    chart_type = "line" if _is_time_field(x_field) else "bar"

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
    """
    if not rows:
        return "No matching data was found for this question."

    if len(rows) == 1:
        row = rows[0]
        values = ", ".join(
            f"{key}: {_format_value(key, value)}" for key, value in row.items()
        )
        return values.capitalize() + "."

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
                f"The highest {numeric_field.replace('_', ' ')} "
                f"was {_format_value(numeric_field, highest[numeric_field])} "
                f"for {highest.get(dimension_field)}."
            )

    return f"Found {len(rows)} results."


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
