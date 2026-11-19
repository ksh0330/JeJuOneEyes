"""Pure helpers that turn AnalysisResult v1 into screen text and tables.

Every number shown here comes from the engine result. Nothing is estimated
or re-aggregated beyond simple totals over the rows the engine returned.
"""

from collections import defaultdict
from datetime import date

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
SUBTOTAL_CODE = "observed_card_subtotal"


def dimension_ids(result: dict) -> list[str]:
    return [column["id"] for column in result["columns"] if column["unit"] is None]


def metric_columns(result: dict) -> list[dict]:
    return [column for column in result["columns"] if column["unit"] is not None]


def column_header(column: dict) -> str:
    return f"{column['label']} ({column['unit']})" if column["unit"] else column["label"]


def format_value(value, unit: str | None) -> str:
    if value is None:
        return "값 없음"
    if isinstance(value, str):
        return value
    if unit == "원":
        return f"{int(round(value)):,}원"
    return f"{value:,.0f}"


def table_rows(result: dict) -> list[dict]:
    """Rows keyed by column label (with unit), values formatted for reading."""
    rows = []
    for row in result["rows"]:
        rows.append(
            {column_header(column): format_value(row.get(column["id"]), column["unit"]) for column in result["columns"]}
        )
    return rows


def chart_series(result: dict, metric_id: str) -> tuple[str, dict]:
    """Return (kind, data) for one metric.

    kind is "bar" with {region: value} or "line" with {month: {region: value}}.
    """
    if "month" in dimension_ids(result):
        series: dict[str, dict[str, float]] = defaultdict(dict)
        for row in result["rows"]:
            series[row["month"]][row.get("region", "전체")] = row[metric_id]
        return "line", dict(sorted(series.items()))
    return "bar", {row.get("region", "전체"): row[metric_id] for row in result["rows"]}


def _region_totals(result: dict, metric_id: str) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for row in result["rows"]:
        if row.get(metric_id) is not None:
            totals[row.get("region", "전체")] += row[metric_id]
    return dict(totals)


def summary_lines(result: dict) -> list[str]:
    """Short answer built only from the returned rows."""
    if result["status"] != "ok":
        return []
    months = result["sources"][0]["observed_months"] if result["sources"] else []
    span = f"관측 {len(months)}개월({months[0]}~{months[-1]} 중)" if months else "관측월 정보 없음"
    lines = []
    for column in metric_columns(result):
        totals = _region_totals(result, column["id"])
        ordered = sorted(totals.items(), key=lambda item: item[1], reverse=True)
        values = ", ".join(f"{region} {format_value(value, column['unit'])}" for region, value in ordered)
        line = f"**{column['label']}** · {span} 합계: {values}."
        if len(ordered) >= 2 and ordered[1][1]:
            (top, top_value), (second, second_value) = ordered[0], ordered[1]
            gap = top_value - second_value
            line += (
                f" {top}이(가) {second}보다 {format_value(gap, column['unit'])} "
                f"({gap / second_value * 100:.1f}%) 많습니다."
            )
        if "month" in dimension_ids(result):
            peaks = []
            for region in totals:
                region_rows = [row for row in result["rows"] if row.get("region") == region and row.get(column["id"]) is not None]
                if region_rows:
                    peak = max(region_rows, key=lambda row: row[column["id"]])
                    peaks.append(f"{region} {peak['month']}")
            if peaks:
                line += f" 월 최고치: {', '.join(peaks)}."
        lines.append(line)
    return lines


def _plan_months(plan: dict) -> list[str]:
    start = date.fromisoformat(plan["period"]["start_month"] + "-01")
    end = date.fromisoformat(plan["period"]["end_month"] + "-01")
    months = []
    index, last = start.year * 12 + start.month - 1, end.year * 12 + end.month - 1
    while index <= last:
        months.append(f"{index // 12:04d}-{index % 12 + 1:02d}")
        index += 1
    return months


def month_coverage(plan: dict, result: dict) -> dict[str, list[str]]:
    """Split the requested period into used, excluded-by-request, and unobserved months."""
    in_period = _plan_months(plan)
    excluded = [month for month in in_period if int(month[5:]) in plan["exclude_months"]]
    requested = [month for month in in_period if month not in excluded]
    observed = sorted({month for source in result.get("sources", []) for month in source["observed_months"]})
    return {
        "observed": observed,
        "excluded": excluded,
        "unobserved": [month for month in requested if month not in observed],
    }


def sorted_issues(result: dict) -> list[dict]:
    return sorted(result["issues"], key=lambda issue: SEVERITY_ORDER.get(issue["severity"], 3))


def subtotal_notice(result: dict) -> str | None:
    for issue in result["issues"]:
        if issue["code"] == SUBTOTAL_CODE:
            return issue["message"]
    return None


def compare_with_previous(previous: dict | None, current: dict) -> list[dict]:
    """Before/after rows for metrics and groups present in both results."""
    if not previous or previous["status"] != "ok" or current["status"] != "ok":
        return []
    if dimension_ids(previous) != dimension_ids(current):
        return []
    dims = dimension_ids(current)
    before = {tuple(row.get(key) for key in dims): row for row in previous["rows"]}
    previous_ids = {column["id"] for column in metric_columns(previous)}
    rows = []
    for row in current["rows"]:
        key = tuple(row.get(dim) for dim in dims)
        old = before.get(key)
        if old is None:
            continue
        for column in metric_columns(current):
            if column["id"] not in previous_ids:
                continue
            old_value, new_value = old.get(column["id"]), row.get(column["id"])
            change = None if old_value is None or new_value is None else new_value - old_value
            rows.append(
                {
                    "구분": " · ".join(str(part) for part in key),
                    "지표": column["label"],
                    "직전 결과": format_value(old_value, column["unit"]),
                    "현재 결과": format_value(new_value, column["unit"]),
                    "차이": format_value(change, column["unit"]) if change is not None else "비교 불가",
                }
            )
    return rows
