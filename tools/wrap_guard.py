#!/usr/bin/env python3
# wrap-guard:allow-file -- 本文件按设计带着被折断的示例；判据见 _SELF_MARKER
"""wrap_guard: 找出（并修好）**因为「这一行太长」而被折断的正文段落**。

机主的全局规则（`feedback_no_hard_wrap_in_paragraphs`）：**行长不是断文本的理由，接收端自己会按它的宽度折行。** 一个段落写成连续的一整行，段落之间用空行分隔。

规则原文列明了管辖范围：邮件正文、申诉/工单表单、issue/PR 描述、**commit message body**、给用户粘贴用的任何草稿，以及文档正文。同样列明了**只有**这些地方该换行：段落之间（空行）、列表项之间、代码块内、以及 ASCII 表格之类靠对齐表意的内容。

## 这个闸门为什么必须存在

这条规则被**重复违反了**。机主 2026-07-27 明确要求过一次（起因是一份按 ~70 字符硬折的申诉草稿），2026-08-02 就同一件事连说三遍，2026-09-23 又一次 —— 那一次的规模是：一个仓的 11 份文档里 168 个散文段被折断（542 行），当天 24 条 commit message 里 20 条违规。

**一条被反复违反的规则，缺的不是重申，是一个会红的判据。** 破折号那条规则走过完全一样的路：先是写进记忆、再是被反复违反、最后做成 `dash_guard.py` 才真的停住。这份是它的同胞。

## 判据

`check_text()` 报两种形态，两种的下一步动作不同，所以分开报：

    paragraph   一个纯散文段占了两行以上 —— 段落内被插了换行符
    list_item   一个列表项的文本跨了行 —— 「列表项之间」可以换行，项内不行

不报的（规则原文列明该换行的地方，以及不是散文的东西）：

    围栏代码块 ``` ~~~          缩进四格的代码块
    表格 | a | b |              引用 >        标题 #
    YAML front matter           HTML 块       链接引用定义 [x]: url
    行尾两个空格（Markdown 里那是一个显式的 <br>，是意图不是意外）
    setext 标题下面那条 === / ---

## 范围：这一版**不管 Python 的 docstring 和注释**

这是一个**说出来的缺口，不是一个沉默的缺口**。理由有两条，都可以被推翻：代码里的换行属于规则原文说的「代码」那一侧；而且一个仓里的 docstring 动辄上万行，全量改写的风险远大于收益。

要扩到 docstring，扩 `_EXT_KIND` 就行 —— 但**扩之前先对着真语料量一次召回**，别让这段文字继续说它没覆盖的事。

## 模式（恰好一个动作）

    --check  （默认）逐条打印 file:line，有发现退 1
    --fix    就地展开。**它不是闸门**：修好之后退 0，只有读不了的文件才退 1，把
             --fix 接进 CI 等于装了一个不可能失败的检查。

展开时的拼接规则是确定的：两侧都是中日韩文字或全角标点 -> 直接粘；否则中间补一个半角空格。**这一条是靠量出来的**，不是审美：中文之间插空格会在渲染后留下可见的缝。

## 目标集

    --message FILE   一份 commit message（`commit-msg` 钩子用这个）
    --staged         git 暂存区里的文本 blob（pre-commit 用）
    --tree  （默认） 所有被 git 跟踪的文本文件
    paths...         显式给文件（覆盖上面）

退出码：0 干净，1 有发现（或 --fix 下有读不了的文件），2 **根本没跑起来**（git 不可用、不是工作树）。**2 永远不许被读成 0** —— 一次「没检查」和一次「检查过了是干净的」必须是两个输出。

## 豁免

文件里出现 `wrap-guard:allow-file` 就整份跳过（本文件就是这么做的，因为它带着示例）。单段豁免在 Markdown 里写 `<!-- wrap-guard:allow -->`，放在那一段前面一行。

豁免要留痕：`--check` 会把跳过的文件数打出来，**一个被跳过的文件和一个干净的文件不许长得一样**。
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
from pathlib import Path

_SCAN_SPEC = importlib.util.spec_from_file_location(
    "_fleet_style_wrap_scan", Path(__file__).with_name("dash_guard.py"))
_SCAN = importlib.util.module_from_spec(_SCAN_SPEC)
_SCAN_SPEC.loader.exec_module(_SCAN)

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:                                                # pragma: no cover
    pass

_SELF_MARKER = "wrap-guard:allow-file"
_PARA_ALLOW = "wrap-guard:allow"

# 扫哪些后缀。`.md` 是主战场；`.txt` / `.rst` 同属散文。
# ⚠ `.py` **不在里面**，那是上面「范围」那一节说明过的缺口。
_EXT_KIND = {".md": "md", ".markdown": "md", ".txt": "prose", ".rst": "prose"}

_LIST = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+")
_TABLE = re.compile(r"^\s*\|")
_QUOTE = re.compile(r"^\s*>")
_HEADING = re.compile(r"^\s*#{1,6}\s")
_SETEXT = re.compile(r"^\s*(=+|-{3,})\s*$")
_LINKDEF = re.compile(r"^\s*\[[^\]]+\]:\s")
_HTML = re.compile(r"^\s*<")
# git trailer：`Co-Authored-By: …`、`Signed-off-by: …`、`Fixes: …`。
# 它们**按格式必须各占一行**，报它们等于让这个钩子挡下每一条带署名的提交。
# 只在 commit message 那一面生效, 在 Markdown 里 `Note: 某某` 是一句散文，
# 不是 trailer，拿同一条规则去套会悄悄放过真正的硬折行。
_TRAILER = re.compile(r"^[A-Za-z][A-Za-z0-9-]*:\s")
_INDENT_CODE = re.compile(r"^(\t| {4,})")

# 整行只有图片/链接（徽章行、图标行），**不是散文**。
# 2026-09-23 实测：母仓 README 顶部五个徽章各占一行，被这个闸门拼成了一整行。
# 渲染结果确实一样（Markdown 段落内的换行本就渲染成空格），但它们不是句子，
# 把它们接起来只会让下次改徽章变难。**判据按内容认**：把所有链接/图片记号
# 和空白剥掉之后什么都不剩，那一行就不是散文。
# **顺序是承重的：先剥图片，再剥链接。**
#
# 一个徽章是嵌套的 `[![alt](img)](href)`。把图片和链接写成一条带 `!?` 的正则，
# 在它身上会剥错位置：`[^\]]*` 在 `![alt]` 的那个 `]` 处就停了，于是匹配到的是
# `[![alt](img)`，外层链接的开方括号被内层图片吃掉，剩下一个 `](href)`,
# 再怎么重复替换都剥不动。实测第一版就是这样，徽章行照样被当成散文拼成一整行。
#
# 分成两条、按顺序来：图片先走，`[![alt](img)](href)` 变成 `[](href)`，
# 链接那条才咬得住。
_MD_TOKENS = (
    re.compile(r"!\[[^\]]*\]\([^)]*\)"),     # 图片
    re.compile(r"\[[^\]]*\]\([^)]*\)"),      # 链接
    re.compile(r"<[^>]+>|`[^`]*`"),          # HTML 标签 / 行内代码
)


def _only_links(ln: str) -> bool:
    """剥光链接之后**一个字都不剩** -> 它不是散文（徽章行、语言切换行）。

    判据是「还有没有文字」，不是「是不是空串」。`[English](a) | [中文版](b)`
    剥完剩一个 `|`，那是分隔符不是句子；要求一无所剩会把这种行判成散文，
    然后把它和下一行拼起来。
    """
    prev, cur = None, ln
    while prev != cur:
        prev = cur
        for pat in _MD_TOKENS:
            cur = pat.sub("", cur)
    return not any(ch.isalnum() or _is_cjk(ch) for ch in cur)


# Two trailing spaces or an unescaped trailing backslash request a hard break.
_EXPLICIT_BR = re.compile(r"\S {2,}$")


def _explicit_break(line: str) -> bool:
    return bool(_EXPLICIT_BR.search(line) or _SCAN._MARKDOWN.escaped(line, len(line)))


def _source_lines(text: str) -> list[str]:
    """Keep physical line endings; Unicode separators remain literal content."""
    return _SCAN._MARKDOWN.source_lines(text)

_CJK_RANGES = (
    (0x2E80, 0x9FFF), (0xF900, 0xFAFF), (0xFE30, 0xFE4F),
    (0xFF00, 0xFF65), (0x20000, 0x2FA1F),
)


def _is_cjk(ch: str) -> bool:
    """中日韩文字或全角标点。**判据按码位，不按 `unicodedata.east_asian_width`** ——
    后者会把「①」「→」这类符号也算成宽字符，而它们两侧该不该有空格与此无关。"""
    o = ord(ch)
    return any(lo <= o <= hi for lo, hi in _CJK_RANGES)


def join_lines(a: str, b: str) -> str:
    """把被折断的两行接回去。两侧都是中日韩就直接粘，否则补一个半角空格。"""
    a, b = a.rstrip(), b.lstrip()
    if not a:
        return b
    if not b:
        return a
    if _is_cjk(a[-1]) and _is_cjk(b[0]):
        return a + b
    return a + " " + b


class _Block:
    """一段连续的非空行，外加它从第几行开始。"""

    __slots__ = ("start", "lines")

    def __init__(self, start: int, lines: list[str]) -> None:
        self.start = start
        self.lines = lines


def _protected_lines(text: str) -> set[int]:
    """Preserve code and HTML using the shared parser's original block offsets."""
    regions = iter(_SCAN._MARKDOWN.code_and_html_regions(text))
    current = next(regions, None)
    protected = set()
    offset = 0
    for number, line in enumerate(_source_lines(text), 1):
        while current and offset >= current[1]:
            current = next(regions, None)
        if current and current[0] < offset + len(line):
            protected.add(number)
        offset += len(line)
    return protected


