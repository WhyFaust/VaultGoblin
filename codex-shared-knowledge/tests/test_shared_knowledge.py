import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "shared_knowledge.py"
spec = importlib.util.spec_from_file_location("shared_knowledge", SCRIPT)
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)


class SharedKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.vault = self.root / "Vault with spaces"
        self.vault.mkdir()
        self.home = self.root / "first-codex"
        self.home.mkdir()
        self.native = self.home / "memories"
        self.native.mkdir()
        (self.native / "memory_summary.md").write_text("Общее решение: использовать SQLite.\n", encoding="utf-8")
        (self.native / "MEMORY.md").write_text("Проверить проект перед изменением.\n", encoding="utf-8")
        self.configure(self.home, "first-pc")

    def configure(self, home, device):
        home.mkdir(exist_ok=True)
        (home / "shared-knowledge.json").write_text(
            json.dumps({"vault_path": str(self.vault), "device": device}), encoding="utf-8"
        )

    def test_export_allowlist_preserves_native_and_other_devices(self):
        (self.native / "raw_memories.md").write_text("not for export", encoding="utf-8")
        (self.home / "auth.json").write_text("not for export", encoding="utf-8")
        devices = self.vault / shared.FOLDER / "devices"
        devices.mkdir(parents=True)
        other = devices / "other-pc.md"
        other.write_text("Other computer knowledge", encoding="utf-8")
        before = {p.name: p.read_bytes() for p in self.native.iterdir()}
        result = shared.export(self.home)
        text = "\n".join(Path(path).read_text(encoding="utf-8") for path in result["files"])
        self.assertEqual(result["status"], "exported")
        self.assertIn("Общее решение", text)
        self.assertNotIn("not for export", text)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.native.iterdir()})
        self.assertEqual(other.read_text(encoding="utf-8"), "Other computer knowledge")
        self.assertEqual(set(shared.metadata(Path(result["file"]).read_text(encoding="utf-8"))["source_updated_at"]),
                         set(shared.SOURCES))

    def test_unchanged_export_does_not_rewrite_and_updates_on_change(self):
        target = Path(shared.export(self.home)["file"])
        before = target.read_bytes(), target.stat().st_mtime_ns
        self.assertEqual(shared.export(self.home)["status"], "unchanged")
        self.assertEqual(before, (target.read_bytes(), target.stat().st_mtime_ns))
        (self.native / "MEMORY.md").write_text("New durable fact", encoding="utf-8")
        result = shared.export(self.home)
        self.assertEqual(result["status"], "exported")
        self.assertTrue(any("New durable fact" in Path(path).read_text(encoding="utf-8") for path in result["files"]))

    def test_second_device_reads_shared_knowledge_without_native_memory(self):
        shared.export(self.home)
        second = self.root / "second-codex"
        self.configure(second, "second-pc")
        self.assertEqual(shared.export(second)["status"], "no_local_memory")
        matches = shared.search(second, "SQLITE")["matches"]
        self.assertTrue(matches)
        self.assertEqual(matches[0]["device"], "first-pc")
        line = Path(matches[0]["file"]).read_text(encoding="utf-8").splitlines()[matches[0]["line"] - 1]
        self.assertIn("SQLite", line)
        self.assertIsNotNone(matches[0]["exported_at"])

    def test_invalid_device_cannot_escape_shared_folder(self):
        self.configure(self.home, "../outside")
        with self.assertRaises(ValueError):
            shared.export(self.home)
        self.assertFalse((self.vault / shared.FOLDER).exists())

    def test_install_is_idempotent_and_preserves_other_instructions(self):
        home = self.root / "new-codex"
        home.mkdir()
        agents = home / "AGENTS.md"
        agents.write_text("# Existing project rules\nKeep this.\n", encoding="utf-8")
        for _ in range(2):
            shared.install(self.vault, "new-pc", home)
        self.assertTrue((home / "skills/codex-shared-knowledge/scripts/shared_knowledge.py").is_file())
        self.assertTrue((home / "skills/codex-shared-knowledge/scripts/install_export_task.ps1").is_file())
        self.assertIn("Keep this.", agents.read_text(encoding="utf-8"))
        self.assertEqual(agents.read_text(encoding="utf-8").count(shared.AGENT_LINE), 1)
        self.assertEqual(shared.settings(home), (self.vault.resolve(), "new-pc"))

    def test_install_rejects_another_devices_name(self):
        shared.export(self.home)
        with self.assertRaisesRegex(ValueError, "already has a snapshot"):
            shared.install(self.vault, "first-pc", self.root / "other-codex")
        self.assertTrue((self.vault / shared.FOLDER / "devices/first-pc/manifest.json").is_file())

    def test_empty_native_memory_does_not_erase_last_snapshot(self):
        target = Path(shared.export(self.home)["file"])
        before = target.read_bytes()
        for name in shared.SOURCES:
            (self.native / name).unlink()
        self.assertEqual(shared.export(self.home)["status"], "no_local_memory")
        self.assertEqual(target.read_bytes(), before)

    def test_modified_generated_snapshot_is_restored_from_native_memory(self):
        target = Path(shared.export(self.home)["file"])
        target.write_text(target.read_text(encoding="utf-8") + "Altered export", encoding="utf-8")
        self.assertEqual(shared.export(self.home)["status"], "exported")
        self.assertNotIn("Altered export", target.read_text(encoding="utf-8"))

    def write_topics(self, first_title="Alpha", first_body="First useful fact", second=True):
        text = (f"# Task Group: {first_title}\n\nscope: First topic\n\n"
                "### rollout_summary_files\n\n"
                "- rollout_summaries/first.md (thread_id=11111111-1111-1111-1111-111111111111)\n\n"
                f"### keywords\n\n- alpha, database\n\n## Reusable knowledge\n\n{first_body}\n")
        if second:
            text += ("\n# Task Group: Beta\n\nscope: Second topic\n\n"
                     "### keywords\n\n- beta, cache\n\n## Reusable knowledge\n\nSecond useful fact\n")
        (self.native / "MEMORY.md").write_text(text, encoding="utf-8")

    def manifest(self):
        return json.loads((self.vault / shared.FOLDER / "devices/first-pc/manifest.json").read_text(encoding="utf-8"))

    def test_stable_ids_survive_text_changes_and_recognized_rename(self):
        self.write_topics()
        shared.export(self.home)
        before = self.manifest()
        first = next(note for note in before["notes"] if note["title"] == "Alpha")
        other = next(note for note in before["notes"] if note["title"] == "Beta")
        path = self.vault / shared.FOLDER / "devices/first-pc" / other["file"]
        unchanged = path.read_bytes(), path.stat().st_mtime_ns
        self.write_topics("Alpha renamed", "Updated useful fact")
        shared.export(self.home)
        after = next(note for note in self.manifest()["notes"] if note["title"] == "Alpha renamed")
        self.assertEqual((after["id"], after["file"]), (first["id"], first["file"]))
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), unchanged)
        result = shared.read_note(self.home, first["id"])["note"]
        self.assertIn("Updated useful fact", result["content"])
        self.assertFalse(result["content"].endswith("First useful fact\n"))

    def test_each_exported_wikilink_resolves(self):
        self.write_topics()
        result = shared.export(self.home)
        for file in result["files"]:
            text = Path(file).read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"))
            self.assertTrue(shared.metadata(text).get("id"))
            for target in re.findall(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", text):
                self.assertTrue((self.vault / (target + ".md")).is_file(), target)

    def test_fenced_headings_do_not_create_topics(self):
        text = "# First\n\n```python\n# Example comment\n```\n\n# Second\n\nAnother fact\n"
        topics = shared.split_topics(text)
        self.assertEqual([topic["title"] for topic in topics], ["First", "Second"])
        self.assertIn("# Example comment", topics[0]["text"])

    def test_reordering_topics_keeps_ids_and_links_shared_sources_only(self):
        self.write_topics()
        native = self.native / "MEMORY.md"
        text = native.read_text(encoding="utf-8")
        boundary = text.index("# Task Group: Beta")
        shared.export(self.home)
        before = {note["title"]: note["id"] for note in self.manifest()["notes"]}
        native.write_text(text[boundary:] + "\n" + text[:boundary], encoding="utf-8")
        shared.export(self.home)
        after = {note["title"]: note["id"] for note in self.manifest()["notes"]}
        self.assertEqual(before, after)
        text = native.read_text(encoding="utf-8").replace("scope: Second topic", (
            "scope: Second topic\nthread_id=11111111-1111-1111-1111-111111111111"))
        native.write_text(text, encoding="utf-8")
        shared.export(self.home)
        alpha = shared.read_note(self.home, before["Alpha"])["note"]
        self.assertEqual(len(alpha["related"]), 2)  # index and a topic with the same real source

    def test_id_search_returns_a_readable_nonempty_snippet(self):
        shared.export(self.home)
        note_id = self.manifest()["notes"][0]["id"]
        result = shared.search(self.home, note_id)["matches"]
        self.assertEqual(result[0]["id"], note_id)
        self.assertTrue(result[0]["snippet"].strip())

    def test_one_search_result_per_note_and_read_by_id_from_second_profile(self):
        self.write_topics(first_body="SQLite database\nSQLite database\nSQLite database")
        shared.export(self.home)
        second = self.root / "second-codex"
        self.configure(second, "second-pc")
        matches = shared.search(second, "SQLite")["matches"]
        self.assertEqual(len(matches), 2)  # summary and one topic, never three duplicate lines
        topic = next(match for match in matches if match["kind"] == "topic")
        found = shared.read_note(second, topic["id"])["note"]
        self.assertEqual(found["device"], "first-pc")
        self.assertIn("SQLite database", found["content"])

    def test_search_stays_inside_generated_device_layer(self):
        shared.export(self.home)
        (self.vault / "personal.md").write_text("UnrelatedUniqueSecret", encoding="utf-8")
        (self.vault / shared.FOLDER / "devices/first-pc/manual.md").write_text("UnrelatedUniqueSecret", encoding="utf-8")
        self.assertEqual(shared.search(self.home, "UnrelatedUniqueSecret")["matches"], [])

    def test_legacy_export_is_backed_up_and_only_own_file_is_migrated(self):
        devices = self.vault / shared.FOLDER / "devices"
        devices.mkdir(parents=True)
        info = {"device": "first-pc", "source_sha256": "f" * 64}
        old = shared.MARKER + json.dumps(info) + " -->\n\nOld knowledge\n"
        legacy = devices / "first-pc.md"
        legacy.write_text(old, encoding="utf-8")
        info["device"] = "other-pc"
        foreign = devices / "other-pc.md"
        foreign.write_text(shared.MARKER + json.dumps(info) + " -->\n\nLegacyUniqueFact\n", encoding="utf-8")
        before = foreign.read_bytes()
        shared.export(self.home)
        self.assertFalse(legacy.exists())
        backups = list((self.home / "backups/shared-knowledge").glob("*.md"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), old)
        self.assertEqual(foreign.read_bytes(), before)
        match = shared.search(self.home, "LegacyUniqueFact")["matches"][0]
        self.assertEqual(match["device"], "other-pc")
        self.assertEqual(shared.read_note(self.home, match["id"])["note"]["kind"], "legacy")

    def test_removed_topic_is_backed_up_and_unmanaged_file_is_preserved(self):
        self.write_topics()
        shared.export(self.home)
        folder = self.vault / shared.FOLDER / "devices/first-pc"
        retired = next(note for note in self.manifest()["notes"] if note["title"] == "Beta")
        before = (folder / retired["file"]).read_bytes()
        manual = folder / "topic-user.md"
        manual.write_text("Keep manual content", encoding="utf-8")
        self.write_topics(second=False)
        shared.export(self.home)
        self.assertFalse((folder / retired["file"]).exists())
        self.assertTrue(any(p.read_bytes() == before for p in (self.home / "backups/shared-knowledge").glob("*.md")))
        self.assertEqual(manual.read_text(encoding="utf-8"), "Keep manual content")

    def test_incomplete_sync_is_reported_and_export_repairs_generated_file(self):
        result = shared.export(self.home)
        path = next(Path(file) for file in result["files"] if Path(file).name.startswith("topic-"))
        path.write_text(path.read_text(encoding="utf-8") + "Broken export", encoding="utf-8")
        self.assertTrue(shared.search(self.home, "SQLite")["warnings"])
        shared.export(self.home)
        self.assertFalse(shared.search(self.home, "SQLite")["warnings"])
        self.assertNotIn("Broken export", path.read_text(encoding="utf-8"))

    def test_manifest_traversal_is_not_read_or_overwritten(self):
        shared.export(self.home)
        path = self.vault / shared.FOLDER / "devices/first-pc/manifest.json"
        data = self.manifest()
        data["notes"][0]["file"] = "../../outside.md"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(ValueError):
            shared.export(self.home)
        self.assertTrue(shared.search(self.home, "SQLite")["warnings"])

    def test_failed_manifest_commit_keeps_legacy_and_can_be_retried(self):
        devices = self.vault / shared.FOLDER / "devices"
        devices.mkdir(parents=True)
        legacy = devices / "first-pc.md"
        legacy.write_text(shared.MARKER + json.dumps({"device": "first-pc"}) + " -->\n\nOld", encoding="utf-8")
        original = shared.atomic_write
        def interrupted(path, text):
            if path.name == "manifest.json":
                raise OSError("Simulated interrupted commit")
            original(path, text)
        with patch.object(shared, "atomic_write", interrupted):
            with self.assertRaises(OSError):
                shared.export(self.home)
        self.assertTrue(legacy.exists())
        self.assertEqual(shared.export(self.home)["status"], "exported")
        self.assertFalse(legacy.exists())
        self.assertFalse(shared.search(self.home, "SQLite")["warnings"])

    def test_parallel_export_is_refused_without_waiting(self):
        with shared.export_lock(self.home):
            with self.assertRaisesRegex(ValueError, "Another export"):
                shared.export(self.home)

    def test_ru_queries_find_english_technical_lessons(self):
        self.write_topics(first_title="TLS certificate review", first_body=(
            "Keep certificate validation enabled.\n"
            "Wait for rule group sync before retrying an update."))
        shared.export(self.home)
        for query in ["проверка сертификата", "синхронизация группы правил"]:
            result = shared.recall(self.home, query)
            self.assertEqual(result["notes"][0]["title"], "TLS certificate review")
            self.assertFalse(result["warnings"])

    def test_mr_and_pipeline_ids_are_exact_phrases(self):
        self.write_topics(first_title="MR !245 stabilization", first_body="MR !245 fixed pipeline 267627.")
        native = self.native / "MEMORY.md"
        native.write_text(native.read_text(encoding="utf-8") +
                          "\n# Noise\n\nMR !198, pipeline 245, thread 2453, pipeline 2676279.\n", encoding="utf-8")
        shared.export(self.home)
        for query in ["MR !245", "pipeline 267627"]:
            matches = shared.search(self.home, query)["matches"]
            self.assertEqual([item["title"] for item in matches], ["MR !245 stabilization"])

    def test_unrelated_and_stopword_only_queries_return_no_matches(self):
        shared.export(self.home)
        for query in ["закат фильма на луне", "и в на", "невозможныйтермин MR"]:
            self.assertEqual(shared.search(self.home, query)["matches"], [])

    def test_whole_word_search_does_not_match_runtimeerror(self):
        self.write_topics(first_body="Re-raise RuntimeError unchanged.")
        shared.export(self.home)
        self.assertEqual(shared.search(self.home, "runtime")["matches"], [])

    def test_projects_are_inferred_from_linux_and_windows_cwd(self):
        text = "# First\n\napplies_to: cwd=/home/faust/dev/esensor-aqa; scope\n"
        text += "# Second\n\napplies_to: cwd=G:\\Work\\Projects\\gitms; scope\n"
        self.assertEqual([item["project"] for item in shared.split_topics(text)], ["esensor-aqa", "gitms"])

    def test_project_filter_excludes_another_repository(self):
        self.write_topics(first_body="applies_to: cwd=/home/faust/dev/esensor-aqa;\nScopedUniqueTerm")
        native = self.native / "MEMORY.md"
        native.write_text(native.read_text(encoding="utf-8").replace("Second useful fact", (
            "applies_to: cwd=G:\\Work\\Projects\\gitms;\nScopedUniqueTerm")), encoding="utf-8")
        shared.export(self.home)
        matches = shared.search(self.home, "ScopedUniqueTerm", project="esensor-aqa")["matches"]
        self.assertEqual([item["title"] for item in matches], ["Alpha"])

    def test_read_by_id_opens_only_the_requested_note(self):
        self.write_topics()
        shared.export(self.home)
        first = self.manifest()["notes"][0]
        opened = []
        original = Path.read_text

        def tracked(path, *args, **kwargs):
            if path.suffix == ".md":
                opened.append(path.name)
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", tracked):
            shared.read_note(self.home, first["id"])
        self.assertEqual(opened, [first["file"]])

    def test_warm_index_reads_only_selected_notes(self):
        self.write_topics()
        shared.export(self.home)
        shared.search(self.home, "alpha")
        opened = []
        original = Path.read_text

        def tracked(path, *args, **kwargs):
            if path.suffix == ".md":
                opened.append(path.name)
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", tracked):
            self.assertTrue(shared.search(self.home, "alpha")["matches"])
        alpha = next(note for note in self.manifest()['notes'] if note['title'] == 'Alpha')
        self.assertEqual(opened, [alpha['file']])

    def test_warm_cache_rejects_changed_or_missing_source(self):
        self.write_topics(first_body="UniqueIndexedLesson")
        shared.export(self.home)
        note = next(item for item in self.manifest()["notes"] if item["title"] == "Alpha")
        target = self.vault / shared.FOLDER / "devices/first-pc" / note["file"]
        self.assertTrue(shared.search(self.home, "UniqueIndexedLesson")["matches"])
        target.write_text(target.read_text(encoding="utf-8") + "\nCorrupted\n", encoding="utf-8")
        result = shared.search(self.home, "UniqueIndexedLesson")
        self.assertTrue(result["warnings"])
        self.assertEqual(result["matches"], [])
        shared.export(self.home)
        self.assertTrue(shared.search(self.home, "UniqueIndexedLesson")["matches"])
        target.unlink()
        result = shared.search(self.home, "UniqueIndexedLesson")
        self.assertEqual(result["matches"], [])
        self.assertTrue(result["warnings"])

    def test_removed_note_disappears_from_local_index(self):
        self.write_topics()
        shared.export(self.home)
        self.assertTrue(shared.search(self.home, "beta")["matches"])
        self.write_topics(second=False)
        shared.export(self.home)
        self.assertEqual(shared.search(self.home, "beta")["matches"], [])

    def test_recall_skips_duplicate_summary_and_caps_complete_json(self):
        self.write_topics(first_body="SQLite " + "a useful lesson " * 800)
        shared.export(self.home)
        result = shared.recall(self.home, "SQLite", max_chars=1600)
        self.assertEqual(len(result["notes"]), 1)
        self.assertEqual(result["notes"][0]["kind"], "topic")
        self.assertLessEqual(len(json.dumps(result, ensure_ascii=False, indent=2)) + 1, 1600)
        self.assertTrue(result["truncated"])

    def test_read_is_bounded_and_full_read_requires_explicit_choice(self):
        self.write_topics(first_body="Large detail " * 1000)
        shared.export(self.home)
        note = next(item for item in self.manifest()["notes"] if item["title"] == "Alpha")
        result = shared.read_note(self.home, note["id"], max_chars=1600)
        self.assertLessEqual(len(json.dumps(result, ensure_ascii=False, indent=2)) + 1, 1600)
        self.assertTrue(result["truncated"])
        full = shared.read_note(self.home, note["id"], full=True)
        self.assertEqual(full["note"]["content"].count("Large detail"), 1000)

    def test_default_search_returns_at_most_three_notes(self):
        (self.native / "MEMORY.md").write_text("\n".join(
            f"# Topic {number}\n\nCommonSearchTerm different lesson {number}\n" for number in range(8)), encoding="utf-8")
        shared.export(self.home)
        self.assertEqual(len(shared.search(self.home, "CommonSearchTerm")["matches"]), 3)

    def test_parallel_searches_share_the_local_cache_safely(self):
        from concurrent.futures import ThreadPoolExecutor
        shared.export(self.home)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: shared.search(self.home, "SQLite"), range(8)))
        self.assertTrue(all(result["matches"] and not result["warnings"] for result in results))

    def test_installer_adds_conditional_recall_rule_only_once(self):
        for _ in range(2):
            shared.install(self.vault, "first-pc", self.home)
        instructions = (self.home / "AGENTS.md").read_text(encoding="utf-8")
        self.assertEqual(instructions.count(shared.RECALL_START), 1)
        self.assertIn(shared.RECALL_RULE, instructions)

    def test_recall_returns_the_matching_code_lesson_instead_of_keywords(self):
        self.write_topics(first_body=("Unrelated first lesson.\n\n"
            "Call wait_for_rule_group_sync() before retrying alreadyUpdating.\n"))
        shared.export(self.home)
        result = shared.recall(self.home, "синхронизация группы правил")
        self.assertIn("wait_for_rule_group_sync", result["notes"][0]["excerpt"])

    def test_source_repository_wins_over_reconstruction_directory(self):
        topics = shared.split_topics("# Reconstruction\n\napplies_to: "
            "cwd=/home/faust/dev/ass-context-reconstruction (source=/home/faust/dev/ass); read-only\n")
        self.assertEqual(topics[0]["project"], "ass")

    def test_project_filter_does_not_leak_other_projects_through_global_summary(self):
        (self.native / 'memory_summary.md').write_text('MR !245 belongs to eSensor.', encoding='utf-8')
        shared.export(self.home)
        self.assertEqual(shared.recall(self.home, 'MR !245', project='gitms')['notes'], [])
        self.assertTrue(shared.recall(self.home, 'MR !245')['notes'])

    def test_read_cli_finishes_with_many_long_warnings(self):
        shared.export(self.home)
        note_id = self.manifest()['notes'][0]['id']
        for letter in 'abc':
            device = letter * 64
            folder = self.vault / shared.FOLDER / 'devices' / device
            folder.mkdir()
            (folder / 'manifest.json').write_text(json.dumps({'version': 3, 'device': device, 'notes': []}), encoding='utf-8')
        environment = os.environ.copy()
        environment['CODEX_HOME'] = str(self.home)
        result = subprocess.run([sys.executable, str(SCRIPT), 'read', note_id, '--max-chars', '800'],
                                env=environment, capture_output=True, text=True, encoding='utf-8', timeout=3, check=True)
        self.assertLessEqual(len(result.stdout), 800)
        response = json.loads(result.stdout)
        self.assertTrue(response['warnings'])
        self.assertTrue(response['truncated'])

    def test_recall_and_search_keep_a_match_late_in_a_long_line(self):
        self.write_topics(first_body='unrelated filler ' * 140 + 'CriticalNeedle: keep TLS checks.')
        shared.export(self.home)
        result = shared.recall(self.home, 'CriticalNeedle')
        self.assertTrue('CriticalNeedle' in result['notes'][0]['excerpt'], 'Recall dropped its own match')
        self.assertLessEqual(len(result['notes'][0]['excerpt']), 1400)
        self.assertTrue(result['notes'][0]['excerpt_truncated'])
        self.assertTrue(result['truncated'])
        result = shared.search(self.home, 'CriticalNeedle')
        self.assertTrue('CriticalNeedle' in result['matches'][0]['snippet'], 'Search dropped its own match')
        self.assertTrue(result['matches'][0]['snippet_truncated'])

    def test_recall_keeps_match_after_long_preceding_context(self):
        self.write_topics(first_body='unrelated filler ' * 140 + '\n\nCriticalNeedle: preserve the answer.')
        shared.export(self.home)
        result = shared.recall(self.home, 'CriticalNeedle')
        self.assertTrue('CriticalNeedle' in result['notes'][0]['excerpt'], 'Context displaced the match')

    def test_smaller_response_budget_keeps_match_and_source_line(self):
        self.write_topics(first_body='unrelated filler ' * 140 + '\n\nCriticalNeedle: preserve the answer.')
        shared.export(self.home)
        result = shared.recall(self.home, 'CriticalNeedle', max_chars=1200)
        self.assertLessEqual(len(json.dumps(result, ensure_ascii=False, indent=2)) + 1, 1200)
        self.assertEqual(len(result['notes']), 1)
        note = result['notes'][0]
        self.assertIn('CriticalNeedle', note['excerpt'])
        source = Path(note['file']).read_text(encoding='utf-8').splitlines()
        self.assertIn(note['excerpt'].splitlines()[0], source[note['line'] - 1])

    def test_specific_match_wins_over_distant_short_term(self):
        self.write_topics(first_body='TLS ' + 'ordinary filler ' * 150 + 'CriticalNeedle: use verified repair.')
        shared.export(self.home)
        for retrieve in (shared.recall, shared.search):
            with self.subTest(command=retrieve.__name__):
                result = retrieve(self.home, 'TLS CriticalNeedle')
                notes = result.get('notes', result.get('matches'))
                self.assertTrue(notes)
                fragment = notes[0].get('excerpt', notes[0].get('snippet'))
                self.assertIn('CriticalNeedle', fragment)
                self.assertTrue(result['truncated'])

    def test_project_paths_with_spaces_work_quoted_and_unquoted(self):
        cases = [
            (r'C:\Work\My Project', r'cwd=C:\Work\My Project;'),
            ('/home/user/My Project', 'cwd=/home/user/My Project;'),
            (r'C:\Work\My Project', r'cwd="C:\Work\My Project";'),
            ('/home/user/My Project', "cwd='/home/user/My Project';"),
            ('/home/user/My Project', 'cwd=/tmp/reconstruction (source=/home/user/My Project);'),
        ]
        for directory, context in cases:
            with self.subTest(context=context):
                self.write_topics(first_title=directory, first_body='applies_to: ' + context + '\nScopedUniqueFact', second=False)
                shared.export(self.home)
                matches = shared.search(self.home, 'ScopedUniqueFact', project=directory)['matches']
                self.assertTrue(matches, 'A path with spaces lost its project match')
                self.assertEqual(matches[0]['project'], 'my project')

    def test_selected_source_is_verified_even_if_size_and_mtime_are_preserved(self):
        self.write_topics(first_body='UniqueIndexedLesson AAAA')
        shared.export(self.home)
        original = shared.search(self.home, 'UniqueIndexedLesson')['matches'][0]
        path = Path(original['file'])
        stamp = path.stat()
        path.write_text(path.read_text(encoding='utf-8').replace('AAAA', 'BBBB'), encoding='utf-8')
        os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        result = shared.search(self.home, 'UniqueIndexedLesson')
        self.assertEqual(result['matches'], [])
        self.assertTrue(result['warnings'])
        self.assertIn('BBBB', path.read_text(encoding='utf-8'))

    def test_warm_default_search_verifies_at_most_three_sources(self):
        (self.native / 'MEMORY.md').write_text('\n'.join(
            f'# Topic {number}\n\nCommonSearchTerm lesson {number}\n' for number in range(8)), encoding='utf-8')
        shared.export(self.home)
        shared.search(self.home, 'CommonSearchTerm')
        with patch.object(shared, 'read_record', wraps=shared.read_record) as read:
            result = shared.search(self.home, 'CommonSearchTerm')
        self.assertEqual(len(result['matches']), 3)
        self.assertEqual(read.call_count, 3)

    def test_unowned_root_markdown_is_ignored_without_sync_warnings(self):
        shared.export(self.home)
        devices = self.vault / shared.FOLDER / 'devices'
        for name in ['README.md', 'my-notes.md']:
            (devices / name).write_text('UnrelatedUniqueManualNote\n', encoding='utf-8')
        result = shared.search(self.home, 'SQLite')
        self.assertTrue(result['matches'])
        self.assertEqual(result['warnings'], [])
        self.assertEqual(shared.search(self.home, 'UnrelatedUniqueManualNote')['matches'], [])


if __name__ == "__main__":
    unittest.main()
