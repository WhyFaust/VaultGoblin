"""Linux integration check; uses a temporary profile, never real Codex memory."""
import json
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/shared_knowledge.py'


def wait_for(check, process, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(process.communicate()[1].decode('utf-8'))
        if check():
            return
        time.sleep(0.025)
    raise AssertionError('Memory change was not exported')


def main():
    with tempfile.TemporaryDirectory(prefix='vaultgoblin-watch-') as temporary:
        root = Path(temporary)
        home, vault = root / 'profile', root / 'vault'
        native = home / 'memories'
        native.mkdir(parents=True)
        vault.mkdir()
        (home / 'shared-knowledge.json').write_text(json.dumps({'vault_path': str(vault), 'device': 'watch-test'}), encoding='utf-8')
        memory = native / 'MEMORY.md'
        memory.write_text('# Topic\n\nStartupFact\n', encoding='utf-8')
        release = root / 'release'
        os.mkfifo(release)
        driver = root / 'driver.py'
        driver.write_text('''import importlib.util, json, sys
from pathlib import Path
root=Path(__file__).parent
spec=importlib.util.spec_from_file_location('shared', sys.argv[1])
shared=importlib.util.module_from_spec(spec); spec.loader.exec_module(shared)
original=shared.export
def tracked(home, if_changed=False):
    (root/'busy').write_bytes(b'1')
    try:
        result=original(home,if_changed=if_changed)
        with (root/'calls').open('ab') as stream: stream.write(b'1\\n')
        if (root/'hold').exists():
            (root/'ready').write_bytes(b'1')
            with (root/'release').open('rb') as stream: stream.read(1)
        return result
    finally: (root/'busy').unlink(missing_ok=True)
shared.export=tracked
try: shared.watch(root/'profile')
except KeyboardInterrupt: pass
''', encoding='utf-8')
        process = subprocess.Popen([sys.executable, str(driver), str(SCRIPT)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = vault / 'Codex Knowledge/devices/watch-test'

        def exported(fact):
            return output.exists() and any(fact in path.read_text(encoding='utf-8') for path in output.glob('*.md'))

        def count():
            path = root / 'calls'
            return len(path.read_bytes().splitlines()) if path.exists() else 0

        def settled():
            wait_for(lambda: not (root / 'busy').exists(), process)

        checks = []
        try:
            wait_for(lambda: exported('StartupFact'), process)
            settled()
            checks.append('startup reconciliation')
            memory.write_text('# Topic\n\nWrittenFact\n', encoding='utf-8')
            wait_for(lambda: exported('WrittenFact'), process)
            settled()
            checks.append('completed in-place write')
            before = count()
            with memory.open('w', encoding='utf-8') as stream:
                stream.write('# Topic\n\nOpenWriteFact')
                stream.flush()
                deadline = time.monotonic() + 0.3
                while time.monotonic() < deadline:
                    assert count() == before
                    time.sleep(0.025)
                stream.write('Finished\n')
            wait_for(lambda: exported('OpenWriteFactFinished'), process)
            settled()
            checks.append('unfinished writes are not exported')
            for fact in ('AtomicFactA', 'AtomicFactB'):
                replacement = native / '.memory-new'
                replacement.write_text('# Topic\n\n' + fact + '\n', encoding='utf-8')
                replacement.replace(memory)
                wait_for(lambda: exported(fact), process)
                settled()
            checks.append('repeated atomic replacement')
            (native / 'memory_summary.md').write_text('SummaryFact\n', encoding='utf-8')
            wait_for(lambda: exported('SummaryFact'), process)
            settled()
            checks.append('new summary file')
            before = count()
            (native / 'raw_memories.md').write_text('UnrelatedFact', encoding='utf-8')
            deadline = time.monotonic() + 0.5
            while time.monotonic() < deadline:
                assert count() == before
                time.sleep(0.025)
            checks.append('unrelated files ignored')
            (root / 'hold').write_bytes(b'1')
            memory.write_text('# Topic\n\nBeforeOverlapFact\n', encoding='utf-8')
            wait_for((root / 'ready').exists, process)
            memory.write_text('# Topic\n\nAfterOverlapFact\n', encoding='utf-8')
            (root / 'hold').unlink()
            with release.open('wb') as stream:
                stream.write(b'1')
            wait_for(lambda: exported('AfterOverlapFact'), process)
            settled()
            checks.append('change during export retained')
            before = count()
            deadline = time.monotonic() + 0.5
            while time.monotonic() < deadline:
                assert count() == before
                time.sleep(0.025)
            checks.append('idle without polling or export calls')
            process.send_signal(2)
            process.communicate(timeout=5)
            config = json.loads((home / 'shared-knowledge.json').read_text(encoding='utf-8'))
            config['project_navigation'] = True
            (home / 'shared-knowledge.json').write_text(json.dumps(config), encoding='utf-8')
            process = subprocess.Popen([sys.executable, str(driver), str(SCRIPT)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            wait_for(lambda: (vault / 'Codex Knowledge/README.md').exists(), process)
            remote = root / 'remote-profile'
            (remote / 'memories').mkdir(parents=True)
            (remote / 'shared-knowledge.json').write_text(json.dumps({'vault_path': str(vault), 'device': 'remote-test'}), encoding='utf-8')
            (remote / 'memories/MEMORY.md').write_text('# Remote topic\n\napplies_to: cwd=/work/remote-app;\nRemoteFact\n', encoding='utf-8')
            spec = importlib.util.spec_from_file_location('shared', SCRIPT)
            shared = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(shared)
            shared.export(remote)
            page = vault / 'Codex Knowledge/Projects/remote-app.md'
            wait_for(lambda: page.exists() and 'Remote topic' in page.read_text(encoding='utf-8'), process)
            checks.append('navigation refreshes when another device arrives')
            print(json.dumps({'passed': len(checks), 'checks': checks, 'export_calls': count()}))
        finally:
            if process.poll() is None:
                process.send_signal(2)
            process.communicate(timeout=5)


if __name__ == '__main__':
    main()
