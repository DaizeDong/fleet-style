"""Rendered link labels and visible rejected-link tails remain measurable prose."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import load_budget
import make_fixtures
import markdown_regions


CASES = json.loads(make_fixtures.prose_fixture_bytes())


class LoadBudgetProse(unittest.TestCase):
    def test_rejected_links_keep_their_visible_tail_words(self):
        for source in CASES['visible']:
            with self.subTest(source=source):
                self.assertIn(CASES['shared'], load_budget.shingles(source))

    def test_inline_reference_and_image_labels_match_plain_words(self):
        for source in CASES['labels']:
            with self.subTest(source=source):
                self.assertEqual(load_budget.shingles(source), {CASES['shared']})

    def test_recognized_metadata_and_code_do_not_become_prose(self):
        for source in CASES['protected']:
            with self.subTest(source=source):
                self.assertNotIn(CASES['shared'], load_budget.shingles(source))

    def test_normalization_keeps_literal_brackets_and_word_adjacency(self):
        for case in CASES['spelling']:
            with self.subTest(source=case['input']):
                self.assertEqual(markdown_regions.without_code(case['input']).split(),
                                 case['expected'].split())

    def budget(self, source):
        with tempfile.TemporaryDirectory(prefix='style-prose-') as directory:
            root = Path(directory)
            (root / 'SKILL.md').write_text(CASES['filler'] + '\n\n' + source, encoding='utf-8')
            (root / 'reference.md').write_text(CASES['shared'], encoding='utf-8')
            output, errors = io.StringIO(), io.StringIO()
            old_argv = sys.argv
            try:
                sys.argv = ['load_budget.py', str(root), '--json', '--max-dup=0']
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                    status = load_budget.main()
            finally:
                sys.argv = old_argv
            self.assertEqual(errors.getvalue(), '')
            row, = json.loads(output.getvalue())
            self.assertTrue(row['measured'])
            self.assertTrue(row['dup_checked'])
            return status, row

    def test_budget_blocks_duplicate_visible_tails_and_rendered_labels(self):
        for source in CASES['visible'] + CASES['labels']:
            with self.subTest(source=source):
                status, row = self.budget(source)
                self.assertEqual(status, 1)
                self.assertGreater(row['dup_shingles'], 0)

    def test_budget_keeps_metadata_and_code_out_of_duplicate_counts(self):
        for source in CASES['protected']:
            with self.subTest(source=source):
                status, row = self.budget(source)
                self.assertEqual(status, 0)
                self.assertEqual(row['dup_shingles'], 0)


if __name__ == '__main__':
    unittest.main()