def _blocks(text: str) -> list[_Block]:
    """Group nonblank prose lines, excluding the shared parser's literal blocks."""
    out: list[_Block] = []
    buf: list[str] = []
    start = 0
    protected = _protected_lines(text)
    for i, raw in enumerate(_source_lines(text), 1):
        ln = raw.rstrip("\r\n")
        if i in protected:
            if buf:
                out.append(_Block(start, buf))
                buf = []
            continue
        if not ln.strip():
            if buf:
                out.append(_Block(start, buf))
                buf = []
            continue
        if not buf:
            start = i
        buf.append(ln)
    if buf:
        out.append(_Block(start, buf))
    return out


def _is_prose_line(ln: str, kind: str = "md") -> bool:
    """这一行是不是**散文**（而不是表格/引用/标题/代码/链接定义/HTML/trailer）。"""
    if kind == "message" and _TRAILER.match(ln):
        return False
    if _only_links(ln):
        return False
    return not (_TABLE.match(ln) or _QUOTE.match(ln) or _HEADING.match(ln)
                or _SETEXT.match(ln) or _LINKDEF.match(ln) or _HTML.match(ln)
                or _INDENT_CODE.match(ln))


def check_text(text: str, path: str = "<text>", kind: str = "md") -> list[dict]:
    """回一串发现。**空列表的意思是「查过了，干净」** —— 调用方要能把它和
    「压根没查」分开，所以扫不动的时候这个函数抛，不回空。"""
    if _SELF_MARKER in text:
        return []
    found: list[dict] = []
    lines = _source_lines(text)
    allowed: set[int] = set()
    for i, ln in enumerate(lines, 1):
        if _PARA_ALLOW in ln and _SELF_MARKER not in ln:
            allowed.add(i + 1)

    for blk in _blocks(text):
        if blk.start in allowed:
            continue
        if not all(_is_prose_line(ln, kind) for ln in blk.lines):
            # 块里混着表格/引用/代码/trailer：只查其中的列表项续行，
            # 段落规则对它不成立。
            _list_continuations(blk, found, path, kind)
            continue
        first = blk.lines[0]
        if _LIST.match(first) or any(_LIST.match(x) for x in blk.lines[1:]):
            # **一行标签后面紧跟一串列表项，中间不留空行，是标准写法。**
            # 2026-09-23 实测：`**Why:**` 加三条 `- …` 被整块判成了一个
            # 「占了 4 行的散文段」。只看第一行不够, 块里**任何一行**是
            # 列表项，段落规则对这一块就不成立，该问的是项内有没有续行。
            _list_continuations(blk, found, path, kind)
            continue
        if len(blk.lines) < 2:
            continue
        if any(_explicit_break(ln) for ln in blk.lines[:-1]):
            continue                    # 行尾双空格 = 显式换行，是意图
        found.append({
            "path": path, "line": blk.start, "kind": "paragraph",
            "lines": len(blk.lines),
            "quote": first.strip()[:70],
            "why": f"一个散文段占了 {len(blk.lines)} 行。段落内不许插换行符，"
                   f"一段写成一整行，接收端自己会按宽度折",
        })
    return found


