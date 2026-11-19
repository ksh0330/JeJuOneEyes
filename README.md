# JeJuOneEyes

제주빅데이터센터 방문자를 위한 자연어 데이터 탐색·분석 Agent입니다. 상인, 도민, 기업·공공기관 실무자가 센터 PC에서 업무 질문을 입력하면, 이용 가능한 데이터를 찾아 전처리·집계하고 표, 차트, 근거로 답하는 것을 목표로 합니다.

현재 로컬 MVP에서 2019년 상권 재분석, 제주 전체 월별 입도객 전년 동월 비교, 두 자료의 결합 요청에 대한 근거 안내를 제공합니다. 실행 방법은 [앱 매뉴얼](app/README.md), 실제 파일과 이용조건은 [데이터 활용 명세](docs/DATA_SPEC.md)에 있습니다. 제품 요구사항과 팀 지침은 [AGENTS.md](AGENTS.md)에서 확인합니다.

## 처음 실행하는 경우

1. [앱 실행 안내](app/README.md)대로 Python 3.12 가상환경을 만들고 의존성을 설치합니다.
2. [데이터 활용 명세](docs/DATA_SPEC.md)의 공개 파일 두 개를 `data/local/`에 둡니다. 환경변수와 API Key는 필요 없습니다.
3. `python -m streamlit run app/main.py`로 실행하고 [사용자 매뉴얼](docs/USER_MANUAL.md)의 예시 질문을 입력합니다.

대회 제출물의 항목별 파일, 사용 모델과 AI 활용 범위, 외부 데이터·오픈소스, 최종 실행 확인은 [최종 결과물 안내](docs/SUBMISSION_GUIDE.md)에 있습니다.

## 팀 시작 문서

- [팀 작업 가이드](docs/TEAM_WORKFLOW.md)에서 클론, worktree, 모델 설정, Claude·Codex·Gemini 프롬프트를 확인합니다.
- [공통 설계](docs/ARCHITECTURE.md)와 [JSON 계약](contracts/)에서 모듈의 입출력과 첫 구현 범위를 확인합니다.
- [제출 준비](docs/SUBMISSION_PLAN.md)에서 기획서 구성, 실행 증거, 최종 ZIP에 들어갈 항목을 확인합니다.

대회 첨부 엑셀과 센터 원자료는 사용 권한이 있는 환경에서 로컬로 준비합니다.
