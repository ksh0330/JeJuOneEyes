"""Pure helpers that turn AnalysisResult v1 into screen text and tables.

Every number shown here comes from the engine result. Nothing is estimated
or re-aggregated beyond simple totals over the rows the engine returned.
"""

from collections import defaultdict
from datetime import date

from core.kg.catalog import ARRIVALS_METRIC
from core.planner import vocabulary as vocab

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
    """Return a categorical comparison or a monthly series for one metric."""
    if metric_id == ARRIVALS_METRIC:
        return "bar", {row["month"]: row[metric_id] for row in result["rows"]}
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
    if any(column["id"] == ARRIVALS_METRIC for column in result["columns"]):
        before, current = sorted(result["rows"], key=lambda row: row["month"])
        previous_count, current_count = before[ARRIVALS_METRIC], current[ARRIVALS_METRIC]
        difference = current_count - previous_count
        rate = f"{difference / previous_count * 100:+.2f}%" if previous_count else "전년 0명으로 산정 불가"
        return [
            f"{before['month']} {previous_count:,}명 → {current['month']} {current_count:,}명",
            f"전년 동월 대비 {difference:+,}명 (증감률 {rate})",
        ]
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
                f" {top}{josa(top, '이', '가')} {second}보다 {format_value(gap, column['unit'])} "
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


# ---------------------------------------------------------------------------
# Headline and reading aids. Every number comes from the engine result.


def josa(word: str, with_final: str, without_final: str) -> str:
    """Pick a Korean particle from the last syllable (이/가, 은/는, 으로/로)."""
    last = word[-1] if word else ""
    if "가" <= last <= "힣":
        final = (ord(last) - ord("가")) % 28
        if with_final == "으로" and final == 8:  # ㄹ 받침은 '로'
            return without_final
        return with_final if final else without_final
    if last.isdigit() and last in "013678":  # 영·일·삼·육·칠·팔
        if with_final == "으로" and last in "178":
            return without_final
        return with_final
    return without_final


def korean_number(value) -> str:
    """1123339 -> '112만 3,339', 33833494533 -> '338억 3,349만 4,533'. Exact, no rounding."""
    number = int(round(value))
    sign = "−" if number < 0 else ""
    number = abs(number)
    parts = []
    for size, unit in ((10**12, "조"), (10**8, "억"), (10**4, "만")):
        quotient, number = divmod(number, size)
        if quotient:
            parts.append(f"{quotient:,}{unit}")
    if number or not parts:
        parts.append(f"{number:,}")
    return sign + " ".join(parts)


def _readable(value, unit: str | None) -> str:
    if unit in ("원", "명"):
        return f"{korean_number(value)}{unit}"
    return f"{value:,.0f}"


def _month_label(month: str) -> str:
    return f"{int(month[:4])}년 {int(month[5:])}월"


def period_phrase(plan: dict, result: dict) -> str:
    """'2019년 1~12월(12개월)' or '2019년 1~12월 중 7·8월을 뺀 10개월'."""
    start, end = plan["period"]["start_month"], plan["period"]["end_month"]
    if start == end:
        base = _month_label(start)
    elif start[:4] == end[:4]:
        base = f"{int(start[:4])}년 {int(start[5:])}~{int(end[5:])}월"
    else:
        base = f"{_month_label(start)}~{_month_label(end)}"
    coverage = month_coverage(plan, result)
    observed = len(coverage["observed"])
    if coverage["excluded"]:
        dropped = "·".join(str(int(month[5:])) for month in coverage["excluded"])
        return f"{base} 중 {dropped}월을 뺀 {observed}개월"
    if coverage["unobserved"]:
        return f"{base} 중 관측된 {observed}개월"
    return base if start == end else f"{base}({observed}개월)"


def _arrivals_pair(result: dict) -> tuple[dict, dict]:
    before, current = sorted(result["rows"], key=lambda row: row["month"])
    return before, current


