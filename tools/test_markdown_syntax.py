"""Literal syntax, table values and physical input ancestors keep their meaning."""

import contextlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dash_guard
import load_budget
import make_fixtures


CASES = json.loads(make_fixtures.syntax_fixture_bytes())


class MarkdownSyntax(unittest.TestCase):
    def test_literal_markup_ticks_cannot_hide_visible_prose(self):
        expected = load_budget.shingles(CASES["shared"])
        for case in CASES["literal"]:
            with self.subTest(text=case["input"]):
                actual, hits = dash_guard.process_text(case["input"], "md")
                self.assertEqual(actual, case["expected"])
                self.assertTrue(hits)
                self.assertTrue(expected <= load_budget.shingles(case["input"]))

    def test_genuine_code_and_literal_syntax_keep_their_bytes(self):
        for text in CASES["protected"]:
            with self.subTest(text=text):
                expected = text.replace("Outside \u2014 prose.", "Outside, prose.")
                actual, hits = dash_guard.process_text(text, "md")
                self.assertEqual(actual, expected)
                self.assertTrue(hits)

    def test_every_recognized_table_layout_preserves_value_semantics(self):
        for case in CASES["tables"]:
            with self.subTest(text=case["input"]):
                actual, hits = dash_guard.process_text(case["input"], "md")
                self.assertEqual(actual, case["expected"])
                self.assertTrue(hits)
                self.assertEqual(dash_guard.process_text(actual, "md"), (actual, []))
                self.assertEqual(load_budget.shingles(case["input"]), set())

    def test_linked_ancestors_are_rejected_before_any_input_read(self):
        with tempfile.TemporaryDirectory(prefix="style-ancestor-") as directory:
            ancestor = Path(directory) / CASES["ancestor_name"]
            root = ancestor / "group" / "sample"
            root.mkdir(parents=True)
            for name in ("SKILL.md", "reference.md"):
                (root / name).write_text(CASES["shared"], encoding="utf-8")
            real_lstat = os.lstat
            for attributes, mode in ((0, stat.S_IFLNK), (1024, stat.S_IFDIR)):
                def alias_info(path, *args, **kwargs):
                    if os.path.normcase(os.fspath(path).rstrip("/\\")) == os.path.normcase(str(ancestor)):
                        return SimpleNamespace(st_mode=mode, st_file_attributes=attributes)
                    return real_lstat(path, *args, **kwargs)

                for scan_all in (False, True):
                    arguments = [str(root.parent), "--scan-all"] if scan_all else [str(root)]
                    output, errors = io.StringIO(), io.StringIO()
                    with self.subTest(attributes=attributes, scan_all=scan_all), \
                            mock.patch.object(load_budget.os, "lstat", side_effect=alias_info), \
                            mock.patch.object(load_budget, "read", wraps=load_budget.read) as reader, \
                            mock.patch.object(sys, "argv", ["load_budget.py", *arguments, "--max-dup", "100", "--json"]), \
                            contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                        status = load_budget.main()
                        self.assertEqual(status, 3)
                        self.assertEqual(output.getvalue(), "")
                        self.assertIn(CASES["ancestor_name"], errors.getvalue())
                        reader.assert_not_called()
            with mock.patch.object(sys, "argv", ["load_budget.py", str(root), "--max-dup", "100", "--json"]), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(load_budget.main(), 0)


if __name__ == "__main__":
    unittest.main()
