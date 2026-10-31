"""wiki_update.py — Thin wrapper around wiki_compile.py for incremental merges.

Equivalent to:
    python3 scripts/wiki_compile.py <slug> --raw-only <path-in-raw> --update-only ...

Exists as a separate command so SKILL.md can map "обнови вики" /
"update wiki page" triggers to a tightly-scoped invocation.

Usage:
    python3 scripts/wiki_update.py <slug> <path-in-raw>
    python3 scripts/wiki_update.py <slug> <path-in-raw> --backend codex --on-conflict ask

All flags after the two positionals are forwarded to wiki_compile.py.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 3:
        print(
            "usage: wiki_update.py <slug> <path-in-raw> [forwarded-flags...]",
            file=sys.stderr,
        )
        return 1

    slug = sys.argv[1]
    raw_path = sys.argv[2]
    forwarded = sys.argv[3:]

    compile_script = Path(__file__).parent / "wiki_compile.py"
    cmd = [
        sys.executable,
        str(compile_script),
        slug,
        "--raw-only",
        raw_path,
        "--update-only",
        *forwarded,
    ]
    proc = subprocess.run(cmd, check=False)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
