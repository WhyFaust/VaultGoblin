import argparse
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading


def request(process, messages, identity, method, params):
    process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": identity, "method": method, "params": params}) + "\n")
    process.stdin.flush()
    while True:
        message = messages.get(timeout=30)
        if message.get("id") == identity:
            if "error" in message:
                raise RuntimeError(message["error"])
            return message["result"]


def check(binary, root, environment):
    def command(*arguments):
        completed = subprocess.run(
            [binary, "--disable", "hooks", *arguments], cwd=root, env=environment,
            capture_output=True, text=True, encoding="utf-8", timeout=60, check=True,
        )
        return json.loads(completed.stdout)

    command("plugin", "marketplace", "add", str(root), "--json")
    installed = command("plugin", "add", "vaultgoblin@vaultgoblin", "--json")
    assert installed["pluginId"] == "vaultgoblin@vaultgoblin", installed
    package = Path(installed["installedPath"])
    for skill in ("codex-shared-knowledge", "vaultgoblin-setup"):
        for name in ("SKILL.md", "agents/openai.yaml"):
            relative = Path("skills") / skill / name
            assert (package / relative).read_bytes() == (root / relative).read_bytes(), relative
    assert (package / "skills/codex-shared-knowledge/scripts/profile_hook.py").is_file()
    assert (package / ".codex-plugin/plugin.json").read_bytes() == (root / ".codex-plugin/plugin.json").read_bytes()
    process = subprocess.Popen(
        [binary, "app-server", "--stdio"], cwd=root, env=environment, stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
    )
    messages = queue.Queue()

    def receive():
        for line in process.stdout:
            messages.put(json.loads(line))

    threading.Thread(target=receive, daemon=True).start()
    try:
        request(process, messages, 1, "initialize", {
            "clientInfo": {"name": "vaultgoblin-install-check", "version": "1.0"},
            "capabilities": {"experimentalApi": True},
        })
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "initialized"}) + "\n")
        process.stdin.flush()
        listed = request(process, messages, 2, "hooks/list", {"cwds": [str(root)]})
        hooks = [hook for group in listed["data"] for hook in group["hooks"]
                 if hook.get("pluginId") == "vaultgoblin@vaultgoblin"]
        assert len(hooks) == 3, listed
        assert {hook["eventName"] for hook in hooks} == {"sessionStart", "stop", "sessionEnd"}, hooks
        assert all(hook["trustStatus"] == "untrusted" for hook in hooks), hooks
        detail = request(process, messages, 3, "plugin/read", {
            "pluginName": "vaultgoblin",
            "marketplacePath": str(root / ".agents/plugins/marketplace.json"),
        })["plugin"]
        assert detail["onboardingSkill"]["name"] == "vaultgoblin:vaultgoblin-setup", detail
        assert len(detail["hooks"]) == 3, detail
        interface = detail["summary"]["interface"]
        for field in ("composerIcon", "logo"):
            asset = Path(interface[field])
            assert asset == root / "assets/vaultgoblin.png", interface
            assert (package / "assets/vaultgoblin.png").read_bytes() == asset.read_bytes(), asset
    finally:
        process.terminate()
        process.wait(timeout=10)
        process.stdin.close()
        process.stdout.close()
    print("Installed skill metadata, icon, onboarding and all three untrusted plugin hooks verified.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex", default="codex")
    args = parser.parse_args()
    binary = shutil.which(args.codex)
    if binary is None:
        raise FileNotFoundError(args.codex)
    root = Path(__file__).resolve().parents[3]
    with tempfile.TemporaryDirectory() as temporary:
        home = Path(temporary).resolve() / "Codex profile"
        home.mkdir()
        check(binary, root, {**os.environ, "CODEX_HOME": str(home)})


if __name__ == "__main__":
    main()
