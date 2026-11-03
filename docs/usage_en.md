# Setup and use across computers

[Русский](usage.md) | English

## Codex plugin

First, set up one Obsidian vault to synchronize across your devices. VaultGoblin
does not transfer files: your existing Obsidian Sync, Remotely Save or another
chosen tool does that. Wait for synchronization to finish.

You need Python 3.10+ with SQLite FTS5 and Codex with plugin installation support.
Search and export use the standard library, without an API, model or server.
On Windows, `python` and `pythonw.exe` must be available on `PATH`.

```bash
codex plugin marketplace add WhyFaust/VaultGoblin
codex plugin add vaultgoblin@vaultgoblin
```

Open **Setup** for the plugin in Codex or explicitly invoke `$vaultgoblin-setup`.
For the first setup, supply an existing vault path and a device name. Names use
lowercase Latin letters, digits, `_` and `-`, up to 64 characters. On another
computer, use its local path to the same vault and a different name.

Setup runs `skills/codex-shared-knowledge/scripts/plugin_setup.py` from the active
plugin. The first run needs `--vault` and `--device`; later runs without them retain
the fields in `CODEX_HOME/shared-knowledge.json`. `CODEX_HOME` defaults to
`~/.codex`. On Windows, Setup also installs a silent export task at logon and
every five minutes.

Review and trust the new definitions in **Settings > Hooks** or `/hooks`. The
installer does not change `trusted_hash` or bypass Codex hook review. Plugin code
updates may require another hook review. Open a new chat to discover the skills.

## Migration and updates

When migrating from the standalone skill, run Setup without new parameters. It
retains the vault, device name, custom local settings, index and exported topics.
It removes only the old VaultGoblin-labelled handlers and its own `AGENTS.md`
instruction block. A recognized old skill copy moves to
`CODEX_HOME/backups/vaultgoblin-plugin/`. Other hooks and rules are preserved.

The plugin runs code from its active installation. An old `repository_path` does
not redirect execution to a clone. Setup and `SessionStart` refresh a stable copy
of two Python scripts and the task installer in `CODEX_HOME/vaultgoblin/runtime/`.
The Windows task uses that path, so changes to the plugin cache directory do not
leave it pointing at a removed version.

Update the plugin through Codex; repeat Setup without parameters when needed.
Make source changes in the Git clone, not the plugin cache or stable runtime.

Do not copy Codex authentication, internal databases or `memories` across devices.
If native memories have not been generated yet, export returns `no_local_memory`,
but another device's knowledge remains readable. VaultGoblin neither generates
nor modifies native Codex memory.

## Search and manual export

The `codex-shared-knowledge` skill selects the script from the active plugin.
For manual commands after Setup, you can use the stable runtime. Example for the
default `CODEX_HOME` on Linux/macOS:

```bash
python3 ~/.codex/vaultgoblin/runtime/shared_knowledge.py recall "SQLite" --project my-project
python3 ~/.codex/vaultgoblin/runtime/shared_knowledge.py search "SQLite" --limit 3
python3 ~/.codex/vaultgoblin/runtime/shared_knowledge.py read "ID-FROM-RESULTS"
python3 ~/.codex/vaultgoblin/runtime/shared_knowledge.py export
```

In Windows PowerShell, use `python` and the path
`"$HOME\.codex\vaultgoblin\runtime\shared_knowledge.py"`.
Replace it with your own path for a custom `CODEX_HOME`.

Choose words from an actual exported topic to check reading. An empty result for
an arbitrary query does not prove absence. `--project` is a strict filter; omit it
for general context. `warnings` reports incomplete synchronization or a changed
source. See [format, search limits and recovery](shared-knowledge_en.md).

## Automation and removing the plugin

On Linux, use the event-driven `watch` command and a user systemd service; the
plugin does not export on every chat end. On macOS, use manual export. See
[automation](automation_en.md) for details and standalone Windows automation setup.

Before removing the plugin, run Setup with `--no-automation`; for example, ask
`$vaultgoblin-setup` to disable automation. This disables plugin hooks through a
local setting and removes only its current profile's task. Then remove the plugin
through Codex. Removing the plugin alone does not remove the Windows task; user
settings and knowledge are retained.

## Standalone installation

If your Codex lacks the plugin CLI, install the skill from a permanent clone:

```bash
git clone https://github.com/WhyFaust/VaultGoblin.git
cd VaultGoblin
python3 skills/codex-shared-knowledge/scripts/shared_knowledge.py install \
  --vault "/path/to/Obsidian Vault" --device main-pc
python3 skills/codex-shared-knowledge/scripts/shared_knowledge.py export
```

On Windows, use `python`. `install` saves settings, deploys the skill to
`CODEX_HOME/skills/`, adds conditional recall to `AGENTS.md` and prepares the stable
runtime. Open a new chat. To update, run `git pull --ff-only` and repeat `install`
with the previous `vault_path` and `device`; custom local fields are preserved.
See the separate [automation setup](automation_en.md).

For import and Wiki setup, see the [pipeline guide](pipeline_en.md). When migrating
an older pipeline installation, retain your own `config.toml`, `processed.json`
and registries in `pipeline/` rather than replacing them with examples. Rebuild
the vault index explicitly or keep the previous location through `[memory].db_dir`.
