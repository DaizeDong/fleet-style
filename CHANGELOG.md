# Changelog

All notable changes to this project are documented here (Keep a Changelog style).

## [0.3.0] - 2026-09-25

### Added

- **`dash_guard` report kinds.** The guard now also reads JS and TS `//` and `/* */` comments (`js`), YAML `#` comments (`yaml`), shell `#` comments in `.sh`, `.bash`, `.zsh` and extensionless files with a shell shebang (`sh`), PowerShell `#` and `<# #>` comments (`ps`), cmd `rem` and `::` lines (`cmd`), one commit message through `--message FILE` (`message`), and it turns a file it meant to read and could not into a counted finding (`unexamined`). Only comment text is examined: every string, template and regex literal is code, so a test asserting on a dash or a regex listing the dash set is never flagged. Shell heredoc bodies and PowerShell here-strings are data and are skipped.

- **A per-kind policy, report by default.** Every new kind prints its findings tagged `[report KIND]` and counts them on the verdict line, and does not change the exit code. `--block-kinds js,yaml` (or `all`) promotes kinds to blocking, and `ci/dash-guard` passes its new `block-kinds` input through. An unknown kind name exits 2, because a typo in a promotion must not leave the gate open without a word.

- 17 new tests, 46 in the dash suite in all, including a mutation check for each new rule: making `js` block by default, reading JS strings as prose, dropping regex literal handling, opening YAML quotes mid word, ignoring heredocs, dropping the `unexamined` count, accepting a typo kind, keeping git's `#` lines in a message, letting `--fix` touch a comment kind and ignoring shebang files each turn at least one test red.

### Unchanged

- Markdown, plain text and Python still block exactly as before, and `--fix` never rewrites a report kind. With `block-kinds` left empty, the old and the new guard were run against every consumer checkout on this machine: 27 repositories, identical exit codes and identical blocking lines in all 27.

### Measured

- The report-only run over those 27 consumers found 43 findings in 10 of them: `js` 27, `ps` 6, `yaml` 5, `sh` 4 and `unexamined` 1 (a Python file the tokenizer rejects). Every one was read by hand and every one is comment prose, not a literal. `--message` over the last 50 commit messages of each consumer found dashes in 54 messages across 8 repositories. These are the numbers the promotion to blocking waits on.

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
