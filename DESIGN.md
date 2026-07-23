# Design

## Source of truth
- Status: Active
- Last refreshed: 2026-07-01
- Primary product surfaces:
  - `/lab/start`
  - `/lab/sessions/<id>`
  - `/research-table/start`
  - `/research-table/sessions/<id>`
  - `/mcp`
- Evidence reviewed:
  - [README.md](/Users/JYH/Documents/Mystic/README.md)
  - [mystic/app/pages.py](/Users/JYH/Documents/Mystic/mystic/app/pages.py)
  - [mystic/app/components.py](/Users/JYH/Documents/Mystic/mystic/app/components.py)
  - [mystic/app/api.py](/Users/JYH/Documents/Mystic/mystic/app/api.py)
  - [mystic/lab/runner.py](/Users/JYH/Documents/Mystic/mystic/lab/runner.py)
  - [mystic/lab/storage.py](/Users/JYH/Documents/Mystic/mystic/lab/storage.py)
  - [mystic/mcp/tools.py](/Users/JYH/Documents/Mystic/mystic/mcp/tools.py)

## Brand
- Personality:
  - Severe, lucid, technical, audit-friendly.
  - Feels like an operating console for research teams, not a chat toy.
- Trust signals:
  - Provenance everywhere.
  - Deterministic tool evidence visually separated from model speculation.
  - Compact system health, timestamps, model/provider labels, and status badges.
- Avoid:
  - Fantasy lab art, beakers, cartoon robots, neon gamer UI, fake “AI magic”.
  - Overly spacious marketing layouts.
  - Any styling that makes unverified claims look complete.

## Product goals
- Goals:
  - Turn Mystic into a serious AI research operating system.
  - Make the full research loop legible: intake, hypothesis, experiment, execution, review, failure, update, report.
  - Show exact provenance across models, tools, sessions, and failures.
  - Make Model Arena a first-class room inside the broader lab OS.
  - Support fast operator control from one place: launch, inspect, verify, rerun, export.
- Non-goals:
  - Game progression, avatars, scoreboards, decorative room scenes.
  - Separate consumer-facing landing site.
  - Hiding research uncertainty to look polished.
- Success signals:
  - Operator can start a session and know the current phase, next action, and system risks in under 10 seconds.
  - Claims, experiments, failures, and imported Model Arena outputs can be traced without reading raw JSON.
  - Proof-critical mode looks and behaves stricter than cheap mode.

## Personas and jobs
- Primary personas:
  - Solo AI researcher running local + CLI + MCP workflows.
  - Research engineer validating model outputs with tool evidence.
  - Adapter/training operator reviewing failure reuse and Raven export opportunities.
- User jobs:
  - Start structured lab sessions.
  - Route roles across local models and CLI providers.
  - Inspect claims and experiments with evidence and failure links.
  - Run referee review before accepting results.
  - Import discoveries from Model Arena into the lab session.
  - Export failures and reports into training and paper workflows.
- Key contexts of use:
  - Desktop-first, dark room, multiple terminal/browser windows open.
  - Long-running sessions with intermittent provider auth issues.
  - Dense mathematical/software reasoning where logs and IDs matter.

## Information architecture
- Primary navigation:
  - `Control Panel`
  - `Create Lab Session`
  - `Active Lab Session`
  - `Model Arena`
  - `Memory Graph`
  - `Failure Museum`
  - `Dataset Room`
  - `Provider / MCP Settings`
- Core routes/screens:
  - `/` -> Control Panel
  - `/lab/start` -> Create Lab Session
  - `/lab/sessions/<id>` -> Lab Session Detail
  - `/research-table/start` -> Model Arena Start
  - `/research-table/sessions/<id>` -> Model Arena Session
  - `/sessions/detail` -> Session index / archive
  - `/teacher-labels` -> Dataset and labels operations
  - `/providers/auth/<id>` -> Provider auth / settings
