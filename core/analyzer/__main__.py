import argparse
import json
from pathlib import Path

from .market import run_analysis


def main() -> int:
    parser = argparse.ArgumentParser(description="제주 공개 상권 CSV 분석")
    parser.add_argument("--csv", type=Path, required=True, help="직접 내려받은 공개 CSV 경로")
    parser.add_argument("--plan", type=Path, required=True, help="AnalysisPlan v1 JSON 파일")
    parser.add_argument("--output", type=Path, help="결과 JSON 경로. 생략하면 터미널에 출력")
    args = parser.parse_args()
    if args.output and args.output.resolve() in {args.csv.resolve(), args.plan.resolve()}:
        parser.error("결과를 입력 CSV나 분석 계획과 같은 파일에 저장할 수 없습니다.")

    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        parser.error(f"분석 계획 파일을 읽을 수 없습니다. {exc}")

    result = run_analysis(plan, args.csv)
    content = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        try:
            args.output.write_text(content, encoding="utf-8")
        except OSError as exc:
            parser.error(f"결과를 저장할 수 없습니다. {exc}")
    else:
        print(content, end="")
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
