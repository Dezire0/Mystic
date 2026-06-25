## Summary
Mystic 디스코드 대시보드에 학습 진행 기반 레벨/경험치 바 표현을 추가하고, Discord 전용 런타임 의존성에서 `requests` 누락으로 연구실이 실패하는 문제를 수정한다.

## Motivation
현재 퍼센트만으로는 “얼마나 학습됐는지” 체감이 약하고, 봇 런타임에 `requests`가 없으면 연구실이 HTTP backend 호출 단계에서 실패한다.

## Current Behavior
- 대시보드는 `%`와 텍스트 위주로 표시됨
- 레벨업/경험치처럼 직관적인 표현이 없음
- `.venv-discord`에 `requests`가 없어 `Ollama/OpenAI-compatible` 호출이 실패할 수 있음

## Expected Behavior
- 각 expert에 `레벨 + XP bar`가 표시된다
- 상세 페이지에서 다음 레벨까지의 상태를 볼 수 있다
- Discord bot runtime dependencies에 `requests`가 포함된다
- 연구실이 `requests` 누락으로 죽지 않는다

## Scope
- `mystic/discord_dashboard.py` 레벨 표현 추가
- `requirements-discord.txt` 의존성 보강
- 테스트 추가/수정
- 봇 런타임에 실제 패키지 설치

## Acceptance Criteria
- overview/detail 페이지에 레벨 정보가 표시된다
- 기존 progress bar는 유지되거나 더 읽기 쉽게 대체된다
- `.venv-discord`에서 `requests` import 가능
- 연구실 HTTP backend 호출이 `requests` 누락으로 실패하지 않는다

## Verification Plan
- 단위 테스트 통과
- `.venv-discord`에서 `import requests` 확인
- 디스코드 봇 서비스 재시작 후 상태 확인