def _list_continuations(blk: _Block, found: list[dict], path: str,
                        kind: str = "md") -> None:
    """列表项**内部**跨行。「列表项之间」可以换行，项内不行。"""
    for off, ln in enumerate(blk.lines):
        if off == 0:
            continue
        prev = blk.lines[off - 1]
        if not _LIST.match(prev):
            continue
        if _LIST.match(ln) or not _is_prose_line(ln, kind):
            continue
        if _explicit_break(prev):
            continue
        found.append({
            "path": path, "line": blk.start + off, "kind": "list_item",
            "lines": 2, "quote": ln.strip()[:70],
            "why": "列表项的文本跨了行。可以在**项与项之间**换行，项内不行",
        })


def fix_text(text: str) -> str:
    """Join reported spans only; preserve every byte outside those spans."""
    while rows := check_text(text):
        lines = _source_lines(text)
        # Work backwards so replacing a span preserves earlier source positions.
        for row in reversed(rows):
            start = row["line"] - (2 if row["kind"] == "list_item" else 1)
            end = start + row["lines"]
            body = [line.rstrip("\r\n") for line in lines[start:end]]
            ending = lines[end - 1][len(body[-1]):]
            joined = body[0]
            for continuation in body[1:]:
                joined = join_lines(joined, continuation)
            lines[start:end] = [joined + ending]
        text = "".join(lines)
        # A list may expose another continuation after its first pair is joined.
    return text


