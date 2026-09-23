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
import re
import subprocess
import sys
from pathlib import Path

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
# 只在 commit message 那一面生效 —— 在 Markdown 里 `Note: 某某` 是一句散文，
# 不是 trailer，拿同一条规则去套会悄悄放过真正的硬折行。
_TRAILER = re.compile(r"^[A-Za-z][A-Za-z0-9-]*:\s")
_FENCE = re.compile(r"^\s*(```|~~~)")
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
# `[![alt](img)`，外层链接的开方括号被内层图片吃掉，剩下一个 `](href)` ——
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


# 一行末尾两个空格在 Markdown 里是一个**显式的 <br>**。那是意图，不是意外。
_EXPLICIT_BR = re.compile(r"\S {2,}$")

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


def _blocks(text: str) -> list[_Block]:
    """按空行切块，**围栏代码块整块跳过**。

    围栏用一个布尔切换而不是配对匹配：一份文档里有奇数个围栏是真实存在的情况（写坏了），
    这时候后半份文档整个被当成代码 —— 那是**保守**的一侧，宁可漏报也不要对着代码乱报。
    """
    out: list[_Block] = []
    buf: list[str] = []
    start = 0
    fence = False
    for i, ln in enumerate(text.splitlines(), 1):
        if _FENCE.match(ln):
            fence = not fence
            if buf:
                out.append(_Block(start, buf))
                buf = []
            continue
        if fence:
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
    lines = text.splitlines()
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
        if _LIST.match(first):
            _list_continuations(blk, found, path, kind)
            continue
        if len(blk.lines) < 2:
            continue
        if any(_EXPLICIT_BR.search(ln) for ln in blk.lines[:-1]):
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
        if _EXPLICIT_BR.search(prev):
            continue
        found.append({
            "path": path, "line": blk.start + off, "kind": "list_item",
            "lines": 2, "quote": ln.strip()[:70],
            "why": "列表项的文本跨了行。可以在**项与项之间**换行，项内不行",
        })


def fix_text(text: str) -> str:
    """把被折断的段落接回去。**只动本闸门会报的那些块**，别的一个字节不碰。"""
    if _SELF_MARKER in text:
        return text
    lines = text.splitlines()
    keep_eol = text.endswith("\n")
    out: list[str] = []
    buf: list[str] = []
    start = 0
    fence = False
    allowed: set[int] = set()
    for i, ln in enumerate(lines, 1):
        if _PARA_ALLOW in ln:
            allowed.add(i + 1)

    def flush() -> None:
        if not buf:
            return
        if start in allowed or not all(_is_prose_line(x) for x in buf):
            out.extend(_fix_list_only(buf))
        elif _LIST.match(buf[0]):
            out.extend(_fix_list_only(buf))
        elif len(buf) > 1 and not any(_EXPLICIT_BR.search(x) for x in buf[:-1]):
            joined = buf[0].rstrip()
            for nxt in buf[1:]:
                joined = join_lines(joined, nxt)
            out.append(joined)
        else:
            out.extend(buf)
        buf.clear()

    for i, ln in enumerate(lines, 1):
        if _FENCE.match(ln):
            flush()
            out.append(ln)
            fence = not fence
            continue
        if fence:
            out.append(ln)
            continue
        if not ln.strip():
            flush()
            out.append(ln)
            continue
        if not buf:
            start = i
        buf.append(ln)
    flush()
    return "\n".join(out) + ("\n" if keep_eol else "")


def _fix_list_only(buf: list[str]) -> list[str]:
    """块里混着别的东西时，只把列表项的续行接回去。"""
    out: list[str] = []
    for ln in buf:
        if (out and _LIST.match(out[-1]) and not _LIST.match(ln)
                and _is_prose_line(ln) and not _EXPLICIT_BR.search(out[-1])):
            out[-1] = join_lines(out[-1], ln)
        else:
            out.append(ln)
    return out


# --------------------------------------------------------------------------
# 目标集
# --------------------------------------------------------------------------

class GitError(RuntimeError):
    """git 跑不起来。**这不是「没东西可扫」** —— 它要退 2，不许退 0。"""


