from decimal import Decimal

from src.backend.response_formatter import build_summary, _format_value


def test_money_has_dollar_sign_and_two_decimals():
    assert _format_value("revenue", Decimal("2486562.811897")) == "$2,486,562.81"
    assert _format_value("average_order_value", 2102.463955853) == "$2,102.46"


def test_margin_ratio_shows_as_percentage_not_dollars():
    # 0.584363933 used to display as "$0.58"
    assert _format_value("profit_margin", Decimal("0.584363933")) == "58.44%"


def test_growth_ratio_shows_as_percentage():
    assert _format_value("revenue_growth", Decimal("0.459528612")) == "45.95%"


def test_exchange_rate_is_not_a_percentage():
    assert _format_value("exchange_rate", Decimal("0.9106")) == "0.91"


def test_already_percent_values_get_a_percent_sign():
    assert _format_value("pct_of_total", Decimal("34.59")) == "34.59%"
    assert _format_value("male_percentage", 50.75330800471637) == "50.75%"


def test_counts_and_years_have_no_decimals():
    assert _format_value("units_sold", 49827) == "49,827"
    assert _format_value("sales_year", 2019) == "2019"


def test_plain_average_gets_two_decimals():
    assert _format_value("average_age", 57.77472815406774) == "57.77"


def test_single_value_summary_reads_cleanly():
    assert (
        build_summary("q", [{"revenue": Decimal("2486562.811897")}])
        == "Revenue: $2,486,562.81"
    )
    assert (
        build_summary("q", [{"average_age": 57.77472815406774}]) == "Average age: 57.77"
    )


def test_multi_row_summary_names_the_top_item():
    rows = [
        {"category": "Computers", "revenue": Decimal("19143319.652778")},
        {"category": "Audio", "revenue": Decimal("3147476.96")},
    ]
    assert (
        build_summary("q", rows)
        == "The highest revenue was $19,143,319.65 for Computers."
    )


def test_empty_period_gives_a_friendly_message():
    summary = build_summary("q", [{"total_revenue_last_month": None}])
    assert "No data found" in summary
    assert "2021" in summary