- Content hierarchy:
  - System state first.
  - Current session and current phase second.
  - Claims / experiments / failures as the main research objects.
  - Notebook and report as derived artifacts.

## Design principles
- Principle 1:
  - Provenance before persuasion. Every meaningful object shows source role, provider/model, evidence state, and related records.
- Principle 2:
  - Research objects over chat bubbles. Claims, experiments, failures, and reports matter more than generic conversation UI.
- Principle 3:
  - Strict mode should visually tighten the system. Proof-critical sessions use higher contrast warnings, stricter validation badges, and more visible failure gates.
- Tradeoffs:
  - Dense layout beats airy simplicity.
  - Dark mode first beats light-only aesthetics.
  - Persistent side panels beat full-width narrative feeds.

## Visual language
- Color:
  - Base surfaces: graphite, slate, charcoal.
  - Text: cool off-white with muted blue-gray secondary text.
  - Verified / proved / supports: green.
  - Heuristic / needs detail / pending: amber.
  - Failed / refuted / contradiction: red.
  - Unknown / blocked / offline: gray.
  - Model Arena / multi-model debate / controller: indigo-violet.
- Typography:
  - UI: `Geist Sans`, `IBM Plex Sans`, or `SF Pro Text`.
  - Logs / IDs / formulas / paths: `Berkeley Mono`, `JetBrains Mono`, or `SF Mono`.
  - No decorative serif headlines.
- Spacing/layout rhythm:
  - Tight 4/8/12/16/24 scale.
  - Panel padding 16-20px desktop, 12-16px mobile.
  - Dense vertical stacks with section headers and inline badges.
- Shape/radius/elevation:
  - 10-14px panel radius.
  - Thin 1px borders.
  - Minimal shadow; prefer tonal separation over glow.
- Motion:
  - Subtle phase-progress highlight.
  - Expand/collapse drawers with 140-180ms ease.
  - No celebratory animation for success.
- Imagery/iconography:
  - Abstract systems glyphs only: graph, flask outline, scales, note, paper, chip, shield, terminal.
  - No “lab illustration” motif.

## Components
- Existing components to reuse:
  - Page hero shell and panel primitives from [mystic/app/components.py](/Users/JYH/Documents/Mystic/mystic/app/components.py)
  - `ParticipantSelector`
  - `ProviderAuthCard`
  - `ResearchPhaseSection`
  - `DiscoveryCard`
  - `VerificationRequestCard`
  - `ToolEvidenceCard`
  - `FinalSynthesisPanel`
- New/changed components:
  - `ControlStatusGrid`
  - `SessionModeBadge`
  - `PhaseRail`
  - `RoomShortcutRail`
  - `ClaimBoardCard`
  - `ExperimentRunCard`
  - `RefereeChecklistPanel`
  - `FailureExportCard`
  - `MemoryGraphMiniMap`
  - `NotebookTimeline`
  - `ReportPreviewPanel`
  - `ProviderSettingsTable`
  - `MCPHealthCard`
- Variants and states:
  - Claim cards: `PROVED`, `TESTED`, `HEURISTIC`, `FAILED`, `UNKNOWN`, `NEEDS_MORE_DETAIL`, `REFUTED`
  - Experiment cards: `draft`, `dry-run`, `running`, `supports`, `refutes`, `inconclusive`, `error`
  - Session mode badge: `cheap`, `serious`, `proof_critical`, `single_session_subagents`, `multi_model_debate`
  - Provider card: `ready`, `not_authenticated`, `missing`, `error`, `disabled`
- Token/component ownership:
  - Add semantic status tokens first.
  - Keep components server-renderable without introducing a JS app bundle by default.

## Accessibility
- Target standard:
  - WCAG 2.2 AA.
- Keyboard/focus behavior:
  - Left phase rail, right object drawers, and action buttons fully keyboard navigable.
  - Visible 2px focus ring in indigo or green depending on context.
