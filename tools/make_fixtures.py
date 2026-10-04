#!/usr/bin/env python3
"""Reproduce the synthetic inputs used by the style scanner contract tests."""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path("tests/fixtures/scan_cases.json")


def physical_line_cases():
    """Build code whose literal separators must not become Markdown line breaks."""
    cases = []
    for newline in ("\n", "\r\n", "\r"):
        for separator in ("\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"):
            for marker in ("```", "~~~"):
                for placement in ("before", "after"):
                    embedded = ("literal" + separator + marker if placement == "before"
                                else marker + separator)
                    code = newline.join((marker + "text", embedded,
                                         "first synthetic vector branch \u2014 literal",
                                         "second buffer return signal output token", marker, "", ""))
                    cases.append({"name": f"physical fence {newline!r} {separator!r} {marker} {placement}",
                                  "code": code, "input": code + "Outside \u2014 prose.\n",
                                  "expected": code + "Outside, prose.\n",
                                  "wrap_input": code + "Outside paragraph\ncontinues here.\n",
                                  "wrap_expected": code + "Outside paragraph continues here.\n"})
    return cases


def fixture_bytes():
    """Return exact UTF-8 bytes; no runtime or personal data is read."""
    cases = {
        "clean": "A synthetic guide with ordinary punctuation.\n",
        "dash": "A synthetic guide \u2014 with an aside.\n",
        "broken_python": "def sample(:\n    # synthetic prose \u2014 unfinished\n",
        "invalid_utf8_hex": "fffe616263",
        "comment_inputs": {
            "sample.js": "// synthetic prose \u2014 comment\n",
            "sample.yml": "# synthetic prose \u2014 comment\n",
            "sample.sh": "# synthetic prose \u2014 comment\n",
            "sample.ps1": "# synthetic prose \u2014 comment\n",
            "sample.cmd": "rem synthetic prose \u2014 comment\n",
            "hook": "#!/usr/bin/env sh\n# synthetic prose \u2014 comment\n",
        },
        "gitlink_index_row": "160000 " + "0" * 40 + " 0\tdependency\0",
        "wrap_added_diff": "@@ -1,0 +2,1 @@\n+++ synthetic continuation\n",
        "wrap_binary_diff": "diff --git a/guide.md b/guide.md\nindex 1111111..2222222 100644\nBinary files a/guide.md and b/guide.md differ\n",
        "wrap_incomplete_diff": "diff --git a/guide.md b/guide.md\n--- a/guide.md\n+++ b/guide.md\n",
        "wrap_mode_diff": "diff --git a/guide.md b/guide.md\nold mode 100644\nnew mode 100755\n",
        "wrap_inputs": {
            "wrapped": "Synthetic paragraph begins here\nand continues here.\n",
            "clean": "Synthetic paragraph stays on one line.\n",
            "allow": "guide.md # Synthetic archived-document exemption\n",
            "attributes": ["*.md -diff\n", "*.md binary\n"],
            "message": "Synthetic subject\n\nSynthetic paragraph begins here\nand continues here.\n",
            "fences": [
                "````markdown\n```\nalpha\nbeta\n```\n````\n",
                "```text\n~~~\nalpha\nbeta\n~~~\n```\n",
                "> ````markdown\n> ```\n> alpha\n> beta\n> ```\n> ````\n",
            ],
        },
        "filenames": ["r\u00e9sum\u00e9.md", "\u91c7\u8d2d.md", "a file.md", "-guide.md"],
        "framed_paths": ["new name.md", "line\nbreak.md"],
        "added_diff": "@@ -1 +1 @@\n-old line\n+new line\n@@ -8,0 +9,2 @@\n+first\n+second\n",
    }
    repair = []
    for count in (1, 2, 3):
        for prefix in ("", "- "):
            first = prefix + "Synthetic first line" + "\\" * count
            text = first + "\ncontinued here.\n"
            repair.append({"name": f"backslash break {count} {bool(prefix)}", "input": text,
                           "expected": text if count % 2 else first + " continued here.\n"})
    for opening, closing in (("<pre>", "</pre>"), ("<PRE class='synthetic'>", "</PRE>"),
                             ("<textarea>", "</textarea>")):
        protected = opening + "\n\nSynthetic first line\nsecond line\n\n" + closing + "\n\n"
        repair.append({"name": opening, "input": protected + cases["wrap_inputs"]["wrapped"],
                       "expected": protected + "Synthetic paragraph begins here and continues here.\n"})
    allowed = "<!-- wrap-guard:allow -->\n- Synthetic list item\ncontinued here.\n"
    repair.append({"name": "allowed list", "input": allowed, "expected": allowed})
    for newline in ("\n", "\r\n", "\r"):
        for separator in ("\u2028", "\u0085", "\x0b"):
            protected = newline.join(("```text", "Synthetic" + separator + "literal", "```", "", ""))
            repair.append({"name": f"literal bytes {newline!r} {separator!r}",
                           "input": protected + "Synthetic prose" + newline + "continues." + newline,
                           "expected": protected + "Synthetic prose continues." + newline})
    cases["wrap_inputs"]["repair_cases"] = repair
    repair.extend({"name": case["name"], "input": case["wrap_input"],
                   "expected": case["wrap_expected"]} for case in physical_line_cases())
    scissors = "# ------------------------ >8 ------------------------\n"
    tail = "Discarded synthetic first line\ndiscarded second line.\n"
    cases["wrap_inputs"]["message_cases"] = [
        {"name": "only discarded tail wraps", "input": "Synthetic subject\n\nClean body.\n" + scissors + tail,
         "exit_code": 0, "line": None},
        {"name": "visible body wraps", "input": "Synthetic subject\n\nFirst body line\nsecond body line.\n" + scissors + tail,
         "exit_code": 1, "line": 3},
        {"name": "comment lines preserve coordinates", "input": "Synthetic subject\n\n# Synthetic comment\n# Another comment\nFirst body line\nsecond body line.\n" + scissors + tail,
         "exit_code": 1, "line": 5},
    ]
    return (json.dumps(cases, ensure_ascii=True, indent=2) + "\n").encode("utf-8")


