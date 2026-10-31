"""Tests for scripts/wiki_models.py — ChangeSet shape contract and helpers."""

import pytest

from scripts.wiki_models import (
    CORE_PAGES,
    META_PAGES,
    REQUIRED_FRONTMATTER,
    WIKI_CONFIDENCES,
    WIKI_MODES,
    WIKI_NOTE_TYPE,
    WIKI_PAGE_TYPES,
    WIKI_RAW_KINDS,
    WIKI_STATUSES,
    ChangeSet,
    ChangeSetShapeError,
    Contradiction,
    LogEntry,
    OpenQuestion,
    WikiPage,
    WikiPageUpdate,
    is_valid_slug,
    is_valid_wiki_source_doc,
    parse_changeset,
    synth_source_doc,
)


# ── Constants ────────────────────────────────────────────────────────────────


class TestConstants:
    def test_note_type_is_wiki(self):
        assert WIKI_NOTE_TYPE == "wiki"

    def test_page_types_cover_all_buckets(self):
        for required in ("core", "entity", "concept", "comparison", "query", "raw", "meta"):
            assert required in WIKI_PAGE_TYPES

    def test_modes(self):
        assert set(WIKI_MODES) == {"project", "corpus"}

    def test_raw_kinds(self):
        for required in ("articles", "docs", "transcripts", "assets"):
            assert required in WIKI_RAW_KINDS

    def test_core_pages_match_plan(self):
        expected = {
            "overview",
            "architecture",
            "components",
            "workflows",
            "goals-and-roadmap",
            "glossary",
            "open-questions",
        }
        assert set(CORE_PAGES) == expected

    def test_meta_pages(self):
        assert set(META_PAGES) == {"SCHEMA", "index", "log"}

    def test_required_frontmatter_includes_wiki_fields(self):
        for required in ("note_type", "wiki_project", "wiki_page_type", "wiki_status", "date"):
            assert required in REQUIRED_FRONTMATTER

    def test_confidences(self):
        assert set(WIKI_CONFIDENCES) == {"high", "medium", "low"}

    def test_statuses_cover_lifecycle(self):
        for required in ("stub", "draft", "stable", "stale", "contradicted", "ingested"):
            assert required in WIKI_STATUSES


# ── Helpers ──────────────────────────────────────────────────────────────────


class TestSlugValidation:
    @pytest.mark.parametrize(
        "value", ["a", "abc", "abc-def", "abc-123", "0name", "long-kebab-case-slug"]
    )
    def test_valid(self, value):
        assert is_valid_slug(value)

    @pytest.mark.parametrize("value", ["", "-leading", "Trailing-", "UPPER", "white space", "x_y"])
    def test_invalid(self, value):
        assert not is_valid_slug(value)


class TestSynthSourceDoc:
    def test_format(self):
        assert synth_source_doc("foo", "entity", "bar") == "wiki:foo:entity:bar"

    def test_round_trips_through_validator(self):
        sd = synth_source_doc("my-proj", "core", "overview")
        assert is_valid_wiki_source_doc(sd)

    def test_validator_rejects_non_wiki(self):
        assert not is_valid_wiki_source_doc("Some.docx")
        assert not is_valid_wiki_source_doc("wiki:foo")
        assert not is_valid_wiki_source_doc("wiki:UPPER:entity:bar")


# ── ChangeSet (de)serialization ──────────────────────────────────────────────


