#!/usr/bin/env python3
# dash-guard:scanner-file -- this file carries the dash set by design; see _self_marker
"""dash_guard: flag / fix en-dash and em-dash used as prose in a public repo.

House rule (user global): published prose carries NO en/em dash. The ASCII hyphen `-` is left
ALONE (it is code syntax: identifiers, flags, file names, versions, URLs, ranges in code), so this
guard only touches the en-dash U+2013, em-dash U+2014 and horizontal bar U+2015. None of those
three ever appear in code SYNTAX, so every occurrence outside a code span is prose and is a target.

Modes (exactly one action):
  --check  (default) print every offending file:line; exit 1 if any (pre-commit / CI gate)
  --fix              rewrite the offending files in place. NOT a gate: see the note at the end of
                     main(). It exits 0 after a successful repair and 1 only for files it could not
                     read, so wiring --fix into CI would install a check that cannot fail.

Exit codes: 0 clean, 1 findings (or, under --fix, unexaminable files), 2 the scan could not run at
all (git unusable / not a work tree). 2 must never be read as 0; see _git.

Target set:
  --staged           the git staged text blobs (pre-commit hook)
  --tree   (default) every git-tracked text file
  paths...           explicit files (overrides the set)
  --message FILE     one commit message (the subject and body; git's own `#` lines and everything
                     under a scissors line are ignored). Its findings are kind "message".

Finding kinds and their policy (2026-09-25, report-only rollout):
  md, prose, py      BLOCK. Unchanged: these are the kinds every consumer has been clean on.
  js                 REPORT. `//` and `/* */` comments in .js/.mjs/.cjs/.jsx/.ts/.mts/.cts/.tsx.
                     String, template and regex literals are code and are never examined.
  yaml               REPORT. `#` comments in .yml/.yaml (workflows, actions). Scalars are not
                     examined yet, including prose ones such as `description:`; comments only.
  sh, ps, cmd        REPORT. Shell `#` comments (.sh/.bash/.zsh and extensionless files whose
                     shebang names a shell), PowerShell `#` and `<# #>` comments (.ps1/.psm1/.psd1),
                     and cmd `rem` / `::` lines (.cmd/.bat). Quoted strings and heredoc bodies are
                     data and are skipped.
  message            REPORT. --message.
  unexamined         REPORT. A file the guard meant to read and could not (undecodable bytes,
                     source the tokenizer rejects). It used to be printed and then ignored by the
                     verdict; it is now a counted finding like any other.
A REPORT finding is printed with its kind and counted on the verdict line, and does not change the
exit code. `--block-kinds js,yaml` (or `all`) promotes kinds to BLOCK; the CI action passes its
`block-kinds` input through. The default set of blocking kinds is exactly the set that existed
before this rollout, so pinning this version changes no consumer's verdict. `--fix` never rewrites
the report kinds: there is no fixer for them yet, and a repair that edits code files deserves its
own review before it exists.

Markdown safety: fenced ``` code blocks and inline `code` spans are skipped, so a dash shown as a
literal example survives. In every other text file each en/em dash is treated as prose.

Replacement (deterministic):
  markdown table cell that is ONLY a dash  -> "none"  (the cell means "no value", not an aside)
  markdown table cell STARTING with a dash -> ASCII "-" (a sub-item marker, not an aside)
  spaced   ` — ` / ` – `                 -> ", "   (appositive / aside; never grammatically wrong)
  ASCII range  A-B  (ONE dash, short token both sides) -> "A to B"  (e.g. T1-T9, 2020-2026)
  any leftover run  —— / – / ―           -> "," glued to the preceding word (never " ,")

Why the table rules exist: a table cell holding a single long dash is the conventional way to write
"no default". Substituting punctuation there produced cells reading "," or ", something", which is
not prose at all, and NO gate can see it afterwards because the output contains no dash. The cell
rules run before the prose rules so a dash that is a value never reaches the appositive rule.
"""
from __future__ import annotations

import argparse
import bisect
import io
import os
import re
import subprocess
import sys
import tokenize

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
         ".tmpl": "md",
         # Comment-only kinds (report by default, see the module docstring). Only the COMMENT text
         # is examined; every literal is code.
         ".js": "js", ".mjs": "js", ".cjs": "js", ".jsx": "js",
         ".ts": "js", ".mts": "js", ".cts": "js", ".tsx": "js",
         ".yml": "yaml", ".yaml": "yaml",
         ".sh": "sh", ".bash": "sh", ".zsh": "sh",
         ".ps1": "ps", ".psm1": "ps", ".psd1": "ps",
         ".cmd": "cmd", ".bat": "cmd"}