- Contrast/readability:
  - Primary text minimum 7:1 on dark surfaces.
  - Status colors never carry meaning alone; always pair with text badge.
- Screen-reader semantics:
  - Phase rail as nav landmark.
  - Timeline as ordered list.
  - Claim/experiment/failure cards use descriptive headings and labels.
- Reduced motion and sensory considerations:
  - Disable panel transitions under reduced motion.
  - Avoid flashing health indicators.

## Responsive behavior
- Supported breakpoints/devices:
  - Desktop: 1440+ optimized.
  - Laptop: 1024-1439.
  - Tablet: 768-1023.
  - Mobile inspection mode: 390-767.
- Layout adaptations:
  - Desktop:
    - 3-column lab session layout.
    - Sticky left phase rail, scrollable center timeline, sticky right intelligence column.
  - Tablet:
    - Left rail collapses into a horizontal phase strip.
    - Right column becomes stacked drawers below timeline.
  - Mobile:
    - Single column.
    - Phase strip collapses into segmented control.
    - Claims / experiments / failures become tabs.
- Touch/hover differences:
  - Hover reveals secondary controls on desktop.
  - Touch uses explicit “More” menus and persistent buttons.

## Interaction states
- Loading:
  - Skeleton bars for status cards, timeline cards, and side panels.
  - Preserve layout while data loads.
- Empty:
  - Empty claims board: “No claims extracted yet. Advance the session or run a role.”
  - Empty experiments: “No experiment has been designed for the current claim.”
  - Empty failures: “No archived failures yet. Referee review may still expose one.”
- Error:
  - Provider auth and MCP errors are shown inline in the relevant panel and echoed in Control Panel alerts.
  - Do not replace the whole page with an error unless the session itself is missing.
- Success:
  - Quiet confirmation toast or inline banner only.
  - No modal celebration.
- Disabled:
  - Actions disabled with reason text, e.g. “No linked claim”, “Provider login required”.
- Offline/slow network, if applicable:
  - Keep last-known system status visible with timestamp.
  - Mark stale data explicitly.

## Content voice
- Tone:
  - Direct, technical, unsentimental.
- Terminology:
  - Use “claim”, “experiment”, “failure”, “referee”, “session”, “evidence”, “provenance”, “next action”.
  - Avoid “achievement”, “quest”, “mission”, “level”.
- Microcopy rules:
  - Every warning should name the failure surface and next operator action.
  - Never imply proof when status is heuristic or unknown.

## Implementation constraints
- Framework/styling system:
  - Existing FastAPI + server-rendered HTML.
  - Prefer shared component functions in `mystic/app/components.py` and page assembly in `mystic/app/pages.py`.
- Design-token constraints:
  - Introduce CSS custom properties for semantic status tokens and dark-mode surfaces.
  - Avoid per-screen bespoke color values.
- Performance constraints:
  - Keep first render usable without client hydration.
  - Graph/detail views may progressively enhance later.
- Compatibility constraints:
  - Preserve current routes and existing Research Table flows.
  - Keep Model Arena as integrated Research Table, not a duplicate subsystem.
- Test/screenshot expectations:
  - Add page tests for route-level content and state visibility.
  - Future UI refactor should preserve room/phase labels and provenance text in rendered HTML.

## Sitemap
- `Control Panel`
  - System Status
  - Active Sessions
  - Failures & Warnings
  - Quick Actions
- `Create Lab Session`
  - Problem Intake Form
  - Participants
  - Mode / Safety / Scope
- `Lab Session Detail`
  - Main Lab Room
  - Theory Room
  - Hypothesis Chamber
  - Experiment Room
  - Simulation Tank
  - Proof Forge
  - Referee Court
  - Failure Museum
  - Dataset Room
  - Lab Notebook
  - Paper Room
  - Research Memory Graph
  - Model Arena
- `Provider / MCP Settings`
  - Provider auth
  - MCP endpoint status
  - Gateway / health / warnings

## Screen mockups

