#!/usr/bin/env python3
"""Export local Codex memories as linked topics and read only this shared layer."""

import argparse
import base64
import hashlib
import json
import os
import re
import shlex
import sqlite3
import sys
import tempfile
import uuid
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath

FOLDER = "Codex Knowledge"
SOURCES = ("memory_summary.md", "MEMORY.md")
MARKER = "<!-- codex-shared-knowledge: "
GENERATOR = "codex-shared-knowledge"
AGENT_LINE = "- codex-shared-knowledge — предыдущие решения и проектные знания с других устройств через Obsidian."
RECALL_START = "<!-- codex-shared-recall -->"
RECALL_END = "<!-- /codex-shared-recall -->"
EXPORT_HOOK = "VaultGoblin: export shared knowledge"
RECALL_RULE = (
    RECALL_START + "\n"
    "Перед содержательной работой в знакомом проекте, разбором повторной ошибки или вопросом о прошлом решении "
    "один раз используй codex-shared-knowledge. Для простых правок и общих вопросов пропускай поиск. "
    "Допускается один уточняющий запрос; уже прочитанные фрагменты в той же задаче повторно не загружай.\n"
    + RECALL_END
)


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser().resolve()


def contained(root: Path, target: Path) -> Path:
    """Reject paths redirected outside the intended root by links or traversal."""
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Path leaves the intended directory: {target}")
    return target


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def metadata(text: str) -> dict:
    text = text.replace("\r\n", "\n")
    if text.startswith("---\n"):
        header, separator, _ = text[4:].partition("\n---\n")
        if not separator:
            return {}
        try:
            data = {key: json.loads(value) for key, value in (
                line.split(": ", 1) for line in header.splitlines()
            )}
        except (ValueError, TypeError):
            return {}
        return data if data.get("generator") == GENERATOR else {}
    first = text.split("\n", 1)[0]
    if not first.startswith(MARKER) or not first.endswith(" -->"):
        return {}
    try:
        data = json.loads(first[len(MARKER):-4])
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def settings(home: Path) -> tuple[Path, str]:
    config = json.loads((home / "shared-knowledge.json").read_text(encoding="utf-8"))
    vault = Path(config["vault_path"]).expanduser().resolve()
    device = config["device"]
    if not isinstance(device, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", device):
        raise ValueError("Device must use 1-64 lowercase Latin letters, digits, '-' or '_'.")
    if not vault.is_dir():
        raise ValueError(f"Obsidian vault directory not found: {vault}")
    contained(vault, vault / FOLDER / "devices")
    return vault, device


def install(vault: Path, device: str, home: Path) -> dict:
    vault = vault.expanduser().resolve()
    if not vault.is_dir():
        raise ValueError(f"Obsidian vault directory not found: {vault}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", device):
        raise ValueError("Choose a device name using lowercase Latin letters, digits, '-' or '_'.")
    config_path = contained(home, home / "shared-knowledge.json")
    local_settings = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    if not isinstance(local_settings, dict):
        raise ValueError("Local shared-knowledge settings must be an object")
    devices = contained(vault, vault / FOLDER / "devices")
    if (devices / f"{device}.md").exists() or (devices / device).exists():
        if not config_path.exists() or settings(home) != (vault, device):
            raise ValueError(f"Device '{device}' already has a snapshot. Choose another device name.")
    source = Path(__file__).resolve().parents[1]
    destination = contained(home, home / "skills" / "codex-shared-knowledge")
    for relative in ("SKILL.md", "scripts/shared_knowledge.py", "scripts/install_export_task.ps1",
                     "tests/test_shared_knowledge.py"):
        target = contained(home, destination / relative)
        content = (source / relative).read_text(encoding="utf-8")
        if (source / relative).resolve() != target.resolve():
            atomic_write(target, content)
    agent_path = contained(home, home / "AGENTS.md")
    instructions = agent_path.read_text(encoding="utf-8") if agent_path.exists() else ""
    if AGENT_LINE not in instructions.splitlines():
        instructions = instructions.rstrip() + "\n\n" + AGENT_LINE + "\n"
    if RECALL_START in instructions:
        if RECALL_END not in instructions:
            raise ValueError("Incomplete codex-shared-recall block in AGENTS.md")
        instructions = re.sub(re.escape(RECALL_START) + r".*?" + re.escape(RECALL_END),
                              lambda _: RECALL_RULE, instructions, count=1, flags=re.S)
    else:
        instructions = instructions.rstrip() + "\n\n" + RECALL_RULE + "\n"
    if not agent_path.exists() or agent_path.read_text(encoding="utf-8") != instructions:
        atomic_write(agent_path, instructions)
    local_settings.update(vault_path=str(vault), device=device)
    if (source.parents[1] / ".git").exists() and (source.parents[1] / "pipeline").is_dir():
        local_settings["repository_path"] = str(source.parents[1].resolve())
    atomic_write(config_path, json.dumps(local_settings, ensure_ascii=False, indent=2) + "\n")
    return {"status": "installed", "skill": str(destination), "vault": str(vault), "device": device}


def install_hooks(home: Path) -> dict:
    """Merge only our export handlers; Codex retains its normal hook trust review."""
    settings(home)
    path = contained(home, home / "hooks.json")
    previous = path.read_text(encoding="utf-8") if path.exists() else "{}"
    config = json.loads(previous)
    if not isinstance(config, dict) or not isinstance(config.get("hooks", {}), dict):
        raise ValueError("hooks.json must contain a hooks object")
    hooks = config.setdefault("hooks", {})
    script = contained(home, home / "skills/codex-shared-knowledge/scripts/shared_knowledge.py")
    if not script.is_file():
        raise ValueError("Install the shared-knowledge skill before installing hooks")
    args = [sys.executable, str(script), "export", "--quiet"]
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    powershell = ("$env:CODEX_HOME = " + quote(home) + "; & "
                  + " ".join(quote(arg) for arg in args) + "; exit $LASTEXITCODE")
    windows_command = ("powershell.exe -NoProfile -NonInteractive -EncodedCommand "
                       + base64.b64encode(powershell.encode("utf-16le")).decode("ascii"))
    command = "CODEX_HOME=" + shlex.quote(str(home)) + " " + shlex.join(args)
    for event in ("Stop", "SessionEnd"):
        groups = hooks.get(event, [])
        if not isinstance(groups, list):
            raise ValueError(f"Invalid {event} hook groups")
        preserved = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise ValueError(f"Invalid {event} hook group")
            if any(not isinstance(handler, dict) for handler in group["hooks"]):
                raise ValueError(f"Invalid {event} hook handler")
            remaining = [handler for handler in group["hooks"] if handler.get("statusMessage") != EXPORT_HOOK]
            if remaining:
                preserved.append({**group, "hooks": remaining})
        handler = {"type": "command", "command": command, "commandWindows": windows_command,
                   "statusMessage": EXPORT_HOOK, "timeout": 10 if event == "Stop" else 3}
        if event == "Stop":
            handler["async"] = True
        hooks[event] = preserved + [{"hooks": [handler]}]
    updated = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
    if updated != previous:
        if path.exists():
            digest = hashlib.sha256(previous.encode("utf-8")).hexdigest()[:16]
            backup = contained(home, home / "backups/shared-knowledge-hooks" / f"{digest}.json")
            if not backup.exists():
                atomic_write(backup, previous)
        atomic_write(path, updated)
    return {"status": "configured", "file": str(path), "events": ["Stop", "SessionEnd"],
            "trust": "Review these definitions in Codex /hooks before they can run"}


class ExportBusyError(ValueError):
    """Another export already owns this profile's write lock."""


@contextmanager
def export_lock(home: Path):
    """Serialize this profile's manual and scheduled exports; release on process exit."""
    with (home / "shared-knowledge-export.lock").open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ExportBusyError("Another export is running; retry later.") from error
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def context_path(text: str, field: str) -> str:
    match = re.search(rf"\b{field}\s*[=:]\s*(?:\"([^\"\r\n]+)\"|'([^'\r\n]+)'|([^\r\n;,()]+))", text)
    if not match:
        return ""
    value = next(part for part in match.groups() if part is not None).strip()
    return re.split(r"\s+and\s+(?=(?:[A-Za-z]:[\\/]|/))", value, maxsplit=1)[0]


def split_topics(text: str) -> list[dict]:
    """Use native heading boundaries, never headings inside fenced examples."""
    headings = []
    fence = None
    offset = 0
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
        if marker:
            delimiter, rest = marker.groups()
            if fence is None:
                fence = delimiter
            elif delimiter[0] == fence[0] and len(delimiter) >= len(fence) and not rest.strip():
                fence = None
        elif fence is None:
            heading = re.match(r"^(#{1,2})[ \t]+(.+?)\s*$", line)
            if heading:
                headings.append((len(heading[1]), offset, heading[2]))
        offset += len(line)
    level = min((item[0] for item in headings), default=1)
    boundaries = [(offset, title) for depth, offset, title in headings if depth == level]
    if not boundaries or boundaries[0][0] > 0:
        boundaries.insert(0, (0, "Общие сведения"))
    items, occurrences = [], {}
    for index, (offset, heading) in enumerate(boundaries):
        end = boundaries[index + 1][0] if index + 1 < len(boundaries) else len(text)
        body = text[offset:end].strip()
        if not body:
            continue
        title = re.sub(r"^Task Group:\s*", "", heading, flags=re.I)
        if re.match(r"^#{1,2}[ \t]+", body):
            body = body.partition("\n")[2].lstrip("\n")
        body = f"# {title}\n\n{body.rstrip()}\n"
        key = heading.casefold()
        occurrences[key] = occurrences.get(key, 0) + 1
        key += f"#{occurrences[key]}"
        path = re.match(r"^(?:[A-Za-z]:[\\/]|/)[^\s]+", title)
        context = next((line for line in body.splitlines() if line.startswith("applies_to:")), "")
        project = project_name(context_path(context, "source") or context_path(context, "cwd")
                               or context_path(body, "cwd") or (path[0] if path else "general"))
        keywords = []
        for block in re.findall(r"(?ms)^###? keywords\s*\n(.*?)(?=^#{1,6} |\Z)", body):
            keywords.extend(part.strip(" \n\r\t-`") for part in re.split(r"[,;\n]", block))
        anchors = sorted(set(re.findall(
            r"\b(?:thread_id|session_id)\s*[=:]\s*([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})", body, re.I,
        )))
        items.append({"source": "MEMORY.md", "kind": "topic", "key": key, "title": title,
                      "project": project, "keywords": list(dict.fromkeys(k for k in keywords if k))[:16],
                      "anchors": anchors, "text": body + "\n"})
    return items


def load_manifest(folder: Path, device: str) -> dict:
    path = contained(folder, folder / "manifest.json")
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 2 or data.get("device") != device:
        raise ValueError(f"Unsupported or incorrect device manifest: {path}")
    if not isinstance(data.get("notes"), list):
        raise ValueError(f"Invalid notes manifest: {path}")
    seen = set()
    for note in data["notes"]:
        if not isinstance(note, dict):
            raise ValueError(f"Invalid note record: {path}")
        name, note_id = note.get("file", ""), note.get("id", "")
        valid = (name == "summary.md" and note_id == f"{device}-summary") or (
            bool(re.fullmatch(r"topic-[0-9a-f]{16}\.md", name)) and note_id == f"{device}-{name[6:-3]}"
        )
        if not valid or note_id in seen or note.get("source") not in SOURCES:
            raise ValueError(f"Invalid or duplicate note identity in {path}")
        contained(folder, folder / name)
        seen.add(note_id)
    return data


def render_note(info: dict, body: str) -> str:
    fields = {"generator": GENERATOR, "version": 2, **info}
    header = "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in fields.items())
    return f"---\n{header}\n---\n\n{body.rstrip()}\n"


def note_link(device: str, name: str, title: str) -> str:
    label = re.sub(r"[\[\]|\r\n]", " ", title).strip()
    return f"[[{FOLDER}/devices/{device}/{Path(name).stem}|{label}]]"


def backup_and_remove(home: Path, device: str, path: Path, expected_id: str | None = None) -> None:
    data = path.read_bytes()
    info = metadata(data.decode("utf-8"))
    if info.get("device") != device or (expected_id is not None and info.get("id") != expected_id):
        raise ValueError(f"Refusing to remove an unowned file: {path}")
    digest = hashlib.sha256(data).hexdigest()
    backup = contained(home, home / "backups" / "shared-knowledge" / f"{device}-{path.stem}-{digest[:16]}.md")
    if not backup.exists():
        atomic_write(backup, data.decode("utf-8"))
    if backup.read_bytes() != data or path.read_bytes() != data:
        raise ValueError(f"File changed while making its backup: {path}")
    path.unlink()


def export(home: Path) -> dict:
    vault, device = settings(home)
    with export_lock(home):
        return export_topics(home, vault, device)


def recover_topic_backups(home: Path, device: str, known: set[str]) -> tuple[list[dict], dict[str, Path]]:
    """Recover only this exporter's checksummed topic backups during the v2 upgrade."""
    folder = contained(home, home / "backups" / "shared-knowledge")
    recovered = {}
    for path in sorted(folder.glob(f"{device}-topic-*.md")):
        match = re.fullmatch(re.escape(device) + r"-(topic-([0-9a-f]{16}))-([0-9a-f]{16})\.md", path.name)
        if not match:
            continue
        note_id = f"{device}-{match[2]}"
        if note_id in known:
            continue
        contained(folder, path)
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest()[:16] != match[3]:
            raise ValueError(f"Topic backup checksum mismatch: {path}")
        text = data.decode("utf-8").replace("\r\n", "\n")
        info = metadata(text)
        if (info.get("generator") != GENERATOR or info.get("device") != device
                or info.get("id") != note_id or info.get("kind") != "topic"
                or info.get("source") != "MEMORY.md"):
            continue
        body = body_of(text)[0].lstrip("\n")
        parsed = split_topics(body)
        record = {key: info[key] for key in ("id", "source", "kind", "title", "project", "keywords",
                                             "source_updated_at", "exported_at", "content_sha256")}
        record.update({"file": match[1] + ".md", "key": f"recovered:{note_id}",
                       "anchors": sorted({anchor for topic in parsed for anchor in topic["anchors"]}),
                       "file_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                       "status": "archived", "archived_at": datetime.fromtimestamp(
                           path.stat().st_mtime, timezone.utc).isoformat()})
        previous = recovered.get(note_id)
        if previous is None or (record["source_updated_at"], record["exported_at"]) > (
                previous[0]["source_updated_at"], previous[0]["exported_at"]):
            recovered[note_id] = (record, path)
    return [record for record, _ in recovered.values()], {record["id"]: path for record, path in recovered.values()}


