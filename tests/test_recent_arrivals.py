"""The official workbook stays local. The catalog and join checks run without it."""

import importlib.util
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from core.kg.catalog import CATALOG
from core.planner.registered_query import ARRIVALS_QUESTION, JOIN_QUESTION, plan_registered_query


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "data" / "local" / "jeju-arrivals.xlsx"
HAS_STREAMLIT = importlib.util.find_spec("streamlit") is not None


class RecentArrivalsTest(unittest.TestCase):
    def test_catalog_contract_and_incompatible_join(self):
        schema = json.loads((ROOT / "contracts/catalog.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(CATALOG)
        combined = plan_registered_query(JOIN_QUESTION)
        self.assertEqual(combined.status, "unsupported")
        self.assertIsNone(combined.plan)
        notes = "\n".join(combined.notes)
        self.assertIn("지역 단위가 달라", notes)
        self.assertIn("2026-09은 두 자료의 공통 관측 기간(2019-01~2019-12) 밖", notes)
        self.assertIn("읍면동 / 제주특별자치도 전체", notes)
        alternatives = {item["dataset_id"]: item["question"] for item in combined.guide["alternatives"]}
        self.assertEqual(alternatives["ijto.monthly_arrivals"], ARRIVALS_QUESTION)
        for question in alternatives.values():
            self.assertEqual(plan_registered_query(question).status, "ready")

    @unittest.skipUnless(WORKBOOK.is_file() and HAS_STREAMLIT, "공식 입도객 XLSX 또는 Streamlit이 없습니다.")
    def test_official_arrivals_and_join_in_the_app(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=60).run()
        app.text_area(key="question").input(ARRIVALS_QUESTION)
        next(button for button in app.button if button.label == "분석하기").click().run()
        self.assertFalse(app.exception)
        text = "\n".join(item.value for item in app.markdown)
        for value in ("1,181,507명", "1,123,339명", "-58,168명", "-4.92%", "2025-09, 2026-09", "공공누리 제1유형"):
            self.assertIn(value, text)
        self.assertIn("2026년 9월 제주 입도객은 112만 3,339명으로, 지난해 같은 달보다 5만 8,168명(4.92%) 줄었습니다.", text)

        app.text_input(key="followup_text").set_value(JOIN_QUESTION)
        next(button for button in app.button if button.label == "후속 요청 실행").click().run()
        self.assertFalse(app.exception)
        warnings = "\n".join(item.value for item in app.warning)
        self.assertIn("지역 단위가 달라", warnings)
        self.assertIn("공통 관측 기간(2019-01~2019-12)", warnings)
        self.assertEqual(len(app.session_state["turns"]), 1)
        self.assertIn("두 자료를 결합하지 않았습니다", [item.value for item in app.subheader])

        next(button for button in app.button if button.label.startswith("2019년 9월 연동과 노형동")).click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state["turns"]), 2)
        self.assertEqual(app.session_state["turns"][-1]["plan"]["period"], {"start_month": "2019-09", "end_month": "2019-09"})
