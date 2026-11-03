import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from shared_knowledge import (
    AGENT_LINE, EXPORT_HOOK, RECALL_END, RECALL_START, atomic_write, codex_home,
    contained, installation_settings, install_runtime,
)


def legacy_hooks(home: Path) -> tuple[Path, str, str]:
    path = contained(home, home / "hooks.json")
    previous = path.read_text(encoding="utf-8") if path.exists() else "{}"
    config = json.loads(previous)
    if not isinstance(config, dict) or not isinstance(config.get("hooks", {}), dict):
        raise ValueError("hooks.json must contain a hooks object")
    changed = False
    for event in ("Stop", "SessionEnd"):
        if event not in config.get("hooks", {}):
            continue
        groups = config["hooks"][event]
        if not isinstance(groups, list):
            raise ValueError(f"Invalid {event} hook groups")
        remaining = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise ValueError(f"Invalid {event} hook group")
            if any(not isinstance(handler, dict) for handler in group["hooks"]):
                raise ValueError(f"Invalid {event} hook handler")
            handlers = [h for h in group["hooks"] if h.get("statusMessage") != EXPORT_HOOK]
            changed |= len(handlers) != len(group["hooks"])
            if handlers or not group["hooks"]:
                remaining.append({**group, "hooks": handlers})
        config["hooks"][event] = remaining
    updated = json.dumps(config, ensure_ascii=False, indent=2) + "\n" if changed else previous
    return path, previous, updated


def legacy_instructions(home: Path) -> tuple[Path, str, str]:
    path = contained(home, home / "AGENTS.md")
    previous = path.read_text(encoding="utf-8") if path.exists() else ""
    if (RECALL_START in previous) != (RECALL_END in previous):
        raise ValueError("Incomplete codex-shared-recall block in AGENTS.md")
    updated = previous
    if RECALL_START in updated:
        start = updated.index(RECALL_START)
        end = updated.index(RECALL_END, start) + len(RECALL_END)
        updated = updated[:start] + updated[end:]
    updated = "".join(line for line in updated.splitlines(keepends=True) if line.rstrip("\r\n") != AGENT_LINE)
    return path, previous, updated


def save_migration(home: Path, path: Path, previous: str, updated: str) -> None:
    if previous == updated:
        return
    digest = hashlib.sha256(previous.encode("utf-8")).hexdigest()[:16]
    backup = contained(home, home / "backups/vaultgoblin-plugin" / f"{path.name}-{digest}")
    if not backup.exists():
        atomic_write(backup, previous)
    atomic_write(path, updated)


def setup(home: Path, vault: Path | None = None, device: str | None = None, *, automation: bool = True) -> dict:
    path = contained(home, home / "shared-knowledge.json")
    original = path.read_text(encoding="utf-8") if path.exists() else None
    previous = json.loads(original) if original is not None else {}
    if not isinstance(previous, dict):
        raise ValueError("Local shared-knowledge settings must be an object")
    if vault is None and not previous.get("vault_path"):
        raise ValueError("Specify --vault for the first setup")
    if device is None and not previous.get("device"):
        raise ValueError("Specify --device for the first setup")
    local = installation_settings(vault or Path(previous["vault_path"]), device or previous["device"], home)
    with closing(sqlite3.connect(":memory:")) as database:
        database.execute("CREATE VIRTUAL TABLE capability USING fts5(text)")
    migrations = [legacy_hooks(home), legacy_instructions(home)]
    skill = contained(home, home / "skills/codex-shared-knowledge")
    if skill.exists():
        script = contained(home, skill / "scripts/shared_knowledge.py")
        if not script.is_file() or 'GENERATOR = "codex-shared-knowledge"' not in script.read_text(encoding="utf-8"):
            raise ValueError(f"Unrecognized skill at {skill}; move it aside before plugin setup")
    runtime = install_runtime(home)
    local["plugin_auto_export"] = automation and os.name == "nt"
    atomic_write(path, json.dumps(local, ensure_ascii=False, indent=2) + "\n")
    try:
        if os.name == "nt":
            command = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                       "-File", str(runtime / "install_export_task.ps1"), "-PythonPath", sys.executable]
            if not automation:
                command.append("-Remove")
            completed = subprocess.run(
                command, env={**os.environ, "CODEX_HOME": str(home)}, capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if completed.returncode:
                raise ValueError(f"Task Scheduler setup failed: {completed.stderr.strip() or completed.stdout.strip()}")
    except subprocess.TimeoutExpired as error:
        raise ValueError("Task Scheduler outcome is unknown; inspect this profile's task before retrying. "
                         "Settings and runtime are prepared; legacy migration has not run.") from error
    except (OSError, ValueError) as error:
        raise ValueError(f"Settings and runtime are prepared; legacy migration has not run. {error}") from error
    for migration in migrations:
        save_migration(home, *migration)
    if skill.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        destination = contained(home, home / "backups/vaultgoblin-plugin" / f"skill-{stamp}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(skill), str(destination))
    return {"status": "configured", "vault": local["vault_path"], "device": local["device"],
            "runtime": str(runtime), "automatic_export": local["plugin_auto_export"],
            "hooks": "Review VaultGoblin hooks in Codex Settings > Hooks"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure the native VaultGoblin Codex plugin")
    parser.add_argument("--vault", type=Path)
    parser.add_argument("--device")
    parser.add_argument("--no-automation", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(setup(codex_home(), args.vault, args.device, automation=not args.no_automation),
                         ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, subprocess.TimeoutExpired) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
