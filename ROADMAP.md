# Roadmap

Current: **v0.1.0**

## v0.1.0 (current)

Feature names only. Why each gate behaves the way it does lives in the tool docstrings,
which are the single home for those rules, and what changed lives in `CHANGELOG.md`.

- `tools/dash_guard.py`: flag or repair en dash, em dash and horizontal bar in published
  prose, across the tracked tree, the staged blobs or explicit paths. Markdown fences,
  inline code spans, allow marked lines and the scanner's own source are exempt.
- `tools/load_budget.py`: measure a skill's always loaded lines against a two rung budget,
  and detect prose duplicated between `SKILL.md` and an on demand reference by word
  shingle.
- `ci/dash-guard` and `ci/load-budget`: composite actions that run each guard's own tests
  first and fail on a missing scanner rather than skipping it.
- `conftest.py`: keep this kit's tests out of a consumer's collection while leaving them
  reachable by path.
- `.github/workflows/style.yml`: this repository runs its own dash gate through its own
  action.
- `.github/workflows/notify-consumers.yml` and `docs/AUTOMATIC_SYNC.md`: optional pin
  advancement through each consumer's normal commit gates.

## Planned

- **A LICENSE file.** The repository ships none, so it carries no license badge and a
  consumer has no stated terms for the code it pins.
- **File types `dash_guard` does not examine.** The extension map covers Markdown, plain
  prose, Python and templates. Anything outside it is skipped, and a skipped file is
  reported but not checked, so prose in a YAML description or a shell comment passes.
- **Repository shapes `load_budget` does not understand.** It discovers
  `skills/*/SKILL.md` and a root `SKILL.md`. Every other layout reports that nothing was
  measured, which is the correct refusal and still a gap.
- **A test that pins the numbers written in prose.** `conftest.py` states this kit's test
  count in its own docstring, and nothing fails when the suite grows past it.
- **A hook path that does not fight the security kit.** `core.hooksPath` points at one
  directory, so these gates cannot run at the commit boundary alongside `fleet-guards`
  without a shim that forwards to both.
