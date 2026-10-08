# Combined maintenance documentation

The `combined` profile is for a PRIVATE repository that intentionally maintains source and versioned backups together. A trusted caller must select it explicitly. Missing public release files never select this profile automatically. The storage and visibility gates establish eligibility; this checker reports those properties as unverified.

## Admitted inputs

The checker reads only `README.md`, `ROADMAP.md`, `docs/MAINTENANCE_CHANGELOG.md` and optional `.gitmodules`, with the normal 1 MiB limit and physical-file checks. The first three files are required. A root `CHANGELOG.md` may be curation DATA and is never opened under this profile. `README_CN.md`, package/plugin metadata and linked storage or recovery payloads are also outside the read boundary.

Local links resolve relative to their source document. Their targets receive path metadata checks, and anchors are checked only when the target is another admitted document. Sparse files retain the existing exact skip-worktree regular-file check. No documented command is executed.

## Maintenance duties

| Document | Structural obligation |
|---|---|
| README | Substantive Design Philosophy before Installation or Setup, plus setup prose and a command or linked entry. Existing Chinese heading forms also work. |
| README current state | A substantive `Current` or `当前` section with a local file link to the current evidence or maintenance guide. |
| README recovery | A substantive `Recovery`, `Restore`, `恢复` or `还原` section with a local file link to recovery instructions. |
| README storage | A substantive `Storage`, `存储` or data-contract section linking to `storage.contract.json`. The checker inspects that target's path metadata only. |
| ROADMAP | Substantive Current and Planned/Future sections describing capabilities, verification limits and next work. A numeric version does not replace these duties. |
| Dedicated maintenance changelog | Substantive notes under Unreleased or the latest ISO-dated maintenance heading. Empty Unreleased is valid when the latest dated entry has substantive notes. Dates must be valid, nonfuture, unique and newest first. Unreleased can appear once before dated entries. |

At accepted and release stages, current scaffold placeholders fail. Future roadmap tasks and older dated maintenance history retain the existing placeholder boundary. Draft still requires the document structure and links, but permits unfinished prose. New `readme.maintenance` and `changelog.maintenance` checks report maintenance obligations; version-source, displayed-version and numeric-release checks report `NOT_APPLICABLE`.

The release stage applies the same maintenance duties. It does not manufacture a release version or establish publication. README translation, package metadata and curation history remain outside this profile's requirements.

## Evidence limits

These checks establish document structure and local path consistency. They do not prove that the rationale is sound, the current state is accurate, the recovery guide works, storage is safe, or changelog history is complete. Independent review must compare the maintained documents with implementation and relevant evidence, and preserve that distinction in the private handoff.
