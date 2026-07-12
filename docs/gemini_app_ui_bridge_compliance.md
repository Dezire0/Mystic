# Gemini App UI Bridge Compliance Gate

Assessment date: 2026-07-12.

This integration is local and user-controlled. It never extracts credentials, cookies, browser storage, network traffic, or hidden application state. It does not bypass CAPTCHA, quota, login, or account restrictions.

## Sources reviewed

- Google [Terms of Service](https://policies.google.com/terms/embedded?hl=en-US) prohibit automated access that violates machine-readable page instructions.
- `https://gemini.google.com/robots.txt` currently disallows `/app/` and `/chat/` for all user agents.
- Chrome's [minimum-permission policy](https://developer.chrome.com/docs/webstore/program-policies/user-data-faq/) requires the narrowest permissions necessary.
- Chrome [Native Messaging documentation](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging?hl=en) requires an allowed-origin manifest and framed stdin/stdout messages.

## Result

| Proposed action | Classification | Decision |
| --- | --- | --- |
| Open Gemini in a dedicated profile | allowed_or_not_restricted | User-controlled manual action. |
| Extension session controls and local job display | allowed_or_not_restricted | No Gemini-page access or credential access. |
| Native Messaging with one installed extension ID | allowed_or_not_restricted | Restricted by Chrome host manifest and local IPC. |
| Automatically submit prompts in `gemini.google.com/app` | prohibited_or_unsupported | Not implemented while robots instructions disallow automated app access. |
| Automatically scrape rendered Gemini responses | prohibited_or_unsupported | Not implemented for the same reason. |
| Manual send and explicit visible-response import | unclear_requires_user_control | Implemented as the least-privileged fallback. |
| Cookies, OAuth, storage, hidden RPCs, interception, CAPTCHA/quota bypass, account rotation, stealth/headless automation | prohibited_or_unsupported | Never implemented. |

## Permitted mode

`manual_send` is the only enabled mode. `session_visible` and `confirm_send` are documented as unavailable unless this assessment is revisited after Google explicitly permits the relevant automated behavior and machine-readable restrictions allow it.