def headline(plan: dict, result: dict) -> str | None:
    """One sentence that answers the question, built from the returned rows."""
    if result["status"] != "ok" or not result["rows"]:
        return None
    if any(column["id"] == ARRIVALS_METRIC for column in result["columns"]):
        before, current = _arrivals_pair(result)
        previous_count, current_count = before[ARRIVALS_METRIC], current[ARRIVALS_METRIC]
        difference = current_count - previous_count
        opening = f"{_month_label(current['month'])} 제주 입도객은 {korean_number(current_count)}명으로,"
        if not previous_count:
            return f"{opening} 지난해 같은 달이 0명이어서 증감률은 산정하지 않습니다."
        if not difference:
            return f"{opening} 지난해 같은 달과 같습니다."
        direction = "늘었습니다" if difference > 0 else "줄었습니다"
        rate = abs(difference) / previous_count * 100
        return f"{opening} 지난해 같은 달보다 {korean_number(abs(difference))}명({rate:.2f}%) {direction}."

    metrics = metric_columns(result)
    if not metrics:
        return None
    column = metrics[0]
    subject = column["label"]
    if column["id"] == "card_amount_krw" and plan.get("industry_ids"):
        industries = ", ".join(vocab.INDUSTRIES[item]["label"] for item in plan["industry_ids"] if item in vocab.INDUSTRIES)
        subject = f"{industries} {subject}" if industries else subject
    unit = column["unit"]
    if unit not in ("원", "명"):
        subject = f"{subject}({unit})"
    totals = sorted(_region_totals(result, column["id"]).items(), key=lambda item: item[1], reverse=True)
    period = period_phrase(plan, result)
    if len(totals) == 1:
        region, value = totals[0]
        return f"{period} {region}의 {subject}{josa(subject.rstrip(')'), '은', '는')} {_readable(value, unit)}입니다."
    (top, top_value), (second, second_value) = totals[0], totals[1]
    values = ", ".join(f"{region} {_readable(value, unit)}" for region, value in totals)
    tail = values[-1]
    sentence = f"{period} {subject}{josa(subject.rstrip(')'), '은', '는')} {values}{josa(tail, '으로', '로')}"
    gap = top_value - second_value
    if not gap:
        return f"{sentence} 같습니다."
    rate = f"({gap / second_value * 100:.1f}%)" if second_value else ""
    return f"{sentence} {top}{josa(top, '이', '가')} {second}보다 {_readable(gap, unit)}{rate} 많습니다."


def scope_caption(plan: dict, result: dict) -> str:
    """Comparison target, time, unit, and how the difference is taken, for the table and chart."""
    if any(column["id"] == ARRIVALS_METRIC for column in result["columns"]):
        before, current = _arrivals_pair(result)
        return (
            f"비교 대상: {before['month']}와 {current['month']} (같은 달, 1년 차이) · 지역: 제주특별자치도 전체 · "
            f"단위: 명 · 차이 = {current['month']} − {before['month']}, 증감률 = 차이 ÷ {before['month']} × 100"
        )
    regions = ", ".join(dict.fromkeys(row.get("region", "전체") for row in result["rows"]))
    metrics = metric_columns(result)
    units = metrics[0]["unit"] if len(metrics) == 1 else ", ".join(f"{column['label']}({column['unit']})" for column in metrics)
    shape = "월별 값" if "month" in dimension_ids(result) else "기간 합계"
    return f"비교 대상: {regions} · 기간: {period_phrase(plan, result)} · 값: {shape} · 단위: {units}"


def _signed(value, unit: str | None) -> str:
    text = f"{abs(int(round(value))):,}{unit if unit in ('원', '명') else ''}"
    return ("+" if value > 0 else "−" if value < 0 else "") + text


def difference_row(result: dict) -> dict | None:
    """A '차이' row under a two-item comparison table, labelled with its direction."""
    if result["status"] != "ok" or len(result["rows"]) != 2:
        return None
    columns = result["columns"]
    if any(column["id"] == ARRIVALS_METRIC for column in columns):
        before, current = _arrivals_pair(result)
        difference = current[ARRIVALS_METRIC] - before[ARRIVALS_METRIC]
        rate = f" ({difference / before[ARRIVALS_METRIC] * 100:+.2f}%)".replace("-", "−") if before[ARRIVALS_METRIC] else ""
        metric = next(column for column in columns if column["id"] == ARRIVALS_METRIC)
        return {"관측월": f"차이 ({current['month']} − {before['month']})", column_header(metric): _signed(difference, "명") + rate}
    if dimension_ids(result) != ["region"]:
        return None
    first_metric = metric_columns(result)[0]["id"]
    top, second = sorted(result["rows"], key=lambda row: row.get(first_metric) or 0, reverse=True)
    row = {"지역": f"차이 ({top['region']} − {second['region']})"}
    for column in metric_columns(result):
        a, b = top.get(column["id"]), second.get(column["id"])
        if a is None or b is None:
            row[column_header(column)] = "비교 불가"
            continue
        rate = f" ({(a - b) / b * 100:+.1f}%)".replace("-", "−") if b else ""
        row[column_header(column)] = _signed(a - b, column["unit"]) + rate
    return row


