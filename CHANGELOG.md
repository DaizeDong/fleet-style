# Changelog

All notable changes to this project are documented here (Keep a Changelog style).

## [0.1.0] - 2026-09-22

The code here declares no version, so `0.1.0` is assigned at this point and the README
badge, the ROADMAP heading and this entry are the only places it appears.

### Added

- **docs: unify repo structure (Skill Repo Spec v1).** The README is restructured to the
  spec's section order with the philosophy first, `README_CN.md` matches it section for
  section, and the mandatory `ROADMAP.md` and `CHANGELOG.md` are added. Nothing about the
  two gates changed.

  Six requirements of that spec are deliberately not met, every one because meeting it
  would claim something untrue of a submodule that is not a skill, and all six are argued
  in `docs/2026-09-22-spec-adaptation.md` rather than left as a silent omission: no
  `.claude-plugin/plugin.json`, no `SKILL.md` and therefore no L0 or L1 documentation
  layer, no `LICENSE` badge while the file is absent, no `.pii-allow` until there is an
  exemption to argue for, no `dash-guard.yml` workflow because the gate already runs here
  through this repository's own action, and five of the nine fingerprint topics refused.

### Existing at this version

- `dash_guard`: the no en dash rule, over the tracked tree, the staged blobs or explicit
  paths, with a deterministic `--fix` that is not usable as a gate.
- `load_budget`: the always loaded budget and the no second copy rule, with both halves
  able to fail and a separate exit code for having measured nothing.
- `ci/dash-guard` and `ci/load-budget`: composite actions that run each guard's own tests
  before the guard, and fail on a missing scanner.
- `conftest.py`: this kit's tests stay out of a consumer's count and remain reachable at
  `pytest style/tools/`.
- Optional consumer notification, so a passing commit here can advance a pin through each
  consumer's own gates.
