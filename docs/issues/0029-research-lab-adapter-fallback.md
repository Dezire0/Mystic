## Summary
Discord 연구실 실행 시 활성 Raven backend가 `adapter`로 설정되어 있지만 봇 런타임에 `torch`가 없을 경우, 연구실이 실패하지 않고 기본 Raven backend로 자동 폴백되도록 수정한다.

## Motivation
디스코드 봇은 가벼운 `.venv-discord`에서 돌아가고, 여기에 항상 PEFT/torch 스택이 설치되어 있지는 않다. 현재는 이 상태에서 연구실이 전혀 답하지 못한다.

## Problem
- `active_raven_backend=adapter`면 `build_critic_client()`가 무조건 adapter 로딩 시도
- `torch` 또는 `peft`가 없으면 `RuntimeError`로 즉시 실패
- 사용자에게는 "연구실 실행 실패"만 노출됨

## Current Behavior
- adapter critic 의존성이 없으면 연구실 전체 실패

## Expected Behavior
- adapter critic 로딩 실패 시 기본 Raven backend로 자동 폴백
- 실제 사용된 critic backend/model이 결과에 반영
- 경고는 로그에 남기되 사용자 응답은 계속 진행

## Scope
- `mystic/research_lab.py` critic backend 선택 로직 수정
- 폴백 테스트 추가
- README에 동작 설명 보강

## Acceptance Criteria
- adapter dependency missing 상황에서 `run_research_lab()`가 계속 동작한다
- fallback backend는 `backend` + `raven_model` 조합을 사용한다
- 기존 adapter 성공 경로는 유지된다

## Verification Plan
- 단위 테스트로 adapter 실패 후 ollama fallback 검증
- `.venv-discord` 환경에서 연구실 테스트 통과
- 디스코드 봇 서비스 재시작 후 상태 확인
