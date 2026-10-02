"""Generated worktree-path regressions; all contents and path states are synthetic."""
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

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import dash_guard as guard

CASES = json.loads(Path(__file__).with_name("worktree_cases.json").read_text(encoding="utf-8"))


class WorktreePathContracts(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory(prefix="style-worktree-")
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name)
        self.repo = self.root / "repo"
        self.target = self.repo / "nested" / "guide.txt"
        self.target.parent.mkdir(parents=True)
        self.neighbor = self.repo / "neighbor.txt"
        self.outside = self.root / "outside.txt"
        self.target.write_text(CASES["content"], encoding="utf-8")
        self.neighbor.write_text(CASES["clean"], encoding="utf-8")
        self.outside.write_text(CASES["outside"], encoding="utf-8")
        self.paths = ["nested/guide.txt", "neighbor.txt"]

    def invoke(self, *args):
        out, err = io.StringIO(), io.StringIO()
        argv = ["dash_guard.py", "--repo", str(self.repo), *map(str, args)]
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err), \
                mock.patch.object(guard, "_tracked", return_value=(self.paths, self.paths)):
            code = guard.cli()
        return code, out.getvalue(), err.getvalue()

    def metadata(self, original, case, path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        selected = self.target if case["where"] == "leaf" else self.target.parent
        if os.path.normcase(os.path.abspath(path)) != os.path.normcase(str(selected)):
            return info
        fields = {name: getattr(info, name) for name in (
            "st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")}
        fields["st_file_attributes"] = getattr(info, "st_file_attributes", 0)
        if case["kind"] == "symlink":
            fields["st_mode"] = stat.S_IFLNK | 0o777
        elif case["kind"] == "reparse":
            fields["st_file_attributes"] |= 1024
        else:
            fields["st_nlink"] = 2
        return SimpleNamespace(**fields)

    def test_linked_paths_are_incomplete_before_any_payload_open(self):
        original_lstat, original_open = os.lstat, open
        for case in CASES["unsafe"]:
            for args in (("--tree",), ("--tree", "--fix"),
                         (self.target,), ("--fix", self.target)):
                with self.subTest(case=case["name"], args=args):
                    opened = []
                    def access(path, *positional, **keywords):
                        if os.path.normcase(os.path.abspath(path)) == os.path.normcase(str(self.target)):
                            opened.append(positional)
                        return original_open(path, *positional, **keywords)
                    with mock.patch.object(guard.os, "lstat",
                            side_effect=lambda path, *a, **k: self.metadata(original_lstat, case, path, *a, **k)), \
                            mock.patch("builtins.open", side_effect=access):
                        code, out, err = self.invoke(*args)
                    self.assertEqual(code, 1, (out, err))
                    self.assertNotIn("clean", out.lower())
                    self.assertIn("could NOT be examined", err)
                    self.assertIn("unsafe worktree path", err)
                    self.assertEqual(opened, [])
                    self.assertEqual(self.target.read_text(encoding="utf-8"), CASES["content"])
                    self.assertEqual(self.outside.read_text(encoding="utf-8"), CASES["outside"])
                    if "--fix" in args:
                        self.assertIn("fixed 0 line(s)", out)

    def test_target_changes_after_read_or_at_open_are_not_repaired(self):
        original_lstat, original_open = os.lstat, open
        original_process = guard.process_text
        by_name = {case["name"]: case for case in CASES["unsafe"]}
        for name in CASES["changes"]:
            for phase in CASES["phases"]:
                with self.subTest(change=name, phase=phase):
                    self.target.write_text(CASES["content"], encoding="utf-8")
                    state = {"changed": False}
                    def change():
                        state["changed"] = True
                        if name == "replacement":
                            replacement = self.target.with_suffix(".tmp")
                            replacement.write_text(CASES["changed_content"], encoding="utf-8")
                            os.replace(replacement, self.target)
                        elif name == "content":
                            self.target.write_text(CASES["changed_content"], encoding="utf-8")
                    def metadata(path, *args, **kwargs):
                        if state["changed"] and name in by_name:
                            return self.metadata(original_lstat, by_name[name], path, *args, **kwargs)
                        return original_lstat(path, *args, **kwargs)
                    def process(*args, **kwargs):
                        result = original_process(*args, **kwargs)
                        if phase == "after_transform" and args[0] == CASES["content"]:
                            change()
                        return result
                    def access(path, mode="r", *args, **kwargs):
                        if os.path.normcase(os.path.abspath(path)) == os.path.normcase(str(self.target)) and mode == "w" and phase == "before_open":
                            change()
                        return original_open(path, mode, *args, **kwargs)
                    with mock.patch.object(guard.os, "lstat", side_effect=metadata), \
                            mock.patch.object(guard, "process_text", side_effect=process), \
                            mock.patch("builtins.open", side_effect=access):
                        code, out, err = self.invoke("--tree", "--fix")
                    self.assertTrue(state["changed"], "scheduled mutation was not reached")
                    self.assertEqual(code, 1, (out, err))
                    self.assertIn("fixed 0 line(s)", out)
                    self.assertIn("could not repair", err)
                    expected = CASES["changed_content"] if name in {"replacement", "content"} else CASES["content"]
                    self.assertEqual(self.target.read_text(encoding="utf-8"), expected)
                    self.assertEqual(self.outside.read_text(encoding="utf-8"), CASES["outside"])

    def test_descriptor_redirection_cannot_read_or_truncate_external_target(self):
        original_open = os.open
        for phase in ("read", "write"):
            with self.subTest(phase=phase):
                self.target.write_text(CASES["content"], encoding="utf-8")
                flags_seen = []
                def descriptor(path, flags, *args, **kwargs):
                    writing = bool(flags & (os.O_WRONLY | os.O_RDWR))
                    if os.path.normcase(os.path.abspath(path)) == os.path.normcase(str(self.target)) and writing == (phase == "write"):
                        flags_seen.append(flags)
                        return original_open(self.outside, flags, *args, **kwargs)
                    return original_open(path, flags, *args, **kwargs)
                with mock.patch.object(guard.os, "open", side_effect=descriptor):
                    code, out, err = self.invoke("--tree", "--fix")
                self.assertEqual(code, 1, (out, err))
                self.assertIn("fixed 0 line(s)", out)
                self.assertTrue(flags_seen)
                self.assertTrue(all(not flags & (os.O_TRUNC | os.O_CREAT) for flags in flags_seen))
                self.assertEqual(self.target.read_text(encoding="utf-8"), CASES["content"])
                self.assertEqual(self.outside.read_text(encoding="utf-8"), CASES["outside"])

    def test_open_return_topology_change_is_not_repaired(self):
        original_lstat, original_open = os.lstat, open
        for case in CASES["unsafe"]:
            with self.subTest(case=case["name"]):
                self.target.write_text(CASES["content"], encoding="utf-8")
                state = {"changed": False}
                def metadata(path, *args, **kwargs):
                    if state["changed"]:
                        return self.metadata(original_lstat, case, path, *args, **kwargs)
                    return original_lstat(path, *args, **kwargs)
                def access(path, mode="r", *args, **kwargs):
                    stream = original_open(path, mode, *args, **kwargs)
                    if os.path.normcase(os.path.abspath(path)) == os.path.normcase(str(self.target)) and mode == "w":
                        state["changed"] = True
                    return stream
                with mock.patch.object(guard.os, "lstat", side_effect=metadata), \
                        mock.patch("builtins.open", side_effect=access):
                    code, out, err = self.invoke("--tree", "--fix")
                self.assertTrue(state["changed"], "scheduled mutation was not reached")
                self.assertEqual(code, 1, (out, err))
                self.assertIn("fixed 0 line(s)", out)
                self.assertIn("could not repair", err)
                self.assertEqual(self.target.read_text(encoding="utf-8"), CASES["content"])
                self.assertEqual(self.outside.read_text(encoding="utf-8"), CASES["outside"])

    def test_safe_ordinary_file_still_repairs_and_truncates(self):
        code, out, err = self.invoke("--tree", "--fix")
        self.assertEqual(code, 0, (out, err))
        self.assertIn("fixed 1 line(s) across 1 file(s)", out)
        self.assertEqual(self.target.read_text(encoding="utf-8"), CASES["fixed"])
        self.assertEqual(self.neighbor.read_text(encoding="utf-8"), CASES["clean"])
        self.assertEqual(self.outside.read_text(encoding="utf-8"), CASES["outside"])

    def test_edited_file_can_be_scanned_and_repaired_again(self):
        for content in (CASES["changed_content"], CASES["content"]):
            self.target.write_text(content, encoding="utf-8")
            code, out, err = self.invoke("--tree", "--fix")
            self.assertEqual(code, 0, (out, err))
            self.assertIn("fixed 1 line(s) across 1 file(s)", out)
            code, out, err = self.invoke("--tree")
            self.assertEqual(code, 0, (out, err))
            self.assertIn("2 file(s) examined", out)
        self.assertEqual(self.target.read_text(encoding="utf-8"), CASES["fixed"])
        self.assertEqual(self.outside.read_text(encoding="utf-8"), CASES["outside"])

    def test_staged_blobs_do_not_inspect_worktree_topology(self):
        with mock.patch.object(guard, "_git", return_value=str(self.repo) + "\n"), \
                mock.patch.object(guard, "_staged", return_value=(self.paths, self.paths)), \
                mock.patch.object(guard, "_index_text", return_value=CASES["clean"]), \
                mock.patch.object(guard, "_worktree_snapshot", side_effect=AssertionError("worktree consulted")):
            code, out, err = self.invoke("--staged")
        self.assertEqual(code, 0, (out, err))
        self.assertIn("2 file(s) examined", out)


if __name__ == "__main__":
    unittest.main()