# Policy. BLOCKING_DEFAULT is frozen at the kinds that existed before the report-only rollout, so a
# consumer that pins this version gets byte-identical exit codes. Every other kind reports.
BLOCKING_DEFAULT = frozenset({"md", "prose", "py"})
REPORT_KINDS = ("js", "yaml", "sh", "ps", "cmd", "message", "unexamined")
ALL_KINDS = tuple(sorted(BLOCKING_DEFAULT)) + REPORT_KINDS
_COMMENT_KINDS = frozenset({"js", "yaml", "sh", "ps", "cmd"})
# An extensionless file is examined only when its shebang names one of these interpreters.
_SHELL_SHEBANG = re.compile(rb"^#![^\n]*\b(?:ba|z|da|k)?sh\b")


def parse_block_kinds(spec):
    """'js,yaml' / 'all' / '' -> the full set of blocking kinds. An unknown name raises ValueError:
    a typo in a promotion must not quietly leave the gate report-only."""
    kinds = set(BLOCKING_DEFAULT)
    for name in (spec or "").replace(" ", "").split(","):
        if not name:
            continue
        if name == "all":
            kinds.update(ALL_KINDS)
        elif name in ALL_KINDS:
            kinds.add(name)
        else:
            raise ValueError("unknown kind %r (known: %s, all)" % (name, ", ".join(ALL_KINDS)))
    return frozenset(kinds)

_SPACED = re.compile(rf"\s+[{_DASHES}]+\s+")
# A range is a SINGLE dash between two SHORT alphanumeric tokens: 2020-2026, T1-T9, A-Z.
# Both limits are load-bearing. Without the single-dash requirement the Chinese pause
# `attach——attach` is read as a range and rewritten to "attach to attach", which is not a
# typographic change but a false sentence; measured on a real repository. Without the token
# length limit the same thing happens to a single dash between two words. Anything wider
# falls through to the leftover-run rule, which turns it into a comma and never invents a
# word that was not there.
_RANGE = re.compile(
    rf"(?<![A-Za-z0-9])([A-Za-z0-9]{{1,4}})[{_DASHES}]([A-Za-z0-9]{{1,4}})(?![A-Za-z0-9])"
)
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
_CELL_DASH_ONLY = re.compile(rf"(?<=\|)\s*[{_DASHES}]+\s*(?=\||\r?$)")
# A cell that OPENS with a dash run followed by text: a sub-item marker, so it becomes an ASCII
# hyphen (which this guard never touches) and keeps the indent it was drawing.
_CELL_DASH_LEAD = re.compile(rf"(?<=\|)(\s*)[{_DASHES}]+(?=[ \t]\S)")


def fix_table_cells(line: str) -> str:
    """Rewrite dash-as-value cells in one markdown table row, before any prose rule sees them."""
    if not _TABLE_ROW.match(line) or line.count("|") < 2:
        return line

    def _cell(m):
        rest = m.string[m.end():]                       # no trailing pad on the last cell of a row
        return f" {NO_VALUE} " if rest.startswith("|") else f" {NO_VALUE}"

    line = _CELL_DASH_ONLY.sub(_cell, line)
    return _CELL_DASH_LEAD.sub(r"\1-", line)


def _split_md_code(line: str, in_fence: bool):
    """Yield (segment, is_code) for a markdown line, protecting inline `code`. `in_fence` marks a
    line inside a ``` fenced block (entirely code). Returns (segments, new_in_fence)."""
    stripped = line.lstrip()
    if stripped.startswith("```") or stripped.startswith("~~~"):
        return [(line, True)], (not in_fence)
    if in_fence:
        return [(line, True)], True
    # protect inline code spans (`...`)
    segs = []
    for part in re.split(r"(`[^`]*`)", line):
        segs.append((part, part.startswith("`") and part.endswith("`") and len(part) >= 2))
    return segs, False


_ALLOW = "dash-guard: allow"       # a line carrying this marker is left untouched (rare legit dash)


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


# --- comment-only kinds (report by default) ---------------------------------------------------
# Each lexer returns the (start, end) character spans that are COMMENTS. Everything else, above all
# every string, template and regex literal, is code: a JS test that asserts on "a — b", or a
# regex character class listing the dash set, must never be read as prose. These are small
# hand-written lexers, not parsers. When one guesses wrong it can only move a dash between
# "comment" and "code", and the kinds they serve are report-only until each has been measured.

