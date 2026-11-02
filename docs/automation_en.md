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
`install-hooks` and the old Windows task installer remain for compatibility.
This version of `watch` supports Linux; search and manual export remain portable.

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
