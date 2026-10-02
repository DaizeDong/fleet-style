#!/usr/bin/env python3
# dash-guard:scanner-file -- this file carries the dash set by design; see _self_marker
"""dash_guard: flag / fix en-dash and em-dash used as prose in a public repo.

House rule (user global): published prose carries NO en/em dash. The ASCII hyphen `-` is left
ALONE (it is code syntax: identifiers, flags, file names, versions, URLs, ranges in code), so this
guard only touches the en-dash U+2013, em-dash U+2014 and horizontal bar U+2015. None of those
three ever appear in code SYNTAX, so every occurrence outside a code span is prose and is a target.

Modes (exactly one action):
  --check  (default) print every offending file:line; exit 1 for findings or incomplete coverage
  --fix              rewrite the offending files in place. NOT a gate: see the note at the end of
                     main(). It exits 0 after a successful repair and 1 only for files it could not
                     read, so wiring --fix into CI would install a check that cannot fail.

Exit codes: 0 clean (or repaired under --fix), 1 findings or incomplete coverage,
2 invalid arguments or an unusable Git repository. Every nonzero code blocks a check.

Target set:
  --staged           the git staged text blobs (pre-commit hook)
  --tree   (default) every git-tracked text file
  paths...           explicit files (overrides the set, still read from the index under --staged)

--fix cannot be combined with --staged: rewriting an index version into the worktree would
discard unstaged edits. Fix the worktree, inspect the diff, and stage the intended changes.

Markdown safety: fenced ``` code blocks and inline `code` spans are skipped, so a dash shown as a
literal example survives. In every other text file each en/em dash is treated as prose.

Replacement (deterministic):
  markdown table cell that is ONLY a dash  -> "none"  (the cell means "no value", not an aside)
  markdown table cell STARTING with a dash -> ASCII "-" (a sub-item marker, not an aside)
  spaced   ` — ` / ` – `                 -> ", "   (appositive / aside; never grammatically wrong)
  ASCII range  A–B  (word char both sides) -> "A to B"  (e.g. T1–T9, 2020–2026)
  any leftover run  —— / – / ―           -> "," glued to the preceding word (never " ,")

Why the table rules exist: a table cell holding a single long dash is the conventional way to write
"no default". Substituting punctuation there produced cells reading "," or ", something", which is
not prose at all, and NO gate can see it afterwards because the output contains no dash. The cell
rules run before the prose rules so a dash that is a value never reaches the appositive rule.
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import os
import re
import stat
import subprocess
import sys
import tokenize

_MARKDOWN_SPEC = importlib.util.spec_from_file_location(
    "_fleet_style_markdown", os.path.join(os.path.dirname(__file__), "markdown_regions.py"))
_MARKDOWN = importlib.util.module_from_spec(_MARKDOWN_SPEC)
_MARKDOWN_SPEC.loader.exec_module(_MARKDOWN)

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

_DASHES = "–—―"          # – — ―
_DASH_RE = re.compile(f"[{_DASHES}]")
# How each extension is processed:
#   "md"    Markdown/rst: full prose de-dash, code fences + inline `code` exempt.
#   "prose" plain text: full prose de-dash, line by line.
#   "py"    Python: de-dash COMMENT tokens ONLY. Every string literal (docstring AND a data literal
#           like re.compile(r"[–—]")) is left untouched, so a functional dash-as-data is never
#           corrupted. Output/display strings are handled by the skill's runtime _inline normalizer,
#           not here.
#   "tmpl"  A generator template, processed as Markdown. This extension exists because a template is
#           the one file whose dashes are invisible twice over: the .tmpl suffix hid it from this map,
#           and the generator that expands it holds the rest of its prose in Python STRING literals,
#           which the "py" rule leaves alone by design. skill-smith therefore reported a clean tree
#           while its CONFIG.md.tmpl carried 22 dashes and every repo it scaffolded was born failing
#           the very gate it vendored. Markdown handling is the right rule even for a non-Markdown
#           template (a systemd unit, a gitignore): those carry no fences and no inline code spans, so
#           md degrades to plain prose on them, while a .md.tmpl keeps its fenced blocks protected.
# Any extension not listed is left completely alone (a mixed prose/data code file we cannot auto-edit
# safely). The rule is enforced on published docs + the .py comment prose; runtime output compliance
# is the renderer's job.
_KIND = {".md": "md", ".markdown": "md", ".rst": "md", ".txt": "prose", ".py": "py",
         ".tmpl": "md"}

_SPACED = re.compile(rf"\s+[{_DASHES}]+\s+")
_RANGE = re.compile(rf"([A-Za-z0-9])[{_DASHES}]+([A-Za-z0-9])")
# The leftover run is matched TOGETHER with the blanks hugging it, so the replacement decides the
# spacing instead of inheriting a stray space and emitting " ,".
_RUN = re.compile(rf"[ \t]*[{_DASHES}]+[ \t]*")

NO_VALUE = "none"                  # what an empty-meaning table cell says (fleet convention)


def _run_sub(m) -> str:
    """Replacement for a dash run that neither the spaced rule nor the range rule claimed.

    Three shapes, all of which used to collapse to a bare "," carrying whatever blank happened to
    sit in front of it:
      "... one thing —"  (hard-wrapped prose, sentence continues next line) -> "... one thing,"
      "foo —bar" / "foo— bar"                                              -> "foo, bar"
      "— foo"  at the very start of the segment (decoration, not an aside)  -> "foo"

    A dash with NO blank on either side ("$2.0B–$4.6B") keeps the old bare comma on purpose: those
    are ranges the range rule cannot claim (it needs a word character on both sides and a currency
    symbol is not one), rendering them is a separate judgement call, and widening the spacing here
    would churn hundreds of lines across the fleet without making any of them correct.
    """
    text, run = m.string, m.group()
    lead, trail = run[:1].isspace(), run[-1:].isspace()
    if not lead and not trail:
        return ","                               # tight dash: unchanged, no gratuitous respacing
    rest = text[m.end():]
    if rest in ("", "\r"):                       # the dash ended the line: glue the comma on
        return ","
    if m.start() == 0 and trail:
        return ""                                # a leading dash is decoration; drop it
    return ", "


def fix_prose(s: str) -> str:
    """Replace en/em dashes in one prose segment. Order matters: spaced separators first (they
    become ', '), then ASCII ranges ('A to B'), then any leftover dash run becomes a comma that is
    glued to the preceding word."""
    s = _SPACED.sub(", ", s)
    s = _RANGE.sub(r"\1 to \2", s)
    s = _RUN.sub(_run_sub, s)
    return s


# --- markdown table cells -------------------------------------------------------------------
# A pipe-table row. Markdown allows up to three leading spaces before the pipe.
_TABLE_ROW = re.compile(r"^ {0,3}\|")
# A cell whose ENTIRE content is a dash run: it means "no value", so it becomes a word.
_CELL_DASH_ONLY = re.compile(rf"[ \t]*[{_DASHES}]+[ \t]*\r?")
# A cell that OPENS with a dash run followed by text: a sub-item marker, so it becomes an ASCII
# hyphen (which this guard never touches) and keeps the indent it was drawing.
_CELL_DASH_LEAD = re.compile(rf"^([ \t]*)[{_DASHES}]+(?=[ \t]+\S)")


def fix_table_cells(line: str, content_start=None) -> str:
    """Rewrite real table cells after code masking; escaped pipes are cell content."""
    if content_start is not None:
        prefix, body = line[:content_start], line[content_start:]
        if _TABLE_ROW.match(body):
            return prefix + fix_table_cells(body)
        pieces = []
        for left, right in _MARKDOWN._cell_ranges(body, 0, len(body)):
            cell = body[left:right]
            if _CELL_DASH_ONLY.fullmatch(cell):
                cell = re.sub(rf"[{_DASHES}]+", NO_VALUE, cell)
            else:
                cell = _CELL_DASH_LEAD.sub(r"\1-", cell)
            pieces.append(cell)
        return prefix + "|".join(pieces)
    pipes = [index for index, char in enumerate(line)
             if char == "|" and not _MARKDOWN.escaped(line, index)]
    if not _TABLE_ROW.match(line) or len(pipes) < 2:
        return line
    pieces = [line[:pipes[0] + 1]]
    for index, left in enumerate(pipes):
        has_next = index + 1 < len(pipes)
        right = pipes[index + 1] if has_next else len(line)
        cell = line[left + 1:right]
        if _CELL_DASH_ONLY.fullmatch(cell):
            cell = f" {NO_VALUE}" + (" " if has_next else "") + ("\r" if cell.endswith("\r") else "")
        else:
            cell = _CELL_DASH_LEAD.sub(r"\1-", cell)
        pieces.append(cell)
        if has_next:
            pieces.append("|")
    return "".join(pieces)


_ALLOW = "dash-guard: allow"       # a line carrying this marker is left untouched (rare legit dash)


def _process_md(text):
    # NUL-delimited placeholders keep protected pipes and dashes out of every replacement.
    # Choose a delimiter absent from the source, then restore each exact protected substring.
    delimiter = "\0"
    while delimiter in text:
        delimiter += "\0"
    regions = list(_MARKDOWN.code_regions(text))
    tables = list(_MARKDOWN.table_regions(text))
    table_index = 0
    region_index, offset = 0, 0
    lines, hits = [], []
    for lineno, line in enumerate(text.split("\n"), 1):
        end = offset + len(line)
        while region_index < len(regions) and regions[region_index][1] <= offset:
            region_index += 1
        while table_index < len(tables) and tables[table_index][1] <= offset:
            table_index += 1
        table_start = (tables[table_index][0] - offset
                       if table_index < len(tables) and tables[table_index][0] < end else None)
        pieces, protected, cursor = [], [], 0
        for left, right in regions[region_index:]:
            if left >= end:
                break
            left, right = max(left, offset) - offset, min(right, end) - offset
            token = f"{delimiter}{len(protected)}{delimiter}"
            pieces.extend((line[cursor:left], token))
            protected.append((token, line[left:right]))
            cursor = right
        pieces.append(line[cursor:])
        if _ALLOW in line:
            fixed = line
        else:
            fixed = fix_prose(fix_table_cells("".join(pieces), content_start=table_start))
            for token, original in protected:
                fixed = fixed.replace(token, original)
        if fixed != line:
            hits.append((lineno, line))
        lines.append(fixed)
        offset = end + 1
    return "\n".join(lines), hits


def _process_py(text: str, notes=None):
    """De-dash Python COMMENT tokens ONLY. Every string literal (docstring AND a data literal such as
    re.compile(r"[–—]") or a test fixture) is left untouched, so a functional dash-as-data is never
    corrupted. A line carrying the allow marker is skipped. Unparseable source is left as-is (we never
    blind-edit code we cannot tokenize). Returns (new_text, hits).

    Leaving unparseable source alone is the RIGHT behaviour and is unchanged. What was wrong is that
    it returned the same (text, []) as a genuinely clean file, so a .py file full of dashes that the
    tokenizer choked on counted as examined-and-clean. It now records the reason in `notes`, which
    main() prints and counts, so a clean report can never quietly include a file nobody read."""
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError) as e:
        if notes is not None:
            notes.append("untokenizable (%s)" % type(e).__name__)
        return text, []
    edits = {}                       # lineno -> (col_of_hash, fixed_comment)
    for tok in toks:
        if tok.type == tokenize.COMMENT and _ALLOW not in tok.line:
            fixed = fix_prose(tok.string)
            if fixed != tok.string:
                edits[tok.start[0]] = (tok.start[1], fixed)
    if not edits:
        return text, []
    lines, hits = text.split("\n"), []
    for lineno, (col, fixed) in edits.items():
        orig = lines[lineno - 1]
        lines[lineno - 1] = orig[:col] + fixed      # a comment always runs to end of line
        hits.append((lineno, orig))
    return "\n".join(lines), hits


def process_text(text: str, kind: str, notes=None):
    """Return (new_text, hits) where hits = list of (lineno, original_line).
    kind: "py" (comments only), "md" (prose, code spans exempt), "prose" (plain text, full).
    notes: optional list; anything appended is a reason this file was not fully examined."""
    if kind == "py":
        return _process_py(text, notes)
    if kind == "md":
        return _process_md(text)
    out_lines, hits = [], []
    for lineno, line in enumerate(text.split("\n"), 1):
        if _ALLOW in line:
            out_lines.append(line)
            continue
        fixed = fix_prose(line)
        if fixed != line:
            hits.append((lineno, line))
        out_lines.append(fixed)
    return "\n".join(out_lines), hits


_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def added_line_numbers(repo, path):
    """Line numbers this staged diff ADDS to `path`, numbered in the post-image.

    Why this exists. --staged scans whole staged files, which is right for a repo whose tree was
    cleaned once and has to stay clean. It is wrong for a tree carrying standing violations nobody
    intends to rewrite, because then every commit touching such a file re-reports lines the commit
    did not introduce, and a check that is always red gets bypassed within a day. The memory pool
    is exactly that case: 2184 standing hits against an owner rule that says existing internal docs
    are not retroactively cleaned while newly written prose must comply.

    Returns None when the added range cannot be determined, and callers MUST read None as "examine
    the whole file" rather than "nothing was added". Returning an empty set on a parse failure
    would convert a broken scan into a silent pass, which is the one outcome this guard exists to
    prevent.
    """
    out = _git(repo, "diff", "--cached", "--no-ext-diff", "--no-textconv", "-U0",
               "--", ":(literal)" + path, allow_fail=True)
    if out is None:
        return None
    nums, seen_hunk = set(), False
    for line in out.splitlines():
        m = _HUNK.match(line)
        if m:
            seen_hunk = True
            start = int(m.group(1))
            count = int(m.group(2)) if m.group(2) is not None else 1
            nums.update(range(start, start + count))
    if not seen_hunk and out.strip():
        return None
    return nums


class GitError(RuntimeError):
    """A git invocation this run depends on did not succeed. Raised, never swallowed."""


def _git(repo, *a, allow_fail=False, raw=False):
    """Run a git command and return its stdout.

    THIS USED TO FAIL OPEN: `return r.stdout if r.returncode == 0 else ""`. _tracked() then returned
    an empty list, the scan loop never executed, `total` stayed 0, and main() printed
    "dash_guard: clean" and exited 0 without opening a single file. Every way git can fail -- not a
    repo, an extracted git-archive with no .git, git missing from PATH, an index.lock, a permission
    error -- arrived at that same green result, including in the CI workflow whose entire job is
    running this command.

    So a nonzero exit RAISES, carrying git's own stderr. allow_fail=True returns None instead, and
    is only for calls where failure is an ordinary state rather than a broken environment. None is
    deliberately distinct from "": that still means git succeeded with genuinely empty output (an
    empty staged diff is the normal case and must stay a normal case).
    """
    try:
        r = subprocess.run(["git", "-C", repo, *a], capture_output=True)
    except (OSError, ValueError) as e:
        if allow_fail:
            return None
        raise GitError("cannot execute `git %s` in %s: %s\n  (is git installed and on PATH?)"
                       % (" ".join(a), repo, e)) from None
    if r.returncode != 0:
        if allow_fail:
            return None
        raise GitError("`git %s` exited %d in %s\n  %s"
                       % (" ".join(a), r.returncode, repo,
                          r.stderr.decode("utf-8", errors="replace").strip().replace("\n", "\n  ")
                          or "(no stderr)"))
    # Preserve filename bytes; replacement characters could silently name a different path.
    return r.stdout if raw else r.stdout.decode("utf-8", errors="surrogateescape")


def _eligible(paths):
    return [f for f in paths if os.path.splitext(f)[1].lower() in _KIND]


def _tracked(repo):
    """(all tracked paths, the ones with a de-dashable extension). Both are returned so main can
    tell 'this repo tracks nothing' from 'this repo tracks no markdown/text/python'."""
    # -z: see the note in pii_guard.tracked_files. Without it a non-ASCII path arrives as a
    # C-quoted escape string that opens nothing, and it vanishes from BOTH the examined and the
    # skipped tally, so the clean line does not even admit something went unread.
    all_paths = [p for p in _git(repo, "ls-files", "-z").split("\0") if p]
    return all_paths, _eligible(all_paths)


def _staged(repo):
    out = _git(repo, "diff", "--cached", "--no-ext-diff", "--no-textconv",
               "--name-only", "-z", "--diff-filter=ACMRTU")
    all_paths = [path for path in out.split("\0") if path]
    return all_paths, _eligible(all_paths)


def _index_path(repo, path):
    """Normalize a literal path inside the repo without following worktree links."""
    absolute = os.path.abspath(path if os.path.isabs(path) else os.path.join(repo, path))
    try:
        inside = os.path.normcase(os.path.commonpath([repo, absolute])) == os.path.normcase(repo)
    except ValueError:
        inside = False
    if not inside or absolute == repo:
        raise GitError("staged path is outside the repository: %s" % path)
    return os.path.relpath(absolute, repo).replace(os.sep, "/")


def _index_text(repo, relative):
    """Read the stage-zero blob; unstaged edits and removals cannot mask it."""
    return _git(repo, "show", "--no-ext-diff", "--no-textconv", ":0:" + relative,
                raw=True).decode("utf-8")



class _UnsafeWorktreePath(OSError):
    """A worktree path cannot be read or repaired without following an unsafe target."""


def _worktree_stamp(info):
    # Windows stat and fstat can expose different deprecated ctime semantics.
    # Use their shared creation timestamp; POSIX retains its change timestamp.
    timestamp = (getattr(info, "st_birthtime_ns", info.st_ctime_ns)
                 if os.name == "nt" else info.st_ctime_ns)
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, timestamp,
            getattr(info, "st_file_attributes", 0))


def _worktree_snapshot(path):
    """Bind an ordinary file and its directory chain without following links."""
    absolute = os.path.abspath(path)
    chain = []
    current = absolute
    while True:
        chain.append(current)
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    snapshot = []
    for current in reversed(chain):
        info = os.lstat(current)
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 1024:
            raise _UnsafeWorktreePath("unsafe worktree path (symlink or reparse point)")
        if current != absolute:
            if not stat.S_ISDIR(info.st_mode):
                raise NotADirectoryError(current)
            stamp = (info.st_dev, info.st_ino, info.st_mode,
                     getattr(info, "st_file_attributes", 0))
        else:
            if not stat.S_ISREG(info.st_mode):
                return None
            if info.st_nlink != 1:
                raise _UnsafeWorktreePath("unsafe worktree path (linked regular file)")
            stamp = _worktree_stamp(info)
        snapshot.append((current, stamp))
    # Recheck the leaf after walking its ancestors; metadata errors remain scan failures.
    if _worktree_stamp(os.stat(path, follow_symlinks=False)) != snapshot[-1][1]:
        raise _UnsafeWorktreePath("worktree target changed during metadata inspection")
    return tuple(snapshot)


def _open_worktree(path, mode, snapshot):
    """Open an already observed file without truncating or creating a raced target."""
    if _worktree_snapshot(path) != snapshot:
        raise _UnsafeWorktreePath("worktree target changed after inspection")

    def checked_opener(filename, flags):
        flags = (flags & ~(os.O_TRUNC | os.O_CREAT)) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(filename, flags)
        try:
            if (_worktree_snapshot(path) != snapshot or
                    _worktree_stamp(os.fstat(descriptor)) != snapshot[-1][1]):
                raise _UnsafeWorktreePath("worktree target changed before access")
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    return open(path, mode, encoding="utf-8", newline=None if mode == "r" else "\n",
                opener=checked_opener)


def main() -> int:
    ap = argparse.ArgumentParser(description="en/em dash guard for public repo prose")
    ap.add_argument("--repo", default=".")
    action = ap.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true", help="check without writing (default)")
    action.add_argument("--fix", action="store_true", help="rewrite offending files in place")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--staged", action="store_true")
    g.add_argument("--tree", action="store_true")
    ap.add_argument("--added-only", action="store_true",
                    help="report only lines the staged diff ADDS (implies --staged); for trees "
                         "with standing violations that are not being retroactively cleaned")
    ap.add_argument("paths", nargs="*", help="explicit files; --staged still reads index content")
    args = ap.parse_args()

    # --fix rewrites whole files, so pairing it with --added-only would silently clean the standing
    # lines the mode exists to leave alone. Refuse rather than pick one of the two meanings.
    if args.added_only and args.fix:
        print("dash_guard: --added-only cannot be combined with --fix. --fix rewrites the whole "
              "file, which would also rewrite the standing lines --added-only exists to skip.",
              file=sys.stderr)
        return 2
    if args.added_only:
        if args.tree:
            ap.error("--added-only cannot be combined with --tree")
        args.staged = True
    if args.staged and args.fix:
        ap.error("--staged cannot be combined with --fix; fix the worktree and stage the result")

    repo = os.path.abspath(args.repo)
    explicit_files = args.paths
    if args.staged:
        # Git's staged names are relative to the repository root, even with -C in a subdirectory.
        explicit_files = [os.path.abspath(os.path.join(repo, path)) for path in args.paths]
        repo = os.path.abspath(_git(repo, "rev-parse", "--show-toplevel").removesuffix("\n"))
    enumerated = None                 # how many paths git named, before the extension filter
    source = "paths"
    if args.paths:
        files = explicit_files
    elif args.staged:
        source = "staged"
        all_paths, files = _staged(repo)
        enumerated = len(all_paths)
    else:
        source = "tree"
        all_paths, files = _tracked(repo)
        enumerated = len(all_paths)

    # A git repo that enumerates nothing is possible (a fresh init, an empty staged set) but it is
    # NOT the same event as a clean scan, and until now the two printed the same line. Say which.
    if source == "tree" and enumerated == 0:
        print("dash_guard: WARNING %s is a git repo but tracks 0 files -- nothing was examined."
              % repo, file=sys.stderr)
    elif enumerated and not files:
        print("dash_guard: NOTE %d %s path(s), none with a de-dashable extension (%s)."
              % (enumerated, source, " ".join(sorted(_KIND))), file=sys.stderr)

    total = 0
    changed_files = 0
    repaired_lines = 0
    examined = 0
    # Two different things, kept apart because only one of them is a problem:
    #   excluded  -- we CHOSE not to read this file (the guard's own source, a sparse tree path). A
    #                declared exclusion is a decision, and a decision does not fail a run.
    #   unexamined -- we MEANT to read it and could not (undecodable bytes, source the tokenizer
    #                rejects). The file may be full of dashes and nobody looked. Both are printed;
    #                only this one affects an exit code.
    excluded = []                     # (path, reason)
    unexamined = []                   # (path, reason)
    # The guard's own source carries the dash set by design, so it is exempt -- but keyed on the
    # vendored PATH, not on the basename. A basename rule means `git mv prose.md tools/../
    # dash_guard.py`, or simply any file called dash_guard.py in any directory, is exempt from the
    # check. pii_guard had the identical hole and it was worth more there; the shape is the same
    # and so is the fix. A legitimate copy at a non-standard path proves what it is by carrying
    # the marker, rather than by being on a list of blessed locations.
    _self_paths = {"tools/dash_guard.py", "tools/test_dash_guard.py",
                   "dash_guard.py", "test_dash_guard.py"}
    _self_marker = "dash-guard:scanner-file"
    for rel in files:
        path = rel if os.path.isabs(rel) else os.path.join(repo, rel)
        if not args.staged:
            try:
                snapshot = _worktree_snapshot(path)
                is_file = snapshot is not None
            except (FileNotFoundError, NotADirectoryError):
                is_file = False
            except _UnsafeWorktreePath as error:
                unexamined.append((rel, str(error)))
                continue
            except (OSError, ValueError) as error:
                unexamined.append((rel, "metadata unavailable (%s)" % type(error).__name__))
                continue
            if not is_file:
                missing = unexamined if args.paths else excluded
                missing.append((rel, "not a file on disk (sparse checkout, or removed)"))
                continue
        _rel = _index_path(repo, rel) if args.staged else os.path.relpath(path, repo).replace(os.sep, "/")
        try:
            if args.staged:
                text = _index_text(repo, _rel)
            else:
                with _open_worktree(path, "r", snapshot) as source_file:
                    text = source_file.read()
                    if (_worktree_snapshot(path) != snapshot or
                            _worktree_stamp(os.fstat(source_file.fileno())) != snapshot[-1][1]):
                        raise _UnsafeWorktreePath("worktree target changed during read")
        except (UnicodeDecodeError, OSError, ValueError) as e:
            # Unchanged behaviour: an undecodable or unreadable file is skipped. It is now RECORDED,
            # because "skipped" reported as "clean" is the same class of lie as the git fail-open.
            unexamined.append((rel, "unreadable (%s)" % type(e).__name__))
            continue
        if _rel in _self_paths or (os.path.basename(_rel) in
                                   {"dash_guard.py", "test_dash_guard.py"}
                                   and _self_marker in text):
            excluded.append((rel, "the guard's own source (contains the dash set by design)"))
            continue
        kind = _KIND.get(os.path.splitext(path)[1].lower())
        if kind is None:
            excluded.append((rel, "no de-dash rule for this extension"))
            continue
        examined += 1
        if not _DASH_RE.search(text):
            continue
        notes = []
        new_text, hits = process_text(text, kind, notes)
        for n in notes:                       # e.g. a .py the tokenizer could not parse
            unexamined.append((rel, n))
            examined -= 1
        if args.added_only and hits:
            added = added_line_numbers(repo, _rel)
            if added is None:
                # Could not determine the added range. Keep every hit and say so: narrowing on a
                # failed parse would turn "we could not tell" into "nothing was added".
                unexamined.append((rel, "added-line range unavailable; reported the whole file"))
            else:
                hits = [h for h in hits if h[0] in added]
        if not hits:
            continue
        total += len(hits)
        if args.fix:
            if new_text != text:
                try:
                    with _open_worktree(path, "w", snapshot) as output_file:
                        if (_worktree_snapshot(path) != snapshot or
                                _worktree_stamp(os.fstat(output_file.fileno())) != snapshot[-1][1]):
                            raise _UnsafeWorktreePath("worktree target changed before repair")
                        output_file.write(new_text)
                        output_file.truncate()
                except (OSError, ValueError) as error:
                    unexamined.append((rel, "could not repair (%s)" % type(error).__name__))
                    continue
                changed_files += 1
                repaired_lines += len(hits)
                print(f"fixed {len(hits):3} {os.path.relpath(path, repo)}")
        else:
            for lineno, line in hits:
                print(f"{os.path.relpath(path, repo)}:{lineno}: {line.strip()[:100]}")

    # Print both lists BEFORE the verdict, in both modes. A file carrying a dash that the tokenizer
    # rejected is exactly the file this guard exists for, and it used to vanish without a word.
    def _report(label, rows):
        if not rows:
            return
        print("dash_guard: %d file(s) %s:" % (len(rows), label), file=sys.stderr)
        for rel, why in rows[:20]:
            print("  %-52s %s" % (rel, why), file=sys.stderr)
        if len(rows) > 20:
            print("  ... and %d more" % (len(rows) - 20), file=sys.stderr)

    _report("deliberately excluded", excluded)
    _report("could NOT be examined", unexamined)

    if args.fix:
        print(f"dash_guard: fixed {repaired_lines} line(s) across {changed_files} file(s); "
              f"{examined} file(s) examined")
        # --fix is a REPAIR, not a gate, and its exit code is deliberately not a verdict on the
        # tree: it just rewrote the tree, so "0 remaining findings" would be true by construction
        # and would let `dash_guard --fix` be wired into CI as a gate that can never fail. The gate
        # is --check, and only --check. What --fix DOES report nonzero is the one thing it cannot
        # honestly claim to have repaired: files it could not read. Those still hold whatever they
        # held, and a repair run that silently left them behind is the same silent-success bug.
        if unexamined:
            print("dash_guard: --fix could not examine %d file(s) (listed above); re-run --check "
                  "to gate." % len(unexamined), file=sys.stderr)
            return 1
        return 0
    if total:
        print(f"dash_guard: {total} prose en/em dash(es) found (run with --fix)", file=sys.stderr)
    skipped = len(excluded) + len(unexamined)
    if unexamined:
        print(f"dash_guard: incomplete ({examined} file(s) examined, {skipped} skipped)")
        return 1
    if total:
        return 1
    # The verdict states its own coverage. "dash_guard: clean" on its own is the identical string
    # whether 400 files were read or none were, which is precisely how the fail-open stayed hidden.
    print(f"dash_guard: clean ({examined} file(s) examined"
          + (f", {skipped} skipped)" if skipped else ")"))
    return 0


def cli():
    """main() with the git-failure exit. 0 clean, 1 findings, 2 the scan never ran. Any nonzero is
    a block for the hook and for CI: an unexamined tree is not a clean tree."""
    try:
        return main()
    except GitError as e:
        print("dash_guard: SCAN FAILED -- git could not be used, so NOTHING was examined.\n"
              "  %s\n"
              "  This is not a clean result. Fix git, or point --repo at a real work tree."
              % str(e).replace("\n", "\n  "), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(cli())
