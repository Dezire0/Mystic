# ALETHEIA / Mystic — Canonical Goal

상태: **ACTIVE STRATEGY / 구현 전환은 미완료**  
전략 버전: **2.1.0 — Project-scoped, Frontier multi-session, Tool-first**  
작성 기준: **2026-09-06**  
추적: **Issue #145**

이 문서는 Mystic/ALETHEIA의 유일한 활성 전략·우선순위 정본이다. 이전 v2.0.0은 `docs/archive/goal.frontier-led-v2.0.0-2026-09-06.md`에 보존했다.

> **ALETHEIA는 별도의 작은 AI 과학자를 만드는 프로젝트가 아니다. 강한 프론티어 모델이 여러 격리 세션에서 과학 연구를 수행할 수 있도록 실제 도구, 연구 상태, 증거, 계산, 검증, 인터페이스를 제공하는 과학 프로젝트다.**

---

## 1. 최종 역할 분리

```text
USER
  |
  | 최초 프로젝트/관리 세션 트리거
  v
WORLD / THE WHOLE
  |- project/session identity
  |- authority / budget / wake / recovery
  |- durable project state refs
  v
ALETHEIA PROJECT MANAGEMENT SESSION
  |- frontier reasoning
  |- hypothesis / experiment / interpretation decisions
  |- bounded work decomposition
  v
ALETHEIA TASK SESSIONS + SCIENTIFIC TOOLS
  |- literature/evidence
  |- data/compute/simulation
  |- counterexample/verification
  |- review/report
  v
RESULTS + EVIDENCE
  v
WORLD / MYSTIC DURABLE STATE
  |
  | result/event wakes management session later
  `---------------------------------------------> repeat
```

### 책임

- **WORLD**: 사용자, DurableActor, project binding, session lifecycle, 권한, credential refs, wake, capacity, 전역 증거 계보.
- **ALETHEIA**: ResearchCampaign/ScientificJob 도메인 상태, 과학 capability, 계산·시뮬레이션·검증, 연구 evidence/artifact, Workbench.
- **프론티어 세션**: 가설 생성, 실험 선택, 자료 해석, 결과 해석, 반론, 다음 연구 판단.
- **사람**: 최초 트리거, 권한/예산 경계, 필요한 승인, 최종 책임.

ALETHEIA는 WORLD를 대신하는 범용 운영체제도 아니고, WORLD 전체를 판단하는 전역 평가자도 아니다.

---

## 2. Global Director는 없다

이 아키텍처는 영구적인 `Global Director` 모델을 요구하지 않는다.

조정은 **프로젝트 단위**다. ALETHEIA 프로젝트에는 현재 하나의 관리 세션이 있을 수 있고, 다른 프로젝트에는 그 프로젝트의 관리 세션이 있을 수 있다.

관리 세션은 특별한 초월적 agent identity가 아니라 **ProjectScope에 바인딩된 일반 InteractiveSession 역할**이다.

모델/탭/프로세스가 죽어도 프로젝트는 살아 있어야 한다.

```text
Project identity / intent / evidence -> durable
Management role / current fence      -> durable
GPT/Astra/Claude/Gemini conversation  -> replaceable
PROTEUS terminal tab                  -> replaceable UI/backend resource
```

---

## 3. 사용자 최초 트리거 + 서버 재트리거 가설

ALETHEIA의 가장 중요한 새 운영 가설은 다음이다.

1. 사용자가 PROTEUS 멀티탭 터미널에서 **ALETHEIA 관리 세션을 먼저 직접 시작**한다.
2. 관리 세션이 WORLD/Mystic 서버와 통신하고 ALETHEIA project/campaign에 바인딩된다.
3. 관리 세션이 필요한 연구 작업을 제안한다.
4. 서버는 bounded task session과 ScientificJob을 생성/재개하고 결과를 durable state에 저장한다.
5. 작업 결과 또는 이벤트가 준비되면 서버가 **나중에 현재 관리 세션을 다시 trigger/resume**한다.
6. 관리 세션은 새 evidence를 읽고 가설/실험/검토의 다음 작업을 결정한다.
7. 다시 sleep한다.
8. 다음 결과/event가 발생하면 같은 구조가 반복된다.

```text
USER START
  -> MANAGEMENT SESSION
  -> SERVER
  -> WORK SESSIONS / SCIENTIFIC JOBS
  -> RESULTS
  -> SERVER WAKE
  -> MANAGEMENT SESSION
  -> NEXT WORK
  -> SLEEP
  -> ...
