"""Demo helpers for `send.chart` (/test-chart* commands).

The Dooers app-web renders chart events with Recharts. Use these commands locally
or in Studio to verify chart wiring after upgrading the SDK.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any


def is_chart_test_command(message: str) -> bool:
    return message.strip().lower().startswith("/test-chart")


async def handle_chart_test(message: str, send: Any) -> AsyncIterator[Any]:
    """Handle /test-chart* commands. Yields chart (and optional help text) events."""
    msg = message.strip().lower()
    chart_name = msg[len("/test-chart") :].lstrip("-") or "all"

    sample_rows = [
        {"month": "Jan", "revenue": 120, "costs": 80},
        {"month": "Feb", "revenue": 180, "costs": 95},
        {"month": "Mar", "revenue": 150, "costs": 88},
        {"month": "Apr", "revenue": 210, "costs": 102},
    ]
    category_rows = [
        {"region": "North", "sales": 320},
        {"region": "South", "sales": 280},
        {"region": "East", "sales": 410},
        {"region": "West", "sales": 360},
    ]
    scatter_rows = [
        {"spend": 10, "conversions": 22},
        {"spend": 18, "conversions": 35},
        {"spend": 25, "conversions": 41},
        {"spend": 32, "conversions": 48},
        {"spend": 40, "conversions": 55},
    ]

    if chart_name in ("bar", "all"):
        yield send.chart(
            title="Monthly Revenue vs Costs",
            message="Bar chart comparing **revenue** and **costs** by month.",
            chart_type="bar",
            x_key="month",
            y_keys=["revenue", "costs"],
            data=sample_rows,
            series=[
                send.chart_series("revenue", label="Revenue"),
                send.chart_series("costs", label="Costs"),
            ],
            size="large",
            x_label="Month",
            y_label="USD (k)",
        )
    if chart_name in ("stacked", "stacked_bar", "all"):
        yield send.chart(
            title="Stacked Costs + Revenue",
            chart_type="stacked_bar",
            x_key="month",
            y_keys=["revenue", "costs"],
            data=sample_rows,
            size="large",
        )
    if chart_name in ("horizontal", "bar_horizontal", "all"):
        yield send.chart(
            title="Sales by Region",
            chart_type="bar_horizontal",
            x_key="region",
            y_keys=["sales"],
            data=category_rows,
            size="small",
        )
    if chart_name in ("small", "small-grid", "all"):
        yield send.chart(
            title="Sales by Region",
            chart_type="bar_horizontal",
            x_key="region",
            y_keys=["sales"],
            data=category_rows,
            size="small",
        )
        yield send.chart(
            title="Revenue Trend",
            chart_type="line",
            x_key="month",
            y_keys=["revenue"],
            data=sample_rows,
            size="small",
        )
        yield send.chart(
            title="Revenue Area",
            chart_type="area",
            x_key="month",
            y_keys=["revenue"],
            data=sample_rows,
            size="small",
        )
        yield send.chart(
            title="Sales Share",
            chart_type="donut",
            x_key="region",
            y_keys=["sales"],
            data=category_rows,
            size="small",
        )
    if chart_name in ("line", "all"):
        yield send.chart(
            title="Revenue Trend",
            chart_type="line",
            x_key="month",
            y_keys=["revenue"],
            data=sample_rows,
            size="medium",
        )
    if chart_name in ("area", "all"):
        yield send.chart(
            title="Revenue Area",
            chart_type="area",
            x_key="month",
            y_keys=["revenue", "costs"],
            data=sample_rows,
            size="medium",
        )
    if chart_name in ("pie", "all"):
        yield send.chart(
            title="Sales Share by Region",
            chart_type="pie",
            x_key="region",
            y_keys=["sales"],
            data=category_rows,
            size="medium",
        )
    if chart_name in ("donut", "all"):
        yield send.chart(
            title="Sales Share (Donut)",
            chart_type="donut",
            x_key="region",
            y_keys=["sales"],
            data=category_rows,
            size="medium",
        )
    if chart_name in ("scatter", "all"):
        yield send.chart(
            title="Spend vs Conversions",
            chart_type="scatter",
            x_key="spend",
            y_keys=["conversions"],
            data=scatter_rows,
            size="medium",
            x_label="Ad Spend (k)",
            y_label="Conversions",
        )
    if chart_name == "all":
        yield send.text(
            "Available chart test commands:\n"
            "- `/test-chart-bar`\n"
            "- `/test-chart-stacked`\n"
            "- `/test-chart-horizontal`\n"
            "- `/test-chart-line`\n"
            "- `/test-chart-area`\n"
            "- `/test-chart-pie`\n"
            "- `/test-chart-donut`\n"
            "- `/test-chart-scatter`\n"
            "- `/test-chart-small` — 4 small charts in a 2-column grid\n"
            "- `/test-chart-all` — show every chart type"
        )
    elif chart_name not in {
        "bar",
        "stacked",
        "stacked_bar",
        "horizontal",
        "bar_horizontal",
        "line",
        "area",
        "pie",
        "donut",
        "scatter",
        "small",
        "small-grid",
    }:
        yield send.text(f"Unknown chart type: `{chart_name}`. Try `/test-chart-all` to see available commands.")
