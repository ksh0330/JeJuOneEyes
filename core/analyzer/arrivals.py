from pathlib import Path
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from core.kg.catalog import ARRIVALS_DATASET, ARRIVALS_METRIC

from .market import PLAN_VALIDATOR, _issue, _requested_months, _result


def read_arrivals(path: Path) -> dict[str, int]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        if "분석용 데이터" not in workbook.sheetnames:
            raise ValueError("공식 입도객 XLSX의 '분석용 데이터' 시트를 찾을 수 없습니다.")
        rows = workbook["분석용 데이터"].values
        if next(rows, None) != ("년도", "월", "구분", "방문객수"):
            raise ValueError("공식 입도객 XLSX의 표 헤더가 일치하지 않습니다.")
        totals = {}
        for year, month, group, count in rows:
            if group != "전체":
                continue
            if type(year) is not int or type(month) is not int or not 1 <= month <= 12:
                raise ValueError("입도객 자료에 유효하지 않은 연월이 있습니다.")
            key = f"{year}-{month:02d}"
            if key in totals or type(count) is not int or count < 0:
                raise ValueError(f"{key}의 전체 입도객 행이 중복되거나 숫자가 올바르지 않습니다.")
            totals[key] = count
        return totals
    finally:
        workbook.close()


def run_arrivals(plan: dict, path: Path | str) -> dict:
    if (
        not PLAN_VALIDATOR.is_valid(plan)
        or plan["operation"] != "compare"
        or plan["region_ids"] != ["jeju.province"]
        or plan["industry_ids"]
        or plan["metrics"] != [ARRIVALS_METRIC]
        or plan["group_by"] != ["month"]
        or any(month.startswith("0000-") for month in plan["period"].values())
    ):
        return _result("needs_input", [_issue("invalid_arrivals_plan", "제주 전체 입도객 비교 조건을 확인해 주세요.")])
    months = sorted(_requested_months(plan["period"], plan["exclude_months"]))
    if len(months) != 2 or months[0][5:] != months[1][5:] or int(months[1][:4]) - int(months[0][:4]) != 1:
        return _result("needs_input", [_issue("invalid_comparison_months", "같은 달의 연속된 두 연도를 선택해 주세요.")])
    try:
        totals = read_arrivals(Path(path))
    except OSError:
        return _result("unavailable", [_issue("arrivals_file_missing", "제주관광공사 공식 XLSX를 받아 입도객 파일 경로에 연결해 주세요.")])
    except (BadZipFile, InvalidFileException, ValueError) as exc:
        return _result("error", [_issue("invalid_arrivals_file", f"입도객 XLSX 구조를 확인해 주세요. {exc}", "error")])
    missing = [month for month in months if month not in totals]
    if missing:
        return _result("no_data", [_issue("arrivals_month_missing", f"연결된 파일에서 {', '.join(missing)}의 확정치를 찾을 수 없습니다.")])
    coverage = ARRIVALS_DATASET["coverage"]
    if min(totals) != coverage["start_month"] or max(totals) != coverage["end_month"]:
        return _result("unavailable", [_issue(
            "arrivals_file_version",
            "연결된 XLSX의 관측 범위가 등록 파일(2001-01~2026-09)과 다릅니다. 2026년 9월 기준 파일을 연결해 주세요.",
        )])
    return _result("ok", [], columns=[
        {"id": "month", "label": "관측월", "unit": None, "method": None},
        {"id": ARRIVALS_METRIC, "label": "제주 전체 입도 관광객 확정치", "unit": "명", "method": "공식 XLSX의 월별 '전체' 행"},
    ], rows=[{"month": month, ARRIVALS_METRIC: totals[month]} for month in months], sources=[{
        "dataset_id": ARRIVALS_DATASET["id"], "title": ARRIVALS_DATASET["title"],
        "reference": ARRIVALS_DATASET["reference"], "observed_months": months,
    }])