_REGEX_PREFIX_WORDS = frozenset({"return", "typeof", "instanceof", "in", "of", "new", "delete",
                                 "void", "throw", "case", "do", "else", "yield", "await"})
_REGEX_PREFIX_PUNCT = set("(,=:[!&|?{};+-*%<>~^")


def _js_comment_spans(text):
    spans, n, i = [], len(text), 0
    stack = []            # "tmpl" = inside a template body; int = brace depth of a ${ } expression
    prev, prev_word = "", ""
    while i < n:
        c = text[i]
        if stack and stack[-1] == "tmpl":
            if c == "\\":
                i += 2
            elif c == "`":
                stack.pop()
                prev, prev_word = "`", ""
                i += 1
            elif text.startswith("${", i):
                stack.append(0)
                prev, prev_word = "{", ""
                i += 2
            else:
                i += 1
            continue
        if c in " \t\r\n":
            i += 1
            continue
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            spans.append((i, j))
            i = j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            spans.append((i, j))
            i = j
            continue
        if c in "'\"":
            j = i + 1
            while j < n and text[j] not in (c, "\n"):
                j += 2 if text[j] == "\\" else 1
            i, prev, prev_word = j + 1, "a", ""
            continue
        if c == "`":
            stack.append("tmpl")
            i += 1
            continue
        if c == "/" and (prev == "" or prev in _REGEX_PREFIX_PUNCT
                         or (prev == "a" and prev_word in _REGEX_PREFIX_WORDS)):
            j, in_class = i + 1, False
            while j < n and text[j] != "\n":
                ch = text[j]
                if ch == "\\":
                    j += 2
                    continue
                if ch == "[":
                    in_class = True
                elif ch == "]":
                    in_class = False
                elif ch == "/" and not in_class:
                    break
                j += 1
            i = j + 1
            while i < n and text[i].isalnum():
                i += 1                                   # regex flags
            prev, prev_word = "a", ""
            continue
        if stack and isinstance(stack[-1], int):
            if c == "{":
                stack[-1] += 1
            elif c == "}":
                if stack[-1] == 0:
                    stack.pop()                          # back into the template body
                    i += 1
                    continue
                stack[-1] -= 1
        if c.isalnum() or c in "_$":
            j = i
            while j < n and (text[j].isalnum() or text[j] in "_$"):
                j += 1
            prev, prev_word, i = "a", text[i:j], j
            continue
        prev, prev_word = c, ""
        i += 1
    return spans


_HEREDOC = re.compile(r"<<(-?)[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")


def _hash_line_comment(line, quote_anywhere, escape):
    """Column where a `#` comment starts in one line, or -1. A `#` opens a comment only at the start
    of a word (line start, or after a blank or ; & | ( ), so `$#`, `${#x}` and `a#b` are code.
    Quotes are tracked within the line. quote_anywhere=False (YAML) opens a quote only at the start
    of a token, so the apostrophe in a plain scalar such as `don't` is not a quote."""
    q = None
    k, n = 0, len(line)
    while k < n:
        ch = line[k]
        if q:
            if ch == escape and q == '"' and k + 1 < n:
                k += 2
                continue
            if ch == q:
                q = None
        elif ch == escape and escape and k + 1 < n:
            k += 2
            continue
        elif ch in "'\"" and (quote_anywhere or k == 0 or line[k - 1] in " \t:[{,-"):
            q = ch
        elif ch == "#" and (k == 0 or line[k - 1] in " \t;&|("):
            return k
        k += 1
    return -1


