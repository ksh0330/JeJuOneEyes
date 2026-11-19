# 분석 계획 플래너

질문·선택지·후속 요청을 [AnalysisPlan v1](../../contracts/analysis-plan.schema.json)로 바꾼다.

- `plan_from_text(text)`: 첫 질문. 지역·지표·업종처럼 결과가 달라지는 조건이 빠지면 `needs_input`과 선택지(`Clarification`)를 돌려준다. 기간이 없으면 등록 자료 기간(2019년 1~12월)을 쓰고 그 사실을 `notes`에 남긴다.
- `plan_from_choices(...)`: 안내형 선택지. 같은 조건이면 자연어와 같은 계획을 만든다.
- `apply_followup(previous, text)`: 직전 계획을 복사해 요청에서 언급한 필드만 바꾸고 전체를 다시 검증한다. 바뀐 조건은 `changes`로 돌려준다. 지원하지 않는 요청(결제 건수, 등록되지 않은 지역·업종)은 `unsupported`와 사유를 주고 직전 계획을 유지한다.
- `1월과 12월`처럼 월을 따로 지정하면 사이의 달을 제외한다. 후속 요청에서 분석할 월이나 월 범위를 새로 지정하면 월 선택을 다시 설정한다. `7~8월 빼고 다시`처럼 제외할 월만 지정하면 직전 기간을 유지한다.
- `apply_answers(response, answers)`: 확인 질문에 대한 답을 계획에 채운다.
- `describe_plan(plan)`, `diff_plans(before, after)`: 화면용 조건 표와 변경 목록.

첫 구현은 규칙 기반이며 결과가 결정적이다. 지원 어휘는 [`vocabulary.py`](vocabulary.py)에 두고, 분석 엔진이 지원하는 ID와 일치하는지 `tests/test_planner.py`가 확인한다. 로컬 SLM(Qwen2.5-1.5B-Instruct Q4_K_M, llama.cpp CPU 후보)을 연결할 때는 모델이 같은 `Extraction`을 만들도록 하고 계획 조립·검증·후속 병합은 이 모듈을 재사용한다. 제품 프롬프트는 그때 `core/planner/prompts/`에 추가한다.
