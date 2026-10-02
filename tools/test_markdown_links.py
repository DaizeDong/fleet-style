"""Reference definitions and link nesting preserve rendered prose and real code."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dash_guard
import load_budget
import make_fixtures


CASES = json.loads(make_fixtures.link_fixture_bytes())


class MarkdownLinks(unittest.TestCase):
    def test_reference_syntax_cannot_hide_the_following_paragraph(self):
        shared = load_budget.shingles(CASES['shared'])
        for case in CASES['visible']:
            with self.subTest(text=case['input']):
                actual, hits = dash_guard.process_text(case['input'], 'md')
                self.assertEqual(actual, case['expected'])
                self.assertTrue(hits)
                if CASES['shared'] in case['input']:
                    self.assertTrue(shared <= load_budget.shingles(case['input']))

    def test_completed_inner_links_disable_outer_link_openers(self):
        shared = load_budget.shingles(CASES['shared'])
        for source in CASES['protected']:
            with self.subTest(text=source):
                self.assertEqual(dash_guard.process_text(source, 'md'), (source, []))
                self.assertFalse(shared & load_budget.shingles(source))

    def test_invalid_definitions_keep_actual_inline_code(self):
        shared = load_budget.shingles(CASES['shared'])
        for source in CASES['invalid']:
            with self.subTest(text=source):
                self.assertEqual(dash_guard.process_text(source, 'md'), (source, []))
                self.assertFalse(shared & load_budget.shingles(source))


if __name__ == '__main__':
    unittest.main()
