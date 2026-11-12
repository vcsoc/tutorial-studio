"""Actual Pi RPC extension acceptance. No LLM requests or subagents are started."""

import json
from pathlib import Path
import queue
import shutil
import subprocess
import threading

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not shutil.which("pi"), reason="Pi CLI not installed")
@pytest.mark.parametrize("entrypoint", [
    ROOT / "pi/index.ts",
    pytest.param(Path.home() / ".pi/agent/extensions/tutorial-studio.ts", marks=pytest.mark.skipif(not (Path.home() / ".pi/agent/extensions/tutorial-studio.ts").exists(), reason="Optional global loader not installed")),
])
def test_actual_pi_registration_doctor_and_approval_gate(tmp_path, entrypoint):
    process = subprocess.Popen(["pi", "-ne", "-ns", "-np", "--no-themes", "-nc", "--no-mcp", "--no-session", "-e", str(entrypoint), "--mode", "rpc"], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    records = queue.Queue()
    evidence = []

    def read_records():
        for line in iter(process.stdout.readline, b""):
            records.put(json.loads(line))

    threading.Thread(target=read_records, daemon=True).start()

    def send(data):
        process.stdin.write(json.dumps(data).encode() + b"\n")
        process.stdin.flush()

    def request(identifier, payload, approve=False):
        send({"id": identifier, **payload})
        while True:
            record = records.get(timeout=40)
            evidence.append(record)
            assert record.get("type") != "agent_start", "Extension command must not trigger a model request"
            if record.get("type") == "extension_ui_request" and record.get("method") == "input":
                send({"type": "extension_ui_response", "id": record["id"], "value": str(tmp_path / "editor-workspace")})
            if record.get("type") == "extension_ui_request" and record.get("method") == "confirm":
                send({"type": "extension_ui_response", "id": record["id"], "confirmed": approve})
            if record.get("type") == "response" and record.get("id") == identifier:
                assert record["success"], record
                return record

    try:
        commands = request("commands", {"type": "get_commands"})
        assert any(c["name"] == "tutorial" for c in commands["data"]["commands"])
        request("doctor", {"type": "prompt", "message": "/tutorial doctor"})
        messages = request("messages", {"type": "get_messages"})
        message = next(m for m in messages["data"]["messages"] if m.get("customType") == "tutorial-studio")
        actual_doctor = json.loads(message["content"])
        assert actual_doctor["render_ready"] is True
        assert actual_doctor["model_error"] is None
        assert set(actual_doctor["model_hashes"]) == {"model.onnx", "voices.bin"}
        declined = tmp_path / "declined.json"
        request("deny", {"type": "prompt", "message": "/tutorial init " + str(declined)})
        assert not declined.exists()
        approved = tmp_path / "approved.json"
        request("allow", {"type": "prompt", "message": "/tutorial init " + str(approved)}, approve=True)
        assert json.loads(approved.read_text())["schema_version"] == 1
        request("deny-studio", {"type": "prompt", "message": "/tutorial studio"})
        assert not (tmp_path / "editor-workspace").exists()
        assert sum(r.get("method") == "confirm" for r in evidence) == 3
        (tmp_path / "pi-acceptance.json").write_text(json.dumps(evidence, indent=2))
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
