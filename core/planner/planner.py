"""Turn questions, choices, and follow-up requests into AnalysisPlan v1.

This first planner is rule based and deterministic. The local SLM can later
produce the same `Extraction` and reuse plan building, follow-up merging, and
validation below.
"""

import copy
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from jsonschema import Draft202012Validator

from . import vocabulary as vocab

PLAN_VALIDATOR = Draft202012Validator(
    json.loads(
        (Path(__file__).resolve().parents[2] / "contracts" / "analysis-plan.schema.json").read_text(
            encoding="utf-8"
        )
    )
)

READY = "ready"
NEEDS_INPUT = "needs_input"
UNSUPPORTED = "unsupported"


@dataclass
class Clarification:
    """A question the user answers with a radio button or checkboxes."""

    field: str
    question: str
    options: list[tuple[str, object]]
    multi: bool = False


@dataclass
class PlannerResponse:
    status: str
    plan: dict | None
    clarifications: list[Clarification] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    changes: list[str] = field(default_factory=list)
    guide: dict | None = None  # structured guidance for requests that span datasets


@dataclass
class Extraction:
    """Conditions explicitly stated in one message. None means not mentioned."""

    region_ids: list[str] | None = None
    region_mode: str = "replace"
    asks_other_region: bool = False
    industry_ids: list[str] | None = None
    metrics: list[str] | None = None
    metric_mode: str = "replace"
    operation: str | None = None
    year: int | None = None
    months: list[int] | None = None
    exclude_add: set[int] = field(default_factory=set)
    exclude_remove: set[int] = field(default_factory=set)
    clear_excludes: bool = False
    ambiguous_summer: bool = False
    problems: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Text extraction

_RANGE = re.compile(r"(\d{1,2})\s*월?\s*(?:~|-|–|부터|에서)\s*(\d{1,2})\s*월(?:\s*까지)?")
_LIST = re.compile(r"(\d{1,2})\s*월?\s*(?:,|·|와|과|및|랑|하고)\s*(\d{1,2})\s*월")
_SINGLE = re.compile(r"(\d{1,2})\s*월")
_EXCLUDE_AFTER = re.compile(r"^\s*(?:을|를|은|는|만|도)?\s*(?:빼|제외|말고|뺀)")
_INCLUDE_AFTER = re.compile(
    r"^\s*(?:을|를|은|는|도)?\s*(?:다시\s*)?(?:포함|넣|빼지\s*말|제외하지\s*말)"
)
_CLEAR_EXCLUDES = re.compile(r"(제외\s*없이|빼지\s*말고\s*다시|제외\s*(?:조건)?\s*(?:없애|해제|취소)|전체\s*월|모든\s*(?:달|월)|1~12월\s*전체)")
_TREND = re.compile(r"(추이|월별|매월|달마다|월\s*단위|흐름)")
_COMPARE = re.compile(r"(합계로|총합|기간\s*합|합산해서|전체\s*합)")
_UNION = re.compile(r"(도\s|도$|같이|함께|추가|포함|까지|더\s)")
_REPLACE_METRIC = re.compile(r"(기준으로|로\s*바꿔|대신|만\s*보)")


def _month_mentions(text: str) -> list[tuple[list[int], str]]:
    """Return month groups and the text that follows each group."""
    taken = [False] * len(text)
    found: list[tuple[int, list[int], str]] = []
    for pattern, expand in ((_RANGE, True), (_LIST, False), (_SINGLE, False)):
        for match in pattern.finditer(text):
            if any(taken[match.start():match.end()]):
                continue
            numbers = [int(value) for value in match.groups() if value is not None]
            if expand and len(numbers) == 2 and numbers[0] <= numbers[1]:
                numbers = list(range(numbers[0], numbers[1] + 1))
            for index in range(match.start(), match.end()):
                taken[index] = True
            found.append((match.start(), numbers, text[match.end():match.end() + 12]))
    return [(numbers, after) for _, numbers, after in sorted(found)]


def _names_in(text: str, table: dict) -> list[str]:
    return [item_id for item_id, item in table.items() if any(alias in text for alias in item["aliases"])]


