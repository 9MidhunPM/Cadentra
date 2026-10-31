"""Exercise the subscription calendar seam with independent expected dates."""

import json
import unittest
from dataclasses import FrozenInstanceError
from datetime import date, datetime
from pathlib import Path

from app.modules.subscriptions.calendar import CycleSnapshot, get_cycle_bounds

CASES = json.loads(Path(__file__).with_name("calendar_cases.json").read_text())
CADENCES = ("DAILY", "WEEKLY", "MONTHLY", "YEARLY")


class CycleBoundsTests(unittest.TestCase):
    def test_all_golden_boundaries_keep_the_original_anchor(self):
        for case in CASES["boundary_cases"]:
            snapshot = CycleSnapshot(
                start_date=date.fromisoformat(case["anchor"]),
                end_date=date(2100, 1, 1),
                cadence=case["cadence"],
            )
            for index, expected in zip(case["indices"], case["expected"], strict=True):
                with self.subTest(case=case["id"], index=index):
                    bounds = get_cycle_bounds(snapshot, index)
                    self.assertIsNotNone(bounds)
                    self.assertEqual(bounds[0], date.fromisoformat(expected))
                    self.assertLess(bounds[0], bounds[1])
                    self.assertEqual(snapshot.start_date.isoformat(), case["anchor"])

    def test_golden_periods_apply_exclusive_expiry_and_close_caps(self):
        for case in CASES["period_cases"]:
            with self.subTest(case=case["id"]):
                snapshot = CycleSnapshot(
                    start_date=date.fromisoformat(case["anchor"]),
                    end_date=date.fromisoformat(case["end_date"]),
                    cadence=case["cadence"],
                    close_effective_on=(
                        date.fromisoformat(case["close_effective_on"])
                        if case["close_effective_on"]
                        else None
                    ),
                )
                self.assertEqual(
                    get_cycle_bounds(snapshot, case["cycle_index"]),
                    (
                        date.fromisoformat(case["expected_start"]),
                        date.fromisoformat(case["expected_end"]),
                    ),
                )

    def test_invalid_cycle_indices_raise_value_error(self):
        snapshot = CycleSnapshot(date(2027, 1, 31), date(2028, 1, 1), "MONTHLY")
        for index in (-1, True, False, 1.0, "1", None):
            with self.subTest(index=index), self.assertRaises(ValueError):
                get_cycle_bounds(snapshot, index)

    def test_unsupported_cadence_is_rejected_even_for_an_exhausted_index(self):
        for cadence in ("monthly", "FORTNIGHTLY", "", None):
            with self.subTest(cadence=cadence), self.assertRaises(ValueError):
                snapshot = CycleSnapshot(date(2027, 1, 1), date(2028, 1, 1), cadence)
                get_cycle_bounds(snapshot, 10**40)

    def test_invalid_snapshot_dates_are_rejected(self):
        valid = {"start_date": date(2027, 1, 1), "end_date": date(2028, 1, 1), "cadence": "DAILY"}
        invalid_fields = (
            {"start_date": "2027-01-01"},
            {"start_date": None},
            {"start_date": datetime(2027, 1, 1)},
            {"end_date": "2028-01-01"},
            {"end_date": None},
            {"end_date": datetime(2028, 1, 1)},
            {"end_date": date(2027, 1, 1)},
            {"end_date": date(2026, 12, 31)},
            {"close_effective_on": "2027-02-01"},
            {"close_effective_on": datetime(2027, 2, 1)},
            {"close_effective_on": date(2026, 12, 31)},
        )
        for changes in invalid_fields:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                get_cycle_bounds(CycleSnapshot(**(valid | changes)), 0)

    def test_a_cycle_starting_at_expiry_or_closure_does_not_exist(self):
        for close in (None, date(2027, 2, 28)):
            with self.subTest(close=close):
                snapshot = CycleSnapshot(date(2027, 1, 31), date(2027, 2, 28), "MONTHLY", close)
                self.assertEqual(
                    get_cycle_bounds(snapshot, 0), (date(2027, 1, 31), date(2027, 2, 28))
                )
                self.assertIsNone(get_cycle_bounds(snapshot, 1))
        closed_at_start = CycleSnapshot(
            date(2027, 1, 31), date(2028, 1, 1), "MONTHLY", date(2027, 1, 31)
        )
        self.assertIsNone(get_cycle_bounds(closed_at_start, 0))

    def test_early_close_caps_service_before_original_expiry(self):
        snapshot = CycleSnapshot(date(2027, 1, 31), date(2027, 8, 1), "MONTHLY", date(2027, 3, 31))
        self.assertEqual(get_cycle_bounds(snapshot, 1), (date(2027, 2, 28), date(2027, 3, 31)))
        self.assertIsNone(get_cycle_bounds(snapshot, 2))

    def test_arbitrarily_large_valid_indices_are_exhausted_without_overflow(self):
        for cadence in CADENCES:
            with self.subTest(cadence=cadence):
                snapshot = CycleSnapshot(date(2027, 1, 31), date(2100, 1, 1), cadence)
                self.assertIsNone(get_cycle_bounds(snapshot, 10**40))

    def test_periods_at_the_date_limit_cap_without_overflow(self):
        for cadence in CADENCES:
            with self.subTest(cadence=cadence):
                snapshot = CycleSnapshot(date(9999, 12, 30), date.max, cadence)
                self.assertEqual(get_cycle_bounds(snapshot, 0), (date(9999, 12, 30), date.max))
                self.assertIsNone(get_cycle_bounds(snapshot, 1))

    def test_snapshot_is_frozen_and_repeated_queries_do_not_mutate_it(self):
        snapshot = CycleSnapshot(date(2027, 1, 31), date(2028, 1, 1), "MONTHLY")
        before = (
            snapshot.start_date,
            snapshot.end_date,
            snapshot.cadence,
            snapshot.close_effective_on,
        )
        first = get_cycle_bounds(snapshot, 1)
        get_cycle_bounds(snapshot, 2)
        self.assertEqual(get_cycle_bounds(snapshot, 1), first)
        self.assertEqual(
            (snapshot.start_date, snapshot.end_date, snapshot.cadence, snapshot.close_effective_on),
            before,
        )
        with self.assertRaises(FrozenInstanceError):
            snapshot.start_date = date(2027, 2, 28)


if __name__ == "__main__":
    unittest.main()
