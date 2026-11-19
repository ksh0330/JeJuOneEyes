import json
import unittest
from pathlib import Path

from core.analyzer import market
from core.planner import (
    NEEDS_INPUT,
    READY,
    UNSUPPORTED,
    apply_answers,
    apply_followup,
    plan_from_choices,
    plan_from_text,
)
from core.planner import vocabulary as vocab

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PLAN = json.loads((ROOT / "contracts" / "examples" / "analysis-plan.json").read_text(encoding="utf-8"))
QUESTION = "2019년 연동과 노형동의 한식 음식점업 카드 이용금액을 비교해줘"


class PlannerTest(unittest.TestCase):
    def test_vocabulary_matches_analyzer_support(self):
        self.assertLessEqual(set(vocab.REGIONS), set(market.REGIONS))
        self.assertLessEqual(set(vocab.INDUSTRIES), set(market.INDUSTRIES))
        self.assertLessEqual(set(vocab.METRICS), set(market.METRICS))

    def test_text_and_choices_build_the_same_plan(self):
        text = plan_from_text(QUESTION)
        choices = plan_from_choices(
            operation="compare",
            region_ids=["jeju.nohyeong_dong", "jeju.yeon_dong"],
            industry_ids=["food.korean_restaurant"],
            metrics=["card_amount_krw"],
            start_month="2019-01",
            end_month="2019-12",
            exclude_months=[],
        )
        self.assertEqual(text.status, READY)
        self.assertEqual(text.plan, choices.plan)
        self.assertEqual(text.plan, {**EXAMPLE_PLAN, "exclude_months": []})

    def test_followup_excludes_july_august_and_keeps_other_conditions(self):
        first = plan_from_text(QUESTION).plan
        followup = apply_followup(first, "7~8월 빼고 다시")
        self.assertEqual(followup.status, READY)
        self.assertEqual(followup.plan, EXAMPLE_PLAN)
        self.assertEqual(followup.changes, ["제외 조건: 없음 → 7월, 8월 제외"])
        self.assertEqual(first["exclude_months"], [], "previous plan must not be mutated")

        restored = apply_followup(followup.plan, "제외 없이 전체 월로 다시")
        self.assertEqual(restored.plan["exclude_months"], [])
        self.assertEqual(restored.plan["region_ids"], first["region_ids"])

    def test_followup_variants(self):
        first = plan_from_text(QUESTION).plan
        self.assertEqual(apply_followup(first, "7, 8월 제외").plan["exclude_months"], [7, 8])
        self.assertEqual(apply_followup(first, "노형동만 보여줘").plan["region_ids"], ["jeju.nohyeong_dong"])
        both = apply_followup(first, "방문인구도 같이 보여줘").plan
        self.assertEqual(both["metrics"], ["card_amount_krw", "visit_population_monthly_sum"])
        trend = apply_followup(first, "월별 추이로 바꿔줘").plan
        self.assertEqual((trend["operation"], trend["group_by"]), ("trend", ["region", "month"]))

    def test_ambiguous_summer_asks_which_months(self):
        first = plan_from_text(QUESTION).plan
        response = apply_followup(first, "여름 빼고 다시")
        self.assertEqual(response.status, NEEDS_INPUT)
        self.assertEqual(response.clarifications[0].field, "exclude_months")
        answered = apply_answers(response, {"exclude_months": [7, 8]})
        self.assertEqual(answered.plan, EXAMPLE_PLAN)

    def test_missing_industry_is_asked_not_guessed(self):
        response = plan_from_text("연동과 노형동 카드 이용금액 비교")
        self.assertEqual(response.status, NEEDS_INPUT)
        self.assertEqual([c.field for c in response.clarifications], ["industry_ids"])
        answered = apply_answers(response, {"industry_ids": ["food.korean_restaurant"]})
        self.assertEqual(answered.status, READY)
        self.assertEqual(answered.plan["industry_ids"], ["food.korean_restaurant"])

    def test_unsupported_requests_keep_previous_plan(self):
        first = plan_from_text(QUESTION).plan
        for text in ("건수 기준으로 바꿔줘", "애월읍도 포함해줘"):
            response = apply_followup(first, text)
            self.assertEqual(response.status, UNSUPPORTED)
            self.assertEqual(response.plan, first)
            self.assertTrue(response.notes)

    def test_all_months_excluded_is_explained_before_running(self):
        response = plan_from_text("연동 한식 카드 이용금액 7월만 보여줘")
        followup = apply_followup(response.plan, "7월 빼고 다시")
        self.assertEqual(followup.status, UNSUPPORTED)
        self.assertIn("모든 달이 제외", followup.notes[0])

    def test_examples_produce_ready_plans(self):
        for example in vocab.EXAMPLE_QUESTIONS:
            with self.subTest(example=example["text"]):
                self.assertEqual(plan_from_text(example["text"]).status, READY)


if __name__ == "__main__":
    unittest.main()
