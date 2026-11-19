import json
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

from jsonschema import Draft202012Validator

from core.connectors.market_csv import MarketRow, read_market_rows


CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
PLAN_VALIDATOR = Draft202012Validator(
    json.loads((CONTRACTS / "analysis-plan.schema.json").read_text(encoding="utf-8"))
)
DATASET = json.loads((CONTRACTS / "examples" / "catalog.json").read_text(encoding="utf-8"))[
    "datasets"
][0]
SOURCE_YEAR = 2019
REGIONS = {"jeju.yeon_dong": "연동", "jeju.nohyeong_dong": "노형동"}
INDUSTRIES = {"food.korean_restaurant": "한식 음식점업"}
CARD_AMOUNT = "card_amount_krw"
VISIT_POPULATION = "visit_population_monthly_sum"
METRICS = {
    CARD_AMOUNT: {
        "label": "카드 이용금액",
        "unit": "원",
        "method": "선택한 업종의 이용금액 합계",
    },
    VISIT_POPULATION: {
        "label": "지역 전체 방문 유동인구 추정치",
        "unit": "월 누적 추정치 합계",
        "method": "지역·월·성별의 반복 값을 한 번씩 반영해 관측월을 합산",
    },
}
DIMENSIONS = {"region": "지역", "month": "월"}


def _issue(code: str, message: str, severity: str = "warning") -> dict:
    return {"code": code, "severity": severity, "message": message}


def _result(status: str, issues: list[dict], *, columns=(), rows=(), sources=()) -> dict:
    return {
        "schema_version": 1,
        "status": status,
        "columns": list(columns),
        "rows": list(rows),
        "sources": list(sources),
        "issues": issues,
    }


def _requested_months(period: dict, excluded: list[int]) -> set[str]:
    start = date.fromisoformat(f"{period['start_month']}-01")
    end = date.fromisoformat(f"{period['end_month']}-01")
    first = start.year * 12 + start.month - 1
    last = end.year * 12 + end.month - 1
    return {
        f"{index // 12:04d}-{index % 12 + 1:02d}"
        for index in range(first, last + 1)
        if index % 12 + 1 not in excluded
    }


def _metric_values(
    groups: dict[tuple[str, str], list[MarketRow]], metrics: list[str], industries: set[str]
) -> tuple[dict[str, dict], list[dict]]:
    values = {metric: {} for metric in metrics}
    sexes = {"남성", "여성"}
    expected_keys = {(industry, sex) for industry in industries for sex in sexes}
    card_conflicts = 0
    population_conflicts = 0
    repeated_population_rows = 0

    for key, group in groups.items():
        if CARD_AMOUNT in values:
            matching = [row for row in group if not industries or row.industry in industries]
            observed_keys = {(row.industry, row.sex) for row in matching}
            if len(observed_keys) != len(matching):
                card_conflicts += 1
            elif matching and expected_keys <= observed_keys and all(
                row.card_amount is not None for row in matching
            ):
                values[CARD_AMOUNT][key] = sum(
                    row.card_amount for row in matching if row.card_amount is not None
                )

        if VISIT_POPULATION in values:
            population_by_sex: dict[str, set[Decimal]] = defaultdict(set)
            observed_rows = 0
            for row in group:
                if row.visit_population is not None:
                    population_by_sex[row.sex].add(row.visit_population)
                    observed_rows += 1
            repeated_population_rows += observed_rows - sum(
                len(entries) for entries in population_by_sex.values()
            )
            if any(len(entries) > 1 for entries in population_by_sex.values()):
                population_conflicts += 1
            elif set(population_by_sex) == sexes:
                values[VISIT_POPULATION][key] = sum(
                    next(iter(entries)) for entries in population_by_sex.values()
                )

    issues = []
    if card_conflicts:
        issues.append(_issue("duplicate_card_rows", f"카드 집계 키가 중복된 지역·월 {card_conflicts}개를 계산에서 제외했습니다."))
    if population_conflicts:
        issues.append(_issue("conflicting_population", f"방문인구 값이 일치하지 않는 지역·월 {population_conflicts}개를 계산에서 제외했습니다."))
    if repeated_population_rows:
        issues.append(_issue("repeated_population", f"조회 범위에서 방문인구가 반복된 {repeated_population_rows:,}개 행을 확인했습니다. 지역·월·성별 관측값은 한 번만 집계합니다.", "info"))
    return values, issues


