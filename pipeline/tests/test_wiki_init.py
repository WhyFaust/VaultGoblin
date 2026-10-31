"""Tests for scripts/wiki_init.py — pure layout creator, no LLM."""

from pathlib import Path

import pytest

from scripts.wiki_init import init_wiki_space, render_template


# ── render_template ──────────────────────────────────────────────────────────


class TestRenderTemplate:
    def test_substitutes_placeholders(self):
        text = render_template(
            "SCHEMA.template.md",
            {"slug": "demo", "title": "Demo", "mode": "project", "description": "x", "date": "2026-05-15"},
        )
        assert "{{slug}}" not in text
        assert "{{title}}" not in text
        assert "{{mode}}" not in text
        assert "demo" in text
        assert "Demo" in text
        assert "project" in text

    def test_log_template_seeds_init_row(self):
        text = render_template(
            "log.template.md",
            {"slug": "demo", "title": "Demo", "mode": "corpus", "description": "", "date": "2026-05-15"},
        )
        assert "init" in text
        assert "corpus" in text


# ── init_wiki_space — project mode ───────────────────────────────────────────


class TestInitProjectMode:
    @pytest.fixture
    def root(self, tmp_path: Path) -> Path:
        target = tmp_path / "demo"
        init_wiki_space(
            root=target,
            slug="demo",
            mode="project",
            title="Demo Project",
            description="An example wiki-space for tests.",
            force=False,
        )
        return target

    def test_meta_files_created(self, root: Path):
        assert (root / "SCHEMA.md").is_file()
        assert (root / "index.md").is_file()
        assert (root / "log.md").is_file()

    def test_core_pages_created(self, root: Path):
        for core in (
            "overview",
            "architecture",
            "components",
            "workflows",
            "goals-and-roadmap",
            "glossary",
            "open-questions",
        ):
            assert (root / "pages" / f"{core}.md").is_file(), f"missing {core}"

    def test_bucket_dirs_created(self, root: Path):
        for d in ("entities", "concepts", "comparisons", "queries"):
            assert (root / d).is_dir()
            assert (root / d / ".gitkeep").is_file()

    def test_raw_layout(self, root: Path):
        assert (root / "raw").is_dir()
        assert (root / "raw" / "_README.md").is_file()
        for kind in ("articles", "docs", "transcripts", "assets"):
            assert (root / "raw" / kind).is_dir()
            assert (root / "raw" / kind / ".gitkeep").is_file()

    def test_schema_carries_slug_and_mode(self, root: Path):
        text = (root / "SCHEMA.md").read_text(encoding="utf-8")
        assert "wiki_project: demo" in text
        assert "wiki_mode: project" in text

    def test_overview_uses_provided_description(self, root: Path):
        text = (root / "pages" / "overview.md").read_text(encoding="utf-8")
        assert "An example wiki-space for tests." in text


# ── init_wiki_space — corpus mode ────────────────────────────────────────────


class TestInitCorpusMode:
    def test_no_core_pages(self, tmp_path: Path):
        target = tmp_path / "library"
        init_wiki_space(
            root=target,
            slug="library",
            mode="corpus",
            title="Reading Library",
            description="",
            force=False,
        )
        assert not (target / "pages").exists()
        # Meta still required
        assert (target / "SCHEMA.md").is_file()
        # Bucket dirs still created
        assert (target / "entities").is_dir()

    def test_schema_records_corpus_mode(self, tmp_path: Path):
        target = tmp_path / "library"
        init_wiki_space(
            root=target, slug="library", mode="corpus", title="L", description="", force=False
        )
        text = (target / "SCHEMA.md").read_text(encoding="utf-8")
        assert "wiki_mode: corpus" in text


# ── Refusal & --force ────────────────────────────────────────────────────────


class TestRefusal:
    def test_refuses_when_root_exists(self, tmp_path: Path):
        target = tmp_path / "demo"
        target.mkdir()
        with pytest.raises(FileExistsError):
            init_wiki_space(
                root=target, slug="demo", mode="project", title="x", description="", force=False
            )

    def test_force_overwrites_meta(self, tmp_path: Path):
        target = tmp_path / "demo"
        init_wiki_space(target, "demo", "project", "First", "first run", force=False)

        # Add a custom file the script doesn't own — must survive --force.
        custom = target / "entities" / "user-edit.md"
        custom.write_text("---\nfoo: bar\n---\nuser content\n", encoding="utf-8")

        init_wiki_space(target, "demo", "project", "Second", "second run", force=True)

        assert custom.exists(), "user files outside template set must survive --force"
        schema = (target / "SCHEMA.md").read_text(encoding="utf-8")
        assert "Second" in schema


# ── Language selection ──────────────────────────────────────────────────────


class TestLangSelection:
    def test_default_lang_is_english(self, tmp_path: Path):
        target = tmp_path / "demo"
        init_wiki_space(target, "demo", "project", "Demo", "desc", force=False)
        schema = (target / "SCHEMA.md").read_text(encoding="utf-8")
        # English templates open with "frozen contract"
        assert "frozen contract" in schema

    def test_lang_ru_uses_russian_templates(self, tmp_path: Path):
        target = tmp_path / "demo"
        init_wiki_space(target, "demo", "project", "Demo", "desc", force=False, lang="ru")
        schema = (target / "SCHEMA.md").read_text(encoding="utf-8")
        # Russian templates open with "замороженный контракт"
        assert "замороженный контракт" in schema
        log = (target / "log.md").read_text(encoding="utf-8")
        assert "Журнал" in log
        index = (target / "index.md").read_text(encoding="utf-8")
        assert "Индекс" in index
        # Core stub uses Russian heading
        overview = (target / "pages" / "overview.md").read_text(encoding="utf-8")
        assert "# Обзор" in overview

    def test_lang_ru_corpus_uses_russian_placeholder(self, tmp_path: Path):
        target = tmp_path / "library"
        init_wiki_space(target, "library", "corpus", "L", "", force=False, lang="ru")
        index = (target / "index.md").read_text(encoding="utf-8")
        assert "режим corpus" in index

    def test_unsupported_lang_rejected(self, tmp_path: Path):
        target = tmp_path / "demo"
        with pytest.raises(ValueError, match="unsupported lang"):
            init_wiki_space(target, "demo", "project", "x", "", force=False, lang="de")
