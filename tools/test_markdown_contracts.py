"""Regressions for Markdown protection, dependency discovery and fixture export."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dash_guard
import load_budget
import make_fixtures


CASES = json.loads(make_fixtures.markdown_fixture_bytes())
ROOT = Path(__file__).resolve().parents[1]


class MarkdownContracts(unittest.TestCase):
    def test_only_physical_newlines_change_fence_state(self):
        for case in CASES["physical_lines"]:
            with self.subTest(case=case["name"]):
                actual, hits = dash_guard.process_text(case["input"], "md")
                self.assertEqual(actual, case["expected"])
                self.assertEqual(len(hits), 1)
                self.assertEqual(load_budget.shingles(case["code"]), set())

    def test_code_bytes_survive_and_neighboring_prose_is_fixed(self):
        for case in CASES["markdown"]:
            with self.subTest(case=case["name"]):
                actual, hits = dash_guard.process_text(case["input"], "md")
                self.assertEqual(actual, case["expected"])
                self.assertTrue(hits)
                self.assertEqual(dash_guard.process_text(actual, "md"), (actual, []))

    def test_all_fence_styles_are_excluded_from_prose_shingles(self):
        for block in CASES["code_blocks"]:
            with self.subTest(block=block[:4]):
                self.assertEqual(load_budget.shingles(block), set())

    def test_shared_code_alone_does_not_make_prose_duplicate(self):
        for block in CASES["code_blocks"][:2]:
            with self.subTest(block=block[:4]):
                one = load_budget.shingles(CASES["prose_a"] + block)
                two = load_budget.shingles(CASES["prose_b"] + block)
                self.assertTrue(one)
                self.assertTrue(two)
                self.assertFalse(one & two)

    def test_nested_submodule_is_excluded_but_neighboring_reference_remains(self):
        with tempfile.TemporaryDirectory(prefix="style-budget-") as directory:
            root = Path(directory)
            (root / "SKILL.md").write_text(CASES["prose_a"], encoding="utf-8")
            nested = root / "vendor" / "kit"
            nested.mkdir(parents=True)
            reference = nested / "README.md"
            reference.write_text(CASES["prose_a"], encoding="utf-8")
            marker = nested / ".git"
            marker.write_text(CASES["marker"], encoding="utf-8")
            self.assertTrue(load_budget.in_submodule(str(root), str(reference)))
            self.assertEqual(load_budget.audit(str(root / "SKILL.md"))["ref_count"], 0)
            marker.unlink()
            self.assertFalse(load_budget.in_submodule(str(root), str(reference)))
            self.assertEqual(load_budget.audit(str(root / "SKILL.md"))["dup_pct"], 100.0)

    def test_kit_collection_accepts_subdirectory_without_absorbing_consumer_tests(self):
        spec = importlib.util.spec_from_file_location("style_collection_contract", ROOT / "conftest.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for directory, arguments, allowed in [
            (ROOT, (), True),
            (ROOT / "tools", (), True),
            (ROOT.parent, (), False),
            (ROOT.parent / (ROOT.name + "-sibling"), (), False),
            (ROOT.parent, (str(ROOT / "tools"),), True),
        ]:
            with self.subTest(directory=directory.name, args=arguments):
                config = SimpleNamespace(invocation_params=SimpleNamespace(dir=directory, args=arguments))
                self.assertEqual(module._asked_for_explicitly(config), allowed)
                self.assertEqual(module.pytest_ignore_collect(ROOT / "tools", config), None if allowed else True)

    def test_generator_exports_flat_artifacts_for_shared_guard(self):
        with tempfile.TemporaryDirectory(prefix="style-fixtures-") as directory:
            out = Path(directory)
            before = {name: (ROOT / "tests/fixtures" / name).read_bytes() for name in make_fixtures.artifacts()}
            with mock.patch.object(sys, "argv", ["make_fixtures.py", "--out", str(out)]), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                try:
                    code = make_fixtures.main()
                except SystemExit as error:
                    code = error.code
            self.assertEqual(code, 0)
            self.assertEqual({path.name for path in out.iterdir()}, set(make_fixtures.artifacts()))
            for name, expected in make_fixtures.artifacts().items():
                self.assertEqual((out / name).read_bytes(), expected)
                self.assertEqual((ROOT / "tests/fixtures" / name).read_bytes(), before[name])

    def test_generator_check_detects_changed_export_without_rewriting(self):
        with tempfile.TemporaryDirectory(prefix="style-fixture-check-") as directory:
            out = Path(directory)
            for name, payload in make_fixtures.artifacts().items():
                (out / name).write_bytes(payload)
            for corrupt in (False, True):
                if corrupt:
                    (out / "scan_cases.json").write_bytes(b"corrupt\n")
                with self.subTest(corrupt=corrupt), \
                        mock.patch.object(sys, "argv", ["make_fixtures.py", "--out", str(out), "--check"]), \
                        contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    try:
                        code = make_fixtures.main()
                    except SystemExit as error:
                        code = error.code
                    self.assertEqual(code, 1 if corrupt else 0)
                if corrupt:
                    self.assertEqual((out / "scan_cases.json").read_bytes(), b"corrupt\n")


if __name__ == "__main__":
    unittest.main()
