"""Atomic note replacement and stale-snapshot protection; temporary vaults only."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts import vault_writer


def test_failed_copy_keeps_previous_note_and_removes_temporary_file(tmp_path: Path, monkeypatch):
    source, target = tmp_path / "staged.md", tmp_path / "existing.md"
    source.write_text("Complete new note", encoding="utf-8")
    target.write_text("Previous note", encoding="utf-8")

    def interrupted_copy(source, temporary):
        Path(temporary).write_text("Partial new note", encoding="utf-8")
        raise OSError("Interrupted copy")

    monkeypatch.setattr(vault_writer.shutil, "copy2", interrupted_copy)
    with pytest.raises(OSError, match="Interrupted"):
        vault_writer.atomic_copy_note(source, target, vault=tmp_path)
    assert target.read_text(encoding="utf-8") == "Previous note"
    assert not list(tmp_path.glob(".dataweave-*.tmp"))


def test_concurrent_change_is_kept_instead_of_overwritten(tmp_path: Path, monkeypatch):
    source, target = tmp_path / "staged.md", tmp_path / "existing.md"
    source.write_text("Prepared update", encoding="utf-8")
    target.write_text("Original note", encoding="utf-8")
    expected = {"existing.md": hashlib.sha256(target.read_bytes()).hexdigest()}
    copy = vault_writer.shutil.copy2

    def changed_during_staging(source, temporary):
        copy(source, temporary)
        target.write_text("Newer synced note", encoding="utf-8")

    monkeypatch.setattr(vault_writer.shutil, "copy2", changed_during_staging)
    with pytest.raises(ValueError, match="WIKI_SNAPSHOT_CHANGED"):
        vault_writer.atomic_copy_note(source, target, vault=tmp_path, expected=expected)
    assert target.read_text(encoding="utf-8") == "Newer synced note"
    assert not list(tmp_path.glob(".dataweave-*.tmp"))


def test_preflight_rejects_stale_snapshot_before_any_writes(tmp_path: Path, monkeypatch):
    vault, staging = tmp_path / "vault", tmp_path / "staging"
    vault.mkdir()
    staging.mkdir()
    target = vault / "existing.md"
    target.write_text("Newer note", encoding="utf-8")
    manifest = staging / "expected-state.json"
    manifest.write_text(json.dumps({"existing.md": "0" * 64}), encoding="utf-8")
    monkeypatch.setattr(vault_writer, "load_config", lambda: {"vault": {"vault_path": str(vault)}})
    monkeypatch.setattr(vault_writer, "load_registry", lambda: pytest.fail("Writer passed stale preflight"))
    monkeypatch.setattr("sys.argv", ["vault_writer", "--staging", str(staging), "--expected-state", str(manifest)])
    with pytest.raises(SystemExit) as result:
        vault_writer.main()
    assert result.value.code == 1
    assert target.read_text(encoding="utf-8") == "Newer note"


def test_snapshot_manifest_cannot_read_outside_vault(tmp_path: Path):
    with pytest.raises(ValueError, match="leaves vault"):
        vault_writer.check_expected_state(tmp_path, {"../outside.md": None})


def test_atomic_copy_replaces_matching_note(tmp_path: Path):
    source, target = tmp_path / "staged.md", tmp_path / "existing.md"
    source.write_text("New note", encoding="utf-8")
    target.write_text("Previous note", encoding="utf-8")
    expected = {"existing.md": hashlib.sha256(target.read_bytes()).hexdigest()}
    vault_writer.atomic_copy_note(source, target, vault=tmp_path, expected=expected)
    assert target.read_text(encoding="utf-8") == "New note"
    assert not list(tmp_path.glob(".dataweave-*.tmp"))


def test_compile_writer_pass_preserves_raw_and_commits_portable_log_last(tmp_path: Path, monkeypatch):
    from types import SimpleNamespace
    from scripts import wiki_compile
    from scripts.wiki_models import ChangeSet

    vault = tmp_path / "vault"
    root = vault / "LLM Wiki/demo"
    raw = root / "raw/docs/evidence.md"
    raw.parent.mkdir(parents=True)
    raw.write_text("---\nwiki_status: ingested\n---\n\nOriginal evidence", encoding="utf-8")
    snapshot = wiki_compile.snapshot_wiki_space(root)
    snapshot["wiki_folder"] = "LLM Wiki"
    batch = wiki_compile.select_raw_inputs(snapshot, since_last_compile=True, raw_only_glob=None)
    changes = ChangeSet(project="demo", compile_id="fixture")
    changes.log_entry.raws_consumed = ["raw/docs/evidence.md"]
    staging = tmp_path / "staging"
    wiki_compile._append_log_to_staging(staging, "demo", snapshot, changes, "fixture", 0, batch)
    note = staging / "pages/z-last.md"
    note.parent.mkdir()
    note.write_text('---\nnote_type: wiki\nwiki_project: demo\nwiki_page_type: core\n'
                    'source_doc: wiki:demo:core:z-last\n---\n\n# Complete note', encoding="utf-8")
    before = raw.read_bytes()
    written = []
    copy = vault_writer.atomic_copy_note

    def record_copy(source, target, **kwargs):
        copy(source, target, **kwargs)
        written.append(target.name)

    def run_writer(command, **kwargs):
        monkeypatch.setattr("sys.argv", command[1:])
        vault_writer.main()
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(vault_writer, "load_config", lambda: {"vault": {"vault_path": str(vault)}})
    monkeypatch.setattr(vault_writer, "load_registry", lambda: {})
    monkeypatch.setattr(vault_writer, "save_registry", lambda registry: None)
    monkeypatch.setattr(vault_writer, "atomic_copy_note", record_copy)
    monkeypatch.setattr(wiki_compile.subprocess, "run", run_writer)
    assert wiki_compile.write_to_vault(staging, snapshot=snapshot) == 0
    assert raw.read_bytes() == before
    assert written == ["z-last.md", "log.md"]
    assert wiki_compile.snapshot_wiki_space(root)["compiled_raws_version"] == 2
    assert wiki_compile.select_raw_inputs(
        wiki_compile.snapshot_wiki_space(root), since_last_compile=True, raw_only_glob=None) == []
