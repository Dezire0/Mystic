## Summary
Mystic 연구실에 Core plan critic, specialist cross-review, heavy reasoning agent의 원격 backend 분리를 추가한다.

## Motivation
현재는 Core fan-out은 생겼지만, 계획 자체를 공격하는 뇌와 specialist 간 상호 비평이 부족하고, 무거운 reasoning agent가 모두 로컬에 걸려 성능/품질 한계가 크다.

## Current Behavior
- Core routing은 있음
- support specialists fan-out은 있음
- Core plan critic 없음
- specialist cross-review 없음
- heavy reasoning agent의 원격 분리 없음

## Expected Behavior
- Core가 세운 계획을 plan critic이 먼저 공격한다
- specialist 초안 이후 cross-review 단계가 생긴다
- synthesis는 specialist draft + review를 함께 본다
- 특정 heavy specialist는 원격 OpenAI-compatible backend로 분리 가능하다

## Scope
- `mystic/research_lab.py` orchestration 확장
- progress stage 확장
- Discord bot progress 메시지 확장
- 테스트 갱신

## Acceptance Criteria
- progress에 `plan_critic_complete`, `cross_review_complete`가 나타난다
- result에 참여 specialist는 유지된다
- 원격 설정이 있을 때 heavy specialist는 원격 backend/model 사용 가능
- 설정이 없으면 로컬 fallback

## Verification Plan
- `.venv-discord/bin/python -m unittest tests.test_research_lab tests.test_discord_bot_messages tests.test_discord_dashboard`
- `.venv-discord/bin/python -m py_compile mystic/research_lab.py scripts/run_discord_bot.py`
