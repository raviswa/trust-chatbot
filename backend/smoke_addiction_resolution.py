#!/usr/bin/env python3
"""Run a live API smoke sweep for addiction resolution responses."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


DEFAULT_BASE_URL = "http://127.0.0.1:8000"

ADDICTION_CASES = [
    ("gaming", "I game all night and I get angry when I cannot stop."),
    ("social_media", "I cannot stop scrolling and I compare myself to others every time I post."),
    ("nicotine", "I vape constantly and I reach for it whenever stress hits."),
    ("gambling", "I keep gambling to win back what I lost and the debt is building."),
    ("food", "I binge eat in secret when I feel overwhelmed and ashamed."),
    ("work", "I cannot stop working and I feel guilty whenever I rest."),
    ("shopping", "I shop online when I am stressed and hide the purchases after."),
    ("pornography", "I feel ashamed because I cannot stop watching porn even when I want to."),
]


def _post_json(url: str, payload: dict, timeout: float) -> tuple[int, dict]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def run_sweep(base_url: str, patient_code: str, timeout: float) -> dict:
    suite_id = f"live-addiction-sweep-{int(time.time())}"
    results: dict[str, dict] = {}

    for index, (label, message) in enumerate(ADDICTION_CASES, start=1):
        session_id = f"{suite_id}-{index}"
        payload = {
            "message": message,
            "session_id": session_id,
            "patient_code": patient_code,
        }
        status, response_json = _post_json(f"{base_url}/chat", payload, timeout)
        results[label] = {
            "http_status": status,
            "json": response_json,
        }

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live addiction resolution smoke sweep.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base API URL. Default: http://127.0.0.1:8000")
    parser.add_argument("--patient-code", default="PAT-002", help="Patient code to use for the sweep. Default: PAT-002")
    parser.add_argument("--timeout", type=float, default=30.0, help="Request timeout in seconds. Default: 30")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = parser.parse_args()

    try:
        results = run_sweep(args.base_url.rstrip("/"), args.patient_code, args.timeout)
    except urllib.error.HTTPError as exc:
        sys.stderr.write(f"HTTP error: {exc.code} {exc.reason}\n")
        return 1
    except urllib.error.URLError as exc:
        sys.stderr.write(f"Connection error: {exc.reason}\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"Unexpected error: {exc}\n")
        return 1

    if args.pretty:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(results, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())