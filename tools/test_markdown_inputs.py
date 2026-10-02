"""Prose must remain visible outside actual Markdown code and table blocks."""

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dash_guard
import load_budget
import make_fixtures


CASES = json.loads(make_fixtures.input_fixture_bytes())


class MarkdownInputs(unittest.TestCase):
    def test_pipe_prose_remains_measurable(self):
        expected = load_budget.shingles(CASES["shared"])
        self.assertTrue(expected)
        for text in CASES["ordinary"]:
            with self.subTest(text=text):
                self.assertTrue(expected <= load_budget.shingles(text))

    def test_complete_tables_are_excluded_with_or_without_outer_pipes(self):
        for text in CASES["tables"]:
            with self.subTest(text=text):
                self.assertEqual(load_budget.shingles(text), set())
                self.assertEqual(load_budget.shingles(text + "\n" + CASES["shared"]),
                                 load_budget.shingles(CASES["shared"]))

    def test_html_backticks_do_not_hide_prose(self):
        expected = load_budget.shingles(CASES["shared"])
        for case in CASES["html"]:
            with self.subTest(text=case["input"]):
                actual, hits = dash_guard.process_text(case["input"], "md")
                self.assertEqual(actual, case["expected"])
                self.assertTrue(hits)
                self.assertEqual(dash_guard.process_text(actual, "md"), (actual, []))
                self.assertTrue(expected <= load_budget.shingles(case["input"]))

    def test_markdown_inline_parsing_resumes_after_html(self):
        for text in CASES["after_html"]:
            with self.subTest(text=text):
                expected = text.replace("Outside \u2014 prose.", "Outside, prose.")
                self.assertEqual(dash_guard.process_text(text, "md")[0], expected)

    def test_html_inside_real_code_remains_protected(self):
        for text in CASES["code"]:
            with self.subTest(text=text):
                self.assertEqual(dash_guard.process_text(text, "md"), (text, []))
                self.assertEqual(load_budget.shingles(text), set())


if __name__ == "__main__":
    unittest.main()