def _git(repo: Path, *args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", str(repo), *args],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
    except FileNotFoundError as exc:                             # pragma: no cover
        raise GitError("PATH 里没有 git") from exc
    if r.returncode != 0:
        raise GitError(f"git {' '.join(args)} 退 {r.returncode}: {r.stderr.strip()[:200]}")
    return r.stdout


def _tracked(repo: Path) -> list[Path]:
    out = _git(repo, "ls-files", "-z")
    return [repo / p for p in out.split("\0") if p]


def _staged(repo: Path) -> list[Path]:
    out = _git(repo, "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR")
    return [repo / p for p in out.split("\0") if p]


def _eligible(paths) -> list[Path]:
    return [p for p in paths if p.suffix.lower() in _EXT_KIND and p.is_file()]


def _added_lines(repo: Path, path: Path) -> set[int]:
    """这次提交**新增**的行号。挡存量会让每次提交重报同一批，而那种噪音正是
    把人训练成忽略钩子的东西。"""
    try:
        diff = _git(repo, "diff", "--cached", "-U0", "--", str(path))
    except GitError:
        return set()
    added: set[int] = set()
    cur = 0
    for ln in diff.splitlines():
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", ln)
        if m:
            cur = int(m.group(1))
            continue
        if ln.startswith("+") and not ln.startswith("+++"):
            added.add(cur)
            cur += 1
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

    if a.fix and a.added_only:
        print("wrap_guard: --fix 会重写整份文件，和 --added-only 放在一起等于"
              "把 --added-only 想跳过的存量也一并改了。两者不许同时给。",
              file=sys.stderr)
        return 2

    # --- commit message：它自成一个目标集，不经过 git 文件列表 ---
    if a.message:
        p = Path(a.message)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"wrap_guard: 读不了 {p}：{exc}", file=sys.stderr)
            return 2
        body = _message_body(text)
        found = check_text(body["text"], path=str(p), kind="message")
        for f in found:
            f["line"] += body["offset"]
        return _report(found, scanned=1, skipped=0, what="commit message")

    repo = Path(a.repo).resolve()
    try:
        if a.paths:
            targets = _eligible(Path(x) for x in a.paths)
        elif a.staged:
            targets = _eligible(_staged(repo))
        else:
            targets = _eligible(_tracked(repo))
    except GitError as exc:
        # **「扫不动」和「扫干净了」必须是两个输出。**
        print(f"wrap_guard: 没能跑起来 —— {exc}", file=sys.stderr)
        return 2

    found: list[dict] = []
    skipped = 0
    fixed = 0
    unreadable = 0
    for p in targets:
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            unreadable += 1
            continue
        if _SELF_MARKER in text:
            skipped += 1
            continue
        if a.fix:
            new = fix_text(text)
            if new != text:
                p.write_text(new, encoding="utf-8")
                fixed += 1
            continue
        rows = check_text(text, path=p.as_posix())
        if a.added_only and a.staged:
            keep = _added_lines(repo, p)
            rows = [r for r in rows if r["line"] in keep]
        found.extend(rows)

    if a.fix:
        print(f"wrap_guard --fix：展开了 {fixed} 份文件"
              f"（跳过 {skipped} 份带豁免标记的，{unreadable} 份读不了）")
        # **--fix 不是闸门。** 它修好之后退 0；只有读不了的文件才退 1。
        return 1 if unreadable else 0
    return _report(found, scanned=len(targets), skipped=skipped, what="文件")


def _message_body(text: str) -> dict:
    """commit message 去掉标题行和注释行之后的正文，以及它在原文里的行偏移。

    标题行本来就该是一行，不参与段落规则；`#` 开头的是 git 自己加的说明。
    """
    lines = text.splitlines()
    keep: list[str] = []
    offset = 0
    started = False
    for i, ln in enumerate(lines):
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
    return {"text": "\n".join(keep), "offset": offset}


def _report(found: list[dict], *, scanned: int, skipped: int, what: str) -> int:
    if not found:
        # **把扫过多少、跳过多少打出来。** 一个被跳过的文件和一个干净的文件
        # 不许长得一样 —— 那正是「被喂了空的检查器」那个形状。
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
