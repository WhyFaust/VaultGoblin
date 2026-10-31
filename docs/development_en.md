# Development

[Русский](development.md) | English

## Layout

The components are independent. Shared knowledge uses only the standard library;
`pipeline/` owns import and Wiki processing with separate dependencies. The
installed skill is a deployed copy, not the source of code changes.

| Directory | Purpose |
|---|---|
| `skills/codex-shared-knowledge/scripts/` | Export, FTS5 search and Windows task installation |
| `skills/codex-shared-knowledge/tests/` | Export, IDs, search boundaries and context-budget regressions |
| `pipeline/scripts/` | Processing commands and shared modules |
| `pipeline/prompts/` | Short model instructions, without agent installation or command catalogs |
| `pipeline/rules/` | Note, taxonomy and Wiki contracts |
| `pipeline/templates/wiki/` | RU/EN Wiki templates |
| `pipeline/examples/` | Example regular notes |
| `pipeline/tests/` | Wiki, writer, index and document-processing checks |
| `docs/` | Paired RU/EN guides |

## Checks

From the repository root, Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install pytest -r pipeline/requirements.txt
.venv/bin/python -W error::EncodingWarning -X warn_default_encoding -m unittest discover -s skills/codex-shared-knowledge/tests -q
cd pipeline
../.venv/bin/python -X utf8 -m pytest -q
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pytest -r pipeline/requirements.txt
.\.venv\Scripts\python.exe -W error::EncodingWarning -X warn_default_encoding -m unittest discover -s skills/codex-shared-knowledge/tests -q
Push-Location pipeline
..\.venv\Scripts\python.exe -X utf8 -m pytest -q
Pop-Location
```

CI runs both suites on Linux and Windows. Tests use temporary data and mock external
calls. They do not verify NotebookLM, Google Drive, model availability or file
delivery through your chosen Obsidian synchronization mechanism.

Use `--help` for CLI smoke checks. `doctor.py` reads local configuration;
`memory_index.py build` indexes a real vault and is not a routine test. Run model
integration checks separately for a specific task.

## Local data

Do not commit `config.toml`, `shared-knowledge.json`, authentication, `.env`,
`processed.json`, deduplication registries, staging, vault contents, memory exports
or SQLite databases. The root `.gitignore` excludes them. Example settings contain
no personal paths or credentials. Use `tempfile` for new temporary files.

When moving a script, update callers, skill instructions, scheduling and both
guides. Keep Wiki snapshot checks, link validation and writes through the writer.
Index changes must remain compatible with existing installations.