# --------------------------------------------------------------------------
# 目标集
# --------------------------------------------------------------------------

class GitError(RuntimeError):
    """git 跑不起来。**这不是「没东西可扫」** —— 它要退 2，不许退 0。"""


def _git(repo: Path, *args: str) -> str:
    try:
        return _SCAN._git(str(repo), *args)
    except _SCAN.GitError as error:
        raise GitError(str(error)) from error


def _tracked(repo: Path) -> list[Path]:
    out = _git(repo, "ls-files", "-z")
    links = _SCAN._gitlinks(str(repo))
    return [repo / p for p in out.split("\0") if p and p not in links]


def _staged(repo: Path) -> list[Path]:
    out = _git(repo, "diff", "--cached", "--no-ext-diff", "--no-textconv",
               "--name-only", "-z", "--diff-filter=ACMRTU")
    links = _SCAN._gitlinks(str(repo))
    return [repo / p for p in out.split("\0") if p and p not in links]


def _read_worktree(path: Path):
    snapshot = _SCAN._worktree_snapshot(path)
    if snapshot is None:
        raise FileNotFoundError(path)
    with _SCAN._open_worktree(path, "rb", snapshot) as stream:
        text = stream.read().decode("utf-8")
        if (_SCAN._worktree_snapshot(path) != snapshot or
                _SCAN._worktree_stamp(os.fstat(stream.fileno())) != snapshot[-1][1]):
            raise _SCAN._UnsafeWorktreePath("worktree target changed during read")
    return text, snapshot


