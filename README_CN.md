# fleet-style

三个文档和文风脚本，放在一个仓里，每台机器只放一份本地 checkout。

[![样式套件](https://img.shields.io/badge/%E6%A0%B7%E5%BC%8F%E5%A5%97%E4%BB%B6-%E6%9C%AC%E5%9C%B0%20checkout-orange?style=flat)](#安装)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![闸门](https://img.shields.io/badge/%E9%97%B8%E9%97%A8-3-green?style=flat)](#闸门总览)
[![语言](https://img.shields.io/badge/%E8%AF%AD%E8%A8%80-EN%20%2F%20CN-blue?style=flat)](#语言)
[![路线图](https://img.shields.io/badge/%E8%B7%AF%E7%BA%BF%E5%9B%BE-v0.3.0-purple?style=flat)](ROADMAP.md)

[English](README.md) | [中文版](README_CN.md)

---

## 设计哲学

检查通过必须来自实际完成的扫描。缺少输入、Git 不可用或扫描器不存在时，应报告失败。共享工具只维护一份实现，放在一份 checkout 里。自动检查负责有限的结构问题，独立评审负责含义、设计取舍和行为证据。

`dash_guard` 在 Git 不可用或当前目录不是工作树时退 2；`load_budget` 找不到可测的 skill 时退 3。

## 它是什么（不是什么）

它是三个检查脚本：`dash_guard` 检查公开正文的破折号，`load_budget` 检查常驻加载成本和重复正文，`doc_contract` 检查根文档结构、版本、日期和入口链接。

本仓不提供 Claude Code skill/plugin 或 `SKILL.md`。安全检查和文档检查适用范围不同：公开仓需要发布守卫，没有 `SKILL.md` 的仓则没有 skill 加载预算可测。两个套件分开，消费仓各取适用的检查。

## 安装

每台机器一次：

```bash
git clone https://github.com/DaizeDong/fleet-style.git <path>
git config --global fleet.style <path>        # 用正斜杠，例如 C:/src/fleet-style
```

这份 checkout 始终停在 `main`，改动在它的 `git worktree` 里做。

只有 `dash_guard` 自动运行，由消费仓的 `.githooks/pre-commit` 转发脚本调用（就是 fleet-guards 的那份转发脚本，在最后的 `exec` 之前加上这一段）：

```sh
S=$(git config --get fleet.style)
if [ -z "$S" ] || [ ! -s "$S/tools/dash_guard.py" ]; then
  echo "BLOCKED: git config fleet.style is unset or has no tools/dash_guard.py; nothing was checked." >&2
  exit 1
fi
python "$S/tools/dash_guard.py" --check --staged --added-only </dev/null || exit 1
```

配置项没设，或者 checkout 里没有这个脚本，一律拦下；没有任何备用位置。`load_budget` 和 `doc_contract` 是按需手动跑的脚本，不接任何钩子。

## 快速开始

在本仓根目录跑（从消费仓跑时把 `tools/` 换成 `"$(git config --get fleet.style)/tools/"`）：

```bash
python tools/dash_guard.py --tree      # 所有被跟踪的文本文件
python tools/dash_guard.py --staged    # 只看 staged 的 blob
python tools/dash_guard.py --fix FILE  # 确定性修复，不是闸门
python tools/dash_guard.py --message .git/COMMIT_EDITMSG   # 查一条 commit message
python tools/load_budget.py .          # 常驻加载预算
python tools/doc_contract.py --root . --profile software --stage accepted
```

## 闸门总览

| 闸门 | 它断言什么 | 退出码 |
| --- | --- | --- |
| `tools/dash_guard.py` | 公开 prose 不含 en dash、em dash、horizontal bar。Markdown 围栏与行内 code 豁免，带 `dash-guard: allow` 标记的行豁免，扫描器源文件按固定路径或标记识别。Markdown、纯文本、Python 注释和 commit message（`--message`）里的发现都阻断。扫描不完整时始终阻断。暂存模式读取 Git index，修复模式验证文件与目录身份后才写入。 | 0 干净，1 有发现或扫描不完整，2 扫描跑不起来 |
| `tools/load_budget.py` | 一个 skill 的常驻加载行数不超预算，且 `SKILL.md` 里的正文不是 reference 里正文的第二份副本。重复用 word shingle 检测，所以一条规则的措辞出现在展开它的那份 reference 里并不会触发。 | 0 在预算内，1 超预算，3 什么都没测到 |
| `tools/doc_contract.py` | 根文档结构、版本、日期和入口链接。 | 0 通过，非零为失败 |

共享 Markdown 解析器只把 LF、CRLF 和 CR 当作换行；代码行中的 Unicode 分隔符不会打开或关闭围栏。Commit message 检查在 Git scissors 标记处停止，移除注释后仍按原始文件行号报告正文问题。

## 怎么跑起来的

`dash_guard` 在提交时跑，只看这次暂存内容新增的行，从不查历史：老 commit 里的一个破折号无害，不值得为它重写一段历史，这也是这套 kit 与安全那套最尖锐的区别。本仓自己的 `.githooks/pre-commit` 也这样检查本仓，`core.hooksPath=.githooks`。

## 文档完成契约

```bash
python tools/doc_contract.py --root . --profile skill --stage accepted
```

调用方通过 `--profile` 选择 `skill`、`software`、`companion` 或显式的 `combined`，通过 `--stage` 选择 `draft`、`accepted` 或 `release`。仓内内容不能自行选择 draft。

skill 和 software 需要双语 README、ROADMAP、CHANGELOG，设计依据位于安装之前，当前版本保持一致。companion 需要维护 README 或 DATA 入口。PRIVATE combined profile 使用专门的维护变更记录，不打开根目录的策展 DATA。各 profile 的职责、版本和日期规则、链接检查、JSON 输出及读取边界统一见[文档检查契约](docs/DOCUMENTATION_CONTRACT.md)；combined 的具体要求见[维护文档契约](docs/COMBINED_DOCUMENTATION.md)。

结构检查不能证明设计质量、双语准确性、变更记录完整、安装成功或外部效果。独立评审仍需核对相应证据。扫描器解析、暂存读取、修复和重复检测的细节见[扫描器参考](docs/SCANNERS.md)。

## 输出示例

```
$ python tools/dash_guard.py --tree
dash_guard: 1 file(s) deliberately excluded:
  tools/dash_guard.py                    the guard's own source (contains the dash set by design)
dash_guard: clean (16 file(s) examined, 1 skipped)
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

这些检查不扫描完整 Git 历史，提交钩子只看新增的行，所以已经躺在老 commit 或旧文件里的违规就留在那儿。`dash_guard --fix` 就地重写文件，并且刻意不能当闸门用：它修复成功后退 0，把它接进钩子等于装了一个不可能失败的检查。v0.3.0 新增的注释类没有修复器，在消费方升级之前只报告。它们的词法器是手写的小东西，不是解析器；YAML 标量（包括 `description:` 这种写成正文的）暂不检查，块标量里的 `#` 行也算正文不算注释，只有 `run:` 块例外，那里的 `#` 行会被计入，因为那是 shell 注释。JS 词法器还没在 `.jsx` 或 `.tsx` 文件上量过召回率，因为目前没有消费方带这类文件；`js` 要改成阻断之前必须先量。而 `load_budget` 只认两种仓库形态，`skills/*/SKILL.md` 和根目录下的 `SKILL.md`，别的形态一律报成什么都没测到。

## 语言

English (`README.md`) · 中文 (`README_CN.md`)

## 路线图 · 贡献 · 许可

见 [ROADMAP.md](ROADMAP.md) · [CHANGELOG.md](CHANGELOG.md)。
