# fleet-style

四个文档和文风闸门，放在一个仓里，以 git submodule 的方式被消费。

[![子模块](https://img.shields.io/badge/%E5%AD%90%E6%A8%A1%E5%9D%97-%E6%A0%B7%E5%BC%8F%E5%A5%97%E4%BB%B6-orange?style=flat)](#安装)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![闸门](https://img.shields.io/badge/%E9%97%B8%E9%97%A8-4-green?style=flat)](#闸门总览)
[![语言](https://img.shields.io/badge/%E8%AF%AD%E8%A8%80-EN%20%2F%20CN-blue?style=flat)](#语言)
[![路线图](https://img.shields.io/badge/%E8%B7%AF%E7%BA%BF%E5%9B%BE-v0.3.0-purple?style=flat)](ROADMAP.md)

[English](README.md) | [中文版](README_CN.md)

---

## 设计哲学

有三条承诺撑着这套 kit。它们也决定文档检查的边界：自动检查判断结构，独立评审判断设计取舍和真实能力。

**没跑过的扫描不叫干净。** 两个工具都拒绝把「没查出问题」和「压根没查」混为一谈。git 不可用、或者当前目录根本不是一个 work tree 时，`dash_guard` 退 2，而不是枚举到零个文件然后打印 clean。找不到可测的 skill 时，`load_budget` 退 3，而不是把它报成一种状态。这里每一个 CI 步骤遇到扫描器缺失都是失败而不是跳过，因为一次不带 `--recursive` 的克隆留下的空 `style/` 目录，读起来和一个通过了的闸门一模一样。

**不可能失败的闸门不是闸门。** 每个 action 都先跑守卫自己的测试，再跑守卫；而那些测试里的每一条保证都配了负对照：一份超预算的 `SKILL.md` 必须退 1，一段重复的正文必须退 1，同一份 fixture 上把阈值翻过去，判定也必须跟着翻。这条规则来自本仓自己的历史：`load_budget` 曾经有一半什么都挡不住，却照常打印 `ok`。

**一份副本，钉住，永不 vendoring。** 这两个工具曾经被手工拷进每一个想要它们的仓，而副本会无声地漂。submodule 把那份手写的仓库清单换成了一个住在消费方仓里的指针，什么时候动这个指针由消费方自己决定。

## 它是什么（不是什么）

它是一个 git submodule，里面有四个检查器、对应测试和 composite GitHub Actions。`dash_guard` 检查公开正文的破折号，`wrap_guard` 检查段落硬折行，`load_budget` 检查常驻加载成本和重复正文，`doc_contract` 检查根文档结构、版本、日期和入口链接。

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
- uses: ./style/ci/dash-guard        # 也可选择 wrap-guard、load-budget、doc-contract
```

`ci/dash-guard` 有一个可选输入 `block-kinds`。JS、YAML、shell、PowerShell 和 cmd 的注释，以及 commit message，默认只报告发现；消费方可以用 `with: {block-kinds: 'js,yaml'}` 将指定类别设为阻断。文件读不了、无法完整解析或读取期间发生变化时，一律阻断，不受这个输入影响。

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
python style/tools/doc_contract.py --root . --profile skill --stage accepted
```

要验证你钉住的那个 commit 在这里仍然是过的，按路径显式点名这套 kit 的测试：

```bash
pytest style/tools/
```

在消费方根目录裸跑 `pytest` 不会收集到它们。`conftest.py` 把这些测试挡在消费方的计数之外，因为这个 fleet 里有好几个仓拿最低测试数当闸门，而一个被无关测试撑满的地板什么都说明不了。

## 闸门总览

| 闸门 | 它断言什么 | 退出码 |
| --- | --- | --- |
| `tools/dash_guard.py` | 公开 prose 不含 en dash、em dash、horizontal bar。Markdown 围栏与行内 code 豁免，带 `dash-guard: allow` 标记的行豁免，扫描器源文件按固定路径或标记识别。Markdown、纯文本和 Python 注释默认阻断。JS、YAML、shell、PowerShell 和 cmd 的注释，以及 commit message（`--message`），默认报告，可用 `--block-kinds` 设为阻断。扫描不完整时始终阻断。暂存模式读取 Git index，修复模式验证文件与目录身份后才写入。 | 0 干净，1 有发现或扫描不完整，2 扫描跑不起来 |
| `tools/wrap_guard.py` | 正文段落里不许有硬折行：一段写成一整行，段落之间用空行分隔。围栏、HTML 块、表格、引用、标题、徽章行、git trailer 和显式 Markdown 换行保留，带豁免标记的段落、列表项或文件按声明跳过。暂存模式从 Git index 读取文本和 `.wrap-allow`；`--added-only` 强制获取文本差异，即使 attributes 把 Markdown 标成 binary 也能检查，无法获取行范围则阻断。`--fix` 只拼接报出的段落或续行，保留其余字节及换行格式；中日韩之间直接粘、其余补一个半角空格。链接或读写期间变化的文件会被拒绝，不能与暂存模式同时使用。 | 0 干净，1 有发现或扫描不完整，2 扫描跑不起来 |
| `tools/load_budget.py` | 一个 skill 的常驻加载行数不超预算，且 `SKILL.md` 里的正文不是 reference 里正文的第二份副本。重复用 word shingle 检测，所以一条规则的措辞出现在展开它的那份 reference 里并不会触发。 | 0 在预算内，1 超预算，3 什么都没测到 |

| CI action | 接线方式 |
| --- | --- |
| `ci/dash-guard` | 装 pytest，跑 `tools/test_dash_guard.py`，然后扫调用方仓库的树。输入 `block-kinds` 把报告类升为阻断。 |
| `ci/wrap-guard` | 装 pytest，验证生成的测试数据，跑 wrap、共享文件读写和 Markdown 合同测试，然后扫调用方仓库的树。 |
| `ci/load-budget` | 装 pytest，`tools/test_load_budget.py` 不在就失败，跑它，然后测量调用方仓库。 |
| `ci/doc-contract` | 先验证合成测试，再检查调用方根文档。`profile` 默认 `skill`，`stage` 默认 `accepted`。 |

共享 Markdown 解析器只把 LF、CRLF 和 CR 当作换行；代码行中的 Unicode 分隔符不会打开或关闭围栏。Commit message 检查在 Git scissors 标记处停止，移除注释后仍按原始文件行号报告正文问题。

## 怎么跑起来的

闸门跑在 CI 上，针对调用方那个仓，别处都不跑。它们只扫当前树，从不查历史：老 commit 里的一个破折号无害，不值得为它重写一段历史，这也是这套 kit 与安全那套最尖锐的区别。

本仓用自己的 action 跑 dash、wrap 和文档检查，另外独立运行加载预算回归测试与 workflow pin 检查。本仓不声明 skill，因此只测试加载预算工具，不拿本仓当它的测量对象。

## 文档完成契约

`doc_contract.py` 的 `--profile` 接受 `skill`、`software`、`companion`，`--stage` 接受 `draft`、`accepted`、`release`。调用方 CLI 或 CI 提供阶段，仓内声明不能自行降为草稿。Skill 和软件需要双语 README、ROADMAP、CHANGELOG；伴生仓只需要根 README 或 DATA 维护入口，其他安全和类型义务由相应闸门负责。

两份 README 都要在安装前放置有实质正文的设计哲学，安装节需要命令或链接入口。检查会发现当前正文的已知模板占位、缺失的安装脚本，以及没有初始化必要 submodule 的 clone 步骤。草稿允许占位，接受和发布阶段拒绝。未来路线图的 `TODO` 与历史发布说明仍然合法。

版本取自 `.claude-plugin/plugin.json`，其次是 `package.json`，两者同时存在时必须一致；没有这两者时，ROADMAP 必须声明唯一数字版本。完整 SemVer 包括预发布与 build 后缀。README 版本和路线图徽章、当前版本字段、ROADMAP 的当前数字和最新 CHANGELOG 发布必须一致；有明确用途的 Current 节也可跟随 manifest，不重复数字。发布日期必须是有效、非未来的 ISO 日期，按日期从新到旧排列，原始版本字符串不能重复。维护分支历史与不同 build 版本可以保留。空 Unreleased 可以通过，发布阶段还要求最新数字发布有实质说明。占位检查只针对当前模板标记，普通待办描述和历史发布文字可以保留。

旧徽章里的 `0.2.2 alpha` 这类空格展示标签，数字基础版本与源版本比较，展示后缀在双语 README 间核对；真正的 SemVer 预发布和 build 后缀仍完整比较。历史条目支持逗号分隔的版本、日期和标题。软件历史可以保留只有版本、带 `validated against` 注释及 `and earlier` 汇总的格式，缺日期及相关时间顺序明确标为未验证。发布阶段仍要求有日期的发布条目。根文档锚点按平台路径身份匹配，Windows 文件名大小写差异不会绕过检查。

检查只读取限定根文档、根设计哲学文档和已知元数据，每个输入最多 1 MiB。本地链接检查路径元数据，规范化后的根文档路径还检查 anchor，其他 payload 不打开。稀疏检出中，缺失目标只有在 Git index 明确记录为 skip-worktree 的普通文件时才可通过，路径另列在 `index_metadata_paths`。普通 tracked 文件缺失、index 内的 symlink 或 submodule、reparse 路径和越出根目录的路径都会失败。文档命令不执行，错误 URL 也返回具名失败。`--json` 返回 schema 1、`ok`、具名 `checks`、`failures`、推断的 `version` 和 `unverified` 边界；通过退 0，检查失败或不完整退 1，参数无效退 2。

结构检查不能证明设计质量、双语准确性、变更记录完整、安装成功或外部效果。接受交付前，独立评审仍要根据证据核对这些内容。

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
