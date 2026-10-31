# Documents, notes and Wiki

[Русский](pipeline.md) | English

## Setup

This component is optional for shared Codex search. From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r pipeline/requirements.txt
cp pipeline/config.example.toml pipeline/config.toml
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r pipeline/requirements.txt
Copy-Item pipeline/config.example.toml pipeline/config.toml
```

Copy the example only for a new installation. Preserve existing `config.toml` and
processing registries. Set `vault.vault_path`; `/` or single-quoted TOML strings
are convenient for Windows paths. An empty `rclone.staging_dir` uses the OS temporary
folder. For Google Drive, configure rclone and `rclone.remote` separately.

The following commands run from `pipeline/`. On Windows, replace
`../.venv/bin/python` with `..\.venv\Scripts\python.exe -X utf8`.

## Wiki from selected sources

```bash
cd pipeline
../.venv/bin/python scripts/wiki_init.py my-project --mode project --title "My project" --lang en
../.venv/bin/python scripts/wiki_ingest.py my-project /path/to/source.md --kind docs --no-compile
../.venv/bin/python scripts/wiki_compile.py my-project --since-last-compile --dry-run
../.venv/bin/python scripts/wiki_compile.py my-project --since-last-compile
../.venv/bin/python scripts/wiki_lint.py my-project --strict
```

Normal compilation calls an authenticated Codex CLI. `--backend claude` selects
another supported backend; `VAULTGOBLIN_BACKEND` sets the choice for the environment.
When running inside an agent, automatic selection also checks its environment.
The CLI controls model settings. `--dry-run` does not call a model.

`project` creates core project pages. `corpus` starts with the shared structure
and grows entities and concepts. Templates support `--lang ru` and `--lang en`.
`wiki_ingest.py` accepts a file or directory and `--kind articles|docs|transcripts|assets`.

A Wiki lives at `<vault>/<wiki_folder>/<slug>/`:

| Layer | Purpose |
|---|---|
| `raw/` | Immutable inputs |
| `pages/`, `entities/`, `concepts/`, `comparisons/`, `queries/` | Compiled pages |
| `SCHEMA.md`, `index.md`, `log.md` | Contract, navigation and consumed-input ledger |

Compilation preserves existing wikilinks and verifies the source snapshot before
writing. The portable ledger in `log.md` stores SHA-256 of normalized UTF-8 text;
local paths are not part of source identity. Historical hashes remain supported.
`raw/_README.md` is not an input.

Use `wiki_update.py <slug> raw/docs/file.md` for one new input.
`--raw-only` explicitly selects inputs for reprocessing. `--update-only` updates
navigation without confirming new inputs. Import old local confirmations with
`wiki_compile.py <slug> --migrate-compile-state`. Check it with `--dry-run` first:
changed or unknown inputs are not confirmed.

Finish synchronization before switching PCs. Use one writer per Wiki. There is
no transaction across all pages: a partial failure may leave some pages updated.
Fix the cause and retry with a fresh snapshot. Do not bypass `WIKI_LINKS_LOST`,
`WIKI_SNAPSHOT_CHANGED` or `WIKI_WRITE_FORBIDDEN`.

## Atomic notes and contacts

| Task | Command after `../.venv/bin/python` |
|---|---|
| Local or rclone `.docx` document | `scripts/process.py "Document.docx"` |
| Existing note | `scripts/process_note.py "Note Title" --mode atomize` |
| Keep and improve one note | `scripts/process_note.py "Note Title" --mode enrich` |
| Contacts from a note | `scripts/process_contacts.py "Contacts Note"` |
| Existing JSON plan without a model call | `scripts/process.py plan.json --from-plan` |
| Markdown from a plan only | `scripts/generate_notes.py plan.json` |

For unattended runs, use `--non-interactive --on-conflict skip|overwrite` where
supported. Read `--help` first. Semantic processing calls a model and must preserve
the source's meaning. Regular notes and Wiki are separate. Contracts live in
`rules/`, prompts in `prompts/` and examples in `examples/`. Generated notes are
written through `vault_writer.py`, which checks boundaries and conflicts.

## NotebookLM

This optional integration requires local authentication. From `pipeline/`, install
browser dependencies:

```bash
../.venv/bin/python scripts/notebooklm_setup.py --skip-login
```

Then run `../.venv/bin/notebooklm login` in a separate interactive terminal, sign
in to Google and follow the completion prompt. On Windows, use
`..\.venv\Scripts\notebooklm.exe`. Credentials are not synchronized through Git.

`process_notebook.py <id>` fetches curated notes and processes them;
`fetch_notebook.py <id>` only fetches inputs. Options: `--include-sources`,
`--include-mindmap`, `--profile <name>`. For `NOTEBOOKLM_AUTH_REQUIRED`, check
dependencies and the local session; do not copy authentication from another PC.

`research_notebook.py run <id> "query" --dry-run` previews research.
Without `--dry-run`, it runs research and imports results once.
`research_notebook.py dedupe <id> --dry-run` previews duplicates for explicit cleanup.
An interrupted import is not a reason to retry automatically: inspect its result first.

## Vault search and maintenance

`memory_index.py status` reports the separate vault-wide index. Run the first
`memory_index.py build` explicitly. Afterwards, the writer can refresh it through
`[memory].auto_update`. `search "query" --json` supports `--folder`, `--tag`,
`--limit`, `--prefix` and `--raw`. This is not the shared Codex index.

`doctor.py` checks local setup and the selected backend; rclone and NotebookLM
are only needed by their own workflows. `audit_vault.py`, `dedup_vault.py`,
`fix_similar_notes.py`, `fix_atomic_notes.py` and `archive_empty_notes.py` are explicit
maintenance operations. Start with `--help` and `--dry-run`. Do not run them
automatically during ordinary knowledge recall.
