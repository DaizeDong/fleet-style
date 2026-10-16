# fleet-style

Three document and house-style scripts in one place, run from one local checkout per machine.

    dash_guard    published prose carries no en/em dash (the ASCII hyphen is code syntax)
    load_budget   PHILOSOPHY P7: the always-loaded budget and the no-second-copy rule
    doc_contract  bounded root-document completion, versions and entry links

## Design Philosophy

Every reported pass needs an observed check. Missing inputs and unavailable scanners block; the kit holds one implementation, in one checkout. The documentation contract follows the same rule: it catches bounded structural problems while independent review assesses meaning, tradeoffs and demonstrated behavior.

### Why this is a separate repo from fleet-guards

Security checks and documentation checks have different scope. Every public consumer needs publication guards, while a repository without `SKILL.md` has no skill loading budget to measure. Keeping the kits separate lets each consumer select the checks that apply to it.

## Install

Once per machine:

    git clone https://github.com/DaizeDong/fleet-style.git <path>
    git config --global fleet.style <path>        # forward slashes, e.g. C:/src/fleet-style

The checkout stays on `main`; edits happen in a `git worktree` of it.

Only `dash_guard` runs automatically, from a consumer's `.githooks/pre-commit` shim (the fleet-guards shim with this block before its final `exec`):

```sh
S=$(git config --get fleet.style)
if [ -z "$S" ] || [ ! -s "$S/tools/dash_guard.py" ]; then
  echo "BLOCKED: git config fleet.style is unset or has no tools/dash_guard.py; nothing was checked." >&2
  exit 1
fi
python "$S/tools/dash_guard.py" --staged --added-only </dev/null || exit 1
```

An unset key or a checkout without the script blocks; there is no fallback location. `load_budget` and `doc_contract` are on-demand scripts and are not wired into any hook.

## Checking files by hand

    python tools/dash_guard.py --tree
    python tools/dash_guard.py --staged
    python tools/dash_guard.py --added-only
    python tools/load_budget.py .

From a consumer, run them as `python "$(git config --get fleet.style)/tools/<tool>.py"`.

Staged checks read Git index blobs. Incomplete reads or parses block, and `--fix --staged` is refused to preserve unstaged changes. Use `--fix --tree`, review the diff, then stage selected repairs. Incomplete scans always block.

The [scanner reference](docs/SCANNERS.md) defines parser protection, repair behavior, duplication measurement and read limits.

## Document completion contract

    python tools/doc_contract.py --root . --profile software --stage accepted

Choose `skill`, `software`, `companion` or explicit `combined` with `--profile`, and `draft`, `accepted` or `release` with `--stage`. The caller supplies both; repository content cannot select draft for itself.

Skills and software require both READMEs, ROADMAP and CHANGELOG, with rationale before setup and consistent current versions. Companions require a maintenance README or DATA entry. The PRIVATE combined profile uses a dedicated maintenance changelog and leaves curation DATA unopened. The [documentation contract](docs/DOCUMENTATION_CONTRACT.md) defines profile duties, version and date rules, link checks, JSON output and read boundaries; [combined maintenance](docs/COMBINED_DOCUMENTATION.md) specifies that profile's requirements.

These checks establish structure and visible consistency. Independent review must assess meaning, bilingual accuracy, history completeness and evidence of installation or external behavior.

## This repository's own hooks

`.githooks/pre-commit` runs the fleet-guards checks and `dash_guard` on this repository; `.githooks/pre-push` runs the fleet-guards push checks. Both use `core.hooksPath=.githooks`.

## Languages

English (`README.md`) · 中文 (`README_CN.md`)

## Roadmap · Contributing · License

See [ROADMAP.md](ROADMAP.md) · [CHANGELOG.md](CHANGELOG.md).
