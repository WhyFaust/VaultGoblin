import argparse
import json

from export_background import run
from shared_knowledge import codex_home, contained, install_runtime


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    home = codex_home()
    config = contained(home, home / "shared-knowledge.json")
    if not config.is_file():
        return 0
    try:
        local = json.loads(config.read_text(encoding="utf-8"))
        if not local.get("plugin_auto_export", False):
            return 0
        runtime = contained(home, home / "vaultgoblin" / "runtime")
        if args.refresh or not (runtime / "export_background.py").is_file():
            runtime = install_runtime(home)
        return run(home, wait=False, launcher=runtime / "export_background.py")
    except (OSError, ValueError, TypeError, AttributeError) as error:
        with (home / "shared-knowledge-export.log").open("a", encoding="utf-8") as log:
            print(f"VaultGoblin hook: {error}", file=log)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