```

이 문서 작성 시점에 이 PROTEUS server-originated re-trigger가 반복적으로 검증되었다고 주장하지 않는다. 이것은 **THE WHOLE Project Session Fabric에서 실험해야 할 핵심 가설**이다.

### “무한 반복”의 정확한 의미

무한 busy loop가 아니다.

프로젝트 생애 동안 다음 bounded cycle을 필요한 만큼 반복할 수 있다는 뜻이다.

```text
WAKE -> READ STATE -> REASON -> REQUEST WORK -> GATHER -> CHECKPOINT -> SLEEP
```

각 cycle에는 budget, deadline, capacity, quota, cooldown, fan-out ceiling, 취소/정지 조건이 있다. 일이 없으면 모델을 계속 돌리지 않는다.

---

## 4. 하나의 강한 모델을 여러 세션으로 사용한다

기본 전략은 specialist reasoning model을 여러 개 유지하는 것이 아니다.

예를 들어 같은 frontier backend 하나로:

```text
ALETHEIA management session
ALETHEIA literature session
ALETHEIA hypothesis/counterexample session
ALETHEIA simulation-interpretation session
ALETHEIA adversarial-review session
```

을 동시에 만들 수 있다.

이들은 서로 다른 모델이 아니라 **서로 다른 project-scoped context branch**다.

전문성은 다음 조합으로 만든다.

> **Frontier intelligence + project context + task profile + allowed tools + current evidence**

### task session 규칙

작업 세션은:

- 하나의 명확한 bounded work item을 받는다;
- 필요한 project context만 읽는다;
- 허용된 capability만 사용한다;
- proposal/result/evidence를 반환한다;
- project goal, 권한, canonical evidence를 직접 소유하지 않는다.

관리 세션이 여러 결과를 모아 판단하더라도, 상태 변경/실행은 WORLD/Mystic의 revision/authority/schema 검사를 통과해야 한다.

---

## 5. Specialist model layer는 critical path에서 제거한다

ALETHEIA의 기본 구조에서 다음을 더 이상 필수로 만들지 않는다.

- 별도 Director/Theorist/Referee 모델;
- 역할별 LoRA/QLoRA;
- Raven/Forge식 작은 scientist 모델 육성;
- specialist model router;
- model-majority voting;
- specialist approval을 첫 연구의 선행조건으로 두는 것.

기존 `mystic/alethia_approval.py`, `mystic/alethia_benchmark/`, `mystic/specialist_dispatcher.py`, NVIDIA/Lightning 실험은 **legacy/optional tool-backend evidence**로 재분류한다.

필요한 retrieval gap이 실제로 측정될 때 embedding/reranker를 사용할 수 있다. 이때도 이는 `scientific specialist agent`가 아니라 **검색 도구의 내부 backend**다.

결정적 solver, parser, OCR, vector index, reranker, SymPy/Lean/Z3류 검증기, GPU compute는 local이어도 유용할 수 있다. `local tool`과 `local reasoning scientist`를 혼동하지 않는다.

열린 PR #142는 production specialist 승인이나 새 canonical direction으로 간주하지 않는다. M01에서 사용처와 보존 가치가 확인될 때까지 핵심 경로와 분리한다.

---

## 6. MCP와 세션은 1:1이 아니다

MCP/module은 capability boundary다. Session은 reasoning worker다.

```text
literature MCP  ----+
math MCP        -----+--> management session may use allowed subset
simulation MCP  -----+--> task session A may use another subset
evidence MCP    -----+--> task session B may use another subset
```

PROTEUS UI에서 MCP/모듈/업무별로 탭을 나누는 것은 좋은 projection일 수 있다. 하지만 `MCP 하나 = 영구 세션 하나`를 protocol invariant로 만들지 않는다.

세션은 project_id, task profile, allowed capability refs, current state/evidence refs, operation identity를 가진다.

---

## 7. ALETHEIA ProjectScope와 연구 상태

ALETHEIA는 THE WHOLE의 ProjectScope 위에 올라간다. Mystic 안에 별도 WORLD를 만들지 않는다.

ProjectScope는 전역 project/session/authority refs를 가진다. Mystic은 과학 도메인의 durable object를 소유한다.

주요 도메인 객체:

- `ResearchCampaign`
- hypotheses / claims
- scientific models
- experiments
- `ScientificJob`
- scientific results/failures
- evidence/artifact refs
- reports / visualizations

### single-writer rule

같은 revision을 WORLD와 Supabase/Mystic이 동시에 독립적으로 쓰지 않는다.

- WORLD: project/actor/session/authority/wake의 정본.
- Mystic: 명시적으로 위임된 scientific domain state의 writer.
- WORLD는 Mystic resource를 typed ref + revision/hash로 추적.

양쪽 연결에는 stable operation ID, outbox/event identity, idempotency, reconciliation을 사용한다.

---

## 8. 기존 CampaignRuntime을 버리지 않는다

`ResearchCampaign`과 `ScientificJob`은 새 구조의 중요한 기반이다.

유지할 것:

- revision/CAS;
- idempotency;
- checkpoint/rollback evidence;
- budget;
- ScientificJob lease/outbox/retry;
- worker가 campaign을 직접 수정하지 않는 경계;
- result hash/provenance;
- logical exactly-once attachment;
- explicit failure states.

바꿀 것:

### 동기 AI hook -> durable decision operation

현재 `HypothesisGenerator`, `ExperimentPlanner`, `ModelSelector`, `Referee`, `ReportWriter` 훅을 서로 다른 모델로 채우는 것이 목표가 아니다.

이들은 다음과 같은 **판단 요청 종류**가 된다.

```text
persist decision request
 -> wake/assign frontier session
 -> wait for proposal
 -> validate schema/project revision/controller fence
 -> apply accepted domain command
 -> record receipt/evidence
