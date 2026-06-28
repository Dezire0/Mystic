## Summary
Mystic 연속 학습 서비스가 macOS 절전으로 멈추지 않도록 하고, 재부팅 또는 로그인 후 자동 복구되도록 서비스 실행 방식을 강화한다.

## Motivation
사용자가 컴퓨터를 꺼두거나 자리를 비운 동안 학습이 멈춘다. 완전한 전원 차단 상태에서 로컬 프로세스를 계속 실행할 수는 없지만, 적어도 절전 때문에 죽지 않게 하고 부팅 후 자동으로 다시 이어지게 해야 한다.

## Problem
- 현재 launchd user agent는 로그인 후 자동 시작은 가능하지만 절전 방지 보장이 없다.
- 노트북이 sleep 상태로 들어가면 로컬 continuous daemon과 원격 cycle daemon이 멈출 수 있다.
- 전원이 완전히 꺼진 상태에서 로컬 프로세스가 계속 도는 것과 절전 방지를 혼동하기 쉽다.

## Current Behavior
- `RunAtLoad` / `KeepAlive`는 이미 설정되어 있다.
- 서비스는 launchd로 재시작되지만, 프로세스 실행을 `caffeinate`로 감싸지 않아 idle sleep을 적극적으로 막지 않는다.
- 상태 출력에는 “전원 꺼짐 자체는 불가능, 절전 방지만 가능”이라는 운영 의미가 드러나지 않는다.

## Expected Behavior
- continuous training / remote cycle launchd 서비스는 기본적으로 `caffeinate`를 통해 idle/system sleep을 막는다.
- 서비스 status 출력에서 sleep prevention 설정 여부를 확인할 수 있다.
- 사용자는 재부팅 후 로그인 시 서비스가 자동 복구된다는 점과, 완전 전원 종료 상태는 로컬 실행이 불가능하다는 점을 명확히 알 수 있다.

## Scope
- `scripts/manage_continuous_training.py`
- `scripts/manage_remote_cycle_service.py`
- 관련 서비스 테스트 추가
- 운영 의미를 설명하는 문서 갱신

## Acceptance Criteria
- 설치된 continuous/remote launchd plist의 `ProgramArguments`가 기본적으로 `/usr/bin/caffeinate`를 통해 데몬을 실행한다.
- 사용자가 원하면 절전 방지 없이 실행하도록 opt-out 인자를 줄 수 있다.
- 서비스 status 출력에 sleep prevention 설정이 포함된다.
- 테스트가 launchd payload와 daemon command를 검증한다.

## Verification Plan
- `python3 -m unittest tests.test_manage_training_services tests.test_manage_discord_bot_service tests.test_training_continuous`
- `python3 scripts/manage_continuous_training.py status`
- `python3 scripts/manage_remote_cycle_service.py status`

## Reproduction Steps
1. macOS에서 Mystic continuous/remote 서비스를 launchd로 실행한다.
2. 화면을 끄거나 일정 시간 방치해 sleep이 발생한다.
3. 이후 heartbeat가 멈추거나 작업이 지연된다.

## Actual Result
절전 진입 시 로컬 서비스가 기대만큼 계속 돌지 않을 수 있다.

## Expected Result
절전은 최대한 방지되고, 재부팅/로그인 후에는 자동 복구되며, “완전 전원 종료 상태는 불가능”이라는 운영 한계가 명확히 문서화되어야 한다.

## Environment
- Project root: `/Users/JYH/Documents/Mystic`
- macOS launchd user agents

## Non-goals
- 전원이 완전히 꺼진 상태에서 로컬 프로세스를 계속 실행하게 만들지 않는다.
- root 권한이 필요한 시스템 전역 LaunchDaemon 설치는 이 이슈 범위에 포함하지 않는다.