def markdown_fixture_bytes():
    dash = "\u2014"
    outside = f"Outside {dash} prose."
    fixed = "Outside, prose."
    cases = {
        "markdown": [
            {"name": "double inline", "input": f"``a {dash} b`` {outside}", "expected": f"``a {dash} b`` {fixed}"},
            {"name": "embedded backtick", "input": f"``a ` b {dash} c`` {outside}", "expected": f"``a ` b {dash} c`` {fixed}"},
            {"name": "mixed fence", "input": f"```text\n~~~\na {dash} b\n```\n{outside}", "expected": f"```text\n~~~\na {dash} b\n```\n{fixed}"},
            {"name": "shorter fence", "input": f"````text\n```\na {dash} b\n````\n{outside}", "expected": f"````text\n```\na {dash} b\n````\n{fixed}"},
            {"name": "closer with text", "input": f"```text\n``` still code\na {dash} b\n```\n{outside}", "expected": f"```text\n``` still code\na {dash} b\n```\n{fixed}"},
            {"name": "tilde fence", "input": f"~~~~text\n~~~\na {dash} b\n~~~~\n{outside}", "expected": f"~~~~text\n~~~\na {dash} b\n~~~~\n{fixed}"},
            {"name": "escaped table pipe in code", "input": f"| `\\| {dash} item` | {dash} |", "expected": f"| `\\| {dash} item` | none |"},
            {"name": "escaped table pipe in prose", "input": f"| value \\| {dash} suffix | {dash} |", "expected": "| value \\|, suffix | none |"},
            {"name": "multiline inline", "input": f"A ``multi\na {dash} b\nline`` {outside}", "expected": f"A ``multi\na {dash} b\nline`` {fixed}"},
            {"name": "unmatched backtick", "input": f"A `open {dash} prose.", "expected": "A `open, prose."},
            {"name": "escaped backtick", "input": f"A \\`escaped {dash} prose.", "expected": "A \\`escaped, prose."},
            {"name": "placeholder collision", "input": f"\u00000\u0000 ``a {dash} b`` {outside}", "expected": f"\u00000\u0000 ``a {dash} b`` {fixed}"},
        ],
        "code_blocks": [
            "~~~\nshared vector branch value buffer return sample tuple signal input output token\n~~~\n",
            "````\n```\nshared vector branch value buffer return sample tuple signal input output token\n```\n````\n",
            "```\nshared vector branch value buffer return sample tuple signal input output token\n",
        ],
        "prose_a": "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu\n",
        "prose_b": "orange violet amber green copper silver purple indigo yellow black white teal\n",
        "marker": "gitdir: synthetic\n",
        "physical_lines": physical_line_cases(),
    }
    return (json.dumps(cases, ensure_ascii=True, indent=2) + "\n").encode("utf-8")


def block_fixture_bytes():
    """Build synthetic Markdown block boundaries without consulting local files."""
    dash = "\u2014"
    outside = f"Outside {dash} prose."
    fixed = "Outside, prose."
    shared = "shared vector branch value buffer return sample tuple signal input output token"
    paragraphs = []
    for ticks in ("`", "``"):
        for blank in ("", "   ", "\t"):
            for newline in ("\n", "\r\n"):
                separator = newline + blank + newline
                text = f"First {ticks}unfinished{separator}{outside}{separator}Last {ticks}unfinished"
                paragraphs.append({"name": repr((ticks, blank, newline)), "input": text,
                                   "expected": text.replace(outside, fixed)})
    boundary_lines = ("# Heading", "- Item", "1. Item", "> Quote", "---", "===")
    boundaries = []
    for line in boundary_lines:
        text = f"First `unfinished\n{line} {dash} body\nLast `unfinished"
        if line in ("---", "==="):
            text = f"First `unfinished\n{line}\n{outside}\nLast `unfinished"
        boundaries.append({"name": line, "input": text,
                           "expected": text.replace(f" {dash} ", ", ")})
    wrappers = [
        ("quote", "> ", "> "),
        ("nested quote", "> > ", "> > "),
        ("bullet list", "- ", "  "),
        ("ordered list", "12. ", "    "),
        ("quote list", "> - ", ">   "),
        ("list quote", "- > ", "  > "),
        ("nested list", "- outer\n  - ", "    "),
        ("later list block", "- item\n\n  ", "  "),
        ("tab list", "-\t", "\t"),
    ]
    fences, unclosed, code_blocks = [], [], []
    for name, opening, continuation in wrappers:
        for marker in ("```", "~~~", "````", "~~~~"):
            code = f"{opening}{marker}text\n{continuation}literal {dash} value\n{continuation}{marker}\n"
            fences.append({"name": f"{name} {marker}", "input": code + outside,
                           "expected": code + fixed})
            block = f"{opening}{marker}\n{continuation}{shared}\n{continuation}{marker}\n"
            if "outer" not in opening and "item" not in opening:
                code_blocks.append(block)
            open_code = f"{opening}{marker}\n{continuation}literal {dash} value\n"
            unclosed.append({"name": f"{name} {marker}", "input": open_code + outside,
                             "expected": open_code + fixed})
    multiline = []
    for prefix, continuation in (("", ""), ("> ", "> "), ("- ", "  "), ("> ", ""), ("- ", "")):
        for ticks in ("`", "``"):
            code = f"{prefix}A {ticks}first\n{continuation}literal {dash} value\n{continuation}last{ticks} "
            multiline.append({"name": repr((prefix, continuation, ticks)), "input": code + outside,
                              "expected": code + fixed})
    duplicate = []
    for blank in ("", "   ", "\t"):
        separator = "\n" + blank + "\n"
        duplicate.append(f"Opening `unfinished{separator}{shared}{separator}Closing `unfinished")
    cases = {"paragraphs": paragraphs, "block_starts": boundaries, "fences": fences,
             "unclosed": unclosed, "multiline": multiline, "code_blocks": code_blocks,
             "duplicate_prose": duplicate, "shared_prose": shared}
    return (json.dumps(cases, ensure_ascii=True, indent=2) + "\n").encode("utf-8")


