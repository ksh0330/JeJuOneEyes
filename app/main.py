"""JeJuOneEyes 분석 화면 (Streamlit).

실행: 저장소 루트에서 `streamlit run app/main.py`
질문·원자료·결과는 이 PC에서만 처리하며 외부로 보내지 않는다.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app import presenter  # noqa: E402
from core.analyzer import run_analysis  # noqa: E402
from core.analyzer.arrivals import run_arrivals  # noqa: E402
from core.kg.catalog import ARRIVALS_DATASET, ARRIVALS_ID, ARRIVALS_METRIC, source_for_metrics  # noqa: E402
from core.planner import (  # noqa: E402
    NEEDS_INPUT,
    READY,
    apply_answers,
    describe_plan,
    diff_plans,
    plan_from_choices,
)
from core.planner import vocabulary as vocab  # noqa: E402
from core.planner.registered_query import ARRIVALS_QUESTION, JOIN_QUESTION, plan_registered_query  # noqa: E402

DATA_DIR = ROOT / "data" / "local"
CSV_PATTERN = "*매쉬업결과_19.csv"
ARRIVALS_FILE = DATA_DIR / "jeju-arrivals.xlsx"
MONTH_OPTIONS = [f"{vocab.DATA_YEAR}-{month:02d}" for month in range(1, 13)]
SEVERITY_ICON = {"error": "⛔", "warning": "⚠️", "info": "ℹ️"}
ROLES = ("전체", "소상공인·예비창업자", "도민·학생·지역 연구자", "도내 기업 실무자", "공무원·공공기관 실무자")


# ---------------------------------------------------------------------------
# State


def init_state() -> None:
    defaults = {"turns": [], "pending": None, "notice": [], "question": "", "input_source": "자연어"}
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def reset_analysis() -> None:
    st.session_state.turns = []
    st.session_state.pending = None
    st.session_state.notice = []
    st.session_state.question = ""
    st.session_state.input_source = "자연어"


def default_csv() -> str:
    matches = sorted(DATA_DIR.glob(CSV_PATTERN)) if DATA_DIR.exists() else []
    return str(matches[0]) if matches else ""


@st.cache_data(show_spinner=False)
def cached_analysis(plan_json: str, path: str, modified: float, dataset_id: str | None) -> dict:
    plan = json.loads(plan_json)
    return run_arrivals(plan, path) if dataset_id == ARRIVALS_ID else run_analysis(plan, path)


def execute(plan: dict) -> dict:
    dataset = source_for_metrics(plan["metrics"])
    dataset_id = dataset["id"] if dataset else None
    local_path = st.session_state.arrivals_path if dataset_id == ARRIVALS_ID else st.session_state.csv_path
    path = Path(local_path)
    modified = path.stat().st_mtime if path.is_file() else 0.0
    return cached_analysis(json.dumps(plan, sort_keys=True), local_path, modified, dataset_id)


def handle(response, request: str, source: str) -> None:
    """Run a ready plan, park a plan that needs answers, or show why not."""
    st.session_state.notice = []
    if response.status == READY:
        st.session_state.pending = None
        st.session_state.turns.append(
            {
                "request": request,
                "source": source,
                "plan": response.plan,
                "changes": response.changes,
                "notes": response.notes,
                "result": execute(response.plan),
            }
        )
    elif response.status == NEEDS_INPUT:
        st.session_state.pending = {"response": response, "request": request, "source": source}
    else:
        st.session_state.pending = None
        st.session_state.notice = response.notes


def load_example(text: str) -> None:
    st.session_state.question = text
    st.session_state.input_source = "예시 질문(수정 가능)"


def submit_question() -> None:
    text = st.session_state.question.strip()
    if not text:
        st.session_state.notice = ["질문을 입력하거나 예시 질문을 눌러 주세요."]
        return
    handle(plan_registered_query(text), text, st.session_state.input_source)


def submit_followup(text: str | None = None) -> None:
    text = (text or st.session_state.get("followup_text", "")).strip()
    if not text:
        return
    previous = st.session_state.turns[-1]["plan"]
    handle(plan_registered_query(text, previous), text, "후속 요청")
    st.session_state.followup_text = ""


# ---------------------------------------------------------------------------
# Widgets


def choices_form(prefix: str, plan: dict | None, *, label: str) -> None:
    """Guided choices that build the same AnalysisPlan as text input."""
    plan = plan or {
        "operation": "compare",
        "region_ids": list(vocab.REGIONS),
        "industry_ids": list(vocab.INDUSTRIES),
        "metrics": ["card_amount_krw"],
        "period": dict(vocab.DATA_PERIOD),
        "exclude_months": [],
    }
    with st.form(f"{prefix}_form"):
        operation = st.radio(
            "분석 목적",
            options=list(vocab.OPERATION_LABELS),
            format_func=vocab.OPERATION_LABELS.get,
            index=list(vocab.OPERATION_LABELS).index(plan["operation"]),
            horizontal=True,
            key=f"{prefix}_operation",
        )
        st.markdown("**지역** (여러 곳 선택 가능)")
        region_cols = st.columns(len(vocab.REGIONS))
        regions = [
            region_id
            for column, (region_id, item) in zip(region_cols, vocab.REGIONS.items())
            if column.checkbox(item["label"], value=region_id in plan["region_ids"], key=f"{prefix}_region_{region_id}")
        ]
        industry_options = [*([item_id] for item_id in vocab.INDUSTRIES), []]
        industry_labels = [*(item["label"] for item in vocab.INDUSTRIES.values()), vocab.ALL_INDUSTRIES_LABEL]
        industry_index = industry_options.index(plan["industry_ids"]) if plan["industry_ids"] in industry_options else 0
        industry_choice = st.radio(
            "업종 (카드 이용금액에 적용)",
            options=range(len(industry_options)),
            format_func=lambda index: industry_labels[index],
            index=industry_index,
            horizontal=True,
            key=f"{prefix}_industry",
        )
        st.markdown("**지표** (여러 개 선택 가능)")
        metric_cols = st.columns(len(vocab.METRICS))
        metrics = [
            metric_id
            for column, (metric_id, item) in zip(metric_cols, vocab.METRICS.items())
            if column.checkbox(item["label"], value=metric_id in plan["metrics"], key=f"{prefix}_metric_{metric_id}")
        ]
        start_col, end_col = st.columns(2)
        start = start_col.selectbox(
            "시작 월", MONTH_OPTIONS, index=_month_index(plan["period"]["start_month"], 0), key=f"{prefix}_start"
        )
        end = end_col.selectbox(
            "종료 월", MONTH_OPTIONS, index=_month_index(plan["period"]["end_month"], 11), key=f"{prefix}_end"
        )
        excluded = st.multiselect(
            "기간 안에서 제외할 달",
            options=list(range(1, 13)),
            default=plan["exclude_months"],
            format_func=lambda month: f"{month}월",
            key=f"{prefix}_exclude",
        )
        submitted = st.form_submit_button(label, type="primary")
    if submitted:
        response = plan_from_choices(
            operation=operation,
            region_ids=regions,
            industry_ids=industry_options[industry_choice],
            metrics=metrics,
            start_month=start,
            end_month=end,
            exclude_months=excluded,
        )
        if st.session_state.turns and response.status == READY:
            response.changes = diff_plans(st.session_state.turns[-1]["plan"], response.plan)
        handle(response, "선택지로 조건 지정", "안내형 선택지")
        st.rerun()


def _month_index(month: str, fallback: int) -> int:
    return MONTH_OPTIONS.index(month) if month in MONTH_OPTIONS else fallback


def plan_table(plan: dict) -> None:
    if ARRIVALS_METRIC in plan["metrics"]:
        rows = [
            ("목적", "전년 동월 비교"),
            ("지역", ARRIVALS_DATASET["region_label"]),
            ("비교 월", f"{plan['period']['start_month']}, {plan['period']['end_month']}"),
            ("지표", "제주 전체 입도 관광객 확정치"),
        ]
    else:
        rows = describe_plan(plan)
    st.table(pd.DataFrame(rows, columns=["조건", "값"]).set_index("조건"))


def render_pending() -> None:
    pending = st.session_state.pending
    response = pending["response"]
    st.subheader("분석 계획 확인")
    st.caption(f"요청: {pending['request']}")
    plan_table(response.plan)
    for note in response.notes:
        st.caption(f"ℹ️ {note}")
    st.info("결과가 달라지는 조건이 빠졌거나 뜻이 여러 가지입니다. 아래에서 골라 주세요.")
    answers = {}
    with st.form("clarify_form"):
        for clarification in response.clarifications:
            labels = [label for label, _ in clarification.options]
            if clarification.multi:
                st.markdown(f"**{clarification.question}**")
                picked = [
                    value
                    for label, value in clarification.options
                    if st.checkbox(label, key=f"clarify_{clarification.field}_{label}")
                ]
                answers[clarification.field] = picked
            else:
                index = st.radio(
                    clarification.question,
                    options=range(len(labels)),
                    format_func=lambda i, labels=labels: labels[i],
                    key=f"clarify_{clarification.field}",
                )
                answers[clarification.field] = clarification.options[index][1]
        submitted = st.form_submit_button("이 조건으로 분석", type="primary")
    if submitted:
        handle(apply_answers(response, answers), pending["request"], pending["source"])
        st.rerun()


def render_result(turn: dict, previous: dict | None) -> None:
    result = turn["result"]
    plan = turn["plan"]
    if result["status"] != "ok":
        st.error("이 조건으로는 결과를 만들 수 없습니다.")
        for issue in presenter.sorted_issues(result):
            st.markdown(f"{SEVERITY_ICON.get(issue['severity'], '•')} {issue['message']} `{issue['code']}`")
        return

    st.markdown("#### 요약")
    for line in presenter.summary_lines(result):
        st.markdown(f"- {line}")
    st.caption("요약은 분석 엔진이 반환한 값만 사용합니다. 관찰된 차이의 원인은 추가 조사가 필요합니다.")

    notice = presenter.subtotal_notice(result)
    if notice:
        st.warning(f"**관측 소계 안내** · {notice}")

    st.markdown("#### 결과 표")
    st.dataframe(pd.DataFrame(presenter.table_rows(result)), hide_index=True, width="stretch")

    st.markdown("#### 차트")
    metrics = presenter.metric_columns(result)
    chart_cols = st.columns(len(metrics))
    for column, metric in zip(chart_cols, metrics):
        with column:
            st.caption(presenter.column_header(metric))
            kind, data = presenter.chart_series(result, metric["id"])
            if kind == "line":
                frame = pd.DataFrame.from_dict(data, orient="index").sort_index()
                frame.index.name = "월"
                st.line_chart(frame)
            else:
                frame = pd.DataFrame({presenter.column_header(metric): data})
                frame.index.name = "비교 월" if metric["id"] == ARRIVALS_METRIC else "지역"
                st.bar_chart(frame)

    comparison = presenter.compare_with_previous(previous["result"] if previous else None, result)
    if comparison and turn["changes"]:
        st.markdown("#### 직전 결과와 비교")
        st.dataframe(pd.DataFrame(comparison), hide_index=True, width="stretch")

    render_evidence(plan, result)


def render_evidence(plan: dict, result: dict) -> None:
    st.markdown("#### 근거")
    coverage = presenter.month_coverage(plan, result)
    for source in result["sources"]:
        if source["dataset_id"] == ARRIVALS_ID:
            details = f"원자료 {ARRIVALS_DATASET['origin']} · {ARRIVALS_DATASET['license']}"
        else:
            details = f"{vocab.DATA_YEAR}년 공개 CSV(로컬 파일)"
        st.markdown(f"- **출처**: [{source['title']}]({source['reference']}) · {details} · 자료 ID `{source['dataset_id']}`")
    st.markdown(
        f"- **실제 관측월** ({len(coverage['observed'])}개월): " + ", ".join(coverage["observed"])
    )
    if coverage["excluded"] and ARRIVALS_METRIC not in plan["metrics"]:
        st.markdown("- **요청으로 제외한 달**: " + ", ".join(coverage["excluded"]))
    if coverage["unobserved"]:
        st.markdown("- **요청 기간 중 계산에 쓰지 못한 달**: " + ", ".join(coverage["unobserved"]))

    st.markdown("**결과 컬럼과 계산 방법**")
    st.table(
        pd.DataFrame(
            [
                {"컬럼 ID": c["id"], "표시 이름(label)": c["label"], "단위": c["unit"] or "—", "계산 방법": c["method"] or "—"}
                for c in result["columns"]
            ]
        ).set_index("컬럼 ID")
    )

    st.markdown("**품질·한계 알림 (issues)**")
    issues = presenter.sorted_issues(result)
    if not issues:
        st.caption("엔진이 보고한 알림이 없습니다.")
    for issue in issues:
        st.markdown(f"{SEVERITY_ICON.get(issue['severity'], '•')} {issue['message']} `{issue['code']}`")

    with st.expander("분석 계획·결과 원본(JSON)"):
        st.json({"plan": plan, "result": result}, expanded=False)
        st.download_button(
            "집계 결과 JSON 내려받기",
            data=json.dumps({"plan": plan, "result": result}, ensure_ascii=False, indent=2),
            file_name="jeju-analysis-result.json",
            mime="application/json",
            help="공개 자료의 집계 결과만 담습니다. 센터 원자료 결과는 센터 반출 규정을 따릅니다.",
        )


def render_faq() -> None:
    with st.expander("자주 묻는 질문"):
        st.markdown(
            f"""
