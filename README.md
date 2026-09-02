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

## Moving the pin

    git -C style fetch && git -C style checkout <sha>

then commit the new pointer. A submodule pins one commit and does not follow the source on its
own, which is deliberate: a bad commit here cannot reach every consumer by itself.

## An empty style/ is not a pass

A plain `git clone` without `--recursive` leaves it EMPTY, and so does a CI checkout without
`submodules: true`. Every action here fails on a missing scanner rather than skipping, because a
gate that is not there is not a gate that passed.