def table_fixture_bytes():
    """Synthetic table boundaries and escaped delimiter runs."""
    dash = "\u2014"
    header = "| alpha | beta | gamma |\n| --- | :---: | ---: |\n"
    cross_cells, cross_rows, cell_code = [], [], []
    for ticks in ("`", "``"):
        row = f"| {ticks}open | {dash} | close{ticks} |\n"
        cross_cells.append({"name": ticks, "input": header + row,
                            "expected": header + row.replace(f" {dash} ", " none ")})
        rows = f"| {ticks}open | value | last |\n| middle | {dash} | last |\n| first | value | close{ticks} |\n"
        cross_rows.append({"name": ticks, "input": header + rows,
                           "expected": header + rows.replace(f" {dash} ", " none ")})
        for code in (f"{ticks}literal {dash} value{ticks}", f"{ticks}literal \\| {dash} value{ticks}"):
            row = f"| {code} | {dash} | last |\n"
            cell_code.append({"name": code, "input": header + row,
                              "expected": header + f"| {code} | none | last |\n"})
    contextual = []
    for opening, continuation in (("> ", "> "), ("- ", "  "), ("> - ", ">   "), ("- > ", "  > ")):
        lines = ["| alpha | beta | gamma |", "| --- | --- | --- |", f"| `open | text {dash} body | close` |"]
        text = opening + lines[0] + "\n" + "\n".join(continuation + line for line in lines[1:]) + "\n"
        contextual.append({"name": opening, "input": text, "expected": text.replace(f"text {dash} body", "text, body")})
    ordinary = []
    for text in (f"Ordinary `literal | {dash} value` Outside {dash} prose.",
                 f"| `literal | {dash} value` |\n| --- | --- | --- |\nOutside {dash} prose.",
                 f"Ordinary `literal\nvalue | {dash} body\nlast` Outside {dash} prose."):
        ordinary.append({"name": text.splitlines()[0], "input": text,
                         "expected": text.replace(f"Outside {dash} prose.", "Outside, prose.")})
    escaped_runs = []
    for length in (1, 2, 3):
        ticks = "`" * length
        for backslashes in (1, 2, 3, 4):
            opening = "\\" * backslashes + "`" * (length + backslashes % 2)
            code = f"{opening}literal {dash} body{ticks}"
            text = code + f" Outside {dash} prose."
            escaped_runs.append({"name": repr((length, backslashes)), "input": text,
                                 "expected": code + " Outside, prose."})
    cases = {"cross_cells": cross_cells, "cross_rows": cross_rows, "cell_code": cell_code,
             "contextual": contextual, "ordinary": ordinary, "escaped_runs": escaped_runs}
    return (json.dumps(cases, ensure_ascii=True, indent=2) + "\n").encode("utf-8")


def input_fixture_bytes():
    """Generate prose, HTML and malformed input cases without reading user data."""
    shared = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"
    dash = "\u2014"
    tables = []
    for header, delimiter, row in (
        ("| alpha | beta |", "| --- | --- |", f"| {shared} | value |"),
        ("alpha | beta", "--- | ---", f"{shared} | value"),
    ):
        for opening, continuation in (("", ""), ("> ", "> "), ("- ", "  "), ("> - ", ">   ")):
            tables.append(opening + header + "\n" + continuation + delimiter + "\n" + continuation + row + "\n")
    ordinary = [f"| {shared} |\n", f"alpha | beta\nnot a delimiter\n{shared}",
                f"| {shared} | value |\n| --- | --- | --- |\n"]
    html = []
    for opening, closing in (("<div>", "</div>"), ("<script>", "</script>"),
                             ("<!--", "-->"), ("<?sample", "?>"),
                             ("<!DOCTYPE sample [", ">"), ("<![CDATA[", "]]>"),
                             ('<sample-card label="value">', "</sample-card>")):
        for prefix in ("", "> "):
            body = f"literal `{shared} {dash} body`"
            text = prefix + opening + "\n" + prefix + body + "\n" + prefix + closing + "\n"
            html.append({"input": text, "expected": text.replace(f" {dash} ", ", ")})
    after_html = [
        f"<div>\ntext\n</div>\n\nA `literal {dash} value` Outside {dash} prose.",
        f"<!-- text -->\nA `literal {dash} value` Outside {dash} prose.",
        f"> <div>\n> text\nOutside {dash} prose.\n\nA `literal {dash} value`.",
        f"An ordinary paragraph\n<span>\nA `literal {dash} value` Outside {dash} prose.",
        f"An ordinary <span>`literal {dash} value`</span> Outside {dash} prose.",
    ]
    code = [f"```html\n<div>\n`literal {dash} value`\n</div>\n```\n",
            f"    <div>\n    `literal {dash} value`\n    </div>\n"]
    cases = {"shared": shared, "tables": tables, "ordinary": ordinary,
             "html": html, "after_html": after_html, "code": code,
             "invalid_utf8_hex": (shared.encode("utf-8") + b"\n\xff\n").hex(),
             "invalid_thresholds": ["nan", "NaN", "inf", "-inf", "-0.01", "100.01"],
             "marker": "gitdir: synthetic\n"}
    return (json.dumps(cases, ensure_ascii=True, indent=2) + "\n").encode("utf-8")


