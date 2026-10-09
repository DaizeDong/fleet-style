# Scanner behavior

Paths below are relative to the kit checkout. In a consumer, prefix tool paths with `style/`.

## Staged scans and repair

The staged modes read the index blobs, including when explicit paths are supplied. An unstaged edit or removal cannot hide content that is about to be committed. `--added-only` checks the added lines of that same staged version. Unreadable or untokenizable inputs produce an incomplete result and a nonzero exit. Deliberate exclusions are listed separately with the examined count.

Comment scanning also covers JavaScript, TypeScript, YAML, shell, PowerShell and cmd files. These kinds report by default; pass `--block-kinds js,yaml,sh,ps,cmd` or the CI action's `block-kinds` input to make their findings block. `--message FILE --block-kinds message` checks a commit message and preserves Git's comment and scissors handling. An incomplete scan always blocks regardless of the selected kinds. Comment files have no automatic fixer. Shell scripts without an extension are identified from the same staged or worktree content being checked, so an unstaged shebang change cannot hide a staged comment.

`wrap_guard.py` uses the same safe file access and Markdown block parser. Its staged checks read text and `.wrap-allow` from the index; `--added-only` checks changed lines using textual Git ranges even when attributes mark Markdown as binary. Missing inputs and unavailable ranges block. Repair preserves code blocks, HTML blocks, explicit Markdown hard breaks, and allowed paragraphs or list items. It joins only reported spans and retains other bytes, including line endings and Unicode separators inside code. Repair rejects links and files that change during access, and `--fix --staged` is refused to preserve unstaged edits.

The shared Markdown parser treats LF, CRLF and CR as line endings. Unicode separators inside a physical code line cannot open or close a fence. Commit-message checks stop at Git's scissors marker and report visible body findings at their original source line numbers, including when comments have been removed.

Use `--fix --tree` to repair worktree files, inspect the diff, and stage the changes you want. `--fix --staged` is refused because replacing worktree files from the index would discard unstaged edits. `--check` and `--fix` are mutually exclusive.

    python tools/make_fixtures.py --check
    python -m pytest tools/ -q

The first command verifies the generated synthetic inputs. The second runs the kit's full test suites, including controls for incomplete scans and staged content.

The scanners share Markdown code protection that respects paragraph and container boundaries. Fenced and indented code, including code in quotes and lists, stays unchanged when fixing prose and is excluded from duplication measurements. Inline code can span physical lines within one paragraph. An unmatched delimiter cannot hide prose in a later block. Dependency references are excluded when a submodule marker exists at any ancestor below the skill's reference root.

In GitHub Markdown tables, inline code stays within its own cell. An escaped pipe remains part of that cell. Ordinary paragraphs containing pipes retain normal inline-code behavior. The no-value and leading-item repairs also apply to recognized tables in containers and without outer pipes, preserving their container prefixes. Literal backticks inside inline HTML or link destinations and titles cannot open a code span over following prose. Those literal fields retain their bytes, and code in link labels or around HTML keeps normal code-span precedence. Duplication measurements exclude complete tables, including tables without outer pipes and tables in quotes or lists. HTML blocks follow their own boundaries: literal backticks there do not hide prose, while HTML inside a Markdown code block remains protected.

Link reference definitions are parsed before inline code. Their destinations and titles remain literal, including multiline definitions in quotes and lists, and cannot hide the next paragraph. Full, collapsed and shortcut references use the document's defined labels. Completing a link disables enclosing link openers; image openers retain their separate nesting rules, preserving genuine code after an invalid nested link.

Duplication checks use those same parsed links to normalize inline, reference and image labels. Their delimiters and targets are removed while adjacent label text stays joined. Escaped, unresolved and rejected link syntax remains visible prose, so a link-shaped tail cannot erase words that should be compared.

`load_budget.py --max-dup` accepts a finite percentage from 0 through 100. A decoding, discovery or read error exits 3 and reports the affected input on stderr; it emits no partial JSON success. Inputs must be regular files in physical directories, including the supplied root's ancestors. Links are reported as unsupported, and submodules are pruned before traversing their contents. Missing references still produce the explicit `NOT CHECKED` result described by the tool.

`tools/make_fixtures.py --out DIRECTORY` writes the synthetic fixtures by basename for the shared data-boundary check. Add `--check` to verify that directory without rewriting it.
