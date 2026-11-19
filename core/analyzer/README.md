# 시장조사 분석 엔진 실행

팀원은 [제주데이터허브 상권분석 매쉬업](https://jejudatahub.net/data/view/data/748)의 2019년 원본 `제주특별자치도_주제3_상권분석을 위한 유동인구에 따른 카드 매출액 변화 데이터 활용_매쉬업결과_19.csv`를 각자 내려받아 `data/local/`에 둔다. 원래 파일명과 인코딩을 유지한다. `--csv`에 다른 로컬 경로를 지정해도 된다. CSV는 Git과 제출 ZIP에서 제외한다. 제품 실행 중 이 모듈은 네트워크를 사용하지 않는다.

대회는 제주데이터허브 공개 원자료 또는 센터 방문으로 제공받은 데이터 중 1종 이상의 실제 분석 활용을 요구한다. 현재 시연은 위 공개 원자료를 사용한다. 참가자용 허브 목록 엑셀의 예시 데이터는 구조 확인용이다. 그 엑셀은 DAKER 외부에 배포하거나 제3자에게 제공할 수 없다. 센터 자료는 제공 명세와 이용조건을 확인한 뒤 별도 연결한다. [공식 대회 데이터 안내](https://daker.ai/public/hackathons/jeju-ai-bigdata-agent-challenge#section-data) · [센터 제공데이터 명세](https://jejudatahub.net/center/data)

아래 명령은 저장소 루트에서 실행한다. 이전에 만든 `.venv`가 있다면 해당 가상환경을 재사용한다.

**Windows PowerShell**

```powershell
py -3.12 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r core/analyzer/requirements.txt
$csv = Get-ChildItem -LiteralPath './data/local' -Filter '*_19.csv' -File | Select-Object -First 1
./.venv/Scripts/python.exe -m core.analyzer --csv $csv.FullName --plan contracts/examples/analysis-plan.json --output data/local/market-result.json
```

**macOS**

```sh
python3.12 -m venv .venv
./.venv/bin/python -m pip install -r core/analyzer/requirements.txt
csv='./data/local/제주특별자치도_주제3_상권분석을 위한 유동인구에 따른 카드 매출액 변화 데이터 활용_매쉬업결과_19.csv'
./.venv/bin/python -m core.analyzer --csv "$csv" --plan contracts/examples/analysis-plan.json --output data/local/market-result.json
```

## 플래너·UI 연결

- `from core.analyzer import run_analysis`로 불러오고 `run_analysis(plan, csv_path)`를 호출한다. 입력은 `AnalysisPlan v1`, 반환은 `AnalysisResult v1`이다. 데이터 경로는 작업자가 준비한 로컬 파일에서 가져온다.
- 첫 버전은 연동·노형동과 한식 음식점업, 카드 이용액 및 지역 전체 방문 유동인구를 지원한다. 업종 ID가 빈 배열이면 관측된 업종·성별의 카드 금액 소계를 반환하고, 전체 업종의 관측 완전성은 확인할 수 없음을 `issues`에 표시한다. CSV의 날짜 연도가 등록 연도인 2019년과 일치하는지는 필터 적용 전에 확인한다. 월별 추이는 `operation`을 `trend`로 바꾸고 `group_by`에 `month`를 포함한다. 연동·노형동 비교에 실제 사용한 공통 월과 진단을 결과에서 표시한다.
- 2019년 검산 기준은 연동 `33,833,494,533원`, 노형동 `32,321,443,476원`이다. 예시 계획 그대로 7~8월을 빼면 각각 `28,067,882,813원`, `26,632,168,999원`이다. 화면 캡처나 문서 초안에는 테스트용 CSV가 아닌 실제 공개 파일에서 재계산한 결과를 사용하고 2019년 자료임을 표시한다.
- 변경 전후 확인은 가상환경 Python으로 `-m unittest discover -s tests -p test_market_analyzer.py`를 실행한다. 위 원본 CSV와 같은 계획을 macOS에서도 한 번 실행해 비교한 뒤 통합 환경을 확정한다.
