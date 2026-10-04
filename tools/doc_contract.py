#!/usr/bin/env python3
"""Check bounded root documentation without executing documented commands.

This is a structural contract. It cannot establish design quality, translation
accuracy, historical completeness, working installation or product effectiveness.
Only trusted CLI/CI inputs select the profile and lifecycle stage.
"""
from __future__ import annotations

import argparse
from datetime import date
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
from urllib.parse import unquote, urlsplit

_SPEC = importlib.util.spec_from_file_location("_doc_markdown", Path(__file__).with_name("markdown_regions.py"))
_MD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MD)

SEMVER = (r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
          r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?")
_VERSION = re.compile(SEMVER + r"\Z")
_PHILOSOPHY = re.compile(r"design\s+philosophy|设计哲学|設計哲學|设计理念|設計理念", re.I)
_INSTALL = re.compile(r"install(?:ation)?|setup|getting\s+started|安装|安裝|部署", re.I)
_FUTURE = re.compile(r"planned|future|next|backlog|待办|待辦|计划|計劃|未来|未來", re.I)
_CURRENT = re.compile(r"current|当前|當前", re.I)
_PLACEHOLDER = re.compile(r"\b(?:TODO|TBD|FIXME)\b|\{\{[^}\n]+\}\}|\b(?:YOUR_|REPLACE_ME|INSERT_HERE)\w*|"
                          r"待填写|待填寫|待补充|待補充|占位正文|placeholder\s+(?:text|body)|"
                          r"fill\s+(?:this|in|out)|write\s+(?:the|your)\s+(?:description|philosophy)", re.I)
_FILLER = re.compile(r"explain\s+(?:the\s+)?design\s+choices\s+here|initial release\.?$|设计哲学写在这里", re.I)
_ROOT_DOCS = ("README.md", "README_CN.md", "CHANGELOG.md", "ROADMAP.md", "PHILOSOPHY.md", "PHILOSOPHY_CN.md")
_METADATA = (".claude-plugin/plugin.json", "package.json", ".gitmodules")
_HEADING = re.compile(r"(?m)^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
CHECK_NAMES = ("docs.required", "readme.philosophy", "readme.install", "docs.placeholders",
               "version.source", "version.current", "changelog.releases", "roadmap.current", "links.local")


def visible(text):
    """Blank code/HTML blocks without changing offsets or physical lines."""
    chars = list(text)
    for start, end in _MD.code_and_html_regions(text):
        for i in range(start, end):
            if chars[i] not in "\r\n":
                chars[i] = " "
    return "".join(chars)


def section_ranges(text):
    clean = visible(text)
    headings = list(_HEADING.finditer(clean))
    for i, heading in enumerate(headings):
        end = next((later.start() for later in headings[i + 1:]
                    if len(later[1]) <= len(heading[1])), len(text))
        yield heading[2].strip(), heading.start(), heading.end(), end


def sections(text):
    return [(title, text[body_start:end], start) for title, start, body_start, end in section_ranges(text)]


def meaningful(body):
    prose = _MD.without_code(body)
    prose = re.sub(r"(?m)^\s*#+.*$", "", prose)
    prose = re.sub(r"[\W_]", "", prose)
    return len(prose) >= 30


def substantive_notes(body):
    prose = re.sub(r"(?m)^\s*#+.*$", "", _MD.without_code(body))
    return len(re.sub(r"[\W_]", "", prose)) >= 12


def semver(value):
    if not isinstance(value, str) or not _VERSION.fullmatch(value):
        return None
    base, _, prerelease = value.split("+", 1)[0].partition("-")
    ids = prerelease.split(".") if prerelease else []
    if any(item.isdigit() and len(item) > 1 and item.startswith("0") for item in ids):
        return None
    return tuple(map(int, base.split("."))), tuple(ids)


def version_order(value):
    base, ids = semver(value)
    return base, (1,) if not ids else (0, tuple((0, int(x)) if x.isdigit() else (1, x) for x in ids))


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def path_metadata(root, relative):
    """Only inspect metadata; reject links, escapes and non-physical ancestors."""
    target = Path(os.path.abspath(root / relative))
    if not target.is_relative_to(root):
        raise ValueError("local path escapes root")
    for component in (target, *target.parents):
        info = component.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("linked/reparse path is unsupported")
        if component == target and not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
            raise ValueError("path is not a regular file or directory")
    return target


def read_input(root, relative):
    path = path_metadata(root, relative)
    if not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise ValueError("input is not a bounded regular file")
    return path.read_text(encoding="utf-8-sig")


def local_links(text):
    """Inline links/images and reference definitions outside code/HTML blocks."""
    clean = visible(text)
    protected = list(_MD.code_regions(text))
    for match in re.finditer(r"!?\[[^\]\n]*\]\(\s*(<[^>\n]+>|[^\s)]+)(?:\s+[^)]+)?\)", clean):
        if not _MD.escaped(clean, match.start()) and not any(start <= match.start() < end for start, end in protected):
            yield match[1].strip("<>")
    for match in re.finditer(r"(?m)^ {0,3}\[[^\]\n]+\]:\s*(<[^>\n]+>|\S+)", clean):
        yield match[1].strip("<>")


def anchors(text):
    seen, result = {}, set()
    for heading, _, _ in sections(text):
        title = heading.replace("`", "").lower().strip()
        title = re.sub(r"[^\w\-\s]", "", title).replace(" ", "-")
        count = seen.get(title, 0)
        seen[title] = count + 1
        result.add(title + (f"-{count}" if count else ""))
    result.update(re.findall(r"\bid=[\"']([^\"']+)[\"']", text))
    result.update(re.findall(r"<a\s+name=[\"']([^\"']+)[\"']", text, re.I))
    return result


def current_versions(text):
    matches = []
    for line in visible(text).splitlines():
        if _CURRENT.search(line) and re.match(r"\s*(?:#+\s*)?(?:current|当前|當前|v?\d)", line, re.I):
            matches.extend(re.findall(r"(?<![\w.])v?(\d+\.\d+\.\d+(?:-[\w.-]+)?(?:\+[\w.-]+)?)(?![\w.+-])", line))
    return matches


def displayed_versions(text):
    values = []
    for payload in re.findall(r"/badge/(?:version|版本)[-:]([^\s)]+)", visible(text), re.I):
        value = unquote(payload).rsplit("-", 1)[0].replace("--", "-").removeprefix("v")
        values.append(value)
    for line in visible(text).splitlines():
        match = re.match(r"\s*(?:\*\*)?(?:version|版本)\s*[:：]\s*(?:\*\*)?v?([\w.+-]+)", line, re.I)
        if match:
            values.append(match[1])
    return values


def check(root, profile="skill", stage="accepted"):
    root = Path(os.path.abspath(root))
    errors = {name: [] for name in CHECK_NAMES}
    docs, metadata, not_applicable = {}, {}, set()

    def fail(name, detail):
        if detail not in errors[name]:
            errors[name].append(detail)

    inputs = ("README.md", "DATA.md") if profile == "companion" else _ROOT_DOCS + _METADATA
    for name in inputs:
        try:
            value = read_input(root, name)
        except FileNotFoundError:
            continue
        except (OSError, UnicodeError, ValueError) as exc:
            fail("docs.required", f"{name}: {type(exc).__name__} reading bounded input")
            continue
        (metadata if name in _METADATA else docs)[name] = value
    required = ("README.md", "README_CN.md", "CHANGELOG.md", "ROADMAP.md")
    if profile == "companion":
        if not any(name in docs for name in ("README.md", "DATA.md")):
            fail("docs.required", "companion needs README.md or DATA.md maintenance entry")
        not_applicable.update(set(CHECK_NAMES) - {"docs.required", "docs.placeholders", "links.local"})
    else:
        for name in required:
            if name not in docs:
                fail("docs.required", f"missing {name}")
        for name in ("README.md", "README_CN.md"):
            if name not in docs:
                continue
            entries = sections(docs[name])
            philosophy = [entry for entry in entries if _PHILOSOPHY.search(entry[0])]
            installs = [entry for entry in entries if _INSTALL.search(entry[0])]
            if not philosophy or not any(((meaningful(body) and not _FILLER.search(body))
                                         or stage == "draft" and (_PLACEHOLDER.search(body) or _FILLER.search(body)))
                                         and (not installs or offset < installs[0][2])
                                         for _, body, offset in philosophy):
                fail("readme.philosophy", f"{name}: needs substantive Design Philosophy before installation")
            if not installs:
                fail("readme.install", f"{name}: missing installation entry")
                continue
            body = installs[0][1]
            if not (re.search(r"(?m)^\s*(?:```|~~~| {4}\S)|`[^`]*(?:install|setup|add)[^`]*`", body)
                    or list(local_links(body))):
                fail("readme.install", f"{name}: installation needs a command or linked entry")
            for match in re.finditer(r"(?m)^\s*(?:\$\s*)?(?:python\d*|node|bash|sh|pwsh|powershell)\s+(?:-\w+\s+)*(?!-)([\w./-]+\.(?:py|js|sh|ps1))", body):
                try:
                    path_metadata(root, match[1])
                except (OSError, ValueError):
                    fail("readme.install", f"{name}: declared command path unavailable: {match[1]}")
            if ".gitmodules" in metadata and "git clone" in body:
                if not (re.search(r"git clone[^\n]*(?:--recursive|--recurse-submodules)", body)
                        or re.search(r"git submodule update[^\n]*--init[^\n]*--recursive", body)):
                    fail("readme.install", f"{name}: clone entry must initialize required submodules")

    if stage != "draft":
        for name, text in docs.items():
            if name == "ROADMAP.md":
                # Future work may legitimately remain TODO; only current/root material is checked.
                ranges = [(start, end) for heading, start, _, end in section_ranges(text)
                          if _FUTURE.search(heading) and not _CURRENT.search(heading)]
                for start, end in sorted(ranges, reverse=True):
                    text = text[:start] + text[end:]
            if _PLACEHOLDER.search(_MD.without_code(text)):
                fail("docs.placeholders", f"{name}: unresolved scaffold placeholder in current documentation")

    source = None
    if profile != "companion":
        versions = []
        for name in _METADATA[:2]:
            if name not in metadata:
                continue
            try:
                value = json.loads(metadata[name], object_pairs_hook=unique_json)["version"]
                if semver(value) is None:
                    raise ValueError("invalid SemVer")
                versions.append(value)
            except (ValueError, TypeError, KeyError):
                fail("version.source", f"{name}: needs unique full SemVer version")
        if len(set(versions)) > 1:
            fail("version.source", "manifest/package version sources conflict")
        roadmap = docs.get("ROADMAP.md", "")
        current = current_versions(roadmap)
        if versions:
            source = versions[0]
        elif not errors["version.source"]:
            if len(set(current)) == 1 and semver(current[0]):
                source = current[0]
            elif roadmap:
                fail("version.source", "without manifest/package, ROADMAP needs one numeric current version")
        if roadmap:
            if any(semver(value) is None for value in current) or len(set(current)) > 1 or source and any(value != source for value in current):
                fail("roadmap.current", "ROADMAP current version declarations conflict")
            elif not current and not any(_CURRENT.search(heading) and meaningful(body)
                                         for heading, body, _ in sections(roadmap)):
                fail("roadmap.current", "ROADMAP needs a purposeful current section or current version declaration")
        if source and not errors["version.source"]:
            for name in ("README.md", "README_CN.md"):
                if any(value != source for value in displayed_versions(docs.get(name, ""))):
                    fail("version.current", f"{name}: displayed current version differs from {source}")
        changelog = docs.get("CHANGELOG.md", "")
        releases, unreleased = [], []
        for heading, body, offset in sections(changelog):
            if re.fullmatch(r"\[?Unreleased\]?", heading, re.I):
                unreleased.append(offset)
                continue
            if not re.match(r"\[?v?\d", heading):
                continue
            match = re.fullmatch(r"\[?v?(" + SEMVER + r")\]?\s+-\s+(\S+)", heading)
            if not match or semver(match[1]) is None:
                fail("changelog.releases", "CHANGELOG release needs full SemVer and ISO date")
                continue
            try:
                published = date.fromisoformat(match[2])
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", match[2]) or published > date.today():
                    raise ValueError("invalid/future date")
            except ValueError:
                fail("changelog.releases", "CHANGELOG release date is invalid or in the future")
                continue
            releases.append((match[1], published, offset, body))
        if len(unreleased) > 1 or unreleased and releases and unreleased[0] > releases[0][2]:
            fail("changelog.releases", "Unreleased must occur once before releases")
        for earlier, later in zip(releases, releases[1:]):
            if version_order(earlier[0]) <= version_order(later[0]) or earlier[1] < later[1]:
                fail("changelog.releases", "CHANGELOG releases must be unique and ordered newest first by version/date")
        if releases and source and not errors["version.source"] and releases[0][0] != source:
            fail("changelog.releases", f"newest CHANGELOG release differs from {source}")
        if stage == "release" and (not releases or not substantive_notes(releases[0][3])):
            fail("changelog.releases", "release stage requires substantive notes for latest numeric release")

    unchecked_anchors = 0
    for name, text in docs.items():
        for target in local_links(text):
            url = urlsplit(target)
            if url.scheme or url.netloc:
                continue
            relative = unquote(url.path) or name
            try:
                destination = path_metadata(root, relative)
            except (OSError, ValueError):
                fail("links.local", f"{name}: missing or unsupported local destination: {relative}")
                continue
            if url.fragment:
                if relative in docs:
                    if unquote(url.fragment) not in anchors(docs[relative]):
                        fail("links.local", f"{name}: unknown root-doc anchor: {target}")
                else:
                    unchecked_anchors += 1
    checks = [{"name": name, "status": "FAIL" if errors[name] else
               "NOT_APPLICABLE" if name in not_applicable else "PASS",
               "detail": "; ".join(errors[name]) or ("not required for companion" if name in not_applicable else "checked")}
              for name in CHECK_NAMES]
    failures = [{"name": row["name"], "detail": row["detail"]} for row in checks if row["status"] == "FAIL"]
    return {"schema_version": 1, "profile": profile, "stage": stage, "ok": not failures,
            "checks": checks, "failures": failures, "version": source,
            "unverified": ["semantic completeness and bilingual accuracy", "documented commands and external behavior",
                           f"anchors outside admitted root docs ({unchecked_anchors}); targets metadata-checked only"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--profile", choices=("skill", "software", "companion"), default="skill")
    parser.add_argument("--stage", choices=("draft", "accepted", "release"), default="accepted")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = check(args.root, args.profile, args.stage)
    if args.json:
        print(json.dumps(result, ensure_ascii=True))
    else:
        for row in result["checks"]:
            print(f"{row['status']} {row['name']}: {row['detail']}")
        for detail in result["unverified"]:
            print(f"UNVERIFIED {detail}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
