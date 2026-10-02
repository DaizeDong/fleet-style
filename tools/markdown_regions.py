"""Locate Markdown blocks and matching backtick spans at their original offsets."""

from bisect import bisect_right
import re
import string


_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})([^\r\n]*)")
_TICKS = re.compile(r"`+")
_QUOTE = re.compile(r"^ {0,3}> ?")
_LIST = re.compile(r"^( {0,3})([-+*]|[0-9]{1,9}[.)])( +|$)")
_HEADING = re.compile(r"^ {0,3}#{1,6}(?:[ \t]|$)")
_SETEXT = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")
_THEMATIC = re.compile(r"^ {0,3}(?:(?:\* *){3,}|(?:- *){3,}|(?:_ *){3,})$")
_HTML_RAW = re.compile(r"^ {0,3}<(?:script|pre|style|textarea)(?:[ \t>]|$)", re.I)
_HTML_RAW_END = re.compile(r"</(?:script|pre|style|textarea)>", re.I)
_HTML_BLOCK_TAG = re.compile(
    r"^ {0,3}</?(?:address|article|aside|base|basefont|blockquote|body|caption|center|col|"
    r"colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|"
    r"frameset|h[1-6]|head|header|hr|html|iframe|legend|li|link|main|menu|menuitem|nav|"
    r"noframes|ol|optgroup|option|p|param|search|section|source|summary|table|tbody|td|"
    r"tfoot|th|thead|title|tr|track|ul)(?:[ \t]|/?>|$)", re.I)
_HTML_ATTRIBUTE = r"[A-Za-z_:][A-Za-z0-9_.:-]*(?:[ \t]*=[ \t]*(?:[^\s\"'=<>`]+|'[^']*'|\"[^\"]*\"))?"
_HTML_COMPLETE_TAG = re.compile(
    r"^ {0,3}(?:<[A-Za-z][A-Za-z0-9-]*(?:[ \t]+" + _HTML_ATTRIBUTE
    + r")*[ \t]*/?>|</[A-Za-z][A-Za-z0-9-]*[ \t]*>)[ \t]*$")
_HTML_SPECIAL = (
    (re.compile(r"^ {0,3}<!--"), re.compile(r"-->")),
    (re.compile(r"^ {0,3}<\?"), re.compile(r"\?>")),
    (re.compile(r"^ {0,3}<![A-Z]"), re.compile(r">")),
    (re.compile(r"^ {0,3}<!\[CDATA\["), re.compile(r"\]\]>")),
)
_INLINE_ATTRIBUTE = _HTML_ATTRIBUTE.replace("[ \\t]", "[ \\t\\r\\n]")
_INLINE_HTML = re.compile(
    r"(?:<[A-Za-z][A-Za-z0-9-]*(?:[ \t\r\n]+" + _INLINE_ATTRIBUTE
    + r")*[ \t\r\n]*/?>|</[A-Za-z][A-Za-z0-9-]*[ \t\r\n]*>"
    r"|<!--(?!>|->)(?:(?!--).)*?(?<!-)-->"
    r"|<\?.*?\?>|<![A-Z][^>]*>|<!\[CDATA\[.*?\]\]>)", re.S)
_AUTOLINK = re.compile(
    r"<(?:[A-Za-z][A-Za-z0-9+.-]{1,31}:[^\s<>]*"
    r"|[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*)>")


def escaped(text, position):
    """Whether an odd run of backslashes precedes a punctuation character."""
    start = position
    while start and text[start - 1] == "\\":
        start -= 1
    return (position - start) % 2 == 1


def _cell_ranges(text, start, end):
    """Split a known table row before inline parsing, keeping escaped pipes."""
    left = start
    for position in range(start, end):
        if text[position] == "|" and not escaped(text, position):
            yield left, position
            left = position + 1
    yield left, end


