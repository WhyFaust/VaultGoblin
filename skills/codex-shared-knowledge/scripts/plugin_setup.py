import argparse
import hashlib
import json
import os
import shlex
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


PROFILE_HOOK = "VaultGoblin: profile export"
PROFILE_EVENTS = ("SessionStart", "Stop", "SessionEnd")


def profile_commands(home: Path) -> tuple[str, str]:
    script = contained(home, home / "scripts/vaultgoblin_hook.py")
    quoted = str(script).replace("`", "``").replace("$", "`$").replace('"', '`"')
    windows = f'& pythonw.exe -B "{quoted}"; exit $LASTEXITCODE'
    return shlex.join([sys.executable, "-B", str(script)]), windows


def owns_profile_handler(home: Path, handler: dict) -> bool:
    return handler.get("statusMessage") == PROFILE_HOOK and handler.get("command") in profile_commands(home)


def new_profile_handler(home: Path, event: str) -> dict:
    command, windows = profile_commands(home)
    handler = {"type": "command", "command": windows if os.name == "nt" else command,
               "timeout": 3 if event == "SessionEnd" else 10, "statusMessage": PROFILE_HOOK}
    if os.name != "nt":
        handler["commandWindows"] = windows
    if event == "Stop":
        handler["async"] = True
    return handler


def prepare_hooks(home: Path, enabled: bool | None = None) -> tuple[tuple[Path, str, str], bool]:
    path = contained(home, home / "hooks.json")
    previous = path.read_text(encoding="utf-8") if path.exists() else "{}"
    config = json.loads(previous)
    if not isinstance(config, dict) or not isinstance(config.get("hooks", {}), dict):
        raise ValueError("hooks.json must contain a hooks object")
    changed = False
    detected = False
    for event in PROFILE_EVENTS:
        if event not in config.get("hooks", {}):
            continue
        groups = config["hooks"][event]
        if not isinstance(groups, list):
            raise ValueError(f"Invalid {event} hook groups")
        remaining = []
        installed = False
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise ValueError(f"Invalid {event} hook group")
            if any(not isinstance(handler, dict) for handler in group["hooks"]):
                raise ValueError(f"Invalid {event} hook handler")
            handlers = []
            for handler in group["hooks"]:
                owned = owns_profile_handler(home, handler)
                detected |= owned
                installed |= owned
                if handler.get("statusMessage") == EXPORT_HOOK and event != "SessionStart":
                    continue
                if owned and enabled is False:
                    continue
                handlers.append(handler)
            changed |= len(handlers) != len(group["hooks"])
            if handlers or not group["hooks"]:
                remaining.append({**group, "hooks": handlers})
        config["hooks"][event] = remaining
        if enabled is True and not installed:
            remaining.append({"hooks": [new_profile_handler(home, event)]})
            changed = True
    if enabled is True:
        hooks = config.setdefault("hooks", {})
        for event in PROFILE_EVENTS:
            if event not in hooks:
                hooks[event] = [{"hooks": [new_profile_handler(home, event)]}]
                changed = True
    updated = json.dumps(config, ensure_ascii=False, indent=2) + "\n" if changed else previous
    return (path, previous, updated), detected


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


def configure_windows_task(home: Path, installer: Path, *, remove: bool = False) -> None:
    if os.name != "nt":
        return
    command = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
               "-File", str(installer)]
    command.extend(["-Remove"] if remove else ["-PythonPath", sys.executable])
    try:
        completed = subprocess.run(
            command, env={**os.environ, "CODEX_HOME": str(home)}, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError("Task Scheduler outcome is unknown; inspect this profile's task before retrying.") from error
    if completed.returncode:
        raise ValueError(f"Task Scheduler setup failed: {completed.stderr.strip() or completed.stdout.strip()}")


def disable_automation(home: Path, local: dict) -> dict:
    migration, detected = prepare_hooks(home, False)
    if "plugin_profile_hooks" not in local and detected:
        local = {**local, "plugin_profile_hooks": True}
    local = {**local, "plugin_auto_export": False}
    path = contained(home, home / "shared-knowledge.json")
    atomic_write(path, json.dumps(local, ensure_ascii=False, indent=2) + "\n")
    configure_windows_task(home, Path(__file__).with_name("install_export_task.ps1"), remove=True)
    save_migration(home, *migration)
    return {"status": "configured", "vault": local.get("vault_path"), "device": local.get("device"),
            "automatic_export": False}


def setup(home: Path, vault: Path | None = None, device: str | None = None, *, automation: bool = True,
          profile_hooks: bool | None = None) -> dict:
    path = contained(home, home / "shared-knowledge.json")
    original = path.read_text(encoding="utf-8") if path.exists() else None
    previous = json.loads(original) if original is not None else {}
    if not isinstance(previous, dict):
        raise ValueError("Local shared-knowledge settings must be an object")
    if not automation and vault is None and device is None:
        if profile_hooks is not None:
            previous["plugin_profile_hooks"] = profile_hooks
        return disable_automation(home, previous)
    if vault is None and not previous.get("vault_path"):
        raise ValueError("Specify --vault for the first setup")
    if device is None and not previous.get("device"):
        raise ValueError("Specify --device for the first setup")
    local = installation_settings(vault or Path(previous["vault_path"]), device or previous["device"], home)
    with closing(sqlite3.connect(":memory:")) as database:
        database.execute("CREATE VIRTUAL TABLE capability USING fts5(text)")
    _, detected = prepare_hooks(home)
    profile_mode = profile_hooks if profile_hooks is not None else previous.get("plugin_profile_hooks", detected)
    if not isinstance(profile_mode, bool):
        raise ValueError("plugin_profile_hooks must be a boolean")
    hook_migration, _ = prepare_hooks(home, profile_mode and automation)
    migrations = [hook_migration, legacy_instructions(home)]
    skill = contained(home, home / "skills/codex-shared-knowledge")
    if skill.exists():
        script = contained(home, skill / "scripts/shared_knowledge.py")
        if not script.is_file() or 'GENERATOR = "codex-shared-knowledge"' not in script.read_text(encoding="utf-8"):
            raise ValueError(f"Unrecognized skill at {skill}; move it aside before plugin setup")
    runtime = install_runtime(home)
    if profile_mode:
        wrapper = contained(home, home / "scripts/vaultgoblin_hook.py")
        content = Path(__file__).with_name("profile_hook.py").read_text(encoding="utf-8")
        if not wrapper.exists() or wrapper.read_text(encoding="utf-8") != content:
            atomic_write(wrapper, content)
    local["plugin_profile_hooks"] = profile_mode
    local["plugin_auto_export"] = automation and os.name == "nt"
    atomic_write(path, json.dumps(local, ensure_ascii=False, indent=2) + "\n")
    try:
        configure_windows_task(home, runtime / "install_export_task.ps1", remove=not automation)
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
    parser.add_argument("--profile-hooks", action="store_true", default=None)
    args = parser.parse_args()
    try:
        print(json.dumps(setup(codex_home(), args.vault, args.device, automation=not args.no_automation,
                               profile_hooks=args.profile_hooks),
                         ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, subprocess.TimeoutExpired) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
