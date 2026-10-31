import json
import hashlib
from pathlib import Path

import pytest

from scripts import (
    atomize, audit_vault, dedup_vault, generate_notes, process_contacts, process_note,
    vault_writer, wiki_compile, wiki_ingest, wiki_init,
    wiki_lint,
)


def config_for(vault, staging):
    return {"vault": {"vault_path": str(vault), "notes_folder": "Notes", "moc_folder": "MOCs"},
            "rclone": {"staging_dir": str(staging)}, "memory": {"enabled": False}}


def note(title, *, source="source.docx", kind="atomic"):
    return {"id": title, "title": title, "note_type": kind, "tags": ["tech/tools", "tech/ai"],
            "date": "2026-10-31", "source_doc": source, "body": "# " + title + "\n\nContent."}


@pytest.mark.parametrize("kind", ["atomic", "moc"])
@pytest.mark.parametrize("policy", ["skip", "overwrite"])
def test_existing_destination_obeys_conflict_policy(tmp_path, monkeypatch, kind, policy):
    vault, staging = tmp_path / "vault", tmp_path / "staging"
    staging.mkdir()
    cfg = config_for(vault, staging)
    folder = vault / ("MOCs" if kind == "moc" else "Notes")
    folder.mkdir(parents=True)
    target = folder / "Common.md"
    original = generate_notes.render_note_md(note("Common", source="first.docx", kind=kind))
    target.write_text(original, encoding="utf-8")
    incoming = generate_notes.render_note_md(note("Common", source="second.docx", kind=kind))
    (staging / "Common.md").write_text(incoming, encoding="utf-8")
    monkeypatch.setattr(vault_writer, "load_config", lambda: cfg)
    monkeypatch.setattr(vault_writer, "load_registry", lambda: {})
    monkeypatch.setattr(vault_writer, "save_registry", lambda _: None)
    monkeypatch.setattr("sys.argv", ["writer", "--staging", str(staging), "--non-interactive", "--on-conflict", policy])
    vault_writer.main()
    assert target.read_text(encoding="utf-8") == (original if policy == "skip" else incoming)


def test_atomizing_cannot_replace_and_archive_its_own_output(tmp_path):
    vault = tmp_path / "vault"
    original = vault / "Notes/Original.md"
    original.parent.mkdir(parents=True)
    original.write_text("Original meaning", encoding="utf-8")
    result = {"notes": [note("Original"), note("Overview", kind="moc")]}
    assert atomize.validate_atom_plan(result) == []
    with pytest.raises(ValueError, match="replace its original"):
        process_note.write_atomize_result(result, original, config_for(vault, tmp_path / "staging"))
    assert original.read_text(encoding="utf-8") == "Original meaning"
    assert not (vault / ".archive").exists()
    assert not (tmp_path / "staging").exists()


@pytest.mark.parametrize("query_type", ["relative", "absolute"])
def test_personal_processing_cannot_edit_outside_vault(tmp_path, query_type):
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("Untouched", encoding="utf-8")
    cfg = config_for(vault, tmp_path / "staging")
    query = "../outside.md" if query_type == "relative" else str(outside)
    with pytest.raises(ValueError, match="leaves the configured vault"):
        process_note.find_note(query, cfg)
    with pytest.raises(ValueError, match="leaves the configured vault"):
        process_note.write_enrich_result({"note": note("Changed")}, outside, cfg)
    assert outside.read_text(encoding="utf-8") == "Untouched"


