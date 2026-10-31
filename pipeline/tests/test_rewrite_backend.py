import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import doctor, rewrite_backend
from scripts.atomize import load_atomization_prompt
from scripts.process_contacts import load_contacts_prompt
from scripts.process_note import load_personal_prompt


def test_backend_defaults_to_codex_and_respects_explicit_selection(monkeypatch):
    for name in ("VAULTGOBLIN_BACKEND", "CODEX_THREAD_ID", "CODEX_CI", "CLAUDECODE"):
        monkeypatch.delenv(name, raising=False)
    assert rewrite_backend.detect_backend() == "codex"
    monkeypatch.setenv("VAULTGOBLIN_BACKEND", "claude")
    assert rewrite_backend.detect_backend() == "claude"
    assert rewrite_backend.detect_backend("codex") == "codex"


@pytest.mark.parametrize("outcome", ["success", "timeout", "missing", "empty"])
def test_codex_output_is_validated_and_temporary_files_are_cleaned(tmp_path, monkeypatch, outcome):
    targets = []
    monkeypatch.setattr(rewrite_backend, "RUNTIME_DIR", tmp_path)
    def fake_run(cmd, **kwargs):
        output = Path(cmd[cmd.index("-o") + 1])
        targets.append(output)
        assert kwargs["encoding"] == "utf-8"
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(cmd, 1)
        if outcome != "missing":
            output.write_text("result" if outcome == "success" else "", encoding="utf-8")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(rewrite_backend.subprocess, "run", fake_run)
    if outcome == "success":
        assert rewrite_backend.call_codex("prompt", project_root=tmp_path) == "result"
    else:
        with pytest.raises(RuntimeError):
            rewrite_backend.call_codex("prompt", project_root=tmp_path)
    assert targets and not targets[0].parent.exists()


def test_prompt_loaders_use_the_new_prompt_files():
    assert "Document atomization" in load_atomization_prompt()
    assert "Personal Note Processing Contract" in load_personal_prompt()
    assert "Contact Notes Processing Contract" in load_contacts_prompt()
    assert "trigger_phrases" not in load_atomization_prompt()


def test_doctor_checks_only_the_selected_model_cli(tmp_path, monkeypatch, capsys):
    checked = []
    monkeypatch.setattr(doctor, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(doctor, "check_path", lambda *a, **kw: True)
    monkeypatch.setattr(doctor, "check_command", lambda name: checked.append(name) or True)
    monkeypatch.setattr(doctor, "detect_backend", lambda: "codex")
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    monkeypatch.setattr(doctor, "check_python_import", lambda *a: False)
    monkeypatch.setattr(doctor, "check_notebooklm_auth", lambda: None)
    doctor.main()
    assert checked == ["codex"]
    assert "rclone: optional" in capsys.readouterr().out
