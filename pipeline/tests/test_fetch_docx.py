from types import SimpleNamespace

import pytest

from scripts import fetch_docx, process


def test_fetch_uses_argument_list_and_supports_unicode_paths(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(fetch_docx.subprocess, "run", lambda cmd, **kw: (
        calls.append((cmd, kw)) or SimpleNamespace(returncode=0, stderr="")
    ))
    result = fetch_docx.fetch_document("Папка/Мой документ.docx", {
        "rclone": {"staging_dir": str(tmp_path), "remote": "drive:"},
    })
    assert result == tmp_path / "Папка" / "Мой документ.docx"
    cmd, options = calls[0]
    assert cmd == ["rclone", "copyto", "drive:Папка/Мой документ.docx", str(result)]
    assert options == {"capture_output": True, "text": True, "encoding": "utf-8"}


@pytest.mark.parametrize("filename", ["../outside.docx", "/outside.docx", "C:\\file.docx", "report.txt"])
def test_fetch_rejects_paths_outside_staging(tmp_path, monkeypatch, filename):
    def unexpected_call(*args, **kwargs):
        pytest.fail("rclone must not be called for an invalid path")
    monkeypatch.setattr(fetch_docx.subprocess, "run", unexpected_call)
    with pytest.raises(ValueError):
        fetch_docx.fetch_document(filename, {"rclone": {"staging_dir": str(tmp_path)}})
    assert not list(tmp_path.iterdir())


def test_fetch_reports_rclone_error(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_docx.subprocess, "run", lambda *a, **kw:
                        SimpleNamespace(returncode=3, stderr="File not found"))
    with pytest.raises(RuntimeError, match="rclone exited with 3: File not found"):
        fetch_docx.fetch_document("missing.docx", {"rclone": {"staging_dir": str(tmp_path)}})


def test_document_pipeline_uses_current_python_for_download(tmp_path, monkeypatch):
    commands = []
    def fake_run(cmd, desc):
        commands.append(cmd)
        return str(tmp_path / "input.docx")
    monkeypatch.setattr(process, "run", fake_run)
    monkeypatch.setattr(process, "load_config", lambda: {"rclone": {"staging_dir": str(tmp_path)}})
    monkeypatch.setattr(process.sys, "argv", ["process.py", "remote.docx"])
    process.main()
    assert commands[0] == [process.sys.executable, str(process.SCRIPTS_DIR / "fetch_docx.py"), "remote.docx"]
