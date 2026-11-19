import re

from core.kg.catalog import ARRIVALS_DATASET, ARRIVALS_ID, ARRIVALS_METRIC, combination_notes, sources_for_question

from . import vocabulary as vocab
from .planner import READY, UNSUPPORTED, PlannerResponse, apply_followup, build_plan, plan_from_text


ARRIVALS_QUESTION = "2026년 9월 제주 입도객을 전년 동월과 비교해줘"
JOIN_QUESTION = "2026년 9월 제주 입도객과 같은 달 연동 한식 카드 이용금액을 결합해줘"
_YEAR_MONTH = re.compile(r"\b(20\d{2})\s*(?:년|-)\s*(1[0-2]|0?[1-9])\s*(?:월|(?!\d))")


def plan_registered_query(text: str, previous: dict | None = None) -> PlannerResponse:
    sources = sources_for_question(text)
    months = [f"{year}-{int(month):02d}" for year, month in _YEAR_MONTH.findall(text)]
    if len(sources) > 1:
        return PlannerResponse(UNSUPPORTED, previous, notes=combination_notes(sources, months))

    if sources and sources[0]["id"] == ARRIVALS_ID:
        districts = ("제주시", "서귀포", *vocab.JEJU_AREAS, *(item["label"] for item in vocab.REGIONS.values()))
        if any(district in text for district in districts) or re.search(r"내국인|외국인|지역별|공항별|항공편별", text):
            return PlannerResponse(UNSUPPORTED, previous, notes=["이 시연은 제주 전체의 월별 입도객 총계만 비교합니다."])
        if len(months) != 1 or not re.search(r"전년\s*동월|작년\s*(?:같은\s*달|동월)", text):
            return PlannerResponse(UNSUPPORTED, previous, notes=[f'연도와 월을 지정해 전년 동월 비교를 요청해 주세요. 예: "{ARRIVALS_QUESTION}"'])
        selected = months[0]
        year, month = selected.split("-")
        prior = f"{int(year) - 1}-{month}"
        coverage = ARRIVALS_DATASET["coverage"]
        start, end = coverage["start_month"], coverage["end_month"]
        if not start <= prior < selected <= end:
            return PlannerResponse(UNSUPPORTED, previous, notes=[f"등록 파일의 관측 범위는 {start}~{end}입니다. 비교할 두 월이 모두 있는 기간을 선택해 주세요."])
        plan = build_plan(
            operation="compare", region_ids=["jeju.province"], industry_ids=[],
            metrics=[ARRIVALS_METRIC], start_month=prior, end_month=selected,
            exclude_months=[value for value in range(1, 13) if value != int(month)],
        )
        plan["group_by"] = ["month"]
        return PlannerResponse(READY, plan)

    if previous and ARRIVALS_METRIC in previous["metrics"]:
        if sources:
            return plan_from_text(text)
        return PlannerResponse(UNSUPPORTED, previous, notes=[f'예시처럼 자료와 비교 월을 지정해 새 분석을 요청해 주세요. "{ARRIVALS_QUESTION}"'])
    return apply_followup(previous, text) if previous else plan_from_text(text)
