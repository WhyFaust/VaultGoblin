# Export when memory changes

[Русский](automation.md) | English

## Linux

After plugin setup, search and manual export are available. Plugin hooks do not
start automatic exports on Linux. For the event-driven watcher, use a permanent
Git clone, create an environment and install the optional watcher dependency:

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

After installing the plugin, run **Setup** or `$vaultgoblin-setup`. Setup retains
the local profile, refreshes the stable runtime and installs a silent task.
No extra packages or model calls are needed.

The plugin supplies `SessionStart`, `Stop` and `SessionEnd` through `hooks/hooks.json`.
`SessionStart` refreshes the runtime from the active installation. Hook commands
use `PLUGIN_ROOT`; the task uses `CODEX_HOME/vaultgoblin/runtime/`, without a pinned
plugin cache version. Open **Settings > Hooks** or `/hooks`, review and trust the
new definitions. Plugin updates may require another hook review.

Each hook quickly starts a separate export process bounded to 240 seconds.
`SessionEnd` runs synchronously, so it does not wait for the export itself.
The `Codex Shared Knowledge Export-<profile hash>` task runs at logon and every
five minutes: Codex has no documented memory-write event, and memory may change
after hooks. `export --if-changed` skips unchanged sources; the shared lock
prevents concurrent export writes for one profile.

Export starts through `pythonw.exe`; the child `python.exe` uses `CREATE_NO_WINDOW`.
Standard output, errors and exit codes are appended to
`CODEX_HOME/shared-knowledge-export.log`. The task also reports its exit code
through `LastTaskResult`. The selected `python.exe` needs a sibling `pythonw.exe`.

The task name includes a hash of `CODEX_HOME` so profiles do not replace each
other's tasks. The old `Codex Shared Knowledge Export` task is migrated only when
its `Action.Arguments` contains the exact current `CODEX_HOME` path in double
quotes. An unrelated task with the same name is preserved. Plugin migration
removes only the old VaultGoblin-labelled handlers, retaining other hooks and rules.

To disable automation, run Setup with `--no-automation`. It disables plugin hooks
through a local setting and removes only its current profile's task. Do this before
removing the plugin: uninstallation does not remove the Windows task automatically.
Settings and knowledge are retained.
Disabling without new `--vault` or `--device` values also works when the vault is
unavailable: it does not check FTS5 or require an installed export runtime.

### Without the plugin

After `install`, run from the permanent clone:

```powershell
python .\skills\codex-shared-knowledge\scripts\shared_knowledge.py install-hooks
& .\skills\codex-shared-knowledge\scripts\install_export_task.ps1 -PythonPath (Get-Command python.exe).Source
```

`install` and `install-hooks` prepare the same stable runtime. `install-hooks`
merges `Stop` and `SessionEnd` handlers into the existing `CODEX_HOME/hooks.json`
and backs up the previous file. Trust the definitions through Codex's normal
review. The task installer expects that runtime to be ready. To update, repeat
`install` with the previous `vault_path` and `device`, then run these two commands.
Custom local fields are preserved.

## macOS

Search and manual `export` work after Setup. Plugin hooks do not start automatic
exports. Use the manual command in the [setup guide](usage_en.md).

## Readable vault structure

Preview the plan first. This example uses the default `CODEX_HOME` on Linux/macOS;
see the [setup guide](usage_en.md) for the Windows path.

```bash
python3 ~/.codex/vaultgoblin/runtime/shared_knowledge.py organize --clean-setup
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
manual navigation pages are never overwritten. Make source changes in the Git
clone; update the installed plugin and runtime from that source.
