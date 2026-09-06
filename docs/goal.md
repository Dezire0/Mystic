# ALETHEIA / Mystic — Canonical Goal

상태: **ACTIVE STRATEGY / 구현 전환은 미완료**  
전략 버전: **2.0.0 — Frontier-led, Tool-first, WORLD-owned**  
작성 기준: **2026-09-06**  
전략 변경 추적: [Issue #143](https://github.com/Dezire0/Mystic/issues/143)

> **우리는 작은 모델들로 거대한 과학자를 다시 만드는 대신, 가장 적합한 프론티어 모델이 실제 연구를 수행할 수 있는 과학 도구·증거·인터페이스를 만든다.**
>
> **프론티어는 연구를 판단한다. WORLD는 권한과 지속성을 통제한다. ALETHEIA는 계산·실험·검증을 수행하고 증거를 제공한다.**

이 문서는 Mystic 저장소의 **유일한 활성 전략·우선순위·로드맵 정본**이다. 새로운 목표나 변경된 순서를 다른 문서에 별도 로드맵으로 만들지 않는다. 상세 API/운영 문서는 유지하되 이 문서의 목표와 연결한다.

이 변경은 문서와 개발 지침의 전환이다. 실행 코드 삭제, 모델 설정 변경, 데이터 이전, 서비스 배포, 유료 호출, specialist 승인, 기존 PR 병합을 실행했다는 뜻이 아니다.

## 1. 목표와 성공의 정의

ALETHEIA는 THE WHOLE 위에서 작동하는 **과학 연구 애플리케이션 및 도구 계층**이다. `Mystic`은 현재 코드 저장소 이름이며, 이름 변경이나 저장소 분리는 선행조건이 아니다.

사용자는 연구 문제를 제시한다. 승인된 프론티어 세션은 자료를 검토하고, 가설과 모델을 만들고, 실험을 선택하고, 도구의 실제 결과를 해석하며 다음 행동을 결정한다. 시스템은 이를 재개 가능한 연구 기록으로 남긴다.

성공은 에이전트 수, 등록 모델 수, 도구 수, 문서 분량이 아니다. **하나의 연구가 실제 도구 실행과 추적 가능한 증거를 통해 진행되고, 중단 후 복구되며, 틀렸거나 불충분한 결과도 정직하게 보고되는 것**이다.

장기적으로 새로운 수학·과학 연구를 지원한다. 다만 재현 가능한 계산 성공과 새로운 과학적 발견은 구분한다. 새로움과 타당성은 각각 검토해야 하며, 모델의 자신감은 어느 쪽도 보장하지 않는다.

## 2. 근거 기준과 현재 상태

### 2.1 이번 계획에서 확인한 기준점

| 대상 | 기준점 | 의미 |
| --- | --- | --- |
| THE WHOLE | `2fcb1c2346b2632788343ccd8f6e0e8a17130616` | 목표·세션 런타임·아키텍처·경계 문서 기준 |
| Mystic | `3e1e10ced6e5c94cb5562bdd0ab45b63f4ca57f2` | 이번 문서 변경 전 `main`의 코드·문서 기준 |
| Specialist suite | [PR #142](https://github.com/Dezire0/Mystic/pull/142), head `9023e1737dbc1c19157444121a76e2c02eac6782` | 열린 작업. `main` 완료나 실 GPU 반복 검증으로 계산하지 않음 |

자료 우선순위는 두 가지로 나눈다.

- **현재 무엇이 존재하는가:** 해당 버전의 코드·설정·테스트·실행 증거가 우선한다. 과거의 공개 MCP 정상 기록이 지금의 정상 운영을 보장하지 않는다.
- **앞으로 무엇을 만드는가:** 이 문서가 우선한다. WORLD가 소유하는 공통 계약은 THE WHOLE의 정본을 따른다.

이번 검토는 저장소 감사다. 운영 서버의 현재 건강 상태, 실제 모델 접근권, 전체 테스트 통과를 새로 측정한 보고서가 아니다. 임의의 완성도 백분율은 사용하지 않는다.

### 2.2 재사용 가능한 기반과 실제 공백

| 항목 | 확인된 기반 | 남은 일 / 주장하지 않는 것 |
| --- | --- | --- |
| ResearchCampaign | 상태 전환, 예산, revision/CAS, 체크포인트, 도메인 기록, 외부 판단 훅 | 프론티어의 비동기 판단을 안전하게 적용하는 완성된 루프는 아님 |
| ScientificJob | durable job, lease, outbox, 재시도, 결과 검증, 논리적 중복 부착 방지 | 별도 trusted worker와 운영 환경의 연결·복구를 다시 검증해야 함 |
| MCP / Control Center | 연구·작업·장면·보고서의 기존 인터페이스 | 현재 live 상태 및 새 프론티어 경로 사용성은 별도 검증 |
| 계산·장면 계층 | 기존 과학 엔진, 장면/결과 연결, 시각화 기반 | 광범위한 엔진 목록 전체가 구현되었다고 보지 않음 |
| Specialist | benchmark/approval 코드와 Lightning 실행 기반 | 초기 후보는 EXPERIMENTAL. toy 성능이나 dispatcher 성공은 품질 승인 아님 |
| WORLD 세션 기반 | DurableActor/InteractiveSession, MNEME 지속성, fencing, reference 기본값, 선택적 `codex.cli` 코드 | 배포된 Codex 검증, 일반 Capability Proxy/ExecutionSubstrate, 전체 자율 루프 완료는 아님 |
| WORLD–ALETHEIA 연결 | 경계가 정의되어 있음 | 검토 기준의 WORLD에서 ALETHEIA는 placeholder. 실연동을 새로 입증해야 함 |

### 2.3 반드시 바로잡을 불일치

1. 기존 `CODEX_PROMPT.md`는 오픈모델별 고정 agent/prompt/학습 분리를 강제했다. 새 과학 도구 경로에서는 그 의무를 폐기한다.
2. `configs/models.json`의 legacy 경로는 Ollama/Qwen 및 Raven adapter를 가리킨다. 이것을 전체 Mystic의 유일한 실행 경로라고 단정하지 않되, 새 기본 연구 경로의 필수 의존성에서 제거한다.
3. `CampaignRuntime`의 판단 훅은 동기 callable이며 `run_hook()`은 결과를 반환한다. 프론티어 세션 요청·대기·검증·적용·복구 계약으로 전환해야 한다.
4. 현재 `transition()`은 단계 이동마다 `runtime.iteration`과 `iterations_used`를 증가시킨다. 새 `research_iteration`은 **가설/실험/평가의 한 연구 주기**를 뜻하도록 분리하고, 기존 카운터의 의미를 조용히 바꾸지 않는다.
5. 이전 roadmap과 README에는 서로 다른 시대의 상태·우선순위가 섞여 있다. 문서 보관본은 역사 자료이며 새로운 실행 지시가 아니다.
6. THE WHOLE의 오래된 경계 문서 일부와 최신 세션 문서는 backend 상태 설명이 다르다. 최신 세션 코드·집중 문서와 목표의 Current Build를 우선하고, 이를 Mystic에서 임의로 완료 처리하지 않는다.

## 3. 책임 분리

| 책임 | 소유자 | 금지할 중복 |
| --- | --- | --- |
| 사용자·DurableActor·PersistentIntent·세션 수명 | WORLD | Mystic 내부에 또 다른 전역 agent/session OS 만들기 |
| 권한·승인·credential lease·전역 예산·모듈 admission | WORLD | 모델 출력이나 session ID를 권한으로 인정하기 |
| 가설·실험 선택·결과 해석·후속 연구 판단 | 승인된 프론티어 세션 | local 모델 학습을 먼저 완료해야 연구할 수 있는 구조 |
| Campaign/Model/Experiment의 도메인 불변조건 | ALETHEIA의 결정적 서비스 | 모델이 DB나 내부 worker RPC를 직접 수정하기 |
| 계산·시뮬레이션·피팅·검증·결과 생성 | 승인된 과학 도구/worker | 자연어 응답을 실제 실행 결과로 위장하기 |
| 전역 상태·증거 계보 및 정본 참조 | WORLD/MNEME | provider 대화나 UI 저장소를 정본으로 삼기 |
| 연구 UI·3D·room 화면 | Control Center 및 projection | 화면 상태가 실행 권한이나 과학적 진실을 소유하기 |
| 연구 분야별 결론 검토 | 과학 도구 + 프론티어 검토 + 필요시 사람 | ALETHEIA를 WORLD 전체의 범용 평가자로 바꾸기 |

ALETHEIA는 일반 운영·금융·브라우저 자동화 부서가 아니다. OIKOS 등 다른 도메인의 역할을 흡수하지 않는다. 공통 실행과 세션 연결은 WORLD에 기여하고, 과학에 고유한 도구만 Mystic에서 구현한다.

### 상태 저장의 이중 주인 방지

WORLD/MNEME가 전역 정본과 소유권을 가진다는 원칙과, 현재 Mystic의 local/Supabase 데이터 보존을 함께 지킨다.

- 각 자원의 `owner`, `resource_id`, `revision`, `schema_version`, `content_hash`, resolver를 명시한다. 한 자원의 revision을 쓰는 주인은 하나다.
- 전환기에는 Mystic 저장소를 **명시적으로 위임된 과학 도메인 저장소**로 유지할 수 있다. WORLD/MNEME에는 해당 자원의 정본 참조·소유권·증거 manifest를 남긴다.
- WORLD의 actor/authority 상태를 Supabase에 별도 정본으로 복제하거나, 같은 campaign을 MNEME와 Supabase에서 동시에 갱신하지 않는다.
- 대형 PDF·배열·그림·로그는 해시가 있는 artifact reference로 전달한다. 모든 원본을 모든 저장소에 복사하지 않는다.
- 양쪽을 묶는 가짜 분산 트랜잭션 대신 outbox, 안정적인 이벤트 ID, 중복 제거, 명시적 reconciliation을 사용한다.
- 저장소를 이전할 때만 snapshot/export → import/hash 검증 → writer fencing → resolver 전환 → 복구 검증을 수행한다. 무중단 양방향 쓰기는 기본 해법이 아니다.
- WORLD와 Mystic의 job은 상위 operation과 하위 scientific job으로 연결한다. 둘이 같은 물리 작업을 독립적으로 재시도하지 않는다.

## 4. 목표 실행 구조

아래는 **TARGET**이다. 모든 화살표가 현재 배포되었다는 뜻이 아니다.

```text
사용자 문제 / 승인된 WORLD 이벤트
                  |
      WORLD Actor + Intent + Session Runtime
                  |
      프론티어 세션: Astra 우선 정책 / 교체 가능
                  |
      ResearchProposal / CapabilityRequest
                  |
       WORLD 권한·정책·예산 검증
                  |
       ALETHEIA Capability Adapter
                  |
   Campaign 검증 + ScientificJob + Trusted Worker
                  |
     계산 / 검색 / 시뮬레이션 / 검증 도구
                  |
        실제 결과 + Evidence/Artifact refs
                  |
      프론티어 해석 / 다음 실험 / 결론
                  |
     체크포인트 + 보고서 + Workbench projection
```

### 두 운영 모드와 전환

**Frontier-assisted:** 사용자가 명시적으로 연결한 프론티어에서 기존 인증된 도구 경로를 사용한다. 이를 첫 유용성 검증으로 삼는다. 수동 실행이 필요한 구간은 그대로 표시하며 서버 자율 실행이라고 부르지 않는다.

**WORLD-managed:** 검증된 SessionBackend, 권한 있는 Capability Proxy, scoped 실행 경계와 복구 조건이 갖춰진 뒤 WORLD가 세션과 연구 작업을 관리한다. proxy가 없는데 unrestricted CLI나 프롬프트 규칙으로 권한 검증을 대신하지 않는다.

두 모드는 같은 과학 도메인 서비스·검증기·증거 형식을 사용한다. 임시 보조 경로가 별도의 영구 오케스트레이터로 성장하지 않도록 철거 조건을 둔다.

## 5. 프론티어 모델 정책

사용자 선호는 **Astra 6 계열을 우선 판단 세션으로 검토**하는 것이다. 이 선호를 정확한 실행 model ID, 요금제 권한, 현재 CLI 연결 가능성 또는 비교 성능을 검증했다는 주장으로 바꾸지 않는다.

- 실제 실행에는 관찰·승인한 `backend_id`, provider/model identity, 버전 또는 관찰 시각을 기록한다. Codex CLI라는 이름만으로 Astra를 사용했다고 기록하지 않는다.
- 모델명은 교체 가능한 정책 설정이다. 과학 도구 API에 특정 모델명을 넣지 않는다.
- 기본 단위는 **하나의 활성 판단 세션**이다. 독립 검토나 특정 capability 공백이 입증될 때만 추가 세션을 사용한다.
- 분야별 역할은 prompt/task profile로 표현할 수 있다. 역할 수만큼 프로세스·모델·LoRA를 만들 의무는 없다.
- 모델의 가설과 행동 제안은 자유롭게 생성할 수 있다. 사전 열거한 답만 고르게 하는 구조로 과학적 판단을 축소하지 않는다. 단, 실제 도구 사용과 상태 변경은 검증된 계약을 따라야 한다.
- 판단 모델이 없거나 quota가 소진되면 대기·명시적 대체·사용자 확인을 선택한다. local 모델로 조용히 바꾸고 같은 품질이라고 보고하지 않는다.
- 프론티어의 판단도 틀릴 수 있다. 수학 검사, 단위 검사, 독립 재실행, 데이터 검증은 유지한다.

### local의 정확한 의미

`local execution`과 `local reasoning model`은 다르다. CPU 계산, SymPy 같은 결정적 도구, 오프라인 데이터 처리, 승인된 embedding/reranker는 유용한 도구 후보다. 이들을 프론티어 판단보다 작은 모델이라는 이유만으로 삭제하지 않는다. 반대로 specialist라는 이름만으로 채택하지도 않는다.

## 6. 최소 계약: 기존 기반을 감싸고 확장한다

새 범용 agent framework, 별도 session scheduler, 독자적인 공통 bus를 만들지 않는다. WORLD의 envelope, StateRef, EvidenceRef, CapabilityRequest/Result 의미를 재사용하고, 미구현 부분은 버전이 명시된 작은 호환 adapter로 격리한다.

새 과학 계층의 핵심 계약은 다음으로 제한한다. 아래 이름은 **설계 대상**이며 현재 공개 API 목록이 아니다.

| 계약 | 필요한 내용 |
| --- | --- |
| `ResearchContext` | 문제·목표·현재 phase·실제 연구 주기·가설·불확실성·예산·가능한 도구·증거 요약 및 원문 참조 |
| `ResearchDecisionRequest` | campaign/revision, controller fence, context hash, 요청 종류, 만료 시각, operation/idempotency identity |
| `ResearchProposal` | 새 가설/모델/실험/해석, 근거 refs, 가정·한계, 요청 capability, 예상 비용, 사용자에게 보일 짧은 판단 근거 |
| `ScientificResultRef` | 기존 job/result와의 참조, input/output hash, engine/runtime version, seed/tolerance/units, 상태, artifact refs |
| `ScientificReview` | 검토 대상 claim, 실제 수행한 검사, 검토자 provenance, 반례/한계, 판정, unresolved items |

기존 domain 객체를 재사용한다. 같은 의미의 Model/Experiment/Evidence를 새 이름으로 복제하지 않는다.

### 판단 요청에서 상태 적용까지

```text
decision request 저장
    -> 세션에 context 전달
    -> 응답 대기 / 재개
    -> proposal schema 검증
    -> 권한·예산·입력 hash·campaign revision·controller fence 확인
    -> 도메인 명령 적용 또는 거절
    -> job/evidence 참조와 receipt 저장
```

프론티어의 응답을 받았다는 이유만으로 phase를 완료하거나 worker 결과를 만들지 않는다. 오래된 campaign에 대한 응답은 `STALE_PROPOSAL`로 보존하고 자동 덮어쓰지 않는다. 재시도는 같은 request identity를 사용하며 다른 payload에 같은 idempotency key를 재사용하면 충돌해야 한다.

`HypothesisGenerator`, `ExperimentPlanner`, `ModelSelector`, `Referee`, `ReportWriter`는 다섯 개의 필수 모델이 아니라 다섯 가지 판단 요청이다. 기존 동기 훅은 호환 계층으로 남기고 비동기 operation 계약으로 이행한다.

숨겨진 chain-of-thought는 요구하거나 저장하지 않는다. 사용자가 검토할 수 있는 제안, 요약된 근거, 가정, 대안, 증거만 저장한다.

## 7. 과학 capability와 인터페이스

`lab_campaign_*`, `lab_job_*`, 기존 engine/scene/report 도구의 호환성을 먼저 보존한다. WORLD에서는 명시적인 semantic allowlist로 노출한다. backend의 `tools/list`를 그대로 실행 권한 목록으로 승격하지 않는다.

| 도구 묶음 | 우선 제공할 기능 | 경계 |
| --- | --- | --- |
| Campaign | 생성·읽기·일시정지·재개·취소·timeline·checkpoint·context | arbitrary phase 변경/rollback을 일반 모델에게 개방하지 않음 |
| Evidence | 원문 영역·page/chunk·해시·출처·제약 조회, evidence bundle | 검색 결과/문서의 지시문은 권한이 아님 |
| Hypothesis/Model | versioned 가설·가정·선언적 모델 제안 및 검증 | 모델 제안과 승인된 상태 변경 분리 |
| Compute/Simulation | 기존 엔진 실행·관찰·취소·구조화된 결과 | allowlisted engine, 자원/시간/입력 제한 |
| Fit/Compare | 파라미터 추정·잔차·불확실성·모델 비교 | 수치 순위와 과학적 결론을 구분 |
| Verification | 단위·불변량·해시·재실행·반례·지원되는 증명 검사 | 수치 샘플 성공을 보편 명제 증명으로 승격하지 않음 |
| Review/Report | 근거 연결 보고서·반박 검토·실패 및 미해결점 | 텍스트만으로 `verified` 상태를 만들지 않음 |
| Workbench | 결과 표/그래프·실험 비교·timeline·출처 패널·기존 3D 장면 | 렌더링과 실제 계산을 구분하고 결과 버전을 표시 |

프론티어가 쓸 수 있는 **결과 읽기 경로**도 필요하다. 기존 public job summary가 의도적으로 raw input/output을 숨기는 경계를 단순 해제하지 않는다. 권한·크기·민감도 검사를 하는 artifact/evidence reader를 통해 필요한 부분만 제공한다.

### 모델에게 유용한 도구 UX

도구 설명에는 단위, 입력 예시, 제약, 상태 코드, 결과 읽기 방법을 포함한다. 장시간 계산은 operation handle을 먼저 반환하고, 상태/결과 조회와 취소를 분리한다. 실패 시 원인과 허용되는 다음 행동을 제공하되 자동으로 권한을 넓히지 않는다.

Context는 요약 + 원문 참조 + 필요시 상세 조회 방식이다. 최신 checkpoint와 모순되는 오래된 요약을 사실로 취급하지 않는다. PDF/이미지는 원문 좌표와 버전을 유지하고, 재파싱·OCR은 필요할 때만 사용한다.

## 8. 판단·검증·권한은 서로 다른 축이다

프론티어는 어떤 과학적 설명이 타당한지 판단한다. 결정적 서비스는 명령이 허용되며 계약에 맞는지 검사한다. 수학/과학 도구는 수행 가능한 검증을 실행한다. 사용자는 위임 범위와 고위험 변경을 승인한다.

보고서와 UI는 다음을 분리한다.

- 모델이 제안한 주장과 가정.
- 실제 관측 자료 및 계산/시뮬레이션 결과.
- 결과에서 도출한 해석과 그 한계.
- 독립적으로 확인한 검사와 아직 하지 못한 검사.
- 실행 성공 여부와 과학적 지지 여부.

`computed`, `simulated`, `supported`, `inconclusive`, `refuted`, `formally_verified` 같은 개념은 버전이 있는 판정 스키마로 정의한다. 기존 상태명과의 mapping 없이 enum을 교체하지 않는다. 해시는 무결성 증거이지 내용의 진실성이나 서명된 출처 증명이 아니다.

프론티어끼리 동의해도 검증 완료가 아니다. 같은 모델의 두 세션도 완전히 독립적인 증거가 아니다. 독립 검토는 동일한 고정 자료와 결과를 보되, 가능하면 원래 결론의 영향을 줄이고 실제 반례/재계산을 요구한다.

## 9. Human Workbench와 3D 방향

UI는 장식이나 대화창 복제가 아니라 연구의 관측·개입 인터페이스다. 기존 Control Center를 재사용한다.

첫 사용 흐름은 문제 입력 → 진행 상태 → 제안된 실험 → 실제 결과 → 근거 및 한계 → 다음 행동이다. 사용자는 언제든 일시정지·취소하고, 승인 요청과 비용/대기 이유를 볼 수 있어야 한다.

필수 화면은 campaign timeline, hypothesis/model 비교, job 상태, evidence 원문 패널, 실행 버전, 예산, 결과 표/그래프다. 기존 3D 장면은 실제 결과와 연결해 활용한다. 모든 실험을 3D로 만들 필요는 없다.

3D trajectory/vector/parameter viewer는 같은 검증된 artifact를 사용한다. 아름다운 그림을 시뮬레이션 증거로 위장하거나 UI가 직접 결과를 쓰게 하지 않는다. 재연결 후 서버 상태로 화면을 재구성한다.

터미널·웹·향후 Bloome room은 같은 상태의 projection이다. 새 협업 제품이나 room이 없더라도 첫 연구를 완료할 수 있어야 한다.

## 10. 유지·전환·중단·삭제 후보

아래는 코드 소거 명령이 아니라 **파일/기능 단위 이행 계획**이다. 이번 문서 변경에서 실행 코드는 그대로 둔다.

| 대상 | 결정 | 구체적 조치 |
| --- | --- | --- |
| `mystic/lab/campaign*.py` | KEEP + TRANSFORM | 지속성/CAS/체크포인트 유지. 비동기 판단 계약·과학 주기 카운터·위임 상태 참조 추가 |
| `mystic/lab/scientific_job*.py` | KEEP | engine/job 경계, lease, outbox, 결과 해시, 중복 부착 방지 유지. 실제 worker 연결 검증 |
| `mystic/lab/engines/`, 기존 adapter/scene/reports | KEEP + EXTEND | 도구 API와 evidence UX 개선. 고유한 과학 기능에 투자 |
| `mystic/lab/agents.py` 및 고정 역할 매핑 | TRANSFORM | task/review profile로 전환. 역할별 모델/프로세스 필수 의무 제거 |
| `mystic/lab/runner.py`, `mystic/research_lab.py`, `mystic/debate/`, `mystic/research_table/` | AUDIT + EXTRACT | 상태·증거·보고서 기능은 보존. 중복 planning/debate orchestration을 새 기본 경로에서 분리 |
| `configs/models.json`, `mystic/llm_client.py`, `mystic/models/` | LEGACY / OPTIONAL | local generation 기본 경로 의존 제거. provider-neutral 호환 기능은 호출자 감사 후 재사용 |
| `mystic/raven_training.py`, `mystic/raven_compare.py`, `mystic/raven_dataset_builder.py`, `mystic/training/` | RETIRE FROM CRITICAL PATH | Raven/LoRA 자체 과학자 육성을 본 제품의 선행 작업에서 제외 |
| `scripts/train_raven_lora.py`, `scripts/prepare_raven_training_data.py`, `scripts/promote_raven_adapter.py`, `scripts/run_mystic_cycle.py` | FREEZE / ARCHIVE CANDIDATE | 학습·승격 자동화를 새 연구 시작 조건으로 사용하지 않음. 파일 제거는 usage/rollback 검사 후 |
| `mystic/lab/training_export.py`, Failure Museum | SPLIT | 실패 기록·반례·회귀 데이터는 유지. 학습용 export만 opt-in 분리 |
| `mystic/alethia_approval.py`, `mystic/alethia_benchmark/`, `mystic/specialist_dispatcher.py` | KEEP OPTIONAL | 좁은 도구의 품질/환경 승인에 사용. 전체 연구 일정의 필수 관문으로 만들지 않음 |
| `mystic/lab/provider_connect.py`, `provider_router.py` | COMPATIBILITY | 기존 호출자는 보존. WORLD 세션/credential 기능을 다시 만들지 말고 adapter로 축소 |
| `mystic/verification/`, 관련 결정적 검사 | KEEP + AUDIT | local이라는 이유로 제거 금지. 실제 검증 범위와 unsupported 상태를 명시 |
| 옛 README/roadmap/Codex 지침 | SUPERSEDED | 보관본으로 이동하고 활성 진입점은 이 goal로 연결 |

### 지금 중단할 제품 방향

고정된 Raven/Forge/여러 local scientist를 먼저 완성하는 계획, 모든 모델의 학습 데이터 수집 의무, 필수 다중 모델 토론, model-majority 판정, 모델 없는 상태에서도 자동으로 성공을 만들어내는 mock 경로를 중단한다.

HERMES/PROTEUS/OpenClaw 자체를 Mystic 안에서 재구현하지 않는다. 범용 브라우저·CLI hosting·컴퓨터 제어는 WORLD의 교체 가능한 backend/substrate 문제다.

### 실제 코드 삭제 게이트

삭제 전에 caller/import/API/배포 사용처 목록, 대체 capability parity, 상태·증거 export, 회귀 테스트, 보안·복구 parity, rollback 경로가 필요하다. 공유되는 verifier/parser/storage 코드를 학습 코드와 묶어 삭제하지 않는다.

순서는 **기본 경로에서 분리 → 명시적 legacy 옵션 → 비교 검증 → 사용처 이전 → 복구 점검 → 코드 제거**다. 데이터·실패 기록·원본 증거·과거 모델 provenance는 임의 삭제하지 않는다. 중단된 작업의 late result도 기록 없이 버리지 않는다.

## 11. 단일 실행 로드맵

아래 M 번호는 **ALETHEIA 전용**이다. THE WHOLE의 M19–M36과 같은 번호 체계로 혼동하지 않는다. 이 문서 작성은 계획 확정이며, 아래 구현 milestone 완료로 계산하지 않는다.

상태: `NEXT` = 다음 실행 대상, `PLANNED` = 구현/검증 필요, `OPTIONAL` = 측정된 필요가 있을 때만, `LATER` = 기반 수락 뒤.

| ID | 한 줄 목표 | 선행조건 | 완료 증거 | 상태 |
| --- | --- | --- | --- | --- |
| M01 | 현재 실행 경로·도구·문서·legacy 의존성 및 회귀 기준을 동결한다 | 본 goal | 파일/호출자 inventory, 기존 테스트·MCP 상태, 삭제 후보별 사용처 | NEXT |
| M02 | 과학 capability·상태 소유권·판단 요청/응답 최소 계약을 정한다 | M01 | schema/version/권한/오류/멱등성 계약 및 호환 테스트 | PLANNED |
| M03 | WORLD–ALETHEIA의 실제 read-only adapter와 resource resolver를 연결한다 | M02 | 인증된 discovery/read, 데이터 경계·권한 실패·unavailable 테스트 | PLANNED |
| M04 | 프론티어용 ResearchContext·도구 안내·evidence/artifact 읽기를 만든다 | M02, M03 | 제한된 크기의 context, 출처 drill-down, 데이터 유출·오래된 요약 검사 | PLANNED |
| M05 | 기존 판단 훅을 비동기 proposal·검증·적용 계약으로 바꾼다 | M02, M04 | stale 응답 거절, 동일 요청 replay, 잘못된 proposal/권한 거절 | PLANNED |
| M06 | 기존 ScientificJob을 실제 trusted scientific worker까지 완결한다 | M01, M02 | 실제 engine 결과, 취소·lease 상실·재시작·중복 부착 검증 | PLANNED |
| M07 | 프론티어 하나가 실제 도구로 끝내는 첫 assisted 연구를 만든다 | M05, M06 | 모델 응답과 실제 계산을 구분한 결과·receipt·미해결점, mock 없음 | PLANNED |
| M08 | 재현 가능한 evidence bundle·독립 검사·보고서를 완성한다 | M07 | 입력/버전/seed/tolerance/단위/출처, 재실행 결과 및 정직한 판정 | PLANNED |
| M09 | 기존 Workbench에 실험 비교·근거·그래프 및 결과 기반 3D를 연결한다 | M07, M08 | 같은 artifact를 보는 UI, 승인·취소, 재연결·empty/error 상태 검사 | PLANNED |
| M10 | 검증된 WORLD 프론티어 세션에 연구 controller를 바인딩한다 | M03, M05, M08; 검증된 공식 backend | actor/campaign 연계, controller fence, sleep/resume, 모델 identity 기록 | PLANNED |
| M11 | WORLD 권한 경계를 통과하는 과학 write/execute capability를 연결한다 | M06, M10; WORLD proxy/실행 경계 | grant scope·예산·증거 계보, 직접 DB/worker 우회 거절 | PLANNED |
| M12 | 서버에서 재개 가능한 최소 두 연구 주기의 bounded loop를 만든다 | M08, M11 | 주기/전환 카운터 구분, interrupt/recovery, 대기·종료·예산 강제 | PLANNED |
| M13 | 모델 피팅·잔차·불확실성·실험 비교 도구를 확장한다 | M07, M08 | 합성 정답/노이즈/과적합/불충분 데이터 fixture와 명시적 한계 | PLANNED |
| M14 | 반례 탐색·symbolic 검사·지원 가능한 formal verification을 연결한다 | M07, M08 | false conjecture 반례, 검증기 미설치/실패와 증명 후보의 구분 | PLANNED |
| M15 | 필요한 retrieval/parser/reranker만 비교 평가해 on-demand 채택한다 | M04; 측정된 공백 | exact revision 반복 평가, 단순 baseline 비교, 비용/품질 근거 | OPTIONAL |
| M16 | 두 번째 프론티어로 이식성과 선택적 독립 검토를 입증한다 | M10, M12 | 같은 campaign/context/권한으로 교체, 모델명 비의존성, 검토 provenance | OPTIONAL |
| M17 | 실패·반례·결정 요약을 후속 연구의 증거 기억으로 재사용한다 | M08, M12 | 원본 계보, scope별 검색, 오래된 가정·모순·중복 실험 탐지 | PLANNED |
| M18 | 필요한 새 과학 도구를 격리 제작·시험·수동 admission할 수 있게 한다 | M02, M08; WORLD 승인된 build/sandbox 경계 | 신규 도구 manifest, test/benchmark, 권한 검토, rollback; 자동 self-approval 금지 | OPTIONAL |
| M19 | 고정된 연구 수락 시나리오로 도구·자율성·복구를 종합 검증한다 | M12, M13, M14, M17 | 아래 수락 게이트, 실제 결과·실패·비용·한계 보고 | PLANNED |
| M20 | 대체가 검증된 local-agent/training·중복 orchestration 코드를 철거한다 | M19; 대상별 삭제 게이트 | 참조 제거, 증거/데이터 보존, 호환 또는 명시적 종료, rollback 검증 | LATER |
| M21 | WORLD의 evolution 정책으로 도구·prompt·backend 개선을 통제한다 | M19; upstream admission/canary/rollback | held-out 비교, process integrity, 제한 canary, 회귀 시 복구 | LATER |
| M22 | 검증된 연구 흐름을 새 분야와 department/room projection으로 확장한다 | M19; 실제 사용자 필요 | 재사용 가능한 도메인 pack, UI는 비정본, 추가 비용 대비 효용 | LATER |

### 실행 순서의 핵심

```text
M01 -> M02 -> M03 -> M04 -> M05 --+
             \-> M06 ------------+-> M07 -> M08 -> M09
                                      |       |
                                      |       +-> M10 -> M11 -> M12 -> M17
                                      +-> M13 / M14                  |
                                                        M19 <-------+
                                                         |
                                                     M20 / M21 / M22
```

M15·M16·M18은 조건부 가지다. NVIDIA 승인, 두 번째 모델, 새 도구 제작 체계, 모든 분야의 엔진, Bloome를 첫 연구의 선행조건으로 추가하지 않는다. M06은 M03–M05와 가능한 범위에서 병렬 개발할 수 있다.

## 12. THE WHOLE 선행조건과 우회 금지

| WORLD 선행조건 | ALETHEIA와의 관계 | 미완료 시 |
| --- | --- | --- |
| 공통 계약/registry 방향(M19–M20) | M02–M03은 현재 Gateway에 작은 정적 adapter로 시작할 수 있음 | 미래 registry가 이미 있다고 가정하지 않고 호환 mapping 명시 |
| 세션 foundation(M21–M22), 공식 backend 검증(M23) | M10 | reference/fake 통과를 프론티어 통과로 기록하지 않음 |
| 권한 있는 Capability Proxy/실행·credential 경계(M24) | M11, managed M12 | supervised 기존 인증 경로만 사용. unrestricted shell로 대체 금지 |
| Session/Execution 검증(M25), capacity/quota 선택(M26) | managed 연구의 복구·자원 조건 | 기본 1세션/제한 동시성, capacity 불명 시 대기 |
| Specialist-on-Demand(M30) | 선택적인 M15/M16 | permanent fleet를 만들지 않음 |
| Evolution(M33–M34) | M21 | 비교 증거와 사람 검토까지만. 자동 promotion 구현 주장 금지 |
| 앱/조직 projection(M35–M36) | M22 | 연구 도구 완성을 room 제품에 종속하지 않음 |

WORLD 전체 로드맵 완료까지 연구 도구 개발을 멈추지는 않는다. 다만 공통 기반이 없다는 이유로 Mystic에 동일한 전역 kernel을 또 만들지도 않는다.

PROTEUS의 설치된 native web 실행 증거와 WSFS backend admission은 다르다. 웹 UI 사용이 필요하면 WORLD의 실험적 backend 정책을 따르고, 공식 programmable 경로와 별도로 검증한다.

## 13. 첫 연구 및 최종 수락 시나리오

### 첫 assisted pilot: 작지만 실제로 작동하는 연구

안전한 합성 운동 자료 또는 기존 projectile engine을 사용한다. 프론티어가 가정과 예측을 만들고, 실제 엔진을 실행하고, 결과를 읽어 틀린 예측이나 모델의 적용 한계를 설명한다. 하나의 evidence-linked 보고서를 저장한다.

필수 조건은 **실제 모델 응답 1회 이상, 실제 도구 실행, 결과 읽기, 입력/결과 계보, false success 없음**이다. 명시적인 사용자 조작이 개입했다면 보고서에 기록한다. 이 pilot을 완전 자율 과학자라고 부르지 않는다.

### M19 수락 묶음

| 시나리오 | 보여야 하는 능력 | 유효한 결과 |
| --- | --- | --- |
| 운동 모델 비교 | 합성 관측에 대한 등속/가속도 모델 비교, 잔차, 구별되는 후속 실험 | 지지되는 모델 또는 자료 불충분 |
| 개체군 합성 자료 | 지수/로지스틱 후보 피팅, 불확실성, 추가 관측의 가치 | 한계가 명시된 선택 또는 inconclusive |
| 수학적 탐구 | 가설 제안, 반례 탐색, 수정, 가능한 검증기 실행 | 반례/비형식 후보/검증된 범위의 결과 |
| 근거 중심 자료 연구 | 제공되거나 허용된 자료의 원문 계보, 상충 근거, 계산/추론 구분 | 출처·한계가 포함된 보고서 |

각 managed 수락 campaign은 최소 두 **실제 연구 주기**를 실행한다. phase 이동 두 번으로 대체하지 않는다. 한 종류 이상의 중단/복구를 검증하며, 반복 실행은 성공·실패를 모두 보존한다.

### 공통 hard gate

- 위조된 engine/model 결과, 권한 우회, 비밀 노출, 증거 없는 상태 승격이 없어야 한다.
- 중복 배달/오래된 controller/취소 후 결과/실행 중 crash가 완료된 증거를 중복 부착하거나 최신 상태를 덮어쓰지 않아야 한다.
- 독립 재실행은 선언한 수치 tolerance와 seed 조건을 따른다. GPU 계산에 무조건 bitwise 동일성을 약속하지 않는다.
- 예산·시간·반복 한계를 서버가 강제하고, quota/인증/도구 부재는 명시적으로 대기 또는 실패한다.
- 보고서는 실행 성공과 과학적 판정을 분리하고, `inconclusive`를 정상 결과로 허용한다.

## 14. 평가와 비용

프론티어가 크다는 이유만으로 모든 작업에서 더 낫다고 가정하지 않는다. 새 구조는 **같은 모델·동일 입력·동일 도구 접근**을 가진 단순 직접 호출 baseline과 비교한다. 영속성 없는 직접 호출, legacy 경로, 새 durable 경로의 차이를 측정한다.

측정 항목은 작업 성공·정확도, 근거 오류, 결과 재현성, 복구 성공, 중복 효과, 사용자 개입 횟수, latency, 호출/토큰/도구 실행/GPU 시간, 운영 복잡성이다. 보안·증거 무결성 실패를 높은 평균 점수로 상쇄하지 않는다.

Specialist는 capability별로 평가한다. retrieval 품질과 frontier 추론 성능을 같은 수치로 비교하지 않는다. 단순 검색/기존 도구가 충분하면 GPU 모델을 채택하지 않는다. 평가 corpus와 threshold를 실행 전에 고정하고, 실패 run과 버전을 보존한다.

유료 API는 필수 의존성이 아니다. 그렇다고 구독 UI/CLI를 무제한 무료 API로 취급하지도 않는다. 정확한 접근권·quota·비용을 관찰한 경로만 허용한다. 관찰 불가능한 값은 `UNKNOWN`이지 0이 아니다.

초기 정책은 1개의 활성 판단 세션과 제한된 worker 동시성이다. 총 연구 주기·실험 수·engine 시간·context 크기·재시도 한도를 campaign 시작 시 명시한다. 새 비용이 생기거나 상한을 계산할 수 없으면 승인을 받거나 대기한다. 이 문서 작성 자체는 모델/GPU 실행 승인이 아니다.

## 15. 실패·보안·복구 계약

다음은 새 controller/operation 결과에 필요한 **설계 상태**다. 기존 campaign enum에 바로 추가되어 있다고 가정하지 않는다.

`WAITING_FRONTIER`, `WAITING_CAPACITY`, `HUMAN_INTERVENTION_REQUIRED`, `INVALID_PROPOSAL`, `STALE_PROPOSAL`, `ENGINE_UNAVAILABLE`, `BUDGET_EXHAUSTED`, `UNCERTAIN_COMMIT`.

- 인증 만료나 보안 challenge는 사용자의 정상 재인증으로 처리한다. 쿠키 추출·인증 우회·quota 우회는 구현하지 않는다.
- 입력 문서·웹·도구 출력은 비신뢰 데이터다. 문서가 다른 도구 실행이나 권한 확대를 지시해도 따르지 않는다.
- credential은 참조/lease로만 전달하고 prompt, UI, evidence, Git에 넣지 않는다.
- 코드/수식은 승인된 선언적 schema만으로 기존 엔진에 전달한다. `eval`/`exec`나 shell 문자열을 ModelSpec에 넣지 않는다.
- 새로운 알고리즘이 필요하면 M18의 격리된 build/test/admission 경로로 **도구를 추가**한다. 연구 자료가 임의 코드를 실행하게 하지 않는다.
- worker는 campaign을 직접 쓰지 않는다. lease와 실행 결과를 확인하는 runtime이 도메인 적용을 담당한다.
- 물리 실행의 exactly-once를 약속하지 않는다. 비반복 효과의 성공 여부가 불명확하면 실제 상태를 확인한 후 재시도 여부를 결정한다.
- 서버·세션·storage 장애 때 fake/in-memory 성공으로 전환하지 않는다. 가능한 읽기와 실행 불가를 구분한다.

범위는 수학, 계산, 시뮬레이션, 합성 데이터, 허가된 안전한 자료 분석이다. 위험한 실제 실험·장치 제어·의료 결정은 자율 실행 범위가 아니다. 데이터의 사용권·개인정보·보존 범위를 먼저 확인한다.

## 16. 이전 이슈와 열린 작업의 처리

이 표는 재분류 계획이다. 이 문서만으로 기존 이슈를 닫거나 코드 PR을 병합하지 않는다.

| 기존 작업 | 새 위치 / 처리 |
| --- | --- |
| #111 Autonomous Scientist epic | 장기 목적은 유지. 실행 순서는 본 M01–M22로 대체 |
| #112 runner fleet | M06에서 최소 trusted worker를 먼저 수락. 다중 host 확장은 측정된 필요 이후 |
| #114 engine expansion/ModelSpec | M02/M13/M14/M18에 capability 단위로 분해 |
| #115 autonomous loop | M05/M10–M12. 새 자체 LLM brain 대신 frontier session controller |
| #116 model construction/selection | M13의 계산 도구 + frontier의 과학적 판단 |
| #117 experiment manager | M12/M13의 결정적 예산/의존성 + frontier의 다음 실험 제안 |
| #118 referee/reproducibility | M08/M14, 필요시 M16. local referee 필수화 금지 |
| #119 production acceptance | M19. 문서의 조건 충족과 실제 운영 검증을 따로 기록 |
| #126 trusted worker | M06. 현재 미검증 부분을 완료된 기반으로 가정하지 않음 |
| #127/#128 specialist foundation | 재사용되는 부분을 코드·증거로 확인, 미구현 범위는 M15의 조건부 작업으로 이동 |
| #141 / PR #142 benchmark suite | 유지하되 M15의 optional 도구 평가로 재배치. real 반복 run과 별도 승인 없이 production 승격 금지 |
| Raven/LoRA/Kaggle 관련 기존 작업 | active 핵심 queue에서 제외. 필요한 재현 기록을 보존하고 개별 종료/보관 여부 검토 |

PR #142의 내용은 이 문서 작업에 섞어 병합하지 않는다. 해당 PR의 README/문서 변경은 새 진입점과 충돌할 수 있으므로 이후 명시적으로 rebase·재검토한다.

## 17. 실행·검증·철거 방법

한 번에 전체 재작성하지 않는다. 각 milestone은 issue, 최소 변경, 회귀 검사, 기능 검증, 문서 갱신, rollback을 한 작업 단위로 묶는다.

1. 현재 import/call graph와 live 설정을 확인하고 기준 실행을 보존한다.
2. 새 기능을 feature flag와 좁은 adapter로 추가한다.
3. 테스트용 fake와 실제 실행 증거를 분리한다.
4. 동일한 입력으로 기존/새 경로를 비교한다.
5. 실제 권한 경계와 restart/cancel/duplicate/stale 처리를 검증한다.
6. 제한된 사용처를 새 경로로 옮기고 기록한다.
7. 삭제 게이트를 통과한 중복 코드만 철거한다.

검증에는 schema/contract, campaign/job/CAS/lease, frontier unavailable/quota, 악성 문서/잘못된 도구 요청, 결과 provenance, UI 회귀, 실제 MCP/worker smoke, 재시작·rollback이 포함된다.

계획 문서 PR에서는 코드 테스트나 운영 검증을 수행하지 않았다면 그대로 적는다. 모델 호출, 설치, migration, deployment를 실제로 하지 않고 완료 상태를 붙이지 않는다.

## 18. 지금 실행할 다음 작업

**다음 구현 대상은 M01이다.** 작업 프롬프트의 기준은 다음과 같다.

> `docs/goal.md`를 먼저 읽고 Mystic `main`과 열린 PR을 다시 확인한다. 현재 MCP/engine/campaign/job/provider/legacy-training 호출 경로와 사용처를 목록화하고 기존 회귀 기준을 측정한다. 새 프론티어 경로에서 필요한 기능과 단순 legacy 의존성을 분리한다. 이 단계에서 runtime/data를 무차별 삭제하지 않는다. 결과를 이 goal의 Current Build 및 M01 상태에 반영한 뒤, M02의 최소 계약과 M06 worker 검증 작업을 준비한다.

첫 실제 가치 검증은 M07이다. 첫 managed 자율 연구 증명은 M12다. 종합 수락은 M19다. 이 셋을 모두 같은 의미의 완료라고 부르지 않는다.

## 19. 문서와 변경 기록 규칙

README와 CODEX_PROMPT는 진입점이며 자체 roadmap을 갖지 않는다. 기존 campaign/job/engine/approval 문서는 구현 참조로 유지한다. 보관된 계획은 `docs/archive/`에 있으며 실행 우선순위를 정하지 않는다.

새 아이디어는 이 파일의 관련 milestone에 후보로 연결하고, 개선할 지표·기존 대체 대상·권한 영향·검증 방법을 적는다. 모델 추가나 라이브러리 채택만으로 milestone을 완료하지 않는다.

완료 기록에는 정확한 commit/PR, 테스트 명령과 결과, real/mock 구분, 배포 여부, 남은 한계, 복구 방법을 남긴다. model/backend/도구 교체는 승인·검증·migration 영향을 함께 갱신한다.

## 20. 근거 문서

### WORLD 기준 — 접근권이 있는 내부 참조

- [Canonical goal, 고정 기준점](https://github.com/Dezire0/the-whole/blob/2fcb1c2346b2632788343ccd8f6e0e8a17130616/docs/goal.md)
- [Session Runtime Foundation](https://github.com/Dezire0/the-whole/blob/2fcb1c2346b2632788343ccd8f6e0e8a17130616/docs/session-runtime.md)
- [Architecture](https://github.com/Dezire0/the-whole/blob/2fcb1c2346b2632788343ccd8f6e0e8a17130616/docs/architecture.md)
- [Boundaries](https://github.com/Dezire0/the-whole/blob/2fcb1c2346b2632788343ccd8f6e0e8a17130616/docs/boundaries.md)
- [Development policy](https://github.com/Dezire0/the-whole/blob/2fcb1c2346b2632788343ccd8f6e0e8a17130616/docs/development-policy.md)

### Mystic 구현 기준

- [ResearchCampaign runtime](research_campaign_runtime.md), [상태 기계](campaign_state_machine.md)
- [ScientificJob runtime](scientific_job_runtime.md), [논리적 결과 부착](exactly_once_result_attachment.md)
- [Specialist approval gate](alethia_specialist_approval_routing_gate_v0.md), [Lightning dispatcher](alethia_lightning_specialist_dispatcher_v0.md)
- [CampaignRuntime 원본 코드](https://github.com/Dezire0/Mystic/blob/3e1e10ced6e5c94cb5562bdd0ab45b63f4ca57f2/mystic/lab/campaign_runtime.py)
- [기존 역할 매핑](https://github.com/Dezire0/Mystic/blob/3e1e10ced6e5c94cb5562bdd0ab45b63f4ca57f2/mystic/lab/agents.py)
- [Legacy 모델 설정](https://github.com/Dezire0/Mystic/blob/3e1e10ced6e5c94cb5562bdd0ab45b63f4ca57f2/configs/models.json)
- [과거 문서 보관 안내](archive/README.md)

**최종 원칙: 모델은 교체해도 연구와 증거는 이어져야 한다. 도구는 늘릴 수 있어도 권한은 자동으로 늘어나면 안 된다. 판단을 프론티어에 맡겨도 검증을 포기하지 않는다.**