def read_ignore(repo: Path, *, staged=False) -> list[tuple[str, str]]:
    """仓库自己声明的「这些路径不归这条规则管」。格式：`前缀 # 理由`。

    2026-09-23 由一次真实的越界逼出来：在一个仓里跑 `--tree`，它扫到 153 份
    文件、改写了 123 份 —— 其中大半是 `solver/archive/` 和几百份调研笔记。
    **归档件里的旧形态就该原样留着**，那正是「归档不是删除」的意思；
    而那个仓的另一条闸门（单源化）早就把 archive 排除在外了，
    这一条却不知道，因为**没有任何办法让仓库把它知道的事告诉工具**。

    理由是必填的：一张只有路径、没有理由的豁免表，三个月后没人敢删任何一行。
    """
    f = repo / ".wrap-allow"
    if staged:
        if not _git(repo, "ls-files", "-z", "--", ".wrap-allow"):
            return []
        text = _SCAN._index_text(str(repo), ".wrap-allow")
    else:
        try:
            text, _ = _read_worktree(f)
        except FileNotFoundError:
            return []
    out: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        prefix, _, why = line.partition("#")
        prefix, why = prefix.strip(), why.strip()
        if not prefix:
            continue
        if not why:
            raise ValueError(
                f".wrap-allow: {prefix!r} 没写理由。**一张只有路径、没有理由的"
                f"豁免表，三个月后没人敢删任何一行。** 格式是 `前缀 # 理由`")
        out.append((prefix, why))
    return out


def _eligible(paths, ignore: list[tuple[str, str]] | None = None,
              repo: Path | None = None) -> list[Path]:
    """筛出该扫的文件。豁免前缀**按仓库相对路径比**。

    第一版拿绝对路径去比，于是 `solver/archive/` 这样的前缀一条都匹配不上，
    而它**一声不响地全都放行了**：输出里照样写着「查了 153 份文件」，
    和豁免真的生效时唯一的区别是那个数字 —— 一个没人会去核对的数字。
    """
    keep = [p for p in paths if p.suffix.lower() in _EXT_KIND]
    if not ignore:
        return keep
    out = []
    for p in keep:
        rel = p.as_posix()
        if repo is not None:
            try:
                rel = p.absolute().relative_to(repo).as_posix()
            except ValueError:
                pass
        if not any(rel.startswith(pre) for pre, _ in ignore):
            out.append(p)
    return out


