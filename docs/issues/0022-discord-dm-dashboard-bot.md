# Issue #22: Add Discord DM dashboard bot for Mystic training status

## Summary
Add a Discord bot that can DM users a paginated Mystic training dashboard and show per-expert detail pages with progress, dataset, ETA, and failure logs.

## Motivation
Mystic already writes live state and report JSON locally, but the user wants a Discord-first monitoring surface that can be checked from DM without opening local HTML reports.

## Current Behavior
- Training state is available through local JSON/HTML files only.
- There is no Discord bot, no DM activation flow, and no expert detail view in chat.

## Expected Behavior
- A Discord bot can be started locally with a token from environment variables.
- Users can activate DM delivery and open a dashboard page from Discord.
- Overview pages list all experts across three pages with progress percent and operating status.
- Clicking or selecting an expert opens a detail page with the expert name, progress bar, dataset, ETA, and the latest failure details when available.

## Scope
- Add a Discord bot runtime script and status aggregation helpers.
- Read existing Mystic state/report JSON; do not create a new backend.
- Add DM activation persistence.
- Add README and env guidance for the bot.

## Non-goals
- Host the bot remotely.
- Add a web admin panel.
- Add Discord OAuth or multi-tenant account management.

## Acceptance Criteria
- The bot can open a DM overview page with three expert pages.
- Expert detail pages show dataset, progress, ETA, and failure text when applicable.
- Status colors/icons distinguish running, waiting, and failed states.
- The bot reads from existing Mystic files and does not break append-only logs.

## Verification Plan
- Run unit tests for the new status aggregation helpers.
- Run `py_compile` on the new bot modules.
- Verify the generated embeds/views from helper functions locally.

## Player Flow
1. User runs a slash command from a server or DM.
2. Bot opens or reuses a DM and sends the overview page.
3. User moves between overview pages or selects an expert.
4. Bot updates the message with the expert detail page.

## Actual Result
There is currently no Discord bot for Mystic status monitoring.

## Environment
- Project root: `/Users/JYH/Documents/Mystic`
- Python 3.11
- Local Discord bot token via environment variable
