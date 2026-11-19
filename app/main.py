"""제주한눈(JejuOneEyes) 분석 화면 (Streamlit).

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

from app import brand, charts, presenter  # noqa: E402
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
VIEW_TEXT, VIEW_NUMBERS = "글로 보기", "수치·그래프로 보기"
QUESTION_PLACEHOLDER = "예: 2019년 연동과 노형동의 한식 음식점업 카드 이용금액을 비교해줘"
ROLE_TAGS = {
    "소상공인·예비창업자": "소상공인",
    "도민·학생·지역 연구자": "도민·연구자",
    "도내 기업 실무자": "기업 실무자",
    "공무원·공공기관 실무자": "공공기관",
}
# Badge tones per role (theme colors: orange, blue=sky, gray=slate, violet=navy).
ROLE_BADGE = {"소상공인": "orange", "도민·연구자": "blue", "기업 실무자": "gray", "공공기관": "violet"}
QUICK_STARTS = (
    {
        "key": "qs_market",
        "tag": "2019 · 읍면동",
        "title": "2019년 상권 비교",
        "body": "연동·노형동 카드 이용금액과 방문 유동인구, 월별 추이, 특정 달 제외",
        "question": vocab.EXAMPLE_QUESTIONS[0]["text"],
    },
    {
        "key": "qs_arrivals",
        "tag": "2001–2026 · 제주 전체",
        "title": "입도객 전년 동월 비교",
        "body": "제주 전체 월별 확정치로 같은 달의 전년 대비 증감",
        "question": ARRIVALS_QUESTION,
    },
    {
        "key": "qs_join",
        "tag": "결합 판단",
        "title": "자료 결합 요청",
        "body": "두 자료를 합칠 수 있는지 확인하고, 각 자료로 대신 할 분석을 안내",
        "question": JOIN_QUESTION,
    },
)
CENTER_SCHEMAS = ("카드 이용 현황(읍면동)", "내국인 유동인구(읍면동)", "음식물쓰레기 배출 현황")
HISTORY_LIMIT = 8


# ---------------------------------------------------------------------------
# State


def init_state() -> None:
    defaults = {
        "turns": [], "pending": None, "notice": [], "guide": None, "question": "", "input_source": "자연어", "history": [],
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def reset_analysis() -> None:
    st.session_state.turns = []
    st.session_state.pending = None
    st.session_state.notice = []
    st.session_state.guide = None
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
    st.session_state.screen_version = st.session_state.get("screen_version", 0) + 1
    st.session_state.notice = []
    st.session_state.guide = None
    if response.status == READY:
        st.session_state.pending = None
        turn = {
            "request": request,
            "source": source,
            "plan": response.plan,
            "changes": response.changes,
            "notes": response.notes,
            "result": execute(response.plan),
        }
        st.session_state.turns.append(turn)
        st.session_state.history = [turn, *st.session_state.history][:HISTORY_LIMIT]
    elif response.status == NEEDS_INPUT:
        st.session_state.pending = {"response": response, "request": request, "source": source}
    else:
        st.session_state.pending = None
        st.session_state.notice = response.notes
        st.session_state.guide = response.guide


def load_example(text: str) -> None:
    st.session_state.question = text
    st.session_state.input_source = "예시 질문(수정 가능)"
    st.session_state.notice = []
    st.session_state.guide = None


def restore_turn(index: int) -> None:
    """Bring back a recent question with its conditions and result. Nothing is recomputed."""
    turn = st.session_state.history[index]
    st.session_state.turns = [{**turn, "changes": [], "source": f"최근 질문 복원 ({turn['source']})"}]
    st.session_state.pending = None
    st.session_state.notice = []
    st.session_state.guide = None
    st.session_state.screen_version = st.session_state.get("screen_version", 0) + 1


def run_alternative(text: str) -> None:
    """Run a single-dataset question suggested by the join guidance."""
    previous = st.session_state.turns[-1]["plan"] if st.session_state.turns else None
    handle(plan_registered_query(text, previous), text, "결합 안내의 단독 분석")


def submit_question() -> None:
    text = st.session_state.question.strip()
    if not text:
        st.session_state.notice = ["질문을 입력하거나 예시 질문을 눌러 주세요."]
        return
    handle(plan_registered_query(text), text, st.session_state.input_source)


def submit_followup(text: str) -> None:
    text = (text or "").strip()
    if not text or not st.session_state.turns:
        return
    previous = st.session_state.turns[-1]["plan"]
    handle(plan_registered_query(text, previous), text, "후속 요청")


SCROLL_TO_ANSWER = """
<script>
(() => {
  // The pinned follow-up input keeps the page stuck to the bottom. When a new answer
  // arrives (the marker version changes), bring its heading into view. Installed once.
  if (window.__jejuAnswerWatch) return;
  window.__jejuAnswerWatch = true;
  let seen = null;
  const go = () => {
    const heading = [...document.querySelectorAll("h1, h2, h3")].find((element) =>
      ["분석 결과", "분석 계획 확인", "두 자료를 결합하지 않았습니다"].some((title) => element.textContent.trim().startsWith(title)));
    if (!heading) return;
    // An upward wheel event releases the stick-to-bottom lock before scrolling.
    const box = document.querySelector('[data-testid="stAppScrollToBottomContainer"]');
    if (box) box.dispatchEvent(new WheelEvent("wheel", { deltaY: -120, bubbles: true }));
    heading.scrollIntoView({ block: "start" });
  };
  setInterval(() => {
    const marker = document.querySelector("[data-answer-version]");
    const version = marker ? marker.dataset.answerVersion : null;
    if (seen === null) { seen = version; if (version === "0") return; }
    if (version !== seen) {
      seen = version;
      if (version && version !== "0") [50, 400, 1000, 2000].forEach((delay) => setTimeout(go, delay));
    }
  }, 250);
})();
</script>
"""


def answer_scroll_marker() -> None:
    version = st.session_state.get("screen_version", 0)
    st.html(f'<span data-answer-version="{version}"></span>{SCROLL_TO_ANSWER}', unsafe_allow_javascript=True)


def _md(text: str) -> str:
    """Keep '1~12월' from turning into strikethrough in Markdown."""
    return text.replace("~", "\\~")


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
    with st.form(f"{prefix}_form", border=False):
        with st.container(key=f"{prefix}_step_1"):
            st.html(brand.step_badge(1, "지역 선택", "여러 곳 선택 가능"))
            region_cols = st.columns(len(vocab.REGIONS))
            regions = [
                region_id
                for column, (region_id, item) in zip(region_cols, vocab.REGIONS.items())
                if column.checkbox(item["label"], value=region_id in plan["region_ids"], key=f"{prefix}_region_{region_id}")
            ]
        with st.container(key=f"{prefix}_step_2"):
            st.html(brand.step_badge(2, "기간과 제외할 달", f"{vocab.DATA_YEAR}년 자료"))
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
                placeholder="제외할 달 없음",
            )
        with st.container(key=f"{prefix}_step_3"):
            st.html(brand.step_badge(3, "지표와 보는 방식", "지표는 여러 개 선택 가능"))
            metric_cols = st.columns(len(vocab.METRICS))
            metrics = [
                metric_id
                for column, (metric_id, item) in zip(metric_cols, vocab.METRICS.items())
                if column.checkbox(item["label"], value=metric_id in plan["metrics"], key=f"{prefix}_metric_{metric_id}")
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
            operation = st.radio(
                "분석 목적",
                options=list(vocab.OPERATION_LABELS),
                format_func=vocab.OPERATION_LABELS.get,
                index=list(vocab.OPERATION_LABELS).index(plan["operation"]),
                horizontal=True,
                key=f"{prefix}_operation",
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
        dataset = source_for_metrics(plan["metrics"])
        outside = presenter.outside_coverage(plan, dataset["coverage"]) if dataset else []
        if outside:
            coverage = dataset["coverage"]
            span = outside[0] if len(outside) == 1 else f"{outside[0]}~{outside[-1]}"
            st.markdown(
                f"⚠️ 요청 기간 {span}은 '{dataset['title']}'의 관측 범위"
                f"({coverage['start_month']}\\~{coverage['end_month']}) 밖입니다. 관측 범위 안의 기간으로 다시 요청해 주세요."
            )
        for issue in presenter.sorted_issues(result):
            st.markdown(f"{SEVERITY_ICON.get(issue['severity'], '•')} {issue['message']} `{issue['code']}`")
        return

    if st.session_state.get("view_mode", VIEW_TEXT) == VIEW_NUMBERS:
        render_numbers_view(turn, previous)
    else:
        render_text_view(plan, result)
    render_evidence(plan, result)


def render_text_view(plan: dict, result: dict) -> None:
    """Headline is above; here: plain explanation and one representative chart."""
    for line in presenter.explain_lines(plan, result):
        st.markdown(f"- {_md(line)}")
    metric = presenter.metric_columns(result)[0]
    st.markdown(f"**대표 그래프 · {presenter.column_header(metric)}**")
    st.caption(_md(presenter.scope_caption(plan, result)))
    st.altair_chart(charts.metric_chart(result, metric), width="stretch")


def render_numbers_view(turn: dict, previous: dict | None) -> None:
    """Exact values, units, differences, and comparison time for each target."""
    result, plan = turn["result"], turn["plan"]
    scope = _md(presenter.scope_caption(plan, result))
    cards = presenter.metric_cards(result)
    if cards:
        for column, card in zip(st.columns(len(cards)), cards):
            column.metric(card["label"], card["value"], border=True)
    notice = presenter.subtotal_notice(result)
    if notice:
        st.warning(f"**관측 소계 안내** · {notice}", icon="⚠️")

    st.markdown("#### 결과 표")
    st.caption(scope)
    rows = presenter.table_rows(result)
    difference = presenter.difference_row(result)
    st.dataframe(pd.DataFrame([*rows, difference] if difference else rows), hide_index=True, width="stretch")
    for line in presenter.summary_lines(result):
        st.markdown(f"- {_md(line)}")

    st.markdown("#### 그래프")
    st.caption(scope)
    for metric in presenter.metric_columns(result):
        st.markdown(f"**{presenter.column_header(metric)}**")
        st.altair_chart(charts.metric_chart(result, metric), width="stretch")

    comparison = presenter.compare_with_previous(previous["result"] if previous else None, result)
    if comparison and turn["changes"]:
        st.markdown("#### 직전 결과와 비교")
        st.dataframe(pd.DataFrame(comparison), hide_index=True, width="stretch")


def render_evidence(plan: dict, result: dict) -> None:
    st.divider()
    st.markdown("#### 근거 · 출처와 계산 방법")
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


def render_guide(guide: dict) -> None:
    """A request that spans datasets: show why they are not joined and what each can answer."""
    st.subheader("두 자료를 결합하지 않았습니다")
    st.table(
        pd.DataFrame(
            [
                {"자료": item["title"], "지역 단위": item["region"], "시간 단위": item["time_grain"], "관측 기간": item["coverage"]}
                for item in guide["datasets"]
            ]
        ).set_index("자료")
    )
    st.warning("\n".join(f"- {reason}" for reason in guide["reasons"]))
    st.markdown("**각 자료로 따로 할 수 있는 분석**")
    for index, item in enumerate(guide["alternatives"]):
        left, right = st.columns(2)
        left.markdown(f"- {item['scope']}")
        if item["question"]:
            right.button(
                item["question"], key=f"alternative_{index}", on_click=run_alternative, args=(item["question"],), width="stretch"
            )
    st.divider()


def faq_body() -> None:
    st.markdown(
        f"""