def run_analysis(plan: dict, csv_path: Path | str) -> dict:
    """Run AnalysisPlan v1 against the locally supplied public market CSV."""
    if not PLAN_VALIDATOR.is_valid(plan):
        return _result("needs_input", [_issue("invalid_plan", "지역·기간·지표와 제외할 월을 확인해 주세요.")])
    if set(plan["region_ids"]) - REGIONS.keys():
        return _result("unavailable", [_issue("unsupported_region", "이 시연에서 지원하는 비교 지역은 연동과 노형동입니다.")])
    if set(plan["industry_ids"]) - INDUSTRIES.keys() or set(plan["metrics"]) - METRICS.keys():
        return _result("unavailable", [_issue("unsupported_metric_or_industry", "이 시연에서 지원하는 업종과 지표를 선택해 주세요.")])
    if plan["operation"] == "trend" and "month" not in plan["group_by"]:
        return _result("needs_input", [_issue("trend_needs_month", "추이를 보려면 월 기준을 선택해 주세요.")])

    try:
        requested_months = _requested_months(plan["period"], plan["exclude_months"])
    except ValueError:
        requested_months = set()
    if not requested_months:
        return _result("needs_input", [_issue("empty_period", "시작·종료 월과 제외 조건을 확인해 주세요.")])

    regions = {REGIONS[region_id] for region_id in plan["region_ids"]}
    industries = {INDUSTRIES[industry_id] for industry_id in plan["industry_ids"]}
    try:
        observations = read_market_rows(
            Path(csv_path), DATASET["columns"], "제주시", regions, requested_months, source_year=SOURCE_YEAR
        )
    except OSError:
        return _result("unavailable", [_issue("source_unavailable", f"원출처에서 받은 {SOURCE_YEAR}년 공개 CSV를 연결해 주세요.")])
    except (UnicodeError, ValueError) as exc:
        message = "공개 CSV를 UTF-8 또는 CP949로 읽을 수 없습니다." if isinstance(exc, UnicodeError) else str(exc)
        return _result("error", [_issue("invalid_source", message, "error")])

    groups = defaultdict(list)
    for observation in observations:
        groups[observation.region, observation.month].append(observation)
    values, issues = _metric_values(groups, plan["metrics"], industries)
    common_months = sorted(
        month for month in {month for _, month in groups}
        if all((region, month) in metric_values for region in regions for metric_values in values.values())
    )
    if not common_months:
        issues.append(_issue("no_common_months", "선택한 지역과 지표 모두에서 관측된 공통 월이 없습니다."))
        return _result("no_data", issues)
    if len(common_months) < len(requested_months):
        issues.append(_issue("incomplete_coverage", f"요청한 {len(requested_months)}개월 중 모든 지역·지표에서 관측된 {len(common_months)}개월을 사용했습니다."))

    grouped = defaultdict(lambda: dict.fromkeys(plan["metrics"], 0))
    for region in sorted(regions):
        for month in common_months:
            dimensions = {"region": region, "month": month}
            group_key = tuple(dimensions[key] for key in plan["group_by"])
            for metric, metric_values in values.items():
                grouped[group_key][metric] += metric_values[region, month]

    columns = [{"id": key, "label": DIMENSIONS[key], "unit": None, "method": None} for key in plan["group_by"]]
    for metric in plan["metrics"]:
        column = {"id": metric, **METRICS[metric]}
        if metric == CARD_AMOUNT and not industries:
            column["label"] = "관측된 업종·성별의 카드 이용금액 소계"
            column["method"] = "CSV에 관측된 업종·성별 행의 이용금액 합계"
            issues.append(
                _issue(
                    "observed_card_subtotal",
                    "전체 업종 조회에는 업종·성별 자료가 빠져 있을 수 있습니다. "
                    "금액은 CSV에서 관측된 행의 소계입니다.",
                )
            )
        columns.append(column)
    rows = [
        {
            **dict(zip(plan["group_by"], group_key)),
            **{metric: float(value) if isinstance(value, Decimal) else value for metric, value in totals.items()},
        }
        for group_key, totals in sorted(grouped.items())
    ]
    sources = [{"dataset_id": DATASET["id"], "title": DATASET["title"], "reference": DATASET["reference"], "observed_months": common_months}]
    return _result("ok", issues, columns=columns, rows=rows, sources=sources)
