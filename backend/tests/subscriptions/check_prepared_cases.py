#!/usr/bin/env python3
"""Check prepared inputs against the planning reference, not application behavior."""

from __future__ import annotations

import json
import runpy
from datetime import date
from pathlib import Path

ASSETS = Path(__file__).resolve().parent
ROOT = ASSETS.parents[2]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    cases = json.loads((ASSETS / "calendar_cases.json").read_text())
    shared = json.loads((ROOT / "contracts/billing-vectors.json").read_text())
    reference = runpy.run_path(str(ROOT / "scripts/check_pack.py"))["boundary"]
    require(cases["schema_version"] == 1, "Unsupported fixture schema")
    ids = [case["id"] for group in ("boundary_cases", "period_cases") for case in cases[group]]
    require(len(ids) == len(set(ids)), "Duplicate case IDs")
    require(bool(cases["boundary_cases"]) and bool(cases["period_cases"]), "Missing fixture cases")

    for case in cases["boundary_cases"]:
        require(case["test_id"] == "T09", f"Wrong acceptance ID: {case['id']}")
        indices = case["indices"]
        require(bool(indices) and all(type(i) is int and i >= 0 for i in indices),
                f"Invalid indices: {case['id']}")
        require(indices == sorted(set(indices)), f"Repeated or unordered indices: {case['id']}")
        anchor = date.fromisoformat(case["anchor"])
        expected = [date.fromisoformat(value) for value in case["expected"]]
        require(expected == [reference(anchor, case["cadence"], i) for i in indices],
                f"Calendar reference mismatch: {case['id']}")

    for canonical in shared["cadence_cases"]:
        keys = ("anchor", "cadence", "indices", "expected")
        require(any(all(case[key] == canonical[key] for key in keys)
                    for case in cases["boundary_cases"]),
                f"Missing unchanged canonical case: {canonical['cadence']}")

    for case in cases["period_cases"]:
        require(case["test_id"] == "T09", f"Wrong acceptance ID: {case['id']}")
        index = case["cycle_index"]
        require(type(index) is int and index >= 0, f"Invalid cycle index: {case['id']}")
        anchor = date.fromisoformat(case["anchor"])
        expiry = date.fromisoformat(case["end_date"])
        close = date.fromisoformat(case["close_effective_on"]) if case["close_effective_on"] else expiry
        start = reference(anchor, case["cadence"], index)
        end = min(reference(anchor, case["cadence"], index + 1), expiry, close)
        require(anchor < expiry and start < end, f"Ineligible period: {case['id']}")
        require((start.isoformat(), end.isoformat()) == (case["expected_start"], case["expected_end"]),
                f"Period reference mismatch: {case['id']}")

    print(f"PASS prepared calendar assets: {len(cases['boundary_cases'])} boundary cases, "
          f"{len(cases['period_cases'])} period cases; canonical fixtures retained")
    print("Planning-reference comparison only. No application or lifecycle scenarios were executed.")


if __name__ == "__main__":
    main()
