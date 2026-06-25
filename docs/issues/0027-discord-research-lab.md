# Issue #27: Add Mystic Discord research lab for real user math questions

## Summary
Add a real test mode to the Mystic Discord bot so users can submit natural-language math questions and receive a structured research-style answer using the local Mystic inference stack.

## Motivation
The bot currently shows training status only. The user wants a practical "local lab" mode that actually answers mathematical questions using Mystic's trained status and specialist structure.

## Current Behavior
- `/mystic` opens the dashboard only.
- There is no user-facing question answering workflow inside the Discord bot.
- Trained specialist metadata and Raven status are not reused for live question answering.

## Expected Behavior
- The bot exposes a research-lab command for natural-language math questions.
- The answer flow explicitly performs:
  1. question understanding
  2. strategy planning
  3. approach execution
  4. conclusion drafting
  5. hallucination reduction via critique
- The workflow uses local Mystic model configuration and available trained-state context.

## Scope
- Add a new local inference pipeline module for research-lab execution.
- Add Discord slash command integration.
- Reuse existing Mystic LLM backend selection and Raven critique parser.
- Surface specialist/model choice and caution state in the final reply.

## Non-goals
- Full symbolic proof engine integration
- Web frontend
- Multi-user persistent session state
- Automatic theorem verification beyond current LLM/Raven critique

## Acceptance Criteria
- A Discord user can submit a math question through the bot.
- The bot returns a structured answer with strategy and conclusion.
- The pipeline uses a critic pass to reduce unsupported claims.
- Failures are reported clearly instead of crashing the bot.

## Verification Plan
- Add focused unit tests for routing/parsing/fallback behavior.
- Run bot-adjacent tests.
- Smoke-test command registration and response formatting locally.

## Player Flow
1. User runs the research-lab slash command with a question.
2. Bot acknowledges and runs the local pipeline.
3. Bot returns:
   - chosen specialist
   - model/backend summary
   - structured reasoning result
   - confidence or caution note after Raven review

## Actual Result
No live research-lab question answering exists yet.

## Expected Result
Mystic should function as a usable local mathematical research assistant inside Discord.

## Environment
- Project root: `/Users/JYH/Documents/Mystic`
- Discord DM/status bot
- Local Ollama / OpenAI-compatible / adapter backends
