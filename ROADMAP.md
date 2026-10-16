# Roadmap

Current: **v0.3.0**

## v0.3.0 (current)

Feature names only. Why each gate behaves the way it does lives in the tool docstrings, which are the single home for those rules, and what changed lives in `CHANGELOG.md`.

- `tools/dash_guard.py`: flag or repair en dash, em dash and horizontal bar in published prose, across the tracked tree, the staged blobs or explicit paths. Markdown fences, inline code spans, allow marked lines and the scanner's own source are exempt.
- `tools/dash_guard.py` report kinds: JS, YAML, shell, PowerShell and cmd comments, and one commit message (`--message`), each reported and counted without failing until promoted with `--block-kinds`. Incomplete scans always block.
- `tools/load_budget.py`: measure a skill's always loaded lines against a two rung budget, and detect prose duplicated between `SKILL.md` and an on demand reference by word shingle.
- `tools/doc_contract.py`: bounded documentation checks with skill, software, companion and explicit combined maintenance profiles; trusted draft, accepted and release stages; explicit semantic/external verification limits. Combined checks read a dedicated maintenance changelog and leave curation DATA and version metadata unopened. PRIVATE visibility, storage safety and restoration remain separate verification duties. These additions are recorded under Unreleased, without changing the existing release version.
- One local checkout per machine, named by `git config fleet.style`. `dash_guard` runs from each consumer's `.githooks/pre-commit` shim on staged added lines; `load_budget` and `doc_contract` run on demand.

## Planned

- **Promote the report kinds to blocking.** Each kind moves to the default blocking set only after a report-only run across every consumer is reviewed and the findings are cleaned. For `js` that includes measuring recall on `.jsx` and `.tsx` files, which no consumer carries yet. The first run, on 2026-09-25, is recorded in `CHANGELOG.md`.
- **YAML prose scalars and a fixer for the comment kinds.** `description:` and similar scalars are prose that `dash_guard` does not read yet, and the comment kinds can be flagged but not repaired. Both need measuring against real files before they exist.
- **A standard `commit-msg` shim for `--message`.** The mode exists; consumers that want it add their own `.githooks/commit-msg`.
- **Repository shapes `load_budget` does not understand.** It discovers `skills/*/SKILL.md` and a root `SKILL.md`. Every other layout reports that nothing was measured, which is the correct refusal and still a gap.
