"""Tests for doc-expiry-doctor. Run with: python3 -m unittest discover -s tests -v"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from doc_expiry_doctor import (  # noqa: E402
    apply_filters,
    classify,
    days_until,
    load_documents,
    main,
    normalize_record,
    parse_date,
    sort_records,
)

TODAY = date(2026, 11, 2)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "doc_expiry_doctor.py")
SAMPLE = os.path.join(ROOT, "examples", "documents.json")
BAD_SAMPLE = os.path.join(ROOT, "examples", "bad-documents.json")


def record(holder, doc_type, expiry, reminder_days=None):
    item = {"holder": holder, "type": doc_type, "expiry": expiry}
    if reminder_days is not None:
        item["reminder_days"] = reminder_days
    return item


class TestParseDate(unittest.TestCase):
    def test_valid_iso_date(self):
        self.assertEqual(parse_date("2026-11-20"), date(2026, 11, 20))

    def test_rejects_impossible_date(self):
        with self.assertRaises(ValueError):
            parse_date("2026-02-30")

    def test_rejects_wrong_format(self):
        for bad in ("20 Nov 2026", "11/20/2026", "2026-11-2", "2026/11/20"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    parse_date(bad)

    def test_rejects_non_string(self):
        for bad in (20261120, None, ["2026-11-20"]):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    parse_date(bad)


class TestNormalizeRecord(unittest.TestCase):
    def test_valid_record(self):
        item, error = normalize_record(record("Maria Lopez", "CDL", "2026-11-20"), 0)
        self.assertIsNone(error)
        self.assertEqual(item["holder"], "Maria Lopez")
        self.assertEqual(item["type"], "CDL")
        self.assertEqual(item["expiry"], "2026-11-20")
        self.assertIsNone(item["reminder_days"])

    def test_alias_fields(self):
        raw = {
            "holder": "Sam Ortiz",
            "document_type": "CDL",
            "expiry_date": "2026-12-20",
        }
        item, error = normalize_record(raw, 0)
        self.assertIsNone(error)
        self.assertEqual(item["type"], "CDL")
        self.assertEqual(item["expiry"], "2026-12-20")

    def test_missing_holder(self):
        _item, error = normalize_record({"type": "CDL", "expiry": "2026-11-20"}, 0)
        self.assertIn("holder", error)

    def test_missing_type(self):
        _item, error = normalize_record(
            {"holder": "Maria Lopez", "expiry": "2026-11-20"}, 1
        )
        self.assertIn("type", error)

    def test_missing_expiry(self):
        _item, error = normalize_record(
            {"holder": "Maria Lopez", "type": "CDL"}, 2
        )
        self.assertIn("expiry", error)

    def test_bad_expiry_date(self):
        _item, error = normalize_record(
            record("Maria Lopez", "CDL", "2026-02-30"), 0
        )
        self.assertIn("expiry", error)

    def test_blank_holder_rejected(self):
        _item, error = normalize_record(record("   ", "CDL", "2026-11-20"), 0)
        self.assertIn("holder", error)

    def test_negative_reminder_rejected(self):
        _item, error = normalize_record(
            record("Maria Lopez", "CDL", "2026-11-20", reminder_days=-5), 0
        )
        self.assertIn("reminder_days", error)

    def test_non_integer_reminder_rejected(self):
        for bad in ("30", 2.5, True):
            with self.subTest(bad=bad):
                _item, error = normalize_record(
                    record("Maria Lopez", "CDL", "2026-11-20", reminder_days=bad),
                    0,
                )
                self.assertIn("reminder_days", error)

    def test_non_object_record_rejected(self):
        _item, error = normalize_record("not a record", 0)
        self.assertIsNotNone(error)


class TestLoadDocuments(unittest.TestCase):
    def _write(self, directory, data, name="docs.json"):
        path = os.path.join(directory, name)
        with open(path, "w", encoding="utf-8") as handle:
            if isinstance(data, str):
                handle.write(data)
            else:
                json.dump(data, handle)
        return path

    def test_loads_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp, [record("Maria Lopez", "CDL", "2026-11-20")]
            )
            records, errors = load_documents(path)
            self.assertEqual(errors, [])
            self.assertEqual(len(records), 1)

    def test_loads_documents_wrapper(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp,
                {"documents": [record("Maria Lopez", "CDL", "2026-11-20")]},
            )
            records, errors = load_documents(path)
            self.assertEqual(errors, [])
            self.assertEqual(len(records), 1)

    def test_collects_bad_records_and_keeps_good_ones(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp,
                [
                    record("Maria Lopez", "CDL", "2026-11-20"),
                    record("James Carter", "CDL", "2026-02-30"),
                ],
            )
            records, errors = load_documents(path)
            self.assertEqual(len(records), 1)
            self.assertEqual(len(errors), 1)

    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "{not json")
            with self.assertRaises(ValueError):
                load_documents(path)

    def test_missing_file_raises(self):
        with self.assertRaises(ValueError):
            load_documents(os.path.join(tempfile.gettempdir(), "no-such-doc-expiry-file.json"))

    def test_sample_file_is_valid(self):
        records, errors = load_documents(SAMPLE)
        self.assertEqual(errors, [])
        self.assertEqual(len(records), 7)

    def test_bad_sample_has_three_errors(self):
        records, errors = load_documents(BAD_SAMPLE)
        self.assertEqual(len(records), 1)
        self.assertEqual(len(errors), 3)


class TestClassify(unittest.TestCase):
    def test_expired(self):
        status, days = classify(record("A", "CDL", "2026-10-15"), TODAY, 30)
        self.assertEqual(status, "expired")
        self.assertEqual(days, -18)

    def test_expires_today_is_expiring_soon(self):
        status, days = classify(record("A", "CDL", "2026-11-02"), TODAY, 30)
        self.assertEqual((status, days), ("expiring_soon", 0))

    def test_window_boundary_is_inclusive(self):
        status, _days = classify(record("A", "CDL", "2026-12-02"), TODAY, 30)
        self.assertEqual(status, "expiring_soon")

    def test_one_day_past_window_is_later(self):
        status, _days = classify(record("A", "CDL", "2026-12-03"), TODAY, 30)
        self.assertEqual(status, "later")

    def test_reminder_days_overrides_window(self):
        item = record("A", "CDL", "2026-12-20", reminder_days=60)
        status, days = classify(item, TODAY, 30)
        self.assertEqual((status, days), ("expiring_soon", 48))

    def test_days_until(self):
        self.assertEqual(
            days_until(record("A", "CDL", "2026-11-20"), TODAY), 18
        )


class TestFiltersAndSorting(unittest.TestCase):
    def setUp(self):
        self.items = [
            record("Maria Lopez", "CDL", "2026-11-20"),
            record("Maria Lopez", "Medical card", "2026-12-15"),
            record("James Carter", "CDL", "2026-10-15"),
        ]

    def test_type_filter_case_insensitive(self):
        result = apply_filters(self.items, ["cdl"], [])
        self.assertEqual(len(result), 2)

    def test_holder_filter_is_substring(self):
        result = apply_filters(self.items, [], ["maria"])
        self.assertEqual(len(result), 2)

    def test_filters_combine(self):
        result = apply_filters(self.items, ["CDL"], ["maria"])
        self.assertEqual(len(result), 1)

    def test_sort_by_expiry_then_holder(self):
        ordered = sort_records(self.items)
        self.assertEqual(
            [r["expiry"] for r in ordered],
            ["2026-10-15", "2026-11-20", "2026-12-15"],
        )


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, CLI, *args],
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_default_within_30(self):
        proc = self.run_cli(SAMPLE, "--today", "2026-11-02")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Already expired (1):", proc.stdout)
        self.assertIn("James Carter", proc.stdout)
        self.assertIn("Expiring within 30 days (3):", proc.stdout)
        self.assertIn("Maria Lopez", proc.stdout)
        self.assertIn("Sam Ortiz", proc.stdout)
        self.assertNotIn("2027-03-01", proc.stdout)

    def test_within_60_adds_medical_card(self):
        proc = self.run_cli(SAMPLE, "--today", "2026-11-02", "--within", "60")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Expiring within 60 days (4):", proc.stdout)
        self.assertIn("Medical card", proc.stdout)

    def test_within_90_adds_insurance(self):
        proc = self.run_cli(SAMPLE, "--today", "2026-11-02", "--within", "90")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Expiring within 90 days (5):", proc.stdout)
        self.assertIn("Insurance", proc.stdout)

    def test_all_lists_everything_sorted(self):
        proc = self.run_cli(SAMPLE, "--today", "2026-11-02", "--all")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("All documents, sorted by expiry (7):", proc.stdout)
        self.assertIn("2027-03-01", proc.stdout)
        first = proc.stdout.index("2026-10-15")
        last = proc.stdout.index("2027-03-01")
        self.assertLess(first, last)

    def test_expired_only(self):
        proc = self.run_cli(SAMPLE, "--today", "2026-11-02", "--expired")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Already expired (1):", proc.stdout)
        self.assertNotIn("Expiring within", proc.stdout)

    def test_json_output(self):
        proc = self.run_cli(SAMPLE, "--today", "2026-11-02", "--json")
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["today"], "2026-11-02")
        self.assertEqual(payload["within_days"], 30)
        self.assertEqual(payload["counts"]["expired"], 1)
        self.assertEqual(payload["counts"]["expiring_soon"], 3)
        self.assertEqual(payload["counts"]["later"], 3)
        self.assertEqual(payload["counts"]["total"], 7)
        self.assertEqual(len(payload["records"]), 4)

    def test_type_filter(self):
        proc = self.run_cli(
            SAMPLE, "--today", "2026-11-02", "--all", "--type", "CDL"
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("All documents, sorted by expiry (3):", proc.stdout)
        self.assertNotIn("Medical card", proc.stdout)

    def test_holder_filter(self):
        proc = self.run_cli(
            SAMPLE, "--today", "2026-11-02", "--all", "--holder", "priya"
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("All documents, sorted by expiry (2):", proc.stdout)
        self.assertNotIn("Maria Lopez", proc.stdout)

    def test_check_valid_file(self):
        proc = self.run_cli(SAMPLE, "--check")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("OK: 7 valid record(s)", proc.stdout)

    def test_check_bad_file_exits_nonzero(self):
        proc = self.run_cli(BAD_SAMPLE, "--check")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("ERRORS (3):", proc.stdout)

    def test_default_mode_rejects_bad_file(self):
        proc = self.run_cli(BAD_SAMPLE, "--today", "2026-11-02")
        self.assertEqual(proc.returncode, 2)

    def test_missing_file_exits_2(self):
        proc = self.run_cli("no-such-file.json")
        self.assertEqual(proc.returncode, 2)

    def test_main_returns_zero_for_sample(self):
        self.assertEqual(main([SAMPLE, "--today", "2026-11-02"]), 0)


class TestNoEmDash(unittest.TestCase):
    def test_no_em_dash_in_repo_text(self):
        for dirpath, _dirnames, filenames in os.walk(ROOT):
            if "__pycache__" in dirpath or ".git" in dirpath:
                continue
            for name in filenames:
                if name.endswith((".py", ".md", ".json", ".toml")):
                    path = os.path.join(dirpath, name)
                    with open(path, encoding="utf-8") as handle:
                        self.assertNotIn(
                            "\u2014", handle.read(), "em dash found in %s" % path
                        )


if __name__ == "__main__":
    unittest.main()
