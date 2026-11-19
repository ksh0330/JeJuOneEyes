import json
from pathlib import Path


CATALOG = json.loads(Path(__file__).with_name("catalog.json").read_text(encoding="utf-8"))
MARKET_ID = "hub.market_mashup_2019"
ARRIVALS_ID = "ijto.monthly_arrivals"
ARRIVALS_METRIC = "arrivals_total"
DATASETS = {dataset["id"]: dataset for dataset in CATALOG["datasets"]}
ARRIVALS_DATASET = DATASETS[ARRIVALS_ID]
TIME_LABELS = {"hour": "시간", "day": "일", "month": "월"}


def sources_for_question(text: str) -> list[dict]:
    return [
        dataset
        for dataset in DATASETS.values()
        if any(alias in text for metric in dataset["metrics"] for alias in metric.get("aliases", ()))
    ]


def source_for_metrics(metrics: list[str]) -> dict | None:
    return next(
        (
            dataset for dataset in DATASETS.values()
            if metrics and set(metrics) <= {metric["id"] for metric in dataset["metrics"]}
        ),
        None,
    )


def combination_notes(sources: list[dict], requested_months: list[str]) -> list[str]:
    """Compare registered spatial units and observation periods of the selected datasets."""
    descriptions = [
        f"{source['title']} · {source['region_label']} · {TIME_LABELS[source['native_time_grain']]} 단위 · "
        f"{source['coverage']['start_month']}~{source['coverage']['end_month']}"
        for source in sources
    ]
    start = max(source["coverage"]["start_month"] for source in sources)
    end = min(source["coverage"]["end_month"] for source in sources)
    reasons = []
    if len({source["region_scheme"] for source in sources}) > 1:
        reasons.append("지역 단위가 달라 직접 결합할 수 없습니다.")
    if len({source["native_time_grain"] for source in sources}) > 1:
        reasons.append("시간 집계 단위가 달라 직접 결합할 수 없습니다.")
    if start > end:
        reasons.append("등록된 관측 기간이 겹치지 않습니다.")
    elif requested_months:
        unsupported = sorted({month for month in requested_months if not start <= month <= end})
        if unsupported:
            reasons.append(f"요청 월 {', '.join(unsupported)}은 두 자료의 공통 관측 기간({start}~{end}) 밖입니다.")
    source_ids = {source["id"] for source in sources}
    verified_join = any(
        {join["left_dataset"], join["right_dataset"]} == source_ids and join["status"] == "verified"
        for join in CATALOG["joins"]
    )
    if not verified_join:
        reasons.append("검증된 결합 규칙이 없어 각 자료를 따로 분석해 주세요.")
    return [*descriptions, *reasons]
