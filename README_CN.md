# fleet-style

三个与安全无关的房规闸门，放在一个仓里，以 git submodule 的方式被消费。

[![子模块](https://img.shields.io/badge/%E5%AD%90%E6%A8%A1%E5%9D%97-%E6%A0%B7%E5%BC%8F%E5%A5%97%E4%BB%B6-orange?style=flat)](#安装)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![闸门](https://img.shields.io/badge/%E9%97%B8%E9%97%A8-2-green?style=flat)](#闸门总览)
[![语言](https://img.shields.io/badge/%E8%AF%AD%E8%A8%80-EN%20%2F%20CN-blue?style=flat)](#语言)
[![路线图](https://img.shields.io/badge/%E8%B7%AF%E7%BA%BF%E5%9B%BE-v0.3.0-purple?style=flat)](ROADMAP.md)

[English](README.md) | [中文版](README_CN.md)

---

## ⭐ 先读这里, 设计理念

有三条承诺撑着这套 kit，它们比里面那三条规则本身更值得先看。

**没跑过的扫描不叫干净。** 两个工具都拒绝把「没查出问题」和「压根没查」混为一谈。git 不可用、或者当前目录根本不是一个 work tree 时，`dash_guard` 退 2，而不是枚举到零个文件然后打印 clean。找不到可测的 skill 时，`load_budget` 退 3，而不是把它报成一种状态。这里每一个 CI 步骤遇到扫描器缺失都是失败而不是跳过，因为一次不带 `--recursive` 的克隆留下的空 `style/` 目录，读起来和一个通过了的闸门一模一样。

**不可能失败的闸门不是闸门。** 每个 action 都先跑守卫自己的测试，再跑守卫；而那些测试里的每一条保证都配了负对照：一份超预算的 `SKILL.md` 必须退 1，一段重复的正文必须退 1，同一份 fixture 上把阈值翻过去，判定也必须跟着翻。这条规则来自本仓自己的历史：`load_budget` 曾经有一半什么都挡不住，却照常打印 `ok`。

**一份副本，钉住，永不 vendoring。** 这两个工具曾经被手工拷进每一个想要它们的仓，而副本会无声地漂。submodule 把那份手写的仓库清单换成了一个住在消费方仓里的指针，什么时候动这个指针由消费方自己决定。

## 它是什么（不是什么）

它是一个 git submodule，里面装着两个扫描器、它们的测试，以及两个 composite GitHub Action。 `dash_guard` 执行那条房规：公开的 prose 不带 en dash、em dash 和 horizontal bar，同时不碰 ASCII 连字符，因为那是代码语法。`load_budget` 量的是一份 `SKILL.md` 在每次调用时要付的成本，以及其中有多少正文是从按需加载的 reference 里复制过来的。

它**不是** Claude Code 的 skill 或 plugin，也不带 `SKILL.md`：它是一个你加进仓里、再从 CI 调用的 submodule。它**不是**那套安全 kit。`fleet-guards` 的存在是为了让真实标识符不进公开历史，而这里没有任何东西干这件事；这两个闸门抓的是一条文风规则和一条架构规则。它也**不接** `core.hooksPath`，因为那个设置只能指向一个目录，而那个目录属于站在标识符与公开 push 之间的那套闸门。

把两套 kit 分开，也就把它们的答案分开了。每一个公开仓都需要安全闸门。而一个没有 `SKILL.md` 的仓，加载预算根本没东西可测，并且每跑一次就说一次。

## 安装

```bash
git submodule add -b main https://github.com/DaizeDong/fleet-style.git style
```

然后在每个想要闸门的 workflow 里：

```yaml
- uses: actions/checkout@v4
  with: {submodules: true}
- uses: actions/setup-python@v5
  with: {python-version: '3.x'}
- uses: ./style/ci/dash-guard        # 或者 ./style/ci/load-budget
```

`ci/dash-guard` 有一个可选输入 `block-kinds`。v0.3.0 新增的几类（JS、YAML、shell、PowerShell 和 cmd 的注释，commit message，以及读不了的文件）只报告、不失败，直到消费方在这里点名，比如 `with: {block-kinds: 'js,yaml'}`。留空时判决与 v0.3.0 之前完全一致。

移动指针：

```bash
git -C style fetch && git -C style checkout <sha>
```

然后提交新指针。一个 submodule 钉住一个 commit。消费方也可以启用 [自动同步](docs/AUTOMATIC_SYNC.md)：源仓 workflow 通过之后，一个 dispatch 事件会让指针经由消费方自己的提交闸门前进。

## 快速开始

直接对消费它的那个仓跑任一工具：

```bash
python style/tools/dash_guard.py --tree      # 所有被跟踪的文本文件
python style/tools/dash_guard.py --staged    # 只看 staged 的 blob
python style/tools/dash_guard.py --fix FILE  # 确定性修复，不是闸门
python style/tools/dash_guard.py --message .git/COMMIT_EDITMSG   # 查一条 commit message
python style/tools/dash_guard.py --tree --block-kinds js,yaml    # 把报告类升为阻断
python style/tools/load_budget.py .          # 常驻加载预算
```

要验证你钉住的那个 commit 在这里仍然是过的，按路径显式点名这套 kit 的测试：

```bash
pytest style/tools/
```

在消费方根目录裸跑 `pytest` 不会收集到它们。`conftest.py` 把这些测试挡在消费方的计数之外，因为这个 fleet 里有好几个仓拿最低测试数当闸门，而一个被无关测试撑满的地板什么都说明不了。

## 闸门总览

| 闸门 | 它断言什么 | 退出码 |
| --- | --- | --- |
| `tools/dash_guard.py` | 公开 prose 不含 en dash、em dash、horizontal bar。Markdown 围栏与行内 code 豁免，带 `dash-guard: allow` 标记的行豁免，扫描器自己的源文件按文件名豁免，因为它把那组破折号当数据装在身上。Markdown、纯文本和 Python 注释是阻断类。JS 的 `//` 与 `/* */` 注释、YAML 的 `#` 注释、shell、PowerShell 和 cmd 注释、commit message（`--message`）以及读不了的文件是报告类：带着类别打印出来，计入判决行，只有在 `--block-kinds` 里点名才阻断。所有字符串、模板和正则字面量都是代码，从不检查。 | 0 干净，1 有阻断类发现，2 扫描跑不起来 |
| `tools/wrap_guard.py` | 正文段落里不许有硬折行：一段写成一整行，段落之间用空行分隔。只有段落之间、列表项之间、代码块内和表格内才该换行。围栏、表格、引用、标题、徽章行和 git trailer 豁免，前面一行写了 `wrap-guard:allow` 的那一段豁免，扫描器自己的源文件按文件名豁免（它身上带着被折断的示例）。`--fix` 把行接回去，中日韩之间直接粘、其余补一个半角空格。 | 0 干净，1 有发现，2 扫描跑不起来 |
| `tools/load_budget.py` | 一个 skill 的常驻加载行数不超预算，且 `SKILL.md` 里的正文不是 reference 里正文的第二份副本。重复用 word shingle 检测，所以一条规则的措辞出现在展开它的那份 reference 里并不会触发。 | 0 在预算内，1 超预算，3 什么都没测到 |

| CI action | 接线方式 |
| --- | --- |
| `ci/dash-guard` | 装 pytest，跑 `tools/test_dash_guard.py`，然后扫调用方仓库的树。输入 `block-kinds` 把报告类升为阻断。 |
| `ci/wrap-guard` | 装 pytest，跑 `tools/test_wrap_guard.py`，然后扫调用方仓库的树。 |
| `ci/load-budget` | 装 pytest，`tools/test_load_budget.py` 不在就失败，跑它，然后测量调用方仓库。 |

## 怎么跑起来的

闸门跑在 CI 上，针对调用方那个仓，别处都不跑。它们只扫当前树，从不查历史：老 commit 里的一个破折号无害，不值得为它重写一段历史，这也是这套 kit 与安全那套最尖锐的区别。

本仓用自己的 action 跑自己的闸门。`.github/workflows/style.yml` 调用 `./ci/dash-guard`，所以一处损坏会先在这里暴露，再轮到消费方。里面没有 load budget 这个 job，因为本仓不声明任何 skill，那个工具每次提交都会退 3。

## 输出示例

```
$ python tools/dash_guard.py --tree
dash_guard: 2 file(s) deliberately excluded:
  tools/dash_guard.py                    the guard's own source (contains the dash set by design)
  tools/test_dash_guard.py               the guard's own source (contains the dash set by design)
dash_guard: clean (16 file(s) examined, 2 skipped)
```

```
$ python tools/load_budget.py .
load_budget: FAIL, measured NOTHING under /path/to/fleet-style
  looked for: skills/*/SKILL.md and SKILL.md at the root
  This repo declares no skill (no .claude-plugin/plugin.json, no skills/, no root
  SKILL.md), so load_budget has nothing here to guard. Drop tools/load_budget.py
  from it rather than letting an inert gate report a result.
```

第二条正是设计在起作用。一个没东西可测的仓会被告知别再背着这个闸门，而不是收下一个毫无含义的绿勾。

## 局限

两个闸门都不保护历史。它们读的是此刻的树，所以已经躺在老 commit 里的违规就留在那儿。这里也不接钩子，所以只在 CI 里跑它们的消费方，是在 push 之后而不是之前知道违规的。`dash_guard --fix` 就地重写文件，并且刻意不能当闸门用：它修复成功后退 0，把它接进 CI 等于装了一个不可能失败的检查。v0.3.0 新增的注释类没有修复器，在消费方升级之前只报告。它们的词法器是手写的小东西，不是解析器；YAML 标量（包括 `description:` 这种写成正文的）暂不检查，块标量里的 `#` 行也算正文不算注释，只有 `run:` 块例外，那里的 `#` 行会被计入，因为那是 shell 注释。JS 词法器还没在 `.jsx` 或 `.tsx` 文件上量过召回率，因为目前没有消费方带这类文件；`js` 要改成阻断之前必须先量。而 `load_budget` 只认两种仓库形态，`skills/*/SKILL.md` 和根目录下的 `SKILL.md`，别的形态一律报成什么都没测到。

## 语言

English (`README.md`) · 中文 (`README_CN.md`)

## 路线图 · 贡献 · 许可

见 [ROADMAP.md](ROADMAP.md) · [CHANGELOG.md](CHANGELOG.md)。

与房规仓库规范的每一处偏离及其理由，记录在 [docs/2026-09-22-spec-adaptation.md](docs/2026-09-22-spec-adaptation.md)。