def extract(text: str) -> Extraction:
    text = " ".join(text.split())
    found = Extraction()

    region_ids = _names_in(text, vocab.REGIONS)
    known_labels = {item["label"] for item in vocab.REGIONS.values()}
    unknown_areas = [area for area in vocab.JEJU_AREAS if area in text and area not in known_labels]
    if unknown_areas:
        supported = "·".join(item["label"] for item in vocab.REGIONS.values())
        found.problems.append(
            f"{', '.join(unknown_areas)}은(는) 이 시연 자료에 아직 등록되지 않았습니다. "
            f"현재 비교할 수 있는 지역은 {supported}입니다."
        )
    if region_ids:
        found.region_ids = region_ids
        found.region_mode = "union" if _UNION.search(text) else "replace"
    elif re.search(r"(다른\s*지역|지역도|인접\s*지역|주변\s*지역)", text):
        found.asks_other_region = True

    if re.search(vocab.ALL_INDUSTRY_PATTERN, text):
        found.industry_ids = []
    else:
        industry_ids = _names_in(text, vocab.INDUSTRIES)
        if industry_ids:
            found.industry_ids = industry_ids
        unsupported = [word for word in vocab.UNSUPPORTED_INDUSTRY_WORDS if word in text]
        if unsupported:
            found.problems.append(
                f"'{unsupported[0]}' 업종은 이 시연에서 아직 분석하지 않습니다. "
                "한식 음식점업 또는 전체 업종(관측 소계)을 선택해 주세요."
            )

    metrics = _names_in(text, vocab.METRICS)
    if metrics:
        found.metrics = metrics
        found.metric_mode = "replace" if _REPLACE_METRIC.search(text) else "union"
    unsupported_metric = [word for word in vocab.UNSUPPORTED_METRIC_WORDS if word in text]
    if unsupported_metric:
        found.problems.append(
            "결제 건수·건당 이용액은 이 공개 자료의 등록 지표가 아니어서 계산하지 않습니다. "
            "카드 이용금액 또는 방문 유동인구를 선택해 주세요."
        )

    if _TREND.search(text):
        found.operation = "trend"
    elif _COMPARE.search(text):
        found.operation = "compare"

    year = re.search(r"(20\d{2})\s*년", text)
    if year:
        found.year = int(year.group(1))

    if _CLEAR_EXCLUDES.search(text):
        found.clear_excludes = True
    period_months: list[int] = []
    for numbers, after in _month_mentions(text):
        if any(not 1 <= number <= 12 for number in numbers):
            found.problems.append("월은 1부터 12 사이로 입력해 주세요.")
            continue
        if _INCLUDE_AFTER.search(after):
            found.exclude_remove.update(numbers)
        elif _EXCLUDE_AFTER.search(after):
            found.exclude_add.update(numbers)
        else:
            period_months.extend(numbers)
    if period_months:
        found.months = sorted(set(period_months))
    if re.search(r"여름\s*(?:을|를|은|는|만|철)?\s*(?:빼|제외|말고|뺀)", text):
        found.ambiguous_summer = True
    return found


# ---------------------------------------------------------------------------
# Plan building


def _period(year: int, months: list[int] | None) -> dict:
    first, last = (min(months), max(months)) if months else (1, 12)
    return {"start_month": f"{year}-{first:02d}", "end_month": f"{year}-{last:02d}"}


def _unselected_months(months: list[int] | None) -> set[int]:
    if not months:
        return set()
    return set(range(min(months), max(months) + 1)).difference(months)


def _group_by(operation: str) -> list[str]:
    return ["region", "month"] if operation == "trend" else ["region"]


def build_plan(
    *,
    operation: str,
    region_ids: list[str],
    industry_ids: list[str],
    metrics: list[str],
    start_month: str,
    end_month: str,
    exclude_months: list[int],
) -> dict:
    """Build a plan from explicit choices. Field order follows the contract."""
    order_regions = [item for item in vocab.REGIONS if item in region_ids] + [
        item for item in region_ids if item not in vocab.REGIONS
    ]
    order_metrics = [item for item in vocab.METRICS if item in metrics] + [
        item for item in metrics if item not in vocab.METRICS
    ]
    return {
        "schema_version": 1,
        "operation": operation,
        "period": {"start_month": start_month, "end_month": end_month},
        "region_ids": order_regions,
        "industry_ids": list(industry_ids),
        "metrics": order_metrics,
        "group_by": _group_by(operation),
        "exclude_months": sorted(set(exclude_months)),
    }


def plan_from_choices(
    *,
    operation: str,
    region_ids: list[str],
    industry_ids: list[str],
    metrics: list[str],
    start_month: str,
    end_month: str,
    exclude_months: list[int],
) -> PlannerResponse:
    """Choices UI entry point. Produces the same plan shape as text input."""
    missing = []
    if not region_ids:
        missing.append("지역을 하나 이상 선택해 주세요.")
    if not metrics:
        missing.append("지표를 하나 이상 선택해 주세요.")
    if start_month > end_month:
        missing.append("시작 월이 종료 월보다 늦습니다.")
    if missing:
        return PlannerResponse(UNSUPPORTED, None, notes=missing)
    plan = build_plan(
        operation=operation,
        region_ids=region_ids,
        industry_ids=industry_ids,
        metrics=metrics,
        start_month=start_month,
        end_month=end_month,
        exclude_months=exclude_months,
    )
    return _checked(plan)