def _line_spans(text, kind):
    """Comment spans for the line-oriented kinds: yaml, sh, ps, cmd."""
    spans, pos = [], 0
    heredoc = None            # (terminator, strip_tabs) while inside a shell heredoc body
    ps_block = False          # inside a PowerShell <# ... #> block comment
    ps_here = None            # closing token of a PowerShell here-string, '@ or "@
    for raw in text.split("\n"):
        line_start, line = pos, raw.rstrip("\r")
        pos += len(raw) + 1
        if kind == "cmd":
            if re.match(r"^\s*@?\s*(?:rem(?:\s|$)|::)", line, re.I):
                spans.append((line_start, line_start + len(line)))
            continue
        if heredoc:
            body = line.lstrip("\t") if heredoc[1] else line
            if body == heredoc[0]:
                heredoc = None
            continue
        if ps_here:
            if line.startswith(ps_here):
                ps_here = None
            continue
        if ps_block:
            end = line.find("#>")
            spans.append((line_start, line_start + (len(line) if end < 0 else end + 2)))
            ps_block = end < 0
            continue
        if kind == "ps":
            st = line.lstrip()
            if st.startswith("<#"):
                end = line.find("#>", line.find("<#") + 2)
                s = line_start + line.find("<#")
                spans.append((s, line_start + (len(line) if end < 0 else end + 2)))
                ps_block = end < 0
                continue
            if line.rstrip().endswith(("@'", '@"')):
                ps_here = line.rstrip()[-1] + "@"
            col = _hash_line_comment(line, True, "`")
        elif kind == "sh":
            col = _hash_line_comment(line, True, "\\")
            code = line if col < 0 else line[:col]
            m = _HEREDOC.search(code)
            if m and "<<<" not in code:
                heredoc = (m.group(3), m.group(1) == "-")
        else:                                            # yaml
            col = _hash_line_comment(line, False, "\\")
        if col >= 0:
            spans.append((line_start + col, line_start + len(line)))
    return spans


def _process_comments(text, kind):
    """Hits for a comment-only kind: every line holding a dash INSIDE a comment span. The text is
    returned unchanged; these kinds have no fixer."""
    spans = _js_comment_spans(text) if kind == "js" else _line_spans(text, kind)
    if not spans:
        return text, []
    starts = [s for s, _ in spans]
    lines = text.split("\n")
    line_starts, p = [], 0
    for ln in lines:
        line_starts.append(p)
        p += len(ln) + 1
    hit_lines = set()
    for m in _DASH_RE.finditer(text):
        k = bisect.bisect_right(starts, m.start()) - 1
        if k >= 0 and spans[k][0] <= m.start() < spans[k][1]:
            hit_lines.add(bisect.bisect_right(line_starts, m.start()))
    hits = [(no, lines[no - 1]) for no in sorted(hit_lines) if _ALLOW not in lines[no - 1]]
    return text, hits


_SCISSORS = re.compile(r"^# -+ >8 -+$")


def message_text(raw):
    """The part of a commit message a reader sees: git's `#` lines blanked (not removed, so line
    numbers still match the file) and everything from a scissors line on dropped."""
    out = []
    for ln in raw.split("\n"):
        if _SCISSORS.match(ln.rstrip("\r")):
            break
        out.append("" if ln.startswith("#") else ln)
    return "\n".join(out)


def process_text(text: str, kind: str, notes=None):
    """Return (new_text, hits) where hits = list of (lineno, original_line).
    kind: "py" (comments only), "md" (prose, code spans exempt), "prose" (plain text, full),
    "message" (a commit message, as prose), or a comment-only kind (js, yaml, sh, ps, cmd).
    notes: optional list; anything appended is a reason this file was not fully examined."""
    if kind == "py":
        return _process_py(text, notes)
    if kind in _COMMENT_KINDS:
        return _process_comments(text, kind)
    if kind == "message":
        kind = "prose"
    is_md = (kind == "md")
    out_lines, hits, in_fence = [], [], False
    for lineno, line in enumerate(text.split("\n"), 1):
        if _ALLOW in line:
            out_lines.append(line)
            continue
        if is_md:
            # Table cells first: a dash that IS the value must never reach the appositive rule.
            work = line if in_fence else fix_table_cells(line)
            segs, in_fence = _split_md_code(work, in_fence)
            new_parts = []
            for part, is_code in segs:
                new_parts.append(part if is_code else fix_prose(part))
            new_line = "".join(new_parts)
            if new_line != line:
                hits.append((lineno, line))
            out_lines.append(new_line)
        else:
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
    out = _git(repo, "diff", "--cached", "-U0", "--", path, allow_fail=True)
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


def _git(repo, *a, allow_fail=False):
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
        r = subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
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
                          (r.stderr or "").strip().replace("\n", "\n  ") or "(no stderr)"))
    return r.stdout


def _shebang_kind(path):
    """'sh' for an extensionless file whose first line is a shell shebang, else None. Git hooks and
    installers are the usual case, and they are exactly where shell comments hold prose."""
    try:
        with open(path, "rb") as f:
            head = f.read(128)
    except OSError:
        return None
    return "sh" if _SHELL_SHEBANG.match(head) else None


def _kind_of(path):
    ext = os.path.splitext(path)[1].lower()
    if ext:
        return _KIND.get(ext)
    return _shebang_kind(path)


