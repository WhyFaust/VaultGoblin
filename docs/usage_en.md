# Setup and use across computers

[Русский](usage.md) | English

## Shared Codex knowledge

First, set up one Obsidian vault to synchronize across your devices. VaultGoblin
does not transfer files: your existing Obsidian Sync, Remotely Save or another
chosen tool does that. Wait for synchronization to finish.

Clone the project into a permanent folder and run from its root:

```bash
git clone https://github.com/WhyFaust/VaultGoblin.git
cd VaultGoblin
python3 skills/codex-shared-knowledge/scripts/shared_knowledge.py install \
  --vault "/path/to/Obsidian Vault" --device main-pc
python3 skills/codex-shared-knowledge/scripts/shared_knowledge.py export
```

Python 3.10+ with SQLite FTS5 is required. This component needs no extra packages.
On Windows, use `python`. PowerShell example:

```powershell
python .\skills\codex-shared-knowledge\scripts\shared_knowledge.py install --vault "C:\Users\name\Documents\Obsidian Vault" --device windows-pc
python .\skills\codex-shared-knowledge\scripts\shared_knowledge.py export
```

Device names use lowercase Latin letters, digits, `_` and `-`, up to 64 characters.
On the second PC, repeat the commands with its path to the same vault and a
different name. Do not copy Codex authentication, internal databases or `memories`.

The installer writes local settings to `CODEX_HOME/shared-knowledge.json`, deploys
the skill to `CODEX_HOME/skills/` and adds a small block to `AGENTS.md`.
`CODEX_HOME` defaults to `~/.codex`. Existing instructions are preserved.
Open a new Codex chat to load the updated instructions.

If Codex has not generated local memories yet, export returns `no_local_memory`.
You can still read another device's knowledge. Codex manages native memory;
VaultGoblin neither generates nor modifies it.

## Check reading

```bash
python3 skills/codex-shared-knowledge/scripts/shared_knowledge.py recall "SQLite" --project my-project
python3 skills/codex-shared-knowledge/scripts/shared_knowledge.py search "SQLite" --limit 3
python3 skills/codex-shared-knowledge/scripts/shared_knowledge.py read "ID-FROM-RESULTS"
```

Choose words from an actual exported topic. An empty result for an arbitrary query
does not prove absence. `--project` is a strict filter; omit it for general context.
`warnings` reports incomplete synchronization or a changed source.
See [format, search limits and recovery](shared-knowledge_en.md).

## Scheduled exports

Export is separate from search and makes no model calls. On Windows:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\skills\codex-shared-knowledge\scripts\install_export_task.ps1 -PythonPath (Get-Command python.exe).Source
```

The `Codex Shared Knowledge Export` task runs at sign-in and every 5 minutes for
the current user. Log: `CODEX_HOME/shared-knowledge-export.log`. It uses the current
clone; reinstall the task if you move it. For a `.venv` interpreter, pass its full
path as `-PythonPath`.

On Linux, reuse your existing user systemd timer. Command:

```text
/absolute/path/to/python3 /absolute/path/to/VaultGoblin/skills/codex-shared-knowledge/scripts/shared_knowledge.py export
```

Keep the local `CODEX_HOME` in the service if it differs from `~/.codex`.
Without a scheduler, you can run export manually.

## Update an existing installation

```bash
git pull --ff-only
python3 skills/codex-shared-knowledge/scripts/shared_knowledge.py install \
  --vault "/local/path/to/vault" --device existing-device-name
python3 skills/codex-shared-knowledge/scripts/shared_knowledge.py export
```

Keep the old `vault_path` and `device` from local settings. `repository_path`
will point to this clone; custom settings are preserved. The installed skill is a
deployed copy. Make code changes in the Git clone.

After upgrading from the old layout, reinstall the task or update the timer's
`ExecStart`: the script now lives in `skills/codex-shared-knowledge/scripts/`.
For import and Wiki processing, move your `config.toml`, `processed.json` and
registries from the old component folder to `pipeline/`; do not replace them with
examples. The vault index now defaults to `~/.cache/vaultgoblin/`. Rebuild it
explicitly or set `[memory].db_dir` to the previous directory. Notes and IDs stay
the same.

For import and Wiki setup, see the [pipeline guide](pipeline_en.md).

Turn and session export hooks: [automation setup](automation_en.md).
