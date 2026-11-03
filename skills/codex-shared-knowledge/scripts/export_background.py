import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from shared_knowledge import contained

EXPORT_TIMEOUT = 240


def run(home: Path, wait: bool) -> int:
    home = home.expanduser().resolve()
    log_path = contained(home, home / "shared-knowledge-export.log")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with log_path.open("a", encoding="utf-8") as log:
        try:
            if not wait:
                subprocess.Popen(
                    [sys.executable, "-B", str(Path(__file__).resolve()), str(home), "--wait"],
                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                    creationflags=flags, start_new_session=os.name != "nt",
                )
                return 0
            python = Path(sys.executable).with_name("python.exe") if os.name == "nt" else Path(sys.executable)
            result = subprocess.run(
                [str(python), "-B", str(Path(__file__).with_name("shared_knowledge.py")),
                 "export", "--if-changed", "--quiet"],
                env={**os.environ, "CODEX_HOME": str(home)}, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, creationflags=flags, timeout=EXPORT_TIMEOUT,
            )
            print(f"{datetime.now(timezone.utc).isoformat()} export exit={result.returncode}", file=log)
            return result.returncode
        except (OSError, subprocess.TimeoutExpired) as error:
            print(f"{datetime.now(timezone.utc).isoformat()} ERROR: {error}", file=log)
            return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded shared-knowledge export without a console")
    parser.add_argument("home", type=Path)
    parser.add_argument("--wait", action="store_true")
    args = parser.parse_args()
    return run(args.home, args.wait)


if __name__ == "__main__":
    raise SystemExit(main())