@pytest.mark.parametrize("titles", [("A:B", "A?B"), ("Alpha", "alpha")])
@pytest.mark.parametrize("processor", ["document", "personal", "contacts"])
def test_all_note_generators_reject_filename_collisions_before_writing(tmp_path, monkeypatch, titles, processor):
    vault = tmp_path / "vault"
    vault.mkdir()
    original = vault / "Original.md"
    original.write_text("Original", encoding="utf-8")
    staging = tmp_path / "staging"
    cfg = config_for(vault, staging)
    notes = [note(title) for title in titles] + [note("Overview", kind="moc")]
    plan = {"notes": notes}
    assert atomize.validate_atom_plan(plan) == []
    with pytest.raises(ValueError, match="same filename"):
        if processor == "document":
            source = tmp_path / "plan.json"
            source.write_text(json.dumps(plan), encoding="utf-8")
            monkeypatch.setattr("sys.argv", ["generate", str(source)])
            monkeypatch.setattr(generate_notes, "load_config", lambda: cfg)
            generate_notes.main()
        elif processor == "personal":
            process_note.write_atomize_result(plan, original, cfg)
        else:
            contacts = [{**item, "note_type": "contact"} for item in notes[:2]]
            process_contacts.write_contacts_result({"contacts": contacts, "moc": notes[-1]}, original, cfg)
    assert not staging.exists()
    assert original.read_text(encoding="utf-8") == "Original"


@pytest.mark.parametrize("source", [r"C:\Users\name\source.md", 'https://example.com/"quoted"?x=1', "line1\nline2"])
def test_raw_source_yaml_roundtrips(source):
    text = wiki_ingest._build_raw_frontmatter("demo", "source", source, "2026-10-31")
    fm, _ = vault_writer.split_frontmatter(text + "Body")
    assert fm["raw_source"] == source
    assert fm["note_type"] == "wiki"
    generated = generate_notes.render_note_md(note("Example", source=source))
    fm, _ = vault_writer.split_frontmatter(generated)
    assert fm["source_doc"] == source


@pytest.mark.parametrize("module,args", [
    (wiki_init, ["demo", "--mode", "corpus"]),
    (wiki_ingest, ["demo", "source.md", "--no-compile"]),
    (wiki_compile, ["demo", "--dry-run"]),
    (wiki_lint, ["demo", "--json"]),
])
@pytest.mark.parametrize("folder", ["../outside", "/outside", r"nested\outside"])
def test_wiki_commands_reject_unsafe_roots_before_io(tmp_path, monkeypatch, module, args, folder):
    vault = tmp_path / "vault"
    vault.mkdir()
    cfg = config_for(vault, tmp_path / "staging")
    cfg["wiki"] = {"wiki_folder": folder}
    monkeypatch.setattr(module, "_load_config", lambda **_: cfg)
    monkeypatch.setattr("sys.argv", ["wiki"] + args)
    assert module.main() == 1
    assert not list(vault.iterdir())
    assert not (tmp_path / "outside").exists()


@pytest.mark.parametrize("wiki_folder", ["LLM Wiki", "Custom Wiki"])
def test_maintenance_excludes_wiki_and_shared_exports(tmp_path, wiki_folder):
    files = {
        "LLM Wiki/demo/raw/docs/one.md": "---\nnote_type: wiki\n---\n[[Old]] evidence",
        "LLM Wiki/demo/raw/docs/two.md": "---\nnote_type: wiki\n---\n[[Old]] evidence",
        "LLM Wiki/demo/SCHEMA.md": "---\nnote_type: wiki\n---\n[[Old]] contract",
        "Codex Knowledge/devices/pc/topic.md": '---\ngenerator: "codex-shared-knowledge"\n---\n[[Old]] export',
        "Notes/Regular.md": "---\nnote_type: atomic\n---\n[[Old]] regular note",
    }
    files = {path.replace("LLM Wiki", wiki_folder): text for path, text in files.items()}
    for relative, text in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    assert [item.title for item in dedup_vault.deep_scan_vault(tmp_path, wiki_folder=wiki_folder)] == ["Regular"]
    assert [item.title for item in audit_vault.iter_notes(tmp_path, wiki_folder=wiki_folder)] == ["Regular"]
    assert dedup_vault.update_wikilinks(tmp_path, {"Old": "New"}, wiki_folder=wiki_folder) == 1
    for relative, text in files.items():
        expected = text.replace("[[Old]]", "[[New]]") if relative.startswith("Notes/") else text
        assert (tmp_path / relative).read_text(encoding="utf-8") == expected