def _table_fields(content):
    fields = [content[left:right].strip() for left, right in _cell_ranges(content, 0, len(content))]
    if len(fields) == 1:
        return []
    if not fields[0]:
        fields.pop(0)
    if fields and not fields[-1]:
        fields.pop()
    return fields


def _delimiter_columns(content):
    fields = _table_fields(content)
    return len(fields) if fields and all(re.fullmatch(r":?-+:?", field) for field in fields) else 0


def _fence_start(content):
    match = _FENCE.match(content)
    if match:
        marker, info = match.groups()
        if marker[0] != "`" or "`" not in info:
            return marker
    return None


def _continue_containers(content, containers):
    """Strip only prefixes belonging to the previous line's open containers."""
    for index, (kind, width) in enumerate(containers):
        if kind == "quote":
            match = _QUOTE.match(content)
            if not match:
                return content, containers[:index]
            content = content[match.end():]
        elif content.strip() and not content.startswith(" " * width):
            return content, containers[:index]
        else:
            content = content[width:]
    return content, containers[:]


def _list_start(content, in_paragraph=False):
    match = _LIST.match(content)
    if not match or _THEMATIC.fullmatch(content):
        return None
    indent, marker, spaces = match.groups()
    padding = len(spaces) if 1 <= len(spaces) <= 4 else 1
    width = len(indent) + len(marker) + padding
    if in_paragraph and (marker[0].isdigit() and marker[:-1] != "1" or not content[width:].strip()):
        return None
    return width


def _html_start(content, in_paragraph=False):
    """Return an HTML block's end rule; a None rule ends at a blank line.

    CommonMark's seven HTML block forms do not parse Markdown inline code.
    Only a complete generic tag (type 7) cannot interrupt an open paragraph.
    """
    if _HTML_RAW.match(content):
        return (_HTML_RAW_END,)
    for opening, ending in _HTML_SPECIAL:
        if opening.match(content):
            return (ending,)
    if _HTML_BLOCK_TAG.match(content) or not in_paragraph and _HTML_COMPLETE_TAG.fullmatch(content):
        return (None,)
    return None


def _interrupts_paragraph(content):
    return (not content.strip() or _QUOTE.match(content) or _HEADING.match(content)
            or _THEMATIC.fullmatch(content) or _SETEXT.fullmatch(content)
            or _fence_start(content) or _list_start(content, in_paragraph=True) is not None
            or _html_start(content, in_paragraph=True) is not None)


def _original_column(line, expanded_column):
    """Map a stripped container prefix back through tab expansion."""
    column = 0
    for index, char in enumerate(line):
        if column >= expanded_column:
            return index
        column += 4 - column % 4 if char == "\t" else 1
    return len(line)


def _label_end(text, opening, end):
    """Find a reference label's closing bracket without treating its ticks as code."""
    cursor = opening + 1
    while cursor < end and cursor - opening <= 1000:
        char = text[cursor]
        if char == "\\" and cursor + 1 < end and text[cursor + 1] in string.punctuation:
            cursor += 2
            continue
        if char == "[":
            return None
        if char == "]":
            return cursor + 1 if cursor - opening - 1 <= 999 else None
        cursor += 1
    return None


def _label_key(label):
    return re.sub(r"[ \t\r\n]+", " ", label.strip()).casefold()


def _destination_end(text, cursor, end, *, empty=False):
    if cursor >= end:
        return None
    if text[cursor] == "<":
        cursor += 1
        while cursor < end and text[cursor] != ">":
            if text[cursor] in "\r\n<":
                return None
            if text[cursor] == "\\" and cursor + 1 < end and text[cursor + 1] in string.punctuation:
                cursor += 1
            cursor += 1
        return cursor + 1 if cursor < end else None
    start, depth = cursor, 0
    while cursor < end:
        char = text[cursor]
        if char == "\\" and cursor + 1 < end and text[cursor + 1] in string.punctuation:
            cursor += 2
            continue
        if char.isspace() or char == ")" and depth == 0:
            break
        if ord(char) < 32 or ord(char) == 127 or char == "<":
            return None
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        cursor += 1
    return cursor if not depth and (empty or cursor > start) else None