def syntax_fixture_bytes():
    """Generate inline syntax and table layout cases without external inputs."""
    dash = "\u2014"
    shared = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"
    prefixes = [
        '<span title="literal ` attribute">label</span>',
        '<!-- literal ` comment -->',
        '[label](https://example.com/`path)',
        '[label](https://example.com/ "literal ` title")',
        '[label](<https://example.com/`path> \'literal title\')',
    ]
    literal = []
    for prefix in prefixes:
        text = f"Before {prefix} {shared} {dash} body ` suffix."
        literal.append({"input": text, "expected": text.replace(f" {dash} ", ", ")})
    protected = [
        f'Before `literal <span title="value"> {dash} body` Outside {dash} prose.',
        f'Before [literal `{dash} body`](https://example.com/) Outside {dash} prose.',
        f'Before <span title="literal {dash} attribute">label</span> Outside {dash} prose.',
        f'Before [label](https://example.com/{dash}path "title") Outside {dash} prose.',
        f'Before \\[label](`literal {dash} body`) Outside {dash} prose.',
    ]
    tables = []
    for outer in (False, True):
        header = "| alpha | beta |" if outer else "alpha | beta"
        delimiter = "| --- | --- |" if outer else "--- | ---"
        for opening, continuation in (("", ""), ("> ", "> "), ("- ", "  "),
                                       ("> - ", ">   "), ("- > ", "  > ")):
            for code in (False, True):
                first = f"`literal \\| {dash} body`" if code else dash
                row = f"{first} | {dash} detail"
                expected = f"{first if code else 'none'} | - detail"
                if outer:
                    row, expected = f"| {row} |", f"| {expected} |"
                prefix = opening + header + "\n" + continuation + delimiter + "\n" + continuation
                tables.append({"input": prefix + row + "\n", "expected": prefix + expected + "\n"})
    cases = {"shared": shared, "literal": literal, "protected": protected,
             "tables": tables, "ancestor_name": "synthetic-alias"}
    return (json.dumps(cases, ensure_ascii=True, indent=2) + "\n").encode("utf-8")


def link_fixture_bytes():
    """Generate reference-definition and link/image precedence examples."""
    dash = "\u2014"
    shared = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"
    definitions = [
        '[ref]: https://example.com/`',
        '[ref]: https://example.com/ "literal ` title"',
        "[ref]: https://example.com/ 'literal ` title'",
        '[ref]: https://example.com/\n  "literal ` title"',
        '[ref]:\n  https://example.com/`',
        '[ref]: <https://example.com/`>\n  "multiline\n  title"',
        '[two\n words]: https://example.com/`',
        '[ref]: https://example.com/`\n[second]: /another',
        f'[ref]: <https://example.com/{dash}> "literal {dash} ` title"',
    ]
    visible = []
    for definition in definitions:
        source = definition + f'\n{shared} {dash} tail`\n'
        expected = definition + f'\n{shared}, tail`\n'
        for first, later in (("", ""), ("> ", "> "), ("- ", "  "),
                             ("> - ", ">   "), ("- > ", "  > ")):
            def wrap(value):
                return ''.join((first if i == 0 else later) + line
                               for i, line in enumerate(value.splitlines(keepends=True)))
            visible.append({'input': wrap(source), 'expected': wrap(expected)})
    protected = []
    for inner in ('[inner](https://example.com/)', '*[inner](https://example.com/)*',
                  '[inner][ref]', '[ref][]', '[ref]'):
        source = f'[outer {inner}](dest`) {shared} {dash} tail`\n'
        if '(https' not in inner:
            source += '\n[ref]: https://example.com/\n'
        protected.append(source)
    images = [
        f'[outer ![image](https://example.com/)](dest`) {shared} {dash} tail`\n',
        f'![outer [inner](https://example.com/)](dest`) {shared} {dash} tail`\n',
        f'[outer ![image][ref]](dest`) {shared} {dash} tail`\n\n[ref]: /image\n',
    ]
    visible.extend({'input': value, 'expected': value.replace(f' {dash} ', ', ')} for value in images)
    literal = [
        f'[ref]: /literal{dash}path\n\nVisible {dash} prose.\n',
        f'[label][literal`id] {shared} {dash} tail`\n\n[literal`id]: /target\n',
        f'[ref]: /target "title with {dash} value"\nVisible {dash} prose.\n',
    ]
    visible.extend({'input': value, 'expected': value.replace(f' {dash} prose', ', prose')
                    .replace(f'{shared} {dash}', f'{shared},')} for value in literal)
    interrupted = f'[ref]: /target "literal`\n# Heading\n{shared} {dash} tail` title"\n'
    visible.append({'input': interrupted, 'expected': interrupted.replace(f' {dash} ', ', ')})
    invalid = [
        f'[]: /literal`\n{shared} {dash} tail`\n',
        f'[ref]: /literal` trailing\n{shared} {dash} tail`\n',
        f'[ref]: /literal` "unclosed\n{shared} {dash} tail`\n',
        f'Paragraph [ref]: /literal`\n{shared} {dash} tail`\n',
    ]
    return (json.dumps({'shared': shared, 'visible': visible, 'protected': protected,
                        'invalid': invalid}, ensure_ascii=True, indent=2) + '\n').encode('utf-8')


def prose_fixture_bytes():
    """Generate parser-aware duplication examples without any runtime data."""
    shared = "copper silver nickel cobalt zinc tin lead iron"
    filler = "orchard meadow canyon glacier plateau valley forest coast"
    visible = [
        r'\[guide](prefix ' + shared + ' suffix)',
        r'\\\[guide](prefix ' + shared + ' suffix)',
        'guide](prefix ' + shared + ' suffix)',
        '[outer [inner](/target)](prefix ' + shared + ' suffix)',
        '[outer [inner][ref]](prefix ' + shared + ' suffix)\n\n[ref]: /target\n',
    ]
    labels = [
        '[' + shared + '](/target)',
        '[' + shared + '][ref]\n\n[ref]: /target\n',
        '[' + shared + '][]\n\n[' + shared + ']: /target\n',
        '[' + shared + ']\n\n[' + shared + ']: /target\n',
        '[ref]: /target\n\n[' + shared + '][REF]\n',
        '![' + shared + '](/image)',
        '![' + shared + '][ref]\n\n[ref]: /image\n',
        '![' + shared + '][]\n\n[' + shared + ']: /image\n',
        '![' + shared + ']\n\n[' + shared + ']: /image\n',
    ]
    protected = [
        '[guide](/target "prefix ' + shared + ' suffix")',
        '[guide][ref]\n\n[ref]: /target "prefix ' + shared + ' suffix"\n',
        '`' + shared + '`',
    ]
    spelling = [
        {'input': 's[ilver](/target)', 'expected': 'silver'},
        {'input': '[sil](/target)ver', 'expected': 'silver'},
        {'input': 's[il][ref]ver\n\n[ref]: /target\n', 'expected': 'silver'},
        {'input': 's![il](/image)ver', 'expected': 'silver'},
        {'input': '[literal][missing]', 'expected': '[literal][missing]'},
        {'input': r'\[literal](tail)', 'expected': r'\[literal](tail)'},
        {'input': '[outer [inner](/target)](tail)', 'expected': '[outer inner](tail)'},
    ]
    return (json.dumps({'shared': shared, 'filler': filler, 'visible': visible,
                        'labels': labels, 'protected': protected, 'spelling': spelling},
                       ensure_ascii=True, indent=2) + '\n').encode('utf-8')


