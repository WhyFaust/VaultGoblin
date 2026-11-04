import builtins
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load_module(name, path=None):
    spec = importlib.util.spec_from_file_location(name, path or SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProfileHookTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.home = self.root / "Codex profile"
        self.home.mkdir()
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.shared = load_module("shared_knowledge")
        with patch.dict(sys.modules, shared_knowledge=self.shared):
            self.setup = load_module("plugin_setup")
            background = types.ModuleType("export_background")
            background.run = Mock(return_value=0)
            with patch.dict(sys.modules, export_background=background):
                self.plugin = load_module("plugin_hook")
        scheduler = patch.object(self.setup, "configure_windows_task")
        self.scheduler = scheduler.start()
        self.addCleanup(scheduler.stop)

    def install(self, **options):
        return self.setup.setup(self.home, self.vault, "test-device", **options)

    def settings(self):
        return json.loads((self.home / "shared-knowledge.json").read_text(encoding="utf-8"))

    def write_hooks(self, config):
        text = json.dumps(config, indent=4) + "\n"
        (self.home / "hooks.json").write_text(text, encoding="utf-8")
        return text

    def own_hooks(self):
        return {"hooks": {event: [{"hooks": [self.setup.new_profile_handler(self.home, event)]}]
                          for event in self.setup.PROFILE_EVENTS}}

    def test_existing_profile_is_detected_and_keeps_definition_bytes_and_trust(self):
        hooks = self.own_hooks()
        for groups in hooks["hooks"].values():
            groups[0]["hooks"][0]["command"] = self.setup.profile_commands(self.home)[1]
        original = self.write_hooks(hooks)
        trust = self.home / "config.toml"
        trust.write_bytes(b'[hooks.trusted]\nhash = "keep-native-trust"\n')
        self.install()
        self.assertIs(self.settings()["plugin_profile_hooks"], True)
        runtime = self.home / "vaultgoblin/runtime"
        wrapper = self.home / "scripts/vaultgoblin_hook.py"
        snapshots = {path: (path.read_bytes(), path.stat().st_mtime_ns)
                     for path in [wrapper, *runtime.iterdir()]}
        self.install()
        self.assertEqual((self.home / "hooks.json").read_text(encoding="utf-8"), original)
        self.assertEqual(trust.read_bytes(), b'[hooks.trusted]\nhash = "keep-native-trust"\n')
        self.assertEqual(wrapper.read_bytes(), (SCRIPTS / "profile_hook.py").read_bytes())
        self.assertEqual({path: (path.read_bytes(), path.stat().st_mtime_ns) for path in snapshots}, snapshots)
        self.assertFalse((self.home / "backups").exists())

    def test_registration_preserves_foreign_handlers_matchers_and_content_backup(self):
        foreign = {"type": "command", "command": "foreign.py", "statusMessage": self.setup.PROFILE_HOOK}
        same_script = {"type": "command", "command": self.setup.profile_commands(self.home)[1],
                       "statusMessage": "Foreign owner"}
        empty = {"matcher": "keep-empty", "hooks": []}
        group = {"matcher": "keep-matcher", "description": "keep", "hooks": [foreign, same_script]}
        original = self.write_hooks({"extension": {"keep": True}, "hooks": {
            "Stop": [group, empty], "PreToolUse": [{"hooks": [foreign]}]}})
        self.install(profile_hooks=True)
        path = self.home / "hooks.json"
        config = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(config["extension"], {"keep": True})
        self.assertEqual(config["hooks"]["Stop"][:2], [group, empty])
        self.assertEqual(config["hooks"]["PreToolUse"], [{"hooks": [foreign]}])
        for event in self.setup.PROFILE_EVENTS:
            own = [handler for item in config["hooks"][event] for handler in item["hooks"]
                   if self.setup.owns_profile_handler(self.home, handler)]
            self.assertEqual(len(own), 1)
            self.assertEqual(own[0]["timeout"], 3 if event == "SessionEnd" else 10)
            self.assertEqual(own[0].get("async", False), event == "Stop")
        backup, = (self.home / "backups/vaultgoblin-plugin").glob("hooks.json-*")
        self.assertEqual(backup.read_text(encoding="utf-8"), original)
        stable = path.read_bytes()
        self.install()
        self.assertEqual(path.read_bytes(), stable)

    def test_invalid_hook_shapes_fail_before_any_settings_runtime_or_scheduler_write(self):
        for invalid in ({"SessionStart": {}}, {"Stop": [{"hooks": None}]},
                        {"SessionEnd": [{"hooks": ["not an object"]}]}):
            with self.subTest(invalid=invalid):
                original = self.write_hooks({"hooks": invalid})
                for automation in (True, False):
                    with self.assertRaises(ValueError):
                        if automation:
                            self.install(profile_hooks=True)
                        else:
                            self.setup.setup(self.home, profile_hooks=True, automation=False)
                self.assertEqual((self.home / "hooks.json").read_text(encoding="utf-8"), original)
                self.assertFalse((self.home / "shared-knowledge.json").exists())
                self.assertFalse((self.home / "vaultgoblin").exists())
        self.scheduler.assert_not_called()

    def test_disable_removes_owned_hooks_without_prerequisites_and_retains_mode(self):
        hooks = self.own_hooks()
        foreign = {"type": "command", "command": "foreign", "statusMessage": self.setup.PROFILE_HOOK}
        hooks["hooks"]["Stop"][0]["hooks"].append(foreign)
        hooks["hooks"]["Stop"][0]["hooks"].append(
            {"statusMessage": self.shared.EXPORT_HOOK, "command": "old-export"})
        self.write_hooks(hooks)
        config = {"vault_path": str(self.vault), "device": "test-device", "foreign": {"keep": 1}}
        (self.home / "shared-knowledge.json").write_text(json.dumps(config), encoding="utf-8")
        self.vault.rmdir()
        with patch.object(self.setup, "installation_settings", side_effect=AssertionError("vault")), \
             patch.object(self.setup, "install_runtime", side_effect=AssertionError("runtime")), \
             patch.object(self.setup.sqlite3, "connect", side_effect=AssertionError("FTS5")):
            self.setup.setup(self.home, automation=False)
            self.setup.setup(self.home, automation=False)
        self.assertEqual(self.settings(), {**config, "plugin_auto_export": False, "plugin_profile_hooks": True})
        expected = {"hooks": {"SessionStart": [], "Stop": [{"hooks": [foreign]}], "SessionEnd": []}}
        self.assertEqual(json.loads((self.home / "hooks.json").read_text(encoding="utf-8")), expected)
        self.assertTrue(self.scheduler.call_args.kwargs["remove"])
        self.assertFalse((self.home / "vaultgoblin").exists())
        self.vault.mkdir()
        self.install()
        self.assertIs(self.settings()["plugin_profile_hooks"], True)
        restored = json.loads((self.home / "hooks.json").read_text(encoding="utf-8"))
        for event in self.setup.PROFILE_EVENTS:
            self.assertTrue(any(self.setup.owns_profile_handler(self.home, handler)
                                for group in restored["hooks"][event] for handler in group["hooks"]))

    def test_explicit_manual_setup_prepares_runtime_without_registering_hooks(self):
        result = self.install(automation=False, profile_hooks=True)
        self.assertEqual(result["vault"], str(self.vault))
        self.assertEqual(result["device"], "test-device")
        self.assertIs(self.settings()["plugin_auto_export"], False)
        self.assertIs(self.settings()["plugin_profile_hooks"], True)
        self.assertTrue((self.home / "vaultgoblin/runtime/export_background.py").is_file())
        self.assertTrue((self.home / "scripts/vaultgoblin_hook.py").is_file())
        self.assertFalse((self.home / "hooks.json").exists())
        self.assertTrue(self.scheduler.call_args.kwargs["remove"])

    def test_profile_wrapper_checks_flag_before_import_or_export(self):
        wrapper = load_module("profile_hook")
        original_import = builtins.__import__

        def guard(name, *args, **kwargs):
            if name == "export_background":
                self.fail("disabled wrapper imported runtime")
            return original_import(name, *args, **kwargs)

        for value in (None, {}, {"plugin_auto_export": False}, {"plugin_auto_export": 1}):
            with self.subTest(value=value):
                path = self.home / "shared-knowledge.json"
                if value is not None:
                    path.write_text(json.dumps(value), encoding="utf-8")
                with patch.object(wrapper, "__file__", str(self.home / "scripts/vaultgoblin_hook.py")), \
                     patch.object(builtins, "__import__", side_effect=guard):
                    self.assertEqual(wrapper.main(), 0)

    def test_plugin_callbacks_refresh_without_exporting_in_profile_mode(self):
        (self.home / "shared-knowledge.json").write_text(
            json.dumps({"plugin_auto_export": True, "plugin_profile_hooks": True}), encoding="utf-8")
        for arguments in ([], ["--refresh"]):
            with self.subTest(arguments=arguments), \
                 patch.dict(os.environ, CODEX_HOME=str(self.home)), \
                 patch.object(sys, "argv", ["plugin_hook.py", *arguments]), \
                 patch.object(self.plugin, "install_runtime") as refresh, \
                 patch.object(self.plugin, "run") as export:
                self.assertEqual(self.plugin.main(), 0)
                self.assertEqual(refresh.call_count, bool(arguments))
                export.assert_not_called()

    def test_upgrade_replaces_stable_runtime_and_wrapper_and_survives_cache_removal(self):
        bundle = self.root / "plugin cache"
        shutil.copytree(SCRIPTS, bundle)
        with patch.object(self.setup, "__file__", str(bundle / "plugin_setup.py")), \
             patch.object(self.shared, "__file__", str(bundle / "shared_knowledge.py")):
            self.install(profile_hooks=True)
            wrapper = self.home / "scripts/vaultgoblin_hook.py"
            wrapper.write_text("stale wrapper", encoding="utf-8")
            runtime = self.home / "vaultgoblin/runtime"
            (runtime / "export_background.py").write_text("stale runtime", encoding="utf-8")
            self.install()
        self.assertEqual(wrapper.read_bytes(), (bundle / "profile_hook.py").read_bytes())
        self.assertEqual((runtime / "export_background.py").read_bytes(),
                         (bundle / "export_background.py").read_bytes())
        shutil.rmtree(bundle)
        (self.home / "shared-knowledge.json").write_text(
            json.dumps({"plugin_auto_export": True}), encoding="utf-8")
        (runtime / "export_background.py").write_text(
            'def run(home, wait):\n    return 23 if home.name == "Codex profile" and wait is False else 91\n',
            encoding="utf-8")
        original_path = sys.path[:]
        self.addCleanup(lambda: sys.path.__setitem__(slice(None), original_path))
        with patch.dict(os.environ, CODEX_HOME=str(self.root / "wrong profile")), \
             patch.dict(sys.modules):
            sys.modules.pop("export_background", None)
            installed = load_module("installed_profile_hook", wrapper)
            self.assertEqual(installed.main(), 23)
        hooks = (self.home / "hooks.json").read_text(encoding="utf-8")
        self.assertNotIn(str(bundle), hooks)
        self.assertIn("vaultgoblin_hook.py", hooks)


if __name__ == "__main__":
    unittest.main()
