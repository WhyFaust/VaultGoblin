# Development

[Русский](development.md) | English

## Layout

The components are independent. Shared knowledge uses only the standard library;
`pipeline/` owns document import and Wiki processing with separate dependencies.
Change sources in the Git clone. `.codex-plugin/plugin.json` defines the plugin
version, skills directory, `hooks/hooks.json` and interface metadata. The catalog
`.agents/plugins/marketplace.json` exposes this root as `vaultgoblin`.

Code runs from the active plugin installation. Setup and `SessionStart` refresh
`CODEX_HOME/vaultgoblin/runtime/` for automatic export. The runtime, plugin cache
and old deployed skill copy are not sources of code changes.

| Directory | Purpose |
|---|---|
| `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json` | Manifest and installation catalog |
| `hooks/` | Hook definitions and launcher |
| `skills/vaultgoblin-setup/` | Initial setup, migration and automation controls |
| `skills/codex-shared-knowledge/scripts/` | Export, FTS5 search, runtime and Windows task |
| `pipeline/scripts/` | Document processing and shared modules |
| `pipeline/prompts/`, `pipeline/rules/`, `pipeline/templates/wiki/` | Prompts, contracts and templates |
| `pipeline/examples/` | Example regular notes |
| `docs/` | Paired RU/EN guides |

## Package validation

Automated tests have been removed from the repository. Package validation is available:

```bash
python -m pip install -r requirements-dev.txt
python scripts/check_package.py
```

It checks package structure and metadata without a model or working vault. A pass
does not establish export, Wiki, watcher, hook, scheduler or external-integration
behavior. Verify changed behavior separately within the requested task, using
temporary data and a separate `CODEX_HOME`.

Use `--help` to inspect a CLI. `doctor.py` reads local configuration;
`memory_index.py build` indexes the real vault. A real Windows Setup changes the
scheduler, so these operations are not file validation. Use external models and
the user's vault only within the user's task.

## Automatic releases

The release workflow synchronizes `.codex-plugin/plugin.json` and `metadata.version`
in both `SKILL.md` files. Do not bump them manually. After changes reach `main`,
the workflow validates the package and chooses the largest Conventional Commit bump:

| Commit | Bump |
|---|---|
| `fix:` or `perf:` | patch, for example `1.2.3` → `1.2.4` |
| `feat:` | minor, for example `1.2.3` → `1.3.0` |
| `!` after type/scope or a `BREAKING CHANGE:` / `BREAKING-CHANGE:` footer | major, for example `1.2.3` → `2.0.0` |
| `docs:`, `chore:`, `ci:`, `build:`, `style:`, `refactor:` without a breaking change | no new release |

The first release uses the current version as its base; later releases use the
latest stable `vX.Y.Z` tag. For a squash merge, preserve the type and breaking marker
in the final commit title and body. Multiple commit types produce the largest bump,
not a sequence of releases.

The workflow writes synchronized versions, creates a `chore(release): vX.Y.Z`
commit, a tag and a GitHub Release containing the package ZIP. An installed copy
changes version after a Codex plugin update, not immediately after publication.
To install the new version:

```bash
codex plugin marketplace upgrade vaultgoblin
codex plugin add vaultgoblin@vaultgoblin
```

Start a new chat and run Setup for the existing installation. Local paths and the
selected profile-hook mode are retained. Their launcher and runtime live outside
the cache; changed hook definitions still require normal Codex trust.

## Local data and changes

Do not commit `config.toml`, `shared-knowledge.json`, authentication, `.env`,
`processed.json`, deduplication registries, staging, the vault, memory exports or
SQLite databases. The root `.gitignore` excludes them. Examples contain no personal
paths or credentials. Create temporary files through `tempfile`.

When relocating a script, update callers, skill instructions, scheduled tasks and
both guides. Preserve Wiki snapshot/link checks and writes through the writer.
A new index must remain compatible with already installed devices.