def _eligible(paths, repo=None):
    out = []
    for f in paths:
        ext = os.path.splitext(f)[1].lower()
        if ext in _KIND:
            out.append(f)
        elif not ext and repo is not None and _shebang_kind(os.path.join(repo, f)):
            out.append(f)
    return out


def _tracked(repo):
    """(all tracked paths, the ones with a de-dashable extension). Both are returned so main can
    tell 'this repo tracks nothing' from 'this repo tracks no markdown/text/python'."""
    # -z: see the note in pii_guard.tracked_files. Without it a non-ASCII path arrives as a
    # C-quoted escape string that opens nothing, and it vanishes from BOTH the examined and the
    # skipped tally, so the clean line does not even admit something went unread.
    all_paths = [p for p in _git(repo, "ls-files", "-z").split("\0") if p]
    return all_paths, _eligible(all_paths, repo)


def _staged(repo):
    out = _git(repo, "diff", "--cached", "--name-only", "--diff-filter=ACM")
    all_paths = [f for f in out.splitlines() if f.strip()]
    return all_paths, _eligible(all_paths, repo)


def _print_rows(label, rows):
    if not rows:
        return
    print("dash_guard: %d file(s) %s:" % (len(rows), label), file=sys.stderr)
    for rel, why in rows[:20]:
        print("  %-52s %s" % (rel, why), file=sys.stderr)
    if len(rows) > 20:
        print("  ... and %d more" % (len(rows) - 20), file=sys.stderr)


def _counts_text(counts):
    return " ".join("%s=%d" % (k, counts[k]) for k in ALL_KINDS if counts.get(k))


