# Agent Usage

This document shows how Claude Code and Codex should operate on this repository.

## Canonical Flow
1. Read `AGENTS.md`.
2. Run `python3 scripts/doctor.py` if setup is uncertain.
3. Choose the matching local command.
4. Use `--dry-run` when available before making high-impact changes.
5. Use explicit non-interactive policies when the command may otherwise prompt.

## Intent To Command
- Import a `.docx` into the vault:
  `python3 scripts/process.py "Document.docx"`
- Import a `.docx` into the vault without prompts:
  `python3 scripts/process.py "Document.docx" --non-interactive --on-conflict skip`
- Rework a personal note:
  `python3 scripts/process_note.py "Note Title"`
- Rework a personal note in atomize mode without prompts:
  `python3 scripts/process_note.py "Note Title" --mode atomize --non-interactive --on-conflict skip`
- Only generate markdown from a prepared plan:
  `python3 scripts/generate_notes.py /path/to/atom-plan.json`
- Only write staged markdown to the vault:
  `python3 scripts/vault_writer.py --staging /path/to/staging --atom-plan /path/to/atom-plan.json`
- Only write staged markdown to the vault without prompts:
  `python3 scripts/vault_writer.py --staging /path/to/staging --atom-plan /path/to/atom-plan.json --non-interactive --on-conflict skip`
- Inspect duplicate candidates without changing files:
  `python3 scripts/dedup_vault.py --dry-run --skip-claude`
- Run dedup without prompts:
  `python3 scripts/dedup_vault.py --non-interactive --decision skip`

## Environment Expectations
- `config.toml` exists and points to a real Obsidian vault.
- `claude` CLI is available in `PATH` for semantic rewrite steps.
- `rclone` is available for `.docx` fetching.

## Notes For Claude Code
- `SKILL.md` is a thin adapter over the repo-local contract.
- Optional registration in `~/.claude/CLAUDE.md` is handled by `install.sh --mode claude`.

## Notes For Codex
- `AGENTS.md` is the primary integration surface.
- No global install is required to understand repository workflows.
- Prefer explicit no-prompt flags in tool runs so the agent never blocks on stdin.

## Portable Wiki Compilation

Normal compilation uses `compiled_raws_version: 2` and `compiled_raws` in the
Wiki-space's `log.md`. The ledger stores SHA-256 of normalized UTF-8 raw file
text and travels with the vault between Windows and Linux. Historical snapshot
hashes remain readable. A new or changed source stays pending until consumed;
raw status and prose log rows do not prove consumption. `raw/_README.md` is not
an input. Use `--raw-only` for intentional replay or explicit batches.

To import matching confirmations from a previous local `wiki_compile_state.json`:

```bash
python3 scripts/wiki_compile.py codex --migrate-compile-state --dry-run
python3 scripts/wiki_compile.py codex --migrate-compile-state
```

This idempotent maintenance pass updates only log metadata and appends an audit
row through the writer. It does not call a model, change raw inputs, or confirm
unknown/changed sources. The previous local state is retained. Normal compilation
uses the synchronized log, not that machine-specific file.

The full snapshot stays local for validation. The model prompt includes selected
raw bodies once and omits historical raw bodies. The writer checks snapshot
fingerprints before writing and checks each target again before atomic note
replacement. A mismatch fails with `WIKI_SNAPSHOT_CHANGED`. The log is written
after regular pages; strict compile writes fail on unreadable/skipped notes.

Run one writer per Wiki-space and finish synchronization before switching PCs.
There is no distributed lock or transaction across all pages: a partial failure
may leave some complete pages updated. Retry from a fresh snapshot after resolving
the error. Dry runs and index regeneration do not advance the ledger. These
commands are maintenance operations, not checks to run automatically.
