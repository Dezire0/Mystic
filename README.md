# ALETHEIA / Mystic

**프론티어 모델이 판단하고, 검증된 과학 도구가 실행하며, WORLD가 권한과 지속성을 소유하는 연구 시스템.**

## 먼저 읽을 문서

**[단일 목표 및 실행 로드맵 — docs/goal.md](docs/goal.md)**

2026-09-06 전략 전환 이후 목표·우선순위·폐기 계획·완료 기준은 위 문서 한 곳에서 관리합니다. 이 README는 진입점이며 별도 로드맵이 아닙니다.

Astra에 대한 사용자 선호는 교체 가능한 프론티어 정책으로 표현합니다. 특정 model ID, 실제 접근권, backend 연결 또는 비교 성능을 이미 검증했다는 뜻은 아닙니다.

## 역할

- **프론티어 세션:** 가설, 실험 선택, 결과 해석, 다음 연구 판단.
- **WORLD / MNEME:** 사용자·actor·세션·권한·전역 상태와 증거 계보.
- **ALETHEIA:** 과학 도구, 결정적 도메인 검증, ScientificJob, 재현 가능한 결과와 연구 인터페이스.

Local 학습 모델과 고정된 다중 agent 팀을 새 연구 경로의 필수 조건으로 삼지 않습니다. 기존 계산 엔진, campaign/job 지속성, 검증기, evidence 및 UI는 유지·확장합니다.

## 현재 코드와 목표의 구분

이 전략 변경은 **문서 변경**입니다. 기존 실행 코드·설정·데이터·배포는 그대로입니다. 새 WORLD–ALETHEIA adapter, 프론티어 판단 bridge, 권한 있는 실행 연결 및 완전한 자율 연구 루프가 구현 완료되었다고 주장하지 않습니다.

기존 코드에는 ResearchCampaign, ScientificJob, MCP/Control Center, 과학 엔진/장면 도구, provider 경로, specialist benchmark/approval 및 legacy Raven training 경로가 공존합니다. 현재 운영 상태는 별도 live 검증이 필요합니다.

## 구현 및 운영 참조

| 문서 | 내용 |
| --- | --- |
| [ResearchCampaign](docs/research_campaign_runtime.md) | 도메인 상태, 체크포인트, 예산, 판단 훅 |
| [ScientificJob](docs/scientific_job_runtime.md) | durable job, worker lease, outbox, 결과 부착 |
| [Campaign state machine](docs/campaign_state_machine.md) | 현재 상태 전환 계약 |
| [Logical result attachment](docs/exactly_once_result_attachment.md) | 물리 실행과 논리적 결과 적용의 구분 |
| [Engine adapter layer](docs/mystic_lab_engine_adapter_layer.md) | 기존 과학 엔진 경계와 제한 |
| [3D virtual lab](docs/mystic_lab_3d_virtual_lab.md) | 장면 및 시각화 참조 |
| [Specialist approval](docs/alethia_specialist_approval_routing_gate_v0.md) | 도구 후보의 평가·승인 경계 |
| [Development entrypoint](CODEX_PROMPT.md) | 코드 변경 시 먼저 확인할 원칙 |

구체적인 이전 설치·운영 명령과 학습 관련 기록은 [기존 README 보관본](docs/archive/README.pre-frontier-2026-09-06.md)에 보존했습니다. 보관본은 역사 자료입니다. 거기에 적힌 모델·상태·우선순위를 현재 기본값이나 새 승인으로 취급하지 마십시오.

[보관 문서와 원래 경로 안내](docs/archive/README.md) · [전략 변경 Issue #143](https://github.com/Dezire0/Mystic/issues/143)
