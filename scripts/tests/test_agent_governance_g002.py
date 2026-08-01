#!/usr/bin/env python3
"""Focused migration checks for direct ARIA skills and optional MemPalace."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[2]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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


def test_mempalace_routing_scenarios() -> None:
    data = json.loads(
        _read(ROOT / "scripts" / "scaffold" / "fixtures" / "routing.json")
    )
    fixtures = {fixture["id"]: fixture for fixture in data["fixtures"]}
    expected = {
        "semantic-recall-current-thesis",
        "semantic-recall-literature-primary",
        "semantic-recall-reviewed-history",
        "semantic-recall-code-direct-source",
    }
    assert expected <= fixtures.keys()
    for fixture_id in expected:
        fixture = fixtures[fixture_id]
        assert fixture["expected_owner_paths"]
        assert fixture["required_outcomes"]
        assert fixture["forbidden_outcomes"]
    assert (
        "primary-source route is available"
        in fixtures["semantic-recall-literature-primary"]["required_outcomes"]
    )
    assert (
        "MemPalace owns code, tests, symbols, or active configuration"
        in fixtures["semantic-recall-code-direct-source"]["forbidden_outcomes"]
    )


def test_route_only_domain_skill_contract() -> None:
    audit = _read(ROOT / "scripts" / "scaffold_audit.py")
    routing = json.loads(
        _read(ROOT / "scripts" / "scaffold" / "fixtures" / "routing.json")
    )

    assert "NATIVE_MINIMAL_SKILLS" not in audit
    retired = {
        "code-review-aria-nbv",
        "counterfactual-rollout-planner",
        "dataset-cache-ops",
        "diagnose-aria",
        "docs-curator",
        "entity-aware-rri",
        "nbv-geometry-contracts",
        "zarr-python",
    }
    for skill_name in retired:
        assert not (ROOT / ".agents" / "skills" / skill_name / "SKILL.md").exists()

    zarr_fixture = next(
        fixture
        for fixture in routing["fixtures"]
        if fixture["id"] == "zarr-storage-api-change"
    )
    assert "expected_tool_refs" not in zarr_fixture
    assert zarr_fixture["expected_owner_paths"] == [
        "aria_nbv/aria_nbv/data_handling/AGENTS.md"
    ]
    fixtures = {fixture["id"]: fixture for fixture in routing["fixtures"]}
    assert fixtures["python-docstring-contract"]["stable_skill_ids"] == [
        "python-standards"
    ]
    for fixture_id in (
        "rerun-offline-inspection",
        "rerun-rollout-zarr-inspection",
        "rerun-sdk-api-change",
    ):
        assert ".agents/skills/rerun-nbv-inspector/SKILL.md" in fixtures[fixture_id][
            "expected_owner_paths"
        ]
    assert fixtures["rerun-sdk-api-change"]["expected_tool_refs"] == [
        "mcp__MCP_DOCKER.get_library_docs"
    ]
    for fixture in fixtures.values():
        assert "expected_skills" not in fixture
        assert "non_goals" not in fixture
        assert fixture["expected_owner_paths"]
        assert fixture["required_outcomes"]
        assert fixture["forbidden_outcomes"]


def test_capture_and_routing_contracts() -> None:
    assert (ROOT / ".agents" / "skills" / "agent-behavior" / "SKILL.md").is_file()
    manifest = tomllib.loads(
        _read(ROOT / ".agents" / "references" / "mattpocock_skills_manifest.toml")
    )
    deprecated_route = next(
        skill for skill in manifest["skill"] if skill["name"] == "design-an-interface"
    )
    assert deprecated_route["posture"] == "skip"
    assert deprecated_route["aria_owner"] == "codebase-design"


if __name__ == "__main__":
    tests = [
        value for name, value in sorted(globals().items()) if name.startswith("test_")
    ]
    for test in tests:
        test()
    print(f"G002 governance migration tests passed: {len(tests)}")
