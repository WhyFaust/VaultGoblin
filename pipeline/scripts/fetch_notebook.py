"""fetch_notebook.py — Download curated notes from a NotebookLM notebook
and serialize them into the parsed-JSON format consumed by atomize.py.

This makes NotebookLM a first-class input source alongside .docx files.
You curate material in NotebookLM (add sources, ask the chat, save answers
as notes, create notes manually). Then run this script to pull every note
in the notebook as a single batch; atomize.py will see the whole corpus
at once and can build wikilinks across notes from different sources.

Usage:
    # Basic: pull text notes only
    python3 scripts/fetch_notebook.py <notebook_id>

    # Include indexed source fulltext as extra sections
    python3 scripts/fetch_notebook.py <notebook_id> --include-sources

    # Include existing mind map(s) as a topic-hierarchy section
    python3 scripts/fetch_notebook.py <notebook_id> --include-mindmap

    # Use a non-default NotebookLM profile (multi-account setups)
    python3 scripts/fetch_notebook.py <notebook_id> --profile work

    # Write to an explicit output path
    python3 scripts/fetch_notebook.py <notebook_id> -o /tmp/nb.json

Output JSON schema (identical to parse_docx.py):
{
  "source_file": "NotebookLM: <notebook title>",
  "heading_depth_offset": 0,
  "sections": [
    {"heading": "<note title>", "level": 1, "paragraphs": ["..."]},
    ...
  ],
  "_notebooklm": {
      "notebook_id": "...",
      "notebook_title": "...",
      "notes_count": N,
      "sources_count": N,
      "mindmaps_count": N
  }
}

Prerequisites:
    pip install "notebooklm-py[browser]"
    playwright install chromium
    notebooklm login
"""

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

try:
    from scripts.config import DEFAULT_STAGING_DIR, load_config
except ModuleNotFoundError:
    from config import DEFAULT_STAGING_DIR, load_config


def _import_notebooklm_client():
    """Import NotebookLMClient lazily so --help works without the package."""
    try:
        from notebooklm import NotebookLMClient  # type: ignore[import-not-found]
    except ImportError as exc:
        print(
            f"{AUTH_ERROR_MARKER}: notebooklm-py is not installed.\n"
            "Run the one-shot installer+login script:\n"
            "  python3 scripts/notebooklm_setup.py\n"
            "This installs the package, Playwright Chromium, and logs you in.",
            file=sys.stderr,
        )
        raise SystemExit(AUTH_EXIT_CODE) from exc
    return NotebookLMClient


# ── Auth pre-flight ────────────────────────────────────────────────────────────


AUTH_ERROR_MARKER = "NOTEBOOKLM_AUTH_REQUIRED"
AUTH_EXIT_CODE = 2


def _notebooklm_auth_paths() -> list[Path]:
    """Return candidate locations where notebooklm-py stores session cookies.

    Honors two forms of upstream configuration:
      1. `NOTEBOOKLM_HOME` env var (via `notebooklm.paths.get_storage_path()`)
      2. legacy hard-coded defaults under `~/.notebooklm` and `~/.config/notebooklm`

    The `NOTEBOOKLM_AUTH_JSON` env var (inline session JSON) is checked
    separately by `check_auth_or_exit()`, because it is not a path.
    """
    paths: list[Path] = []
    try:
        from notebooklm.paths import get_storage_path  # type: ignore[import-not-found]
        paths.append(Path(get_storage_path()))
    except Exception:
        # Upstream package missing or older — fall through to legacy fallbacks.
        pass

    home = Path.home()
    legacy = [
        home / ".notebooklm" / "storage_state.json",
        home / ".config" / "notebooklm" / "storage_state.json",
        home / ".notebooklm" / "default" / "storage_state.json",
    ]
    for p in legacy:
        if p not in paths:
            paths.append(p)
    return paths


def check_auth_or_exit() -> None:
    """Exit with a distinctive marker if the user has not run `notebooklm login`.

    Accepts three forms of authentication, in order of preference:
      1. `NOTEBOOKLM_AUTH_JSON` env var with inline session JSON (upstream
         escape hatch for non-interactive / containerized setups).
      2. The upstream-computed storage path from `notebooklm.paths`.
      3. Legacy locations under `~/.notebooklm` / `~/.config/notebooklm`.

    Claude Code / Codex / any agent consuming this pipeline can detect
    `NOTEBOOKLM_AUTH_REQUIRED` on stderr (plus exit code 2) and prompt the
    user to authenticate, or run `notebooklm login` directly.
    """
    if os.environ.get("NOTEBOOKLM_AUTH_JSON"):
        return

    if any(path.exists() for path in _notebooklm_auth_paths()):
        return

    print(
        f"{AUTH_ERROR_MARKER}: No NotebookLM session found.\n"
        "You are not logged in to NotebookLM.\n"
        "Run this one-shot installer+login script (it handles everything):\n"
        "  python3 scripts/notebooklm_setup.py\n"
        "It installs notebooklm-py[browser], Playwright Chromium, and opens\n"
        "a browser window so you can sign in with your Google account.\n"
        "After it finishes, rerun this command.\n"
        "Alternatively, set NOTEBOOKLM_HOME to your session directory, "
        "or pass NOTEBOOKLM_AUTH_JSON with an inline session JSON.",
        file=sys.stderr,
    )
    raise SystemExit(AUTH_EXIT_CODE)


