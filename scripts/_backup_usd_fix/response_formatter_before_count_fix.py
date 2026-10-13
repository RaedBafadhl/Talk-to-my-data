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

# Money fields are shown as $1,234.56. "margin" is NOT here on purpose: a
# margin is a ratio (0.58 = 58%), handled separately below.
MONEY_KEYWORDS = {"revenue", "profit", "price", "cost", "value", "aov", "order_value"}
RATIO_KEYWORDS = ("margin", "growth", "rate", "share", "ratio", "retention")
PCT_KEYWORDS = ("pct", "percent")

# NOTE: Decimal added -- BigQuery returns aggregated numeric results (SUM,
# AVG, etc.) as Decimal, not plain int/float. Without this, charts and rich
# summaries silently fail to detect the numeric column.
NUMBER_TYPES = (int, float, Decimal)

DATA_RANGE_NOTE = "Our data covers January 2016 to February 2021."


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


def _value_kind(field_name: str, value: Any) -> str:
    """
    Decides how a number should be displayed:
    year | percent_points (already x100) | percent_fraction (0.58 -> 58%) |
    money | integer | number
    """
    name = field_name.lower()
    if "year" in name:
        return "year"
    if any(k in name for k in PCT_KEYWORDS):
        return "percent_points"
    if any(k in name for k in RATIO_KEYWORDS) and "exchange" not in name:
        if abs(value) <= 5:
            return "percent_fraction"
        if "margin" in name:
            return "money"  # a margin in dollars, not a ratio
        return "percent_points"
    if _is_money_field(name):
        return "money"
    return "integer" if isinstance(value, int) else "number"


def _format_value(field_name: str, value: Any) -> str:
    """Formats a value for display: $ for money, % for ratios, 2 decimals."""
    if value is None:
        return "no data"
    if not _is_numeric(value):
        return str(value)

    kind = _value_kind(field_name, value)
    if kind == "year":
        return str(int(value))
    if kind == "money":
        return f"${value:,.2f}"
    if kind == "percent_fraction":
        return f"{value * 100:,.2f}%"
    if kind == "percent_points":
        return f"{value:,.2f}%"
    if kind == "integer":
        return f"{value:,}"
    return f"{value:,.2f}"


def _label(field_name: str) -> str:
    return field_name.replace("_", " ").strip()


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
        return f"No matching data was found for this question. {DATA_RANGE_NOTE}"

    if len(rows) == 1:
        row = rows[0]
        # e.g. "last month" in a dataset that ends in Feb 2021 -> NULL result
        if all(v is None for v in row.values()):
            return f"No data found for that period. {DATA_RANGE_NOTE}"

        text = ", ".join(
            f"{_label(key)}: {_format_value(key, value)}" for key, value in row.items()
        )
        return text[0].upper() + text[1:]

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
                f"The highest {_label(numeric_field)} "
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
