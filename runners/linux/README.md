# Mystic Linux CPU runner

This is the Phase 2B.1 container package for the trusted Linux CPU runner. It
uses the same allowlisted `scripts/mystic_engine_runner.py` runtime as macOS;
it does not accept code, commands, package names, paths, or imports from jobs.

## Operator requirements

- Build from a reviewed persistent checkout, never `/tmp`, and pin the Python
  base image by digest in deployment automation.
- Create the external Docker secret `mystic_engine_runner_token` from a
  per-runner fleet credential. Do not put a credential in Compose, image
  layers, environment files, logs, or shell history.
- Keep the process non-root. The supplied Compose service has a read-only root
  filesystem, a bounded `tmpfs` at `/tmp`, no capabilities, no inbound ports,
  CPU/memory/PID limits, and `no-new-privileges`.
- The supplied Compose file starts with `network_mode: none` for offline image
  verification. Before a real claim loop is started, use a reviewed
  deployment-specific override that enables egress only to the configured
  Mystic Worker HTTPS origin and required DNS. Docker Compose alone cannot
  express an outbound hostname allowlist, so this is enforced by the host or
  network policy layer.
- Set a distinct `MYSTIC_ENGINE_RUNNER_ID` and provision its SHA-256 verifier
  in `lab_engine_runner_credentials` before enabling `fleet_active`.

## Start and drain

```bash
docker compose -f runners/linux/compose.yaml up -d --build
docker compose -f runners/linux/compose.yaml stop
```

`SIGTERM` requests draining, lets an active bounded engine job finish, then
releases the runner. A lost container is recovered only by lease expiry. The
service has no listener and never exposes runner credentials or host details.
