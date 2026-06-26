## Summary
연구실 원격 reasoning 중 Groq/OpenAI-compatible 429 rate limit가 발생해 전체 실행이 실패하는 문제를 수정한다.

## Motivation
현재는 원격 specialist fan-out 중 한 요청만 429를 받아도 연구실 전체가 중단된다. 재시도와 로컬 폴백이 필요하다.

## Current Behavior
- OpenAICompatibleClient는 짧은 고정 재시도만 수행한다
- 429가 반복되면 `LLMClientError`로 즉시 실패한다
- research_lab의 원격 specialist 호출은 단계별 로컬 폴백이 없다
- 기본 병렬 reasoning이 원격 provider rate limit를 쉽게 유발할 수 있다

## Expected Behavior
- 429 응답에서 Retry-After 또는 지수 backoff를 사용해 더 안정적으로 재시도한다
- 원격 specialist 호출이 최종 실패하면 같은 프롬프트를 로컬 fallback backend로 재시도한다
- OpenAI-compatible 원격 backend는 명시 override가 없으면 기본 병렬도를 보수적으로 운영한다
- 연구실 전체는 가능한 한 계속 진행된다

## Scope
- mystic/llm_client.py 재시도 정책 개선
- mystic/research_lab.py 원격->로컬 단계별 폴백 추가
- 테스트 추가

## Acceptance Criteria
- 429를 받는 specialist 호출이 로컬 폴백으로 계속 진행된다
- 테스트가 통과한다
- 디스코드 봇 연구실이 동일 오류로 즉시 중단되지 않는다

## Verification Plan
- .venv-discord/bin/python -m unittest tests.test_research_lab tests.test_discord_bot_messages tests.test_public_prepare
- .venv-discord/bin/python -m py_compile mystic/llm_client.py mystic/research_lab.py scripts/run_discord_bot.py
