# fleet-style

Four document and house-style gates in one place, consumed as a git submodule.

    dash_guard    published prose carries no en/em dash (the ASCII hyphen is code syntax)
    load_budget   PHILOSOPHY P7: the always-loaded budget and the no-second-copy rule
    wrap_guard    keep prose paragraphs on one physical line
    doc_contract  bounded root-document completion, versions and entry links

## Design Philosophy

Every reported pass needs an observed check and a negative control that can fail. Missing inputs and unavailable scanners block; a reusable kit holds one tested implementation, and each consumer pins the commit it accepts. The documentation contract follows the same rule: it catches bounded structural problems while independent review assesses meaning, tradeoffs and demonstrated behavior.

### Why this is a separate repo from fleet-guards

Security checks and documentation checks have different scope. Every public consumer needs publication guards, while a repository without `SKILL.md` has no skill loading budget to measure. Keeping separate kits lets consumers select applicable checks and pin each accepted implementation independently. The original split moved `dash_guard` and `load_budget`, then 17.5% of the guard kit, into this repository.

## Install

    git submodule add -b main https://github.com/DaizeDong/fleet-style.git style

Then in each workflow that wants a gate:

    - uses: actions/checkout@v4
      with: {submodules: true}
    - uses: actions/setup-python@v5
      with: {python-version: '3.x'}
    - uses: ./style/ci/dash-guard        # or wrap-guard, load-budget, doc-contract

This kit runs through CI and does not configure Git hooks. Keep `core.hooksPath` assigned to the publication guards; it supports only one directory. The CI checks remain independent of local hook invocation.

## Checking files locally

    python tools/dash_guard.py --check --tree
    python tools/dash_guard.py --check --staged
    python tools/dash_guard.py --added-only

Staged checks read Git index blobs. Incomplete reads or parses block, and `--fix --staged` is refused to preserve unstaged changes. Use `--fix --tree`, review the diff, then stage selected repairs. Comment kinds report by default unless promoted with `--block-kinds`; incomplete scans always block.

The [scanner reference](docs/SCANNERS.md) defines parser protection, comment kinds, repair behavior, duplication measurement and read limits. To verify generated inputs and the kit tests, run `python tools/make_fixtures.py --check` and `python -m pytest tools/ -q` in the kit checkout.

## Document completion contract

    python style/tools/doc_contract.py --root . --profile skill --stage accepted

Choose `skill`, `software`, `companion` or explicit `combined` with `--profile`, and `draft`, `accepted` or `release` with `--stage`. The caller supplies both; repository content cannot select draft for itself. The action defaults to `skill` and `accepted` and runs regression controls before the check.

Skills and software require both READMEs, ROADMAP and CHANGELOG, with rationale before setup and consistent current versions. Companions require a maintenance README or DATA entry. The PRIVATE combined profile uses a dedicated maintenance changelog and leaves curation DATA unopened. The [documentation contract](docs/DOCUMENTATION_CONTRACT.md) defines profile duties, version and date rules, link checks, JSON output and read boundaries; [combined maintenance](docs/COMBINED_DOCUMENTATION.md) specifies that profile's requirements.

These checks establish structure and visible consistency. Independent review must assess meaning, bilingual accuracy, history completeness and evidence of installation or external behavior.

## Moving the pin

    git -C style fetch && git -C style checkout <sha>

Then commit the new pointer. Consumers select accepted commits independently, or enroll in [automatic synchronization](docs/AUTOMATIC_SYNC.md), which advances the pointer through their own commit gates after upstream checks pass.

## An empty style/ is not a pass

A clone without `--recursive`, or CI checkout without `submodules: true`, can leave `style/` empty. Initialize it with `git submodule update --init`; actions block when their required scanner is missing.
