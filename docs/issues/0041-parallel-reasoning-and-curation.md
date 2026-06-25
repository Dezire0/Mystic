## Summary
Mystic 연구실의 selected specialist 단계 병렬화를 추가하고, specialist/core/router/planner 학습 데이터가 실제로 어떻게 준비되는지 점검한 뒤 품질 중심 선별 경로를 강화한다.

## Motivation
현재 연구실은 heavy specialist가 원격으로 연결되더라도 호출이 거의 직렬이라 지연이 크다. 또한 specialist/core는 train-ready 파이프라인이 있으나, router/planner는 분리된 역할 대비 데이터 선별 경로가 충분히 명시적이지 않다.

## Current Behavior
- method proposal / task execution / objection / revision 단계가 대부분 직렬 호출이다
- heavy specialist는 원격 가능하지만 호출 수가 많아 느리다
- core 학습은 `core_router_lora_v0` 중심이다
- planner 전용 데이터셋/adapter는 아직 분리되어 있지 않다
- train-ready 구성은 있으나 품질 선별 기준이 약하다

## Expected Behavior
- selected specialist의 proposal/execution/revision과 pairwise objection 생성은 가능한 범위에서 병렬 실행된다
- worklog에 병렬 처리 이후에도 specialist별 backend/model이 보인다
- 현재 어떤 agent가 실제 train-ready 대상으로 학습되는지 명확히 설명 가능하다
- 고품질 데이터 선별 규칙을 코드에 반영해 specialist/core/router/planner 데이터 품질을 끌어올린다

## Scope
- `mystic/research_lab.py` 단계 병렬화
- training/prepare 또는 public train-ready preparation 경로 점검 및 품질 필터 강화
- 관련 테스트 갱신

## Acceptance Criteria
- selected specialist proposal/execution/revision 단계가 병렬 처리된다
- objection 생성도 selected specialist pairwise 단위에서 병렬 처리된다
- 테스트가 통과한다
- specialist/core/router/planner 학습 상태와 데이터 선별 상태를 설명할 수 있다

## Verification Plan
- `.venv-discord/bin/python -m unittest tests.test_research_lab tests.test_discord_bot_messages`
- `.venv-discord/bin/python -m py_compile mystic/research_lab.py scripts/run_discord_bot.py`
