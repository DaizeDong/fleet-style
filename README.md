# fleet-style

Two house gates that are not about security, kept in one place and consumed as a git submodule.

[![Git Submodule](https://img.shields.io/badge/Git%20Submodule-Style%20Kit-orange?style=flat)](#install)
[![Gates](https://img.shields.io/badge/Gates-2-green?style=flat)](#gates-at-a-glance)
[![Languages](https://img.shields.io/badge/Languages-EN%20%2F%20CN-blue?style=flat)](#languages)
[![Roadmap](https://img.shields.io/badge/Roadmap-v0.1.0-purple?style=flat)](ROADMAP.md)

[English](README.md) | [中文版](README_CN.md)

---

## ⭐ Read this first, the design philosophy

Three commitments shape this kit, and they matter more than the two rules it enforces.

**A scan that never ran is not a clean scan.** Both tools refuse to confuse "nothing was
found" with "nothing was examined". `dash_guard` exits 2 when git is unusable or the
directory is not a work tree, rather than enumerating zero files and printing clean.
`load_budget` exits 3 when it locates no skill to measure, rather than reporting a state.
Every CI step here fails on a missing scanner instead of skipping it, because an empty
`style/` directory left by a clone without `--recursive` reads exactly like a gate that
passed.

**A gate that cannot fail is not a gate.** Each action runs the guard's own tests before
it runs the guard, and each guarantee in those tests is paired with a negative control:
an over budget `SKILL.md` that must exit 1, a duplicated paragraph that must exit 1, a
threshold flipped across the same fixture that must flip the verdict. The rule comes from
this repository's own history, where half of `load_budget` blocked nothing while printing
`ok`.

**One copy, pinned, never vendored.** These tools were copied by hand into every repository
that wanted them, and copies drift silently. A submodule replaces the hand written list of
repositories with a pointer that lives in the consumer, and the consumer decides when the
pointer moves.

## What it is (and isn't)

It is a git submodule holding two scanners, their tests and two composite GitHub Actions.
`dash_guard` enforces the house rule that published prose carries no en dash, em dash or
horizontal bar, while leaving the ASCII hyphen alone because that is code syntax.
`load_budget` measures what a `SKILL.md` costs on every invocation and how much of it is
prose duplicated from an on demand reference.

It is **not** a Claude Code skill or plugin, and it ships no `SKILL.md`: it is a submodule
you add to a repository and call from CI. It is **not** the security kit. `fleet-guards`
exists to keep a real identifier out of a public history, and nothing here does that; these
two catch a style rule and an architecture rule instead. It is **not** wired to
`core.hooksPath`, because that setting points at one directory and that directory belongs
to the gates standing between an identifier and a public push.

Keeping the two kits apart also keeps their answers apart. Every public repository needs
the security gates. A repository with no `SKILL.md` has nothing for the load budget to
measure, and says so on every run.

## Install

```bash
git submodule add -b main https://github.com/DaizeDong/fleet-style.git style
```

Then in each workflow that wants a gate:

```yaml
- uses: actions/checkout@v4
  with: {submodules: true}
- uses: actions/setup-python@v5
  with: {python-version: '3.x'}
- uses: ./style/ci/dash-guard        # or ./style/ci/load-budget
```

Moving the pin:

```bash
git -C style fetch && git -C style checkout <sha>
```

then commit the new pointer. A submodule pins one commit. Consumers may also enroll in
[automatic synchronization](docs/AUTOMATIC_SYNC.md): once the source workflow passes, a
dispatch event advances the pin through the consumer's normal commit gates.

## Quick start

Run either tool directly against the repository that consumes it:

```bash
python style/tools/dash_guard.py --tree      # every tracked text file
python style/tools/dash_guard.py --staged    # the staged blobs only
python style/tools/dash_guard.py --fix FILE  # deterministic repair, not a gate
python style/tools/load_budget.py .          # the always loaded budget
```

To check that the commit you pinned still passes here, ask for this kit's suite by path:

```bash
pytest style/tools/
```

A bare `pytest` at the consumer's root does not collect it. `conftest.py` keeps these tests
out of a consumer's count, because several repositories in this fleet gate on a minimum
test count and a floor met by unrelated tests is a floor that says nothing.

## Gates at a glance

| Gate | What it asserts | Exit codes |
| --- | --- | --- |
| `tools/dash_guard.py` | Published prose carries no en dash, em dash or horizontal bar. Markdown fences and inline code spans are exempt, a line marked `dash-guard: allow` is exempt, and the scanner's own source is exempt by name because it carries the dash set as data. | 0 clean, 1 findings, 2 the scan could not run |
| `tools/load_budget.py` | A skill's always loaded lines stay under budget, and prose in `SKILL.md` is not a second copy of prose in a reference. Duplication is detected with word shingles, so a rule's own wording appearing in the reference that elaborates it does not trip it. | 0 within budget, 1 over budget, 3 nothing was measured |

| CI action | Wiring |
| --- | --- |
| `ci/dash-guard` | Installs pytest, runs `tools/test_dash_guard.py`, then scans the calling repository's tree. |
| `ci/load-budget` | Installs pytest, fails if `tools/test_load_budget.py` is absent, runs it, then measures the calling repository. |

## How it runs

The gates run in CI, on the calling repository, and nowhere else. They scan the current
tree and never the history: a dash in an old commit is harmless and is not worth rewriting
a history for, which is the sharpest difference between this kit and the security one.

This repository runs its own gates through its own actions. `.github/workflows/style.yml`
calls `./ci/dash-guard`, so a break shows up here before it reaches a consumer. There is no
load budget job in it, because this repository declares no skill and the tool would exit 3
on every commit.

## Example output

```
$ python tools/dash_guard.py --tree
dash_guard: 2 file(s) deliberately excluded:
  tools/dash_guard.py                    the guard's own source (contains the dash set by design)
  tools/test_dash_guard.py               the guard's own source (contains the dash set by design)
dash_guard: clean (9 file(s) examined, 2 skipped)
```

```
$ python tools/load_budget.py .
load_budget: FAIL, measured NOTHING under /path/to/fleet-style
  looked for: skills/*/SKILL.md and SKILL.md at the root
  This repo declares no skill (no .claude-plugin/plugin.json, no skills/, no root
  SKILL.md), so load_budget has nothing here to guard. Drop tools/load_budget.py
  from it rather than letting an inert gate report a result.
```

The second one is the design working. A repository with nothing to measure is told to stop
carrying the gate, instead of collecting a green check that means nothing.

## Limitations

Neither gate protects a history. Both read the tree as it is now, so a violation already in
an old commit stays there. Neither gate is a hook here, so a consumer that only runs them
in CI learns about a violation after the push rather than before it. `dash_guard --fix`
rewrites files in place and is deliberately not usable as a gate: it exits 0 after a
successful repair, so wiring it into CI installs a check that cannot fail. And
`load_budget` only understands two repository shapes, `skills/*/SKILL.md` and a `SKILL.md`
at the root; anything else is reported as nothing measured.

## Languages

English (`README.md`) · 中文 (`README_CN.md`)

## Roadmap · Contributing · License

See [ROADMAP.md](ROADMAP.md) · [CHANGELOG.md](CHANGELOG.md).

The deviations from the house repository spec, and the reason for each, are recorded in
[docs/2026-09-22-spec-adaptation.md](docs/2026-09-22-spec-adaptation.md).
