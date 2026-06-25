## Summary
최종답 검증을 단일 문제 하드코딩에서 벗어나, 범용 산술/대수식 치환 검산기와 특화 finite-search 플러그인으로 구성된 일반 검증 프레임워크로 확장한다.

## Motivation
현재 이집트 분수 회귀 방어는 유효하지만, 단일 패턴 하드코딩으로는 전반적인 정확도 향상에 한계가 있다.

## Current Behavior
- 특정 문제형만 직접 검증
- 일반적인 명시적 후보해는 공통적으로 검산되지 않음
- finite-case 누락 탐색도 단일 케이스용

## Expected Behavior
- 문제에 단순 산술/대수식이 있으면 명시적 후보해를 공통 치환 검산
- 조건식(`x <= y <= z`, 양의 정수 등)도 함께 검사
- 유한 열거가 가능한 일부 유형은 플러그인으로 누락 해 탐색
- verifier가 반례를 찾으면 무조건 INVALID

## Scope
- `mystic/final_answer_verifier.py`를 범용 프레임워크로 재구성
- AST 기반 안전 산술식 평가 추가
- 일반 tuple assignment 추출 추가
- 이집트 분수 finite-search는 framework plugin으로 편입
- 회귀 테스트 추가

## Acceptance Criteria
- `x + y = 5`, 후보 `(2,3)`은 통과
- `x + y = 5`, 후보 `(2,2)`는 INVALID
- `x <= y <= z`, positive integers 조건도 검증
- 기존 이집트 분수 회귀도 그대로 통과

## Verification Plan
- parser/verifier 단위 테스트
- Python compile 확인
