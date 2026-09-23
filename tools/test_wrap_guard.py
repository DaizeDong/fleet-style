#!/usr/bin/env python3
# wrap-guard:allow-file -- 本文件按设计带着被折断的示例
"""`wrap_guard` 自己必须**有可能变红**。

## 这份测试为什么写成这样

同一个家族的上一个闸门（`dash_guard`）第一版里，正则中混进了一个字面 backspace 字节，于是它**静默地永不匹配** —— 打印出来的绿，和一个真的扫过一遍什么都没找到的绿，一模一样。机主为此专门立了一条：写这类闸门时必须反向验证它会失败。

所以下面每一条正向断言旁边都配一条反向的：报得出来 **且** 不该报的时候不报。只有前者，闸门可能是恒真；只有后者，闸门可能是恒假。

## 还有一条这个家族特有的

`--fix` 是**改写**，不是检查。它修好之后退 0，所以把它接进 CI 等于装了一个不可能失败的检查。下面有一条断言钉着这个区别，另有一条钉幂等：连跑两遍的产物必须逐字节相等，否则「修好了」这句话就不成立。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wrap_guard as W                                            # noqa: E402

TOOL = Path(__file__).resolve().parent / "wrap_guard.py"


def _kinds(rows):
    return sorted(r["kind"] for r in rows)


# --------------------------------------------------------------------------
# 一 · 报得出来
# --------------------------------------------------------------------------

def test_a_wrapped_paragraph_is_found():
    text = "这是一个被折断的段落的前半句，\n而这是它的后半句。\n"
    rows = W.check_text(text)
    assert _kinds(rows) == ["paragraph"]
    assert rows[0]["line"] == 1 and rows[0]["lines"] == 2


def test_a_wrapped_list_item_is_found():
    text = "- 这是一个列表项，它的文本\n  被折到了第二行。\n- 这是另一个列表项。\n"
    rows = W.check_text(text)
    assert _kinds(rows) == ["list_item"], rows
    assert rows[0]["line"] == 2


def test_a_long_paragraph_of_many_lines_reports_its_size():
    text = "一\n二\n三\n四\n"
    rows = W.check_text(text)
    assert rows[0]["lines"] == 4


def test_the_guard_finds_something_in_real_corpus():
    """**先证明它对着真语料有东西可查。** 一个被喂了空的检查器，
    打印的绿跟真没查出问题的绿一模一样。"""
    corpus = Path(__file__).resolve().parents[1] / "README_CN.md"
    if not corpus.exists():                                      # pragma: no cover
        pytest.skip("母仓里没有那份语料")
    text = corpus.read_text(encoding="utf-8")
    assert text.strip(), "语料是空的，这条什么都没查"
    W.check_text(text, path=corpus.name)       # 不断言有无，只断言跑得动且有输入


# --------------------------------------------------------------------------
# 二 · 不该报的时候不报（另一半投毒）
# --------------------------------------------------------------------------

def test_a_single_line_paragraph_is_clean():
    assert W.check_text("这是一整段写成一行的正文。\n\n这是第二段。\n") == []


def test_separate_list_items_are_clean():
    """**「列表项之间」本来就该换行。** 把它也报出来，这个闸门会在每一份
    文档上全红，然后被绕过 —— 一个动不动就叫的闸门等于没有闸门。"""
    assert W.check_text("- 第一项。\n- 第二项。\n- 第三项。\n") == []


def test_a_fenced_code_block_is_not_prose():
    text = "```python\nx = 1\ny = 2\n```\n"
    assert W.check_text(text) == []


def test_an_indented_code_block_is_not_prose():
    assert W.check_text("    第一行代码\n    第二行代码\n") == []


def test_a_table_is_not_prose():
    text = "| 列 | 值 |\n|---|---|\n| a | 1 |\n| b | 2 |\n"
    assert W.check_text(text) == []


def test_a_blockquote_and_a_heading_are_not_prose():
    assert W.check_text("> 引用第一行\n> 引用第二行\n") == []
    assert W.check_text("# 标题\n## 另一个标题\n") == []


def test_two_trailing_spaces_are_an_explicit_line_break():
    """Markdown 里行尾两个空格是一个**显式的 `<br>`**。那是意图，不是意外。"""
    assert W.check_text("第一行  \n第二行\n") == []


def test_a_row_of_badges_is_not_a_paragraph():
    r"""徽章行、语言切换行是**一串记号，不是句子**。

    ⚠ 这里的坑在嵌套：徽章是 `[![alt](img)](href)`，用一条带 `!?` 的正则去剥，
    `[^\]]*` 会在 `![alt]` 的那个 `]` 处停住，匹配到 `[![alt](img)`，
    外层链接的开方括号被内层图片吃掉，剩一个 `](href)` 再也剥不动。
    实测第一版就是这样，徽章照样被拼成一整行。所以图片和链接要分两步、按顺序剥。
    """
    badges = ("[![A](https://example.com/a.svg)](#x)\n"
              "[![B](https://example.com/b.svg)](#y)\n")
    assert W.check_text(badges) == []
    assert W.check_text("[English](README.md) | [中文版](README_CN.md)\n"
                        "[Docs](d.md)\n") == []


def test_a_sentence_containing_a_link_is_still_prose():
    """**另一半**：句子里有链接不等于这一行是链接。

    判据是「剥光之后还有没有文字」，不是「有没有出现过链接」——
    后者会把大半份文档判成非散文，然后这个闸门就什么都不管了。
    """
    rows = W.check_text("见 [文档](a.md) 里的前半句，\n还有后半句。\n")
    assert rows and rows[0]["kind"] == "paragraph"


def test_a_label_line_followed_by_a_list_is_not_a_paragraph():
    """**一行标签后面紧跟一串列表项，中间不留空行，是标准写法。**

    2026-09-23 实测：记忆池里的 `**Why:**` 加三条 `- …` 被整块判成了一个
    「占了 4 行的散文段」。只看块的第一行不够 —— 块里任何一行是列表项，
    段落规则对这一块就不成立。
    """
    text = "**Why:**\n- 第一条理由。\n- 第二条理由。\n"
    assert W.check_text(text) == []
    assert W.fix_text(text) == text


def test_a_list_item_inside_such_a_block_is_still_checked():
    """**另一半**：跳过段落规则不等于整块放行，项内续行照报。"""
    text = "**Why:**\n- 这一条的文本\n  折到了第二行。\n"
    rows = W.check_text(text)
    assert [r["kind"] for r in rows] == ["list_item"], rows


def test_a_file_carrying_the_self_marker_is_skipped_whole():
    text = f"# {W._SELF_MARKER}\n被折断的\n段落\n"
    assert W.check_text(text) == []


def test_a_paragraph_can_be_exempted_inline():
    text = f"<!-- {W._PARA_ALLOW} -->\n被折断的\n段落\n"
    assert W.check_text(text) == []


def test_the_exemption_is_not_a_blanket():
    """**另一半**：豁免标记只管紧跟它的那一段，不许顺手放过整份文件。"""
    text = f"<!-- {W._PARA_ALLOW} -->\n放过的\n这一段\n\n没放过的\n这一段\n"
    rows = W.check_text(text)
    assert len(rows) == 1, rows


# --------------------------------------------------------------------------
# 二 b · 仓库自己声明的范围
# --------------------------------------------------------------------------

def test_a_repo_can_declare_paths_this_rule_does_not_govern(tmp_path):
    """**归档件里的旧形态就该原样留着。**

    2026-09-23 由一次真实的越界逼出来：在一个仓里跑 `--tree`，它扫到 153 份
    文件、改写了 123 份，大半是 `archive/` 和几百份调研笔记。那个仓的另一条
    闸门早就把 archive 排除在外了，这一条却不知道 —— 因为**没有任何办法
    让仓库把它知道的事告诉工具**。
    """
    (tmp_path / ".wrap-allow").write_text(
        "# 注释行会被跳过\narchive/   # 归档件是历史证据，旧形态就该留着\n",
        encoding="utf-8")
    got = W.read_ignore(tmp_path)
    assert got == [("archive/", "归档件是历史证据，旧形态就该留着")]


def test_an_exemption_without_a_reason_is_refused(tmp_path):
    """**一张只有路径、没有理由的豁免表，三个月后没人敢删任何一行。**"""
    (tmp_path / ".wrap-allow").write_text("archive/\n", encoding="utf-8")
    with pytest.raises(ValueError) as e:
        W.read_ignore(tmp_path)
    assert "理由" in str(e.value)


def test_no_declaration_file_means_no_exemptions(tmp_path):
    """**另一半**：没有那份文件不等于「全都豁免」。"""
    assert W.read_ignore(tmp_path) == []


def test_explicitly_named_paths_bypass_the_exemption_table(tmp_path):
    """点名就是意图。豁免表是给 `--tree` 的，不是给「我就要查这一份」的。"""
    (tmp_path / ".wrap-allow").write_text("a.md  # 理由\n", encoding="utf-8")
    f = tmp_path / "a.md"
    f.write_text("前半句，\n后半句。\n", encoding="utf-8")
    assert W.main([str(f)]) == 1, "显式点名的文件被豁免表挡掉了"


# --------------------------------------------------------------------------
# 三 · 接回去的那条规则
# --------------------------------------------------------------------------

def test_chinese_lines_join_without_a_space():
    """中文之间插空格会在渲染后留下**可见的缝**。这一条是量出来的，不是审美。"""
    assert W.join_lines("前半句，", "后半句。") == "前半句，后半句。"


def test_latin_lines_join_with_one_space():
    assert W.join_lines("the quick", "brown fox") == "the quick brown fox"


def test_a_mixed_boundary_gets_a_space():
    """一侧是中文一侧是拉丁，补空格 —— 那正是中英混排该有的样子。"""
    assert W.join_lines("这一段讲的是", "Playwright") == "这一段讲的是 Playwright"


def test_fix_makes_the_check_clean():
    text = "这是被折断的前半句，\n而这是后半句。\n\n- 列表项的文本\n  折到了第二行。\n"
    fixed = W.fix_text(text)
    assert W.check_text(fixed) == [], fixed
    assert "这是被折断的前半句，而这是后半句。" in fixed


def test_fix_is_idempotent():
    """**连跑两遍，逐字节相等。** 一个每跑一次就变一点的修复器，
    会让「修好了」这句话永远没有终点。"""
    text = "前半句，\n后半句。\n\n- 项的文本\n  续行。\n\n| a | b |\n|---|---|\n"
    once = W.fix_text(text)
    assert W.fix_text(once) == once


def test_fix_does_not_touch_code_or_tables():
    text = "```\na\nb\n```\n\n| x |\n| y |\n"
    assert W.fix_text(text) == text


def test_fix_keeps_the_trailing_newline_decision():
    assert W.fix_text("一\n二\n").endswith("\n")
    assert not W.fix_text("一\n二").endswith("\n")


# --------------------------------------------------------------------------
# 四 · commit message 那一面
# --------------------------------------------------------------------------

def test_the_subject_line_is_not_a_paragraph(tmp_path):
    """标题行本来就是一行，它不参与段落规则。"""
    p = tmp_path / "MSG"
    p.write_text("这是标题行\n\n这是一整段正文写成一行。\n", encoding="utf-8")
    assert W.main(["--message", str(p)]) == 0


def test_a_wrapped_commit_body_is_caught(tmp_path):
    p = tmp_path / "MSG"
    p.write_text("标题\n\n正文的前半句，\n正文的后半句。\n", encoding="utf-8")
    assert W.main(["--message", str(p)]) == 1


def test_git_comment_lines_in_a_message_are_ignored(tmp_path):
    p = tmp_path / "MSG"
    p.write_text("标题\n\n一整段正文。\n\n# 请输入提交信息\n# 以 '#' 开头的行将被忽略\n",
                 encoding="utf-8")
    assert W.main(["--message", str(p)]) == 0


def test_git_trailers_are_not_a_wrapped_paragraph(tmp_path):
    """**git trailer 按格式必须各占一行。**

    不放过它们，这个钩子会挡下每一条带署名的提交 —— 而一个挡下一切的钩子
    会在第一天就被 `--no-verify` 绕过，等于从来没装。
    """
    p = tmp_path / "MSG"
    p.write_text("标题\n\n一整段正文。\n\n"
                 "Co-Authored-By: Someone <user1@example.com>\n"
                 "Claude-Session: https://example.com/s/1\n", encoding="utf-8")
    assert W.main(["--message", str(p)]) == 0


def test_a_trailer_looking_line_in_markdown_is_still_prose():
    """**另一半**：只有 commit message 那一面认 trailer。

    Markdown 里 `Note: 某某` 是一句散文，拿同一条规则去套，会把真正的
    硬折行悄悄放过。
    """
    text = "Note: 这是前半句，\n这是后半句。\n"
    assert W.check_text(text, kind="md"), "Markdown 里也把它当 trailer 放过了"
    assert W.check_text(text, kind="message") == []


def test_an_unreadable_message_file_exits_two(tmp_path):
    """**读不了不许退 0。** 一次「没检查」和一次「检查过了是干净的」
    必须是两个输出。"""
    assert W.main(["--message", str(tmp_path / "does-not-exist")]) == 2


# --------------------------------------------------------------------------
# 五 · 扫不动要退 2，不许退 0
# --------------------------------------------------------------------------

def test_a_non_repo_directory_cannot_be_reported_as_clean(tmp_path):
    rc = W.main(["--repo", str(tmp_path)])
    assert rc == 2, "在一个不是 git 工作树的目录里，它报了「干净」"


def test_fix_and_added_only_are_refused_together():
    """`--fix` 重写整份文件，和 `--added-only` 放一起等于把存量也一并改了。"""
    assert W.main(["--fix", "--added-only"]) == 2


# --------------------------------------------------------------------------
# 六 · 命令行本体真的跑得起来
# --------------------------------------------------------------------------

def _run(args, cwd=None):
    return subprocess.run([sys.executable, str(TOOL), *args], cwd=cwd,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def test_the_cli_exits_one_on_a_wrapped_file(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("前半句，\n后半句。\n", encoding="utf-8")
    r = _run([str(f)])
    assert r.returncode == 1, r.stdout + r.stderr
    assert "paragraph" in r.stdout


def test_the_cli_exits_zero_on_a_clean_file_and_says_what_it_scanned(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("一整段写成一行。\n", encoding="utf-8")
    r = _run([str(f)])
    assert r.returncode == 0, r.stdout + r.stderr
    # **「跳过了」和「干净」不许长得一样**，所以干净那一行也要报出扫了几份。
    assert "查了 1 份" in r.stdout


def test_the_cli_fix_repairs_and_then_the_check_is_clean(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("前半句，\n后半句。\n", encoding="utf-8")
    assert _run(["--fix", str(f)]).returncode == 0
    assert f.read_text(encoding="utf-8") == "前半句，后半句。\n"
    assert _run([str(f)]).returncode == 0


def test_fix_is_not_a_gate():
    """**`--fix` 修好之后退 0。** 把它接进 CI，就是装了一个不可能失败的检查。
    这一条把那个事实钉在测试里，免得有人在 workflow 里写成 `--fix`。"""
    import inspect

    src = inspect.getsource(W.main)
    assert "--fix 不是闸门" in src
