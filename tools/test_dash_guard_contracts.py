"""Exercise incomplete scans and the exact staged content Git will commit."""

import contextlib
import errno
import io
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dash_guard as guard
import make_fixtures
import test_dash_guard as legacy


CASES = json.loads(make_fixtures.fixture_bytes())


class ScannerContracts(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(prefix="style-contract-")
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()

    def git(self, *args, input=None):
        result = subprocess.run(
            ["git", "-C", str(self.repo), *args],
            capture_output=True, check=True, input=input,
        )
        return result.stdout

    def init(self):
        self.git("init", "-q")

    def stage(self, name="guide.md", text=None):
        path = self.repo / name
        path.write_text(CASES["dash"] if text is None else text, encoding="utf-8")
        self.git("add", "--", name)
        return path

    def invoke(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        argv = ["dash_guard.py", "--repo", str(self.repo), *map(str, args)]
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(stdout), \
                contextlib.redirect_stderr(stderr):
            try:
                code = guard.cli()
            except SystemExit as error:
                code = error.code
        return code, stdout.getvalue(), stderr.getvalue()

    def test_fixture_is_exactly_reproducible(self):
        fixture = make_fixtures.ROOT / make_fixtures.FIXTURE
        self.assertEqual(fixture.read_bytes(), make_fixtures.fixture_bytes())

    def test_incomplete_python_scan_blocks(self):
        path = self.repo / "broken.py"
        path.write_text(CASES["broken_python"], encoding="utf-8")
        code, out, err = self.invoke(path)
        self.assertEqual(code, 1, (out, err))
        self.assertIn("incomplete", out.lower())
        self.assertNotIn("clean", out.lower())
        self.assertIn("1 skipped", out)
        self.assertIn("untokenizable", err)

    def test_undecodable_input_blocks(self):
        path = self.repo / "invalid.md"
        path.write_bytes(bytes.fromhex(CASES["invalid_utf8_hex"]))
        code, out, err = self.invoke(path)
        self.assertEqual(code, 1, (out, err))
        self.assertNotIn("clean", out.lower())
        self.assertIn("could NOT be examined", err)

    def test_missing_explicit_input_blocks(self):
        code, out, err = self.invoke("missing.md")
        self.assertEqual(code, 1, (out, err))
        self.assertNotIn("clean", out.lower())

    def test_metadata_errors_cannot_hide_behind_a_clean_neighbor(self):
        blocked = self.repo / "blocked.md"
        neighbor = self.repo / "neighbor.md"
        blocked.write_text(CASES["dash"], encoding="utf-8")
        neighbor.write_text(CASES["clean"], encoding="utf-8")
        before = blocked.read_bytes()
        original_stat = os.stat
        paths = [blocked.name, neighbor.name]
        errors = [PermissionError(errno.EACCES, "synthetic access failure"),
                  OSError(errno.EIO, "synthetic metadata failure"),
                  OSError(errno.ELOOP, "synthetic link failure"),
                  ValueError("synthetic invalid path")]
        for args in (("--tree",), (blocked, neighbor), ("--tree", "--fix")):
            for error in errors:
                with self.subTest(args=args, error=type(error).__name__):
                    def metadata(path, *positional, **keywords):
                        if os.fspath(path) == str(blocked):
                            raise error
                        return original_stat(path, *positional, **keywords)

                    with mock.patch.object(guard, "_tracked", return_value=(paths, paths)), \
                            mock.patch.object(guard.os, "stat", side_effect=metadata):
                        code, out, err = self.invoke(*args)
                    self.assertEqual(code, 1, (out, err))
                    self.assertNotIn("clean", out.lower())
                    self.assertIn("1 file(s) examined", out)
                    self.assertIn("could NOT be examined", err)
                    self.assertIn("metadata unavailable", err)
                    self.assertNotIn("deliberately excluded", err)
                    self.assertEqual(blocked.read_bytes(), before)

    def test_tree_absence_and_nonregular_paths_keep_intentional_exclusions(self):
        neighbor = self.repo / "neighbor.md"
        neighbor.write_text(CASES["clean"], encoding="utf-8")
        directory = self.repo / "directory.md"
        directory.mkdir()
        paths = ["missing.md", directory.name, neighbor.name]
        with mock.patch.object(guard, "_tracked", return_value=(paths, paths)):
            code, out, err = self.invoke("--tree")
        self.assertEqual(code, 0, (out, err))
        self.assertIn("clean (1 file(s) examined, 2 skipped)", out)
        self.assertIn("deliberately excluded", err)
        self.assertNotIn("could NOT be examined", err)

    def test_not_directory_metadata_keeps_missing_path_policy(self):
        original_stat = os.stat
        missing = self.repo / "missing.md"

        def metadata(path, *positional, **keywords):
            if os.fspath(path) == str(missing):
                raise NotADirectoryError(errno.ENOTDIR, "synthetic non-directory ancestor")
            return original_stat(path, *positional, **keywords)

        paths = [missing.name]
        for args, expected in [(("--tree",), 0), ((missing,), 1)]:
            with self.subTest(args=args), \
                    mock.patch.object(guard, "_tracked", return_value=(paths, paths)), \
                    mock.patch.object(guard.os, "stat", side_effect=metadata):
                code, out, err = self.invoke(*args)
            self.assertEqual(code, expected, (out, err))
            self.assertIn("deliberately excluded" if expected == 0 else "could NOT be examined", err)

    def test_open_access_failure_remains_incomplete_after_metadata_succeeds(self):
        blocked = self.repo / "blocked.md"
        blocked.write_text(CASES["dash"], encoding="utf-8")
        original_open = open

        def read(path, *args, **kwargs):
            if os.fspath(path) == str(blocked):
                raise PermissionError(errno.EACCES, "synthetic read failure")
            return original_open(path, *args, **kwargs)

        paths = [blocked.name]
        with mock.patch.object(guard, "_tracked", return_value=(paths, paths)), \
                mock.patch("builtins.open", side_effect=read):
            code, out, err = self.invoke("--tree")
        self.assertEqual(code, 1, (out, err))
        self.assertNotIn("clean", out.lower())
        self.assertIn("unreadable (PermissionError)", err)
        self.assertNotIn("deliberately excluded", err)

    def test_staged_blob_does_not_consult_worktree_metadata(self):
        target = self.repo / "guide.md"
        original_stat = os.stat
        metadata_calls = []

        def metadata(path, *args, **kwargs):
            if os.fspath(path) == str(target):
                metadata_calls.append(path)
                raise PermissionError(errno.EACCES, "synthetic worktree access failure")
            return original_stat(path, *args, **kwargs)

        with mock.patch.object(guard, "_git", return_value=str(self.repo) + "\n"), \
                mock.patch.object(guard, "_staged", return_value=([target.name], [target.name])), \
                mock.patch.object(guard, "_index_text", return_value=CASES["clean"]) as index_text, \
                mock.patch.object(guard.os, "stat", side_effect=metadata):
            code, out, err = self.invoke("--staged")
        self.assertEqual(code, 0, (out, err))
        self.assertEqual(metadata_calls, [])
        index_text.assert_called_once_with(str(self.repo), target.name)
        self.assertIn("1 file(s) examined", out)

    def test_readable_scanner_source_keeps_intentional_exclusion(self):
        tools = self.repo / "tools"
        tools.mkdir()
        scanner = tools / "dash_guard.py"
        scanner.write_text(CASES["clean"], encoding="utf-8")
        paths = ["tools/dash_guard.py"]
        with mock.patch.object(guard, "_tracked", return_value=(paths, paths)):
            code, out, err = self.invoke("--tree")
        self.assertEqual(code, 0, (out, err))
        self.assertIn("the guard's own source", err)
        self.assertNotIn("could NOT be examined", err)

    def test_documented_check_action_accepts_clean_file(self):
        path = self.repo / "guide.md"
        path.write_text(CASES["clean"], encoding="utf-8")
        code, out, err = self.invoke("--check", path)
        self.assertEqual(code, 0, (out, err))
        self.assertIn("1 file(s) examined", out)

    def test_check_and_fix_are_mutually_exclusive(self):
        path = self.repo / "guide.md"
        path.write_text(CASES["dash"], encoding="utf-8")
        before = path.read_bytes()
        code, out, err = self.invoke("--check", "--fix", path)
        self.assertEqual(code, 2, (out, err))
        self.assertEqual(path.read_bytes(), before)

    def test_staged_unicode_and_space_names_are_scanned(self):
        self.init()
        for name in CASES["filenames"]:
            with self.subTest(name=name):
                self.stage(name)
                try:
                    code, out, err = self.invoke("--staged")
                    self.assertEqual(code, 1, (name, out, err))
                    self.assertIn(CASES["dash"].strip(), out)
                finally:
                    self.git("rm", "--cached", "--", name)

    def test_staged_violation_survives_unstaged_clean_edit(self):
        self.init()
        path = self.stage()
        path.write_text(CASES["clean"], encoding="utf-8")
        code, out, err = self.invoke("--staged")
        self.assertEqual(code, 1, (out, err))
        self.assertIn(CASES["dash"].strip(), out)
        self.assertEqual(path.read_text(encoding="utf-8"), CASES["clean"])

    def test_staged_clean_file_ignores_unstaged_violation(self):
        self.init()
        path = self.stage(text=CASES["clean"])
        path.write_text(CASES["dash"], encoding="utf-8")
        code, out, err = self.invoke("--staged")
        self.assertEqual(code, 0, (out, err))
        self.assertIn("1 file(s) examined", out)

    def test_staged_violation_survives_unstaged_removal(self):
        self.init()
        path = self.stage()
        path.unlink()
        code, out, err = self.invoke("--staged")
        self.assertEqual(code, 1, (out, err))
        self.assertIn(CASES["dash"].strip(), out)

    def test_explicit_staged_path_reads_index(self):
        self.init()
        path = self.stage()
        path.write_text(CASES["clean"], encoding="utf-8")
        for spelling in ("guide.md", "./guide.md", path):
            with self.subTest(spelling=str(spelling)):
                code, out, err = self.invoke("--staged", spelling)
                self.assertEqual(code, 1, (out, err))
                self.assertIn(CASES["dash"].strip(), out)

    def test_explicit_staged_path_must_belong_to_repo(self):
        self.init()
        outside = self.root / "outside.md"
        outside.write_text(CASES["clean"], encoding="utf-8")
        for spelling in (outside, "../outside.md"):
            with self.subTest(spelling=str(spelling)):
                code, out, err = self.invoke("--staged", spelling)
                self.assertNotEqual(code, 0, (out, err))
                self.assertNotIn("clean", out.lower())

    def test_missing_explicit_index_entry_blocks(self):
        self.init()
        path = self.repo / "untracked.md"
        path.write_text(CASES["clean"], encoding="utf-8")
        code, out, err = self.invoke("--staged", "untracked.md")
        self.assertNotEqual(code, 0, (out, err))
        self.assertNotIn("clean", out.lower())

    def test_staged_fix_refused_without_changing_index_or_worktree(self):
        self.init()
        path = self.stage()
        path.write_text(CASES["dash"] * 2, encoding="utf-8")
        before_worktree = path.read_bytes()
        before_index = self.git("show", ":0:guide.md")
        code, out, err = self.invoke("--staged", "--fix")
        self.assertEqual(code, 2, (out, err))
        self.assertEqual(path.read_bytes(), before_worktree)
        self.assertEqual(self.git("show", ":0:guide.md"), before_index)

    def test_added_only_reads_staged_postimage(self):
        self.init()
        path = self.stage()
        path.write_text(CASES["clean"], encoding="utf-8")
        code, out, err = self.invoke("--added-only")
        self.assertEqual(code, 1, (out, err))
        self.assertIn(CASES["dash"].strip(), out)

    def test_added_only_and_tree_are_not_ambiguous(self):
        self.init()
        self.stage(text=CASES["clean"])
        code, out, err = self.invoke("--added-only", "--tree")
        self.assertEqual(code, 2, (out, err))

    def test_staged_enumeration_from_subdirectory_uses_repo_root(self):
        self.init()
        self.stage()
        nested = self.repo / "nested"
        nested.mkdir()
        code, out, err = self.invoke("--repo", nested, "--staged")
        self.assertEqual(code, 1, (out, err))
        self.assertIn(CASES["dash"].strip(), out)

    def test_explicit_staged_path_is_relative_to_requested_subdirectory(self):
        self.init()
        nested = self.repo / "nested"
        nested.mkdir()
        path = self.stage("nested/guide.md")
        path.write_text(CASES["clean"], encoding="utf-8")
        code, out, err = self.invoke("--repo", nested, "--staged", "guide.md")
        self.assertEqual(code, 1, (out, err))
        self.assertIn(CASES["dash"].strip(), out)

    def test_failed_repair_is_not_counted_as_fixed(self):
        path = self.repo / "guide.md"
        path.write_text(CASES["dash"], encoding="utf-8")
        original_open = open

        def refuse_writes(filename, mode="r", *args, **kwargs):
            if "w" in mode:
                raise PermissionError("synthetic write refusal")
            return original_open(filename, mode, *args, **kwargs)

        with mock.patch("builtins.open", side_effect=refuse_writes):
            code, out, err = self.invoke("--fix", path)
        self.assertEqual(code, 1, (out, err))
        self.assertIn("fixed 0 line(s)", out)
        self.assertIn("could not repair", err)
        self.assertEqual(path.read_text(encoding="utf-8"), CASES["dash"])

    def test_staged_enumeration_includes_renames_and_nul_framing(self):
        # Git for Windows refuses control characters in filesystem/index paths;
        # this framing control covers such a name without fabricating a live run.
        names = CASES["framed_paths"]
        with mock.patch.object(guard, "_git", return_value="\0".join(names) + "\0") as git:
            all_paths, eligible = guard._staged(str(self.repo))
        self.assertEqual(all_paths, names)
        self.assertEqual(eligible, names)
        arguments = git.call_args.args
        self.assertIn("-z", arguments)
        self.assertTrue(any(arg.startswith("--diff-filter=") and "R" in arg for arg in arguments))

    def test_added_line_diff_disables_external_helpers(self):
        with mock.patch.object(guard, "_git", return_value=CASES["added_diff"]) as git:
            lines = guard.added_line_numbers(str(self.repo), "guide.md")
        self.assertEqual(lines, {1, 9, 10})
        self.assertIn("--no-ext-diff", git.call_args.args)
        self.assertIn("--no-textconv", git.call_args.args)

    def test_renderer_mismatch_raises_in_existing_pytest_test(self):
        failures = getattr(legacy, "_FAILS", None)
        if failures is not None:
            self.addCleanup(failures.clear)
        with mock.patch.object(legacy, "process_text", return_value=("incorrect", [])):
            with self.assertRaises(AssertionError):
                legacy.test_not_a_table_row()

    def test_original_check_accepts_matching_output(self):
        legacy.check("same", "same", "synthetic equality")


# Keep generated path regressions in the existing tools suite and CI selection.
_worktree_spec = importlib.util.spec_from_file_location(
    "_fleet_style_worktree_tests",
    Path(__file__).resolve().parents[1] / "tests/fixtures/_worktree_contracts.py")
_worktree_tests = importlib.util.module_from_spec(_worktree_spec)
_worktree_spec.loader.exec_module(_worktree_tests)


class WorktreePathContracts(_worktree_tests.WorktreePathContracts):
    """Run the generated worktree cases through the established contract-test entrypoint."""


if __name__ == "__main__":
    unittest.main()