def worktree_fixture_bytes():
    """Generate path-state and content cases without observing the local filesystem."""
    cases = json.loads("{\"content\":\"A synthetic guide \\u2014 with an aside.\\n\",\"fixed\":\"A synthetic guide, with an aside.\\n\",\"clean\":\"A synthetic neighbor with ordinary punctuation.\\n\",\"changed_content\":\"A synthetic draft \\u2014 with an aside.\\n\",\"outside\":\"An external synthetic target \\u2014 must stay unchanged.\\n\",\"unsafe\":[{\"name\":\"leaf_symlink\",\"where\":\"leaf\",\"kind\":\"symlink\"},{\"name\":\"ancestor_symlink\",\"where\":\"ancestor\",\"kind\":\"symlink\"},{\"name\":\"leaf_reparse\",\"where\":\"leaf\",\"kind\":\"reparse\"},{\"name\":\"ancestor_reparse\",\"where\":\"ancestor\",\"kind\":\"reparse\"},{\"name\":\"hardlink_leaf\",\"where\":\"leaf\",\"kind\":\"hardlink\"}],\"changes\":[\"leaf_symlink\",\"ancestor_symlink\",\"leaf_reparse\",\"ancestor_reparse\",\"hardlink_leaf\",\"replacement\",\"content\"],\"phases\":[\"after_transform\",\"before_open\"]}")
    return (json.dumps(cases, ensure_ascii=True, indent=2) + "\n").encode("utf-8")


