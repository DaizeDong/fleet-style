"""Unreadable inputs and invalid limits cannot yield a partial success report."""

import contextlib
import errno
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import load_budget
import make_fixtures


CASES = json.loads(make_fixtures.input_fixture_bytes())


class LoadBudgetInputs(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="style-input-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.skill = self.root / "SKILL.md"
        self.skill.write_text(CASES["shared"], encoding="utf-8")
        self.reference = self.root / "reference.md"
        self.reference.write_text(CASES["shared"], encoding="utf-8")

    def run_cli(self, *arguments):
        output, errors = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", ["load_budget.py", str(self.root), *arguments]), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                status = load_budget.main()
            except SystemExit as error:
                status = error.code
        return status, output.getvalue(), errors.getvalue()

    def assert_incomplete(self, result, name):
        status, output, errors = result
        self.assertNotEqual(status, 0)
        self.assertNotIn('"measured": true', output)
        self.assertNotIn('"dup_checked": true', output)
        self.assertIn(name, errors)

    def test_nonfinite_and_out_of_range_thresholds_are_usage_errors(self):
        for value in CASES["invalid_thresholds"]:
            with self.subTest(value=value):
                status, output, errors = self.run_cli("--max-dup=" + value, "--json")
                self.assertEqual(status, 2)
                self.assertEqual(output, "")
                self.assertIn("--max-dup", errors)

    def test_valid_threshold_endpoints_keep_their_meaning(self):
        for limit, expected in (("0", 1), ("2.0", 1), ("100.0", 0)):
            with self.subTest(limit=limit):
                status, output, errors = self.run_cli("--max-dup", limit, "--json")
                self.assertEqual(status, expected)
                self.assertEqual(errors, "")
                self.assertEqual(json.loads(output)[0]["dup_pct"], 100.0)

    def test_invalid_utf8_in_either_input_stops_the_measurement(self):
        for path in (self.skill, self.reference):
            with self.subTest(path=path.name):
                original = path.read_bytes()
                path.write_bytes(bytes.fromhex(CASES["invalid_utf8_hex"]))
                try:
                    self.assert_incomplete(self.run_cli("--max-dup", "100", "--json"), path.name)
                finally:
                    path.write_bytes(original)

    def deny_scandir(self, blocked):
        scan = os.scandir

        def denied(path):
            if os.path.normcase(os.path.abspath(path)) == os.path.normcase(str(blocked)):
                raise PermissionError(errno.EACCES, "synthetic denied directory", str(blocked))
            return scan(path)

        return mock.patch.object(load_budget.os, "scandir", side_effect=denied)

    def test_reference_discovery_failure_cannot_report_partial_coverage(self):
        blocked = self.root / "reference-private"
        blocked.mkdir()
        (blocked / "detail.md").write_text(CASES["shared"], encoding="utf-8")
        with self.deny_scandir(blocked):
            self.assert_incomplete(self.run_cli("--max-dup", "100", "--json"), blocked.name)

    def test_reference_read_errors_cannot_report_partial_coverage(self):
        real_open = open
        for error_type in (PermissionError, FileNotFoundError):
            def fail_reference(path, *args, **kwargs):
                if os.path.abspath(path) == str(self.reference):
                    raise error_type(errno.EACCES, "synthetic unreadable input", str(path))
                return real_open(path, *args, **kwargs)

            with self.subTest(error=error_type.__name__), mock.patch("builtins.open", side_effect=fail_reference):
                self.assert_incomplete(self.run_cli("--max-dup", "100", "--json"), self.reference.name)

    def test_skill_discovery_failure_cannot_omit_a_second_skill(self):
        blocked = self.root / "skills"
        (blocked / "sample").mkdir(parents=True)
        (blocked / "sample" / "SKILL.md").write_text(CASES["shared"], encoding="utf-8")
        with self.deny_scandir(blocked):
            self.assert_incomplete(self.run_cli("--max-dup", "100", "--json"), blocked.name)

    def test_submodule_is_pruned_before_traversal(self):
        blocked = self.root / "vendor" / "kit"
        blocked.mkdir(parents=True)
        (blocked / ".git").write_text(CASES["marker"], encoding="utf-8")
        (blocked / "detail.md").write_text(CASES["shared"], encoding="utf-8")
        with self.deny_scandir(blocked):
            status, output, errors = self.run_cli("--max-dup", "100", "--json")
        self.assertEqual(status, 0)
        self.assertEqual(errors, "")
        self.assertEqual(json.loads(output)[0]["ref_count"], 1)


if __name__ == "__main__":
    unittest.main()
