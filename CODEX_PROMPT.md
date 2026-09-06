# Mystic / ALETHEIA 개발 진입점

**먼저 [docs/goal.md](docs/goal.md)를 읽는다. 이것이 유일한 활성 전략과 milestone queue다.**

## 변경 원칙

- 프론티어 세션이 연구 판단을 담당하고, Mystic은 과학 도구·검증·도메인 상태·인터페이스를 제공한다.
- 고정된 local agent 팀, 역할별 모델/LoRA, Raven 학습을 기본 연구 경로의 필수 조건으로 만들지 않는다. 역할은 필요한 task profile로 표현할 수 있다.
- WORLD의 actor/session/authority/credential/전역 상태 기능을 Mystic 내부에 중복 구현하지 않는다.
- 기존 ResearchCampaign, ScientificJob, 과학 엔진, 결정적 검증기, 원본 증거와 복구 기능을 재사용한다.
- 모델 응답은 proposal이다. 실제 실행과 상태 적용은 서버의 schema·권한·예산·revision/fence 검사를 통과해야 한다.
- 현재 구현, 목표, 테스트용 fake, 실제 실행, 배포 검증을 구분한다. 실행하지 않은 테스트나 모델 호출을 완료했다고 기록하지 않는다.
- runtime/data/config를 문서 정리와 함께 무단 삭제·이전·변경하지 않는다. goal의 대상별 삭제·rollback 게이트를 따른다.
- API 이름, model/backend identity, 도구 가용성은 코드와 실제 검증으로 확인한다. 추측으로 새로운 provider 경로를 만들지 않는다.
- 작업 시작 시 최신 `main`, 열린 PR, 관련 구현 문서를 확인한다. 특히 PR #142를 승인된 production specialist 상태로 오해하지 않는다.
- 행동·계약·상태가 바뀌는 작업에는 같은 PR에서 goal/관련 구현 문서와 검증 결과를 갱신한다. 새 전략 파일을 별도로 만들지 않는다.

기존 v0.1 지침은 [보관본](docs/archive/CODEX_PROMPT.pre-frontier-2026-09-06.md)이다. 그 문서의 고정 모델 분리 의무나 학습 우선순위는 새 경로에 적용하지 않는다.