def _added_lines(repo: Path, path: Path) -> set[int]:
    """Return added post-image lines, or raise if Git cannot establish the range."""
    diff = _git(repo, "--literal-pathspecs", "diff", "--cached", "--no-ext-diff",
                "--no-textconv", "--no-color", "--text", "-U0", "--", str(path))
    added = set()
    current = None
    content_headers = False
    for line in diff.split("\n"):
        if line.startswith(("Binary files ", "GIT binary patch")):
            raise GitError("Git did not provide textual added-line ranges")
        if current is None and line.startswith(("--- ", "+++ ")):
            content_headers = True
        if line.startswith("@@"):
            match = _SCAN._HUNK.match(line)
            if match is None:
                raise GitError("unrecognized added-line hunk")
            current = int(match.group(1))
        elif current is not None and line.startswith("+"):
            added.add(current)
            current += 1
        elif current is not None and line.startswith(" "):
            current += 1
    if content_headers and current is None:
        raise GitError("Git content headers have no added-line hunk")
    return added


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="硬折行闸门：段落内不许有换行符")
    ap.add_argument("paths", nargs="*", help="显式要查的文件")
    ap.add_argument("--message", help="一份 commit message 文件（commit-msg 钩子用）")
    ap.add_argument("--staged", action="store_true", help="只查 git 暂存区")
    ap.add_argument("--tree", action="store_true", help="查所有被跟踪的文本文件（默认）")
    ap.add_argument("--fix", action="store_true", help="就地展开。**这不是闸门**")
    ap.add_argument("--added-only", action="store_true",
                    help="只报这次新增的行（配 --staged）")
    ap.add_argument("--repo", default=".", help="仓库根")
    a = ap.parse_args(argv)
    if (a.fix and a.staged or a.tree and (a.staged or a.added_only)
            or a.message and (a.fix or a.staged or a.tree or a.added_only or a.paths)):
        print("wrap_guard: incompatible target or repair modes", file=sys.stderr)
        return 2
    if a.added_only:
        a.staged = True

    if a.fix and a.added_only:
        print("wrap_guard: --fix 会重写整份文件，和 --added-only 放在一起等于"
              "把 --added-only 想跳过的存量也一并改了。两者不许同时给。",
              file=sys.stderr)
        return 2

    # --- commit message：它自成一个目标集，不经过 git 文件列表 ---
    if a.message:
        p = Path(a.message)
        try:
            text, _ = _read_worktree(p)
        except (OSError, UnicodeError, ValueError) as exc:
            print(f"wrap_guard: 读不了 {p}：{exc}", file=sys.stderr)
            return 2
        body = _message_body(text)
        found = check_text(body["text"], path=str(p), kind="message")
        for f in found:
            f["line"] = body["line_numbers"][f["line"] - 1]
        return _report(found, scanned=1, skipped=0, what="commit message")

    repo = Path(a.repo).absolute()
    try:
        if a.staged:
            repo = Path(_git(repo, "rev-parse", "--show-toplevel").removesuffix("\n"))
        ignored = [] if a.paths else read_ignore(repo, staged=a.staged)
    except (ValueError, OSError, GitError, _SCAN.GitError) as exc:
        print(f"wrap_guard: {exc}", file=sys.stderr)
        return 2
    try:
        if a.paths:
            # 显式点名的路径**不过豁免表**：点名就是意图，豁免表是给 --tree 的。
            targets = _eligible(Path(os.path.abspath(os.path.join(a.repo, x)))
                                if a.staged else Path(x) for x in a.paths)
            ignored = []
        elif a.staged:
            targets = _eligible(_staged(repo), ignored, repo)
        else:
            targets = _eligible(_tracked(repo), ignored, repo)
    except (GitError, _SCAN.GitError) as exc:
        # **「扫不动」和「扫干净了」必须是两个输出。**
        print(f"wrap_guard: 没能跑起来 —— {exc}", file=sys.stderr)
        return 2

    found: list[dict] = []
    skipped = 0
    fixed = 0
    if ignored:
        # **豁免要留痕。** 一个被声明排除的目录和一个干净的目录，
        # 在输出里不许长得一样。
        print(f"wrap_guard: {len(ignored)} 条路径前缀按 .wrap-allow 排除：")
        for pre, why in ignored:
            print(f"  {pre:<40} {why}")
    unreadable = 0
    for p in targets:
        try:
            if a.staged:
                rel = _SCAN._index_path(str(repo), str(p))
                text = _SCAN._index_text(str(repo), rel)
            else:
                text, snapshot = _read_worktree(p)
        except (OSError, ValueError, GitError, _SCAN.GitError) as error:
            print(f"wrap_guard: cannot examine {p}: {type(error).__name__}", file=sys.stderr)
            unreadable += 1
            continue
        if _SELF_MARKER in text:
            skipped += 1
            continue
        if a.fix:
            new = fix_text(text)
            if new != text:
                try:
                    with _SCAN._open_worktree(p, "wb", snapshot) as stream:
                        if (_SCAN._worktree_snapshot(p) != snapshot or
                                _SCAN._worktree_stamp(os.fstat(stream.fileno())) != snapshot[-1][1]):
                            raise _SCAN._UnsafeWorktreePath("worktree target changed before repair")
                        stream.write(new.encode("utf-8"))
                        stream.truncate()
                except (OSError, ValueError) as error:
                    print(f"wrap_guard: cannot repair {p}: {type(error).__name__}", file=sys.stderr)
                    unreadable += 1
                    continue
                fixed += 1
            continue
        rows = check_text(text, path=p.as_posix())
        if a.added_only and a.staged:
            try:
                keep = _added_lines(repo, p)
            except (GitError, _SCAN.GitError) as error:
                print(f"wrap_guard: added lines unavailable for {p}: {error}", file=sys.stderr)
                unreadable += 1
                continue
            git_lines = []
            git_line = 1
            for raw_line in _source_lines(text):
                git_lines.append(git_line)
                git_line += raw_line.count("\n")
            def touches_added(row):
                first = row["line"] - (1 if row["kind"] == "list_item" else 0)
                return any(git_lines[line - 1] in keep
                           for line in range(first, first + row["lines"]))
            rows = [row for row in rows if touches_added(row)]
        found.extend(rows)

    if a.fix:
        print(f"wrap_guard --fix：展开了 {fixed} 份文件"
              f"（跳过 {skipped} 份带豁免标记的，{unreadable} 份读不了）")
        # **--fix 不是闸门。** 它修好之后退 0；只有读不了的文件才退 1。
        return 1 if unreadable else 0
    return _report(found, scanned=len(targets) - unreadable, skipped=skipped, unreadable=unreadable, what="文件")


