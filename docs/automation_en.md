# Automatic exports and hooks

[Русский](automation.md) | English

## Setup

First [install the skill](usage_en.md), then run from the clone's root:

```bash
python3 skills/codex-shared-knowledge/scripts/shared_knowledge.py install-hooks
```

Use `python` on Windows. This adds two handlers to `CODEX_HOME/hooks.json`.
Existing hooks are preserved; the previous file is backed up under
`CODEX_HOME/backups/shared-knowledge-hooks/`. Reinstallation does not create duplicates.

| Trigger | Action |
|---|---|
| `Stop` | Quiet background export after a turn |
| `SessionEnd` | Final synchronous export, with a 3-second timeout |
| Fallback timer | Export every 5 minutes to catch later memory updates |

Handlers run the installed `shared_knowledge.py export --quiet` using the Python
that installed them. They make no model calls, read no transcript or user message,
and do not author knowledge. Successful runs produce no output. A quiet call
succeeds if another export already holds the lock. File and configuration errors
remain visible.

Install the fallback Windows task:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\skills\codex-shared-knowledge\scripts\install_export_task.ps1 -PythonPath (Get-Command python.exe).Source
```

On Linux, keep your existing user systemd timer and set its interval to 5 minutes.
Run the local Python with the clone script's absolute path and `export`.
Windows task log: `CODEX_HOME/shared-knowledge-export.log`.

## Codex trust

Codex requires review and trust for the exact definitions of new hooks through
`/hooks`. Until then, it skips them. VaultGoblin does not bypass that mechanism or
change `trusted_hash`. Open a new chat after installation and review the two handlers
labeled `VaultGoblin: export shared knowledge`.
See the [official hook documentation](https://learn.chatgpt.com/docs/hooks).

Native memory updates happen in the background, so the files may not be ready when
a chat ends. There is no `MemoryUpdated` in the documented event list; the timer
catches delayed changes. See [Codex memories](https://learn.chatgpt.com/docs/customization/memories).

## Reading knowledge

The skill chooses context by task: one search for substantial work in a familiar
project, a repeated failure or an earlier decision. Simple edits and general
questions need no search. Other devices' new data is discovered on the next query.

Hooks do not preload notes into every chat or classify messages. Shared recall
stays within `Codex Knowledge/devices` and keeps its context budget. Use `recall`
or `search` for a manual reading check.