def export_topics(home: Path, vault: Path, device: str) -> dict:
    native = home / "memories"
    documents = {}
    stamps = {}
    for name in SOURCES:
        path = contained(native, native / name)
        if path.is_file():
            before = path.stat()
            documents[name] = path.read_text(encoding="utf-8")
            stamps[name] = before
    if not any(text.strip() for text in documents.values()):
        return {"status": "no_local_memory", "device": device}
    for name, before in stamps.items():
        after = (native / name).stat()
        if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
            raise ValueError("Native memories changed while reading. Retry export.")
    digest = hashlib.sha256(json.dumps(documents, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    devices = contained(vault, vault / FOLDER / "devices")
    folder = contained(vault, devices / device)
    previous = load_manifest(folder, device)
    prior_notes = list(previous.get("notes", []))
    recovered_paths = {}
    # An intentionally deleted export must not resurrect old backups on its next fresh install.
    if previous and not previous.get("history_imported"):
        recovered, recovered_paths = recover_topic_backups(home, device, {note["id"] for note in prior_notes})
        prior_notes += recovered
    items = split_topics(documents.get("MEMORY.md", ""))
    if documents.get("memory_summary.md", "").strip():
        items.insert(0, {"source": "memory_summary.md", "kind": "summary", "key": "summary",
                         "title": "Краткая сводка", "project": "general", "keywords": [], "anchors": [],
                         "text": f"# Краткая сводка: {device}\n\n{documents['memory_summary.md'].strip()}\n"})
    now = datetime.now(timezone.utc).isoformat()
    used, records = set(), []
    current_keys = {(item["source"], item["key"]) for item in items}
    for item in items:
        token = uuid.uuid5(uuid.NAMESPACE_URL, f"{GENERATOR}:{device}:{item['source']}:{item['key']}").hex[:16]
        preferred_id = f"{device}-summary" if item["kind"] == "summary" else f"{device}-{token}"
        old = next((note for note in prior_notes if (note["source"], note["key"]) ==
                    (item["source"], item["key"]) and note["id"] not in used), {})
        if not old:
            old = next((note for note in prior_notes if note["id"] == preferred_id and note["id"] not in used), {})
        if not old and item["anchors"]:
            candidates = [note for note in prior_notes if note["source"] == item["source"]
                          and note["id"] not in used and (note["source"], note["key"]) not in current_keys
                          and set(note.get("anchors", [])) & set(item["anchors"])
                          and sum(bool(set(note.get("anchors", [])) & set(other["anchors"])) for other in items) == 1]
            if len(candidates) == 1:
                old = candidates[0]
        note_id = old.get("id") or preferred_id
        if note_id in used:
            raise ValueError(f"Duplicate topic id: {note_id}")
        used.add(note_id)
        record = {key: value for key, value in item.items() if key != "text"}
        content_hash = hashlib.sha256(item["text"].encode("utf-8")).hexdigest()
        record.update({"id": note_id, "status": "active", "file": old.get("file") or (
            "summary.md" if item["kind"] == "summary" else f"topic-{token}.md"),
            "content_sha256": content_hash,
            "source_updated_at": old.get("source_updated_at") if old.get("content_sha256") == content_hash else
                datetime.fromtimestamp(stamps[item["source"]].st_mtime, timezone.utc).isoformat(),
            "exported_at": old.get("exported_at") if old.get("content_sha256") == content_hash else now})
        records.append(record)
    rendered = {}
    for old in prior_notes:
        if old["id"] in used or old["kind"] != "topic":
            continue
        path = contained(folder, folder / old["file"])
        source = recovered_paths.get(old["id"], path)
        try:
            entry = read_record({"file": str(source), "id": old["id"], "device": device, "sha256": old["file_sha256"]})
        except ValueError:
            # Recognize our completed archive write if the manifest commit was interrupted.
            text = source.read_text(encoding="utf-8")
            info = metadata(text)
            original = dict(info)
            original.pop("archived_at", None)
            if "status" in old:
                original["status"] = old["status"]
            else:
                original.pop("status", None)
            restored = render_note(original, body_of(text)[0].lstrip("\n"))
            if (old.get("status") == "archived" or info.get("status") != "archived"
                    or not info.get("archived_at")
                    or hashlib.sha256(restored.encode("utf-8")).hexdigest() != old["file_sha256"]):
                raise
            entry = {**info, "file": str(source), "content": text}
        body = body_of(entry.pop("content"))[0].lstrip("\n")
        entry.pop("file")
        archived_at = old.get("archived_at") or entry.get("archived_at") or now
        entry.update(status="archived", archived_at=archived_at)
        text = render_note(entry, body)
        rendered[old["file"]] = text
        records.append({**old, "status": "archived", "archived_at": archived_at,
                        "file_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()})
    for item, record in zip(items, records):
        related = [note_link(device, "index.md", "Содержание")]
        related += [note_link(device, other["file"], other["title"]) for other in records
                    if other["id"] != record["id"] and set(other["anchors"]) & set(record["anchors"])]
        info = {key: record[key] for key in ("id", "kind", "title", "project", "source", "keywords", "status",
                                            "source_updated_at", "exported_at", "content_sha256")}
        rendered[record["file"]] = render_note({"device": device, **info, "related": related}, item["text"])
        record["file_sha256"] = hashlib.sha256(rendered[record["file"]].encode("utf-8")).hexdigest()
    unchanged_source = previous.get("source_sha256") == digest
    info = {"device": device, "exported_at": previous["exported_at"] if unchanged_source else now,
            "source_sha256": digest, "source_updated_at": previous["source_updated_at"] if unchanged_source else {
                name: datetime.fromtimestamp(stamp.st_mtime, timezone.utc).isoformat() for name, stamp in stamps.items()}}
    body = f"# Общие знания Codex: {device}\n\nСправочные данные; действуют правила текущей задачи и проекта.\n"
    for project in dict.fromkeys(record["project"] for record in records):
        body += f"\n## {project}\n\n" + "\n".join(
            "- " + note_link(device, record["file"], record["title"] + (
                " (архив)" if record.get("status") == "archived" else ""))
            for record in records if record["project"] == project) + "\n"
    rendered["index.md"] = render_note({"id": f"{device}-index", "kind": "index", **info}, body)
    manifest = {"version": 2, **info, "notes": records, "history_imported": True,
                "index_sha256": hashlib.sha256(rendered["index.md"].encode("utf-8")).hexdigest()}
    legacy = contained(devices, devices / f"{device}.md")
    if legacy.exists() and metadata(legacy.read_text(encoding="utf-8")).get("device") != device:
        raise ValueError(f"Refusing to replace an unowned legacy file: {legacy}")
    for name in rendered:
        target = contained(folder, folder / name)
        if target.exists():
            existing = metadata(target.read_text(encoding="utf-8"))
            expected_id = f"{device}-index" if name == "index.md" else next(
                record["id"] for record in records if record["file"] == name)
            if existing.get("device") != device or existing.get("id") != expected_id:
                raise ValueError(f"Refusing to overwrite an unowned file: {target}")
    changed = False
    for name, text in rendered.items():
        target = contained(folder, folder / name)
        if not target.exists() or target.read_bytes() != text.encode("utf-8"):
            atomic_write(target, text)
            changed = True
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    manifest_path = contained(folder, folder / "manifest.json")
    if not manifest_path.exists() or manifest_path.read_text(encoding="utf-8") != manifest_text:
        atomic_write(manifest_path, manifest_text)
        changed = True
    removed = []
    for path in [*folder.glob("topic-*.md"), folder / "summary.md"]:
        contained(folder, path)
        if not path.is_file() or path.name in rendered:
            continue
        owned = metadata(path.read_text(encoding="utf-8"))
        expected_id = f"{device}-summary" if path.name == "summary.md" else f"{device}-{path.stem[6:]}"
        if owned.get("generator") == GENERATOR and owned.get("device") == device and owned.get("id") == expected_id:
            backup_and_remove(home, device, path, expected_id)
            removed.append(path.name)
    if legacy.exists():
        backup_and_remove(home, device, legacy)
        removed.append(legacy.name)
    return {"status": "exported" if changed or removed else "unchanged", "file": str(folder / "index.md"),
            "device": device, "sources": list(documents), "topics": sum(item["kind"] == "topic" for item in items),
            "archived_topics": sum(record.get("status") == "archived" for record in records),
            "files": [str(folder / name) for name in rendered], "removed": removed}


def project_name(value: str) -> str:
    path = PureWindowsPath(value.strip(" \"'"))
    if path.root and len(path.parts) == 3 and path.parts[-2].casefold() in ("home", "users"):
        return "general"
    return path.name.casefold().replace("_", "-") or "general"


def inventory(home: Path) -> tuple[list[dict], list[dict]]:
    """Read manifests, without opening the generated notes."""
    vault, _ = settings(home)
    folder = contained(vault, vault / FOLDER / "devices")
    entries, warnings, upgraded = [], [], set()
    for device_folder in sorted(folder.iterdir()) if folder.exists() else []:
        if not device_folder.is_dir() or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", device_folder.name):
            continue
        device = device_folder.name
        try:
            contained(vault, device_folder)
            manifest = load_manifest(device_folder, device)
            if not manifest:
                raise ValueError("Device export is incomplete: manifest is missing")
            upgraded.add(device)
            records = [*manifest["notes"], {"file": "index.md", "id": f"{device}-index",
                                         "file_sha256": manifest["index_sha256"]}]
            for record in records:
                path = contained(device_folder, device_folder / record["file"])
                entries.append({"id": record["id"], "device": device, "file": str(path),
                                "sha256": record["file_sha256"]})
        except (OSError, ValueError, KeyError, TypeError) as error:
            warnings.append({"device": device, "message": str(error)})
    for path in sorted(folder.glob("*.md")):
        if path.stem in upgraded or path.is_symlink():
            continue
        contained(folder, path)
        try:
            with path.open(encoding="utf-8") as stream:
                info = metadata(stream.readline())
        except (OSError, UnicodeError):
            continue
        if info.get("device") != path.stem or not info.get("source_sha256"):
            continue
        entries.append({"id": f"{path.stem}-legacy", "device": path.stem, "file": str(path), "sha256": None})
    return entries, warnings


def read_record(record: dict) -> dict:
    text = Path(record["file"]).read_text(encoding="utf-8")
    info = metadata(text)
    if record["sha256"] is None:
        if info.get("device") != record["device"] or not info.get("source_sha256"):
            raise ValueError("Not an owned legacy snapshot")
        info.update(id=record["id"], kind="legacy", title=record["device"], project="general")
    elif (hashlib.sha256(text.encode("utf-8")).hexdigest() != record["sha256"]
          or info.get("id") != record["id"] or info.get("device") != record["device"]):
        raise ValueError("File differs from its committed manifest; sync/export may be in progress")
    return {**info, "file": record["file"], "content": text}


def body_of(text: str) -> tuple[str, int]:
    start = text.find("\n---\n", 4) + 5 if text.startswith("---\n") else text.find("\n") + 1
    return text[start:], text[:start].count("\n")


def bounded(result: dict, max_chars: int = 6000, words: set[str] | None = None) -> dict:
    """Cap the complete JSON response, including metadata and warnings."""
    if max_chars < 800:
        raise ValueError("max_chars must be at least 800")
    result["truncated"] = result.get("truncated", False)
    warnings = result.get("warnings", [])
    if len(warnings) > 3:
        result["warning_count"] = len(warnings)
        result["warnings"] = warnings[:3]
        result["truncated"] = True
    while len(json.dumps(result, ensure_ascii=False, indent=2)) + 1 > max_chars:
        result["truncated"] = True
        group = result.get("notes", result.get("matches", []))
        if len(group) > 1:
            group.pop()
            continue
        note = group[0] if group else result.get("note", {})
        field = next((key for key in ("content", "excerpt", "snippet") if len(note.get(key, "")) > 80), None)
        if field:
            size = len(note[field]) * 2 // 3
            if field != "content" and words:
                note[field], number, _ = passage(note[field], words, size)
                note["line"] += number - 1
            else:
                note[field] = note[field][:size].rstrip() + "\n…"
            if field != "content":
                note[f"{field}_truncated"] = True
        elif group:
            group.pop()
        elif result.get("note"):
            short = {key: note[key] for key in ("id", "file") if key in note}
            result["note"] = short if short != note else {}
        elif result.get("warnings"):
            result.setdefault("warning_count", len(warnings))
            result["warnings"] = [{"message": "Incomplete shared knowledge; inspect the synced manifests."}]
        else:
            break
    return result


def read_note(home: Path, note_id: str, max_chars: int = 6000, full: bool = False) -> dict:
    entries, warnings = inventory(home)
    record = next((entry for entry in entries if entry["id"] == note_id), None)
    if record is None:
        raise ValueError(f"Shared note not found: {note_id}; sync warnings: {warnings}")
    result = {"note": read_record(record), "warnings": warnings}
    return result if full else bounded(result, max_chars)


# Small domain glossary for mixed-language memories; other phrasing is restated by the skill.
ALIASES = {
    "сертификат": ("certificate", "certificates", "tls"),
    "синхрон": ("sync", "synchronization"),
    "групп": ("group", "groups"),
    "правил": ("rule", "rules"),
    "памят": ("memory", "memories"),
    "общ": ("shared",),
    "уведомлен": ("notification", "notifications", "notice"),
    "рол": ("role", "roles"),
}
STOP_WORDS = set("a an the and or in on at of for to with from how what where about "
                 "и или в во на о об по из для с со к что как где куда было был были "
                 "это мы у меня мне было прежнее раньше решение проверка проверки "
                 "ошибка ошибки почему надо нужно сохранять сохранить токены".split())


def query_expression(query: str) -> tuple[str, set[str]]:
    if not query.strip() or len(query) > 500:
        raise ValueError("Search query must contain 1-500 characters")
    identifiers = re.findall(r"\b(?:mr\s*!?\s*\d+|pipeline\s*[:#]?\s*\d+)\b", query.casefold())
    remaining = re.sub(r"\b(?:mr\s*!?\s*\d+|pipeline\s*[:#]?\s*\d+)\b", "", query.casefold())
    terms = re.findall(r"[\w]+(?:[-.][\w]+)*", remaining)
    if not terms and not identifiers:
        raise ValueError("Search query must contain words.")
    groups, words = [], set()
    for identifier in identifiers:
        parts = re.findall(r"[a-z]+|\d+", identifier)
        groups.append('"' + " ".join(parts) + '"')
        words.update(parts)
    for term in dict.fromkeys(terms):
        if term in STOP_WORDS or len(term) == 1 or term.startswith(("проверк", "проверит", "проблем", "ошиб")):
            continue
        variants = (term,)
        for stem, aliases in ALIASES.items():
            if term.startswith(stem):
                variants += aliases
                break
        words.update(word for value in variants for word in re.findall(r"[^\W_]+", value))
        groups.append("(" + " OR ".join('"' + value.replace('"', '""') + '"' for value in variants) + ")")
    return " AND ".join(groups), words


def indexed_search(home: Path, query: str, limit: int, project: str | None) -> tuple[list[dict], list[dict], set[str]]:
    expression, words = query_expression(query)
    if not 1 <= limit <= 50:
        raise ValueError("limit must be 1-50")
    entries, warnings = inventory(home)
    cache = contained(home, home / "shared-knowledge-index.sqlite3")
    if cache.is_symlink():
        raise ValueError("The local recall index must not be a symlink")
    if not cache.exists():
        descriptor = os.open(cache, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(descriptor)
    with closing(sqlite3.connect(cache, timeout=10)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, signature TEXT, info TEXT, "
                           "project TEXT, kind TEXT, archived INTEGER NOT NULL DEFAULT 0)")
        connection.execute("CREATE VIRTUAL TABLE IF NOT EXISTS notes USING fts5(id UNINDEXED, title, keywords, body, tokenize='unicode61')")
        # Serialize refreshes from concurrent chats; only changed note contents are read.
        connection.execute("BEGIN IMMEDIATE")
        try:
            if "archived" not in {row["name"] for row in connection.execute("PRAGMA table_info(documents)")}:
                connection.execute("ALTER TABLE documents ADD COLUMN archived INTEGER NOT NULL DEFAULT 0")
            previous = {row["id"]: row["signature"] for row in connection.execute("SELECT id, signature FROM documents")}
            keep = set()
            for entry in entries:
                try:
                    stamp = Path(entry["file"]).stat()
                    signature = json.dumps([entry["file"], entry["sha256"], stamp.st_mtime_ns, stamp.st_size])
                    keep.add(entry["id"])
                    if previous.get(entry["id"]) == signature:
                        continue
                    note = read_record(entry)
                    body, note["body_offset"] = body_of(note.pop("content"))
                    connection.execute("DELETE FROM notes WHERE id = ?", (entry["id"],))
                    connection.execute("INSERT INTO notes VALUES (?, ?, ?, ?)", (
                        entry["id"], note.get("title", ""), " ".join(note.get("keywords", [])), body))
                    connection.execute("INSERT OR REPLACE INTO documents VALUES (?, ?, ?, ?, ?, ?)", (
                        entry["id"], signature, json.dumps(note, ensure_ascii=False),
                        project_name(note.get("project", "general")), note.get("kind", "legacy"),
                        int(note.get("status") == "archived")))
                except (OSError, ValueError, KeyError, TypeError) as error:
                    keep.discard(entry["id"])
                    warnings.append({"device": entry["device"], "file": entry["file"], "message": str(error)[:300]})
            for note_id in previous.keys() - keep:
                connection.execute("DELETE FROM notes WHERE id = ?", (note_id,))
                connection.execute("DELETE FROM documents WHERE id = ?", (note_id,))
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        scope = " AND d.project = ?" if project else ""
        parameters = [project_name(project)] if project else []
        exact = connection.execute(
            "SELECT d.info, notes.body, 0 AS rank FROM notes JOIN documents d ON notes.id=d.id WHERE d.id=?" + scope,
            [query.casefold(), *parameters]).fetchall()
        rows = exact or (connection.execute(
            "SELECT d.info, notes.body, bm25(notes,0,8,4,1) AS rank FROM notes JOIN documents d ON notes.id=d.id "
            "WHERE notes MATCH ? AND d.kind != 'index'" + scope + " ORDER BY d.archived, rank, d.id LIMIT ?",
            [expression, *parameters, limit * 4]).fetchall() if expression else [])
        records = {entry["id"]: entry for entry in entries}
        found, seen, checked = [], set(), 0
        for row in rows:
            body = row["body"]
            digest = hashlib.sha256(" ".join(body.split()).encode()).hexdigest()
            if digest in seen:
                continue
            if checked == limit:
                break
            cached = json.loads(row["info"])
            record = records.get(cached["id"])
            if record is None:
                warnings.append({"device": cached["device"], "file": cached["file"],
                                 "message": "Shared index changed during search; repeat the query"})
                continue
            checked += 1
            try:
                note = read_record(record)
                verified_body, note["body_offset"] = body_of(note.pop("content"))
                if verified_body != body:
                    raise ValueError("File differs from the local index; repeat the query to refresh it")
            except (OSError, ValueError, KeyError, TypeError) as error:
                warnings.append({"device": record["device"], "file": record["file"], "message": str(error)[:300]})
                connection.execute("DELETE FROM notes WHERE id = ?", (record["id"],))
                connection.execute("DELETE FROM documents WHERE id = ?", (record["id"],))
                continue
            seen.add(digest)
            found.append({**note, "body": verified_body, "score": round(-row["rank"], 6)})
            if len(found) == limit:
                break
        connection.commit()
    return found, warnings, words


def passage(body: str, words: set[str], max_chars: int) -> tuple[str, int, bool]:
    lines = body.splitlines()
    candidates, keywords, reusable = [], False, False
    for number, line in enumerate(lines):
        if line.startswith("#"):
            keywords = bool(re.match(r"^#+\s+keywords\s*$", line, re.I))
            reusable = bool(re.match(r"^##\s+(?:Reusable knowledge|Failures|Полезные решения)", line, re.I))
            continue
        if keywords or not line.strip() or line.startswith(("scope:", "applies_to:", "- rollout_summaries/")):
            continue
        score = len(words & set(re.findall(r"[^\W_]+", line.casefold())))
        candidates.append((score, reusable, -number, number))
    best = max(candidates)[3] if candidates else 0
    start = max(0, best - 2) if max_chars > 400 else best
    end = min(len(lines), best + 5) if max_chars > 400 else best + 1
    text = "\n".join(lines[start:end])
    anchors = words - STOP_WORDS
    matches = [match for match in re.finditer(r"[^\W_]+", lines[best])
               if match[0].casefold() in anchors] if lines else []
    # Prefer a specific identifier over an early short term such as TLS.
    match = max(matches, key=lambda item: len(item[0]), default=None)
    anchor = sum(len(line) + 1 for line in lines[start:best]) + (match.start() if match else 0)
    offset = min(max(0, anchor - max_chars // 3), max(0, len(text) - max_chars))
    window = text[offset:offset + max_chars]
    content_start = offset + len(window) - len(window.lstrip())
    number = start + 1 + text[:content_start].count("\n")
    return window.strip(), number, len(text) > max_chars


RESULT_FIELDS = ("id", "file", "device", "title", "project", "kind", "status", "archived_at", "exported_at", "source_updated_at")


def search(home: Path, query: str, limit: int = 3, project: str | None = None, max_chars: int = 6000) -> dict:
    entries, warnings, words = indexed_search(home, query, limit, project)
    matches = []
    for entry in entries:
        snippet, number, clipped = passage(entry["body"], words, 300)
        matches.append({**{key: entry.get(key) for key in RESULT_FIELDS},
                        "snippet": snippet, "snippet_truncated": clipped,
                        "line": entry["body_offset"] + number, "score": entry["score"]})
    return bounded({"matches": matches, "warnings": warnings,
                    "truncated": any(note["snippet_truncated"] for note in matches)}, max_chars, words)


def recall(home: Path, query: str, project: str | None = None, max_chars: int = 6000) -> dict:
    entries, warnings, words = indexed_search(home, query, 3, project)
    topics = [entry for entry in entries if entry.get("kind") != "summary"]
    notes = []
    for entry in (topics or entries)[:2]:
        excerpt, number, clipped = passage(entry["body"], words, 1400)
        notes.append({**{key: entry.get(key) for key in RESULT_FIELDS},
                      "excerpt": excerpt, "excerpt_truncated": clipped, "line": entry["body_offset"] + number})
    return bounded({"notes": notes, "warnings": warnings,
                    "truncated": any(note["excerpt_truncated"] for note in notes)}, max_chars, words)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("install", help="Install the skill and save local vault settings")
    setup.add_argument("--vault", type=Path, required=True)
    setup.add_argument("--device", required=True)
    export_command = commands.add_parser("export", help="Refresh only this device's linked topics")
    export_command.add_argument("--quiet", action="store_true", help="Suppress successful output for hooks")
    commands.add_parser("install-hooks", help="Configure export hooks without replacing other handlers")
    find = commands.add_parser("search", help="Search generated topics and older device snapshots")
    find.add_argument("query")
    find.add_argument("--limit", type=int, default=3, choices=range(1, 51), metavar="1..50")
    find.add_argument("--project", help="Restrict to a repository name or checkout path")
    find.add_argument("--max-chars", type=int, default=6000)
    retrieve = commands.add_parser("recall", help="Return up to two relevant passages within a context budget")
    retrieve.add_argument("query")
    retrieve.add_argument("--project", help="Repository name or checkout path")
    retrieve.add_argument("--max-chars", type=int, default=6000)
    read = commands.add_parser("read", help="Read one shared note by its stable id")
    read.add_argument("note_id")
    read.add_argument("--max-chars", type=int, default=6000)
    read.add_argument("--full", action="store_true", help="Explicitly return the complete note")
    args = parser.parse_args()
    try:
        home = codex_home()
        if args.command == "install":
            result = install(args.vault, args.device, home)
        elif args.command == "install-hooks":
            result = install_hooks(home)
        elif args.command == "export":
            result = export(home)
        elif args.command == "read":
            result = read_note(home, args.note_id, args.max_chars, args.full)
        elif args.command == "recall":
            result = recall(home, args.query, args.project, args.max_chars)
        else:
            result = search(home, args.query, args.limit, args.project, args.max_chars)
        if not getattr(args, "quiet", False):
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ExportBusyError as error:
        if getattr(args, "quiet", False):
            return 0
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