def _message_body(text: str) -> dict:
    """Drop the subject, comments and scissors tail while retaining source coordinates."""
    lines = _source_lines(text)
    keep: list[str] = []
    line_numbers: list[int] = []
    offset = 0
    started = False
    for i, raw in enumerate(lines):
        ln = raw.rstrip("\r\n")
        if _SCAN._SCISSORS.match(ln):
            break
        if ln.startswith("#"):
            if not started:
                offset = i + 1
            continue
        if not started:
            if i == 0:
                offset = 1
                continue                 # 标题行
            started = True
            offset = i
        keep.append(ln)
        line_numbers.append(i + 1)
    return {"text": "\n".join(keep), "offset": offset, "line_numbers": line_numbers}


def _report(found: list[dict], *, scanned: int, skipped: int, what: str,
            unreadable: int = 0) -> int:
    if unreadable:
        print(f"wrap_guard: incomplete ({scanned} file(s) examined, {unreadable} unreadable)")
        if not found:
            return 1
    if not found:
        # **把扫过多少、跳过多少打出来。** 一个被跳过的文件和一个干净的文件
        # 不许长得一样, 那正是「被喂了空的检查器」那个形状。
        print(f"wrap_guard: 干净（查了 {scanned} 份{what}，"
              f"跳过 {skipped} 份带豁免标记的）")
        return 0
    by_kind: dict[str, int] = {}
    for f in found:
        by_kind[f["kind"]] = by_kind.get(f["kind"], 0) + 1
        print(f'{f["path"]}:{f["line"]}  [{f["kind"]}] {f["why"]}\n'
              f'    {f["quote"]}')
    print(f"\nwrap_guard: {len(found)} 处硬折行 {by_kind}"
          f"（查了 {scanned} 份{what}，跳过 {skipped} 份）")
    print("段落内不许插换行符：一段写成一整行，段落之间用空行。"
          "跑 `wrap_guard.py --fix` 可以就地展开。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