def _summer_question() -> Clarification:
    return Clarification(
        field="exclude_months",
        question="'여름'에서 어느 달을 뺄까요?",
        options=[("7~8월", [7, 8]), ("6~8월", [6, 7, 8])],
    )


def _checked(plan: dict, **extra) -> PlannerResponse:
    errors = validation_messages(plan)
    if errors:
        return PlannerResponse(UNSUPPORTED, plan, notes=errors + extra.get("notes", []), changes=extra.get("changes", []))
    return PlannerResponse(READY, plan, **extra)


def validation_messages(plan: dict) -> list[str]:
    """Explain contract or period errors in user terms before running."""
    messages = []
    if not PLAN_VALIDATOR.is_valid(plan):
        messages.append("분석 조건 형식이 올바르지 않습니다. 선택지에서 지역·기간·지표를 다시 골라 주세요.")
        return messages
    start, end = plan["period"]["start_month"], plan["period"]["end_month"]
    if start > end:
        messages.append("시작 월이 종료 월보다 늦습니다.")
    first, last = int(start[5:]), int(end[5:])
    if start[:4] == end[:4] and set(range(first, last + 1)) <= set(plan["exclude_months"]):
        messages.append("기간 안의 모든 달이 제외되었습니다. 제외할 달을 줄여 주세요.")
    return messages


def plan_from_text(text: str) -> PlannerResponse:
    """First question: build a new plan, asking only for result-changing gaps."""
    found = extract(text)
    if found.problems:
        return PlannerResponse(UNSUPPORTED, None, notes=found.problems)

    notes, clarifications = [], []
    operation = found.operation or "compare"
    year = found.year or vocab.DATA_YEAR
    if not found.year and not found.months:
        notes.append(f"기간을 지정하지 않아 등록 자료의 전체 기간({vocab.DATA_YEAR}년 1~12월)을 사용합니다.")
    elif not found.year:
        notes.append(f"연도를 지정하지 않아 등록 자료 연도인 {vocab.DATA_YEAR}년으로 해석했습니다.")

    region_ids = found.region_ids or []
    if not region_ids:
        clarifications.append(
            Clarification(
                field="region_ids",
                question="어느 지역을 볼까요?",
                options=[(item["label"], item_id) for item_id, item in vocab.REGIONS.items()],
                multi=True,
            )
        )
    metrics = found.metrics or []
    if not metrics:
        clarifications.append(
            Clarification(
                field="metrics",
                question="어떤 지표를 볼까요?",
                options=[(item["label"], item_id) for item_id, item in vocab.METRICS.items()],
                multi=True,
            )
        )
    industry_ids = found.industry_ids
    if industry_ids is None:
        if metrics and "card_amount_krw" not in metrics:
            industry_ids = []  # 방문인구만 보는 경우 업종은 결과에 영향이 없다.
        else:
            clarifications.append(
                Clarification(
                    field="industry_ids",
                    question="카드 이용금액을 어느 업종 기준으로 볼까요?",
                    options=[
                        *((item["label"], [item_id]) for item_id, item in vocab.INDUSTRIES.items()),
                        (vocab.ALL_INDUSTRIES_LABEL, []),
                    ],
                )
            )
            industry_ids = []
    exclude = (_unselected_months(found.months) | found.exclude_add) - found.exclude_remove
    if found.ambiguous_summer:
        clarifications.append(_summer_question())

    plan = build_plan(
        operation=operation,
        region_ids=region_ids,
        industry_ids=industry_ids,
        metrics=metrics,
        **_period(year, found.months),
        exclude_months=sorted(exclude),
    )
    if clarifications:
        return PlannerResponse(NEEDS_INPUT, plan, clarifications=clarifications, notes=notes)
    return _checked(plan, notes=notes)


def apply_answers(response: PlannerResponse, answers: dict) -> PlannerResponse:
    """Fill clarification answers into the draft plan and re-validate."""
    plan = copy.deepcopy(response.plan)
    for clarification in response.clarifications:
        value = answers.get(clarification.field)
        if value is None or value == [] and clarification.field in {"region_ids", "metrics"}:
            return PlannerResponse(NEEDS_INPUT, plan, clarifications=response.clarifications, notes=response.notes)
        if clarification.field == "exclude_months":
            plan["exclude_months"] = sorted(set(plan["exclude_months"]) | set(value))
        else:
            plan[clarification.field] = list(value)
    plan = build_plan(
        operation=plan["operation"],
        region_ids=plan["region_ids"],
        industry_ids=plan["industry_ids"],
        metrics=plan["metrics"],
        start_month=plan["period"]["start_month"],
        end_month=plan["period"]["end_month"],
        exclude_months=plan["exclude_months"],
    )
    return _checked(plan, notes=response.notes, changes=response.changes)


