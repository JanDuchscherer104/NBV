#!/usr/bin/env python3
"""Focused migration checks for direct ARIA skills and the MemPalace plugin."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
from typing import TypedDict

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "mempalace-aria-nbv"


class _ServerConfig(TypedDict):
    command: str
    args: list[str]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _prose(path: Path) -> str:
    return " ".join(_read(path).split())


def _load_server(plugin: Path = PLUGIN) -> _ServerConfig:
    raw: object = json.loads(_read(plugin / ".mcp.json"))
    if not isinstance(raw, dict):
        raise ValueError("MCP config must be a JSON object")
    mcp = {key: value for key, value in raw.items() if isinstance(key, str)}
    raw_servers = mcp.get("mcpServers")
    if not isinstance(raw_servers, dict):
        raise ValueError("MCP config field 'mcpServers' must be an object")
    servers = {key: value for key, value in raw_servers.items() if isinstance(key, str)}
    raw_server = servers.get("mempalace")
    if not isinstance(raw_server, dict):
        raise ValueError("MCP config field 'mcpServers.mempalace' must be an object")
    server = {key: value for key, value in raw_server.items() if isinstance(key, str)}
    command = server.get("command")
    if not isinstance(command, str):
        raise ValueError("MCP server field 'command' must be a string")
    args = server.get("args")
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        raise ValueError("MCP server field 'args' must be a list of strings")
    return {"command": command, "args": args}


def _run_server(
    server: _ServerConfig, cwd: Path, *, override: str | None = None
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        capture = temp / "capture.txt"
        stub = temp / "mempalace-mcp"
        stub.write_text(
            '#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$STUB_CAPTURE"\n',
            encoding="utf-8",
        )
        stub.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = f"{temp}{os.pathsep}{env['PATH']}"
        env["STUB_CAPTURE"] = str(capture)
        if override is None:
            env.pop("MEMPALACE_PALACE_PATH", None)
        else:
            env["MEMPALACE_PALACE_PATH"] = override
        command = [server["command"], *server["args"]]
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        forwarded_args = (
            capture.read_text(encoding="utf-8").splitlines() if capture.exists() else []
        )
        return result, forwarded_args


def test_plugin_boundary() -> None:
    assert not (ROOT / ".codex-plugin").exists()
    marketplace = json.loads(_read(ROOT / ".agents" / "plugins" / "marketplace.json"))
    entry = marketplace["plugins"][0]
    assert entry["source"]["path"] == "./plugins/mempalace-aria-nbv"
    manifest = json.loads(_read(PLUGIN / ".codex-plugin" / "plugin.json"))
    assert manifest["name"] == entry["name"] == "mempalace-aria-nbv"
    assert manifest["mcpServers"] == "./.mcp.json"
    assert not ({"skills", "hooks", "apps"} & manifest.keys())
    mcp = json.loads(_read(PLUGIN / ".mcp.json"))
    server = mcp["mcpServers"]["mempalace"]
    assert server["command"] == "bash"
    assert server["args"][:1] == ["-c"]
    assert "CODEX_PLUGIN_ROOT" not in json.dumps(server)
    assert "git rev-parse --show-toplevel" in server["args"][1]
    assert "exec mempalace-mcp --palace" in server["args"][1]


def test_server_loader_rejects_malformed_fields() -> None:
    malformed_servers: tuple[tuple[dict[str, object], str], ...] = (
        ({"command": 1, "args": []}, "'command' must be a string"),
        ({"command": "bash", "args": ["-c", 1]}, "'args' must be a list of strings"),
    )
    for raw_server, expected in malformed_servers:
        with tempfile.TemporaryDirectory() as directory:
            plugin = Path(directory)
            (plugin / ".mcp.json").write_text(
                json.dumps({"mcpServers": {"mempalace": raw_server}}),
                encoding="utf-8",
            )
            try:
                _load_server(plugin)
            except ValueError as exc:
                assert expected in str(exc)
            else:
                raise AssertionError(f"malformed server config accepted: {raw_server}")


def test_direct_skill_discovery_shape() -> None:
    skill = ROOT / ".agents" / "skills" / "aria-grill"
    assert skill.is_dir()
    assert not (ROOT / ".agents" / "skills" / "plan-grill").exists()
    assert "name: aria-grill" in _read(skill / "SKILL.md")
    assert 'display_name: "Aria Grill"' in _read(skill / "agents" / "openai.yaml")


def test_capture_and_routing_contracts() -> None:
    root_guidance = _prose(ROOT / "AGENTS.md")
    behavior = _prose(ROOT / ".agents" / "skills" / "agent-behavior" / "SKILL.md")
    grill = _prose(ROOT / ".agents" / "skills" / "aria-grill" / "SKILL.md")
    assert "capture is owned by `agent-behavior`" in root_guidance
    assert "system or developer instructions" not in root_guidance
    for exclusion in (
        "system or developer",
        "earlier messages",
        "tool output",
        "transcripts",
        "markup tags",
    ):
        assert exclusion in behavior
    assert "Repository policy routes implicit ARIA use" in root_guidance
    assert "explicit user invocation overrides" in root_guidance
    assert "sole ARIA routing gateway" not in grill
    for capability in (
        "codebase-design",
        "improve-codebase-architecture",
        "domain-modeling",
        "aria-nbv-mermaid",
        "visualize",
    ):
        assert f"`{capability}`" in grill
    assert "`DESIGN-IT-TWICE` workflow" in grill
    assert "`design-an-interface`" not in grill
    manifest = tomllib.loads(
        _read(ROOT / ".agents" / "references" / "mattpocock_skills_manifest.toml")
    )
    deprecated_route = next(
        skill for skill in manifest["skill"] if skill["name"] == "design-an-interface"
    )
    assert deprecated_route["posture"] == "skip"
    assert deprecated_route["aria_owner"] == "codebase-design"
    assert "DESIGN-IT-TWICE" in deprecated_route["reason"]
    assert "explicitly invoke its available installed skill" in grill
    assert "continue with source-grounded" in grill
    assert "perform only read-only grounding and questions" in grill
    assert "Do not implement or write durable glossary" in grill


def test_launcher_from_root_and_nested_cwd() -> None:
    expected = str(ROOT / ".artifacts" / "mempalace" / "palace")
    server = _load_server()
    for cwd in (ROOT, ROOT / "plugins" / "mempalace-aria-nbv"):
        result, forwarded_args = _run_server(server, cwd)
        assert result.returncode == 0, result.stderr
        assert forwarded_args == ["--palace", expected]


def test_launcher_fails_closed_and_honors_override() -> None:
    server = _load_server()
    with tempfile.TemporaryDirectory() as directory:
        outside = Path(directory)
        failed, failed_args = _run_server(server, outside)
        assert failed.returncode == 2
        assert "not inside a Git repository" in failed.stderr
        assert failed_args == []
        override = "/tmp/explicit-aria-palace"
        succeeded, succeeded_args = _run_server(server, outside, override=override)
        assert succeeded.returncode == 0, succeeded.stderr
        assert succeeded_args == ["--palace", override]


def test_temp_cache_startup_shape() -> None:
    with tempfile.TemporaryDirectory() as directory:
        cached_plugin = Path(directory) / "cache" / "mempalace-aria-nbv" / "local"
        shutil.copytree(PLUGIN, cached_plugin)
        server = _load_server(cached_plugin)
        result, forwarded_args = _run_server(server, ROOT / "plugins")
        assert result.returncode == 0, result.stderr
        assert forwarded_args == [
            "--palace",
            str(ROOT / ".artifacts" / "mempalace" / "palace"),
        ]


if __name__ == "__main__":
    tests = [
        value for name, value in sorted(globals().items()) if name.startswith("test_")
    ]
    for test in tests:
        test()
    print(f"G002 governance migration tests passed: {len(tests)}")
