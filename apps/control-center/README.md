# Mystic LAB Control Center

The Control Center is the separate `mystic-console` Cloudflare Worker and React application for safe operation of Mystic LAB.

## Architecture

The browser only calls same-origin `/api` endpoints. The Worker checks the fallback administrator session in a `Secure`, `HttpOnly`, `SameSite=Strict` cookie, rejects cross-origin mutations, and throttles failed logins in the bound `MYSTIC_CONSOLE_RATE_LIMITS` KV namespace. It then invokes an allowlisted Mystic MCP tool through the `MYSTIC` service binding. The Mystic Worker still enforces its MCP boundary on service-bound calls, so the server-side `MYSTIC_SERVICE_TOKEN` secret is required; if the binding is unavailable in a local or separate-account deployment, the same secret is sent only in a server-to-server request to `MYSTIC_API_ORIGIN`. Neither credential is added to the browser bundle, a URL, or web storage.

The scene engine keeps `SceneDocument` as its serializable source of truth. React Three Fiber is a presentation and interaction layer only. User edits are explicit scene commands, while the BFF maps those changes to Mystic scene tools with a required `expected_revision`. Supabase atomically locks and replaces persisted scene bundles through `mystic_mutate_lab_scene`; stale writes return `scene_conflict` without overwriting data. Revision polling runs every 15 seconds in visible tabs; clean views update automatically and local dirty state becomes an explicit conflict instead of being overwritten. Session, scene, and audit lists come from the live `lab_session_list`, `lab_scene_list`, and `lab_activity_list` MCP tools.

The Engine and Runs screens use fixed, server-side `/api/engines`, `/api/engine-jobs`, and `/api/engine-runs` mappings to the deployed Mystic `/lab/*` API. The browser cannot choose a backend URL, an MCP tool name, SQL/RPC name, or an authorization header. Engine manifests, jobs, runs, artifacts, and visualization descriptors are parsed with Zod before display. The legacy generic built-in schemas have bounded local form fallbacks that mirror their public validators until the registry publishes detailed schemas. Descriptor payloads are bounded and never become executable shaders, URLs, HTML, or scripts; attached result references are fetched afresh, validated, and rendered as non-editable spatial layers. Scene attachment always sends the displayed revision and presents a conflict instead of silently retrying a stale write.

## Required Cloudflare configuration

Set the following only as Worker secrets:

- `MYSTIC_CONSOLE_SESSION_SECRET`
- `MYSTIC_CONSOLE_ADMIN_TOKEN`
- `MYSTIC_SERVICE_TOKEN`

Optional safe variables are `MYSTIC_API_ORIGIN`, `MYSTIC_CONSOLE_SESSION_TTL_SECONDS`, and `MYSTIC_CONSOLE_ALLOWED_EMAILS`. Configure Cloudflare Access before relying on the fallback administrator credential.

Apply `supabase/migrations/` before deploying a Mystic Worker that serves scene mutations or lists. The Mystic Worker must retain `MYSTIC_STORAGE_BACKEND=supabase` and `MYSTIC_SUPABASE_URL=https://wpkellklbmzwfwgofsxa.supabase.co` as runtime variables alongside its existing server-side Supabase service-role secret. Deploy the console with `npm run deploy` from this directory; it targets `mystic-console`, never the production `mystic` Worker.

## Verification

Run `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`, and `npm run test:e2e`. The Playwright workflow deliberately requires an explicitly supplied production-safe URL and administrator credential; it skips rather than manufacturing a live backend response when those values are absent.

For a real hardware measurement, use the deterministic `/lab/benchmark` route. It retains the 100-primitive baseline and adds five bounded Phase 2A result-layer groups (projectile, vectors, N-body, scalar markers, and heatmap points), warms for three seconds, measures ten seconds of rendered frames, then records draw calls, triangles, p50/p95/average frame time, approximate FPS, initialization time, selection latency, and layer-toggle latency. Run it only with an explicit target and credential:

```bash
MYSTIC_RUN_3D_PERF_BENCHMARK=1 \
MYSTIC_CONSOLE_E2E_URL=https://mystic-console.dexproject.workers.dev \
MYSTIC_CONSOLE_E2E_ADMIN_TOKEN='<local secret>' \
npm run test:e2e -- --grep @performance
```

It records no GPU memory metric unless the browser exposes one reliably; its functional assertions intentionally avoid universal FPS thresholds.