def apply_followup(previous: dict, text: str) -> PlannerResponse:
    """Copy the previous plan and change only the fields the request names."""
    found = extract(text)
    if found.problems:
        return PlannerResponse(UNSUPPORTED, previous, notes=found.problems + ["이전 조건은 그대로 유지했습니다."])

    plan = copy.deepcopy(previous)
    clarifications: list[Clarification] = []
    notes: list[str] = []

    if found.region_ids is not None:
        regions = set(found.region_ids)
        if found.region_mode == "union":
            regions |= set(plan["region_ids"])
        plan["region_ids"] = list(regions)
    elif found.asks_other_region:
        remaining = [(item["label"], item_id) for item_id, item in vocab.REGIONS.items() if item_id not in plan["region_ids"]]
        if remaining:
            clarifications.append(Clarification("region_ids", "어느 지역을 추가할까요?", remaining, multi=True))
        else:
            supported = "·".join(item["label"] for item in vocab.REGIONS.values())
            return PlannerResponse(
                UNSUPPORTED,
                previous,
                notes=[f"이 시연 자료에서 비교할 수 있는 지역은 {supported}이며 이미 모두 포함되어 있습니다. 이전 조건을 유지했습니다."],
            )
    if found.industry_ids is not None:
        plan["industry_ids"] = found.industry_ids
    if found.metrics is not None:
        metrics = set(found.metrics)
        if found.metric_mode == "union":
            metrics |= set(plan["metrics"])
        plan["metrics"] = list(metrics)
    if found.operation:
        plan["operation"] = found.operation

    year = found.year or int(plan["period"]["start_month"][:4])
    exclude = set() if found.clear_excludes else set(plan["exclude_months"])
    if found.months:
        plan["period"] = _period(year, found.months)
        exclude = _unselected_months(found.months)
    elif found.year:
        plan["period"] = {
            "start_month": f"{year}-{plan['period']['start_month'][5:]}",
            "end_month": f"{year}-{plan['period']['end_month'][5:]}",
        }
    exclude = (exclude | found.exclude_add) - found.exclude_remove
    plan["exclude_months"] = sorted(exclude)
    if found.ambiguous_summer:
        clarifications.append(_summer_question())

    plan = build_plan(
        operation=plan["operation"],
        region_ids=plan["region_ids"],
        industry_ids=plan["industry_ids"],
        metrics=plan["metrics"],
        start_month=plan["period"]["start_month"],
        end_month=plan["period"]["end_month"],
        exclude_months=plan["exclude_months"],
    )
    changes = diff_plans(previous, plan)
    if clarifications:
        return PlannerResponse(NEEDS_INPUT, plan, clarifications=clarifications, changes=changes)
    if not changes:
        recognized = any(
            (
                found.region_ids, found.industry_ids is not None, found.metrics, found.operation,
                found.year, found.months, found.exclude_add, found.exclude_remove, found.clear_excludes,
            )
        )
        message = (
            "요청한 조건이 이미 현재 분석에 적용되어 있습니다."
            if recognized
            else "바꿀 조건을 찾지 못했습니다. 예: '7~8월 빼고 다시', '방문인구도 같이', '월별 추이로'. "
            "아래 선택지에서 직접 바꿀 수도 있습니다."
        )
        return PlannerResponse(UNSUPPORTED, previous, notes=[message])
    return _checked(plan, changes=changes, notes=notes)


# ---------------------------------------------------------------------------
# Display helpers


def _labels(ids: list[str], table: dict) -> str:
    return ", ".join(table[item]["label"] if item in table else item for item in ids)


def describe_plan(plan: dict) -> list[tuple[str, str]]:
    """Plan fields in user words, in the order shown on screen."""
    excluded = plan["exclude_months"]
    has_card = "card_amount_krw" in plan["metrics"]
    if not has_card:
        industry = "해당 없음 (방문인구는 지역 전체 지표)"
    elif plan["industry_ids"]:
        industry = _labels(plan["industry_ids"], vocab.INDUSTRIES)
    else:
        industry = vocab.ALL_INDUSTRIES_LABEL
    return [
        ("목적", vocab.OPERATION_LABELS[plan["operation"]]),
        ("지역", _labels(plan["region_ids"], vocab.REGIONS) or "선택 필요"),
        ("기간", f"{plan['period']['start_month']} ~ {plan['period']['end_month']}"),
        ("업종", industry),
        ("분석 단위", " · ".join(vocab.GROUP_LABELS[item] for item in plan["group_by"])),
        ("지표", _labels(plan["metrics"], vocab.METRICS) or "선택 필요"),
        ("제외 조건", ", ".join(f"{month}월" for month in excluded) + " 제외" if excluded else "없음"),
    ]


def diff_plans(before: dict, after: dict) -> list[str]:
    """Human-readable list of changed plan fields."""
    old, new = dict(describe_plan(before)), dict(describe_plan(after))
    return [f"{name}: {old[name]} → {new[name]}" for name in new if old[name] != new[name]]
