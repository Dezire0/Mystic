## Summary
Discord 연구실 응답을 한 번에 최종 결과만 보내는 방식에서, 질문 이해부터 검증까지 단계별 진행 메시지를 순차 전송하는 방식으로 바꾼다. 동시에 연구실 출력 언어를 한국어로 고정한다.

## Motivation
현재는 사용자가 답이 나오기 전까지 연구실이 무엇을 하는지 알기 어렵고, 출력도 영어가 섞여 직관성이 떨어진다.

## Current Behavior
- 연구실 답변이 완료 후 한 번에 전송됨
- 중간 진행 상태가 보이지 않음
- 이해/전략/결론 문장이 영어로 나올 수 있음

## Expected Behavior
- 연구실이 `질문 이해 → 전략 수립 → 풀이 생성 → Raven 검증 → 최종 답변` 순서로 진행 메시지를 보낸다
- 최종 메시지 전에도 사용자가 현재 단계를 볼 수 있다
- 핵심 풀이 설명은 한국어로 나온다

## Scope
- `mystic/research_lab.py`에 progress callback 추가
- 한국어 고정 프롬프트 보강
- `scripts/run_discord_bot.py`에서 단계별 메시지 전송
- 테스트 추가

## Acceptance Criteria
- DM/멘션 질문 시 단계 메시지가 순차 전송된다
- 최종 결과는 기존처럼 embed로 정리된다
- 연구실 출력 섹션은 한국어 기준으로 생성된다
- 테스트가 통과한다

## Verification Plan
- 단위 테스트로 progress callback 순서 검증
- `.venv-discord` 테스트 통과
- Discord bot service 재시작 후 상태 확인
