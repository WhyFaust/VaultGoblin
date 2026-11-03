import ctypes
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
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("export_background", SCRIPTS / "export_background.py")
background = importlib.util.module_from_spec(spec)
spec.loader.exec_module(background)


class BackgroundExportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name) / "Codex $O'Brien with spaces"
        self.home.mkdir()

    def test_timeout_is_logged_and_returns_failure(self):
        with patch.object(background.subprocess, "run", side_effect=subprocess.TimeoutExpired("export", 240)) as run:
            self.assertEqual(background.run(self.home, wait=True), 1)
        self.assertEqual(run.call_args.kwargs["timeout"], 240)
        self.assertIn("ERROR:", (self.home / "shared-knowledge-export.log").read_text(encoding="utf-8"))

    def test_launch_failure_is_logged(self):
        with patch.object(background.subprocess, "Popen", side_effect=OSError("launch failed")):
            self.assertEqual(background.run(self.home, wait=False), 1)
        self.assertIn("launch failed", (self.home / "shared-knowledge-export.log").read_text(encoding="utf-8"))

    @unittest.skipUnless(os.name == "nt", "Windows console allocation")
    def test_detached_worker_has_no_console_and_preserves_output_and_failure(self):
        scripts = self.home / "scripts"
        scripts.mkdir()
        shutil.copy2(SCRIPTS / "export_background.py", scripts)
        event_name = "Local\\VaultGoblin-" + self.home.parent.name
        release_name = event_name + "-release"
        (scripts / "shared_knowledge.py").write_text(
            "import ctypes,json,os,sys\n"
            "from pathlib import Path\n"
            "def contained(root, target):\n"
            "    if not target.resolve().is_relative_to(root.resolve()):\n"
            "        raise ValueError('outside root')\n"
            "    if '--wait' in sys.argv:\n"
            "        (root / 'worker.json').write_text(\n"
            "            json.dumps({'pid': os.getpid(), 'console': ctypes.windll.kernel32.GetConsoleWindow()}), encoding='utf-8')\n"
            "    return target\n"
            "if __name__ == '__main__':\n"
            "    sys.stdout.reconfigure(encoding='utf-8')\n"
            "    sys.stderr.reconfigure(encoding='utf-8')\n"
            "    print('probe stdout', flush=True)\n"
            "    print('probe stderr', file=sys.stderr, flush=True)\n"
            "    home = Path(os.environ['CODEX_HOME'])\n"
            "    (home / 'probe.json').write_text(json.dumps({'console': ctypes.windll.kernel32.GetConsoleWindow()}), encoding='utf-8')\n"
            "    kernel = ctypes.WinDLL('kernel32', use_last_error=True)\n"
            "    kernel.OpenEventW.restype = ctypes.c_void_p\n"
            "    kernel.SetEvent.argtypes = [ctypes.c_void_p]\n"
            "    kernel.CloseHandle.argtypes = [ctypes.c_void_p]\n"
            "    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]\n"
            f"    event = kernel.OpenEventW(2, False, {event_name!r})\n"
            f"    release = kernel.OpenEventW(0x00100000, False, {release_name!r})\n"
            "    kernel.SetEvent(event)\n"
            "    result = kernel.WaitForSingleObject(release, 10000)\n"
            "    kernel.CloseHandle(event)\n"
            "    kernel.CloseHandle(release)\n"
            "    if result != 0:\n"
            "        raise SystemExit(8)\n"
            "    raise SystemExit(7)\n", encoding="utf-8")
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateEventW.restype = ctypes.c_void_p
        kernel.OpenEventW.restype = ctypes.c_void_p
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.SetEvent.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        event = kernel.CreateEventW(None, True, False, event_name)
        self.assertTrue(event, ctypes.get_last_error())
        self.addCleanup(kernel.CloseHandle, event)
        release = kernel.CreateEventW(None, True, False, release_name)
        self.assertTrue(release, ctypes.get_last_error())
        self.addCleanup(kernel.CloseHandle, release)
        launcher = scripts / "export_background.py"
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        result = subprocess.run([str(pythonw), str(launcher), str(self.home)], capture_output=True,
                                text=True, encoding="utf-8", timeout=3)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        self.assertEqual(kernel.WaitForSingleObject(event, 10000), 0)
        worker = json.loads((self.home / "worker.json").read_text(encoding="utf-8"))
        process = kernel.OpenProcess(0x00100000, False, worker["pid"])
        self.assertTrue(process, ctypes.get_last_error())
        self.addCleanup(kernel.CloseHandle, process)
        try:
            self.assertEqual(worker["console"], 0)
            self.assertEqual(json.loads((self.home / "probe.json").read_text(encoding="utf-8"))["console"], 0)
        finally:
            kernel.SetEvent(release)
            self.assertEqual(kernel.WaitForSingleObject(process, 10000), 0)
        log = (self.home / "shared-knowledge-export.log").read_text(encoding="utf-8")
        self.assertIn("probe stdout", log)
        self.assertIn("probe stderr", log)
        self.assertIn("export exit=7", log)
        result = subprocess.run([str(pythonw), str(launcher), str(self.home), "--wait"], capture_output=True,
                                text=True, encoding="utf-8", timeout=15)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (7, "", ""))


if __name__ == "__main__":
    unittest.main()
