# Gemini App Manual Relay Extension

This extension is a user-controlled `manual_send` relay. It has no Gemini host permission, content scripts, cookie/debugger/history/webRequest permissions, or Gemini network calls. It never reads, fills, clicks, or scrapes a Gemini page.

## Install

1. Open `chrome://extensions`, enable **Developer mode**, and choose **Load unpacked**.
2. Select this directory and copy the shown extension ID.
3. Run `python scripts/install_mystic_gemini_native_host.py --extension-id <EXTENSION_ID>` from the Mystic repository.
4. Restart Chrome, set `MYSTIC_RUNNER_BEARER_TOKEN` in the local shell, then run `python scripts/mystic_gemini_app_relay.py --start`.
5. Open the extension and click **Start Mystic Relay**.

## Manual flow

1. ChatGPT starts a Mystic orchestration run.
2. Click **Refresh queue**. The approved job shows its session, run, role, round, and prompt.
3. Click **Copy Prompt**, then **Open Gemini**. Sign in and submit the prompt yourself in the official Gemini UI.
4. Copy Gemini's visible response, return to the extension, paste it, preview it, and click **Submit Response**.
5. ChatGPT polls Mystic MCP and retrieves the full ordered transcript. It remains the controller, critic, referee, and final synthesizer.

The local runner sends its bearer token only to Mystic over HTTPS. The extension and Native Messaging manifest contain no token or provider credential.
