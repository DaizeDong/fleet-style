# 2026-09-22: applying the house repository spec to a gate kit

This repository was brought in line with Skill Repo Spec v1, which was written for Claude Code skill repositories. This one is a git submodule holding two scanners and two CI actions. Most of the spec applies as written. A handful of individual requirements are refused outright, because meeting them would mean claiming something untrue, and a few others are adapted because the intent survives even where the letter does not.

This file is the record of those decisions, so the next person auditing this repository against the spec finds a reasoned position rather than silence, and can argue with it. It is dated evidence, not a rule: the rules live in the tool docstrings, the version history in `CHANGELOG.md`.

## Refused, because meeting them would be a false claim

**No `.claude-plugin/plugin.json`.** Chapter 1 makes it mandatory so that even a single skill repository stays installable with `/plugin install`. There is nothing here for that command to install: no `SKILL.md`, no skill entrypoint, no agent behaviour at all. A manifest would be advertising rather than metadata. The manifest's job here is done by `.gitmodules` in each consumer, which is what actually pins and fetches this code.

**No `claude-code`, `claude-plugin`, `claude-skill`, `claude` or `skill` topic.** Chapter 6 calls these part of a nine topic identity fingerprint that every repository carries. Five of the nine are false here. This repository contains no Claude integration of any kind, and `skill` on GitHub reads as "Agent Skill", which this is not. Putting them on would pollute the search results for the repositories where they are true. `llm` is refused for the same reason the worked example refuses it: nothing here makes a model call or holds a prompt. Two scanners read text with regexes and word shingles.

Of the nine, `ai` and `ai-agent` are honest, because the always loaded budget exists only
because an agent pays for `SKILL.md` on every invocation, and `agent` is honest for the
same reason. So the base nine is read here as a base three, and domain topics do the rest.
The repository carries no topics at all at this point, and the honest set to give it is
`ai`, `ai-agent`, `agent`, `git-submodule`, `ci`, `github-actions`, `linter`,
`code-quality`, `static-analysis`, `style-guide` and `python`. Setting them is a change to
the GitHub repository rather than to this tree, so it is recorded here as a decision and
left for whoever runs `gh repo edit`.

**No `SKILL.md`, and no L0 or L1 layer.** Chapter 11's first two layers are the frontmatter description and the per invocation preamble, both of which exist because a skill pays for them on every turn. A submodule is fetched and called, not invoked, so there is nothing to pay and nothing to budget. L2 through L5 apply and are implemented, with one substitution: this repository has no `reference/` directory, because each rule's full text lives in the docstring of the tool that enforces it, next to the code that can be checked against it. `docs/` holds dated evidence, the two READMEs are a tour, and `ROADMAP.md` plus `CHANGELOG.md` are the only places a version number appears.

**The license, resolved the same day.** Chapter 3 fixes the second badge as the license, linking to `LICENSE`, and this repository shipped no such file. A badge asserting MIT over an unlicensed repository states terms that do not exist, and a consumer pinning this submodule would be acting on them, so the slot was left empty rather than filled. The file now exists, MIT, matching the rest of the fleet byte for byte, and the badge went in with it. Recorded here rather than deleted, because the sequence is the point: the gap was stated before it was closed, not quietly skipped.

**No `.github/workflows/dash-guard.yml`.** The spec's chapter 10 asks every repository to run the dash gate in CI, and this one does, through `.github/workflows/style.yml` calling `./ci/dash-guard`, its own composite action, against its own tree. The workflow the task description expects wires `style/ci/dash-guard` from a `style/` submodule. This repository is that submodule and cannot consume itself, so a second workflow would either be a duplicate of the one that already runs or a pointer at a directory that does not exist. Measured here: `python tools/dash_guard.py --tree` exits 0 on this tree, having examined 9 files and skipped 2 by name.

**No load budget job in this repository's own CI.** `ci/load-budget` measures what a `SKILL.md` costs to load. This repository declares none, so the tool exits 3 and says so. Running it on every commit would produce a permanently red job whose redness means nothing, which is the mirror of the failure the tool was written to stop. The action is still shipped and still tested, because consumers with a `SKILL.md` need it.

## Adapted, because the intent survives and the letter does not

**The orange type badge.** Chapter 3 fixes the first badge as `Claude Code Skill` linking to the Claude Code docs. The slot is kept, because a reader should learn what kind of thing this is from the first line of badges, but its content is `Git Submodule / Style Kit` linking to the install section, which is both true and the thing a visitor needs to know first.

**Chapter 4 section 6 and 7.** `Skills at a glance` becomes `Gates at a glance`, one row per scanner plus one row per CI action, and `How to invoke` becomes `How it runs`, because a submodule has no trigger words. The question that section answers, what makes this thing execute, is the same question.

**Version consistency.** Chapter 7 asks for four copies of the version kept in step. The code declares no version anywhere: no `pyproject.toml`, no `__version__`, no manifest. So `0.1.0` is assigned at this point, per the chapter's own instruction for repositories that have never carried one, and it appears in exactly three places: the README badge, the ROADMAP heading and the CHANGELOG entry. There is no fourth copy to keep in step because there is nothing to install.

**No `.pii-allow`.** Chapter 8 lists it as a required file. It is a list of real third party identifiers this repository is allowed to contain, each with an argued reason. This repository contains none, and an empty allowlist asserts nothing. It is created when there is a first exemption to argue for.

**No `guards/` submodule, and therefore no `pii-guard.yml`.** Chapters 8 and 9 require the security kit in every repository. This one carries neither the scanner nor the workflow, by the same argument that split the two kits apart: `fleet-guards` consumes nothing from here and this repository consumes nothing from there, and a mutual submodule pair between two gate kits buys a cycle rather than a control. The identifier question is answered for this repository by the machine level hook, which runs on every repository on this machine regardless of what it carries, and by each consumer's own CI. `.github/workflows/style.yml` already records this reasoning at the top of the file.

**The data boundary toolchain.** Chapter 9 requires `tools/datadir.py`, `tools/test_datadir.py`, `tools/data_boundary.py` and `tools/make_fixtures.py` in every repository. None are present, for the reason above, and the declaration they would enforce is present: `.dataclass.json` argues an empty `data` list rather than defaulting to one, and names the two writes in shipped code that were located before concluding it. The audit's conclusion, that `dash_guard --fix` edits the caller's own source and `load_budget.py` only prints, still holds.

## What was measured, and where

| Claim | How it was checked |
| --- | --- |
| The suite passes | `python -m pytest -q` at the repository root, 49 passed |
| The count written in prose has already drifted | `conftest.py` states 47 in its own docstring while the suite collects 49, which is why `ROADMAP.md` lists a test that pins it |
| The dash gate is armed here and clean | `python tools/dash_guard.py --tree` exits 0, 9 files examined, 2 skipped by name |
| The load budget gate refuses rather than reassures | `python tools/load_budget.py .` exits 3 with `measured NOTHING`, which is why this repository runs no load budget job |
| No version exists to be consistent with | No `pyproject.toml`, no `__version__`, no manifest anywhere in the tree |
| The license badge now has something to point at | `LICENSE` added 2026-09-22, MIT, identical to the rest of the fleet |
