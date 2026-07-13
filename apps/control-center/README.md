# Mystic LAB Control Center

The Control Center is the separate `mystic-console` Cloudflare Worker and React application for safe operation of Mystic LAB.

## Architecture

The browser only calls same-origin `/api` endpoints. The Worker checks the fallback administrator session in a `Secure`, `HttpOnly`, `SameSite=Strict` cookie, then invokes an allowlisted Mystic MCP tool through the `MYSTIC` service binding. The current Mystic Worker still enforces its MCP OAuth boundary on service-bound calls, so the server-side `MYSTIC_SERVICE_TOKEN` secret is required; if the binding is unavailable in a local or separate-account deployment, the same secret is sent only in a server-to-server request to `MYSTIC_API_ORIGIN`. Neither credential is added to the browser bundle, a URL, or web storage.

The scene engine keeps `SceneDocument` as its serializable source of truth. React Three Fiber is a presentation and interaction layer only. User edits are explicit scene commands, while the BFF maps those changes to existing Mystic scene tools. Revision polling runs every 15 seconds in visible tabs; clean views update automatically and local dirty state becomes an explicit conflict instead of being overwritten.

## Required Cloudflare configuration

Set the following only as Worker secrets:

- `MYSTIC_CONSOLE_SESSION_SECRET`
- `MYSTIC_CONSOLE_ADMIN_TOKEN`
- `MYSTIC_SERVICE_TOKEN`

Optional safe variables are `MYSTIC_API_ORIGIN`, `MYSTIC_CONSOLE_SESSION_TTL_SECONDS`, and `MYSTIC_CONSOLE_ALLOWED_EMAILS`. Configure Cloudflare Access before relying on the fallback administrator credential.

Deploy with `npm run deploy` from this directory. This targets `mystic-console`, never the production `mystic` Worker.

## Verification

Run `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`, and `npm run test:e2e`. The Playwright workflow deliberately requires an explicitly supplied production-safe URL and administrator credential; it skips rather than manufacturing a live backend response when those values are absent.
