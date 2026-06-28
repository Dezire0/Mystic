## Summary
로컬 연속 학습의 불필요한 대기 시간을 줄이고, 현재 학습이 몇 단계까지 진행됐는지와 전체 데이터 대비 얼마나 채워졌는지를 Discord 대시보드에서 바로 읽을 수 있게 만든다.

## Motivation
사용자는 지금 Mystic이 실제로 얼마만큼 학습했고 무엇을 하고 있는지 직관적으로 보기 어렵다. 특히 로컬 연속 학습은 성공 후 기본 120초를 쉬고, 대시보드는 많은 전문가를 `60%` 근처로 보여서 실제 진행량과 체감이 어긋난다.

## Current Behavior
- 로컬 연속 학습은 성공 사이클마다 기본 120초를 대기한다.
- `run_overnight_training.py`는 현재 몇 단계 중 몇 단계인지 별도 상태 파일을 남기지 않는다.
- Discord 대시보드는 전문가별 `train_ready`/데이터셋 커버리지를 갖고 있어도 전체 합계와 현재 단계 진행을 한눈에 보여주지 않는다.
- 일부 전문가는 실제 남은 데이터셋이 많아도 최근 성공 이력 때문에 `60%`로 보여 직관성이 떨어진다.

## Expected Behavior
- 성공한 로컬 연속 학습 사이클은 기본적으로 다음 사이클을 바로 시작한다.
- 연속 학습 중 현재 반복, 총 단계 수, 완료 단계 수, 현재 단계 이름을 상태 파일에 기록한다.
- Discord 대시보드 overview/detail에서 전체 데이터셋 진행량, 전체 `train_ready rows`, 남은 데이터셋 수, 현재 로컬 단계 진행을 바로 확인할 수 있다.
- 전문가 진행률은 고정 바닥값보다 실제 데이터 커버리지와 현재 단계 진행을 더 잘 반영한다.

## Scope
- `scripts/run_overnight_training.py` 진행 상태 파일 작성
- `mystic/training/continuous.py` 진행 상태 파일 경로/로드 헬퍼 추가
- `mystic/discord_dashboard.py` 전체 진행량 및 현재 단계 노출 개선
- `scripts/run_continuous_training_daemon.py`
- `scripts/manage_continuous_training.py`
- 관련 테스트 갱신

## Acceptance Criteria
- Discord overview에서 전체 데이터셋 진행량과 현재 로컬 단계가 표시된다.
- Discord detail에서 남은 데이터셋 수와 rows 기준 진행 정보가 표시된다.
- 활성 로컬 전문가의 상태 상세에 현재 단계 정보가 표시된다.
- 로컬 연속 학습 기본 성공 대기 시간이 0초가 된다.
- 대시보드 진행률이 더 이상 일괄적으로 `60%`에 고정되지 않는다.

## Verification Plan
- `python3 -m unittest tests.test_discord_dashboard tests.test_run_overnight_training`
- 현재 `mystic_data` 기준으로 snapshot을 생성해 overview/detail 수치를 확인
- 연속 학습 데몬 인자 기본값이 성공 후 즉시 다음 사이클로 이어지는지 확인

## Reproduction Steps
1. Discord 학습 overview 또는 detail을 연다.
2. 여러 전문가가 같은 퍼센트로 보이지만 실제로는 어떤 데이터셋을 얼마나 채웠는지 즉시 파악하기 어렵다.
3. 로컬 연속 학습 로그를 보면 성공 이후 다음 사이클 전 기본 대기가 있다.

## Actual Result
학습이 돌아가도 "지금 무엇을 하는지", "얼마나 남았는지", "왜 느린지"를 읽기 어렵다.

## Expected Result
사용자는 overview/detail만 보고도 현재 단계, 전체 데이터셋 대비 진행량, 남은 양, 다음 사이클 시작 지연 여부를 즉시 판단할 수 있어야 한다.

## Environment
- Project root: `/Users/JYH/Documents/Mystic`
- Discord dashboard + local continuous training daemon

## Non-goals
- 원격 Kaggle Raven 사이클의 학습 알고리즘 자체를 변경하지 않는다.
- 병렬 GPU 학습 스케줄러를 새로 도입하지 않는다.
