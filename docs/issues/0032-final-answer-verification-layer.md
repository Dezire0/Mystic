## Summary
Raven 판정 전에 최종 답안 후보를 규칙 기반으로 검산하는 레이어를 추가한다. 특히 이집트 분수형 정수해 문제에서 후보 순서쌍 치환 검산과 누락 해 탐색을 수행하고, 오류가 있으면 강제로 `INVALID`를 반환한다.

## Motivation
현재는 생성 모델이 `(2,4,8)` 같은 틀린 튜플을 제시해도 Raven이 `GAP` 수준으로만 판단할 수 있어 수학적 신뢰도가 무너진다.

## Problem
- 명시적 후보 해가 있는 문제에서 최종답 검산이 없음
- 단순 대입으로 바로 틀린 후보도 `INVALID`가 아닌 `GAP/NEEDS_MORE_DETAIL`로 남을 수 있음
- 유한 케이스에서 완전 분류 문제인데도 누락 해를 잡지 못함

## Current Behavior
- Raven verdict는 LLM 출력에 크게 의존
- 규칙 기반 대입 검증 없음

## Expected Behavior
- 후보 튜플 추출
- 간단한 산술/대수식이면 직접 치환 검증
- 틀린 후보가 하나라도 있으면 `INVALID`
- 유한 탐색 가능한 경우 누락 해도 검출
- 이집트 분수형 정수해 문제에 대해 회귀 테스트 추가

## Scope
- verifier 모듈 추가
- `parse_raven_output`에 verification hook 추가
- `mystic_loop.py`, `research_lab.py`, 평가 스크립트 등 parser 호출부에 문제/답안 전달
- 회귀 테스트 추가

## Acceptance Criteria
- `1/x + 1/y + 1/z = 1, x <= y <= z, positive integers` 문제에서 `(2,4,8)` 포함 답은 `INVALID`
- `(2,4,4)` 누락도 치명 오류로 잡힌다
- 올바른 해 집합 `(2,3,6), (2,4,4), (3,3,3)`는 통과한다

## Verification Plan
- parser/verifier 단위 테스트
- 회귀 테스트로 잘못된 Raven 출력 강제 INVALID 확인
