# Roadmap

Current: **v0.3.0**

## v0.3.0 (current)

Feature names only. Why each gate behaves the way it does lives in the tool docstrings, which are the single home for those rules, and what changed lives in `CHANGELOG.md`.

- `tools/dash_guard.py`: flag or repair en dash, em dash and horizontal bar in published prose, across the tracked tree, the staged blobs or explicit paths. Markdown fences, inline code spans, allow marked lines and the scanner's own source are exempt.
- `tools/dash_guard.py` report kinds: JS, YAML, shell, PowerShell and cmd comments, one commit message (`--message`), and files the guard could not read, each reported and counted without failing until promoted with `--block-kinds` or the `ci/dash-guard` input of the same name.
- `tools/load_budget.py`: measure a skill's always loaded lines against a two rung budget, and detect prose duplicated between `SKILL.md` and an on demand reference by word shingle.
- `tools/wrap_guard.py`: flag or repair hard wraps inside prose paragraphs, across the tracked tree, the staged blobs, explicit paths or a single commit message. Fences, tables, quotes, headings, badge rows, git trailers, allow marked paragraphs and the scanner's own source are exempt.
- `ci/dash-guard`, `ci/wrap-guard` and `ci/load-budget`: composite actions that run each guard's own tests first and fail on a missing scanner rather than skipping it.
- `conftest.py`: keep this kit's tests out of a consumer's collection while leaving them reachable by path.
- `.github/workflows/style.yml`: this repository runs its own dash gate through its own action.
- `.github/workflows/notify-consumers.yml` and `docs/AUTOMATIC_SYNC.md`: optional pin advancement through each consumer's normal commit gates.

## Planned

- **Python docstrings and comments are outside `wrap_guard`.** The extension map covers Markdown, plain prose and reStructuredText. A wrapped paragraph inside a docstring passes, which is a stated gap rather than a silent one: widening it means measuring recall against real sources first.

- **Promote the report kinds to blocking.** Each kind moves to the default blocking set only after a report-only run across every consumer is reviewed and the findings are cleaned. The first run, on 2026-09-25, is recorded in `CHANGELOG.md`.
- **YAML prose scalars and a fixer for the comment kinds.** `description:` and similar scalars are prose that `dash_guard` does not read yet, and the comment kinds can be flagged but not repaired. Both need measuring against real files before they exist.
- **A `commit-msg` wiring for `--message`.** The mode exists; nothing in this kit calls it at the commit boundary, for the same `core.hooksPath` reason as below.
- **Repository shapes `load_budget` does not understand.** It discovers `skills/*/SKILL.md` and a root `SKILL.md`. Every other layout reports that nothing was measured, which is the correct refusal and still a gap.
- **A test that pins the numbers written in prose.** `conftest.py` states this kit's test count in its own docstring, and nothing fails when the suite grows past it.
- **A hook path that does not fight the security kit.** `core.hooksPath` points at one directory, so these gates cannot run at the commit boundary alongside `fleet-guards` without a shim that forwards to both.