```

### phase transition != research iteration

현재 구현의 phase transition count와 실제 가설→실험→결과→다음 실험의 연구 cycle을 분리한다.

Autonomous Scientist 수락에서 “2 iteration”은 phase 두 번 이동이 아니라 실제 research cycle 두 번이다.

---

## 9. Scientific Tool Fabric

ALETHEIA의 개발 자원은 여기에 집중한다.

### Evidence / Literature

- paper/web/document acquisition;
- source/page/chunk lineage;
- conflicting evidence collection;
- dataset provenance;
- artifact reading;
- retrieval indexes where useful.

### Mathematics / Verification

- symbolic algebra;
- numerical solvers;
- counterexample search;
- unit/dimension checking;
- invariants;
- supported Lean/Z3/formal paths;
- deterministic reruns.

### Science / Modeling

- simulation engines;
- parameter fitting;
- residual analysis;
- uncertainty/sensitivity;
- model comparison;
- synthetic experiments;
- supplied-data analysis.

### Compute

- trusted CPU/GPU jobs;
- bounded resources;
- versioned environments;
- reproducible input/output contracts.

### Workbench

- campaign timeline;
- active sessions/tasks;
- hypothesis/model comparison;
- evidence source panel;
- result tables/graphs;
- actual-result-linked 3D where useful;
- budget/capacity/wait reason;
- pause/cancel/approval controls.

모델이 내놓은 텍스트와 실제 tool result는 UI와 보고서에서 구분한다.

---

## 10. 동시 실행과 gather

관리 세션은 bounded task fan-out을 제안할 수 있다.

예:

```text
management
  |- task A: 자료 찾기
  |- task B: 다른 가설 찾기
  |- task C: 계산/시뮬레이션 분석
  `- task D: 반박 검토
```

WORLD/Mystic은 각 작업에 operation/session identity와 deadline을 준다.

관리 세션 재트리거 전에 gather policy를 적용한다.

- all required results;
- minimum N results;
- deadline reached;
- decisive evidence received;
- failure/cancel condition.

늦게 온 결과는 보존하지만 stale revision의 project decision을 덮어쓰지 않는다.

같은 frontier 모델을 여러 세션에서 사용해도 context/evidence scope가 섞이지 않아야 한다.

---

## 11. Current Build

이번 전략 업데이트의 Mystic 기준점은 `main` commit `7ad4364a454cfaeabaf922621b11408bb23c830e`다.

확인된 기반:

- ResearchCampaign durable state, budgets, checkpoint, revision/CAS;
- ScientificJob durable execution intent, lease/outbox/retry/result attachment 구조;
- existing MCP/Control Center paths;
- existing engine/scene/report foundations;
- provider routing/connection legacy paths;
- specialist benchmark/approval/Lightning experimental code;
- legacy Raven/training/debate/research-table code.

아직 이 기준점에서 완료되었다고 주장하지 않는 것:

- WORLD ProjectScope integration;
- ALETHEIA project management-session binding;
- PROTEUS server-originated repeated re-trigger;
- same-frontier multi-session pool/gather;
- project-scoped context isolation proof;
- production Capability Proxy/authority bridge;
- fully autonomous multi-cycle frontier research loop;
- legacy specialist/training orchestration removal.

---

## 12. Keep / Transform / Retire

### KEEP

