"""Regression contracts for paragraphs and Markdown container scope."""

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dash_guard
import load_budget
import make_fixtures


CASES = json.loads(make_fixtures.block_fixture_bytes())


class MarkdownBlocks(unittest.TestCase):
    def assert_repairs(self, cases):
        for case in cases:
            with self.subTest(case=case["name"]):
                actual, hits = dash_guard.process_text(case["input"], "md")
                self.assertEqual(actual, case["expected"])
                self.assertTrue(hits)
                self.assertEqual(dash_guard.process_text(actual, "md"), (actual, []))

    def test_paragraph_breaks_end_unmatched_inline_spans(self):
        self.assert_repairs(CASES["paragraphs"])

    def test_new_blocks_end_unmatched_inline_spans(self):
        self.assert_repairs(CASES["block_starts"])

    def test_container_fences_preserve_code_and_release_outside_prose(self):
        self.assert_repairs(CASES["fences"])

    def test_unclosed_fences_end_at_their_container_boundary(self):
        self.assert_repairs(CASES["unclosed"])

    def test_multiline_inline_code_survives_in_one_paragraph(self):
        self.assert_repairs(CASES["multiline"])

    def test_container_code_is_not_prose(self):
        for block in CASES["code_blocks"]:
            with self.subTest(block=block.splitlines()[0]):
                self.assertEqual(load_budget.shingles(block), set())

    def test_duplicate_prose_is_measured_between_unmatched_ticks(self):
        expected = load_budget.shingles(CASES["shared_prose"])
        self.assertTrue(expected)
        for text in CASES["duplicate_prose"]:
            with self.subTest(text=text):
                self.assertTrue(expected <= load_budget.shingles(text))


if __name__ == "__main__":
    unittest.main()
