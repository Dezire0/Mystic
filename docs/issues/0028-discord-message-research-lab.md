## Summary
Discord 봇이 슬래시 명령어 없이도 DM 일반 메시지와 길드 내 `@멘션`에 반응해 Mystic 연구실 답변을 제공하도록 확장한다.

## Motivation
사용자가 slash command 없이 자연스럽게 질문을 보내도 바로 연구실 응답을 받게 해야 실제 사용성이 올라간다.

## Current Behavior
- `/mystic_lab` 슬래시 명령어로만 연구실 실행 가능
- DM 일반 메시지에는 자동 응답하지 않음
- 길드에서 봇 멘션 메시지에도 자동 응답하지 않음

## Expected Behavior
- DM으로 텍스트를 보내면 Mystic 연구실이 바로 실행된다
- 길드 채널에서 봇을 멘션하고 질문하면 Mystic 연구실이 바로 실행된다
- 봇 자신의 메시지나 비어 있는 메시지에는 반응하지 않는다

## Scope
- Discord 메시지 이벤트 처리 추가
- DM/멘션 질문 추출 로직 추가
- `message_content` intent 활성화
- 최소 테스트 및 README 갱신

## Non-goals
- 모든 길드 메시지 자동 응답
- 대화 히스토리 기반 멀티턴 메모리
- 이미지/파일 첨부 해석

## Player Flow
1. 사용자가 DM 또는 길드 멘션으로 질문 전송
2. 봇이 질문 텍스트를 정리
3. Mystic 연구실 파이프라인 실행
4. 임베드와 후속 텍스트로 답변 전송

## Current Behavior
- slash command 진입만 가능

## Expected Behavior
- slash 없이 메시지 기반 진입 가능

## Acceptance Criteria
- DM 일반 텍스트 메시지에 응답한다
- 길드에서는 봇 멘션이 포함된 메시지에만 응답한다
- 멘션 prefix를 제거한 질문 텍스트를 사용한다
- 비어 있는 멘션 메시지에는 안내 메시지를 보낸다
- 기존 `/mystic_lab`은 계속 동작한다

## Verification Plan
- 단위 테스트로 DM/멘션 질문 추출 검증
- `py_compile` 확인
- Discord bot service 재시작 후 상태 확인
