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

检查通过必须来自实际完成的扫描，并有能够失败的负对照。缺少输入、Git 不可用或扫描器不存在时，应报告失败。共享工具只维护一份实现，消费仓固定接受的提交。自动检查负责有限的结构问题，独立评审负责含义、设计取舍和行为证据。

`dash_guard` 在 Git 不可用或当前目录不是工作树时退 2；`load_budget` 找不到可测的 skill 时退 3。CI action 先运行自己的测试，再检查消费仓。超预算和重复正文等合成负对照必须能使对应检查失败。

## 它是什么（不是什么）

它是一个 git submodule，里面有四个检查器、对应测试和 composite GitHub Actions。`dash_guard` 检查公开正文的破折号，`wrap_guard` 检查段落硬折行，`load_budget` 检查常驻加载成本和重复正文，`doc_contract` 检查根文档结构、版本、日期和入口链接。

本仓通过 CI 调用，不提供 Claude Code skill/plugin 或 `SKILL.md`。安全检查和文档检查适用范围不同：公开仓需要发布守卫，没有 `SKILL.md` 的仓则没有 skill 加载预算可测。独立套件让消费仓分别选择适用检查并固定版本。最初拆出的 `dash_guard` 与 `load_budget` 占当时安全套件的 17.5%。

本套件不配置 `core.hooksPath`；该设置只能指向一个目录，应由发布守卫使用。

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

```bash
python style/tools/doc_contract.py --root . --profile skill --stage accepted
```

调用方通过 `--profile` 选择 `skill`、`software`、`companion` 或显式的 `combined`，通过 `--stage` 选择 `draft`、`accepted` 或 `release`。仓内内容不能自行选择 draft。action 默认采用 `skill` 和 `accepted`，先执行回归控制。

skill 和 software 需要双语 README、ROADMAP、CHANGELOG，设计依据位于安装之前，当前版本保持一致。companion 需要维护 README 或 DATA 入口。PRIVATE combined profile 使用专门的维护变更记录，不打开根目录的策展 DATA。各 profile 的职责、版本和日期规则、链接检查、JSON 输出及读取边界统一见[文档检查契约](docs/DOCUMENTATION_CONTRACT.md)；combined 的具体要求见[维护文档契约](docs/COMBINED_DOCUMENTATION.md)。

结构检查不能证明设计质量、双语准确性、变更记录完整、安装成功或外部效果。独立评审仍需核对相应证据。扫描器解析、暂存读取、修复和重复检测的细节见[扫描器参考](docs/SCANNERS.md)。

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

第二条报告没有可测的 skill，退出码为 3，不能用作加载预算通过的证据。

## 局限

这些检查不扫描完整 Git 历史。它们读的是此刻的树，所以已经躺在老 commit 里的违规就留在那儿。这里也不接钩子，所以只在 CI 里跑它们的消费方，是在 push 之后而不是之前知道违规的。`dash_guard --fix` 就地重写文件，并且刻意不能当闸门用：它修复成功后退 0，把它接进 CI 等于装了一个不可能失败的检查。v0.3.0 新增的注释类没有修复器，在消费方升级之前只报告。它们的词法器是手写的小东西，不是解析器；YAML 标量（包括 `description:` 这种写成正文的）暂不检查，块标量里的 `#` 行也算正文不算注释，只有 `run:` 块例外，那里的 `#` 行会被计入，因为那是 shell 注释。JS 词法器还没在 `.jsx` 或 `.tsx` 文件上量过召回率，因为目前没有消费方带这类文件；`js` 要改成阻断之前必须先量。而 `load_budget` 只认两种仓库形态，`skills/*/SKILL.md` 和根目录下的 `SKILL.md`，别的形态一律报成什么都没测到。

## 语言

English (`README.md`) · 中文 (`README_CN.md`)

## 路线图 · 贡献 · 许可

见 [ROADMAP.md](ROADMAP.md) · [CHANGELOG.md](CHANGELOG.md)。

与房规仓库规范的每一处偏离及其理由，记录在 [docs/2026-09-22-spec-adaptation.md](docs/2026-09-22-spec-adaptation.md)。