# ── Helpers ────────────────────────────────────────────────────────────────────


_SLUG_NON_WORD = re.compile(r"[^\w\s-]", flags=re.UNICODE)
_SLUG_WHITESPACE = re.compile(r"[-\s]+")


def slugify(text: str) -> str:
    """Filesystem-safe slug for staging filenames."""
    cleaned = _SLUG_NON_WORD.sub("", text or "").strip()
    cleaned = _SLUG_WHITESPACE.sub("-", cleaned)
    return cleaned.lower() or "notebook"


def content_to_paragraphs(content: str) -> list[str]:
    """Split markdown/plain text into non-empty paragraph strings."""
    if not content:
        return []
    chunks = re.split(r"\n\s*\n", content.strip())
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _coerce_notebook_title(notebook_obj, notebook_id: str) -> str:
    title = getattr(notebook_obj, "title", None)
    return title or f"Notebook {notebook_id}"


# ── Core fetcher ───────────────────────────────────────────────────────────────


async def fetch_notebook_data(
    notebook_id: str,
    *,
    include_sources: bool = False,
    include_mindmap: bool = False,
    profile: str | None = None,
) -> dict:
    """Pull notes (and optionally sources/mindmap) from a NotebookLM notebook.

    Returns a dict in parse_docx.py's output format so the rest of the
    pipeline (atomize → generate → write) can consume it unchanged.
    """
    NotebookLMClient = _import_notebooklm_client()  # pyright: ignore[reportGeneralTypeIssues]

    from_storage_kwargs: dict = {}
    if profile:
        from_storage_kwargs["profile"] = profile

    sections: list[dict] = []
    notes_count = 0
    sources_count = 0
    mindmaps_count = 0
    notebook_title = f"Notebook {notebook_id}"

    async with await NotebookLMClient.from_storage(**from_storage_kwargs) as client:
        # Resolve notebook title (best-effort; some API versions don't expose .get)
        try:
            notebooks = await client.notebooks.list()
            for nb in notebooks:
                if getattr(nb, "id", None) == notebook_id:
                    notebook_title = _coerce_notebook_title(nb, notebook_id)
                    break
        except Exception as exc:
            print(f"WARNING: Could not list notebooks ({exc}); using id as title.", file=sys.stderr)

        # ── Notes ──────────────────────────────────────────────────────────────
        print(f">> Fetching notes from '{notebook_title}'...", file=sys.stderr)
        try:
            note_refs = await client.notes.list(notebook_id)
        except Exception as exc:
            print(f"ERROR: Could not list notes: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

        print(f"   Found {len(note_refs)} notes in notebook", file=sys.stderr)

        for i, note_ref in enumerate(note_refs, 1):
            note_id = getattr(note_ref, "id", None)
            if not note_id:
                continue
            try:
                note = await client.notes.get(notebook_id, note_id)
            except Exception as exc:
                print(f"   [error] note {note_id}: {exc}", file=sys.stderr)
                continue
            if note is None:
                continue

            title = getattr(note, "title", None) or f"Untitled Note {i}"
            content = getattr(note, "content", None) or ""
            paragraphs = content_to_paragraphs(content)
            if not paragraphs:
                print(f"   [skip] empty note: {title}", file=sys.stderr)
                continue

            sections.append({
                "heading": title,
                "level": 1,
                "paragraphs": paragraphs,
            })
            notes_count += 1
            print(
                f"   [{i}/{len(note_refs)}] {title} ({len(paragraphs)} paragraphs)",
                file=sys.stderr,
            )

        # ── Sources (optional) ─────────────────────────────────────────────────
        if include_sources:
            print(">> Fetching source fulltext...", file=sys.stderr)
            try:
                src_refs = await client.sources.list(notebook_id)
            except Exception as exc:
                print(f"WARNING: Could not list sources: {exc}", file=sys.stderr)
                src_refs = []

            for src in src_refs:
                src_id = getattr(src, "id", None)
                if not src_id:
                    continue
                src_title = getattr(src, "title", None) or src_id
                try:
                    fulltext = await client.sources.get_fulltext(notebook_id, src_id)
                except Exception as exc:
                    print(f"   [error] source {src_title}: {exc}", file=sys.stderr)
                    continue
                if not fulltext:
                    continue
                # Upstream returns a `SourceFulltext` dataclass with a
                # `.content: str` field, not a raw string. Older/mocked shims
                # may return a plain string, so accept both.
                if isinstance(fulltext, str):
                    text = fulltext
                else:
                    text = getattr(fulltext, "content", "") or ""
                if not text:
                    continue
                paragraphs = content_to_paragraphs(text)
                if not paragraphs:
                    continue
                sections.append({
                    "heading": f"Source: {src_title}",
                    "level": 1,
                    "paragraphs": paragraphs,
                })
                sources_count += 1
                print(f"   [src] {src_title} ({len(paragraphs)} paragraphs)", file=sys.stderr)

        # ── Mind maps (optional) ───────────────────────────────────────────────
        if include_mindmap:
            print(">> Fetching mind map(s)...", file=sys.stderr)
            try:
                mindmaps = await client.notes.list_mind_maps(notebook_id)
            except Exception as exc:
                print(f"WARNING: Could not list mind maps: {exc}", file=sys.stderr)
                mindmaps = []

            mind_map_paragraphs: list[str] = []
            for mm in mindmaps:
                raw = getattr(mm, "content", None) or getattr(mm, "data", None) or str(mm)
                if isinstance(raw, (dict, list)):
                    raw = json.dumps(raw, ensure_ascii=False, indent=2)
                paragraphs = content_to_paragraphs(str(raw))
                mind_map_paragraphs.extend(paragraphs)
                mindmaps_count += 1

            if mind_map_paragraphs:
                sections.append({
                    "heading": "Mind Map (topic hierarchy)",
                    "level": 1,
                    "paragraphs": mind_map_paragraphs,
                })
                print(f"   Attached {mindmaps_count} mind map(s)", file=sys.stderr)

    return {
        "source_file": f"NotebookLM: {notebook_title}",
        "heading_depth_offset": 0,
        "sections": sections,
        "_notebooklm": {
            "notebook_id": notebook_id,
            "notebook_title": notebook_title,
            "notes_count": notes_count,
            "sources_count": sources_count,
            "mindmaps_count": mindmaps_count,
        },
    }


# ── CLI ────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch curated notes from a NotebookLM notebook and serialize them "
            "into parsed-JSON format compatible with scripts/atomize.py."
        )
    )
    parser.add_argument("notebook_id", help="NotebookLM notebook ID (from URL or `notebooklm list`)")
    parser.add_argument(
        "-o", "--output",
        help="Output JSON path (default: <staging_dir>/nblm-<slug>-parsed.json)",
    )
    parser.add_argument(
        "--include-sources",
        action="store_true",
        help="Also fetch indexed source fulltext and attach as extra sections",
    )
    parser.add_argument(
        "--include-mindmap",
        action="store_true",
        help="Also attach existing mind map(s) as a topic-hierarchy section",
    )
    parser.add_argument(
        "--profile",
        help="NotebookLM profile name (for multi-account setups)",
    )
    args = parser.parse_args()

    # Pre-flight: verify NotebookLM auth exists before touching the client.
    # Emits AUTH_ERROR_MARKER and exits with code 2 when unauthenticated, so
    # agents can detect the state and trigger `notebooklm login`.
    check_auth_or_exit()

    try:
        result = asyncio.run(
            fetch_notebook_data(
                args.notebook_id,
                include_sources=args.include_sources,
                include_mindmap=args.include_mindmap,
                profile=args.profile,
            )
        )
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: Failed to fetch notebook: {exc}", file=sys.stderr)
        sys.exit(1)

    if not result["sections"]:
        print(
            "ERROR: No notes found in this notebook. "
            "Save notes in NotebookLM first (create them manually or use "
            "`notebooklm ask ... --save-as-note`), then rerun.",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.output:
        output_path = Path(args.output)
    else:
        cfg = load_config()
        staging_root = Path(cfg.get("rclone", {}).get("staging_dir", DEFAULT_STAGING_DIR))
        slug = slugify(result["_notebooklm"]["notebook_title"])
        output_path = staging_root / f"nblm-{slug}-parsed.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    meta = result["_notebooklm"]
    print(
        f"Notebook '{meta['notebook_title']}': "
        f"{meta['notes_count']} notes, "
        f"{meta['sources_count']} sources, "
        f"{meta['mindmaps_count']} mindmaps -> {output_path}",
        file=sys.stderr,
    )
    print(str(output_path))


if __name__ == "__main__":
    main()
