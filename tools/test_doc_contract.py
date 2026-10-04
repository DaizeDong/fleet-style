"""Generated synthetic documents exercise the caller-facing contract, not mocks."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parent
CASES = json.loads((HERE.parent / "tests/fixtures/doc_cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_document_contract(case, tmp_path):
    # Losing any named predicate makes its single-fault case unexpectedly pass.
    for name, content in case["files"].items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    run = subprocess.run([sys.executable, str(HERE / "doc_contract.py"), "--root", str(tmp_path),
                          "--profile", case.get("profile", "skill"), "--stage",
                          case.get("stage", "accepted"), "--json"], capture_output=True, text=True)
    assert run.returncode == (1 if case.get("failure") else 0), (run.stdout, run.stderr)
    result = json.loads(run.stdout)
    assert result["schema_version"] == 1
    assert result["ok"] == (not bool(case.get("failure")))
    assert [finding["name"] for finding in result["failures"]] == (
        [case["failure"]] if case.get("failure") else [])
    assert {check["name"] for check in result["checks"]} >= {
        "docs.required", "readme.philosophy", "readme.install", "docs.placeholders",
        "version.source", "version.current", "changelog.releases", "roadmap.current", "links.local"}


def test_invalid_stage_cannot_be_self_declared(tmp_path):
    run = subprocess.run([sys.executable, str(HERE / "doc_contract.py"), "--root", str(tmp_path),
                          "--stage", "anything"], capture_output=True)
    assert run.returncode == 2


def test_action_preserves_trusted_input_boundary():
    action = (HERE.parent / "ci/doc-contract/action.yml").read_text(encoding="utf-8")
    assert "DOC_PROFILE: ${{ inputs.profile }}" in action
    assert "DOC_STAGE: ${{ inputs.stage }}" in action
    assert '--profile "$DOC_PROFILE" --stage "$DOC_STAGE"' in action
    assert 'tools/test_doc_contract.py' in action


def load_checker():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_doc_contract_test", HERE / "doc_contract.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    return checker


def write_case(tmp_path, case):
    for name, content in case["files"].items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def test_linked_payload_is_never_opened(tmp_path, monkeypatch):
    case = next(case for case in CASES if case["name"] == "protected payload link is metadata only")
    write_case(tmp_path, case)
    original = Path.open

    def admitted_open(path, *args, **kwargs):
        assert path != tmp_path / "eval/poison.json", "payload content was opened"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", admitted_open)
    result = load_checker().check(tmp_path)
    assert result["ok"]
    assert any("(1)" in detail for detail in result["unverified"])


def test_linked_root_input_blocks_without_reading_target(tmp_path, monkeypatch):
    write_case(tmp_path, CASES[0])
    outside = tmp_path / "outside.md"
    (tmp_path / "README.md").rename(outside)
    try:
        (tmp_path / "README.md").symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation unavailable on this host")
    original = Path.open

    def admitted_open(path, *args, **kwargs):
        assert path.name not in {"README.md", "outside.md"}, "linked input was opened"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", admitted_open)
    result = load_checker().check(tmp_path)
    assert not result["ok"]
    assert "docs.required" in [row["name"] for row in result["failures"]]
