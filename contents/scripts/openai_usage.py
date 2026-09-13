#!/usr/bin/env python3
"""Read Codex quotas via its app-server; never copy or expose credentials."""
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import time


class UsageError(Exception):
    pass


def normalize(result):
    buckets = result.get("rateLimitsByLimitId") or {}
    quota = buckets.get("codex") or result.get("rateLimits") or {}
    windows = []
    for key, fallback in (("primary", "Primary"), ("secondary", "Secondary")):
        window = quota.get(key)
        if not isinstance(window, dict):
            continue
        percent = window.get("usedPercent")
        if isinstance(percent, bool) or not isinstance(percent, (int, float)) or not math.isfinite(percent):
            continue
        minutes = window.get("windowDurationMins")
        label = fallback
        if isinstance(minutes, (int, float)) and minutes > 0:
            if minutes % 1440 == 0:
                label = f"{minutes / 1440:g}d"
            elif minutes % 60 == 0:
                label = f"{minutes / 60:g}h"
            else:
                label = f"{minutes:g}m"
        reset = window.get("resetsAt")
        if not isinstance(reset, (int, float)) or not math.isfinite(reset) or reset <= 0:
            reset = None
        windows.append({"label": label, "usedPercent": max(0, min(100, percent)), "resetsAt": reset})
    if not windows:
        raise UsageError("No Codex usage limits available. Check your Codex login.")
    return {"windows": windows, "plan": quota.get("planType") or "", "timestamp": time.time(), "error": ""}


def fetch_usage():
    codex = shutil.which("codex")
    if not codex:
        candidate = Path.home() / ".local/bin/codex"
        if candidate.is_file():
            codex = str(candidate)
    if not codex:
        raise UsageError("Install Codex CLI and run 'codex login'.")
    # No threads or model turns are created by these account-only requests.
    with subprocess.Popen([codex, "app-server"], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0) as process:
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        pending = bytearray()
        deadline = time.monotonic() + 30

        def send(message):
            process.stdin.write((json.dumps(message) + "\n").encode())
            process.stdin.flush()

        def receive(request_id):
            while time.monotonic() < deadline:
                if b"\n" not in pending:
                    if not selector.select(max(0, deadline - time.monotonic())):
                        break
                    chunk = os.read(process.stdout.fileno(), 65536)
                    if not chunk:
                        raise UsageError("Codex could not start. Check your Codex CLI login and configuration.")
                    pending.extend(chunk)
                    continue
                line, _, tail = pending.partition(b"\n")
                pending[:] = tail
                message = json.loads(line)
                if message.get("id") != request_id:
                    continue
                if "error" in message:
                    # Do not forward server diagnostics, which may contain account details.
                    raise UsageError("Unable to read Codex usage. Check your connection and run 'codex login' if needed.")
                return message.get("result") or {}
            raise UsageError("OpenAI usage request timed out. Will retry automatically.")

        try:
            send({"id": 1, "method": "initialize", "params": {
                "clientInfo": {"name": "plasma_usage_widget", "version": "1.0.0"}}})
            receive(1)
            send({"method": "initialized"})
            send({"id": 2, "method": "account/rateLimits/read"})
            return normalize(receive(2))
        finally:
            selector.close()
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def cached_usage(max_age):
    directory = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "plasma-openai-usage"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    cache_path = directory / "usage.json"
    # Multiple panel instances share one request and never race cache writes.
    with (directory / "usage.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            cache = json.loads(cache_path.read_text())
            if not isinstance(cache, dict):
                cache = {}
        except (OSError, ValueError):
            cache = {}
        age = time.time() - cache.get("checkedAt", 0)
        if 0 <= age < max_age:
            return cache
        try:
            data = fetch_usage()
        except (UsageError, OSError, ValueError) as exc:
            data = cache if 0 <= time.time() - cache.get("timestamp", 0) < 86400 else {}
            data["error"] = str(exc) if isinstance(exc, UsageError) else "Could not read OpenAI usage. Will retry automatically."
        data["checkedAt"] = time.time()
        temporary = cache_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data))
        temporary.chmod(0o600)
        temporary.replace(cache_path)
        return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-age", type=int, default=300)
    args = parser.parse_args()
    try:
        data = cached_usage(max(55, args.max_age))
    except OSError:
        data = {"error": "Could not access the OpenAI usage cache."}
    print(json.dumps(data))


if __name__ == "__main__":
    main()
