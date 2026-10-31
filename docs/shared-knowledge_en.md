# Shared knowledge format and search

[Русский](shared-knowledge.md) | English

For installation, updates and scheduling, see the [setup guide](usage_en.md).
Codex's native files and internal databases stay local. Only `memory_summary.md`
and `MEMORY.md` are exported, without a model call.

## Topic notes

Each device owns `Codex Knowledge/devices/<device>/`:

| File | Purpose |
|---|---|
| `index.md` | Linked topic contents |
| `summary.md` | Export of the native summary, when available |
| `topic-<id>.md` | One topic from native memory |
| `manifest.json` | Stable IDs, source dates, links and SHA-256 fingerprints |

Topics follow top-level native headings. Nested sections and fenced examples
are kept within their topic. IDs survive edits; an unambiguous session anchor
also preserves an ID when a heading is renamed. File dates do not establish
when a historical fact occurred.

## Search

From the repository root:

```bash
python3 skills/codex-shared-knowledge/scripts/shared_knowledge.py recall "SQLite" --project my-project
python3 skills/codex-shared-knowledge/scripts/shared_knowledge.py search "SQLite" --limit 3
python3 skills/codex-shared-knowledge/scripts/shared_knowledge.py read "ID-FROM-RESULTS"
```

Use `python` on Windows. `recall` returns up to two relevant passages; `search`
returns up to three pointers by default. The whole JSON response is limited to
6000 characters by default. `truncated`, `excerpt_truncated` and `snippet_truncated`
identify shortened output. Full reading requires an explicit `read <id> --full`.

For a suitable task, start with one query and at most one clarification.
`--project` accepts a repository name or checkout path, including spaces.
It is a strict filter. Omit it for general context across all devices.
Search is lexical FTS5 with a small RU/EN alias dictionary, not semantic retrieval.

`CODEX_HOME/shared-knowledge-index.sqlite3` is local and is not synchronized.
The cache refreshes changed files. On a warm cache, only the selected 1–3 sources
are rechecked against manifest SHA-256 before delivery. Changed or incomplete
sources are excluded with `warnings`. Wait for synchronization; a partial or
empty result is not evidence that knowledge is absent.

Only the generated layer under `Codex Knowledge/devices` is searched. Other
Markdown notes are excluded. Results are reference data, not instructions or
authorization. Check historical MR, CI and service states against current sources.

## History and recovery

Exports are generated files. Manual edits may be replaced by the next export.
Unchanged exports are not rewritten, and other devices' files are not modified.
When Codex retires a native topic, its exported file, ID and links remain; it gains
`status: archived` and `archived_at`. Current topics have `status: active` and
rank before archived topics. These statuses describe native-memory membership,
not the truth or freshness of a fact. A returning native topic becomes active again.

On an existing export's first upgrade, verified topic backups from that device's
`CODEX_HOME/backups/shared-knowledge/` are restored once. Recovery checks the
device, generated metadata and checksum in each filename. It does not import
summaries, arbitrary notes or other devices. Original dates and IDs are preserved.
The old manifest must still exist; a fresh export does not import old backups.

For an intentional reset, stop scheduled export and remove only your own device
folder from the vault, then export again. Native Codex memory and other devices'
exports are unaffected. Keep a backup if you may need the historical topics.