def test_merge_rejects_protected_notes_and_unrelated_existing_target(tmp_path):
    vault = tmp_path / "vault"
    raw = vault / "LLM Wiki/demo/raw/docs/source.md"
    raw.parent.mkdir(parents=True)
    raw.write_text("---\nnote_type: wiki\n---\nEvidence", encoding="utf-8")
    raw_note = dedup_vault.VaultNote(raw, "Source", "Evidence", [], "wiki", "wiki:demo:raw:source", 1)
    group = dedup_vault.CandidateGroup(1, [raw_note], [], canonical_title="Merged", canonical_body="Body")
    with pytest.raises(ValueError, match="Cannot merge Wiki"):
        dedup_vault.execute_merge(group, config_for(vault, tmp_path / "staging"), vault)
    assert raw.read_text(encoding="utf-8").endswith("Evidence")
    assert not (vault / ".archive").exists()
    source = vault / "Notes/Source.md"
    source.parent.mkdir()
    source.write_text("---\nnote_type: atomic\n---\nSource", encoding="utf-8")
    target = source.parent / "Merged.md"
    target.write_text("Unrelated note", encoding="utf-8")
    group.notes = [dedup_vault.VaultNote(source, "Source", "Source", [], "atomic", "source", 1)]
    with pytest.raises(ValueError, match="outside the merge group"):
        dedup_vault.execute_merge(group, config_for(vault, tmp_path / "staging"), vault)
    assert source.exists()
    assert target.read_text(encoding="utf-8") == "Unrelated note"


def test_tilde_vault_is_consistent_for_search_write_and_snapshot(tmp_path, monkeypatch):
    profile = tmp_path / "profile"
    vault = profile / "vault"
    source = vault / "Notes/Original.md"
    source.parent.mkdir(parents=True)
    source.write_text("Previous", encoding="utf-8")
    monkeypatch.setenv("USERPROFILE", str(profile))
    monkeypatch.setenv("HOME", str(profile))
    cfg = config_for(Path("~/vault"), tmp_path / "staging")
    found = process_note.find_note("Original", cfg)
    assert found == source
    monkeypatch.setattr(process_note, "load_registry", lambda: {})
    monkeypatch.setattr(process_note, "save_registry", lambda _: None)
    process_note.write_enrich_result({"note": note("Original")}, found, cfg)
    assert "Content." in source.read_text(encoding="utf-8")
    fingerprint = hashlib.sha256(source.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    vault_writer.check_expected_state(Path("~/vault"), {"Notes/Original.md": fingerprint})
    staged = tmp_path / "staged.md"
    staged.write_text("Next version", encoding="utf-8")
    vault_writer.atomic_copy_note(staged, Path("~/vault/Notes/Original.md"), vault=Path("~/vault"),
                                  expected={"Notes/Original.md": fingerprint})
    assert source.read_text(encoding="utf-8") == "Next version"


def test_writer_rejects_bad_destination_before_creating_folders(tmp_path, monkeypatch):
    vault, staging = tmp_path / "vault", tmp_path / "staging"
    vault.mkdir()
    staging.mkdir()
    staged = staging / "Document.md"
    staged.write_text(generate_notes.render_note_md(note("Document")), encoding="utf-8")
    cfg = config_for(vault, staging)
    cfg["vault"]["notes_folder"] = "../outside"
    monkeypatch.setattr(vault_writer, "load_config", lambda: cfg)
    monkeypatch.setattr(vault_writer, "load_registry", lambda: {})
    monkeypatch.setattr("sys.argv", ["writer", "--staging", str(staging), "--non-interactive"])
    with pytest.raises(SystemExit) as result:
        vault_writer.main()
    assert result.value.code == 1
    assert not (tmp_path / "outside").exists()
    with pytest.raises(ValueError, match="leaves the configured vault"):
        vault_writer.atomic_copy_note(staged, tmp_path / "outside.md", vault=vault)
    assert not (tmp_path / "outside.md").exists()
