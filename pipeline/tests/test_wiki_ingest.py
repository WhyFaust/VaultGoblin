"""Successful wiki_ingest CLI flows, without external models."""

from unittest.mock import Mock

import pytest

from scripts import wiki_ingest
from scripts.wiki_init import init_wiki_space


@pytest.fixture(params=["absolute", "home-relative"])
def wiki_root(tmp_path, monkeypatch, request):
    vault = tmp_path / "vault"
    root = vault / "LLM Wiki" / "demo"
    init_wiki_space(root, "demo", "corpus", "Demo", "", force=False)
    vault_path = str(vault)
    if request.param == "home-relative":
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        vault_path = "~/vault"
    config = {"vault": {"vault_path": vault_path}}
    monkeypatch.setattr(wiki_ingest, "_load_config", lambda **_: config)
    return root


@pytest.mark.parametrize("input_kind", ["file", "directory", "url"])
def test_main_ingests_without_compiling(tmp_path, monkeypatch, capsys, wiki_root, input_kind):
    source = "https://example.test/source"
    if input_kind != "url":
        source_file = tmp_path / "inputs" / "source.md"
        source_file.parent.mkdir()
        source_file.write_text("# Source\n\nInput content.\n", encoding="utf-8")
        source = str(source_file.parent if input_kind == "directory" else source_file)
    compile_call = Mock()
    monkeypatch.setattr(wiki_ingest.subprocess, "run", compile_call)
    monkeypatch.setattr("sys.argv", ["wiki_ingest.py", "demo", source, "--no-compile"])

    assert wiki_ingest.main() == 0

    compile_call.assert_not_called()
    written = list((wiki_root / "raw" / "docs").glob("*.md"))
    assert len(written) == 1
    text = written[0].read_text(encoding="utf-8")
    expected_body = source if input_kind == "url" else "# Source\n\nInput content.\n"
    assert expected_body in text
    output = capsys.readouterr()
    assert output.out.replace("\\", "/") == f"OK: LLM Wiki/demo/raw/docs/{written[0].name}\n"
    assert output.err == ""


@pytest.mark.parametrize("compile_returncode", [0, 7])
def test_main_chains_compile_and_returns_its_status(
    tmp_path, monkeypatch, wiki_root, compile_returncode
):
    source = tmp_path / "source.md"
    source.write_text("# Source\n", encoding="utf-8")
    compile_call = Mock()
    compile_call.return_value.returncode = compile_returncode
    monkeypatch.setattr(wiki_ingest.subprocess, "run", compile_call)
    monkeypatch.setattr(
        "sys.argv", ["wiki_ingest.py", "demo", str(source), "--backend", "codex"]
    )

    assert wiki_ingest.main() == compile_returncode

    compile_call.assert_called_once_with(
        [
            wiki_ingest.sys.executable,
            str(wiki_ingest.PROJECT_ROOT / "scripts" / "wiki_compile.py"),
            "demo",
            "--since-last-compile",
            "--backend",
            "codex",
        ],
        check=False,
    )
    assert len(list((wiki_root / "raw" / "docs").glob("*.md"))) == 1
