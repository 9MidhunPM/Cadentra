#!/usr/bin/env python3
"""Check actual API readiness without presenting it as full workflow verification."""
import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default="http://127.0.0.1:8001")
    args = parser.parse_args()
    url = f"{args.origin.rstrip('/')}/api/v1/health"
    try:
        with urlopen(url, timeout=10) as response:
            payload = json.load(response)
            if response.status != 200:
                raise ValueError("readiness did not return HTTP 200")
    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        print(f"FAIL API readiness: {type(error).__name__}")
        return 1
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        print("FAIL API readiness: missing documented data envelope")
        return 1
    if payload["data"].get("status") not in {"ok", "ready"}:
        print("FAIL API readiness: API did not report ready")
        return 1
    print("PASS API/database readiness only; full browser, billing and email checks are separate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
