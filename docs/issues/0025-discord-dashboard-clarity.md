# Issue #25: Simplify Discord dashboard status semantics

## Summary
Simplify the Mystic Discord dashboard so users can immediately tell whether training is actually running, waiting, or broken without interpreting conflicting percentages and raw backend phases.

## Motivation
The current Discord overview mixes multiple progress models:
- some specialists show `100%` while they are not actively training
- Raven can show a low phase-based percent like `32%`
- green currently means both "success" and "running"
- yellow currently means waiting, which conflicts with the desired interpretation

This makes it hard to tell whether Mystic is genuinely training right now.

## Current Behavior
- Overview pages show percent plus status text on every row.
- Green can mean active or simply recently successful.
- Yellow means waiting for data.
- Raw phase text like `submitted` leaks into the overview.

## Expected Behavior
- Yellow means `학습 중`.
- Green means `대기` or `완료`.
- Red means `오류`.
- Overview rows should prioritize a short status label over percent noise.
- Detail pages can still show percent, but the meaning should be clearer.

## Scope
- Simplify status inference in `mystic/discord_dashboard.py`.
- Simplify overview page row formatting and legend text.
- Convert local/remote status boxes to short Korean summaries.
- Keep detail pages informative but less noisy.

## Acceptance Criteria
- A user can open the Discord overview and distinguish active training from waiting at a glance.
- No specialist appears both `100%` and ambiguously "submitted" in the same row style.
- Yellow is used for active training states.
- Overview copy is Korean and short.

## Verification Plan
- Update and run dashboard-focused tests.
- Regenerate the dashboard snapshot locally and inspect representative rows.
- Restart the Discord bot service so the new embeds are served.

## Reproduction Steps
1. Open the Discord DM dashboard.
2. Observe many rows marked `100%` while only one or two actual jobs are active.
3. Observe Raven showing `32%` from a backend phase rather than understandable user-facing status.

## Actual Result
The dashboard is technically populated but hard to interpret.

## Expected Result
The dashboard should answer one question immediately: which models are training now, which are waiting, and which are broken.

## Environment
- Project root: `/Users/JYH/Documents/Mystic`
- Discord DM dashboard bot
