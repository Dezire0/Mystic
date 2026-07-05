# Cloudflare Named Tunnel Template

This template is intentionally placeholder-only. Do not commit real tunnel credentials, real tunnel IDs, or secret files.

## Why use a named tunnel

- Cloudflare quick tunnels are temporary.
- The public Mystic Worker can still expose correct OAuth metadata while runtime MCP calls fail because the backend origin expired.
- A named tunnel gives the Worker a stable backend origin for `MYSTIC_BACKEND_URL`.

## Example flow

Create a named tunnel:

```bash
cloudflared tunnel create mystic-backend
```

Route DNS to the tunnel:

```bash
cloudflared tunnel route dns mystic-backend mystic-backend.example.com
```

Run the tunnel:

```bash
cloudflared tunnel run mystic-backend
```

## Example config template

Use placeholders only:

```yaml
tunnel: <TUNNEL_ID_PLACEHOLDER>
credentials-file: /path/to/<TUNNEL_CREDENTIALS_PLACEHOLDER>.json

ingress:
  - hostname: mystic-backend.example.com
    service: http://127.0.0.1:8765
  - service: http_status:404
```

## Worker configuration

Point the public Worker at the stable backend origin:

```text
MYSTIC_BACKEND_URL=https://mystic-backend.example.com
```

## Post-change checks

After changing the backend origin, rerun:

```bash
curl -i https://mystic.dexproject.workers.dev/health

python scripts/run_remote_mcp_lab_smoke.py \
  --endpoint https://mystic.dexproject.workers.dev/mcp \
  --auth-mode bearer \
  --bearer-token "$MYSTIC_TEST_BEARER_TOKEN"

python scripts/run_remote_mcp_lab_smoke.py \
  --endpoint https://mystic.dexproject.workers.dev/mcp \
  --auth-mode expect-auth-required \
  --allow-auth-required
```
