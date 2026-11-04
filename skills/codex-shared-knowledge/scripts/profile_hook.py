import json
from pathlib import Path
import sys


def main():
    home = Path(__file__).resolve().parents[1]
    settings_path = home / "shared-knowledge.json"
    if not settings_path.is_file():
        return 0
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    if settings.get("plugin_auto_export") is not True:
        return 0
    runtime = home / "vaultgoblin/runtime"
    sys.path.insert(0, str(runtime))
    from export_background import run
    return run(home, wait=False)


if __name__ == "__main__":
    raise SystemExit(main())
