# Issue #23: Add persistent launchd service for the Mystic Discord bot

## Summary
Add a macOS launchd management script so the Mystic Discord bot can run persistently in the background.

## Motivation
The Discord bot now works, but it still requires manual startup. The user wants it to stay running continuously.

## Current Behavior
- `scripts/run_discord_bot.py` must be started manually.
- There is no launchd plist or management command for the Discord bot.

## Expected Behavior
- A launchd service can be installed, started, stopped, restarted, and inspected for the Discord bot.
- The service uses the dedicated `.venv-discord` runtime and reads `.env` automatically through the bot script.
- Logs are written to `mystic_data/logs/`.

## Scope
- Add `scripts/manage_discord_bot_service.py`.
- Add basic test coverage for its command/plist wiring.
- Update README with persistent-run commands.

## Non-goals
- Host the bot remotely.
- Build a separate bot health dashboard.

## Acceptance Criteria
- `install`, `start`, `stop`, `restart`, `status`, and `uninstall` commands exist.
- The plist targets `.venv-discord/bin/python`.
- Service logs are written under `mystic_data/logs/`.

## Verification Plan
- Run focused unit tests for the new service helpers.
- Run `py_compile` on the new script.
- Install/start the launchd service locally and inspect status output.

## Actual Result
Persistent execution for the Discord bot is not available yet.

## Environment
- Project root: `/Users/JYH/Documents/Mystic`
- macOS launchd
