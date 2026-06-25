## Summary
이집트 분수형 정수해 문제에서 Prime이 잘못 생성한 후보 튜플 `(3,6,4), (4,5,7)`를 deterministic verifier가 모두 잡는 회귀 테스트를 추가한다.

## Motivation
현재 구조상 Prime은 아이디어 생성기이고, 최종 정답 판정은 Raven + deterministic verifier가 맡아야 한다. 이 역할 분리가 실제로 유지되는지 회귀 테스트로 고정할 필요가 있다.

## Current Behavior
- verifier는 모든 후보를 검사하도록 설계되어 있음
- 하지만 해당 실제 실패 사례가 테스트에 고정되어 있지 않음

## Expected Behavior
- `(3,6,4)`는 순서 조건과 방정식 둘 다 위반으로 INVALID
- `(4,5,7)`는 방정식 불만족으로 INVALID
- `(2,4,4)` 누락도 INVALID

## Scope
- parser/verifier regression tests 추가

## Acceptance Criteria
- 위 사례들이 테스트로 고정된다
- Raven raw verdict가 무엇이든 parser 결과는 INVALID가 된다

## Verification Plan
- `python -m unittest tests.test_parsers`