def _check_message(path, blocking):
    """--message: one commit message, kind "message". 2 when the file cannot be read, because a
    message nobody read is not a clean message."""
    try:
        raw = open(path, encoding="utf-8").read()
    except (UnicodeDecodeError, OSError) as e:
        print("dash_guard: SCAN FAILED -- cannot read the commit message %s (%s)."
              % (path, type(e).__name__), file=sys.stderr)
        return 2
    _, hits = process_text(message_text(raw), "message")
    gate = "message" in blocking
    for lineno, line in hits:
        tag = "" if gate else "[report message] "
        print(f"{path}:{lineno}: {tag}{line.strip()[:100]}")
    if hits and gate:
        print(f"dash_guard: {len(hits)} en/em dash(es) in the commit message", file=sys.stderr)
        return 1
    if hits:
        print(f"dash_guard: clean (1 commit message examined); {len(hits)} report-only "
              f"finding(s) not gated: message={len(hits)}")
        return 0
    print("dash_guard: clean (1 commit message examined)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="en/em dash guard for public repo prose")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--fix", action="store_true", help="rewrite offending files in place")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--staged", action="store_true")
    g.add_argument("--tree", action="store_true")
    g.add_argument("--message", metavar="FILE",
                   help="check one commit message file (kind 'message', report-only by default)")
    ap.add_argument("--added-only", action="store_true",
                    help="report only lines the staged diff ADDS (implies --staged); for trees "
                         "with standing violations that are not being retroactively cleaned")
    ap.add_argument("--block-kinds", default="", metavar="KINDS",
                    help="comma list of report-only kinds to promote to blocking, or 'all' "
                         "(kinds: %s)" % ", ".join(REPORT_KINDS))
    ap.add_argument("paths", nargs="*", help="explicit files (overrides --staged/--tree)")
    args = ap.parse_args(argv)

    try:
        blocking = parse_block_kinds(args.block_kinds)
    except ValueError as e:
        print("dash_guard: --block-kinds: %s" % e, file=sys.stderr)
        return 2

    # --fix rewrites whole files, so pairing it with --added-only would silently clean the standing
    # lines the mode exists to leave alone. Refuse rather than pick one of the two meanings.
    if args.added_only and args.fix:
        print("dash_guard: --added-only cannot be combined with --fix. --fix rewrites the whole "
              "file, which would also rewrite the standing lines --added-only exists to skip.",
              file=sys.stderr)
        return 2
    if args.message:
        if args.fix or args.added_only or args.paths:
            print("dash_guard: --message checks one message and takes no --fix, --added-only or "
                  "paths.", file=sys.stderr)
            return 2
        return _check_message(args.message, blocking)
    if args.added_only:
        args.staged = True

    repo = os.path.abspath(args.repo)
    enumerated = None                 # how many paths git named, before the extension filter
    source = "paths"
    if args.paths:
        files = args.paths
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

    total = 0                         # BLOCKING hits
    report = {}                       # kind -> report-only hit count
    changed_files = 0
    examined = 0
    # Two different things, kept apart because only one of them is a problem:
    #   excluded  -- we CHOSE not to read this file (the guard's own source, an absent path). A
    #                declared exclusion is a decision, and a decision does not fail a run.
    #   unexamined -- we MEANT to read it and could not (undecodable bytes, source the tokenizer
    #                rejects). The file may be full of dashes and nobody looked. Both are printed.
    #                An unexamined file is a finding of kind "unexamined": counted on the verdict
    #                line (report-only by default), blocking under --block-kinds unexamined, and
    #                a nonzero under --fix, which cannot claim to have repaired a file it never read.
    excluded = []                     # (path, reason)
    unexamined = []                   # (path, reason)
    fix_skipped = 0                   # report-kind files --fix left alone (no fixer exists)
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
        if not os.path.isfile(path):
            excluded.append((rel, "not a file on disk (sparse checkout, or removed)"))
            continue
        _rel = rel.replace(chr(92), "/")
        while _rel.startswith("./"):
            _rel = _rel[2:]
        try:
            text = open(path, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError) as e:
            # Unchanged behaviour: an undecodable or unreadable file is skipped. It is now RECORDED,
            # because "skipped" reported as "clean" is the same class of lie as the git fail-open.
            unexamined.append((rel, "unreadable (%s)" % type(e).__name__))
            continue
        if _rel in _self_paths or (os.path.basename(_rel) in
                                   {"dash_guard.py", "test_dash_guard.py"}
                                   and _self_marker in text):
            excluded.append((rel, "the guard's own source (contains the dash set by design)"))
            continue
        kind = _kind_of(path)
        if kind is None:
            excluded.append((rel, "no de-dash rule for this extension"))
            continue
        if args.fix and kind in _COMMENT_KINDS:
            fix_skipped += 1
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
        if kind not in blocking:
            report[kind] = report.get(kind, 0) + len(hits)
            for lineno, line in hits:
                print(f"{os.path.relpath(path, repo)}:{lineno}: [report {kind}] "
                      f"{line.strip()[:100]}")
            continue
        total += len(hits)
        if args.fix:
            if new_text != text:
                open(path, "w", encoding="utf-8", newline="\n").write(new_text)
                changed_files += 1
                print(f"fixed {len(hits):3} {os.path.relpath(path, repo)}")
        else:
            for lineno, line in hits:
                print(f"{os.path.relpath(path, repo)}:{lineno}: {line.strip()[:100]}")

    # Print both lists BEFORE the verdict, in both modes. A file carrying a dash that the tokenizer
    # rejected is exactly the file this guard exists for, and it used to vanish without a word.
    _print_rows("deliberately excluded", excluded)
    _print_rows("could NOT be examined", unexamined)

    if args.fix:
        print(f"dash_guard: fixed {total} line(s) across {changed_files} file(s); "
              f"{examined} file(s) examined")
        if fix_skipped:
            print("dash_guard: --fix left %d file(s) of comment-only kinds untouched (no fixer "
                  "for js, yaml, sh, ps or cmd yet)" % fix_skipped, file=sys.stderr)
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

    blocked_unexamined = len(unexamined) if "unexamined" in blocking else 0
    if unexamined and not blocked_unexamined:
        report["unexamined"] = len(unexamined)
    rep_total = sum(report.values())
    rep_note = (f"; {rep_total} report-only finding(s) not gated: {_counts_text(report)}"
                if rep_total else "")
    if total or blocked_unexamined:
        if total:
            print(f"dash_guard: {total} prose en/em dash(es) found (run with --fix){rep_note}",
                  file=sys.stderr)
        if blocked_unexamined:
            print(f"dash_guard: {blocked_unexamined} file(s) could not be examined, and kind "
                  f"'unexamined' is blocking{'' if total else rep_note}", file=sys.stderr)
        return 1
    # The verdict states its own coverage. "dash_guard: clean" on its own is the identical string
    # whether 400 files were read or none were, which is precisely how the fail-open stayed hidden.
    # Report-only findings ride on the same line, so a clean verdict never hides that they exist.
    skipped = len(excluded) + len(unexamined)
    print(f"dash_guard: clean ({examined} file(s) examined"
          + (f", {skipped} skipped)" if skipped else ")") + rep_note)
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
