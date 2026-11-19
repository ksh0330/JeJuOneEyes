# 최종 결과물 안내

「제주 AI·빅데이터 활용 AI Agent 개발 챌린지」 최종 ZIP의 구성과 확인 방법이다. ZIP은 이 저장소의 한 커밋을 그대로 묶었다. 원본 데이터 파일은 넣지 않았으며, 각 공식 페이지에서 받아 `data/local/`에 둔다.

## 공식 항목과 파일

| 공식 항목 | 파일 |
| --- | --- |
| 실행 소스 코드 | `app/`(Streamlit 화면), `core/planner/`(질문 → 분석 계획), `core/kg/`(자료 카탈로그), `core/connectors/`·`core/analyzer/`(로컬 파일 읽기·검증·집계), `contracts/`(계획·결과·카탈로그 JSON 계약), `tests/` |
| 실행환경·매뉴얼 | [README](../README.md), [앱 실행 안내](../app/README.md), [사용자 매뉴얼](USER_MANUAL.md), 의존성 `app/requirements.txt`·`core/analyzer/requirements.txt`, 환경변수 예시 `.env.example`, 화면 설정 `.streamlit/config.toml` |
| 데이터 활용 명세 | [데이터 활용 명세](DATA_SPEC.md), 아래 외부 데이터·오픈소스 목록 |
| 결과 설명자료 | [공통 설계](ARCHITECTURE.md), [대표 시연 기록](RESULT_REPORT.md), [입도객·결합 요청 시연 기록](RECENT_ARRIVALS_DEMO.md), [제품 요구사항](../AGENTS.md), 아래 최종 확인 결과 |

## 사용 모델과 Prompt

- **제품 실행.** 제출 앱은 규칙 기반 플래너(`core/planner/`)로 질문을 분석 계획 JSON으로 바꾸고, 로컬 Python 엔진(`core/analyzer/`)이 집계한다. 실행 중 언어 모델을 호출하지 않으므로 제품 Prompt와 API Key가 없다. 같은 자료와 조건에서는 같은 결과가 나온다.
- **로컬 SLM 시험.** Qwen2.5-0.5B-Instruct Q4_K_M(llama.cpp b12541, CPU)을 의도·조건 추출에 시험했고, 5개 질문 중 모든 조건을 맞힌 응답이 없어 제품에 연결하지 않았다. 측정 내용은 [입도객·결합 요청 시연 기록](RECENT_ARRIVALS_DEMO.md)에 있다.
- **개발 보조 AI.** 팀은 코드 구현·리뷰와 문서 작성에 Anthropic Claude(Claude Code)와 OpenAI Codex를 사용했다. 시작 Prompt는 [팀 작업 가이드](TEAM_WORKFLOW.md)에 있다. 수치와 기능 설명은 실제 실행 결과와 대조했다. 센터 원자료와 실제 키는 AI 도구에 입력하지 않았다.

## 외부 데이터

| 자료 | 출처 | 이용조건 | 로컬 파일 |
| --- | --- | --- | --- |
| 상권분석 매쉬업 2019 (필수 데이터) | [제주데이터허브](https://jejudatahub.net/data/view/data/748) | 제주데이터허브 공개 자료 이용조건 | `data/local/제주특별자치도_주제3_상권분석을 위한 유동인구에 따른 카드 매출액 변화 데이터 활용_매쉬업결과_19.csv` |
| 월별 입도 관광객 확정치 | [제주관광공사 제주관광데이터랩](https://data.ijto.or.kr/prog/rpstr/bigdata/sub04_01/view.do?regSn=476), 원자료 제주특별자치도관광협회 | 공공누리 제1유형(출처 표시) | `data/local/jeju-arrivals.xlsx` |

파일 버전, 해시, 집계 기준은 [데이터 활용 명세](DATA_SPEC.md)에 있다. 대회 참가자용 엑셀 2종은 구조 확인에만 참고했고 실행과 ZIP에 사용하지 않았다.

## 오픈소스

| 이름 | 확인 버전 | 라이선스 | 용도 |
| --- | --- | --- | --- |
| Python | 3.12.14 | PSF License | 실행 환경 |
| Streamlit | 1.67.0 | Apache-2.0 | 화면 |
| pandas | 3.1.1 | BSD-3-Clause | 표 렌더링 |
| openpyxl | 3.1.5 | MIT | 입도객 XLSX 읽기 |
| jsonschema | 4.26.0 | MIT | 계획·카탈로그 계약 검증 |

Streamlit이 설치하는 Altair(BSD-3-Clause), NumPy(BSD-3-Clause), PyArrow(Apache-2.0) 등은 차트와 표 렌더링에 함께 쓰인다. 로컬 SLM 시험에는 llama.cpp(MIT)와 Qwen2.5-0.5B-Instruct(Apache-2.0)를 사용했으며 제출 앱에는 포함하지 않았다. 외부 코드를 복사해 넣지 않았다.

## 환경변수와 외부 서비스

- 앱은 환경변수나 API Key 없이 실행된다. `.env.example`은 값이 없는 안내 파일이다. 파일 경로는 화면 사이드바에서 바꿀 수 있다.
- 네트워크는 설치 단계(Python 패키지 설치, 두 공개 파일 내려받기)에만 필요하다. 실행 중에는 외부 API를 호출하지 않는다. `.streamlit/config.toml`이 사용 통계 전송을 끄고 `localhost`에서만 연다. 화면의 출처 링크는 사용자가 누를 때만 열린다.

## 재현 절차

1. ZIP을 풀고 [앱 실행 안내](../app/README.md)대로 Python 3.12 가상환경을 만들어 `app/requirements.txt`를 설치한다.
2. [데이터 활용 명세](DATA_SPEC.md)의 두 공개 파일을 `data/local/`에 둔다.
3. `python -m unittest discover -s tests -p 'test_*.py'`를 실행한다. 두 파일이 있으면 실제 자료 검산과 화면 흐름 테스트까지 실행된다.
4. `python -m streamlit run app/main.py`로 앱을 열고 아래 대표 질문을 실행한다.

| 질문 | 기대 결과 |
| --- | --- |
| `2019년 연동과 노형동의 한식 음식점업 카드 이용금액을 비교해줘` | 연동 33,833,494,533원, 노형동 32,321,443,476원, 관측 12개월 |
| 이어서 `7~8월 빼고 다시` | 연동 28,067,882,813원, 노형동 26,632,168,999원, 관측 10개월, 지역·업종 유지 |
| `2026년 9월 제주 입도객을 전년 동월과 비교해줘` | 2025-09 1,181,507명 → 2026-09 1,123,339명, −58,168명(−4.92%) |
| `2026년 9월 제주 입도객과 같은 달 연동 한식 카드 이용금액을 결합해줘` | 지역 단위(읍면동 / 제주특별자치도 전체)와 공통 관측 기간(2019-01~2019-12) 차이로 결합하지 않고, 각 자료의 단독 분석 질문을 제시 |

## 최종 확인 결과

ZIP을 새 폴더에 풀어 위 절차를 처음부터 실행한 결과는 [최종 실행 확인](FINAL_CHECK.md)에 있다.