class TestChangeSetRoundTrip:
    def _sample_dict(self) -> dict:
        return {
            "project": "demo",
            "compile_id": "2026-05-15T10:00:00Z",
            "creates": [
                {
                    "rel_path": "entities/postgres.md",
                    "frontmatter": {
                        "note_type": "wiki",
                        "wiki_project": "demo",
                        "wiki_page_type": "entity",
                        "wiki_status": "draft",
                        "date": "2026-05-15",
                    },
                    "body": "# Postgres\n\nLinks: [[redis]].",
                    "sources": ["raw/docs/2026-05-15-design.md"],
                }
            ],
            "updates": [
                {
                    "rel_path": "pages/architecture.md",
                    "expected_existing_links": ["postgres", "redis"],
                    "frontmatter": {
                        "note_type": "wiki",
                        "wiki_project": "demo",
                        "wiki_page_type": "core",
                        "wiki_status": "stable",
                        "date": "2026-05-15",
                    },
                    "body": "# Architecture\n\n[[postgres]] feeds [[redis]].",
                    "sources": [],
                }
            ],
            "renames": [{"from": "entities/old.md", "to": "entities/new.md"}],
            "open_questions": [
                {"text": "Confirm sharding key", "raised_in": "entities/postgres.md"}
            ],
            "contradictions": [
                {"page_a": "entities/postgres.md", "page_b": "entities/redis.md", "summary": "TTL"}
            ],
            "log_entry": {
                "summary": "1 create, 1 update",
                "raws_consumed": ["raw/docs/2026-05-15-design.md"],
            },
        }

    def test_parse_then_to_dict_is_idempotent(self):
        data = self._sample_dict()
        cs = parse_changeset(data)
        assert isinstance(cs, ChangeSet)
        assert cs.project == "demo"
        assert cs.compile_id == "2026-05-15T10:00:00Z"

        roundtrip = cs.to_dict()
        # Re-parse to confirm the produced dict is itself a valid ChangeSet
        cs2 = parse_changeset(roundtrip)
        assert cs2.to_dict() == roundtrip

    def test_creates_become_wikipages(self):
        cs = parse_changeset(self._sample_dict())
        assert len(cs.creates) == 1
        assert isinstance(cs.creates[0], WikiPage)
        assert cs.creates[0].rel_path == "entities/postgres.md"

    def test_updates_carry_expected_links(self):
        cs = parse_changeset(self._sample_dict())
        assert isinstance(cs.updates[0], WikiPageUpdate)
        assert cs.updates[0].expected_existing_links == ["postgres", "redis"]

    def test_open_questions_and_contradictions(self):
        cs = parse_changeset(self._sample_dict())
        assert isinstance(cs.open_questions[0], OpenQuestion)
        assert isinstance(cs.contradictions[0], Contradiction)
        assert isinstance(cs.log_entry, LogEntry)

    def test_optional_fields_default_to_empty(self):
        minimal = {"project": "demo", "compile_id": "x"}
        cs = parse_changeset(minimal)
        assert cs.creates == []
        assert cs.updates == []
        assert cs.open_questions == []
        assert cs.contradictions == []
        assert cs.renames == []
        assert cs.log_entry.summary == ""


class TestChangeSetShapeErrors:
    def test_root_must_be_dict(self):
        with pytest.raises(ChangeSetShapeError):
            parse_changeset(["not", "a", "dict"])

    def test_missing_project(self):
        with pytest.raises(ChangeSetShapeError, match="project"):
            parse_changeset({"compile_id": "x"})

    def test_missing_compile_id(self):
        with pytest.raises(ChangeSetShapeError, match="compile_id"):
            parse_changeset({"project": "demo"})

    def test_creates_must_be_list(self):
        with pytest.raises(ChangeSetShapeError, match="creates"):
            parse_changeset({"project": "demo", "compile_id": "x", "creates": "nope"})

    def test_create_entry_missing_fields(self):
        bad = {
            "project": "demo",
            "compile_id": "x",
            "creates": [{"rel_path": "a.md"}],  # missing frontmatter and body
        }
        with pytest.raises(ChangeSetShapeError, match="creates\\[0\\]"):
            parse_changeset(bad)

    def test_update_missing_expected_existing_links(self):
        bad = {
            "project": "demo",
            "compile_id": "x",
            "updates": [{"rel_path": "a.md", "frontmatter": {}, "body": ""}],
        }
        with pytest.raises(ChangeSetShapeError, match="expected_existing_links"):
            parse_changeset(bad)

    def test_update_expected_links_must_be_list(self):
        bad = {
            "project": "demo",
            "compile_id": "x",
            "updates": [
                {
                    "rel_path": "a.md",
                    "expected_existing_links": "should-be-list",
                    "frontmatter": {},
                    "body": "",
                }
            ],
        }
        with pytest.raises(ChangeSetShapeError, match="expected_existing_links"):
            parse_changeset(bad)

    def test_frontmatter_must_be_object(self):
        bad = {
            "project": "demo",
            "compile_id": "x",
            "creates": [{"rel_path": "a.md", "frontmatter": "string", "body": ""}],
        }
        with pytest.raises(ChangeSetShapeError, match="frontmatter"):
            parse_changeset(bad)
