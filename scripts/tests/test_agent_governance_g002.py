#!/usr/bin/env python3
"""Focused migration checks for direct ARIA skills and optional MemPalace."""

from __future__ import annotations

import subprocess
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[2]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _prose(path: Path) -> str:
    return " ".join(_read(path).split())


def _tracked_live_runtime_configs() -> list[Path]:
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split("\0")
    return [
        ROOT / relative
        for relative in tracked
        if relative
        and (
            Path(relative).name
            in {
                ".mcp.json",
                "hooks.json",
                "marketplace.json",
                "mcp.json",
                "plugin.json",
                "settings.json",
                "settings.local.json",
            }
            or relative == ".codex/config.toml"
        )
    ]


def test_plugin_boundary() -> None:
    assert not (ROOT / ".codex-plugin").exists()
    assert not (ROOT / "plugins" / "mempalace-aria-nbv").exists()
    assert not (ROOT / ".agents" / "plugins" / "marketplace.json").exists()

    makefile = _read(ROOT / "Makefile")
    assert "memory-mine" not in makefile
    assert "python -m mempalace" not in makefile
    assert "$(PYTHON_INTERPRETER) -m mempalace" not in makefile

    config = _read(ROOT / ".codex" / "config.example.toml")
    assert "uv tool install 'mempalace==3.6.0'" in config
    assert "codex plugin marketplace add MemPalace/mempalace --ref v3.6.0" in config
    assert "codex plugin add mempalace@mempalace" in config
    assert "NONE-to-ON_INSTALL" in config
    assert "plugins/mempalace-aria-nbv" not in config

    ignored = _read(ROOT / ".gitignore").splitlines()
    assert "/mempalace.yaml" in ignored
    assert "/entities.json" in ignored

    root_policy = _prose(ROOT / "AGENTS.md")
    owner_policy = _prose(ROOT / ".agents" / "references" / "human_owner_intent.md")
    assert "official upstream Codex plugin" in root_policy
    assert "`aria-nbv` wing" in root_policy
    for allowed in ("reviewed debriefs", "canonical state", "tracked TeX"):
        assert allowed in owner_policy
    for excluded in ("raw transcript stores", "downloaded PDF", "credentials"):
        assert excluded in owner_policy
    assert "never promotes content into repository truth automatically" in owner_policy


def test_no_tracked_mempalace_runtime_config() -> None:
    runtime_configs = _tracked_live_runtime_configs()
    assert ROOT / ".gemini" / "settings.json" in runtime_configs
    offenders = [
        path.relative_to(ROOT).as_posix()
        for path in runtime_configs
        if "mempalace" in _read(path).lower()
    ]
    assert not offenders, f"tracked runtime configs invoke MemPalace: {offenders}"


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


if __name__ == "__main__":
    tests = [
        value for name, value in sorted(globals().items()) if name.startswith("test_")
    ]
    for test in tests:
        test()
    print(f"G002 governance migration tests passed: {len(tests)}")
