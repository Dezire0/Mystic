from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import subprocess
import sys

TUNNEL_URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a Cloudflare quick tunnel and publish its origin to a GitHub gist.")
    parser.add_argument("--local-url", default="http://127.0.0.1:8765")
    parser.add_argument("--gist-id", required=True)
    parser.add_argument("--gist-file", default="mystic-origin.json")
    parser.add_argument("--description", default="Mystic public ingress origin state")
    return parser


def update_gist_origin(*, gist_id: str, gist_file: str, description: str, origin: str) -> None:
    payload = {
        "description": description,
        "files": {
            gist_file: {
                "content": json.dumps(
                    {
                        "origin": origin,
                        "updated_at": datetime.now(UTC).isoformat(),
                    },
                    ensure_ascii=True,
                )
                + "\n"
            }
        },
    }
    temp_path = Path("/tmp") / f"mystic-origin-{gist_id}.json"
    temp_path.write_text(json.dumps(payload), encoding="utf-8")
    try:
        result = subprocess.run(
            ["gh", "api", f"/gists/{gist_id}", "--method", "PATCH", "--input", str(temp_path)],
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        temp_path.unlink(missing_ok=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "failed to update gist")


def stream_tunnel(local_url: str, gist_id: str, gist_file: str, description: str) -> int:
    process = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", local_url, "--no-autoupdate"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None

    published_origin: str | None = None
    for line in process.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        if published_origin is not None:
            continue
        match = TUNNEL_URL_PATTERN.search(line)
        if match is None:
            continue
        published_origin = match.group(0)
        update_gist_origin(
            gist_id=gist_id,
            gist_file=gist_file,
            description=description,
            origin=published_origin,
        )
        sys.stdout.write(f"Mystic public origin updated: {published_origin}\n")
        sys.stdout.flush()
    return process.wait()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(stream_tunnel(args.local_url, args.gist_id, args.gist_file, args.description))


if __name__ == "__main__":
    raise SystemExit(main())
