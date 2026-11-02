"""Linux regressions for concurrent exporters and overlapping source writers."""
from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/shared_knowledge.py'


class WatcherSafetyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='vaultgoblin-safety-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home, self.vault = self.root / 'profile', self.root / 'vault'
        self.native = self.home / 'memories'
        self.native.mkdir(parents=True)
        self.vault.mkdir()
        (self.home / 'shared-knowledge.json').write_text(json.dumps({
            'vault_path': str(self.vault), 'device': 'safety-test'}), encoding='utf-8')
        self.memory = self.native / 'MEMORY.md'
        self.summary = self.native / 'memory_summary.md'
        self.memory.write_text('# OriginalTopic\n\nOriginalFact\n', encoding='utf-8')
        self.summary.write_text('OriginalSummary\n', encoding='utf-8')
        self.output = self.vault / 'Codex Knowledge/devices/safety-test'
        self.attempt = self.root / 'attempt'
        driver = self.root / 'driver.py'
        driver.write_text('''import importlib.util, sys
from pathlib import Path
root=Path(__file__).parent
spec=importlib.util.spec_from_file_location('shared',sys.argv[1])
shared=importlib.util.module_from_spec(spec); spec.loader.exec_module(shared)
original=shared.export
def tracked(home,*args,**kwargs):
    (root/'attempt').write_bytes(b'1')
    return original(home,*args,**kwargs)
shared.export=tracked
try: shared.watch(root/'profile')
except KeyboardInterrupt: pass
''', encoding='utf-8')
        self.driver = driver
        self.process = None
        self.addCleanup(self.stop)

    def start(self):
        self.process = subprocess.Popen([sys.executable, str(self.driver), str(SCRIPT)],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.wait(self.attempt.exists)

    def stop(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.send_signal(2)
            self.process.communicate(timeout=5)

    def wait(self, check):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.fail(self.process.communicate()[1].decode('utf-8'))
            if check():
                return
            time.sleep(0.025)
        self.fail('Expected export was not completed')

    def exported(self, fact):
        return self.output.exists() and any(fact in path.read_text(encoding='utf-8')
                                           for path in self.output.glob('*.md'))

    def unchanged_while_open(self, forbidden):
        deadline = time.monotonic() + 0.3
        while time.monotonic() < deadline:
            self.assertIsNone(self.process.poll(), 'Watcher exited')
            self.assertFalse(self.exported(forbidden), 'An unfinished source reached the export')
            time.sleep(0.025)

    @contextmanager
    def held_export_lock(self):
        with (self.home / 'shared-knowledge-export.lock').open('a+b') as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def test_busy_lock_at_startup_keeps_watcher_alive(self):
        with self.held_export_lock():
            self.start()
            self.unchanged_while_open('OriginalFact')
        self.wait(lambda: self.exported('OriginalFact'))
        self.memory.write_text('# AfterLock\n\nAfterLockFact\n', encoding='utf-8')
        self.wait(lambda: self.exported('AfterLockFact'))

    def test_manual_export_lock_does_not_drop_a_later_change(self):
        self.start()
        self.wait(lambda: self.exported('OriginalFact'))
        with self.held_export_lock():
            self.attempt.unlink(missing_ok=True)
            self.memory.write_text('# WhileLocked\n\nWhileLockedFact\n', encoding='utf-8')
            self.wait(self.attempt.exists)
            self.unchanged_while_open('WhileLockedFact')
        self.wait(lambda: self.exported('WhileLockedFact'))

    def test_writer_open_before_startup_is_not_exported(self):
        with self.memory.open('w', encoding='utf-8') as stream:
            stream.write('# StartupPartial\n\nUnfinishedStartup\n')
            stream.flush()
            self.start()
            self.unchanged_while_open('UnfinishedStartup')
            stream.seek(0)
            stream.truncate()
            stream.write('# StartupComplete\n\nCompleteStartup\n')
        self.wait(lambda: self.exported('CompleteStartup'))
        self.assertFalse(self.exported('StartupPartial'))

    def test_other_source_close_waits_for_the_open_writer(self):
        self.start()
        self.wait(lambda: self.exported('OriginalFact'))
        with self.memory.open('w', encoding='utf-8') as stream:
            stream.write('# CrossSourcePartial\n\nUnfinishedCrossSource\n')
            stream.flush()
            self.summary.write_text('CompletedSummary\n', encoding='utf-8')
            self.unchanged_while_open('UnfinishedCrossSource')
            stream.seek(0)
            stream.truncate()
            stream.write('# CrossSourceComplete\n\nCompleteCrossSource\n')
        self.wait(lambda: self.exported('CompleteCrossSource'))
        self.wait(lambda: self.exported('CompletedSummary'))
        self.assertFalse(self.exported('CrossSourcePartial'))

    def test_read_only_source_handle_does_not_block_export(self):
        self.start()
        self.wait(lambda: self.exported('OriginalFact'))
        with self.memory.open('r', encoding='utf-8'):
            self.summary.write_text('SummaryWhileReaderOpen\n', encoding='utf-8')
            self.wait(lambda: self.exported('SummaryWhileReaderOpen'))

    def test_closing_one_writer_does_not_ignore_another_writer(self):
        self.start()
        self.wait(lambda: self.exported('OriginalFact'))
        with self.memory.open('w', encoding='utf-8') as first, self.memory.open('w', encoding='utf-8') as second:
            second.write('# SecondWriterPartial\n\nSecondWriterUnfinished\n')
            second.flush()
            first.close()
            self.summary.write_text('SummaryDuringSecondWriter\n', encoding='utf-8')
            self.unchanged_while_open('SecondWriterUnfinished')
            second.seek(0)
            second.truncate()
            second.write('# SecondWriterComplete\n\nSecondWriterFinal\n')
        self.wait(lambda: self.exported('SecondWriterFinal'))
        self.assertFalse(self.exported('SecondWriterPartial'))


if __name__ == '__main__':
    unittest.main()