### 1. Control Panel
```text
+----------------------------------------------------------------------------------+
| Mystic Virtual Research Lab                                                     |
| System status | MCP gateway | Local backend | Adapters | Active warnings         |
+---------------------------+---------------------------+---------------------------+
| Active Lab Sessions       | Provider Status           | Failed Training Runs      |
| - lab-20260701-01         | local_prime   READY       | raven_vnext_eval warning  |
| - lab-20260701-02         | gemini_cli    AUTH_REQ    | forge_lora_v0 failed      |
|                           | claude_cli    READY       |                           |
+---------------------------+---------------------------+---------------------------+
| Quick Start               | Memory Search             | Failure Feed              |
| [Create Lab Session]      | [query................]   | latest fatal errors       |
| [Open Model Arena]        | matching claims/sessions  | export to Raven           |
| [View Dataset Room]       |                           |                           |
+----------------------------------------------------------------------------------+
```

### 2. Create Lab Session
```text
+--------------------------------------------------+-------------------------------+
| Problem statement                                | Safety / Scope Note           |
| [ multiline input ]                              | - no hidden execution         |
|                                                  | - proof-critical is stricter  |
+--------------------------------------------------+-------------------------------+
| Domain       | Goal                              | Mode                          |
| math         | prove complete solution set       | serious / proof_critical      |
+----------------------------------------------------------------------------------+
| Participants                                                                    |
| [x] local_prime     READY      [x] local_raven      READY                        |
| [ ] gemini_cli      AUTH_REQ   [ ] claude_cli       READY                        |
+----------------------------------------------------------------------------------+
| [Start Lab Session]                                                            |
+----------------------------------------------------------------------------------+
```

### 3. Lab Session Detail
```text
+----------------------+-------------------------------------------+----------------------+
| Phase Rail           | Research Timeline                         | Intelligence Column  |
| Problem Intake       | [Director turn]                           | Claim Board          |
| Background Scan      | [Theorist turn]                           | Experiment Queue     |
| Hypothesis Gen       | [HypothesisGenerator turn]                | Failures             |
| Experiment Design    | [ExperimentDesigner turn]                 | Report Preview       |
| Simulation           | [Simulator / Model Arena / Tool turns]    | Next Actions         |
| Referee Review       | [Referee review]                          |                      |
| Failure Archive      | [Archivist update]                        |                      |
| Knowledge Update     | [Synthesizer update]                      |                      |
| Next Planning        |                                           |                      |
| Report Generation    |                                           |                      |
+----------------------+-------------------------------------------+----------------------+
```

### 4. Claims Board
```text
+----------------------------------------------------------------------------------+
| Claims Board                                                                     |
| [HEURISTIC] Bounded denominator argument          source: Theorist / local_prime |
| evidence: none yet                                related experiments: exp-17     |
| related failures: none                            next: send to Experiment Room   |
|----------------------------------------------------------------------------------|
| [REFUTED] Candidate set {(2,4,8)} complete        source: Model Arena / Gemini   |
| evidence: verifier INVALID                        related failures: fail-3        |
+----------------------------------------------------------------------------------+
```

### 5. Experiment Room
```text
+----------------------------------------------------------------------------------+
| Experiment Room                                                                  |
| linked claim: claim-17                                                           |
| method: python_bruteforce                                                        |
| inputs: candidate tuples, ordering constraint                                    |
| outputs: verifier payload / search results                                       |
| verdict: supports                                                                |
| evidence summary: deterministic verifier confirmed three candidates              |
| [Dry Run] [Run Experiment]                                                       |
+----------------------------------------------------------------------------------+
```

### 6. Referee Court
```text
+----------------------------------------------------------------------------------+
| Referee Court                                                                    |
| Hostile review checklist                                                         |
| [x] hidden assumption check  [x] missing case check  [ ] contradiction sweep     |
| first fatal error: assumes completeness after x=2 branch only                    |
| critique: proof does not close z-growth argument                                 |
| recommended next action: open Experiment Room and test x>=3 branch               |
| [Create Failure]                                                                  |
+----------------------------------------------------------------------------------+
```

