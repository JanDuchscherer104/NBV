#!/usr/bin/env python3
"""Focused migration checks for direct ARIA skills and optional MemPalace."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from scaffold_audit import load_frontmatter  # noqa: E402


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _tracked_live_runtime_configs(root: Path = ROOT) -> list[Path]:
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split("\0")
    return [
        root / relative
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


def _mempalace_runtime_offenders(root: Path = ROOT) -> list[str]:
    return [
        path.relative_to(root).as_posix()
        for path in _tracked_live_runtime_configs(root)
        if "mempalace" in _read(path).lower()
    ]


def _fixture_owner_paths_exist(root: Path, fixture: dict[str, object]) -> bool:
    owner_paths = fixture.get("expected_owner_paths")
    return isinstance(owner_paths, list) and all(
        isinstance(path, str) and (root / path).is_file() for path in owner_paths
    )


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
    assert not _mempalace_runtime_offenders()


def test_mempalace_runtime_and_owner_path_negative_fixtures() -> None:
    with tempfile.TemporaryDirectory(prefix="g002-negative-") as tmp:
        root = Path(tmp)
        runtime = root / ".mcp.json"
        runtime.write_text(
            '{"mcpServers":{"mempalace":{"command":"mempalace"}}}', encoding="utf-8"
        )
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "add", ".mcp.json"], cwd=root, check=True)
        assert _mempalace_runtime_offenders(root) == [".mcp.json"]
        assert not _fixture_owner_paths_exist(
            root,
            {"expected_owner_paths": ["missing-required-owner.md"]},
        )


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
        assert _fixture_owner_paths_exist(ROOT, fixture)
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


def test_mandatory_graphify_routing_scenarios() -> None:
    data = json.loads(
        _read(ROOT / "scripts" / "scaffold" / "fixtures" / "routing.json")
    )
    fixtures = {fixture["id"]: fixture for fixture in data["fixtures"]}
    expected = {
        "graphify-codebase-navigation",
        "graphify-usable-stale-navigation",
        "graphify-unusable-bootstrap-repair",
    }
    assert expected <= fixtures.keys()
    for fixture_id in expected:
        fixture = fixtures[fixture_id]
        assert _fixture_owner_paths_exist(ROOT, fixture)
        assert fixture["required_outcomes"]
        assert fixture["forbidden_outcomes"]

    assert (
        "worktree Graphify initialization and freshness classification precede eligible navigation"
        in fixtures["graphify-codebase-navigation"]["required_outcomes"]
    )
    assert (
        "fresh Graphify is queried before direct search"
        in fixtures["graphify-codebase-navigation"]["required_outcomes"]
    )
    assert (
        "consequential stale sources are verified exactly"
        in fixtures["graphify-usable-stale-navigation"]["required_outcomes"]
    )
    assert (
        "remaining unusable state is reported before direct-source-only fallback"
        in fixtures["graphify-unusable-bootstrap-repair"]["required_outcomes"]
    )
    assert (
        "direct-source-only fallback is treated as a usable-graph alternative"
        in fixtures["graphify-unusable-bootstrap-repair"]["forbidden_outcomes"]
    )


def test_context7_graphify_api_route_keeps_installed_authority() -> None:
    fixtures = {
        fixture["id"]: fixture
        for fixture in json.loads(
            _read(ROOT / "scripts" / "scaffold" / "fixtures" / "routing.json")
        )["fixtures"]
    }
    fixture = fixtures["context7-graphify-api-change"]
    assert _fixture_owner_paths_exist(ROOT, fixture)
    assert fixture["expected_tool_refs"] == [
        "mcp__MCP_DOCKER.resolve_library_id",
        "mcp__MCP_DOCKER.get_library_docs",
    ]
    assert "supplied exact Context7 ID skips resolution" in fixture["required_outcomes"]
    assert "Context7 is required for local owner lookup" in fixture["forbidden_outcomes"]

    context = _read(ROOT / ".agents" / "skills" / "aria-nbv-context" / "SKILL.md")
    registry = _read(
        ROOT
        / ".agents"
        / "skills"
        / "aria-nbv-context"
        / "references"
        / "context7_library_ids.md"
    )
    provenance = _read(ROOT / ".agents" / "skills" / "agents-db" / "references" / "provenance.md")
    assert "supplied exact ID directly; otherwise resolve it, then get current docs" in context
    assert "/graphify-labs/graphify" in registry
    assert "pinned skill/source" in registry
    assert "exact resolved" in provenance
    assert "paired `repo:` anchors" in provenance


def test_mandatory_graphify_contract_is_later_and_source_subordinate() -> None:
    spec = _read(
        ROOT
        / ".omx"
        / "specs"
        / "deep-interview-aria-nbv-agent-scaffold-target-state.md"
    )
    amendment = "### Accepted 2026-08-01 Graphify remediation amendment"
    supersession = "## Accepted 2026-08-14 Mandatory Graphify Supersession"
    assert spec.index(amendment) < spec.index(supersession)
    assert "Graphify as a navigation prerequisite in every\nCodex worktree" in spec
    assert "Graphify chooses navigation context; it never settles behavior" in spec

    root_guidance = _read(ROOT / "AGENTS.md")
    assert "## Graphify" in root_guidance
    assert "query the byte-identical\n  upstream Graphify skill first" in root_guidance
    optional_tools = root_guidance.split("## Optional Tools And Capture", maxsplit=1)[1]
    assert "Graphify" not in optional_tools

    source_order = _read(ROOT / ".agents" / "references" / "source_order.md")
    intent = _read(ROOT / ".agents" / "references" / "human_owner_intent.md")
    assert "Graphify is mandatory navigation in Codex worktrees" in source_order
    assert "Require the Graphify executable and usable graph artifacts as navigation" in intent
    assert "direct-source-only degraded route" in intent


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
        assert (
            ".agents/skills/rerun-nbv-inspector/SKILL.md"
            in fixtures[fixture_id]["expected_owner_paths"]
        )
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


def test_thesis_context_and_context7_routing() -> None:
    context_path = ROOT / ".agents" / "skills" / "aria-nbv-context" / "SKILL.md"
    metadata = load_frontmatter(context_path)["metadata"]
    assert isinstance(metadata, dict)
    canonical_sources = metadata["canonical_sources"]
    assert isinstance(canonical_sources, list)
    for owner in (
        "docs/typst/thesis/main.typ",
        "docs/typst/shared/glossary.typ",
        "docs/typst/shared/symbols.typ",
        "docs/typst/shared/equations.typ",
        "docs/notation.yml",
        ".agents/skills/aria-nbv-context/references/context7_library_ids.md",
    ):
        assert owner in canonical_sources
        assert (ROOT / owner.partition("#")[0]).is_file()

    context_map = _read(
        ROOT
        / ".agents"
        / "skills"
        / "aria-nbv-context"
        / "references"
        / "context_map.md"
    )
    assert "scripts/nbv_typst_includes.py --thesis --mode outline" in context_map

    context7_registry = _read(
        ROOT
        / ".agents"
        / "skills"
        / "aria-nbv-context"
        / "references"
        / "context7_library_ids.md"
    )
    for library_id in (
        "/websites/hydra_cc",
        "/omry/omegaconf",
        "/websites/zarr_readthedocs_io_en_stable",
        "/websites/mojolang",
        "/websites/jcristharif_msgspec",
    ):
        assert library_id in context7_registry
    for superseded_id in (
        "/websites/modular_mojo",
        "/jcrist/msgspec",
        "/zarr-developers/zarr-python",
    ):
        assert superseded_id not in context7_registry

    typst_skill = _read(ROOT / ".agents" / "skills" / "typst-authoring" / "SKILL.md")
    for library_id in (
        "/websites/typst_app",
        "/typst-community/glossarium",
        "/cetz-package/cetz",
        "/jollywatt/typst-fletcher",
        "/touying-typ/touying",
    ):
        assert library_id in typst_skill

    mermaid_skill = _read(ROOT / ".agents" / "skills" / "aria-nbv-mermaid" / "SKILL.md")
    assert "/mermaid-js/mermaid" in mermaid_skill

    outline_script = ROOT / "scripts" / "nbv_typst_includes.py"
    assert outline_script.is_file()
    default_result = subprocess.run(
        [sys.executable, str(outline_script), "--mode", "includes"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "# docs/typst/thesis/main.typ" in default_result.stdout
    assert "# docs/typst/seminar_paper/main.typ" not in default_result.stdout

    seminar_result = subprocess.run(
        [sys.executable, str(outline_script), "--seminar", "--mode", "includes"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "# docs/typst/seminar_paper/main.typ" in seminar_result.stdout


if __name__ == "__main__":
    tests = [
        value for name, value in sorted(globals().items()) if name.startswith("test_")
    ]
    for test in tests:
        test()
    print(f"G002 governance migration tests passed: {len(tests)}")
