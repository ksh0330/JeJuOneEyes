"""Screen flow checks. Real-CSV tests run only when the public 2019 CSV is in data/local/."""

import importlib.util
import unittest
from pathlib import Path

from app import presenter
from core.analyzer import run_analysis
from core.planner import apply_followup, plan_from_text

ROOT = Path(__file__).resolve().parents[1]
CSV = next(iter(sorted((ROOT / "data" / "local").glob("*매쉬업결과_19.csv"))), None)
QUESTION = "2019년 연동과 노형동의 한식 음식점업 카드 이용금액을 비교해줘"
HAS_STREAMLIT = importlib.util.find_spec("streamlit") is not None


def by_region(result):
    return {row["region"]: row["card_amount_krw"] for row in result["rows"]}


class PresenterTest(unittest.TestCase):
    RESULT = {
        "schema_version": 1,
        "status": "ok",
        "columns": [
            {"id": "region", "label": "지역", "unit": None, "method": None},
            {"id": "card_amount_krw", "label": "관측된 업종·성별의 카드 이용금액 소계", "unit": "원", "method": "합계"},
        ],
        "rows": [{"region": "연동", "card_amount_krw": 150}, {"region": "노형동", "card_amount_krw": 100}],
        "sources": [{"dataset_id": "hub.market_mashup_2019", "title": "t", "reference": "r", "observed_months": ["2019-01", "2019-03"]}],
        "issues": [
            {"code": "repeated_population", "severity": "info", "message": "i"},
            {"code": "observed_card_subtotal", "severity": "warning", "message": "관측 소계입니다."},
        ],
    }
    PLAN = {"period": {"start_month": "2019-01", "end_month": "2019-04"}, "exclude_months": [4]}

    def test_labels_units_subtotal_and_coverage(self):
        self.assertEqual(
            presenter.table_rows(self.RESULT)[0],
            {"지역": "연동", "관측된 업종·성별의 카드 이용금액 소계 (원)": "150원"},
        )
        self.assertEqual(presenter.subtotal_notice(self.RESULT), "관측 소계입니다.")
        self.assertEqual(presenter.sorted_issues(self.RESULT)[0]["severity"], "warning")
        self.assertEqual(
            presenter.month_coverage(self.PLAN, self.RESULT),
            {"observed": ["2019-01", "2019-03"], "excluded": ["2019-04"], "unobserved": ["2019-02"]},
        )
        self.assertIn("연동이(가) 노형동보다 50원 (50.0%) 많습니다.", presenter.summary_lines(self.RESULT)[0])


@unittest.skipUnless(CSV, "공개 2019년 CSV가 data/local/에 없습니다.")
class RealCsvFlowTest(unittest.TestCase):
    def test_representative_question_and_followup_match_reference_values(self):
        first = plan_from_text(QUESTION)
        result = run_analysis(first.plan, CSV)
        self.assertEqual(by_region(result), {"연동": 33_833_494_533, "노형동": 32_321_443_476})
        self.assertEqual(len(result["sources"][0]["observed_months"]), 12)

        followup = apply_followup(first.plan, "7~8월 빼고 다시")
        updated = run_analysis(followup.plan, CSV)
        self.assertEqual(by_region(updated), {"연동": 28_067_882_813, "노형동": 26_632_168_999})
        self.assertNotIn("2019-07", updated["sources"][0]["observed_months"])
        self.assertEqual(len(presenter.compare_with_previous(result, updated)), 2)

    def test_all_industries_shows_observed_subtotal(self):
        plan = plan_from_text("연동 전체 업종 카드 이용금액을 노형동과 비교해줘").plan
        result = run_analysis(plan, CSV)
        self.assertEqual(result["status"], "ok")
        self.assertIsNotNone(presenter.subtotal_notice(result))
        self.assertEqual(presenter.metric_columns(result)[0]["label"], "관측된 업종·성별의 카드 이용금액 소계")


@unittest.skipUnless(CSV and HAS_STREAMLIT, "공개 CSV 또는 streamlit이 없습니다.")
class StreamlitAppTest(unittest.TestCase):
    def test_question_then_followup_on_screen(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=60).run()
        self.assertFalse(app.exception)
        app.text_area(key="question").input(QUESTION)
        next(button for button in app.button if button.label == "분석하기").click().run()
        self.assertFalse(app.exception)
        text = " ".join(item.value for item in app.markdown)
        self.assertIn("33,833,494,533원", text)
        self.assertIn("출처", text)
        self.assertIn("실제 관측월", text)

        next(button for button in app.button if button.label == "7~8월 빼고 다시").click().run()
        self.assertFalse(app.exception)
        text = " ".join(item.value for item in app.markdown)
        self.assertIn("28,067,882,813원", text)
        self.assertIn("제외 조건: 없음 → 7월, 8월 제외", text)
        self.assertIn("요청으로 제외한 달", text)


if __name__ == "__main__":
    unittest.main()
