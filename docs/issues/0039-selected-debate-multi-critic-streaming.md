## Summary
Mystic 연구실을 selected specialist 전용 토론 구조로 확장하고, Core 비평 뇌를 다중화하며, 디스코드 진행 로그를 단계별 세분화 스트리밍으로 개선한다.

## Motivation
현재 구조는 primary/support specialist fan-out과 단일 plan critic까지는 있으나, 방법 제안과 역할 재분배가 약하고, selected specialist 간 전면 objection/debate가 없으며, 디스코드 출력도 단계당 한 덩어리라 실제 작업 흐름이 잘 보이지 않는다.

## Current Behavior
- Core가 primary + support specialist를 선택한다
- 단일 Core plan critic만 존재한다
- specialist별 초안 후 제한적인 cross-review만 있다
- selected specialist 전원 간 objection/debate가 없다
- 디스코드 봇은 stage당 한 개 메시지 위주로 보낸다

## Expected Behavior
- CorePlan / Completeness / Counterexample / Cost-Latency critic이 계획을 각각 공격한다
- selected specialist가 각자 자기 분야 풀이법과 맡을 수 있는 태스크를 제안한다
- Core가 이를 조합해 태스크를 재분배한다
- selected specialist만 서로 전원 objection을 생성한다
- objection 이후 각 specialist가 자기 태스크 결과를 보완한다
- 디스코드 봇은 작업 단계와 결정 내역을 더 작은 로그 단위로 순차 전송한다

## Scope
- `mystic/research_lab.py` orchestration 재구성
- progress stage 및 payload 확장
- `scripts/run_discord_bot.py` 단계 로그 세분화
- 테스트 갱신

## Acceptance Criteria
- progress에 `completeness_critic_complete`, `counterexample_critic_complete`, `cost_latency_critic_complete`가 추가된다
- selected specialist만 pairwise objection 대상이 된다
- 방법 제안 → 태스크 재분배 → 태스크 실행 → objection → revision 순서가 드러난다
- 디스코드에서 단계별 로그가 여러 개의 짧은 메시지로 분리되어 보인다
- 최종 Raven/결정적 검증 경로는 유지된다

## Verification Plan
- `.venv-discord/bin/python -m unittest tests.test_research_lab tests.test_discord_bot_messages`
- `.venv-discord/bin/python -m py_compile mystic/research_lab.py scripts/run_discord_bot.py`
