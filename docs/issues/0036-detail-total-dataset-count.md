## Summary
Discord 봇 전문가 디테일 창에 해당 specialist가 지금까지 학습한 총 데이터셋 수를 별도 필드로 표시한다.

## Motivation
현재는 `3/19 datasets` 같은 진행 정보는 있지만, 사용자가 “지금까지 총 몇 개를 학습했는지”를 즉시 읽기 어렵다.

## Current Behavior
- 디테일 창에 `데이터셋 진행`만 있음
- 총 학습 데이터셋 수가 별도 항목으로 보이지 않음

## Expected Behavior
- 디테일 창에 `총 학습 데이터셋` 필드 추가
- 예: `7개`
- 기존 `데이터셋 진행` 필드는 유지

## Scope
- `mystic/discord_dashboard.py` snapshot/detail payload 수정
- 대시보드 테스트 갱신

## Acceptance Criteria
- 디테일 창에 총 데이터셋 수가 노출된다
- 기존 진행률/레벨/실패 로그 등은 그대로 유지된다

## Verification Plan
- `python -m unittest tests.test_discord_dashboard`
