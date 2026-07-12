#!/usr/bin/env python3
"""Local Native Messaging host for the Mystic manual Gemini relay.

This process has no browser-page, credential, cookie, or network access.  Chrome
uses stdio framing while the local runner connects through a mode-0600 Unix socket.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import struct
import sys
import threading
import time
from typing import Any

HOST_NAME = "com.mystic.gemini_app_bridge"
MAX_MESSAGE_BYTES = 1024 * 1024
MAX_RESPONSE_CHARS = 120_000
ALLOWED_OPERATIONS = frozenset({"relay_start", "relay_status", "relay_pause", "relay_resume", "relay_stop", "job_next", "job_get", "response_submit", "job_cancel", "queue_count"})
APP_DIR = Path.home() / "Library" / "Application Support" / "Mystic"
CONFIG_PATH = APP_DIR / "gemini_app_bridge_host.json"
SOCKET_PATH = APP_DIR / "gemini_app_bridge.sock"


def safe_error(code: str) -> dict[str, str]:
    return {"status": code, "safe_error": code.replace("_", " ")}


def read_frame(stream: Any) -> dict[str, Any] | None:
    header = stream.read(4)
    if not header:
        return None
    if len(header) != 4:
        raise ValueError("malformed_message")
    size = struct.unpack("<I", header)[0]
    if size > MAX_MESSAGE_BYTES:
        raise ValueError("message_too_large")
    payload = stream.read(size)
    if len(payload) != size:
        raise ValueError("malformed_message")
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("malformed_message")
    return value


def write_frame(stream: Any, value: dict[str, Any], lock: threading.Lock) -> None:
    payload = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    if len(payload) > MAX_MESSAGE_BYTES:
        raise ValueError("message_too_large")
    with lock:
        stream.write(struct.pack("<I", len(payload)))
        stream.write(payload)
        stream.flush()


def validate_operation(message: dict[str, Any]) -> str:
    operation = message.get("operation")
    if not isinstance(operation, str) or operation not in ALLOWED_OPERATIONS:
        raise ValueError("unsupported_operation")
    return operation


def load_config() -> dict[str, str]:
    try:
        value = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def approved_extension(argv: list[str], config: dict[str, str]) -> bool:
    expected = str(config.get("extension_id", "")).strip()
    if not expected or len(argv) < 2:
        return False
    return argv[1] == f"chrome-extension://{expected}/"


class RelayHost:
    def __init__(self, output: Any) -> None:
        self.output = output
        self.lock = threading.Lock()
        self.state: dict[str, Any] = {"active": False, "paused": False, "status": "stopped", "queue_count": 0, "current_job": None, "submitted_response": None}

    def send_extension(self, value: dict[str, Any]) -> None:
        write_frame(self.output, value, self.lock)

    def public_state(self) -> dict[str, Any]:
        job = self.state.get("current_job") or {}
        return {"active": self.state["active"], "paused": self.state["paused"], "status": self.state["status"], "queue_count": self.state["queue_count"], "job_id": job.get("job_id", ""), "run_id": job.get("run_id", ""), "session_id": job.get("session_id", "")}

    def handle(self, message: dict[str, Any], *, local: bool) -> dict[str, Any]:
        operation = validate_operation(message)
        if operation == "relay_start":
            self.state.update(active=True, paused=False, status="ready")
            return {"status": "ready", **self.public_state()}
        if operation == "relay_pause":
            self.state.update(paused=True, status="paused")
            return {"status": "paused", **self.public_state()}
        if operation == "relay_resume":
            if not self.state["active"]:
                return safe_error("browser_session_not_started")
            self.state.update(paused=False, status="ready")
            return {"status": "ready", **self.public_state()}
        if operation == "relay_stop":
            self.state.update(active=False, paused=False, status="stopped", current_job=None, submitted_response=None)
            return {"status": "stopped", **self.public_state()}
        if operation == "relay_status":
            return {"status": self.state["status"], **self.public_state()}
        if operation == "queue_count":
            return {"status": "ok", "queue_count": self.state["queue_count"]}
        if operation == "job_next":
            job = message.get("job")
            if not local or not isinstance(job, dict):
                return safe_error("local_runner_required")
            if not self.state["active"]:
                return safe_error("browser_session_not_started")
            if self.state["paused"]:
                return safe_error("relay_paused")
            if self.state.get("current_job"):
                return safe_error("one_active_job_required")
            required = ("job_id", "run_id", "session_id", "prompt_text")
            if any(not isinstance(job.get(key), str) or not job[key] for key in required):
                return safe_error("invalid_job")
            self.state.update(current_job=job, submitted_response=None, status="awaiting_user_submission", queue_count=int(message.get("queue_count", 0)))
            self.send_extension({"type": "run_job", "job": job, "queue_count": self.state["queue_count"]})
            return {"status": "awaiting_user_submission", **self.public_state()}
        if operation == "job_get":
            response = self.state.get("submitted_response")
            job = self.state.get("current_job") or {}
            return {"status": "response_ready" if response else self.state["status"], "job": job, "response": response or {}, **self.public_state()}
        if operation == "response_submit":
            if local:
                return safe_error("extension_submission_required")
            job = self.state.get("current_job") or {}
            response = message.get("response_text")
            if not job or message.get("job_id") != job.get("job_id"):
                return safe_error("job_not_active")
            if not isinstance(response, str) or not response.strip() or len(response) > MAX_RESPONSE_CHARS or "\x00" in response:
                return safe_error("invalid_response")
            self.state.update(submitted_response={"job_id": job["job_id"], "response_text": response.replace("\r\n", "\n").strip(), "visible_model_label": str(message.get("visible_model_label", ""))[:120]}, status="response_ready")
            return {"status": "response_ready", **self.public_state()}
        if operation == "job_cancel":
            job = self.state.get("current_job") or {}
            if message.get("job_id") and message.get("job_id") != job.get("job_id"):
                return safe_error("job_not_active")
            self.state.update(current_job=None, submitted_response=None, status="cancelled")
            return {"status": "cancelled", **self.public_state()}
        return safe_error("unsupported_operation")


def serve_socket(host: RelayHost) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(APP_DIR, 0o700)
    try: SOCKET_PATH.unlink()
    except FileNotFoundError: pass
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(SOCKET_PATH)); os.chmod(SOCKET_PATH, 0o600); server.listen(4)
    while True:
        connection, _ = server.accept()
        with connection:
            try:
                data = connection.recv(MAX_MESSAGE_BYTES + 1)
                if len(data) > MAX_MESSAGE_BYTES: raise ValueError("message_too_large")
                response = host.handle(json.loads(data.decode("utf-8")), local=True)
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError): response = safe_error("malformed_message")
            connection.sendall(json.dumps(response, separators=(",", ":")).encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv
    config = load_config()
    if not approved_extension(argv, config):
        print("Mystic Native Messaging host rejected an unapproved extension.", file=sys.stderr)
        return 1
    host = RelayHost(sys.stdout.buffer)
    threading.Thread(target=serve_socket, args=(host,), daemon=True).start()
    while True:
        try:
            message = read_frame(sys.stdin.buffer)
            if message is None: return 0
            response = host.handle(message, local=False)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            response = safe_error(str(error) if str(error) in {"malformed_message", "message_too_large", "unsupported_operation"} else "malformed_message")
        write_frame(sys.stdout.buffer, {"type": "relay_state", "state": response}, host.lock)


if __name__ == "__main__":
    raise SystemExit(main())
