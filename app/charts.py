"""Result charts with labelled values. Data comes only from the engine result."""

import altair as alt
import pandas as pd

from app import presenter
from core.kg.catalog import ARRIVALS_METRIC

ACCENT = "#0F1B2D"
MUTED = "#9DB3CC"
SERIES = ["#0F1B2D", "#38BDF8", "#FF7A00", "#64748B"]


def _axis(unit: str | None) -> alt.Axis:
    if unit == "원":
        return alt.Axis(title=None, labelExpr="format(datum.value / 1e8, ',.0f') + '억원'", grid=True)
    if unit == "명":
        return alt.Axis(title=None, labelExpr="format(datum.value / 1e4, ',.0f') + '만명'", grid=True)
    return alt.Axis(title=None, format=",.0f", grid=True)


def metric_chart(result: dict, metric: dict) -> alt.Chart:
    """Bars for a comparison, lines for a monthly trend; values are written on the marks."""
    unit = metric["unit"]
    kind, data = presenter.chart_series(result, metric["id"])
    if kind == "line":
        rows = [
            {"월": month, "지역": region, "값": value, "표시": presenter.short_value(value, unit)}
            for month, by_region in data.items()
            for region, value in by_region.items()
        ]
        frame = pd.DataFrame(rows)
        base = alt.Chart(frame).encode(
            x=alt.X("월:N", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("값:Q", axis=_axis(unit)),
            color=alt.Color("지역:N", scale=alt.Scale(range=SERIES), legend=alt.Legend(orient="top", title=None)),
            tooltip=["지역", "월", alt.Tooltip("값:Q", format=",.0f", title=presenter.column_header(metric))],
        )
        return (base.mark_line(strokeWidth=2.5) + base.mark_circle(size=60)).properties(height=320)

    target = "비교 월" if metric["id"] == ARRIVALS_METRIC else "지역"
    items = list(data.items())
    if metric["id"] == ARRIVALS_METRIC:
        items.sort()
    top = max(value for _, value in items if value is not None) if items else None
    frame = pd.DataFrame(
        [
            {
                target: name,
                "값": value,
                "표시": presenter.short_value(value, unit),
                # Highlight the latest month, or the larger region.
                "강조": (name == items[-1][0]) if metric["id"] == ARRIVALS_METRIC else (value == top),
            }
            for name, value in items
        ]
    )
    base = alt.Chart(frame).encode(
        x=alt.X(f"{target}:N", title=None, sort=None, axis=alt.Axis(labelAngle=0, labelFontSize=13)),
        y=alt.Y("값:Q", axis=_axis(unit), scale=alt.Scale(zero=True)),
    )
    bars = base.mark_bar(size=72, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        color=alt.condition("datum['강조']", alt.value(ACCENT), alt.value(MUTED)),
        tooltip=[target, alt.Tooltip("값:Q", format=",.0f", title=presenter.column_header(metric))],
    )
    labels = base.mark_text(dy=-10, fontSize=14, fontWeight="bold", color="#1F2A30").encode(text="표시:N")
    return (bars + labels).properties(height=320)