def worktree_regression_bytes():
    return '"""Generated worktree-path regressions; all contents and path states are synthetic."""\nimport contextlib\nimport io\nimport json\nimport os\nfrom pathlib import Path\nimport stat\nimport sys\nimport tempfile\nfrom types import SimpleNamespace\nimport unittest\nfrom unittest import mock\n\nsys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))\nimport dash_guard as guard\n\nCASES = json.loads(Path(__file__).with_name("worktree_cases.json").read_text(encoding="utf-8"))\n\n\nclass WorktreePathContracts(unittest.TestCase):\n    def setUp(self):\n        workspace = tempfile.TemporaryDirectory(prefix="style-worktree-")\n        self.addCleanup(workspace.cleanup)\n        self.root = Path(workspace.name)\n        self.repo = self.root / "repo"\n        self.target = self.repo / "nested" / "guide.txt"\n        self.target.parent.mkdir(parents=True)\n        self.neighbor = self.repo / "neighbor.txt"\n        self.outside = self.root / "outside.txt"\n        self.target.write_text(CASES["content"], encoding="utf-8")\n        self.neighbor.write_text(CASES["clean"], encoding="utf-8")\n        self.outside.write_text(CASES["outside"], encoding="utf-8")\n        self.paths = ["nested/guide.txt", "neighbor.txt"]\n\n    def invoke(self, *args):\n        out, err = io.StringIO(), io.StringIO()\n        argv = ["dash_guard.py", "--repo", str(self.repo), *map(str, args)]\n        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(out), \\\n                contextlib.redirect_stderr(err), \\\n                mock.patch.object(guard, "_tracked", return_value=(self.paths, self.paths)):\n            code = guard.cli()\n        return code, out.getvalue(), err.getvalue()\n\n    def metadata(self, original, case, path, *args, **kwargs):\n        info = original(path, *args, **kwargs)\n        selected = self.target if case["where"] == "leaf" else self.target.parent\n        if os.path.normcase(os.path.abspath(path)) != os.path.normcase(str(selected)):\n            return info\n        fields = {name: getattr(info, name) for name in (\n            "st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")}\n        fields["st_file_attributes"] = getattr(info, "st_file_attributes", 0)\n        if case["kind"] == "symlink":\n            fields["st_mode"] = stat.S_IFLNK | 0o777\n        elif case["kind"] == "reparse":\n            fields["st_file_attributes"] |= 1024\n        else:\n            fields["st_nlink"] = 2\n        return SimpleNamespace(**fields)\n\n    def test_linked_paths_are_incomplete_before_any_payload_open(self):\n        original_lstat, original_open = os.lstat, open\n        for case in CASES["unsafe"]:\n            for args in (("--tree",), ("--tree", "--fix"),\n                         (self.target,), ("--fix", self.target)):\n                with self.subTest(case=case["name"], args=args):\n                    opened = []\n                    def access(path, *positional, **keywords):\n                        if os.path.normcase(os.path.abspath(path)) == os.path.normcase(str(self.target)):\n                            opened.append(positional)\n                        return original_open(path, *positional, **keywords)\n                    with mock.patch.object(guard.os, "lstat",\n                            side_effect=lambda path, *a, **k: self.metadata(original_lstat, case, path, *a, **k)), \\\n                            mock.patch("builtins.open", side_effect=access):\n                        code, out, err = self.invoke(*args)\n                    self.assertEqual(code, 1, (out, err))\n                    self.assertNotIn("clean", out.lower())\n                    self.assertIn("could NOT be examined", err)\n                    self.assertIn("unsafe worktree path", err)\n                    self.assertEqual(opened, [])\n                    self.assertEqual(self.target.read_text(encoding="utf-8"), CASES["content"])\n                    self.assertEqual(self.outside.read_text(encoding="utf-8"), CASES["outside"])\n                    if "--fix" in args:\n                        self.assertIn("fixed 0 line(s)", out)\n\n    def test_target_changes_after_read_or_at_open_are_not_repaired(self):\n        original_lstat, original_open = os.lstat, open\n        original_process = guard.process_text\n        by_name = {case["name"]: case for case in CASES["unsafe"]}\n        for name in CASES["changes"]:\n            for phase in CASES["phases"]:\n                with self.subTest(change=name, phase=phase):\n                    self.target.write_text(CASES["content"], encoding="utf-8")\n                    state = {"changed": False}\n                    def change():\n                        state["changed"] = True\n                        if name == "replacement":\n                            replacement = self.target.with_suffix(".tmp")\n                            replacement.write_text(CASES["changed_content"], encoding="utf-8")\n                            os.replace(replacement, self.target)\n                        elif name == "content":\n                            self.target.write_text(CASES["changed_content"], encoding="utf-8")\n                    def metadata(path, *args, **kwargs):\n                        if state["changed"] and name in by_name:\n                            return self.metadata(original_lstat, by_name[name], path, *args, **kwargs)\n                        return original_lstat(path, *args, **kwargs)\n                    def process(*args, **kwargs):\n                        result = original_process(*args, **kwargs)\n                        if phase == "after_transform" and args[0] == CASES["content"]:\n                            change()\n                        return result\n                    def access(path, mode="r", *args, **kwargs):\n                        if os.path.normcase(os.path.abspath(path)) == os.path.normcase(str(self.target)) and mode == "w" and phase == "before_open":\n                            change()\n                        return original_open(path, mode, *args, **kwargs)\n                    with mock.patch.object(guard.os, "lstat", side_effect=metadata), \\\n                            mock.patch.object(guard, "process_text", side_effect=process), \\\n                            mock.patch("builtins.open", side_effect=access):\n                        code, out, err = self.invoke("--tree", "--fix")\n                    self.assertTrue(state["changed"], "scheduled mutation was not reached")\n                    self.assertEqual(code, 1, (out, err))\n                    self.assertIn("fixed 0 line(s)", out)\n                    self.assertIn("could not repair", err)\n                    expected = CASES["changed_content"] if name in {"replacement", "content"} else CASES["content"]\n                    self.assertEqual(self.target.read_text(encoding="utf-8"), expected)\n                    self.assertEqual(self.outside.read_text(encoding="utf-8"), CASES["outside"])\n\n    def test_descriptor_redirection_cannot_read_or_truncate_external_target(self):\n        original_open = os.open\n        for phase in ("read", "write"):\n            with self.subTest(phase=phase):\n                self.target.write_text(CASES["content"], encoding="utf-8")\n                flags_seen = []\n                def descriptor(path, flags, *args, **kwargs):\n                    writing = bool(flags & (os.O_WRONLY | os.O_RDWR))\n                    if os.path.normcase(os.path.abspath(path)) == os.path.normcase(str(self.target)) and writing == (phase == "write"):\n                        flags_seen.append(flags)\n                        return original_open(self.outside, flags, *args, **kwargs)\n                    return original_open(path, flags, *args, **kwargs)\n                with mock.patch.object(guard.os, "open", side_effect=descriptor):\n                    code, out, err = self.invoke("--tree", "--fix")\n                self.assertEqual(code, 1, (out, err))\n                self.assertIn("fixed 0 line(s)", out)\n                self.assertTrue(flags_seen)\n                self.assertTrue(all(not flags & (os.O_TRUNC | os.O_CREAT) for flags in flags_seen))\n                self.assertEqual(self.target.read_text(encoding="utf-8"), CASES["content"])\n                self.assertEqual(self.outside.read_text(encoding="utf-8"), CASES["outside"])\n\n    def test_open_return_topology_change_is_not_repaired(self):\n        original_lstat, original_open = os.lstat, open\n        for case in CASES["unsafe"]:\n            with self.subTest(case=case["name"]):\n                self.target.write_text(CASES["content"], encoding="utf-8")\n                state = {"changed": False}\n                def metadata(path, *args, **kwargs):\n                    if state["changed"]:\n                        return self.metadata(original_lstat, case, path, *args, **kwargs)\n                    return original_lstat(path, *args, **kwargs)\n                def access(path, mode="r", *args, **kwargs):\n                    stream = original_open(path, mode, *args, **kwargs)\n                    if os.path.normcase(os.path.abspath(path)) == os.path.normcase(str(self.target)) and mode == "w":\n                        state["changed"] = True\n                    return stream\n                with mock.patch.object(guard.os, "lstat", side_effect=metadata), \\\n                        mock.patch("builtins.open", side_effect=access):\n                    code, out, err = self.invoke("--tree", "--fix")\n                self.assertTrue(state["changed"], "scheduled mutation was not reached")\n                self.assertEqual(code, 1, (out, err))\n                self.assertIn("fixed 0 line(s)", out)\n                self.assertIn("could not repair", err)\n                self.assertEqual(self.target.read_text(encoding="utf-8"), CASES["content"])\n                self.assertEqual(self.outside.read_text(encoding="utf-8"), CASES["outside"])\n\n    def test_safe_ordinary_file_still_repairs_and_truncates(self):\n        code, out, err = self.invoke("--tree", "--fix")\n        self.assertEqual(code, 0, (out, err))\n        self.assertIn("fixed 1 line(s) across 1 file(s)", out)\n        self.assertEqual(self.target.read_text(encoding="utf-8"), CASES["fixed"])\n        self.assertEqual(self.neighbor.read_text(encoding="utf-8"), CASES["clean"])\n        self.assertEqual(self.outside.read_text(encoding="utf-8"), CASES["outside"])\n\n    def test_edited_file_can_be_scanned_and_repaired_again(self):\n        for content in (CASES["changed_content"], CASES["content"]):\n            self.target.write_text(content, encoding="utf-8")\n            code, out, err = self.invoke("--tree", "--fix")\n            self.assertEqual(code, 0, (out, err))\n            self.assertIn("fixed 1 line(s) across 1 file(s)", out)\n            code, out, err = self.invoke("--tree")\n            self.assertEqual(code, 0, (out, err))\n            self.assertIn("2 file(s) examined", out)\n        self.assertEqual(self.target.read_text(encoding="utf-8"), CASES["fixed"])\n        self.assertEqual(self.outside.read_text(encoding="utf-8"), CASES["outside"])\n\n    def test_staged_blobs_do_not_inspect_worktree_topology(self):\n        with mock.patch.object(guard, "_git", return_value=str(self.repo) + "\\n"), \\\n                mock.patch.object(guard, "_staged", return_value=(self.paths, self.paths)), \\\n                mock.patch.object(guard, "_index_text", return_value=CASES["clean"]), \\\n                mock.patch.object(guard, "_worktree_snapshot", side_effect=AssertionError("worktree consulted")):\n            code, out, err = self.invoke("--staged")\n        self.assertEqual(code, 0, (out, err))\n        self.assertIn("2 file(s) examined", out)\n\n\nif __name__ == "__main__":\n    unittest.main()\n'.encode("utf-8")


