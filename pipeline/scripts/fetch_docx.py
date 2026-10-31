"""Download a source document through the configured rclone remote."""

import argparse
import subprocess
import sys
from pathlib import Path, PureWindowsPath

try:
    from scripts.config import DEFAULT_STAGING_DIR, load_config
except ModuleNotFoundError:
    from config import DEFAULT_STAGING_DIR, load_config


def fetch_document(filename: str, config: dict) -> Path:
    filename = filename.replace("\\", "/")
    relative = Path(filename)
    if (not filename or relative.is_absolute() or PureWindowsPath(filename).drive
            or ".." in relative.parts or relative.suffix.lower() != ".docx"):
        raise ValueError("Provide a relative .docx path inside the configured remote")
    settings = config.get("rclone", {})
    staging = Path(settings.get("staging_dir") or DEFAULT_STAGING_DIR).expanduser().resolve()
    target = (staging / relative).resolve()
    if not target.is_relative_to(staging):
        raise ValueError("Document destination leaves the staging directory")
    remote = settings.get("remote", "gdrive:").rstrip(":")
    target.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["rclone", "copyto", f"{remote}:{filename}", str(target)],
        capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode:
        raise RuntimeError(f"rclone exited with {result.returncode}: {result.stderr.strip()}")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filename", help="Relative .docx filename in the configured rclone remote")
    args = parser.parse_args()
    try:
        print(fetch_document(args.filename, load_config(strict=True)))
    except (OSError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