### 7. Failure Museum
```text
+----------------------------------------------------------------------------------+
| Failure Museum                                                                   |
| [logic_gap] claim-17                                                             |
| first fatal error: branch completeness not shown                                 |
| lesson: force enumeration before synthesis                                       |
| reusable as training data: yes                                                   |
| [Export to Raven]                                                                |
+----------------------------------------------------------------------------------+
```

### 8. Research Memory Graph
```text
+----------------------------------------------------------------------------------+
| Memory Graph                                                                     |
| session-12 -> claim-17  supports                                                 |
| claim-17  -> exp-21    generated_experiment                                      |
| exp-21    -> claim-17  supports                                                  |
| claim-20  -> fail-3    caused_failure                                            |
| fail-3    -> raven_row generated_training_data                                   |
+----------------------------------------------------------------------------------+
```

### 9. Model Arena
```text
+----------------------------------------------------------------------------------+
| Model Arena                                                                      |
| participants: local_prime | Gemini CLI | Claude CLI | GPT Controller | verifier  |
| round: independent discovery -> cross critique -> tool verification -> revision  |
| final synthesis: INVALID by deterministic verifier                               |
| [Import Accepted Discoveries] [Import Refuted Discoveries as Failures]           |
+----------------------------------------------------------------------------------+
```

### 10. Lab Notebook
```text
+----------------------------------------------------------------------------------+
| Lab Notebook                                                                     |
| 03:14 Background Scan completed                                                  |
| 03:18 claim-17 created                                                           |
| 03:21 exp-21 ran with supports verdict                                           |
| 03:27 Referee found fatal gap                                                    |
| next actions: formalize completeness proof / rerun Model Arena                   |
+----------------------------------------------------------------------------------+
```

### 11. Paper Room
```text
+----------------------------------------------------------------------------------+
| Paper Room                                                                       |
| Surviving claims                                                                 |
| Failed claims                                                                    |
| Evidence                                                                         |
| Limitations                                                                      |
| Next work                                                                        |
| [Export Markdown]                                                                |
+----------------------------------------------------------------------------------+
```

## Component library
- Layout
  - `AppShell`
  - `TopCommandBar`
  - `LeftPhaseRail`
  - `RightInsightColumn`
  - `Panel`
  - `SplitPanel`
- Status and identity
  - `StatusBadge`
  - `ProviderBadge`
  - `ModeBadge`
  - `RoomBadge`
  - `ObjectIdPill`
- Session controls
  - `QuickStartCard`
  - `AdvancePhaseButton`
  - `ImportFromArenaButton`
  - `GenerateReportButton`
- Research objects
  - `ClaimBoardCard`
  - `ExperimentRunCard`
  - `FailureCard`
  - `NotebookEntry`
  - `ReportSectionCard`
  - `MemoryEdgeRow`
- Verification and critique
  - `ToolEvidenceBlock`
  - `RefereeChecklistPanel`
  - `FatalErrorBanner`
  - `ProvenanceFooter`
- Provider / MCP
  - `MCPHealthCard`
  - `ProviderSettingsTable`
  - `AuthWarningBanner`

## Design system tokens
- Color tokens:
  - `--bg-0: #0b1020`
  - `--bg-1: #111827`
  - `--bg-2: #162033`
  - `--panel: rgba(17, 24, 39, 0.88)`
  - `--panel-strong: #111827`
  - `--line: rgba(148, 163, 184, 0.18)`
  - `--text-strong: #e5edf7`
  - `--text-muted: #93a4b8`
  - `--accent-indigo: #6d5efc`
  - `--accent-purple: #8b5cf6`
  - `--ok: #22c55e`
  - `--warn: #f59e0b`
  - `--fail: #ef4444`
  - `--unknown: #94a3b8`
