import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PluginInstallationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "Codex $O'Brien profile"
        self.home.mkdir()
        self.vault = self.root / "Vault with spaces"
        self.vault.mkdir()
        self.shared = load_module("shared_knowledge")
        with patch.dict(sys.modules, {"shared_knowledge": self.shared}):
            self.background = load_module("export_background")
            self.setup = load_module("plugin_setup")
            with patch.dict(sys.modules, {"export_background": self.background}):
                self.hook = load_module("plugin_hook")

    def configure(self, **extra):
        config = {"vault_path": str(self.vault), "device": "fixture-pc", **extra}
        (self.home / "shared-knowledge.json").write_text(json.dumps(config), encoding="utf-8")
        return config

    def install(self, **options):
        with patch.object(self.setup.subprocess, "run") as scheduler:
            scheduler.return_value = subprocess.CompletedProcess([], 0, "", "")
            result = self.setup.setup(self.home, **options)
        if os.name == "nt":
            scheduler.assert_called_once()
            self.assertEqual(scheduler.call_args.kwargs["env"]["CODEX_HOME"], str(self.home))
            self.assertEqual(scheduler.call_args.args[0][0], "powershell.exe")
            self.assertEqual("-Remove" in scheduler.call_args.args[0], options.get("automation") is False)
        else:
            scheduler.assert_not_called()
        return result

    def test_fresh_and_repeat_setup_preserve_local_settings(self):
        result = self.install(vault=self.vault, device="fixture-pc")
        self.assertEqual(result["status"], "configured")
        self.assertEqual(result["automatic_export"], os.name == "nt")
        config_path = self.home / "shared-knowledge.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["foreign_extension"] = {"enabled": True, "paths": ["keep this"]}
        config["repository_path"] = "keep-existing-repository"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        runtime = self.home / "vaultgoblin/runtime"
        snapshots = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in runtime.iterdir()}
        repeated = self.install()
        self.assertEqual(repeated, result)
        self.assertEqual(json.loads(config_path.read_text(encoding="utf-8")), config)
        self.assertEqual(
            {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in runtime.iterdir()}, snapshots
        )
        self.assertFalse((self.home / "skills/codex-shared-knowledge").exists())
        self.assertFalse((self.home / "AGENTS.md").exists())
        self.assertFalse((self.home / "hooks.json").exists())

    def test_migration_backs_up_owned_skill_and_preserves_foreign_rules_and_hooks(self):
        self.configure(foreign_extension={"key": "value"})
        skill = self.home / "skills/codex-shared-knowledge"
        script = skill / "scripts/shared_knowledge.py"
        script.parent.mkdir(parents=True)
        script.write_text('GENERATOR = "codex-shared-knowledge"\n', encoding="utf-8")
        (skill / "local-file.txt").write_text("preserve installed data", encoding="utf-8")
        foreign = {"type": "command", "command": "foreign-hook", "timeout": 12}
        owned = {"type": "command", "command": "old-export", "statusMessage": self.shared.EXPORT_HOOK}
        mixed = {"matcher": "keep-matcher", "description": "keep-group", "hooks": [foreign, owned]}
        empty = {"matcher": "keep-empty-group", "hooks": []}
        original_hooks = {"foreign_top_level": [1, 2], "hooks": {
            "Stop": [mixed, {"hooks": [owned]}, empty],
            "SessionEnd": [{"hooks": [owned]}, {"hooks": [foreign]}],
            "PreToolUse": [{"hooks": [owned]}],
        }}
        hook_text = json.dumps(original_hooks)
        (self.home / "hooks.json").write_text(hook_text, encoding="utf-8")
        instructions = (
            "Keep this rule.\n" + self.shared.AGENT_LINE + "\n" + self.shared.RECALL_START
            + "\nOld owned recall rule.\n" + self.shared.RECALL_END
            + "\n<!-- foreign-rule -->\nKeep another rule.\n"
        )
        (self.home / "AGENTS.md").write_text(instructions, encoding="utf-8")
        self.install()
        expected = {"foreign_top_level": [1, 2], "hooks": {
            "Stop": [{**mixed, "hooks": [foreign]}, empty],
            "SessionEnd": [{"hooks": [foreign]}],
            "PreToolUse": [{"hooks": [owned]}],
        }}
        self.assertEqual(json.loads((self.home / "hooks.json").read_text(encoding="utf-8")), expected)
        self.assertEqual((self.home / "AGENTS.md").read_text(encoding="utf-8"),
                         "Keep this rule.\n\n<!-- foreign-rule -->\nKeep another rule.\n")
        self.assertFalse(skill.exists())
        backups = self.home / "backups/vaultgoblin-plugin"
        moved, = backups.glob("skill-*")
        self.assertEqual((moved / "local-file.txt").read_text(encoding="utf-8"), "preserve installed data")
        hook_backup, = backups.glob("hooks.json-*")
        agent_backup, = backups.glob("AGENTS.md-*")
        self.assertEqual(hook_backup.read_text(encoding="utf-8"), hook_text)
        self.assertEqual(agent_backup.read_text(encoding="utf-8"), instructions)
        first_backups = sorted(path.name for path in backups.iterdir())
        self.install()
        self.assertEqual(sorted(path.name for path in backups.iterdir()), first_backups)

    def test_unrecognized_skill_is_rejected_without_migrating_or_scheduling(self):
        original = self.configure(foreign_extension="preserve")
        skill = self.home / "skills/codex-shared-knowledge"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("unrelated user skill", encoding="utf-8")
        with patch.object(self.setup.subprocess, "run") as scheduler:
            with self.assertRaisesRegex(ValueError, "Unrecognized skill"):
                self.setup.setup(self.home)
        scheduler.assert_not_called()
        self.assertEqual(json.loads((self.home / "shared-knowledge.json").read_text(encoding="utf-8")), original)
        self.assertEqual((skill / "SKILL.md").read_text(encoding="utf-8"), "unrelated user skill")
        self.assertFalse((self.home / "vaultgoblin").exists())
        self.assertFalse((self.home / "backups").exists())

    def test_runtime_exports_topics_after_its_plugin_source_is_removed(self):
        bundle = self.root / "plugin cache"
        bundle.mkdir()
        for name in ("shared_knowledge.py", "export_background.py", "install_export_task.ps1"):
            shutil.copyfile(SCRIPTS / name, bundle / name)
        native = self.home / "memories"
        native.mkdir()
        sources = {
            "memory_summary.md": b"Use SQLite for local storage.\n",
            "MEMORY.md": b"# Fixture alpha\n\nA durable alpha decision.\n\n# Fixture beta\n\nA durable beta decision.\n",
        }
        for name, content in sources.items():
            (native / name).write_bytes(content)
        with patch.object(self.shared, "__file__", str(bundle / "shared_knowledge.py")):
            result = self.install(vault=self.vault, device="fixture-pc", automation=False)
        self.assertFalse(result["automatic_export"])
        self.assertFalse(json.loads((self.home / "shared-knowledge.json").read_text(encoding="utf-8"))[
            "plugin_auto_export"
        ])
        shutil.rmtree(bundle)
        runtime = self.home / "vaultgoblin/runtime"
        self.assertTrue((runtime / "shared_knowledge.py").is_file())
        self.assertFalse((self.home / "skills/codex-shared-knowledge").exists())
        completed = subprocess.run(
            [sys.executable, "-B", str(runtime / "export_background.py"), str(self.home), "--wait"],
            env={**os.environ, "CODEX_HOME": str(self.home), "PYTHONPATH": ""},
            cwd=self.root, capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual((completed.returncode, completed.stdout, completed.stderr), (0, "", ""))
        output = self.vault / "Codex Knowledge/devices/fixture-pc"
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        topics = [note for note in manifest["notes"] if note["kind"] == "topic"]
        self.assertEqual({note["title"] for note in topics}, {"Fixture alpha", "Fixture beta"})
        contents = "\n".join((output / note["file"]).read_text(encoding="utf-8") for note in topics)
        self.assertIn("A durable alpha decision.", contents)
        self.assertIn("A durable beta decision.", contents)
        self.assertEqual({path.name: path.read_bytes() for path in native.iterdir()}, sources)

    def test_unconfigured_hook_has_no_runtime_or_process_effects(self):
        for configuration in (None, {}):
            with self.subTest(configuration=configuration):
                if configuration is not None:
                    (self.home / "shared-knowledge.json").write_text(json.dumps(configuration), encoding="utf-8")
                with patch.dict(os.environ, CODEX_HOME=str(self.home)), \
                     patch.object(sys, "argv", ["plugin_hook.py", "--refresh"]), \
                     patch.object(self.hook, "install_runtime") as refresh, \
                     patch.object(self.hook, "run") as export:
                    self.assertEqual(self.hook.main(), 0)
                refresh.assert_not_called()
                export.assert_not_called()
                self.assertFalse((self.home / "vaultgoblin").exists())
                self.assertFalse((self.home / "shared-knowledge-export.log").exists())
                self.assertEqual(list(self.vault.iterdir()), [])

    def test_manual_hook_refreshes_missing_and_stale_runtime_without_exporting(self):
        self.configure(plugin_auto_export=False)
        config_path = self.home / "shared-knowledge.json"
        original_config = config_path.read_bytes()
        (self.vault / "personal-note.md").write_text("Keep this note.", encoding="utf-8")
        original_vault = {path.name: path.read_bytes() for path in self.vault.iterdir()}
        with patch.dict(os.environ, CODEX_HOME=str(self.home)), \
             patch.object(sys, "argv", ["plugin_hook.py"]), \
             patch.object(self.hook, "install_runtime") as refresh, \
             patch.object(self.hook, "run") as export:
            self.assertEqual(self.hook.main(), 0)
        refresh.assert_not_called()
        export.assert_not_called()
        self.assertFalse((self.home / "vaultgoblin").exists())
        bundle = self.root / "manual plugin cache"
        bundle.mkdir()
        names = ("shared_knowledge.py", "export_background.py", "install_export_task.ps1")
        runtime = self.home / "vaultgoblin/runtime"
        for version in ("first bundle", "updated bundle"):
            with self.subTest(version=version):
                for name in names:
                    (bundle / name).write_text(version + ": " + name, encoding="utf-8")
                with patch.dict(os.environ, CODEX_HOME=str(self.home)), \
                     patch.object(sys, "argv", ["plugin_hook.py", "--refresh"]), \
                     patch.object(self.shared, "__file__", str(bundle / "shared_knowledge.py")), \
                     patch.object(self.hook, "run") as export, \
                     patch.object(subprocess, "Popen") as process, \
                     patch.object(subprocess, "run") as command:
                    self.assertEqual(self.hook.main(), 0)
                export.assert_not_called()
                process.assert_not_called()
                command.assert_not_called()
                self.assertEqual({path.name for path in runtime.iterdir()}, set(names))
                for name in names:
                    self.assertEqual((runtime / name).read_bytes(), (bundle / name).read_bytes())
                self.assertFalse((self.home / "shared-knowledge-export.log").exists())
                self.assertEqual(config_path.read_bytes(), original_config)
                self.assertEqual({path.name: path.read_bytes() for path in self.vault.iterdir()}, original_vault)

    def test_enabled_hook_refreshes_from_the_active_bundle_before_launching_runtime(self):
        self.configure(plugin_auto_export=True)
        bundle = self.root / "active plugin cache"
        bundle.mkdir()
        names = ("shared_knowledge.py", "export_background.py", "install_export_task.ps1")
        for name in names:
            (bundle / name).write_text("active bundle: " + name, encoding="utf-8")
        runtime = self.home / "vaultgoblin/runtime"
        runtime.mkdir(parents=True)
        for name in names:
            (runtime / name).write_text("stale runtime", encoding="utf-8")
        with patch.dict(os.environ, CODEX_HOME=str(self.home)), \
             patch.object(sys, "argv", ["plugin_hook.py", "--refresh"]), \
             patch.object(self.shared, "__file__", str(bundle / "shared_knowledge.py")), \
             patch.object(self.hook, "run", return_value=0) as export:
            self.assertEqual(self.hook.main(), 0)
        export.assert_called_once_with(self.home, wait=False, launcher=runtime / "export_background.py")
        for name in names:
            self.assertEqual((runtime / name).read_bytes(), (bundle / name).read_bytes())
        with patch.dict(os.environ, CODEX_HOME=str(self.home)), \
             patch.object(sys, "argv", ["plugin_hook.py"]), \
             patch.object(self.hook, "install_runtime") as refresh, \
             patch.object(self.hook, "run", return_value=0) as export:
            self.assertEqual(self.hook.main(), 0)
        refresh.assert_not_called()
        export.assert_called_once_with(self.home, wait=False, launcher=runtime / "export_background.py")

    def test_legacy_install_hooks_repairs_runtime_without_the_old_skill(self):
        self.configure()
        self.assertFalse((self.home / "skills/codex-shared-knowledge").exists())
        self.shared.install_hooks(self.home)
        runtime = self.home / "vaultgoblin/runtime"
        for name in ("shared_knowledge.py", "export_background.py", "install_export_task.ps1"):
            self.assertEqual((runtime / name).read_bytes(), (SCRIPTS / name).read_bytes())
        hooks = json.loads((self.home / "hooks.json").read_text(encoding="utf-8"))["hooks"]
        for event in ("Stop", "SessionEnd"):
            handler, = hooks[event][0]["hooks"]
            self.assertIn(str(runtime / "export_background.py").replace("'", "''"), handler["commandWindows"])
            self.assertNotIn("skills/codex-shared-knowledge", handler["command"])
        (runtime / "export_background.py").unlink()
        self.shared.install_hooks(self.home)
        self.assertEqual((runtime / "export_background.py").read_bytes(),
                         (SCRIPTS / "export_background.py").read_bytes())

    @unittest.skipUnless(os.name == "nt", "Windows Task Scheduler")
    def test_scheduler_isolates_profiles_and_migrates_only_the_own_legacy_task(self):
        second = self.root / "second Codex profile"
        second.mkdir()
        for home in (self.home, second):
            (home / "shared-knowledge.json").write_text("{}", encoding="utf-8")
            self.shared.install_runtime(home)
        harness = self.root / "task-isolation.ps1"
        harness.write_text("""param($Installer, $PythonPath, $FirstHome, $SecondHome)
$ErrorActionPreference = 'Stop'
$global:Tasks = @{}
$global:Registered = @()
$global:Removed = @()
function New-ScheduledTaskAction { param($Execute, $Argument); @{Execute=$Execute; Arguments=$Argument} }
function New-ScheduledTaskTrigger { @{} }
function New-ScheduledTaskPrincipal { @{} }
function New-ScheduledTaskSettingsSet { @{} }
function Get-ScheduledTask { param($TaskName, $ErrorAction); $global:Tasks[$TaskName] }
function Register-ScheduledTask {
    param($TaskName, $Action, $Trigger, $Principal, $Settings, $Description, [switch]$Force)
    $global:Registered += $TaskName
    $global:Tasks[$TaskName] = @{TaskName=$TaskName; Actions=@($Action)}
    @{TaskName=$TaskName; State='Ready'}
}
function Unregister-ScheduledTask {
    param($TaskName, $Confirm)
    $global:Removed += $TaskName
    $global:Tasks.Remove($TaskName)
}
$legacyName = 'Codex Shared Knowledge Export'
$foreignAction = @{Execute='pythonw.exe'; Arguments='-B "foreign.py" "' + $SecondHome + '" --wait'}
$global:Tasks[$legacyName] = @{TaskName=$legacyName; Actions=@($foreignAction)}
$env:CODEX_HOME = $FirstHome
& $Installer -PythonPath $PythonPath | Out-Null
$foreignPreserved = $global:Tasks.ContainsKey($legacyName) -and $global:Removed.Count -eq 0
& $Installer -PythonPath $PythonPath | Out-Null
$env:CODEX_HOME = $SecondHome
& $Installer -PythonPath $PythonPath | Out-Null
$legacyMigrated = -not $global:Tasks.ContainsKey($legacyName)
$profileTasks = @($global:Tasks.Values)
$firstName = $global:Registered[0]
$secondName = $global:Registered[2]
$env:CODEX_HOME = $FirstHome
& $Installer -Remove | Out-Null
@{ForeignPreserved=$foreignPreserved; Registered=$global:Registered;
  LegacyMigrated=$legacyMigrated; Removed=$global:Removed; ProfileTasks=$profileTasks;
  FirstRemoved=(-not $global:Tasks.ContainsKey($firstName)); SecondRetained=$global:Tasks.ContainsKey($secondName)
} | ConvertTo-Json -Depth 8 -Compress
""", encoding="utf-8")
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
             str(harness), str(SCRIPTS / "install_export_task.ps1"), sys.executable, str(self.home), str(second)],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        first_name, repeated_name, second_name = result["Registered"]
        self.assertEqual(first_name, repeated_name)
        self.assertNotEqual(first_name, second_name)
        for name in (first_name, second_name):
            self.assertRegex(name, r"^Codex Shared Knowledge Export-[A-F0-9]{12}$")
        self.assertTrue(result["ForeignPreserved"])
        self.assertTrue(result["LegacyMigrated"])
        self.assertEqual(result["Removed"], ["Codex Shared Knowledge Export", first_name])
        self.assertTrue(result["FirstRemoved"])
        self.assertTrue(result["SecondRetained"])
        tasks = {task["TaskName"]: task for task in result["ProfileTasks"]}
        self.assertEqual(set(tasks), {first_name, second_name})
        for name, home in ((first_name, self.home), (second_name, second)):
            action, = tasks[name]["Actions"]
            self.assertEqual(Path(action["Execute"]).name.lower(), "pythonw.exe")
            self.assertEqual(action["Arguments"],
                             f'-B "{home / "vaultgoblin/runtime/export_background.py"}" "{home}" --wait')


if __name__ == "__main__":
    unittest.main()