def doc_fixture_bytes():
    """Generate every document contract example from synthetic constants."""
    from copy import deepcopy

    version = "1.2.0-rc.1+build.7"
    philosophy = ("The tool prevents unfinished guides from becoming accepted deliverables. "
                  "It uses bounded deterministic checks so results stay reproducible. "
                  "These checks cover structure; reviewers still assess meaning and tradeoffs.")
    chinese = ("这个工具避免把尚未完成的文档交付给使用者。检查范围固定，结果可以重复。"
               "自动检查只判断结构，设计取舍和真实能力仍由评审确认。")
    files = {
        "README.md": f"# Synthetic tool\n\n![Version](https://img.shields.io/badge/version-{version}-blue)\n\n"
                     f"## Design Philosophy\n\n{philosophy}\n\n## Installation\n\n"
                     "Run the declared setup entry.\n\n```sh\npython tools/install.py\n```\n\n"
                     "[Roadmap](ROADMAP.md#planned)\n",
        "README_CN.md": f"# 合成工具\n\n![Version](https://img.shields.io/badge/version-{version}-blue)\n\n"
                        f"## 设计哲学\n\n{chinese}\n\n## 安装\n\n运行安装入口。\n\n"
                        "```sh\npython tools/install.py\n```\n",
        "ROADMAP.md": f"# Roadmap\n\nCurrent: **v{version}**\n\n## v{version} (current)\n\n"
                      "The bounded document checks are implemented.\n\n## Planned\n\n"
                      "- TODO: evaluate broader language support after independent review.\n",
        "CHANGELOG.md": f"# Changelog\n\n## [Unreleased]\n\n### Changed\n\n"
                        "- Refined the installation explanation.\n\n"
                        f"## [{version}] - 2024-06-10\n\n- Added bounded document checking.\n\n"
                        "## [1.1.0] - 2024-06-01\n\n- Added synthetic guide examples.\n",
        ".claude-plugin/plugin.json": json.dumps({"name": "synthetic", "version": version}),
        "tools/install.py": "print('synthetic setup')\n",
    }
    cases = [{"name": "valid skill with future TODO and historical release", "files": deepcopy(files)}]

    def case(name, failure, path=None, old=None, new=None, profile="skill", stage="accepted"):
        data = deepcopy(files)
        if path is not None:
            if old is None:
                data[path] = new
            else:
                data[path] = data[path].replace(old, new)
        result = {"name": name, "files": data, "profile": profile, "stage": stage}
        if failure:
            result["failure"] = failure
        cases.append(result)
        return data

    case("star heading is not philosophy", "readme.philosophy", "README.md", "Design Philosophy", "⭐ Read this first")
    case("generic filler is not philosophy", "readme.philosophy", "README.md", philosophy, "Explain the design choices here.")
    case("philosophy after install fails", "readme.philosophy", "README.md", None,
         files["README.md"].replace(f"## Design Philosophy\n\n{philosophy}\n\n", "") +
         f"\n## Design Philosophy\n\n{philosophy}\n")
    case("Chinese philosophy missing", "readme.philosophy", "README_CN.md", "设计哲学", "先读这里")
    case("current README TODO fails", "docs.placeholders", "README.md", "Run the declared setup entry.", "TODO: write setup details.")
    case("draft may carry TODO", None, "README.md", "Run the declared setup entry.", "TODO: write setup details.", stage="draft")
    case("draft philosophy placeholder is explicit", None, "README.md", philosophy, "TODO: write the design philosophy.", stage="draft")
    case("release stage still rejects current TODO", "docs.placeholders", "README.md", "Run the declared setup entry.", "TODO: write setup details.", stage="release")
    case("repository draft flag cannot bypass accepted", "docs.placeholders", "README.md", "Run the declared setup entry.", "TODO: write setup details.")[".doc-contract.json"] = '{"stage":"draft"}'
    case("missing install heading fails", "readme.install", "README.md", "## Installation", "## Usage")
    case("missing declared install file fails", "readme.install", "README.md", "tools/install.py", "tools/missing.py")
    case("prerelease suffix mismatch fails", "version.current", "README_CN.md", version, "1.2.0-rc.2+build.7")
    case("package manifest conflict fails", "version.source")["package.json"] = '{"version":"1.2.0-rc.2+build.7"}'
    case("duplicate manifest field fails", "version.source", ".claude-plugin/plugin.json", None,
         '{"version":"1.2.0","version":"1.3.0"}')
    case("invalid semver fails", "version.source", ".claude-plugin/plugin.json", version, "01.2.0")
    case("malformed release date fails", "changelog.releases", "CHANGELOG.md", "2024-06-10", "2024-02-30")
    case("unparseable release date fails", "changelog.releases", "CHANGELOG.md", "2024-06-10", "tomorrow")
    case("future release date fails", "changelog.releases", "CHANGELOG.md", "2024-06-10", "9999-06-10")
    case("hidden newer release fails", "changelog.releases", "CHANGELOG.md", "## [1.1.0]", "## [2.0.0]")
    case("release date order fails", "changelog.releases", "CHANGELOG.md", "2024-06-01", "2024-07-01")
    case("release scaffold TODO fails", "docs.placeholders", "CHANGELOG.md", "Added bounded document checking.", "TODO: write release notes.")
    case("empty Unreleased remains valid", None, "CHANGELOG.md", "### Changed\n\n- Refined the installation explanation.\n\n", "")
    case("release requires substantive latest notes", "changelog.releases", "CHANGELOG.md", "- Added bounded document checking.", "", stage="release")
    case("conflicting roadmap current fails", "roadmap.current", "ROADMAP.md", "## Planned", "Current: v2.0.0\n\n## Planned")
    case("current placeholder after planned fails", "docs.placeholders", "ROADMAP.md", None,
         f"# Roadmap\n\nCurrent: v{version}\n\n## Planned\n\n- TODO: evaluate another language.\n\n"
         "## Current behavior\n\nTODO: explain the accepted behavior.\n")
    case("numeric prerelease with leading zero fails", "version.source", ".claude-plugin/plugin.json", version, "1.2.0-01")
    case("current roadmap invalid semver fails", "roadmap.current", "ROADMAP.md", version, "01.2.0")
    case("current version field mismatch fails", "version.current", "README.md", "# Synthetic tool", "# Synthetic tool\n\nVersion: **v1.3.0**")
    case("malformed current version field fails", "version.current", "README.md", "# Synthetic tool", "# Synthetic tool\n\nVersion: **v01.3.0**")
    case("escaped literal link is not destination", None, "README.md", "[Roadmap](ROADMAP.md#planned)", "[Roadmap](ROADMAP.md#planned)\n\\[literal](missing.md)")
    case("ancestor traversal link fails", "links.local", "README.md", "ROADMAP.md#planned", "../missing.md")
    case("missing root README fails", "docs.required").pop("README_CN.md")
    data = case("submodule install missing initialization fails", "readme.install")
    data[".gitmodules"] = '[submodule "kit"]\n path = kit\n url = https://example.com/kit.git\n'
    data["README.md"] = data["README.md"].replace("python tools/install.py", "git clone https://example.com/synthetic.git")
    data["README_CN.md"] = data["README_CN.md"].replace("python tools/install.py", "git clone --recurse-submodules https://example.com/synthetic.git")
    data = case("submodule install recursive initialization valid", None)
    data[".gitmodules"] = '[submodule "kit"]\n path = kit\n url = https://example.com/kit.git\n'
    for name in ("README.md", "README_CN.md"):
        data[name] = data[name].replace("python tools/install.py", "git clone https://example.com/synthetic.git\ngit submodule update --init --recursive")
    case("missing roadmap current fails", "roadmap.current", "ROADMAP.md", None, "# Roadmap\n\n## Planned\n\nFuture work remains under review.\n")
    case("manifest-linked current roadmap valid", None, "ROADMAP.md", None,
         "# Roadmap\n\n## Current\n\nVersion follows [plugin manifest](.claude-plugin/plugin.json).\n\n"
         "Bounded checks are implemented.\n\n## Planned\n\n- TODO: review another language.\n")
    data = case("bare purposeful current with manifest valid", None, "ROADMAP.md", None,
                "# Roadmap\n\n## Current\n\nThe current implementation checks root documentation.\n")
    data["README.md"] = data["README.md"].replace("ROADMAP.md#planned", "ROADMAP.md#current")
    case("missing local root link fails", "links.local", "README.md", "ROADMAP.md#planned", "MISSING.md")
    case("missing root anchor fails", "links.local", "README.md", "ROADMAP.md#planned", "ROADMAP.md#missing")
    case("reference link missing destination fails", "links.local", "README.md", "[Roadmap](ROADMAP.md#planned)", "[Roadmap][plan]\n\n[plan]: MISSING.md")
    data = case("literal links in inline code are not destinations", None)
    data["README.md"] += "\nLiteral syntax `[sample](missing.md)` and `TODO` are code examples.\n"
    data = case("protected payload link is metadata only", None)
    data["README.md"] += "\n[Payload](eval/poison.json#never-open)\n"
    data["eval/poison.json"] = "This synthetic payload is not documentation."
    data = case("software requires no plugin", None, profile="software")
    del data[".claude-plugin/plugin.json"]
    data["package.json"] = json.dumps({"version": version})
    data = case("manifest-free current roadmap is version source", None)
    del data[".claude-plugin/plugin.json"]
    cases.append({"name": "valid companion only maintenance entry", "profile": "companion",
                  "files": {"README.md": "# Synthetic companion\n\nConfiguration and real DATA stay private and versioned.\n\n"
                           "Restore by cloning this private repository. Retain historical records during maintenance.\n"}})
    cases.append({"name": "valid companion DATA maintenance entry", "profile": "companion",
                  "files": {"DATA.md": "# Private DATA\n\nRestore and retain the versioned configuration in this private companion.\n"}})
    cases.append({"name": "missing companion entry fails", "profile": "companion", "files": {}, "failure": "docs.required"})
    return (json.dumps(cases, ensure_ascii=True, indent=2) + "\n").encode("utf-8")


def artifacts():
    return {"scan_cases.json": fixture_bytes(), "markdown_cases.json": markdown_fixture_bytes(),
            "block_cases.json": block_fixture_bytes(), "table_cases.json": table_fixture_bytes(),
            "input_cases.json": input_fixture_bytes(), "syntax_cases.json": syntax_fixture_bytes(),
            "link_cases.json": link_fixture_bytes(), "prose_cases.json": prose_fixture_bytes(),
            "worktree_cases.json": worktree_fixture_bytes(),
            "_worktree_contracts.py": worktree_regression_bytes(), "doc_cases.json": doc_fixture_bytes()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--out", type=Path, help="write flat fixture basenames in this directory")
    args = parser.parse_args()
    directory = args.out if args.out is not None else ROOT / FIXTURE.parent
    failed = False
    for name, expected in artifacts().items():
        path = directory / name
        if args.check:
            if not path.is_file() or path.read_bytes() != expected:
                print(f"fixture differs: {name}")
                failed = True
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected)
            print(f"generated {name}")
    if args.check and not failed:
        print("synthetic fixtures match")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