def _title_end(text, cursor, end):
    marker = text[cursor]
    closer = ")" if marker == "(" else marker
    start = cursor
    cursor += 1
    while cursor < end and text[cursor] != closer:
        if marker == "(" and text[cursor] == "(":
            return None
        if text[cursor] == "\\" and cursor + 1 < end and text[cursor + 1] in string.punctuation:
            cursor += 1
        cursor += 1
    if cursor == end or re.search(r"\n[ \t\r]*\n", text[start:cursor]):
        return None
    return cursor + 1


def _reference_definition_end(text, start):
    match = re.compile(r" {0,3}\[").match(text, start)
    if not match:
        return None
    opening = match.end() - 1
    label_end = _label_end(text, opening, len(text))
    if label_end is None or text[label_end:label_end + 1] != ":":
        return None
    label = _label_key(text[opening + 1:label_end - 1])
    if not label:
        return None
    cursor = label_end + 1
    while cursor < len(text) and text[cursor].isspace():
        cursor += 1
    destination = _destination_end(text, cursor, len(text))
    if destination is None:
        return None
    line_end = text.find("\n", destination)
    if line_end < 0:
        line_end = len(text)
    base_end = min(line_end + 1, len(text)) if not text[destination:line_end].strip() else None
    cursor = destination
    while cursor < len(text) and text[cursor].isspace():
        cursor += 1
    if cursor > destination and cursor < len(text) and text[cursor] in "\"'(":
        title_end = _title_end(text, cursor, len(text))
        if title_end is not None:
            tail = title_end
            while tail < len(text) and text[tail] in " \t\r":
                tail += 1
            if tail == len(text) or text[tail] == "\n":
                return min(tail + 1, len(text)), label
    return (base_end, label) if base_end is not None else None


def _reference_definition_lines(lines, index, containers, first_content):
    """Consume consecutive definitions at a paragraph start in the same container."""
    if not re.match(r"^ {0,3}\[", first_content):
        return 0, set()
    parts = [first_content + "\n"]
    for position in range(index + 1, len(lines)):
        line = lines[position]
        expanded = line.expandtabs(4).rstrip("\r\n")
        content, continued = _continue_containers(expanded, containers)
        if continued != containers or _interrupts_paragraph(content):
            break
        parts.append(content + "\n")
    text = "".join(parts)
    cursor, labels = 0, set()
    while cursor < len(text):
        definition = _reference_definition_end(text, cursor)
        if definition is None:
            break
        cursor, label = definition
        labels.add(label)
    return text[:cursor].count("\n"), labels