**어떤 질문을 할 수 있나요?**
- 2019년 연동·노형동의 카드 이용금액(한식 음식점업 또는 전체 업종 소계)과 방문 유동인구: 기간 합계 비교, 월별 추이, 특정 달 제외
- 제주 전체 월별 입도객의 전년 동월 비교({ARRIVALS_DATASET['coverage']['start_month']}~{ARRIVALS_DATASET['coverage']['end_month']} 자료, 2002년 이후 같은 달)
- 두 자료를 합치는 요청은 결합 가능 여부와 대신 할 수 있는 분석을 안내합니다.

**어떻게 질문하나요?**
질문 입력창에 쓰고 **분석하기** 또는 ⌘+Enter(Windows는 Ctrl+Enter)를 누릅니다. 업무별 예시를 누르면 입력창에 들어오고, 고친 뒤 실행할 수 있습니다.
결과가 나오면 화면 아래 고정 입력창에 "7~8월 빼고 다시", "노형동만"처럼 후속 질문을 쓰고 Enter를 누릅니다. 파일명이나 컬럼명은 몰라도 됩니다.

**이용 가능한 자료는?**
제주데이터허브 공개 [상권분석 매쉬업](https://jejudatahub.net/data/view/data/748) {vocab.DATA_YEAR}년 CSV와 [제주관광공사 월별 입도 관광객 확정치]({ARRIVALS_DATASET['reference']})입니다.
두 자료는 지역 단위(읍면동 / 제주 전체)와 관측 기간이 달라 결합 집계를 하지 않습니다.

**결과의 근거는 어디서 보나요?**
결과 아래 '근거'에 출처, 실제로 계산에 쓴 관측월, 제외한 달, 컬럼별 계산 방법, 품질 알림을 표시합니다.
방문인구는 같은 지역·월·성별 값이 업종 행마다 반복되므로 한 번만 반영하며, 월 누적 추정치이지 고유 방문자 수가 아닙니다.

**결과를 저장·반출할 수 있나요?**
공개 자료 집계 결과는 '분석 계획·결과 원본'에서 JSON으로 내려받을 수 있습니다. 센터 원자료를 쓴 결과는 센터의 이용·반출 조건을 따릅니다.
""".replace("~", "\\~")
    )


# ---------------------------------------------------------------------------
# Page


def history_label(turn: dict) -> str:
    """Guided-choice turns have no typed question, so name them by their conditions."""
    if turn["source"] != "안내형 선택지":
        return turn["request"]
    conditions = dict(describe_plan(turn["plan"]))
    parts = [conditions.get("지역"), conditions.get("업종"), conditions.get("지표")]
    excluded = conditions.get("제외 조건")
    if excluded and excluded != "없음":
        parts.append(excluded)
    return "선택지 · " + " · ".join(part for part in parts if part)


def data_status() -> tuple[str, bool, list[tuple[str, str, bool]]]:
    files = [
        ("상권분석 매쉬업 2019", "읍면동 · 2019-01~2019-12", Path(st.session_state.csv_path).is_file()),
        (
            "월별 입도 관광객 확정치",
            f"제주 전체 · {ARRIVALS_DATASET['coverage']['start_month']}~{ARRIVALS_DATASET['coverage']['end_month']}",
            Path(st.session_state.arrivals_path).is_file(),
        ),
    ]
    connected = sum(ok for *_, ok in files)
    return f"로컬 실행 · 공개 데이터 {connected}종 연결", connected == len(files), files


def render_sidebar() -> None:
    st.session_state.setdefault("csv_path", default_csv())
    st.session_state.setdefault("arrivals_path", str(ARRIVALS_FILE))
    with st.sidebar:
        st.html(
            f'<div class="jo-side-brand">{brand.logo_markup(size=34)}</div>'
            '<p class="jo-side-intro">질문하면 센터 PC에서 공개 자료를 찾아 집계하고, 답과 근거를 보여줍니다.</p>'
        )

        st.subheader("연결된 데이터")
        _, _, files = data_status()
        ready = "".join(
            f'<li><span class="jo-pill {"jo-pill-ok" if ok else "jo-pill-off"}">{"연결됨" if ok else "파일 없음"}</span>'
            f"<span>{name}<small>{scope}</small></span></li>"
            for name, scope, ok in files
        )
        center = "".join(
            f'<li><span class="jo-pill jo-pill-plan">스키마 확인</span><span>{name}<small>원자료 미연결</small></span></li>'
            for name in CENTER_SCHEMAS
        )
        st.html(
            f'<div class="jo-data"><h5>바로 분석할 수 있는 공개 자료</h5><ul>{ready}</ul>'
            f"<h5>센터 원자료 · 확장 준비</h5><ul>{center}</ul></div>"
        )
        with st.expander("파일 경로 설정"):
            st.text_input("2019년 상권 CSV 경로", key="csv_path", help=f"data/local/ 에 원래 파일명으로 둔 {vocab.DATA_YEAR}년 CSV")
            st.text_input("입도객 XLSX 경로", key="arrivals_path")
            st.caption("질문·원자료·결과는 이 PC에서만 처리하며 외부로 전송하지 않습니다.")

        st.subheader("최근 질문")
        history = st.session_state.history
        if not history:
            st.caption("분석한 질문이 여기에 쌓입니다. 누르면 그때의 조건과 결과를 다시 엽니다.")
        for index, turn in enumerate(history):
            st.button(
                _md(history_label(turn)),
                key=f"history_{index}",
                on_click=restore_turn,
                args=(index,),
                width="stretch",
                help=f"{turn['source']} · 조건과 결과를 다시 엽니다",
            )

        st.button("새 분석 시작 (조건 초기화)", on_click=reset_analysis, width="stretch", key="reset_sidebar", type="primary")
        with st.expander("자주 묻는 질문"):
            faq_body()


def main() -> None:
    st.set_page_config(page_title="제주한눈 | JejuOneEyes", page_icon=brand.page_icon(), layout="wide")
    init_state()
    st.html(brand.CSS)
    render_sidebar()

    if st.session_state.turns:
        followup = st.chat_input("후속 질문 (예: 7~8월 빼고 다시) · Enter로 실행")
        if followup:
            submit_followup(followup)

    status, ready, _ = data_status()
    st.html(brand.header_markup(status, ready))
    answer_scroll_marker()
    if not ready:
        st.error("연결되지 않은 공개 자료가 있습니다. 왼쪽 '연결된 데이터'와 app/README.md의 준비 절차를 확인해 주세요.", icon="⛔")

    if st.session_state.guide:
        render_guide(st.session_state.guide)
    else:
        for message in st.session_state.notice:
            st.warning(message, icon="⚠️")

    if st.session_state.pending:
        render_pending()
    elif not st.session_state.turns:
        render_start()

    if st.session_state.turns:
        render_turns()


def input_meta() -> str:
    source = st.session_state.input_source
    if source.startswith("예시"):
        mode, tone, hint = "예시", "jo-mode jo-mode-example", "예시 질문을 불러왔습니다. 고친 뒤 실행하세요."
    else:
        mode, tone, hint = "자연어", "jo-mode", "질문을 그대로 쓰면 됩니다. 파일명이나 컬럼명은 몰라도 됩니다."
    return (
        f'<div class="jo-input-meta"><span class="{tone}">입력 방식 · {mode}</span>'
        f'<span><kbd class="jo-kbd">Ctrl</kbd> + <kbd class="jo-kbd">Enter</kbd> 로 실행 (Mac은 <kbd class="jo-kbd">⌘</kbd> + <kbd class="jo-kbd">Enter</kbd>)</span>'
        f"<span>{hint}</span></div>"
    )


def render_start() -> None:
    st.subheader("무엇을 알아볼까요?")
    for column, card in zip(st.columns(3), QUICK_STARTS):
        with column, st.container(key=card["key"]):
            st.html(
                f'<span class="jo-qs-tag">{card["tag"]}</span>'
                f'<div class="jo-qs-title">{card["title"]}</div><p class="jo-qs-body">{card["body"]}</p>'
            )
            st.button(
                "이 질문으로 시작",
                key=f"{card['key']}_button",
                on_click=load_example,
                args=(card["question"],),
                type="tertiary",
                help=card["question"],
            )

    with st.container(key="ask_card"):
        with st.form("ask_form", border=False):
            st.text_area("질문", key="question", placeholder=QUESTION_PLACEHOLDER, height=100)
            button_col, meta_col = st.columns([1, 4], vertical_alignment="center")
            button_col.form_submit_button("분석하기", type="primary", on_click=submit_question, width="stretch")
            meta_col.html(input_meta())

    tab_examples, tab_choices, tab_faq = st.tabs(
        ["업무별 예시 질문", "선택지로 고르기 (2019년 상권)", "자주 묻는 질문"], key="start_tabs"
    )
    with tab_examples:
        role = st.pills(
            "내 업무 · 고른 업무의 예시가 앞에 옵니다. 이용할 수 있는 자료와 분석 범위는 같습니다.",
            ROLES,
            default=ROLES[0],
            required=True,
            key="role",
        ) or ROLES[0]
        if role == "공무원·공공기관 실무자":
            st.caption(
                "공공설비 운영 점검(예: 음식물쓰레기 배출량) 질문은 센터 원자료가 연결되어야 분석할 수 있습니다. "
                "지금은 아래 공개 자료 질문을 실행할 수 있습니다."
            )
        registered_examples = (
            {"text": ARRIVALS_QUESTION, "role": "도내 기업 실무자"},
            {"text": JOIN_QUESTION, "role": "공무원·공공기관 실무자"},
        )
        examples = sorted((*vocab.EXAMPLE_QUESTIONS, *registered_examples), key=lambda example: example["role"] != role)
        st.caption("누르면 위 질문 입력창에 들어갑니다. 고친 뒤 실행하세요.")
        with st.container(key="examples"):
            example_cols = st.columns(2)
            for index, example in enumerate(examples):
                tag = ROLE_TAGS[example["role"]]
                example_cols[index % 2].button(
                    f":{ROLE_BADGE[tag]}-badge[{tag}] {example['text']}",
                    key=f"example_{index}",
                    on_click=load_example,
                    args=(example["text"],),
                    width="stretch",
                    help=f"{example['role']} 예시 · {example['text']}",
                    wrap=True,
                )
    with tab_choices:
        st.caption(
            f"선택지는 {vocab.DATA_YEAR}년 상권분석 매쉬업(연동·노형동의 카드 이용금액·방문 유동인구)용입니다. "
            "입도객 전년 동월 비교는 위 질문 입력창이나 예시 질문으로 실행합니다."
        )
        choices_form("start", None, label="선택한 조건으로 분석")
    with tab_faq:
        faq_body()


def render_headline(turn: dict) -> None:
    headline = presenter.headline(turn["plan"], turn["result"])
    if not headline:
        return
    with st.container(key="headline"):
        st.markdown("#### " + _md(headline))
        st.caption("엔진이 계산한 값으로 만든 문장입니다. 자료가 보여주는 변화까지만 설명합니다.")


def render_turns() -> None:
    turns = st.session_state.turns
    latest = turns[-1]
    previous = turns[-2] if len(turns) > 1 else None
    is_arrivals = ARRIVALS_METRIC in latest["plan"]["metrics"]

    st.subheader("분석 결과")
    render_headline(latest)
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

    if latest["result"]["status"] == "ok":
        st.segmented_control(
            "결과 보기 방식 (같은 결과를 다시 계산하지 않고 바꿔 봅니다)",
            [VIEW_TEXT, VIEW_NUMBERS],
            default=VIEW_TEXT,
            required=True,
            key="view_mode",
        )
    render_result(latest, previous)

    st.divider()
    st.subheader("조건 바꿔 다시 분석")
    if is_arrivals:
        st.caption("입도객 비교는 다른 연월을 질문해 다시 실행합니다. 예: 2025년 9월 제주 입도객을 전년 동월과 비교해줘")
    else:
        suggestion_cols = st.columns(len(vocab.FOLLOWUP_SUGGESTIONS))
        for column, suggestion in zip(suggestion_cols, vocab.FOLLOWUP_SUGGESTIONS):
            column.button(suggestion, key=f"suggest_{suggestion}", on_click=submit_followup, args=(suggestion,), width="stretch")
    st.caption("화면 아래 고정 입력창에 후속 질문을 쓰고 Enter를 누르면 직전 조건을 이어서 다시 분석합니다.")
    action_cols = st.columns([1, 1, 2])
    action_cols[0].button("새 분석 시작", on_click=reset_analysis, width="stretch", key="reset_main")
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
                st.caption(_md(totals))


main()