def outside_coverage(plan: dict, coverage: dict) -> list[str]:
    """Requested months (after exclusions) that fall outside a dataset's registered coverage."""
    requested = [month for month in _plan_months(plan) if int(month[5:]) not in plan["exclude_months"]]
    return [month for month in requested if not coverage["start_month"] <= month <= coverage["end_month"]]


# ---------------------------------------------------------------------------
# 'Read as text' and 'numbers and charts' views. Same result, no recomputation.


def _is_arrivals(result: dict) -> bool:
    return any(column["id"] == ARRIVALS_METRIC for column in result["columns"])


def explain_lines(plan: dict, result: dict) -> list[str]:
    """Plain-language lines under the headline: what was compared, exact values, and limits."""
    if result["status"] != "ok" or not result["rows"]:
        return []
    if _is_arrivals(result):
        before, current = _arrivals_pair(result)
        return [
            f"{_month_label(before['month'])} {korean_number(before[ARRIVALS_METRIC])}명에서 "
            f"{_month_label(current['month'])} {korean_number(current[ARRIVALS_METRIC])}명으로 바뀌었습니다.",
            f"정확한 값: {before['month']} {before[ARRIVALS_METRIC]:,}명, {current['month']} {current[ARRIVALS_METRIC]:,}명.",
            "제주특별자치도 전체의 월별 확정치이며, 지역별·내외국인별 값은 이 비교에 들어가지 않습니다.",
            "증감의 원인은 이 자료만으로 알 수 없습니다.",
        ]
    lines = []
    regions = list(dict.fromkeys(row.get("region", "전체") for row in result["rows"]))
    shape = "월별 값" if "month" in dimension_ids(result) else "기간 합계"
    lines.append(f"{' · '.join(regions)}의 {period_phrase(plan, result)} {shape}를 비교했습니다.")
    for column in metric_columns(result):
        totals = sorted(_region_totals(result, column["id"]).items(), key=lambda item: item[1], reverse=True)
        exact = ", ".join(f"{region} {format_value(value, column['unit'])}" for region, value in totals)
        lines.append(f"정확한 값({column['label']} 합계): {exact}.")
    coverage = month_coverage(plan, result)
    if coverage["excluded"]:
        dropped = "·".join(str(int(month[5:])) for month in coverage["excluded"])
        lines.append(f"{dropped}월은 요청에 따라 계산에서 뺐습니다.")
    if coverage["unobserved"]:
        lines.append(f"요청 기간 중 {', '.join(coverage['unobserved'])}은 관측값이 없어 계산에 쓰지 못했습니다.")
    if any(column["id"] == "visit_population_monthly_sum" for column in metric_columns(result)):
        lines.append("방문 유동인구는 월 누적 추정치이며 고유 방문자 수가 아닙니다.")
    notice = subtotal_notice(result)
    if notice:
        lines.append(notice)
    lines.append("자료가 보여주는 차이까지만 설명합니다. 원인(점포 수, 관광 수요 등)은 추가 조사가 필요합니다.")
    return lines


def metric_cards(result: dict) -> list[dict]:
    """Exact value per compared item and the signed difference, for the numbers view."""
    if result["status"] != "ok" or not result["rows"]:
        return []
    if _is_arrivals(result):
        before, current = _arrivals_pair(result)
        difference = difference_row(result)
        return [
            {"label": f"{before['month']} 입도객", "value": f"{before[ARRIVALS_METRIC]:,}명"},
            {"label": f"{current['month']} 입도객", "value": f"{current[ARRIVALS_METRIC]:,}명"},
            {"label": f"차이 ({current['month']} − {before['month']})", "value": next(iter(v for k, v in difference.items() if k != "관측월"))},
        ]
    if dimension_ids(result) != ["region"]:
        return []
    column = metric_columns(result)[0]
    cards = [
        {"label": f"{row['region']} {column['label']}", "value": format_value(row.get(column["id"]), column["unit"])}
        for row in sorted(result["rows"], key=lambda row: row.get(column["id"]) or 0, reverse=True)
    ]
    difference = difference_row(result)
    if difference:
        cards.append({"label": difference["지역"], "value": difference[column_header(column)]})
    return cards


def short_value(value, unit: str | None) -> str:
    """Rounded label for chart bars. Exact values stay in the table."""
    if value is None:
        return ""
    if unit == "원" and abs(value) >= 10**8:
        return f"{value / 10**8:,.1f}억원"
    if unit == "명" and abs(value) >= 10**4:
        return f"{value / 10**4:,.1f}만명"
    return f"{value:,.0f}"