def _blocks(text, definitions=None):
    """Yield code blocks and individual inline blocks using original offsets.

    Container continuation is mandatory inside code blocks. Only paragraphs can
    continue lazily without repeating a quote prefix or list indentation.
    """
    containers = []
    fence = None
    indented = None
    paragraph = None
    previous = None
    table = False
    html = None
    offset = 0
    lines = text.splitlines(keepends=True)
    reference_until = 0
    for index, line in enumerate(lines):
        end = offset + len(line)
        if index < reference_until:
            offset = end
            continue
        expanded = line.expandtabs(4).rstrip("\r\n")
        content, continued = _continue_containers(expanded, containers)
        same_container = continued == containers
        if fence is not None:
            if same_container:
                match = _FENCE.match(content)
                if match:
                    marker, tail = match.groups()
                    if marker[0] == fence[1] and len(marker) >= fence[2] and not tail.strip():
                        yield "code", fence[0], end
                        fence = None
                offset = end
                continue
            yield "code", fence[0], offset
            fence = None
        if indented is not None:
            if same_container and (not content.strip() or content.startswith("    ")):
                offset = end
                continue
            yield "code", indented, offset
            indented = None
        if html is not None:
            ending = html[0]
            if same_container and (ending is not None or content.strip()):
                yield "html", offset, end
                if ending is not None and ending.search(content):
                    html = None
                offset = end
                continue
            html = None
        if not same_container and paragraph is not None and not _interrupts_paragraph(content):
            # A lazy continuation remains in the same inline block.
            offset = end
            continue
        if not same_container and paragraph is not None:
            yield "inline", paragraph, offset
            paragraph = None
            previous = None
        containers = continued
        new_container = False
        while True:
            quote = _QUOTE.match(content)
            width = _list_start(content, in_paragraph=paragraph is not None)
            if not quote and width is None:
                break
            if paragraph is not None:
                yield "inline", paragraph, offset
                paragraph = None
                previous = None
            new_container = True
            if quote:
                containers.append(("quote", 0))
                content = content[quote.end():]
            else:
                containers.append(("list", width))
                content = content[width:]
        content_offset = offset + _original_column(line, len(expanded) - len(content))
        if table:
            if (same_container and not new_container and not _interrupts_paragraph(content)
                    and _html_start(content) is None):
                yield "table", content_offset, end
                offset = end
                continue
            table = False
        columns = _delimiter_columns(content)
        if (columns and paragraph is not None and previous is not None
                and previous[3] == containers and len(_table_fields(previous[2])) == columns):
            if paragraph < previous[0]:
                yield "inline", paragraph, previous[0]
            yield "table", previous[4], previous[1]
            yield "table", content_offset, end
            paragraph = previous = None
            table = True
            offset = end
            continue
        opening_html = _html_start(content, in_paragraph=paragraph is not None)
        if opening_html is not None:
            if paragraph is not None:
                yield "inline", paragraph, offset
            paragraph = previous = None
            yield "html", offset, end
            ending = opening_html[0]
            if ending is None or not ending.search(content):
                html = opening_html
            offset = end
            continue
        marker = _fence_start(content)
        if paragraph is None:
            count, labels = _reference_definition_lines(lines, index, containers, content)
            if count:
                reference_end = offset + sum(map(len, lines[index:index + count]))
                yield "reference", offset, reference_end
                if definitions is not None:
                    definitions.update(labels)
                reference_until = index + count
                previous = None
                offset = end
                continue
        if marker or not content.strip() or _HEADING.match(content) or _SETEXT.fullmatch(content) or _THEMATIC.fullmatch(content):
            if paragraph is not None:
                yield "inline", paragraph, offset
                paragraph = None
            previous = None
            if marker:
                fence = (offset, marker[0], len(marker))
            elif _HEADING.match(content):
                yield "inline", offset, end
        elif paragraph is None and content.startswith("    "):
            indented = offset
        elif paragraph is None:
            paragraph = offset
        if paragraph is not None:
            previous = (offset, end, content, containers[:], content_offset)
        offset = end
    if fence is not None:
        yield "code", fence[0], len(text)
    elif indented is not None:
        yield "code", indented, len(text)
    elif paragraph is not None:
        yield "inline", paragraph, len(text)


def fenced_regions(text):
    """Yield block-code ranges, stopping unclosed fences at their container end."""
    for kind, start, end in _blocks(text):
        if kind == "code":
            yield start, end


def table_regions(text):
    """Yield recognized table rows after their original container prefixes."""
    for kind, start, end in _blocks(text):
        if kind == "table":
            yield start, end


def _link_tail_end(text, opening, end):
    """Recognize a complete inline link destination and optional quoted title."""
    cursor = opening + 1
    while cursor < end and text[cursor].isspace():
        cursor += 1
    cursor = _destination_end(text, cursor, end, empty=True)
    if cursor is None:
        return None
    before_space = cursor
    while cursor < end and text[cursor].isspace():
        cursor += 1
    if cursor > before_space and cursor < end and text[cursor] in "\"'(":
        cursor = _title_end(text, cursor, end)
        if cursor is None:
            return None
        while cursor < end and text[cursor].isspace():
            cursor += 1
    if cursor < end and text[cursor] == ")" and not re.search(r"\n[ \t\r]*\n", text[opening:cursor]):
        return cursor + 1
    return None


