# 입도객 전년 동월 비교와 자료 결합 요청

2026-11-20 Windows에서 앱 구현 커밋 `6d722a9`를 실행했다. 로컬 Python 3.12.14, Streamlit 1.67.0, openpyxl 3.1.5, Chrome을 사용했다. 2019년 CSV와 2026년 9월 기준 공식 XLSX를 각각 [데이터 활용 명세](DATA_SPEC.md)에 따라 준비했다.

| 질문 | 확인한 응답 | 화면 |
| --- | --- | --- |
| 2026년 9월 제주 입도객을 전년 동월과 비교해줘 | 2025-09 1,181,507명 → 2026-09 1,123,339명. −58,168명 (−4.92%). 두 관측월과 제공처·출처 표시 조건을 표시한다. | [전년 동월 비교](assets/recent-arrivals/06-arrivals-yoy.png) |
| 2026년 9월 제주 입도객과 같은 달 연동 한식 카드 이용금액을 결합해줘 | 자료 두 건의 기간·지역 단위를 표시한다. 요청 월은 공통 관측 기간(2019-01~2019-12) 밖이고 제주 전체와 읍면동을 직접 연결할 규칙이 없어 결합 집계를 실행하지 않는다. | [결합 요청 안내](assets/recent-arrivals/07-join-guard.png) |

Windows에서 두 실제 데이터 파일을 준비한 뒤 `python -m unittest discover -s tests -p 'test_*.py'`를 실행했다. 22건이 통과했다. 기존 상권 재분석과 신규 입도객·결합 요청의 Streamlit 흐름을 포함한다.

## 선택적 로컬 SLM 시험

Intel i5-7200U에서 GPU 레이어 0개, CPU 스레드 2개로 [llama.cpp b12541](https://github.com/ggml-org/llama.cpp/releases/tag/b12541)과 [Qwen2.5-0.5B-Instruct Q4_K_M](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/blob/main/qwen2.5-0.5b-instruct-q4_k_m.gguf)을 시험했다. JSON에 의도·연도·월·지역·업종·제외월만 채우도록 같은 프롬프트를 사용했다.

상권 첫 질문, 제외 월 후속 요청, 전년 동월 비교, 결합 요청, 입도객 비교의 다른 표현까지 총 5개 질문에서 여섯 필드를 모두 맞힌 응답은 0개였다. 1개는 출력 상한까지 JSON을 닫지 못했고, 나머지는 의도나 조건이 달랐다. 실행마다 모델을 새로 읽었으며 질문당 6.02~12.27초가 걸렸다. 제출 앱은 규칙 기반 플래너를 사용한다. 시험은 개인 Windows PC에서 진행했고 센터 PC는 미측정이다.
