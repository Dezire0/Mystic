## Summary
Mystic 연구실에 planner 주도 실행 예산 제어와 종료 규칙을 추가한다. 하드코딩된 문제 유형 제한 없이 planner가 문제별로 fast/medium/full 수준의 실행 깊이를 결정하고, 분기 닫힘/완전성 확보가 확인되면 불필요한 debate/revision 단계를 축소한다.

## Motivation
현재는 쉬운 유한 분기 정수문제에도 연구실 전체 프로토콜이 거의 전부 실행되어 지연이 크다. 문제 종류를 코드에 하드코딩하는 대신 planner가 문제 구조와 불확실성을 보고 적절한 실행 예산을 정해야 한다.

## Current Behavior
- planner는 초기 전략만 세우고 실행 깊이를 통제하지 않는다
- critic/proposal/execution/debate/revision이 거의 항상 동일하게 돈다
- bounded case가 이미 닫혀도 후속 단계가 과하게 실행될 수 있다

## Expected Behavior
- planner가 `execution_mode`, `selected_count_cap`, `debate_rounds`, `require_revision`, `early_stop_if_closed` 같은 실행 예산을 정한다
- fast/medium/full은 planner의 판단 결과이지, 문제 유형 하드코딩이 아니다
- specialist 실행 결과와 objection 결과를 보고 종료 규칙이 맞으면 debate/revision을 축소하거나 건너뛴다

## Scope
- `mystic/research_lab.py` planner 출력 및 orchestration 확장
- progress 로그에 planning budget / early stop 상태 추가
- 테스트 갱신

## Acceptance Criteria
- planner 결과에 실행 예산이 포함된다
- selected specialist 수가 planner cap으로 제한될 수 있다
- 종료 조건이 만족되면 objection/revision 또는 일부 후속 단계가 축소된다
- 테스트가 통과한다

## Verification Plan
- `.venv-discord/bin/python -m unittest tests.test_research_lab tests.test_discord_bot_messages tests.test_public_prepare`
- `.venv-discord/bin/python -m py_compile mystic/research_lab.py scripts/run_discord_bot.py`
