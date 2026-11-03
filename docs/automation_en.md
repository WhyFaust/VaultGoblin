# Export when memory changes

[Русский](automation.md) | English

## Linux

After installing the skill, create an environment and install the optional watcher dependency:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r skills/codex-shared-knowledge/requirements-watch.txt
.venv/bin/python skills/codex-shared-knowledge/scripts/shared_knowledge.py watch
```

`watch` uses native filesystem notifications for completed writes to `MEMORY.md`
and `memory_summary.md`, atomic replacement and deletion. Changes received during
an export remain pending for the next pass. Unrelated files, reads and idle time
trigger no exports. Startup performs one reconciliation for offline changes.
When a manual export holds the lock, the watcher waits for the kernel to release
it while retaining incoming events. Linux descriptor metadata for both sources
is checked before and after reading the snapshot. An open writer defers saving
until close; an open reader does not block export. This also covers writers
that were already open before the watcher started.
`export --if-changed` compares the two source contents with the last manifest and
skips regenerating unchanged notes. Search and manual export still need only the
standard library. No model calls or transcript reads are involved.

For background operation use the user service
[examples/systemd/vaultgoblin-watch.service](../examples/systemd/vaultgoblin-watch.service).
Adjust its clone path and `CODEX_HOME` when needed, then run:

```bash
mkdir -p ~/.config/systemd/user
cp examples/systemd/vaultgoblin-watch.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now vaultgoblin-watch.service
```

Disable the previous periodic timer. Do not also export on every `Stop` or
`SessionEnd`: memory may be written later. Codex has no documented `MemoryUpdated`
event; see [official hooks](https://learn.chatgpt.com/docs/hooks).
The watcher does not require Codex hook trust or change `trusted_hash`.
This version of `watch` supports Linux.

## Windows

After installing the skill, run from the clone root:

```powershell
python .\skills\codex-shared-knowledge\scripts\shared_knowledge.py install-hooks
& .\skills\codex-shared-knowledge\scripts\install_export_task.ps1 -PythonPath (Get-Command python.exe).Source
```

`install-hooks` merges `Stop` and `SessionEnd` handlers into the existing
`CODEX_HOME/hooks.json`, preserving other hooks and a backup of the previous file.
Open Codex `/hooks` and review the new definitions. The installer does not change
hook trust. Hooks export only native memory, without reading chats or calling a model.

Each hook quickly starts a separate export process bounded to 240 seconds.
`SessionEnd` runs synchronously, so it does not wait for the export itself.
The `Codex Shared Knowledge Export` task runs at logon and every five minutes:
Codex has no documented memory-write event, and memory may change after hooks.
`export --if-changed` skips unchanged sources; the shared lock prevents concurrent
export writes for one profile.

Both paths start through `pythonw.exe`; the child `python.exe` uses
`CREATE_NO_WINDOW`. No console is allocated. Standard output, errors and exit
codes are appended to `CODEX_HOME/shared-knowledge-export.log`. The task also
reports its exit code through `LastTaskResult`. The selected `python.exe` must
have a sibling `pythonw.exe`.

To upgrade an existing installation, first repeat `install` with the previous
`vault_path` and `device`, then run both commands above. They replace only
VaultGoblin handlers and the task with that name; repeating them adds no duplicates.
`repository_path` and custom local settings are preserved when installing from
the same clone. You can back up the old task XML first:

```powershell
Export-ScheduledTask -TaskName 'Codex Shared Knowledge Export' | Set-Content -Encoding UTF8 "$env:TEMP\codex-shared-knowledge-task.xml"
```

The old action started console-host `powershell.exe` and hid its window only
after startup. The new task action starts `pythonw.exe` directly, retaining the
fallback export for delayed memory writes.

## Readable vault structure

Preview the plan first:

```bash
python3 skills/codex-shared-knowledge/scripts/shared_knowledge.py organize --clean-setup
```

Add `--apply` to write it:

```text
Codex Knowledge/
  README.md
  Projects/
    esensor-aqa.md
    gitms.md
    general.md
  devices/
    <device>/...
```

Project pages link to current and archived topics using readable titles. Topic
bodies, IDs, filenames and manifests stay unchanged. The watcher also refreshes
navigation when another device's exports arrive. Restart it after the first
`organize --apply` to load the local setting.

`--clean-setup` removes only recognized legacy `Setup` snapshots and the old
`SETUP.md` guide. Changed or removed files are backed up outside the synced vault
under `CODEX_HOME/backups/vaultgoblin-navigation/`. Unknown manual files remain;
manual navigation pages are never overwritten. The Git clone remains the source
of code and installation instructions.
