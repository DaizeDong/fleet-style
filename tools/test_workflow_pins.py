#!/usr/bin/env python3
"""Every reusable workflow this repository calls from another repository is pinned to a commit.

WHY
    `notify-consumers.yml` hands two secrets (the subscription list and the credential mapping) to
    a reusable workflow that lives in another repository. Called at `@main`, whatever lands on that
    branch next runs here with those secrets, without review in this repository. A 40 character
    commit SHA cannot move, so a change to the called workflow reaches this repository only through
    a commit here that advances the pin.

    Actions such as `actions/checkout@v4` are out of scope: they receive no secrets from these
    workflows, and pinning them is a separate decision.

SHAPE
    `find_unpinned` is the checker. The negative controls feed it synthetic workflow text with a
    branch ref, a tag ref and a short SHA and demand each is reported; the positive control feeds it
    a full SHA and a local call and demands silence. The last test runs it over the real workflow
    directory, which is the guarantee itself.
"""

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
WORKFLOWS = os.path.join(os.path.dirname(HERE), ".github", "workflows")

# owner/repo/.github/workflows/file.yml@ref, i.e. a reusable workflow in another repository.
_REMOTE_REUSABLE = re.compile(
    r"^\s*(?:-\s*)?uses:\s*['\"]?([\w.-]+/[\w.-]+/\.github/workflows/[^@\s'\"]+)@([^\s'\"#]+)",
    re.MULTILINE,
)
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def find_unpinned(text):
    """Return (target, ref) for each remote reusable workflow call whose ref is not a full SHA."""
    return [(m.group(1), m.group(2)) for m in _REMOTE_REUSABLE.finditer(text)
            if not _FULL_SHA.match(m.group(2))]


def _job(uses):
    return "jobs:\n  notify:\n    uses: " + uses + "\n    secrets:\n      targets: x\n"


def test_neg_branch_ref_is_reported():
    # Breaks if the checker accepts any ref, or stops matching job level `uses:`.
    assert find_unpinned(_job("example/kit/.github/workflows/dispatch.yml@main")) == [
        ("example/kit/.github/workflows/dispatch.yml", "main")]


def test_neg_tag_and_short_sha_are_reported():
    # A tag can be moved and a short SHA is ambiguous; neither is an immutable pin.
    text = _job("example/kit/.github/workflows/a.yml@v1") + _job(
        "'example/kit/.github/workflows/b.yml@82d771f'")
    assert [r for _, r in find_unpinned(text)] == ["v1", "82d771f"]


def test_pos_full_sha_and_local_calls_pass():
    text = (_job("example/kit/.github/workflows/dispatch.yml@" + "0123456789abcdef" * 2 + "01234567"
                 + "  # main as of 2026-09-25")
            + "    steps:\n      - uses: ./ci/dash-guard\n      - uses: actions/checkout@v4\n"
            + _job("./.github/workflows/local.yml"))
    assert find_unpinned(text) == []


def test_real_workflows_pin_remote_reusable_calls():
    names = sorted(n for n in os.listdir(WORKFLOWS) if n.endswith((".yml", ".yaml")))
    assert names, "no workflow files found, nothing was checked"
    offenders = []
    for n in names:
        with open(os.path.join(WORKFLOWS, n), encoding="utf-8") as f:
            offenders += [(n,) + hit for hit in find_unpinned(f.read())]
    assert offenders == [], "remote reusable workflows not pinned to a full commit SHA: %r" % offenders
