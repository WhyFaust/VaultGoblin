"""Tests for vault_writer routing of note_type=wiki via _wiki_dest."""

from pathlib import Path

import pytest

from scripts.vault_writer import _wiki_dest, get_vault_dest


@pytest.fixture
def cfg(tmp_path: Path) -> dict:
    """Minimal config dict that satisfies the wiki routing path."""
    return {
        "vault": {
            "vault_path": str(tmp_path),
            "notes_folder": "Notes",
            "moc_folder": "MOC",
            "source_folder": "Sources",
            "contacts_folder": "Networking",
        },
        "wiki": {"wiki_folder": "LLM Wiki"},
    }


# ── happy path: each wiki_page_type lands in the right bucket ────────────────


@pytest.mark.parametrize(
    "page_type, expected_subdir",
    [
        ("core", "pages"),
        ("entity", "entities"),
        ("concept", "concepts"),
        ("comparison", "comparisons"),
        ("query", "queries"),
        ("readout", "readouts"),
    ],
)
def test_routing_by_page_type(cfg: dict, page_type: str, expected_subdir: str) -> None:
    fm = {"wiki_project": "demo", "wiki_page_type": page_type}
    dest = _wiki_dest(cfg, fm)
    assert dest == Path(cfg["vault"]["vault_path"]) / "LLM Wiki" / "demo" / expected_subdir


def test_meta_routes_to_space_root(cfg: dict) -> None:
    fm = {"wiki_project": "demo", "wiki_page_type": "meta"}
    dest = _wiki_dest(cfg, fm)
    assert dest == Path(cfg["vault"]["vault_path"]) / "LLM Wiki" / "demo"


def test_raw_routes_under_kind(cfg: dict) -> None:
    fm = {"wiki_project": "demo", "wiki_page_type": "raw", "raw_kind": "articles"}
    dest = _wiki_dest(cfg, fm)
    assert dest == Path(cfg["vault"]["vault_path"]) / "LLM Wiki" / "demo" / "raw" / "articles"


def test_raw_defaults_to_docs(cfg: dict) -> None:
    """When raw_kind is omitted the implementation falls back to 'docs'."""
    fm = {"wiki_project": "demo", "wiki_page_type": "raw"}
    dest = _wiki_dest(cfg, fm)
    assert dest == Path(cfg["vault"]["vault_path"]) / "LLM Wiki" / "demo" / "raw" / "docs"


def test_get_vault_dest_dispatches_to_wiki(cfg: dict) -> None:
    fm = {"wiki_project": "demo", "wiki_page_type": "entity"}
    assert get_vault_dest("wiki", cfg, frontmatter=fm) == _wiki_dest(cfg, fm)


def test_get_vault_dest_back_compat_no_frontmatter(cfg: dict) -> None:
    """Existing callers that omit frontmatter must keep working for non-wiki types."""
    assert get_vault_dest("atomic", cfg) == Path(cfg["vault"]["vault_path"]) / "Notes"
    assert get_vault_dest("moc", cfg) == Path(cfg["vault"]["vault_path"]) / "MOC"
    assert get_vault_dest("source", cfg) == Path(cfg["vault"]["vault_path"]) / "Sources"
    assert get_vault_dest("contact", cfg) == Path(cfg["vault"]["vault_path"]) / "Networking"


def test_get_vault_dest_wiki_folder_default(tmp_path: Path) -> None:
    """If [wiki] section is absent, default folder name 'LLM Wiki' is used."""
    cfg = {
        "vault": {
            "vault_path": str(tmp_path),
            "notes_folder": "Notes",
            "moc_folder": "MOC",
            "source_folder": "Sources",
            "contacts_folder": "Networking",
        }
    }
    fm = {"wiki_project": "demo", "wiki_page_type": "entity"}
    dest = get_vault_dest("wiki", cfg, frontmatter=fm)
    assert dest == tmp_path / "LLM Wiki" / "demo" / "entities"


# ── error paths ──────────────────────────────────────────────────────────────


def test_missing_wiki_project_raises(cfg: dict) -> None:
    with pytest.raises(ValueError, match="wiki_project"):
        _wiki_dest(cfg, {"wiki_page_type": "entity"})


def test_invalid_project_slug_raises(cfg: dict) -> None:
    with pytest.raises(ValueError, match="wiki_project"):
        _wiki_dest(cfg, {"wiki_project": "Has Space", "wiki_page_type": "entity"})


def test_missing_wiki_page_type_raises(cfg: dict) -> None:
    with pytest.raises(ValueError, match="wiki_page_type"):
        _wiki_dest(cfg, {"wiki_project": "demo"})


def test_invalid_wiki_page_type_raises(cfg: dict) -> None:
    with pytest.raises(ValueError, match="wiki_page_type"):
        _wiki_dest(cfg, {"wiki_project": "demo", "wiki_page_type": "bogus"})


def test_raw_with_invalid_kind_raises(cfg: dict) -> None:
    with pytest.raises(ValueError, match="raw_kind"):
        _wiki_dest(cfg, {"wiki_project": "demo", "wiki_page_type": "raw", "raw_kind": "weird"})


@pytest.mark.parametrize(
    "bad_folder",
    ["", "   ", "..", "../escape", "/abs/path", "a/b", "Knowledge/Wiki"],
)
def test_unsafe_wiki_folder_raises(cfg: dict, bad_folder: str) -> None:
    """wiki_folder is joined into vault_path — traversal/absolute/nested rejected."""
    cfg["wiki"]["wiki_folder"] = bad_folder
    with pytest.raises(ValueError, match="wiki_folder"):
        _wiki_dest(cfg, {"wiki_project": "demo", "wiki_page_type": "entity"})


def test_wiki_folder_with_space_is_allowed(cfg: dict) -> None:
    """A single-segment name with spaces (the default 'LLM Wiki') stays valid."""
    cfg["wiki"]["wiki_folder"] = "My Wiki"
    dest = _wiki_dest(cfg, {"wiki_project": "demo", "wiki_page_type": "entity"})
    assert dest == Path(cfg["vault"]["vault_path"]) / "My Wiki" / "demo" / "entities"
