import csv
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from core.analyzer import run_analysis


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"
EXAMPLE_PLAN = CONTRACTS / "examples" / "analysis-plan.json"
RESULT = Draft202012Validator(
    json.loads((CONTRACTS / "analysis-result.schema.json").read_text(encoding="utf-8"))
)


class MarketAnalysisTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.csv_path = Path(directory.name) / "예시 자료.csv"
        self.plan = json.loads(EXAMPLE_PLAN.read_text(encoding="utf-8"))
        self.plan["period"] = {"start_month": "2019-01", "end_month": "2019-02"}
        self.plan["exclude_months"] = []

    def write_rows(self, rows):
        with self.csv_path.open("w", encoding="cp949", newline="") as output:
            writer = csv.writer(output)
            writer.writerow(["년월", "시도명", "읍면동명", "업종명", "성별", "이용금액", "방문인구"])
            writer.writerows(rows)

    def test_population_is_counted_once_and_independent_of_industry(self):
        self.plan["metrics"].append("visit_population_monthly_sum")
        self.write_rows([
            ["2019-01-01", "제주시", "연동", "한식 음식점업", "남성", 12, 3.5],
            ["2019-01-01", "제주시", "연동", "한식 음식점업", "여성", 23, 4],
            ["2019-01-01", "제주시", "연동", "중식 음식점업", "남성", 90, 3.5],
            ["2019-01-01", "제주시", "노형동", "한식 음식점업", "남성", 0, 5],
            ["2019-01-01", "제주시", "노형동", "한식 음식점업", "여성", 0, 6],
            ["2019-02-01", "제주시", "연동", "한식 음식점업", "남성", 500, 8],
            ["2019-02-01", "제주시", "연동", "한식 음식점업", "여성", 500, 9],
        ])
        result = run_analysis(self.plan, self.csv_path)
        RESULT.validate(result)
        self.assertEqual(result["sources"][0]["observed_months"], ["2019-01"])
        self.assertEqual(result["rows"], [
            {"region": "노형동", "card_amount_krw": 0, "visit_population_monthly_sum": 11.0},
            {"region": "연동", "card_amount_krw": 35, "visit_population_monthly_sum": 7.5},
        ])
        self.assertEqual({issue["code"] for issue in result["issues"]}, {"repeated_population", "incomplete_coverage"})

    def test_conflicting_population_is_excluded(self):
        self.plan["region_ids"] = ["jeju.yeon_dong"]
        self.plan["metrics"] = ["visit_population_monthly_sum"]
        self.write_rows([
            ["2019-01-01", "제주시", "연동", "한식 음식점업", "남성", 12, 3],
            ["2019-01-01", "제주시", "연동", "중식 음식점업", "남성", 20, 4],
            ["2019-01-01", "제주시", "연동", "한식 음식점업", "여성", 25, 7],
        ])
        result = run_analysis(self.plan, self.csv_path)
        RESULT.validate(result)
        self.assertEqual(result["status"], "no_data")
        self.assertEqual(result["issues"][0]["code"], "conflicting_population")

    def test_impossible_month_rejected_before_opening_file(self):
        self.plan["exclude_months"] = [13]
        result = run_analysis(self.plan, self.csv_path)
        RESULT.validate(result)
        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(result["issues"][0]["code"], "invalid_plan")

    def test_all_industries_discloses_observed_subtotal_when_a_row_is_missing(self):
        self.plan["region_ids"] = ["jeju.yeon_dong"]
        self.plan["industry_ids"] = []
        self.plan["period"]["end_month"] = "2019-01"
        self.write_rows([
            ["2019-01-01", "제주시", "연동", "한식 음식점업", "남성", 100, 3],
            ["2019-01-01", "제주시", "연동", "한식 음식점업", "여성", 100, 4],
            ["2019-01-01", "제주시", "연동", "중식 음식점업", "남성", 70, 3],
        ])

        result = run_analysis(self.plan, self.csv_path)

        RESULT.validate(result)
        self.assertEqual(result["rows"], [{"region": "연동", "card_amount_krw": 270}])
        self.assertIn("소계", result["columns"][1]["label"])
        self.assertEqual(result["issues"][0]["code"], "observed_card_subtotal")
        self.assertEqual(result["issues"][0]["severity"], "warning")

    def test_wrong_year_is_rejected_even_outside_the_requested_filters(self):
        self.plan["region_ids"] = ["jeju.yeon_dong"]
        cases = [
            ("2020-01", "연동", "2020"),
            ("2019-01", "노형동", "2019년과 다른"),
        ]
        for month, wrong_year_region, expected_message in cases:
            with self.subTest(month=month, wrong_year_region=wrong_year_region):
                self.plan["period"] = {"start_month": month, "end_month": month}
                self.write_rows([
                    ["2019-01-01", "제주시", "연동", "한식 음식점업", "남성", 12, 3],
                    ["2019-01-01", "제주시", "연동", "한식 음식점업", "여성", 12, 4],
                    ["2020-01-01", "제주시", wrong_year_region, "한식 음식점업", "남성", 15, 3],
                    ["2020-01-01", "제주시", wrong_year_region, "한식 음식점업", "여성", 15, 4],
                ])

                result = run_analysis(self.plan, self.csv_path)

                RESULT.validate(result)
                self.assertEqual(result["status"], "error")
                self.assertEqual(result["issues"][0]["code"], "invalid_source")
                self.assertIn(expected_message, result["issues"][0]["message"])
                self.assertEqual(result["sources"], [])


if __name__ == "__main__":
    unittest.main()