- `mystic/lab/campaign*.py` durable domain state;
- `mystic/lab/scientific_job*.py` durable job boundary;
- trusted scientific engines/adapters;
- verification and Reality Anchor concepts;
- evidence/failure/provenance records;
- scene/report/Workbench capabilities;
- useful parsing/retrieval/compute components.

### TRANSFORM

- fixed agent roles -> task profiles for frontier sessions;
- synchronous campaign hooks -> durable async decision operations;
- provider routing -> compatibility adapter behind WORLD session direction;
- Research Table/debate -> optional review/workbench functions, not core orchestration;
- Failure Museum -> research memory/regression evidence first, training export optional.

### RETIRE FROM CRITICAL PATH

- Raven/LoRA training as prerequisite;
- local scientist model fleet;
- specialist model router/approval as core architecture;
- mandatory model debate;
- duplicated global/session orchestration inside Mystic;
- one-MCP-one-agent assumptions.

### DELETE ONLY AFTER PROOF

caller/import/API/deployment usage inventory, replacement capability parity, state/evidence preservation, regression tests and rollback are required before physical code deletion.

---

## 13. 단순화된 ALETHEIA 실행 로드맵

THE WHOLE milestone과 혼동하지 않기 위해 `A` 번호를 사용한다.

### A01 — Inventory and Baseline — NEXT
현재 MCP/campaign/job/engine/provider/training/specialist/debate 호출 경로와 회귀 기준을 동결한다. #142 포함 legacy 사용처를 확인한다.

### A02 — Project / Scientific Capability Contract
WORLD ProjectScope와 Mystic scientific resource 사이의 ID/revision/ref/authority/evidence 계약을 정한다. MCP capability와 session identity를 분리한다.

### A03 — WORLD ↔ ALETHEIA Read/Context Bridge
관리/작업 세션이 project-scoped ResearchContext, campaign 상태, evidence/artifact를 제한적으로 읽을 수 있게 한다.

### A04 — Durable Frontier Decision Operation
기존 sync hook을 request → session proposal → validation → apply → receipt 구조로 바꾼다. stale proposal/fence/replay를 거절한다.

### A05 — Trusted ScientificJob Execution
실제 engine worker까지 연결하고 lease loss, retry, cancellation, restart, duplicate attachment를 검증한다.

### A06 — User-Seeded ALETHEIA Management Session
사용자가 한 관리 세션을 직접 시작하고 ALETHEIA ProjectScope/campaign에 바인딩한다. 한 번의 실제 frontier decision + tool execution + evidence read를 완료한다.

### A07 — Same-Frontier Multi-Session Work
같은 frontier backend의 두 개 이상 격리 task session을 동시에 실행하고 project-scoped context isolation, bounded capabilities와 gather를 검증한다.

### A08 — Server Re-Trigger Feedback Loop
ScientificJob/result/event가 서버 wake를 만들고, 서버가 사용자 최초 트리거 이후 관리 세션을 다시 resume/trigger한다. 최소 세 번 연속 자동 cycle을 증명한다.

PROTEUS 동일 세션 재개가 실패하면 failure를 숨기지 않고 replacement-session reconstruction을 비교한다.

### A09 — Evidence, Reproducibility and Workbench
입력/출력/버전/단위/seed/tolerance/source lineage, 재실행, 반례/한계, active session/task graph와 pause/cancel UI를 통합한다.

### A10 — Bounded Autonomous Research
관리 세션이 최소 두 실제 research cycle 동안 자료→가설→도구→결과→다음 실험을 이어간다. budget/quota/capacity/stop/sleep을 서버가 강제한다.

### A11 — Scientific Tool Expansion
실제 연구에서 부족함이 측정된 fit/uncertainty/formal/retrieval/GPU/data tool만 추가한다. 별도 reasoning specialist 모델은 기본 해법이 아니다.

### A12 — Legacy Simplification
A10/A11 수락 후 대체가 확인된 Raven/local-agent/specialist-routing/중복 orchestration을 기본 경로에서 제거하고 필요한 코드/데이터를 archive한다.

### A13 — Controlled Evolution — LATER
THE WHOLE의 admission/WholeBench/canary/rollback이 준비되면 tool/prompt/backend 개선을 evidence 기반으로 승격한다.

### A14 — Domain/Room Expansion — LATER
검증된 프로젝트 운영을 새 과학 분야와 Bloome/room projection에 확장한다. Room은 비정본 UI다.

---

## 14. THE WHOLE 의존성

ALETHEIA는 THE WHOLE 전체 완료를 기다리지 않지만, 공통 기능을 Mystic 안에 복제하지 않는다.