**이용 가능한 자료는?**
제주데이터허브 공개 [상권분석 매쉬업](https://jejudatahub.net/data/view/data/748) {vocab.DATA_YEAR}년 CSV는 연동·노형동의 카드 이용금액과 지역 전체 방문 유동인구를 제공합니다. 카드 지표는 한식 음식점업 또는 전체 업종(관측 소계)을 선택할 수 있습니다.
[제주관광공사 월별 입도 관광객 확정치]({ARRIVALS_DATASET['reference']})는 제주 전체 입도객의 전년 동월 비교를 제공합니다.

**결과의 근거는 어디서 보나요?**
결과 아래 '근거'에 출처, 실제로 계산에 쓴 관측월, 컬럼별 계산 방법, 품질 알림을 표시합니다.
방문인구는 같은 지역·월·성별 값이 업종 행마다 반복되므로 한 번만 반영하며, 월 누적 추정치이지 고유 방문자 수가 아닙니다.

**결과를 저장·반출할 수 있나요?**
공개 자료 집계 결과는 '분석 계획·결과 원본'에서 JSON으로 내려받을 수 있습니다.
센터 원자료를 쓴 결과는 센터의 이용·반출 조건을 따릅니다.
"""
        )


# ---------------------------------------------------------------------------
# Page


def main() -> None:
    st.set_page_config(page_title="제주 데이터 탐색 Agent", page_icon="📊", layout="wide")
    init_state()

    with st.sidebar:
        st.header("데이터 연결")
        st.session_state.setdefault("csv_path", default_csv())
        st.text_input("공개 CSV 경로 (로컬)", key="csv_path", help=f"data/local/ 에 원래 파일명으로 둔 {vocab.DATA_YEAR}년 CSV")
        if Path(st.session_state.csv_path).is_file():
            st.success("공개 CSV 연결됨")
        else:
            st.error("CSV를 찾을 수 없습니다. app/README.md의 준비 절차를 확인해 주세요.")
        st.session_state.setdefault("arrivals_path", str(ARRIVALS_FILE))
        st.text_input("입도객 XLSX 경로 (로컬)", key="arrivals_path")
        if Path(st.session_state.arrivals_path).is_file():
            st.success("입도객 XLSX 연결됨")
        else:
            st.caption("전년 동월 비교를 하려면 제주관광공사 XLSX를 연결해 주세요.")
        st.caption("질문·원자료·결과는 이 PC에서만 처리하며 외부로 전송하지 않습니다.")
        st.button("새 분석 시작 (조건 초기화)", on_click=reset_analysis, width="stretch")
        render_faq()

    st.title("제주 데이터 탐색·분석 Agent")
    st.caption(
        "질문을 입력하면 등록된 자료에서 조건을 정리해 집계하고, 표·차트와 근거를 보여줍니다."
    )

    for message in st.session_state.notice:
        st.warning(message)

    if st.session_state.pending:
        render_pending()
    elif not st.session_state.turns:
        render_start()

    if st.session_state.turns:
        render_turns()


def render_start() -> None:
    st.subheader("무엇을 알아볼까요?")
    role = st.radio("내 업무 (예시 순서만 바뀝니다)", ROLES, horizontal=True, key="role")
    registered_examples = (
        {"text": ARRIVALS_QUESTION, "role": "도내 기업 실무자"},
        {"text": JOIN_QUESTION, "role": "공무원·공공기관 실무자"},
    )
    examples = sorted((*vocab.EXAMPLE_QUESTIONS, *registered_examples), key=lambda example: example["role"] != role)
    st.markdown("**예시 질문** · 누르면 입력창에 불러와 고쳐 쓸 수 있습니다.")
    example_cols = st.columns(2)
    for index, example in enumerate(examples):
        example_cols[index % 2].button(
            example["text"],
            key=f"example_{index}",
            on_click=load_example,
            args=(example["text"],),
            width="stretch",
            help=example["role"],
        )
    st.text_area(
        "질문",
        key="question",
        placeholder="예: 2019년 연동과 노형동의 한식 음식점업 카드 이용금액을 비교해줘",
        height=90,
    )
    st.caption(f"입력 방식: {st.session_state.input_source}")
    st.button("분석하기", type="primary", on_click=submit_question)
    with st.expander("안내형 선택지로 조건 고르기"):
        choices_form("start", None, label="선택한 조건으로 분석")


def render_turns() -> None:
    turns = st.session_state.turns
    latest = turns[-1]
    previous = turns[-2] if len(turns) > 1 else None

    st.subheader("현재 분석")
    st.caption(f"요청: {latest['request']} · 입력 방식: {latest['source']}")
    left, right = st.columns([3, 2])
    with left:
        st.markdown("**분석 계획**")
        plan_table(latest["plan"])
    with right:
        st.markdown("**이번에 바뀐 조건**")
        if latest["changes"]:
            for change in latest["changes"]:
                st.markdown(f"- {change}")
        else:
            st.caption("첫 분석입니다.")
        for note in latest["notes"]:
            st.caption(f"ℹ️ {note}")
    render_result(latest, previous)

    st.divider()
    st.subheader("조건 바꿔 다시 분석")
    is_arrivals = ARRIVALS_METRIC in latest["plan"]["metrics"]
    if not is_arrivals:
        suggestion_cols = st.columns(len(vocab.FOLLOWUP_SUGGESTIONS))
        for column, suggestion in zip(suggestion_cols, vocab.FOLLOWUP_SUGGESTIONS):
            column.button(suggestion, key=f"suggest_{suggestion}", on_click=submit_followup, args=(suggestion,), width="stretch")
    followup_example = (
        "예: 2025년 9월 제주 입도객을 전년 동월과 비교해줘"
        if is_arrivals else "예: 7~8월 빼고 다시 / 노형동만 / 방문인구도 같이"
    )
    st.text_input("후속 요청", key="followup_text", placeholder=followup_example)
    st.button("후속 요청 실행", on_click=submit_followup, type="primary")
    if not is_arrivals:
        with st.expander("선택지로 현재 조건 직접 수정"):
            choices_form(f"edit_{len(turns)}", latest["plan"], label="수정한 조건으로 다시 분석")

    if len(turns) > 1:
        with st.expander(f"변경 이력 ({len(turns)}회 분석)"):
            for number, turn in enumerate(turns, start=1):
                totals = "; ".join(presenter.summary_lines(turn["result"])) or turn["result"]["status"]
                st.markdown(f"**{number}. {turn['request']}** ({turn['source']})")
                if turn["changes"]:
                    st.caption(" / ".join(turn["changes"]))
                st.caption(totals)


main()
