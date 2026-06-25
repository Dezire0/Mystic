## Summary
최종답 검증기가 후보해에 없는 변수를 만났을 때 연구실 전체를 실패시키지 않도록 수정한다.

## Motivation
검증 계층은 정확도를 높이기 위한 보조 수단이지, 연구실 전체를 다운시키는 실패점이 되면 안 된다.

## Current Behavior
- 문제 식에 후보해로 대입되지 않은 변수가 있으면 `Unknown variable: z` 예외 발생
- 디스코드 연구실이 그대로 실패 메시지를 보냄

## Expected Behavior
- 후보해로 평가 가능한 식만 검증
- 변수 불일치나 검증 불가 상황은 조용히 스킵
- verifier 내부 예외는 parser에서 안전하게 흡수
- 연구실은 계속 답변을 진행

## Scope
- `mystic/final_answer_verifier.py` 안전성 보강
- `mystic/parsers.py` verifier exception guard 추가
- 회귀 테스트 추가

## Acceptance Criteria
- `Unknown variable`로 연구실이 크래시하지 않는다
- 검증 가능한 케이스는 계속 INVALID/VALID를 강제한다
- 검증 불가 케이스는 원래 Raven verdict를 유지한다

## Verification Plan
- parser/verifier 단위 테스트
- py_compile 확인