def _inline_regions(text, start, end, definitions=(), link_syntax=None):
    """Protect code and literals, optionally recording recognized link delimiters."""
    by_length = {}
    for run in _TICKS.finditer(text, start, end):
        by_length.setdefault(run.end() - run.start(), []).append(run.start())
    cursor, brackets = start, []
    while cursor < end:
        char = text[cursor]
        if char == "\\" and cursor + 1 < end and text[cursor + 1] in string.punctuation:
            cursor += 2
            continue
        if char == "`":
            run = _TICKS.match(text, cursor, end)
            length = run.end() - cursor
            same_length = by_length.get(length, [])
            next_position = bisect_right(same_length, cursor)
            if next_position < len(same_length):
                closing = same_length[next_position] + length
                yield cursor, closing
                cursor = closing
            else:
                cursor = run.end()
            continue
        if char == "<":
            match = _INLINE_HTML.match(text, cursor, end) or _AUTOLINK.match(text, cursor, end)
            if match:
                yield cursor, match.end()
                cursor = match.end()
                continue
        if char == "[":
            image = cursor > start and text[cursor - 1] == "!" and not escaped(text, cursor - 1)
            brackets.append({"position": cursor, "image": image, "active": True})
        elif char == "]" and brackets:
            opener = brackets.pop()
            if not opener["active"]:
                cursor += 1
                continue
            closing = None
            if cursor + 1 < end and text[cursor + 1] == "(":
                closing = _link_tail_end(text, cursor + 1, end)
                if closing is not None:
                    # Dash repair protects metadata; prose extraction also removes its delimiters.
                    if cursor + 2 < closing - 1:
                        yield cursor + 2, closing - 1
            if closing is None:
                label = _label_key(text[opener["position"] + 1:cursor])
                reference_end = cursor + 1
                if reference_end < end and text[reference_end] == "[":
                    suffix = _label_end(text, reference_end, end)
                    if suffix is not None:
                        explicit = _label_key(text[reference_end + 1:suffix - 1])
                        label = explicit or label
                        reference_end = suffix
                    else:
                        label = ""
                if label in definitions:
                    closing = reference_end
                    if closing > cursor + 1:
                        yield cursor + 1, closing
            if closing is not None:
                if link_syntax is not None:
                    opening = opener["position"] - int(opener["image"])
                    link_syntax.extend(((opening, opener["position"] + 1), (cursor, closing)))
                if not opener["image"]:
                    for earlier in brackets:
                        if not earlier["image"]:
                            earlier["active"] = False
                cursor = closing
                continue
        cursor += 1


def _excluded_regions(text, tables=False, link_syntax=None):
    definitions = set()
    blocks = list(_blocks(text, definitions))
    for kind, start, end in blocks:
        if kind in {"code", "reference"} or tables and kind == "table":
            yield start, end
        elif kind == "table":
            for left, right in _cell_ranges(text, start, end):
                yield from _inline_regions(text, left, right, definitions, link_syntax)
        elif kind == "inline":
            yield from _inline_regions(text, start, end, definitions, link_syntax)


def code_regions(text):
    """Yield protected code and literal inline ranges within their block bounds."""
    yield from _excluded_regions(text)


def without_code(text, *, tables=False):
    """Keep rendered link labels and prose, excluding code, metadata and optional tables."""
    link_syntax = []
    regions = [(left, right, " ") for left, right in
               _excluded_regions(text, tables=tables, link_syntax=link_syntax)]
    regions.extend((left, right, "") for left, right in link_syntax)
    pieces = []
    start = 0
    for left, right, replacement in sorted(regions, key=lambda region: (region[0], -region[1])):
        if right <= start:
            continue
        pieces.extend((text[start:max(start, left)], replacement))
        start = right
    pieces.append(text[start:])
    return "".join(pieces)
