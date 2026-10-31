# Independent audit and fixes

[Русский](audit.md) | English

2026-10-31. A separate agent without implementation history read the critical
paths and reproduced defects using temporary data. Assumed load: one user,
Windows/Linux, multiple chats and two devices sharing an Obsidian vault.

The initial revision passed 57 shared-knowledge tests and 250 pipeline tests.
The first audit found 12 defects; a second pass added two more. Each now has a regression or an
expanded relevant check. Fixes are verified by rerunning the suites.

| # | Priority | Reproduced failure | Fix |
|---|---|---|---|
| 1 | P1 | `--on-conflict skip` replaced another source's existing file | The writer checks the destination; merge protects unrelated targets |
| 2 | P1 | A ChangeSet updated `raw/` or `SCHEMA.md` | Raw/meta mutations are rejected before staging; routing checks remain |
| 3 | P2 | Windows paths produced invalid source YAML | Source strings use JSON escaping, valid in YAML |
| 4 | P2 | A failed manifest commit permanently blocked archive export | Retry accepts a completed archive write only after reconstructing the prior SHA; changed bodies are rejected |
| 5 | P1 | Atomization replaced the input, then archived the new output | Output/input path collisions fail before writing; the writer must finish all results before archival |
| 6 | P1 | `../outside.md` allowed edits outside the vault | Resolved containment is checked, including direct writes and archival |
| 7 | P2 | `A:B` and `A?B` collapsed into one file | Document, personal and contact generation share a preflight filename check, including case |
| 8 | P2 | Another chat refreshed SQLite between inventory and SELECT, causing `KeyError` | Rows outside the current inventory are skipped with a warning, without deleting another chat's new row |
| 9 | P2 | A new entity duplicated an existing heading | Validation checks the resulting entity set, including updates |
| 10 | P2 | `renames` succeeded without renaming files | Unsupported renames fail explicitly; prompts no longer advertise them |
| 11 | P2 | An unsafe `wiki_folder` let init escape the vault | Init, ingest, compile and lint share Wiki-root validation |
| 12 | P1 | Deduplication moved immutable raw into the ordinary-note archive | Candidate scans, merge and link updates exclude Wiki and shared Codex knowledge, including a configured Wiki folder |
| 13 | P2 | `~/vault` worked for reading but failed for writing and snapshot checks | The loader, commands and low-level guards normalize vault paths consistently |
| 14 | P2 | Without expected-state, `notes_folder="../outside"` let the general writer escape | Destination containment is checked before mkdir and again inside atomic_copy_note without a snapshot |

Regressions live in
[`test_data_boundaries.py`](../pipeline/tests/test_data_boundaries.py),
[`test_wiki_compile.py`](../pipeline/tests/test_wiki_compile.py) and
[`test_shared_knowledge.py`](../skills/codex-shared-knowledge/tests/test_shared_knowledge.py).

## Additional improvements

- Retired native topics remain archived with stable IDs. An upgrade restores
  verified topic backups owned by the current device.
- Index paths are portable across Windows and Linux. CI tests both components
  on both systems. The rclone download path uses Python rather than Bash.
- Temporary files use the OS temporary directory and are cleaned after Codex calls.
  Diagnostics check the selected CLI without requiring every optional integration.
- Duplicate instructions, the old installer, a legacy embedding template and a
  script that appended unsupported boilerplate paragraphs were removed.
- Code, prompts, contracts and RU/EN guides are organized by purpose.
- New hooks preserve foreign settings, back up the old file and do not read chat
  contents. Independent Windows execution checks covered paths with spaces,
  quotes and shell metacharacters.

## Validation limits

Live models, NotebookLM, Google Drive and real file delivery through synchronization
were not tested. Linux runtime is checked by CI separately from local Windows runs.
Not every integration helper was read in full. The environment prevented junction
testing. Direct callback execution does not prove Codex trust or lifecycle delivery;
those are separate checks.

Wiki still requires one writer per space and completed synchronization before
switching computers. There is no transaction across all pages or distributed lock.
