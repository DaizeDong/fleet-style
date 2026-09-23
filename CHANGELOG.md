# Changelog

All notable changes to this project are documented here (Keep a Changelog style).

## [0.2.0] - 2026-09-23

### Added

- **`wrap_guard`: prose paragraphs carry no hard wraps.** A paragraph is one line; blank lines separate paragraphs. Line length is not a reason to break text, because whatever renders it wraps to its own width. The only places a newline belongs are between paragraphs, between list items, inside code blocks and inside ASCII tables where alignment carries meaning.

  Why a third gate rather than a note: the rule had been stated and then violated repeatedly, on 2026-07-27, again on 2026-08-02 (three times before it took), and again on 2026-09-23, where one repository held 168 wrapped paragraphs across 11 documents and 20 of that day's 24 commit messages were wrapped. A rule that keeps being broken is not short of restatement, it is short of a criterion that goes red. The dash rule took this same path before `dash_guard` stopped it.

  Two exemptions are worth naming because getting them wrong makes the gate useless in opposite directions. Git trailers such as `Co-Authored-By:` must each sit on their own line, so a gate that flagged them would block every signed commit and be bypassed with `--no-verify` on day one. Badge rows are nested markdown, `[![alt](img)](href)`, and stripping them with one regex matches the wrong span: `[^\]]*` stops at the `]` inside `![alt]`, the outer link's opening bracket is eaten by the inner image, and a leftover `](href)` never strips. Images are stripped before links for exactly this reason.

- **`ci/wrap-guard`.** Runs the guard's own tests, then scans the calling repository's tree. Never `--fix`: that rewrites files and exits 0, which would install a check that cannot fail.

### Changed

- This repository's own six markdown files were unwrapped by `wrap_guard --fix`, and the repair was verified idempotent by running it twice and comparing the diffs byte for byte.

### Note

- **Commit messages are not covered by CI**, because a message never reaches CI as a file. They are caught by a machine-level `commit-msg` hook that lives outside this repository. That hook only blocks in repositories whose origin owner appears in the operator's identity table: git's own convention is to wrap commit bodies at 72 columns, and enforcing a personal style rule inside other people's clones is the kind of over-reach that silently broke a nightly backup twice when the dash gate was applied too widely.

## [0.1.0] - 2026-09-22

The code here declares no version, so `0.1.0` is assigned at this point and the README badge, the ROADMAP heading and this entry are the only places it appears.

### Added

- **docs: unify repo structure (Skill Repo Spec v1).** The README is restructured to the spec's section order with the philosophy first, `README_CN.md` matches it section for section, and the mandatory `ROADMAP.md` and `CHANGELOG.md` are added. Nothing about the two gates changed.

  Six requirements of that spec are deliberately not met, every one because meeting it would claim something untrue of a submodule that is not a skill, and all six are argued in `docs/2026-09-22-spec-adaptation.md` rather than left as a silent omission: no `.claude-plugin/plugin.json`, no `SKILL.md` and therefore no L0 or L1 documentation layer, no `LICENSE` badge while the file is absent, no `.pii-allow` until there is an exemption to argue for, no `dash-guard.yml` workflow because the gate already runs here through this repository's own action, and five of the nine fingerprint topics refused.

### Existing at this version

- `dash_guard`: the no en dash rule, over the tracked tree, the staged blobs or explicit paths, with a deterministic `--fix` that is not usable as a gate.
- `load_budget`: the always loaded budget and the no second copy rule, with both halves able to fail and a separate exit code for having measured nothing.
- `ci/dash-guard` and `ci/load-budget`: composite actions that run each guard's own tests before the guard, and fail on a missing scanner.
- `conftest.py`: this kit's tests stay out of a consumer's count and remain reachable at
  `pytest style/tools/`.
- Optional consumer notification, so a passing commit here can advance a pin through each consumer's own gates.
