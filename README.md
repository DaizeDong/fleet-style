# fleet-style

The two house gates that are NOT about security, in one place, consumed as a git submodule.

    dash_guard    published prose carries no en/em dash (the ASCII hyphen is code syntax)
    load_budget   PHILOSOPHY P7: the always-loaded budget and the no-second-copy rule

## Why this is a separate repo from fleet-guards

fleet-guards exists to keep a real identifier out of a public history. Nothing here does that.
These two catch a house style rule and an architecture rule, and both are worth catching, but a
repo that wants the security kit should not be made to carry them: they were 17.5% of that kit and
none of it was about the thing the kit is for.

Separating them also makes the answer to "must every public repo have this" different for each,
which it always was. Every public repo needs the security gates. A repo with no SKILL.md has
nothing for the load budget to measure, and said so on every run.

## Install

    git submodule add -b main https://github.com/DaizeDong/fleet-style.git style

Then in each workflow that wants a gate:

    - uses: actions/checkout@v4
      with: {submodules: true}
    - uses: actions/setup-python@v5
      with: {python-version: '3.x'}
    - uses: ./style/ci/dash-guard        # or ./style/ci/load-budget

Hooks are NOT wired here. `core.hooksPath` can only point at one directory, and it belongs to
fleet-guards, whose hooks are the thing standing between an identifier and a public push. These
two run in CI, which cannot be skipped with `--no-verify` anyway.

## Checking files locally

    python tools/dash_guard.py --check --tree
    python tools/dash_guard.py --check --staged
    python tools/dash_guard.py --added-only

The staged modes read the index blobs, including when explicit paths are supplied. An unstaged
edit or removal cannot hide content that is about to be committed. `--added-only` checks the
added lines of that same staged version. Unreadable or untokenizable inputs produce an incomplete
result and a nonzero exit. Deliberate exclusions are listed separately with the examined count.

Use `--fix --tree` to repair worktree files, inspect the diff, and stage the changes you want.
`--fix --staged` is refused because replacing worktree files from the index would discard
unstaged edits. `--check` and `--fix` are mutually exclusive.

    python tools/make_fixtures.py --check
    python -m pytest tools/ -q

The first command verifies the generated synthetic scanner inputs. The second runs both gates'
full test suites, including controls for incomplete scans and staged content.

The scanners share Markdown code protection that respects paragraph and container boundaries.
Fenced and indented code, including code in quotes and lists, stays unchanged when fixing prose
and is excluded from duplication measurements. Inline code can span physical lines within one
paragraph. An unmatched delimiter cannot hide prose in a later block. Dependency references are
excluded when a submodule marker exists at any ancestor below the skill's reference root.

In GitHub Markdown tables, inline code stays within its own cell. An escaped pipe remains part
of that cell. Ordinary paragraphs containing pipes retain normal inline-code behavior.
The no-value and leading-item repairs also apply to recognized tables in containers and without
outer pipes, preserving their container prefixes. Literal backticks inside inline HTML or link
destinations and titles cannot open a code span over following prose. Those literal fields retain
their bytes, and code in link labels or around HTML keeps normal code-span precedence.
Duplication measurements exclude complete tables, including tables without outer pipes and
tables in quotes or lists. HTML blocks follow their own boundaries: literal backticks there do
not hide prose, while HTML inside a Markdown code block remains protected.

Link reference definitions are parsed before inline code. Their destinations and
titles remain literal, including multiline definitions in quotes and lists, and
cannot hide the next paragraph. Full, collapsed and shortcut references use the
document's defined labels. Completing a link disables enclosing link openers;
image openers retain their separate nesting rules, preserving genuine code after
an invalid nested link.

Duplication checks use those same parsed links to normalize inline, reference and
image labels. Their delimiters and targets are removed while adjacent label text
stays joined. Escaped, unresolved and rejected link syntax remains visible prose,
so a link-shaped tail cannot erase words that should be compared.

`load_budget.py --max-dup` accepts a finite percentage from 0 through 100. A decoding, discovery
or read error exits 3 and reports the affected input on stderr; it emits no partial JSON success.
Inputs must be regular files in physical directories, including the supplied root's ancestors.
Links are reported as unsupported, and
submodules are pruned before traversing their contents. Missing references still produce the
explicit `NOT CHECKED` result described by the tool.

`tools/make_fixtures.py --out DIRECTORY` writes the synthetic fixtures by basename for the shared
data-boundary check. Add `--check` to verify that directory without rewriting it.

## Moving the pin

    git -C style fetch && git -C style checkout <sha>

then commit the new pointer. A submodule pins one commit and does not follow the source on its
own, which is deliberate: a bad commit here cannot reach every consumer by itself.

## An empty style/ is not a pass

A plain `git clone` without `--recursive` leaves it EMPTY, and so does a CI checkout without
`submodules: true`. Every action here fails on a missing scanner rather than skipping, because a
gate that is not there is not a gate that passed.
