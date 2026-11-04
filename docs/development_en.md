# Development

[Русский](development.md) | English

## Layout

The components are independent. Shared knowledge uses only the standard library;
`pipeline/` owns import and Wiki processing with separate dependencies. The
Git clone is where source changes belong. `.codex-plugin/plugin.json` is the native
Codex manifest with `hooks/hooks.json` and interface metadata.
`extensions.com.openai.onboardingSkill` points to `skills/vaultgoblin-setup/SKILL.md`. The catalog
`.agents/plugins/marketplace.json` exposes this root as the `vaultgoblin` plugin
in the marketplace with the same name.

Code runs from the active plugin installation. Setup and `SessionStart` refresh
`CODEX_HOME/vaultgoblin/runtime/` for the Windows task. That runtime, the plugin
cache and the old deployed skill copy are not sources of code changes.

| Directory | Purpose |
|---|---|
| `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json` | Plugin manifest and installation catalog |
| `hooks/` | Portable hook definitions and launcher |
| `skills/vaultgoblin-setup/` | Initial setup, migration and automation controls |
| `skills/codex-shared-knowledge/scripts/` | Export, FTS5 search, runtime and Windows task installation |
| `skills/codex-shared-knowledge/tests/` | Export, IDs, search boundaries and context-budget regressions |
| `pipeline/scripts/` | Processing commands and shared modules |
| `pipeline/prompts/` | Short model instructions, without agent installation or command catalogs |
| `pipeline/rules/` | Note, taxonomy and Wiki contracts |
| `pipeline/templates/wiki/` | RU/EN Wiki templates |
| `pipeline/examples/` | Example regular notes |
| `pipeline/tests/` | Wiki, writer, index and document-processing checks |
| `docs/` | Paired RU/EN guides |

## Upgrading the integration

Routing descriptions and UI metadata for both skills are versioned alongside
their instructions. Update source `SKILL.md` and `agents/openai.yaml`, then
check their presence and contents in the actual installed package.

Setup installs profile hooks with `--profile-hooks`. The stable launcher is copied
to `CODEX_HOME/scripts/`; exports use the runtime outside the cache. Tests use
temporary profiles, package replacement and old-cache removal. They also cover
repeat setup, handler ownership and disabling without a vault. Changed hook
definitions remain subject to normal Codex trust review.

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

For the plugin, check its manifest and marketplace, package-relative references,
runtime updates and migration of old hooks while preserving unrelated settings.
Use separate temporary `CODEX_HOME` and vault directories. Real Setup on Windows
changes Task Scheduler, so do not run it as a routine file validation.

A separate `plugin` job installs the package with `codex-cli 0.166.0-alpha.6` in an
isolated `CODEX_HOME` on Ubuntu and Windows, without model calls. It checks the
installed metadata, onboarding and discovery of all three hooks using app-server.
User hook trust and real Windows Task Scheduler behavior need separate checks.

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

## Linux watcher check

```bash
.venv/bin/python -m pip install -r skills/codex-shared-knowledge/requirements-watch.txt
.venv/bin/python skills/codex-shared-knowledge/tests/check_memory_watcher.py
```

The integration check uses temporary files, including atomic replacement and a
new write during export. It never modifies real Codex memory.
