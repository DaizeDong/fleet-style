#!/usr/bin/env python3
# dash-guard:scanner-file -- this file carries the dash set by design; see _self_marker
"""Tests for dash_guard.

The reason this file exists: on 2026-07-17 the guard's --fix pass rewrote every markdown table cell
that held a single em dash (the conventional way to write "no default") into a bare comma, producing
99 cells across 7 repos that read ", something" or just ",". Nothing could detect the damage
afterwards, because the output contains no dash for the guard to flag, and the next --fix run would
have recreated it. So the property under test is stated the strong way: a dash-as-value cell must
round-trip to a WORD, and must never round-trip to punctuation.

Run: python test_dash_guard.py     (also collectable by pytest)
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dash_guard as dg  # noqa: E402
from dash_guard import NO_VALUE, fix_prose, process_text  # noqa: E402

EM = "—"
EN = "–"

_FAILS = []


def check(got, want, what):
    """Compare, and FAIL in whichever runner is driving this file.

    This used to only append to _FAILS, which the __main__ runner at the bottom prints.
    pytest never looks at that list, and CI runs pytest, so every comparison in this file
    was collected and then silently dropped: the suite reported green whatever the guard
    did. Measured by widening the range rule back to its broken form and re-running under
    pytest: 29 passed, including the test written to catch exactly that.

    So it raises as well as records. The __main__ runner already catches AssertionError per
    test and counts it, so both drivers now fail for the same reason. The cost is that a
    test stops at its first mismatch instead of listing every one, which is a fair price
    for a comparison that can fail at all.
    """
    if got != want:
        detail = f"{what}\n     got: {got!r}\n    want: {want!r}"
        _FAILS.append(detail)
        raise AssertionError(detail)


def md(text):
    """Run the real markdown pipeline (the path --fix takes) and return the rewritten text."""
    return process_text(text, "md")[0]


# --- the regression: a dash-only cell becomes a word, never punctuation ----------------------

def test_dash_only_cell_becomes_a_word():
    row = f"| `health_interval` | str | no | {EM} | `*:0/15` |"
    out = md(row)
    check(out, "| `health_interval` | str | no | none | `*:0/15` |", "dash-only cell -> none")
    # The property, stated so a future rewrite cannot satisfy it with different punctuation.
    for cell in out.split("|"):
        assert cell.strip() != ",", f"cell collapsed to a comma: {out!r}"
        assert not cell.strip().startswith(", "), f"cell opens with a comma: {out!r}"
    assert NO_VALUE.isalpha(), "the empty-cell token must be a word, not punctuation"


def test_dash_only_cell_is_idempotent():
    row = f"| a | {EM} | b |"
    once = md(row)
    check(md(once), once, "second --fix pass must not touch the repaired row")


def test_several_dash_cells_in_one_row():
    check(md(f"| SIFY | fcf_cap | null | {EM} | {EM} | {EM} | False |"),
          "| SIFY | fcf_cap | null | none | none | none | False |", "adjacent dash cells")


def test_trailing_dash_cell_without_closing_pipe():
    check(md(f"| Clean BUYs | **0** | {EM}"), "| Clean BUYs | **0** | none", "trailing cell")


def test_leading_dash_cell_is_a_sub_item_marker():
    check(md(f"| {EM} deep band (<$2.0B) | 109 | resolved |"),
          "| - deep band (<$2.0B) | 109 | resolved |", "leading dash -> ASCII hyphen")


def test_prose_inside_a_cell_still_gets_de_dashed():
    check(md(f"| x | a thing {EM} really | y |"), "| x | a thing, really | y |", "aside in a cell")


def test_delimiter_row_untouched():
    check(md("|---|---:|---|"), "|---|---:|---|", "ASCII hyphens are never touched")


def test_code_span_cell_untouched():
    row = f"| `{EM}` | text |"
    check(md(row), row, "a dash shown as code survives")


def test_dash_cell_inside_a_fence_untouched():
    src = f"```\n| a | {EM} |\n```"
    check(md(src), src, "fenced block is code")


def test_allow_marker_wins():
    row = f"| a | {EM} |  <!-- dash-guard: allow -->"
    check(md(row), row, "allow marker skips the line")


def test_not_a_table_row():
    check(md(f"a | b {EM} c"), "a | b, c", "a pipe in prose is not a table")


# --- the adjacent damage: a leftover dash must not leave a space before the comma ------------

def test_dash_at_end_of_line_glues_the_comma():
    check(fix_prose(f"the bot does exactly one thing {EM}"), "the bot does exactly one thing,",
          "hard-wrapped line ending in a dash")


def test_dash_touching_the_next_word():
    check(fix_prose(f"foo {EM}bar"), "foo, bar", "space only on the left")
    check(fix_prose(f"foo{EM} bar"), "foo, bar", "space only on the right")


def test_leading_dash_in_prose_is_dropped():
    check(fix_prose(f"{EM} continued here"), "continued here", "decorative leading dash")


def test_no_output_ever_contains_space_before_comma():
    for s in (f"a {EM}", f"a {EN}", f"a {EM}{EM}b", f"x {EM} y", f"{EM} z", f"t {EM}\r"):
        out = fix_prose(s)
        assert " ," not in out, f"{s!r} -> {out!r} still has a space before the comma"


def test_a_tight_dash_is_not_respaced():
    """A dash with no blank around it is a range the range rule cannot claim (currency symbols are
    not word characters). Rendering those is a separate call; this guard must not respace them,
    or every re-run churns hundreds of fleet lines for nothing."""
    check(fix_prose(f"$2.0B{EN}$4.6B"), "$2.0B,$4.6B", "currency range keeps its old rendering")
    check(fix_prose(f"8.8x{EN}50.5x"), "8.8x to 50.5x", "plain word chars still become a range")


def test_a_pause_between_two_words_is_not_a_range():
    """The range rule must not invent the word "to".

    Measured on a real repository: `attach{EM}{EM}attach` in a Chinese sentence was rewritten to
    "attach to attach", which is not a typographic change, it is a false sentence, and one that
    reads as deliberate. A range is a SINGLE dash between two SHORT tokens. Everything wider
    falls through to the leftover-run rule, which produces a comma and never a word that was
    not there.
    """
    check(fix_prose(f"not attach{EM}{EM}attach fails"), "not attach,attach fails",
          "a doubled dash between identical words is a pause, not a range")
    check(fix_prose(f"spawn{EM}attach"), "spawn,attach",
          "one dash between two long words is still not a range")
    check(fix_prose(f"2020{EN}2026"), "2020 to 2026", "a real numeric range survives")
    check(fix_prose(f"T1{EN}T9"), "T1 to T9", "a real identifier range survives")
    check(fix_prose(f"A{EN}Z"), "A to Z", "a two token range survives")


def test_existing_behavior_preserved():
    check(fix_prose(f"an aside {EM} like this"), "an aside, like this", "spaced aside")
    check(fix_prose(f"2020{EN}2026"), "2020 to 2026", "numeric range")
    check(fix_prose(f"T1{EN}T9"), "T1 to T9", "identifier range")
    check(fix_prose("nothing to do"), "nothing to do", "clean text untouched")


def test_python_comments_only():
    src = f'x = "{EM}"  # an aside {EM} here\n'
    out = process_text(src, "py")[0]
    assert f'"{EM}"' in out, "a dash inside a string literal must survive"
    assert "an aside, here" in out, f"comment not de-dashed: {out!r}"


# --- the enumeration fail-open ---------------------------------------------------------------
# Until 2026-07-30 `_git` returned "" whenever git exited nonzero. `_tracked()` then returned an
# empty list, the scan loop never executed, `total` stayed 0, and main() printed "dash_guard: clean"
# and exited 0 having opened no file. A directory that is not a repo, a git-archive extraction, git
# missing from PATH, an index.lock and a permission error all landed on that same green result --
# including in the vendored CI workflow, whose entire job is running this command. These tests fail
# if that comes back.

class _TmpDir:
    """A temp directory that is guaranteed NOT to be inside a git repo. Plain stdlib so this file
    still runs as a script without pytest."""

    def __enter__(self):
        self.path = tempfile.mkdtemp(prefix="dashguard-test-")
        return self.path

    def __exit__(self, *exc):
        shutil.rmtree(self.path, ignore_errors=True)
        return False


def _inside_a_repo(d):
    return subprocess.run(["git", "-C", d, "rev-parse", "--show-toplevel"],
                          capture_output=True).returncode == 0


def _guard(args, cwd, env_overrides=None):
    env = dict(os.environ)
    env.update(env_overrides or {})
    return subprocess.run([sys.executable, dg.__file__] + args, cwd=cwd,
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=env)


def _git(cwd, *a):
    subprocess.run(["git", "-C", cwd, *a], check=True, capture_output=True)


def test_a_failed_git_call_raises_instead_of_returning_empty():
    try:
        dg._git(os.getcwd(), "definitely-not-a-subcommand")
    except dg.GitError as e:
        assert "definitely-not-a-subcommand" in str(e), f"git's own error is not carried: {e}"
    else:
        raise AssertionError("a failing git call returned normally: that is the fail-open")


def test_allow_fail_returns_none_and_a_real_empty_output_stays_empty_string():
    assert dg._git(os.getcwd(), "definitely-not-a-subcommand", allow_fail=True) is None
    with _TmpDir() as d:
        _git(d, "init", "-q")
        assert dg._git(d, "ls-files") == "", "a SUCCESSFUL git call with no output must be ''"


def test_a_non_repo_directory_is_not_reported_clean():
    """THE REGRESSION. Before the fix this exited 0 printing 'dash_guard: clean'."""
    with _TmpDir() as d:
        if _inside_a_repo(d):
            return                                    # cannot construct the failure here
        p = _guard(["--tree", "--repo", "."], d)
        assert p.returncode != 0, f"a non-repo reported success: {p.stdout!r}"
        assert "clean" not in p.stdout, p.stdout
        assert "SCAN FAILED" in p.stderr, p.stderr


def test_an_exported_tree_with_no_git_dir_is_not_reported_clean():
    """A git-archive extraction: real files, no .git. Grading it clean is a lie about coverage."""
    with _TmpDir() as d:
        if _inside_a_repo(d):
            return
        with open(os.path.join(d, "README.md"), "w", encoding="utf-8") as f:
            f.write(f"an aside {EM} here\n")
        p = _guard(["--tree", "--repo", "."], d)
        assert p.returncode != 0 and "clean" not in p.stdout, p.stdout


def test_git_missing_from_path_is_not_reported_clean_and_is_not_a_traceback():
    with _TmpDir() as d:
        empty = os.path.join(d, "nothing-on-path")
        os.mkdir(empty)
        p = _guard(["--tree", "--repo", "."], d, {"PATH": empty, "GIT_EXEC_PATH": empty})
        assert p.returncode != 0 and "clean" not in p.stdout, p.stdout
        assert "SCAN FAILED" in p.stderr and "Traceback" not in p.stderr, p.stderr


def test_a_repo_tracking_zero_files_says_so():
    """Legitimate (a fresh init), so still exit 0 -- but it must not read like a scan that ran."""
    with _TmpDir() as d:
        _git(d, "init", "-q")
        p = _guard(["--tree", "--repo", "."], d)
        assert p.returncode == 0, p.stderr
        assert "tracks 0 files" in p.stderr, p.stderr


def test_a_clean_report_states_how_many_files_were_examined():
    with _TmpDir() as d:
        _git(d, "init", "-q")
        with open(os.path.join(d, "a.md"), "w", encoding="utf-8") as f:
            f.write("nothing to do\n")
        _git(d, "add", "a.md")
        p = _guard(["--tree", "--repo", "."], d)
        assert p.returncode == 0 and "1 file(s) examined" in p.stdout, p.stdout


def test_a_python_file_the_tokenizer_rejects_is_reported_not_silently_clean():
    """_process_py leaves unparseable source alone -- correct, and unchanged. What was wrong is
    that it returned the same (text, []) as a clean file, so a .py full of dashes that failed to
    tokenize was counted as examined and clean."""
    notes = []
    src = f"def f(:\n    # an aside {EM} here\n"
    out, hits = process_text(src, "py", notes)
    check(out, src, "unparseable source is still left untouched")
    assert hits == [], "no hits can be reported from a file that was never tokenized"
    assert notes and "untokenizable" in notes[0], f"the skip was not recorded: {notes!r}"
    with _TmpDir() as d:
        _git(d, "init", "-q")
        with open(os.path.join(d, "broken.py"), "w", encoding="utf-8") as f:
            f.write(src)
        _git(d, "add", "broken.py")
        p = _guard(["--tree", "--repo", "."], d)
        assert "untokenizable" in p.stderr, p.stderr
        assert "could NOT be examined" in p.stderr, p.stderr
        assert "1 skipped" in p.stdout, "the verdict must state its own coverage: %r" % p.stdout


def test_fix_stays_zero_for_a_deliberate_exclusion():
    """A DECLARED exclusion (the guard's own source) is a decision, not a coverage gap, and must not
    turn every --fix run in every repo red. The split between 'excluded' and 'could not be examined'
    is what keeps the nonzero below meaningful."""
    with _TmpDir() as d:
        _git(d, "init", "-q")
        for name in ("dash_guard.py", "a.md"):
            with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                f.write("nothing to do\n")
        _git(d, "add", "-A")
        p = _guard(["--fix", "--tree", "--repo", "."], d)
        assert p.returncode == 0, f"a declared exclusion failed the repair run: {p.stderr!r}"
        assert "deliberately excluded" in p.stderr, p.stderr


def test_fix_reports_nonzero_when_it_could_not_examine_a_file():
    """--fix is a repair, not a gate: after rewriting the tree its own 'no findings' is true by
    construction. The one thing it CAN honestly fail on is a file it never read."""
    with _TmpDir() as d:
        _git(d, "init", "-q")
        with open(os.path.join(d, "broken.py"), "w", encoding="utf-8") as f:
            f.write(f"def f(:\n    # an aside {EM} here\n")
        _git(d, "add", "broken.py")
        p = _guard(["--fix", "--tree", "--repo", "."], d)
        assert p.returncode != 0, f"--fix hid an unexaminable file: {p.stdout!r}"


# --- report-only kinds (2026-09-25): js, yaml, sh, ps, cmd comments, commit messages, unexamined --
# The property every test below protects: the new kinds see COMMENT prose only (every literal is
# code), and none of them can change a consumer's exit code until that kind is promoted by name.

def _lines(text, kind):
    return [n for n, _ in process_text(text, kind)[1]]


def test_block_policy_default_is_exactly_the_pre_rollout_kinds():
    check(dg.parse_block_kinds(""), frozenset({"md", "prose", "py"}), "default blocking set")
    check(dg.parse_block_kinds("js, yaml"), frozenset({"md", "prose", "py", "js", "yaml"}),
          "promotion adds to the default")
    check(dg.parse_block_kinds("all"), frozenset(dg.ALL_KINDS), "all promotes every kind")
    try:
        dg.parse_block_kinds("jss")
    except ValueError:
        pass
    else:
        raise AssertionError("a typo in --block-kinds was accepted and would leave the gate open")


def test_js_line_and_block_comments_are_examined():
    src = (f"const a = 1; // an aside {EM} here\n"
           f"/* a block\n   comment {EN} two */\n"
           f"const b = 2;\n")
    check(_lines(src, "js"), [1, 3], "js // and /* */ comments")


def test_js_string_template_and_regex_literals_are_code():
    src = (f'const s = "a {EM} b", t = \'c {EN} d\';\n'
           f"const u = `e {EM} f ${{g}} h {EM}`;\n"
           f"const r = /[{EN}{EM}]/g;\n"
           f'const url = "http://x.test/ {EM} // not a comment";\n'
           f"expect(render(x)).toBe(\"{EM}\");\n"
           f"const slashes = /^\\/*{EM}/;\n")
    check(_lines(src, "js"), [], "no js literal is ever read as prose")


def test_js_comment_inside_a_template_expression_is_still_a_comment():
    src = f"const u = `a ${{ f(/* why {EM} */ 1) }} b {EM}`;\n"
    check(_lines(src, "js"), [1], "comment inside ${ } counts, template text does not")
    check(_lines(f"const u = `a ${{ f(1) }} b {EM}`;\n", "js"), [], "template text alone")


def test_js_division_is_not_a_regex():
    src = f"const q = a / b; // ratio {EM} of two\nconst z = c / d / e;\n"
    check(_lines(src, "js"), [1], "a / b / c is division, the trailing comment is found")


def test_js_allow_marker_wins():
    check(_lines(f"// kept {EM} on purpose  dash-guard: allow\n", "js"), [], "allow marker")


def test_yaml_comments_only():
    src = (f"# a workflow {EM} note\n"
           f"name: build {EM} and test\n"
           f"description: 'quoted # {EM} not a comment'\n"
           f"url: a#{EM}b\n"
           f"key: value   # trailing {EN} comment\n"
           f"note: don't stop   # why {EM} here\n")
    check(_lines(src, "yaml"), [1, 5, 6], "yaml: comments yes, scalars no")


def test_yaml_run_block_shell_comment_is_counted():
    """A `#` line inside a `run: |` block is a shell comment written as prose, so it counts. This is
    documented rather than accidental: a workflow's step explanations live exactly there."""
    src = f"steps:\n  - run: |\n      # explain {EM} why\n      echo \"{EM}\"\n"
    check(_lines(src, "yaml"), [3], "shell comment in a run block")


def test_sh_comments_strings_and_heredocs():
    src = (f"#!/bin/sh\n"
           f"# setup {EM} step\n"
           f'echo "{EM} # quoted"\n'
           f"cat <<EOF\n# heredoc body {EM}\nEOF\n"
           f"echo ${{#arr}} {EM}\n"
           f"x=1 # trailing {EN}\n")
    check(_lines(src, "sh"), [2, 8], "sh: comments yes, strings/heredoc/${#} no")


def test_ps_line_block_and_here_string():
    src = (f"# note {EM}\n"
           f"<# block\n  {EM} text #>\n"
           f'$x = "{EM} # in a string"\n'
           f"$h = @'\n# {EM} here-string body\n'@\n"
           f"Write-Host 1 # tail {EN}\n")
    check(_lines(src, "ps"), [1, 3, 8], "ps: comments yes, strings/here-strings no")


def test_cmd_rem_and_double_colon():
    src = f"rem one {EM}\n:: two {EM}\necho three {EM}\n@REM four {EM}\n"
    check(_lines(src, "cmd"), [1, 2, 4], "cmd: rem and :: lines only")


def test_message_text_drops_git_comment_lines_and_the_scissors():
    raw = (f"Subject {EM} line\n\nBody\n# Please enter {EM} the message\n"
           f"# ------------------------ >8 ------------------------\ndiff {EM}\n")
    out = dg.message_text(raw)
    check(_lines(out, "message"), [1], "only the subject is prose here")
    check(len(out.split("\n")), 4, "line numbers still match the file up to the scissors")


def _repo_with(d, files):
    _git(d, "init", "-q")
    for name, body in files.items():
        p = os.path.join(d, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(body if isinstance(body, bytes) else body.encode("utf-8"))
        _git(d, "add", name)


def test_report_kinds_do_not_change_the_exit_code_until_promoted():
    with _TmpDir() as d:
        _repo_with(d, {"a.js": f"// js {EM}\n", ".github/workflows/w.yml": f"# y {EM}\n",
                       "s.sh": f"# s {EM}\n", "p.ps1": f"# p {EM}\n", "c.cmd": f"rem c {EM}\n",
                       "hooks/pre-commit": f"#!/usr/bin/env bash\n# h {EM}\n"})
        p = _guard(["--tree", "--repo", "."], d)
        assert p.returncode == 0, f"a report-only kind turned a consumer red: {p.stderr!r}"
        for tag in ("[report js]", "[report yaml]", "[report sh]", "[report ps]", "[report cmd]"):
            assert tag in p.stdout, (tag, p.stdout)
        assert "hooks/pre-commit:2: [report sh]" in p.stdout.replace("\\", "/"), p.stdout
        assert "js=1 yaml=1 sh=2 ps=1 cmd=1" in p.stdout, p.stdout
        for kind in ("js", "yaml", "sh", "ps", "cmd"):
            q = _guard(["--tree", "--repo", ".", "--block-kinds", kind], d)
            assert q.returncode == 1, f"--block-kinds {kind} did not block: {q.stdout!r}"
        q = _guard(["--tree", "--repo", ".", "--block-kinds", "nope"], d)
        assert q.returncode == 2 and "unknown kind" in q.stderr, q.stderr


def test_md_and_py_still_block_by_default():
    with _TmpDir() as d:
        _repo_with(d, {"a.md": f"an aside {EM} here\n", "b.js": "// fine\n"})
        p = _guard(["--tree", "--repo", "."], d)
        assert p.returncode == 1, "md stopped blocking: the existing behaviour changed"


def test_an_unexaminable_file_is_a_counted_finding():
    with _TmpDir() as d:
        _repo_with(d, {"bad.md": b"\xff\xfe not utf-8 \x80\n", "ok.md": "fine\n"})
        p = _guard(["--tree", "--repo", "."], d)
        assert p.returncode == 0, "unexamined must stay report-only by default"
        assert "unexamined=1" in p.stdout, f"the verdict hid an unread file: {p.stdout!r}"
        q = _guard(["--tree", "--repo", ".", "--block-kinds", "unexamined"], d)
        assert q.returncode == 1 and "could not be examined" in q.stderr, q.stderr


def test_fix_never_rewrites_a_report_kind():
    with _TmpDir() as d:
        body = f"// keep {EM} as is\nconst s = \"{EM}\";\n"
        _repo_with(d, {"a.js": body})
        p = _guard(["--fix", "--tree", "--repo", "."], d)
        assert p.returncode == 0, p.stderr
        assert "left 1 file(s) of comment-only kinds untouched" in p.stderr, p.stderr
        with open(os.path.join(d, "a.js"), encoding="utf-8", newline="") as f:
            check(f.read(), body, "--fix touched a js file")


def test_message_mode_reports_then_blocks_when_promoted():
    with _TmpDir() as d:
        msg = os.path.join(d, "COMMIT_EDITMSG")
        with open(msg, "w", encoding="utf-8") as f:
            f.write(f"Add a thing {EM} carefully\n\n# git comment {EM}\n")
        p = _guard(["--message", msg], d)
        assert p.returncode == 0 and "[report message]" in p.stdout and "message=1" in p.stdout, \
            p.stdout
        q = _guard(["--message", msg, "--block-kinds", "message"], d)
        assert q.returncode == 1, q.stdout
        with open(msg, "w", encoding="utf-8") as f:
            f.write("Add a thing carefully\n\n# git comment " + EM + "\n")
        r = _guard(["--message", msg, "--block-kinds", "message"], d)
        assert r.returncode == 0 and "1 commit message examined" in r.stdout, r.stdout
        s = _guard(["--message", os.path.join(d, "missing")], d)
        assert s.returncode == 2 and "SCAN FAILED" in s.stderr, "an unread message passed"


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    errors = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            errors += 1
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:                        # a test that ERRORS is a failed test
            errors += 1
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    for f in _FAILS:
        errors += 1
        print(f"FAIL {f}")
    print(f"dash_guard tests: {len(tests)} run, {errors} failure(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
