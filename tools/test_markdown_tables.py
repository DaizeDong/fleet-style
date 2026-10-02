"""Regressions for per-cell code and escaped opening delimiters."""

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dash_guard
import make_fixtures


CASES = json.loads(make_fixtures.table_fixture_bytes())


class MarkdownTables(unittest.TestCase):
    def assert_repairs(self, cases):
        for case in cases:
            with self.subTest(case=case["name"]):
                actual, hits = dash_guard.process_text(case["input"], "md")
                self.assertEqual(actual, case["expected"])
                self.assertTrue(hits)
                self.assertEqual(dash_guard.process_text(actual, "md"), (actual, []))

    def test_unmatched_ticks_do_not_cross_cells(self):
        self.assert_repairs(CASES["cross_cells"])

    def test_unmatched_ticks_do_not_cross_rows(self):
        self.assert_repairs(CASES["cross_rows"])

    def test_valid_cell_code_and_escaped_pipes_survive(self):
        self.assert_repairs(CASES["cell_code"])

    def test_tables_within_containers_keep_cell_boundaries(self):
        self.assert_repairs(CASES["contextual"])

    def test_ordinary_pipe_paragraphs_keep_valid_code(self):
        self.assert_repairs(CASES["ordinary"])

    def test_escaping_one_tick_preserves_the_remaining_opening_run(self):
        self.assert_repairs(CASES["escaped_runs"])


if __name__ == "__main__":
    unittest.main()
