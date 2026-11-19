"""Planner vocabulary for the 2019 public market mashup demo.

Values here are internal meaning IDs from AnalysisPlan v1. Users never type
file names, column names, or SQL. Keep the IDs in sync with the analyzer's
supported set (tests/test_planner.py checks this).
"""

DATA_YEAR = 2019
DATA_PERIOD = {"start_month": f"{DATA_YEAR}-01", "end_month": f"{DATA_YEAR}-12"}

REGIONS = {
    "jeju.yeon_dong": {"label": "연동", "aliases": ("연동",)},
    "jeju.nohyeong_dong": {"label": "노형동", "aliases": ("노형동", "노형")},
}

INDUSTRIES = {
    "food.korean_restaurant": {"label": "한식 음식점업", "aliases": ("한식",)},
}
ALL_INDUSTRIES_LABEL = "전체 업종(관측 소계)"
ALL_INDUSTRY_PATTERN = r"(전체\s*업종|모든\s*업종|업종\s*전체|전\s*업종|업종\s*구분\s*없이|업종\s*상관\s*없이)"

METRICS = {
    "card_amount_krw": {
        "label": "카드 이용금액",
        "aliases": ("카드", "이용금액", "이용액", "매출"),
    },
    "visit_population_monthly_sum": {
        "label": "지역 전체 방문 유동인구",
        "aliases": ("방문인구", "방문 인구", "유동인구", "유동 인구", "방문객"),
    },
}

# Requests that the public file cannot answer in this demo.
UNSUPPORTED_METRIC_WORDS = ("건수", "건당", "결제 횟수", "이용자수", "이용자 수")
UNSUPPORTED_INDUSTRY_WORDS = (
    "중식", "일식", "양식", "서양식", "카페", "커피", "편의점", "주점", "술집",
    "숙박", "호텔", "골프", "주유", "슈퍼마켓", "빵집", "제과",
)

# Administrative dong/eup/myeon names in Jeju. Used only to explain that a
# named area is not registered for this demo; not used for data access.
JEJU_AREAS = (
    "일도1동", "일도2동", "이도1동", "이도2동", "삼도1동", "삼도2동", "용담1동", "용담2동",
    "건입동", "화북동", "삼양동", "봉개동", "아라동", "오라동", "외도동", "이호동", "도두동",
    "한림읍", "애월읍", "구좌읍", "조천읍", "한경면", "추자면", "우도면",
    "대정읍", "남원읍", "성산읍", "안덕면", "표선면",
    "송산동", "정방동", "중앙동", "천지동", "효돈동", "영천동", "동홍동", "서홍동",
    "대륜동", "대천동", "중문동", "예래동",
)

OPERATION_LABELS = {"compare": "기간 합계 비교", "trend": "월별 추이"}
GROUP_LABELS = {"region": "지역", "month": "월"}

EXAMPLE_QUESTIONS = (
    {
        "role": "소상공인·예비창업자",
        "text": "2019년 연동과 노형동의 한식 음식점업 카드 이용금액을 비교해줘",
    },
    {
        "role": "소상공인·예비창업자",
        "text": "연동과 노형동의 한식 음식점업 카드 이용금액 월별 추이를 보여줘",
    },
    {
        "role": "도민·학생·지역 연구자",
        "text": "2019년 연동과 노형동의 방문 유동인구를 월별로 비교해줘",
    },
    {
        "role": "도내 기업 실무자",
        "text": "연동 전체 업종 카드 이용금액을 노형동과 비교해줘",
    },
)

FOLLOWUP_SUGGESTIONS = (
    "7~8월 빼고 다시",
    "제외 없이 전체 월로 다시",
    "방문인구도 같이 보여줘",
    "월별 추이로 바꿔줘",
)