- THE WHOLE M23: 실제 frontier SessionBackend 수락 → managed session 신뢰성에 필요.
- M24: Capability Proxy/ExecutionSubstrate → privileged scientific execution에 필요.
- M28: PersistentIntent/wake → project feedback loop의 durable wake 기반.
- M29: durable handoff/message → work result 전달 기반.
- **M30: Project Session Fabric → A06/A07/A10의 정식 project multi-session 기반.**
- **M31: PROTEUS Multi-Tab Feedback Loop → A08의 핵심 실험.**
- M33/M34: evolution → A13.
- M36: application/room projection → A14.

초기 assisted A06은 existing authenticated paths로 제한적으로 검증할 수 있지만, 그것을 full WORLD-managed autonomy라고 부르지 않는다.

---

## 15. A08 핵심 가설 수락 기준

“서버가 관리 세션을 계속 다시 깨울 수 있다”는 주장은 다음이 실제로 통과해야 한다.

- 사용자가 최초 관리 세션을 직접 시작한다;
- project/session identity가 durable하게 기록된다;
- task/result가 durable state에 먼저 기록된다;
- 서버 event가 current management session에 wake/resume을 전달한다;
- 수동 재프롬프트 없이 최소 3번의 관리 cycle이 이어진다;
- 각 cycle이 새 evidence/state revision을 읽는다;
- duplicate result/wake가 중복 scientific state update를 만들지 않는다;
- stale management generation이 최신 상태를 덮지 않는다;
- server restart 후 pending wake/result가 복구된다;
- original PROTEUS tab/session loss를 명시적으로 탐지한다;
- 동일 세션 재개와 replacement-session reconstruction을 결과에서 구분한다;
- budget/cancel/quota/auth/capacity 상태에서 안전하게 sleep/stop한다.

이전에는 이 가설을 architecture 설명만으로 완료 처리하지 않는다.

---

## 16. 과학적 검증 원칙

프론티어가 아무리 강해도 다음은 유지한다.

- 모델 제안과 관측/계산 결과 분리;
- unit/dimension validation;
- input/output hashes와 runtime/engine version;
- seed/tolerance/convergence/validity limit;
- 독립 rerun/반례 where possible;
- source provenance;
- `inconclusive`를 정상 결과로 허용;
- 숨겨진 chain-of-thought를 저장하지 않고 visible rationale/evidence만 저장.

같은 frontier 모델의 여러 세션이 동의했다는 사실은 독립된 과학 증거가 아니다. 실제 도구 결과와 source/evidence가 중요하다.

---

## 17. 지금 하지 않을 것

- Global Director 만들기;
- local frontier imitation을 위해 specialist 모델부터 학습하기;
- 모든 역할에 별도 모델/LoRA 붙이기;
- 필수 model-majority debate;
- ALETHEIA 안에 별도 general agent OS 만들기;
- unlimited parallel sessions;
- PROTEUS 탭을 canonical memory로 사용하기;
- 실험하지 않은 server re-trigger를 “완료”라고 기록하기;
- UI/3D를 실제 simulation evidence처럼 취급하기.

---

## 18. 다음 작업

**다음은 A01이다.**

현재 `main`, 열린 PR, provider/session/tool 경로를 inventory하고 어떤 legacy 코드가 새 project-session 철학과 실제로 충돌하는지 사용처 단위로 확인한다. 이 단계에서 대규모 삭제는 하지 않는다.

첫 실제 성공 지점:

- **A06:** 사용자가 시작한 관리 세션이 한 번 실제 연구/tool cycle 수행.
- **A08:** 서버가 같은 관리 역할을 다시 깨워 3번 이상 feedback cycle 수행.
- **A10:** 두 번 이상의 실제 research cycle을 bounded autonomous mode에서 수행.

세 단계를 같은 “자율 연구소 완료”로 부르지 않는다.

---

## 19. Focused references

- `docs/aletheia-project-session-loop.md` — ALETHEIA에 적용한 관리 세션/멀티세션 가설
- `docs/research_campaign_runtime.md`
- `docs/scientific_job_runtime.md`
- `docs/exactly_once_result_attachment.md`
- `docs/mystic_lab_engine_adapter_layer.md`
- `docs/mystic_lab_3d_virtual_lab.md`
- `docs/archive/goal.frontier-led-v2.0.0-2026-09-06.md` — 이전 전략

최종 원칙:

> **새 가설을 만드는 지능은 프론티어 세션에서 빌린다. ALETHEIA는 그 세션들이 서로 다른 방에서 실제 과학 도구를 쓰고, 결과를 남기고, 서버가 다시 관리 세션을 깨워 다음 판단을 하게 만드는 연구 환경을 제공한다.**
