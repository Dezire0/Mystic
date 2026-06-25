## Summary
Mystic 연구실을 단일 specialist 풀이에서 Core 중심 다중 specialist orchestration으로 확장한다. Core가 여러 specialist를 선택하고, 각 specialist가 자기 위치에서 풀이 초안을 낸 뒤, Core가 이를 종합하고 Raven/검증기로 마감한다.

## Motivation
현재는 한 specialist의 품질이 곧 전체 품질이 되며, Core planning과 cross-check가 약하다.

## Current Behavior
- 연구실은 사실상 1개 specialist 중심
- Raven은 사후 검토 위주
- specialist 간 병렬적 관점 수집이 거의 없음

## Expected Behavior
- Core가 primary + support specialists를 선택
- 각 specialist가 가능한 풀이/공격 관점을 낸다
- Core synthesis 단계에서 이를 종합
- 디스코드 단계 메시지에도 specialist별 진행이 드러난다

## Scope
- `mystic/research_lab.py` 다중 specialist fan-out 추가
- progress callback stage 확장
- Discord bot progress 메시지 확장
- 테스트 갱신

## Acceptance Criteria
- 연구실 결과에 참여 specialist 목록이 포함된다
- support specialists가 최소 2개 이상 선택될 수 있다
- specialist별 초안 후 synthesis가 일어난다
- 기존 Raven/최종 검증 경로는 유지된다

## Verification Plan
- `python -m unittest tests.test_research_lab tests.test_discord_bot_messages`
- `python -m py_compile mystic/research_lab.py scripts/run_discord_bot.py`