- Type tokens:
  - `--font-ui: "Geist Sans", "IBM Plex Sans", "SF Pro Text", sans-serif`
  - `--font-mono: "Berkeley Mono", "JetBrains Mono", "SF Mono", monospace`
  - `--text-xs: 12px`
  - `--text-sm: 13px`
  - `--text-md: 14px`
  - `--text-lg: 16px`
  - `--text-xl: 20px`
- Radius tokens:
  - `--radius-sm: 8px`
  - `--radius-md: 12px`
  - `--radius-lg: 14px`
- Space tokens:
  - `--space-1: 4px`
  - `--space-2: 8px`
  - `--space-3: 12px`
  - `--space-4: 16px`
  - `--space-5: 24px`
- Shadow tokens:
  - `--shadow-1: 0 1px 2px rgba(0,0,0,0.2)`
  - `--shadow-2: 0 8px 24px rgba(0,0,0,0.24)`

## Responsive behavior
- Control Panel:
  - Desktop shows 3-column system summary.
  - Mobile stacks status, sessions, and warnings in priority order: MCP -> providers -> sessions -> failures.
- Create Lab Session:
  - Desktop has form + safety panel.
  - Mobile turns safety panel into collapsible info card below submit.
- Lab Session Detail:
  - Desktop 3-column.
  - Tablet collapses right rail beneath timeline.
  - Mobile uses tabs: `Timeline`, `Claims`, `Experiments`, `Failures`, `Report`.
- Memory Graph:
  - Desktop can support split list + graph later.
  - Mobile defaults to sortable list of relations.

## Empty/loading/error states
- Control Panel loading:
  - Skeleton cards with stale timestamp placeholders.
- Control Panel error:
  - Show `MCP gateway unavailable`, `local backend down`, `provider auth required` as separate banners.
- Lab Session empty:
  - If no turns yet, center panel shows “Session created. No research steps have run yet.”
- Claims empty:
  - “No claims extracted. Use Theory Room or Model Arena.”
- Experiments empty:
  - “No experiment designed. Link a claim first.”
- Failures empty:
  - “No archived failures. Referee Court may still expose hidden gaps.”
- Provider auth error:
  - Inline banner on affected provider card and mirrored badge in Control Panel.
- Proof-critical mode:
  - Add persistent strictness strip: `Unverified claims will not be promoted without referee/tool support.`

## Developer handoff notes
- The current UI code in [mystic/app/components.py](/Users/JYH/Documents/Mystic/mystic/app/components.py) and [mystic/app/pages.py](/Users/JYH/Documents/Mystic/mystic/app/pages.py) is a usable structural baseline but not the target visual system. It currently uses a warm light palette and serif-heavy hero treatment; replace that with the dark research OS system above.
- Start implementation by refactoring `BASE_CSS` into semantic dark-mode tokens instead of per-component ad hoc colors.
- Keep server-rendered HTML as the default architecture.
- Promote lab objects to first-class components before adding new decorative layout.
- Separate `tool evidence` and `model output` visually everywhere.
- Add `phase rail` and `right intelligence column` to `LabSessionPage` first; that gives the highest product lift.
- Keep Model Arena purple/indigo scoped to that room only. Do not let it dominate the global app theme.
- Preserve route compatibility:
  - `/lab/start`
  - `/lab/sessions/<id>`
  - `/research-table/start`
  - `/research-table/sessions/<id>`
- When a claim status changes, update both badge color and adjacent text label.
- Treat `Failure Museum` as high-value research memory, not an error graveyard.

## Open questions
- [ ] Should `Proof Forge` appear as a separate center-phase lane, or as a filtered view over turns tagged `ProofForger`?
- [ ] Does `Dataset Room` remain under `/teacher-labels` initially, or should it become its own route immediately?
- [ ] Should `Provider / MCP Settings` live in the main app nav or behind a settings drawer for operator-only access?
