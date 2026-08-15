# Design

## Source of truth

- Status: Active
- Last refreshed: 2026-08-14
- Primary product surfaces: local Mystic Control Center specialist registry and evidence provenance views.
- Evidence reviewed: `mystic/app/api.py`, `mystic/app/pages.py`, `mystic/app/components.py`, `docs/research_campaign_runtime.md`, `docs/scientific_job_runtime.md`, and `docs/mystic_lab_phase2d_specialists.md`.

## Brand

- Personality: calm, rigorous, laboratory-like, and legible under scientific scrutiny.
- Trust signals: explicit state labels, provenance paths, empty states, timestamps, and no implied live execution.
- Avoid: chatbot framing, simulated intelligence, dashboards that disguise unavailable data, or controls that imply arbitrary model execution.

## Product goals

- Goals: make specialist availability, benchmark standing, routing eligibility, and evidence lineage inspectable.
- Non-goals: configure provider credentials, run models, expose document bodies, or replace the research controller.
- Success signals: an operator can distinguish candidate metadata, verified state, current usage, and missing evidence at a glance.

## Personas and jobs

- Primary personas: research operator, scientific reviewer, and Mystic developer.
- User jobs: inspect a specialist's safe capability record; understand why it is unavailable; trace evidence to a source/page/transformation.
- Key contexts of use: local development and pre-rollout review, often with no external provider configured.

## Information architecture

- Primary navigation: direct read-only routes from the existing local FastAPI surface.
- Core routes/screens: `/specialists`, `/specialists/:id`, `/evidence`.
- Content hierarchy: status and classification first, capabilities/limitations second, recent safe usage and provenance third.

## Design principles

- Show evidence state before model branding.
- Make a missing or unverified result explicit rather than suggesting success.
- Tradeoffs: preserve the existing server-rendered, dependency-free UI rather than introducing a new frontend system.

## Visual language

- Color: reuse existing warm paper panels with teal for information, green for verified/healthy, and red for unavailable/failure states.
- Typography: reuse the current serif title and system sans body stack.
- Spacing/layout rhythm: reuse `.page`, `.hero`, `.grid`, `.panel`, `.meta-row`, and `.badge` primitives.
- Shape/radius/elevation: reuse existing rounded panel and subtle-shadow values.
- Motion: none required.
- Imagery/iconography: none required; text labels must carry status.

## Components

- Existing components to reuse: `layout`, panels, grids, chips, badges, and action rows in `mystic/app/components.py`.
- New/changed components: specialist summary/detail cards and compact provenance path cards in `mystic/app/pages.py`.
- Variants and states: healthy, unverified, disabled, unavailable, empty usage, and missing evidence.
- Token/component ownership: existing `BASE_CSS` remains authoritative.

## Accessibility

- Target standard: semantic headings, descriptive links, and text-based state labels compatible with WCAG AA intent.
- Keyboard/focus behavior: native links only; no custom keyboard interaction.
- Contrast/readability: reuse existing foreground/background tokens and never make colour the sole state indicator.
- Screen-reader semantics: provenance is an ordered list; status is visible text.
- Reduced motion and sensory considerations: no animated content.

## Responsive behavior

- Supported breakpoints/devices: existing responsive grid and narrow viewport layout.
- Layout adaptations: cards collapse through the existing `auto-fit` grid.
- Touch/hover differences: no hover-only information or actions.

## Interaction states

- Loading: server-rendered routes; no fabricated loading result.
- Empty: explicitly state when no safe evidence or usage record exists.
- Error: route returns ordinary HTTP error for unknown IDs; pages display unavailable model state from safe data.
- Success: registry and provenance cards report actual persisted values.
- Disabled: disabled/unclassified models state the benchmark or configuration reason.
- Offline/slow network, if applicable: remote provider state stays unverified; pages make no client-side request.

## Content voice

- Tone: precise, conservative, and non-anthropomorphic.
- Terminology: use “specialist”, “candidate”, “evidence”, “provenance”, and “controller”; avoid “agent” for specialist models.
- Microcopy rules: never say a model is working, superior, or used unless a recorded result says so.

## Implementation constraints

- Framework/styling system: current FastAPI server-rendered HTML and inline CSS only.
- Design-token constraints: do not add a parallel CSS/token system.
- Performance constraints: list views return bounded, redacted metadata; no raw document contents.
- Compatibility constraints: preserve existing Research Table pages and root redirect.
- Test/screenshot expectations: unit tests assert semantic headings, status labels, and provenance nodes; no visual snapshot baseline exists.

## Open questions

- [ ] Which authenticated Control Center/BFF is authoritative for deploying these local views? Owner: platform; impact: Phase 2D.2 rollout.
- [ ] What benchmark thresholds and corpus governance approve live specialist use? Owner: research platform; impact: model enablement.
