#!/usr/bin/env python3
"""Read the DeepSeek API balance; never copy or expose credentials."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request


class UsageError(Exception):
    pass


def api_key():
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    # dsh keeps the key in its credentials store; read it in place.
    try:
        text = (Path.home() / ".dsh/.credentials.yaml").read_text()
    except OSError:
        text = ""
    match = re.search(r"^\s*DEEPSEEK_API_KEY:\s*[\"']?([^\s\"']+)", text, re.M)
    if not match:
        raise UsageError("No DeepSeek API key. Log in with dsh or set DEEPSEEK_API_KEY.")
    return match.group(1)


def fetch_usage():
    request = urllib.request.Request("https://api.deepseek.com/user/balance", headers={
        "Authorization": "Bearer " + api_key(), "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise UsageError("DeepSeek rejected the API key.")
        raise UsageError(f"DeepSeek API error ({exc.code}). Will retry automatically.")
    balances = []
    for info in result.get("balance_infos") or []:
        try:
            balances.append({"currency": str(info.get("currency") or ""),
                             "total": float(info.get("total_balance")),
                             "granted": float(info.get("granted_balance") or 0),
                             "toppedUp": float(info.get("topped_up_balance") or 0)})
        except (TypeError, ValueError):
            continue
    if not balances:
        raise UsageError("DeepSeek returned no balance information.")
    return {"balances": balances, "available": bool(result.get("is_available")),
            "timestamp": time.time(), "error": ""}


def track_spend(data, cache):
    # The API has no usage endpoint, so today's spend is the drop since the
    # first reading of the day; a top-up resets the baseline.
    today = time.strftime("%Y-%m-%d")
    previous = cache.get("dayStart") if cache.get("day") == today else None
    starts = {}
    for balance in data["balances"]:
        start = (previous or {}).get(balance["currency"])
        if not isinstance(start, (int, float)) or balance["total"] > start:
            start = balance["total"]
        starts[balance["currency"]] = start
        balance["spentToday"] = round(start - balance["total"], 4)
    data["day"] = today
    data["dayStart"] = starts


def cached_usage(max_age):
    directory = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "plasma-deepseek-usage"
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
            track_spend(data, cache)
        except (UsageError, OSError, ValueError) as exc:
            data = cache if 0 <= time.time() - cache.get("timestamp", 0) < 86400 else {}
            data["error"] = str(exc) if isinstance(exc, UsageError) else "Could not read DeepSeek balance. Will retry automatically."
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
        data = {"error": "Could not access the DeepSeek usage cache."}
    print(json.dumps(data))


if __name__ == "__main__":
    main()
