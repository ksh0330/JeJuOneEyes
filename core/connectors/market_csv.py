import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from io import StringIO
from pathlib import Path


@dataclass(frozen=True)
class MarketRow:
    month: str
    region: str
    industry: str
    sex: str
    card_amount: int | None
    visit_population: Decimal | None


def read_market_rows(
    csv_path: Path,
    columns: dict[str, str],
    city: str,
    regions: set[str],
    months: set[str],
    *,
    source_year: int,
) -> list[MarketRow]:
    """Read the public extract without changing the original file."""
    raw = csv_path.read_bytes()
    try:
        contents = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        contents = raw.decode("cp949")

    reader = csv.DictReader(StringIO(contents, newline=""))
    if not set(columns.values()).issubset(reader.fieldnames or ()):
        raise ValueError("공개 상권 CSV의 필수 컬럼이 없습니다.")

    rows = []
    for raw_row in reader:
        try:
            observed_date = date.fromisoformat(raw_row[columns["month"]])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"CSV {reader.line_num}행의 날짜 형식을 확인해 주세요.") from exc
        if observed_date.year != source_year:
            raise ValueError(
                f"CSV {reader.line_num}행에 등록 연도 {source_year}년과 다른 "
                f"{observed_date.year}년 자료가 있습니다. {source_year}년 원본 CSV를 연결해 주세요."
            )

        region = raw_row[columns["region"]]
        month = observed_date.isoformat()[:7]
        if raw_row[columns["city"]] != city or region not in regions or month not in months:
            continue
        try:
            amount = raw_row[columns["card_amount"]].strip()
            population = raw_row[columns["visit_population"]].strip()
            visit_population = Decimal(population) if population else None
            if visit_population is not None and not visit_population.is_finite():
                raise ValueError("Non-finite visit population")
            rows.append(
                MarketRow(
                    month=month,
                    region=region,
                    industry=raw_row[columns["industry"]],
                    sex=raw_row[columns["sex"]],
                    card_amount=int(amount) if amount else None,
                    visit_population=visit_population,
                )
            )
        except (AttributeError, TypeError, ValueError, InvalidOperation) as exc:
            raise ValueError(f"CSV {reader.line_num}행의 수치 형식을 확인해 주세요.") from exc
    return rows
