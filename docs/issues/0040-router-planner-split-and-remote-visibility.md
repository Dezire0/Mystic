## Summary
Mystic 연구실에서 router를 경량화하고 Core planner를 별도 단계로 분리하며, 원격 reasoning backend 사용 여부와 병목 원인을 더 명확하게 드러낸다.

## Motivation
현재 router가 specialist 선택과 초기 전략까지 같이 맡아 부담이 크고, 사용자는 heavy specialist가 실제로 원격으로 도는지 즉시 확인하기 어렵다. 또한 느린 이유가 모델 자체인지, 원격 미설정인지, 호출 수 과다인지 구분이 잘 안 된다.

## Current Behavior
- router가 specialist 선택과 초기 strategy까지 함께 생성한다
- heavy specialist는 원격 가능하지만 환경변수가 없으면 조용히 로컬 fallback 된다
- 진행 로그에서 어떤 specialist가 원격/로컬로 실행됐는지 즉시 파악하기 어렵다

## Expected Behavior
- router는 primary/support specialist 선택과 간단한 라우팅 이유만 담당한다
- Core planner가 초기 실행 전략을 별도 단계에서 생성한다
- progress 로그에 remote enabled 여부와 실제 specialist backend가 더 분명히 나타난다
- 원격이 느린 이유를 코드 구조상 설명할 수 있는 상태가 된다

## Scope
- `mystic/research_lab.py`의 router/planner 분리
- progress stage에 planner 단계 추가
- remote enablement 상태와 selected specialist backend 정보 강화
- 테스트 갱신

## Acceptance Criteria
- `run_research_lab()`가 `route_question()` 다음에 별도 `plan_question()` 단계를 거친다
- progress에 `planning_complete`가 추가된다
- 결과 로그에서 heavy specialist의 backend/model을 더 쉽게 확인할 수 있다
- 기존 multi-critic / debate / Raven 검증 흐름은 유지된다

## Verification Plan
- `.venv-discord/bin/python -m unittest tests.test_research_lab tests.test_discord_bot_messages`
- `.venv-discord/bin/python -m py_compile mystic/research_lab.py scripts/run_discord_bot.py`
