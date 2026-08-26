#!/usr/bin/env python3
"""Focused migration checks for direct ARIA skills and optional MemPalace."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from scaffold_audit import (  # noqa: E402
    RepositoryPointer,
    Skill,
    active_custom_reference_files,
    audit_reference_graph,
    audit_repository_pointer,
    custom_skill_paths,
    deprecated_context7_calls,
    explicit_tool_ids,
    load_frontmatter,
    local_markdown_pointers,
    repository_pointers,
)

CUSTOM_SKILLS = tuple(sorted(custom_skill_paths()))
GRAPHIFY_BUNDLE = ROOT / ".agents" / "skills" / "graphify"
CONTEXT7_REGISTRY = (
    ROOT
    / ".agents"
    / "skills"
    / "aria-nbv-context"
    / "references"
    / "context7_library_ids.md"
)
CONTEXT7_PLUGIN_CALLS = {
    "mcp__codex_apps__context7_resolve_library_id",
    "mcp__codex_apps__context7_query_docs",
}
GRAPHIFY_UPSTREAM_BLOBS = {
    ".graphify_version": "2d72c8d340b915a70b4c553e2a7fe6c8a9b7ea35",
    "SKILL.md": "af3f723c7878b8ca9252af511270511002086ed4",
    "references/add-watch.md": "77844343e140553b7f1bf419e32640568c2014ff",
    "references/exports.md": "242ff868e015b158504dda3ea1992e4cd9686843",
    "references/extraction-spec.md": "4b278b28d3681400286c66af4d61ca2e48bcc211",
    "references/github-and-merge.md": "a41ea06e17c1676483356a2a06504a1bfb0870e4",
    "references/hooks.md": "438b8b16be18480a1e77759b3e74fc8a9e97eae7",
    "references/query.md": "56565eb782951a1f0e1279f851b8a022292f3ac3",
    "references/transcribe.md": "b967f8379998b890945706b3c95fef23b2ec402f",
    "references/update.md": "3632fd41266964bdcf04b58d4359f9364cedfbce",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _git_blob_id(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode()
    return hashlib.sha1(header + content, usedforsecurity=False).hexdigest()


def _context7_ids(text: str) -> set[str]:
    """Return exact backticked registry IDs, not URL path substrings."""
    return {
        token.strip()
        for token in re.findall(r"`([^`\n]+)`", text)
        if re.fullmatch(
            r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?", token.strip()
        )
    }


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


def _is_session_local_review_artifact(path: str) -> bool:
    relative = Path(path)
    return relative.parts[:2] == (".omx", "reviews") and len(relative.parts) > 2


def _raw_review_plan_pointers(text: str) -> list[str]:
    role = r"(?:architect(?:ure)?|critic|critique)"
    path = r"\.omx/plans/[^\s`\"']*"
    return re.findall(
        rf"{path}(?:{role}[^\s`\"']*review|review[^\s`\"']*{role})[^\s`\"']*",
        text,
        flags=re.IGNORECASE,
    )


def _fixture_owner_paths_exist(root: Path, fixture: dict[str, object]) -> bool:
    owner_paths = fixture.get("expected_owner_paths")
    return isinstance(owner_paths, list) and all(
        isinstance(path, str) and (root / path).exists() for path in owner_paths
    )


def _backticked_owner_anchors(text: str) -> list[tuple[str, str]]:
    """Return repository file/anchor references that can be checked exactly."""
    references: list[tuple[str, str]] = []
    for value in re.findall(r"`([^`\n]+#[^`\n]+)`", text):
        relative, anchor = value.rsplit("#", maxsplit=1)
        if (ROOT / relative).is_file():
            references.append((relative, anchor))
    return references


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


def test_custom_skill_discovery_is_dynamic_with_explicit_upstream_exemption() -> None:
    discovered = custom_skill_paths()
    expected = {
        path.resolve()
        for path in (ROOT / ".agents" / "skills").glob("*/SKILL.md")
        if path.parent.name != "graphify"
    }
    assert discovered == expected
    assert (GRAPHIFY_BUNDLE / "SKILL.md").resolve() not in discovered
    assert "APPROVED_CUSTOM_SKILL_PATHS" not in _read(
        ROOT / "scripts/scaffold_audit.py"
    )


def test_custom_skills_use_only_native_name_and_description_frontmatter() -> None:
    for skill_path in CUSTOM_SKILLS:
        with_context = load_frontmatter(skill_path)
        assert set(with_context) == {"name", "description"}, skill_path
        assert with_context["name"] == skill_path.parent.name
        assert isinstance(with_context["description"], str)
        assert with_context["description"].strip()


def test_upstream_graphify_bundle_is_exempt_and_byte_identical() -> None:
    assert GRAPHIFY_BUNDLE / "SKILL.md" not in CUSTOM_SKILLS
    actual_files = {
        path.relative_to(GRAPHIFY_BUNDLE).as_posix()
        for path in GRAPHIFY_BUNDLE.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    assert actual_files == set(GRAPHIFY_UPSTREAM_BLOBS)
    for relative, expected_blob in GRAPHIFY_UPSTREAM_BLOBS.items():
        assert _git_blob_id((GRAPHIFY_BUNDLE / relative).read_bytes()) == expected_blob


def test_custom_skill_conditional_reference_links_exist_directly() -> None:
    link_pattern = re.compile(r"\]\((?:\./)?(references/[^)#]+\.md)(?:#[^)]+)?\)")
    checked_links = 0
    for skill_path in CUSTOM_SKILLS:
        links = link_pattern.findall(_read(skill_path))
        for relative in links:
            checked_links += 1
            assert (skill_path.parent / relative).is_file(), (skill_path, relative)
    assert checked_links > 0


def test_repository_pointer_discovery_and_integrity_boundaries() -> None:
    tmp_parent = ROOT / ".tmp"
    tmp_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="g002-pointer-", dir=tmp_parent) as tmp:
        root = Path(tmp)
        bare_path = root / "bare" / "SKILL.md"
        bare_path.parent.mkdir()
        bare_path.write_text(
            "---\nname: bare\ndescription: Test fixture.\n---\nSee `references/guide.md`.\n",
            encoding="utf-8",
        )
        references = bare_path.parent / "references"
        references.mkdir()
        guide = references / "guide.md"
        guide.write_text(
            "See `orphan.md` or [the leaf](./orphan.md).\n", encoding="utf-8"
        )
        orphan = references / "orphan.md"
        orphan.write_text("# Orphan\n", encoding="utf-8")
        pointers = local_markdown_pointers(guide, _read(guide))
        assert "orphan.md" not in pointers
        assert "./orphan.md" in pointers
        bare_skill = Skill(
            bare_path,
            "bare",
            "bare",
            "Test fixture.",
            1,
            _read(bare_path),
        )
        assert not audit_reference_graph([bare_skill])

        package_index = root / "package" / "references" / "packages" / "index.md"
        package_index.parent.mkdir(parents=True)
        package_index.write_text("See [booktabs](./booktabs.md).\n", encoding="utf-8")
        booktabs = package_index.parent / "booktabs.md"
        booktabs.write_text("# Booktabs\n", encoding="utf-8")
        assert "./booktabs.md" in local_markdown_pointers(
            package_index, _read(package_index)
        )

        source = root / "owners.md"
        source.write_text(
            "[missing](./missing.qmd) "
            "[outside](/tmp/outside.md) "
            "`.agents/missing.toml` `docs/` `scripts/check.py` "
            "`https://example.com/docs/a.md` `git status` "
            "`docs/*.md` `.omx/state/.../runtime.json` `<owner>/file.md`\n",
            encoding="utf-8",
        )
        raw = {pointer.raw for pointer in repository_pointers(source, _read(source))}
        assert raw == {
            "./missing.qmd",
            "/tmp/outside.md",
            ".agents/missing.toml",
            "docs/",
            "scripts/check.py",
        }
        missing = next(
            pointer
            for pointer in repository_pointers(source, _read(source))
            if pointer.raw == "./missing.qmd"
        )
        assert any(
            "does not exist" in error for error in audit_repository_pointer(missing)[1]
        )
        absolute = next(
            pointer
            for pointer in repository_pointers(source, _read(source))
            if pointer.raw == "/tmp/outside.md"
        )
        assert any(
            "escapes repo root" in error
            for error in audit_repository_pointer(absolute)[1]
        )

        markdown = root / "anchor.md"
        markdown.write_text("# Present\n", encoding="utf-8")
        typst = root / "anchor.typ"
        typst.write_text("= Present <ssec:present>\n", encoding="utf-8")
        for target in (
            RepositoryPointer(
                source, "./anchor.md#present", "./anchor.md", "present", "markdown"
            ),
            RepositoryPointer(
                source,
                "./anchor.typ#ssec:present",
                "./anchor.typ",
                "ssec:present",
                "backtick",
            ),
        ):
            assert audit_repository_pointer(target)[1] == []

        outside = root / "outside.md"
        outside.symlink_to("/tmp")
        escaped = RepositoryPointer(
            source, "./outside.md", "./outside.md", "", "markdown"
        )
        assert any(
            "escapes repo root" in error
            for error in audit_repository_pointer(escaped)[1]
        )


def test_context7_ids_and_plugin_calls_have_one_owner() -> None:
    skill_files = tuple(
        path
        for path in (ROOT / ".agents" / "skills").rglob("*.md")
        if "graphify" not in path.parts
    )
    registry_text = _read(CONTEXT7_REGISTRY)
    registry_ids = _context7_ids(registry_text)
    assert registry_ids
    assert "/facebookresearch/efm3d" not in _context7_ids(
        "https://github.com/facebookresearch/efm3d"
    )

    for library_id in registry_ids:
        owners = [
            path for path in skill_files if library_id in _context7_ids(_read(path))
        ]
        assert owners == [CONTEXT7_REGISTRY], (library_id, owners)

    collision = f"`{next(iter(CONTEXT7_PLUGIN_CALLS))}_suffix`"
    assert not (CONTEXT7_PLUGIN_CALLS & explicit_tool_ids(collision))

    call_owners = {
        call: [path for path in skill_files if call in explicit_tool_ids(_read(path))]
        for call in CONTEXT7_PLUGIN_CALLS
    }
    assert call_owners == {call: [CONTEXT7_REGISTRY] for call in CONTEXT7_PLUGIN_CALLS}


def test_active_skill_routes_contain_no_deprecated_docker_context7_calls() -> None:
    deprecated = {
        "mcp__MCP_DOCKER.resolve_library_id",
        "mcp__MCP_DOCKER.get_library_docs",
    }
    positive_routes = {
        fixture["id"]: fixture
        for fixture in json.loads(
            _read(ROOT / "scripts" / "scaffold" / "fixtures" / "routing.json")
        )["fixtures"]
        if fixture.get("expected_tool_refs")
    }
    for fixture_id, fixture in positive_routes.items():
        assert not deprecated.intersection(fixture["expected_tool_refs"]), fixture_id
        if CONTEXT7_PLUGIN_CALLS.intersection(fixture["expected_tool_refs"]):
            assert (
                ".agents/skills/aria-nbv-context/references/context7_library_ids.md"
                in fixture["expected_owner_paths"]
            ), fixture_id
    assert not deprecated_context7_calls(active_custom_reference_files())

    with tempfile.TemporaryDirectory(prefix="g002-context7-") as tmp:
        reference = Path(tmp) / "references" / "active.md"
        reference.parent.mkdir()
        reference.write_text(
            "Call mcp__MCP_DOCKER.get_library_docs here.\n", encoding="utf-8"
        )
        assert deprecated_context7_calls((reference,)) == {
            reference: {"mcp__MCP_DOCKER.get_library_docs"}
        }


def test_existing_routing_families_remain_declared() -> None:
    routing = json.loads(
        _read(ROOT / "scripts" / "scaffold" / "fixtures" / "routing.json")
    )
    fixtures = {fixture["id"]: fixture for fixture in routing["fixtures"]}
    expected_families = {
        "graphify-codebase-navigation",
        "graphify-usable-stale-navigation",
        "graphify-unusable-bootstrap-repair",
        "context7-graphify-api-change",
        "context7-pytorch3d-conceptual-plan",
        "context7-not-needed-target-rri-section",
        "active-thesis-scientific-language",
        "package-contract-owner",
        "rerun-offline-inspection",
        "rerun-rollout-zarr-inspection",
        "rerun-sdk-api-change",
        "semantic-recall-current-thesis",
        "semantic-recall-literature-primary",
        "semantic-recall-reviewed-history",
        "semantic-recall-code-direct-source",
        "code-index-frustum-rendering",
        "concrete-failure",
    }
    assert expected_families <= fixtures.keys()
    for fixture_id in expected_families:
        fixture = fixtures[fixture_id]
        assert _fixture_owner_paths_exist(ROOT, fixture), fixture_id
        assert fixture["required_outcomes"], fixture_id
        assert fixture["forbidden_outcomes"], fixture_id


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
            ".agents/skills/aria-nbv-context/references/semantic-memory-boundary.md"
            in fixture["expected_owner_paths"]
        )
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
        "Graphify query handles broad questions, path handles relationships, and explain handles focused concepts before raw search"
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
        "mcp__codex_apps__context7_query_docs",
    ]
    assert fixture["forbidden_tool_refs"] == [
        "mcp__MCP_DOCKER.resolve_library_id",
        "mcp__MCP_DOCKER.get_library_docs",
    ]
    assert "supplied exact Context7 ID skips resolution" in fixture["required_outcomes"]
    assert (
        "one focused seed query is issued per external concept"
        in fixture["required_outcomes"]
    )
    assert (
        "Context7 is required for local owner lookup" in fixture["forbidden_outcomes"]
    )

    context = _read(ROOT / ".agents" / "skills" / "aria-nbv-context" / "SKILL.md")
    registry = _read(
        ROOT
        / ".agents"
        / "skills"
        / "aria-nbv-context"
        / "references"
        / "context7_library_ids.md"
    )
    provenance = _read(
        ROOT / ".agents" / "skills" / "agents-db" / "references" / "provenance.md"
    )
    assert "Use a supplied exact ID directly; otherwise call" in context
    assert "Do not use Docker MCP Context7" in context
    assert "/graphify-labs/graphify" in registry
    assert "seed menu, not one broad\nquery" in registry
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
    lifecycle = "## Accepted 2026-08-19 Graphify Lifecycle And Routing Supersession"
    context_hierarchy = (
        "## Accepted 2026-08-19 Context Hierarchy And Context7 Plugin Supersession"
    )
    pointer_retirement = (
        "## Accepted 2026-08-21 Source-Order Compatibility Pointer Retirement"
    )
    assert spec.index(amendment) < spec.index(supersession)
    assert spec.index(supersession) < spec.index(lifecycle)
    assert spec.index(lifecycle) < spec.index(context_hierarchy)
    assert spec.index(context_hierarchy) < spec.index(pointer_retirement)
    assert "Graphify as a navigation prerequisite in every\nCodex worktree" in spec
    assert "Graphify chooses navigation context; it never settles behavior" in spec
    assert "upstream Graphify `query`, `path`, or\n`explain` before raw search" in spec
    assert "single current owner of\nthe hierarchical source map" in spec
    assert "retires `.agents/references/source_order.md` completely" in spec
    assert "mcp__codex_apps__context7_query_docs" in spec
    amendment_text = spec.split(amendment, 1)[1].split(supersession, 1)[0]
    assert "Graphify 0.9.31" in amendment_text
    assert "4fe11092ccbe9f543608f140c790f68d5d83cae4" in amendment_text
    lifecycle_text = spec.split(lifecycle, 1)[1].split(context_hierarchy, 1)[0]
    assert "Graphify\n0.9.48" in lifecycle_text
    assert "b2cd36267456c166788c95be6e68574064a92a42" in lifecycle_text

    root_guidance = _read(ROOT / "AGENTS.md")
    assert "## Graphify And Context7 Plugin" in root_guidance
    assert "upstream Graphify `query`, `path`, and `explain`" in root_guidance
    optional_tools = root_guidance.split("## Optional Tools And Capture", maxsplit=1)[1]
    assert "Graphify" not in optional_tools

    context = _read(ROOT / ".agents" / "skills" / "aria-nbv-context" / "SKILL.md")
    intent = _read(ROOT / ".agents" / "references" / "human_owner_intent.md")
    assert "## Branch Index" in context
    assert "## Graphify Branch" not in context
    assert "## Context7 Plugin Branch" not in context
    assert (
        "Require the Graphify executable and usable graph artifacts as navigation"
        in intent
    )
    assert "direct-source-only degraded route" in intent


def test_agents_db_loads_upstream_graphify_with_mandatory_aria_reconciliation() -> None:
    internal_db = _read(ROOT / ".agents" / "AGENTS_INTERNAL_DB.md")
    upstream = """## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query \"<question>\"` when graphify-out/graph.json exists. Use `graphify path \"<A>\" \"<B>\"` for relationships and `graphify explain \"<concept>\"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost)."""
    assert upstream in internal_db
    assert internal_db.count("## graphify") == 1
    reconciliation = internal_db.split("### ARIA-NBV mandatory reconciliation", 1)[1]
    assert "Graphify is mandatory navigation in Codex worktrees" in reconciliation
    assert "exact repository\nsources remain authoritative" in reconciliation
    assert "scripts/check_graphify_freshness.py --json" in reconciliation
    assert "repair or reinitialize `unusable` artifacts" in reconciliation
    assert "treating Graphify as optional" in reconciliation

    active_projection_owners = (
        ROOT / "scripts" / "build_graphify_projection.py",
        ROOT / "scripts" / "tests" / "test_build_graphify_projection.py",
        ROOT / "docs" / "literature" / "README.md",
    )
    for owner in active_projection_owners:
        assert "optional Graphify" not in _read(owner)

    root_guidance = _read(ROOT / "AGENTS.md")
    assert "## Graphify And Context7 Plugin" in root_guidance
    assert "then opens exact owners before consequential" in root_guidance


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

    fixtures = {fixture["id"]: fixture for fixture in routing["fixtures"]}
    for fixture_id, guide in (
        ("zarr-rollout-storage-api", "aria_nbv/aria_nbv/rollouts/AGENTS.md"),
        (
            "zarr-offline-vin-storage-api",
            "aria_nbv/aria_nbv/data_handling/AGENTS.md",
        ),
    ):
        assert "expected_tool_refs" not in fixtures[fixture_id]
        assert guide in fixtures[fixture_id]["expected_owner_paths"]
    assert "entity-rri-implementation" not in fixtures
    assert fixtures["target-admission-protocol"]["expected_owner_paths"] == [
        "aria_nbv/AGENTS.md",
        "aria_nbv/aria_nbv/targets/protocol.py",
    ]
    oracle_routes = {
        "oracle-evidence-construction": "aria_nbv/aria_nbv/oracle/evidence.py",
        "oracle-private-scoring": "aria_nbv/aria_nbv/oracle/_scoring.py",
        "oracle-scene-rri-scoring": "aria_nbv/aria_nbv/oracle/scene_rri.py",
        "oracle-target-rri-scoring": "aria_nbv/aria_nbv/oracle/target_rri.py",
        "oracle-label-dtos": "aria_nbv/aria_nbv/oracle/labels.py",
        "oracle-label-pipeline": "aria_nbv/aria_nbv/oracle/pipelines",
    }
    for fixture_id, owner in oracle_routes.items():
        assert owner in fixtures[fixture_id]["expected_owner_paths"]
        assert (
            "aria_nbv/aria_nbv/oracle/README.md"
            in fixtures[fixture_id]["expected_owner_paths"]
        )
    geometry_routes = {
        "geometry-pose-generation": "aria_nbv/aria_nbv/pose_generation",
        "geometry-rendering-camera": "aria_nbv/aria_nbv/rendering",
        "geometry-vin-frame-contract": "aria_nbv/aria_nbv/vin/AGENTS.md",
    }
    for fixture_id, owner in geometry_routes.items():
        assert owner in fixtures[fixture_id]["expected_owner_paths"]
    assert fixtures["rri-metric-semantics"]["expected_owner_paths"] == [
        "aria_nbv/aria_nbv/rri_metrics/AGENTS.md"
    ]
    assert fixtures["vin-scorer-input-fields"]["expected_owner_paths"] == [
        "aria_nbv/aria_nbv/vin/AGENTS.md"
    ]
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
        "mcp__codex_apps__context7_query_docs"
    ]
    for fixture in fixtures.values():
        assert "expected_skills" not in fixture
        assert "non_goals" not in fixture
        assert fixture["expected_owner_paths"]
        assert fixture["required_outcomes"]
        assert fixture["forbidden_outcomes"]


def test_capture_and_routing_contracts() -> None:
    agent_behavior_path = ROOT / ".agents" / "skills" / "agent-behavior" / "SKILL.md"
    assert agent_behavior_path.is_file()
    agent_behavior = _read(agent_behavior_path)
    assert len(agent_behavior.splitlines()) <= 100
    assert "Load only detail that materially improves" not in agent_behavior
    for invariant in (
        "Surface conflicting interpretations, terminology, and",
        "current owner's smallest interface",
        "demonstrated variation",
        "Lowest shared owner.",
        "consult reviewed intent only when a material choice remains unsettled",
        "remove only debris created by this change",
        "report pre-existing cleanup separately",
        "second source of truth",
    ):
        assert invariant in agent_behavior
    assert "**Workpackage completion, Git, or external action:**" in agent_behavior
    assert "After completing a durable\n  workpackage" in agent_behavior
    descriptor = _read(agent_behavior_path.parent / "agents" / "openai.yaml")
    assert 'short_description: "Owner-first ARIA-NBV preflight"' in descriptor
    assert "scope one traceable lane" in descriptor
    assert "consult reviewed intent only for unsettled choices" in descriptor
    reference_paths = {
        link.split("#", 1)[0]
        for link in re.findall(r"\]\((references/[^)]+)\)", agent_behavior)
    }
    assert reference_paths == {
        "references/durable-capture.md",
        "references/execution-branches.md",
        "references/external-actions.md",
        "references/reviewed-intent.md",
    }
    for reference_path in reference_paths:
        assert (agent_behavior_path.parent / reference_path).is_file()

    intent_reference = _read(
        agent_behavior_path.parent / "references" / "reviewed-intent.md"
    )
    precedence = (
        "1. **Accepted scoped specification.**",
        "2. **Exact owner.**",
        "3. **Accepted plan.**",
        "4. **Reviewed human intent.**",
    )
    offsets = [intent_reference.index(marker) for marker in precedence]
    assert offsets == sorted(offsets)
    assert ".agents/references/human_owner_intent.md" in intent_reference
    assert "Its `Open Choices` are unresolved evidence" in intent_reference
    assert "overrides neither" in intent_reference
    assert "persist it at the smallest exact owner" in intent_reference
    for requirement in (
        "## Candidate Owner Intent",
        "direct user\ninstruction or repeated task evidence",
        "precise, reusable\ncross-task preference",
        "proposed for current-user review",
        "Omit this section for one-off instructions",
        "do not add it to\n`.agents/references/human_owner_intent.md` automatically",
        "current-user\nacceptance",
        "implementation commit from the debrief",
    ):
        assert requirement in intent_reference

    memory = _read(ROOT / ".agents" / "memory" / "README.md")
    assert "### Candidate Owner Intent" in memory
    assert "candidate-intent branch" in memory
    assert "Omit the section otherwise" in memory
    assert "only explicit current-user acceptance" in memory

    execution_branches = _read(
        agent_behavior_path.parent / "references" / "execution-branches.md"
    )
    assert "## Failure-First Diagnosis" in execution_branches
    assert "## Reversible Learning" in execution_branches

    external_actions = _read(
        agent_behavior_path.parent / "references" / "external-actions.md"
    )
    assert "## Local Git Scope" in external_actions
    assert "## External Boundary" in external_actions
    for requirement in (
        "immutable commit link",
        "resolvable review threads",
        "exact-head proof",
        "verdict, architecture,\n  verification, and residual risk",
        "open a draft pull\n  request after its first coherent verified workpackage",
    ):
        assert requirement in external_actions

    conventions = _read(
        ROOT
        / ".agents"
        / "skills"
        / "python-standards"
        / "references"
        / "general_conventions.md"
    )
    for requirement in (
        "composition root",
        "single-consumer private helper local",
        "speculative generic utility bucket",
    ):
        assert requirement in conventions

    skill_style = _read(ROOT / ".agents" / "skills" / "README.md")
    assert "preserve a direct activation condition" in skill_style

    root_guidance = _read(ROOT / "AGENTS.md")
    assert "Failure-first diagnosis uses `agent-behavior`" in root_guidance
    assert "establish the smallest red reproducer" not in root_guidance

    retired_manifest = (
        ROOT / ".agents" / "references" / "mattpocock_skills_manifest.toml"
    )
    assert not retired_manifest.exists()
    for owner in (
        ROOT / ".agents" / "references" / "README.md",
        ROOT / ".agents" / "skills" / "README.md",
        ROOT / ".codex" / "config.example.toml",
        ROOT
        / ".agents"
        / "skills"
        / "academic-writing"
        / "references"
        / "upstream-matt-writing.md",
    ):
        assert "mattpocock_skills_manifest" not in _read(owner)

    routing = json.loads(
        _read(ROOT / "scripts" / "scaffold" / "fixtures" / "routing.json")
    )
    fixtures = {fixture["id"]: fixture for fixture in routing["fixtures"]}
    completion = fixtures["durable-workpackage-completion"]
    assert completion["expected_owner_paths"] == [
        ".agents/skills/agent-behavior/SKILL.md",
        ".agents/skills/agent-behavior/references/external-actions.md",
    ]
    assert completion["required_outcomes"] == [
        "a focused local commit creates a rollback boundary before unrelated work"
    ]

    capture = fixtures["deliberate-angle-bracket-capture-read-only"]
    assert capture["expected_owner_paths"] == [
        "AGENTS.md",
        ".agents/skills/agent-behavior/SKILL.md",
        ".agents/skills/agent-behavior/references/durable-capture.md",
        ".agents/skills/aria-nbv-context/SKILL.md",
    ]
    assert (
        "deliberate user-authored angle-bracket prose activates durable capture"
        in (capture["required_outcomes"])
    )
    assert "read-only wording disables capture routing" in capture["forbidden_outcomes"]
    assert "Deliberate user-authored `<...>` prose" in root_guidance
    assert "including a read-only capture request" in root_guidance
    assert "markup tags" in agent_behavior


def test_qh_guidance_points_to_typst_owners_without_duplicate_policy() -> None:
    docs_guidance = _read(ROOT / "docs" / "AGENTS.md")
    anchors = _backticked_owner_anchors(docs_guidance)
    assert anchors == [
        ("docs/typst/thesis/sections/01-research-questions.typ", "ssec:rq3"),
        ("docs/typst/thesis/sections/01-research-questions.typ", "ssec:rq5"),
        ("docs/typst/thesis/development/roadmap.typ", "ssec:promotion-queue"),
    ]
    for relative_path, anchor in anchors:
        assert f"<{anchor}>" in _read(ROOT / relative_path)
    assert "privileged V0/GT target path is only a sanity or upper-bound route" in (
        docs_guidance
    )
    assert "conditional online bridge is RQ5" in docs_guidance
    assert "M6 scope decision pending M5 evidence" in docs_guidance
    assert "V0 GT actor-visible-target runs as main V1 performance" not in docs_guidance
    assert "only after offline `Q_H` evidence is stable" not in docs_guidance

    fixtures = {
        fixture["id"]: fixture
        for fixture in json.loads(
            _read(ROOT / "scripts" / "scaffold" / "fixtures" / "routing.json")
        )["fixtures"]
    }
    hazard = fixtures["docs-qh-scientific-hazard-routing"]
    assert _fixture_owner_paths_exist(ROOT, hazard)
    assert (
        "privileged V0/GT routes to RQ3 as a sanity or upper-bound path"
        in (hazard["required_outcomes"])
    )
    assert (
        "a stale milestone anchor substitutes for the promotion queue"
        in (hazard["forbidden_outcomes"])
    )

    context = _read(ROOT / ".agents" / "skills" / "aria-nbv-context" / "SKILL.md")
    assert "## Owner Hierarchy" in context
    assert "**Scientific language**" in context
    assert "docs/typst/shared/glossary.typ" in context
    capture_rule = context.split("## Capture Rule", maxsplit=1)[1]
    for destination in (
        "Repo invariant: root or nearest nested `AGENTS.md`",
        "Repeatable workflow: the owning skill's `SKILL.md`",
        "Actionable work: Agents-DB issues, todos, or refactors.",
        "Public narrative or scientific language: the smallest active Quarto/Typst",
    ):
        assert destination in capture_rule


def test_thin_guidance_routes_retain_review_and_package_contracts() -> None:
    root_guidance = _read(ROOT / "AGENTS.md")
    assert "severity-ranked, line-referenced findings" in root_guidance
    assert "P0-P2 PR findings as resolvable GitHub review threads" in root_guidance
    assert "resolve them only\n  after exact-head evidence" in root_guidance
    assert "Architect and\n  critic review outputs stay session-local" in root_guidance

    for route in (
        "Mermaid and thesis-diagram work uses `aria-nbv-mermaid`",
        "Backlog or memory changes use\n  `agents-db`",
        "cleanup uses `simplification`",
        "LRZ work uses `lrz-ai-systems`",
        "offline/\n  rollout inspection work uses `rerun-nbv-inspector`",
    ):
        assert route in root_guidance
    routed_skill_targets = {
        "agent-behavior": ".agents/skills/agent-behavior/SKILL.md",
        "aria-nbv-context": ".agents/skills/aria-nbv-context/SKILL.md",
        "aria-grill": ".agents/skills/aria-grill/SKILL.md",
        "aria-nbv-mermaid": ".agents/skills/aria-nbv-mermaid/SKILL.md",
        "agents-db": ".agents/skills/agents-db/SKILL.md",
        "simplification": ".agents/skills/simplification/SKILL.md",
        "lrz-ai-systems": ".agents/skills/lrz-ai-systems/SKILL.md",
        "rerun-nbv-inspector": ".agents/skills/rerun-nbv-inspector/SKILL.md",
    }
    for skill_name, relative_path in routed_skill_targets.items():
        assert f"`{skill_name}`" in root_guidance
        assert (ROOT / relative_path).is_file()
    assert "Standard Workflow" not in root_guidance
    assert "## Commands" not in root_guidance

    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split("\0")
    tracked_role_reviews = [
        path for path in tracked if _is_session_local_review_artifact(path)
    ]
    assert not tracked_role_reviews
    retired_review = (
        ROOT / ".omx/specs/autoresearch-thesis-peer-review-20260816/report.md"
    )
    retired_review_owner = (
        ROOT
        / ".agents/memory/history/2026/08/2026-08-16_thesis_peer_review_and_mode_contract.md"
    )
    assert not retired_review.exists()
    assert ".omx/specs/autoresearch-thesis-peer-review-20260816/report.md" not in _read(
        retired_review_owner
    )
    eligible_debrief = ".agents/memory/history/2026/08/eligible-architecture-review.md"
    assert not _is_session_local_review_artifact(eligible_debrief)
    assert not _is_session_local_review_artifact(".omx/reviews")
    assert _is_session_local_review_artifact(".omx/reviews/architect-review.md")
    assert _is_session_local_review_artifact(
        ".omx/reviews/nested/peer-review/report.md"
    )
    assert not _is_session_local_review_artifact(
        ".omx/specs/nested/accepted-architecture-review/report.md"
    )
    assert not _is_session_local_review_artifact(
        ".omx/specs/nested/accepted-peer-review/report.md"
    )

    migrated_review_pointers = {
        ROOT / ".omx" / "plans" / "ralplan-handoff-online-oracle-mvp.md": (
            ".omx/reviews/ralplan-architect-review-online-oracle-mvp-iteration-6.md",
            ".omx/reviews/ralplan-critic-review-online-oracle-mvp-iteration-3.md",
        ),
        ROOT
        / ".omx"
        / "plans"
        / "ralplan-handoff-aria-nbv-domain-skill-distillation.md": (
            ".omx/reviews/ralplan-architect-review-aria-nbv-domain-skill-distillation-consensus-loop-3-iteration-2.md",
            ".omx/reviews/ralplan-critic-review-aria-nbv-domain-skill-distillation-approved.md",
            ".omx/reviews/ralplan-architect-review-aria-nbv-domain-skill-distillation-amendment-20260801.md",
            ".omx/reviews/ralplan-critic-review-aria-nbv-domain-skill-distillation-amendment-20260801.md",
        ),
        ROOT / ".omx" / "plans" / "ralplan-handoff-graphify-typst-projection.md": (
            ".omx/reviews/ralplan-architect-review-graphify-typst-projection.md",
            ".omx/reviews/ralplan-critic-review-graphify-typst-projection.md",
        ),
        ROOT / ".omx" / "plans" / "prd-thin-root-nested-agents-rewrite.md": (
            ".omx/reviews/thin-root-nested-agents-rewrite-architect-review.md",
            ".omx/reviews/thin-root-nested-agents-rewrite-critic-review.md",
        ),
        ROOT / ".omx" / "plans" / "test-spec-thin-root-nested-agents-rewrite.md": (
            ".omx/reviews/thin-root-nested-agents-rewrite-architect-review.md",
            ".omx/reviews/thin-root-nested-agents-rewrite-critic-review.md",
        ),
    }
    for owner, expected_pointers in migrated_review_pointers.items():
        owner_text = _read(owner)
        assert not _raw_review_plan_pointers(owner_text), owner
        for pointer in expected_pointers:
            assert pointer in owner_text, (owner, pointer)

    ignored = _read(ROOT / ".gitignore")
    assert ".omx/reviews/" in ignored.splitlines()
    assert ".omx/specs/**" not in ignored.splitlines()
    for role in ("architect", "architecture", "critic", "critique"):
        assert f".omx/**/*{role}*review*" not in ignored.splitlines()
        assert f".omx/**/*review*{role}*" not in ignored.splitlines()
    ignored_role_reviews = subprocess.run(
        [
            "git",
            "check-ignore",
            "--no-index",
            "--stdin",
        ],
        cwd=ROOT,
        check=True,
        input=(
            ".omx/reviews/architect-review.md\n.omx/reviews/nested/peer-review/report.md\n"
        ),
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert ignored_role_reviews == [
        ".omx/reviews/architect-review.md",
        ".omx/reviews/nested/peer-review/report.md",
    ]

    with tempfile.TemporaryDirectory(prefix="g002-review-ignore-") as tmp:
        root = Path(tmp)
        (root / ".gitignore").write_text(ignored, encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        isolated_ignored_paths = subprocess.run(
            ["git", "check-ignore", "--no-index", "--stdin"],
            cwd=root,
            check=True,
            input=(
                ".omx/reviews/architect-review.md\n"
                ".omx/reviews/nested/peer-review/report.md\n"
                ".omx/specs/nested/accepted-architecture-review/report.md\n"
                ".omx/specs/nested/accepted-peer-review/report.md\n"
                ".omx/specs/nested/peer/review/report.md\n"
                ".omx/specs/nested/review/peer/report.md\n"
                ".omx/specs/nested/accepted-spec/report.md\n"
                ".omx/specs/nested/ordinary/report.md\n"
                ".omx/context/accepted-architecture-review.md\n"
                ".omx/interviews/accepted-peer-review.md\n"
                ".omx/specs/accepted-spec.md\n"
                ".omx/plans/accepted-critic-review.md\n"
                ".agents/memory/history/2026/08/eligible-debrief.md\n"
                f"{eligible_debrief}\n"
            ),
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        assert isolated_ignored_paths == [
            ".omx/reviews/architect-review.md",
            ".omx/reviews/nested/peer-review/report.md",
        ]

    package_guidance = _read(ROOT / "aria_nbv" / "AGENTS.md")
    conventions = _read(
        ROOT
        / ".agents"
        / "skills"
        / "python-standards"
        / "references"
        / "general_conventions.md"
    )
    assert "python-standards` owns generic Python" in package_guidance
    assert "`pyproject.toml` owns executable formatter/linter" in package_guidance
    assert "Binding short-form rules live in" not in conventions
    assert "This file owns the generic non-docstring Python" in conventions
    python_skill = _read(ROOT / ".agents" / "skills" / "python-standards" / "SKILL.md")
    examples_path = (
        ROOT
        / ".agents"
        / "skills"
        / "python-standards"
        / "references"
        / "canonical-examples.md"
    )
    examples = _read(examples_path)
    assert "references/canonical-examples.md" in python_skill
    for example in (
        "## Module Docstring",
        "## Theory-Rich Function Docstring",
        "## Config Or Datamodel Field Docs",
        "## Sequencing Example",
    ):
        assert example in examples
    for implementation_snippet in (
        "High-level oracle RRI computation orchestrator",
        "def compute_rri(",
        "class OracleRRIConfig(",
        "def run(self, sample: EfmSnippetView)",
    ):
        assert implementation_snippet not in python_skill
        assert implementation_snippet in examples
    for contract in (
        "targeted regression",
        "public\n  interface",
        "tracer-bullet test",
        "real-data or integration seams",
    ):
        assert contract in package_guidance

    data_guidance = _read(
        ROOT / "aria_nbv" / "aria_nbv" / "data_handling" / "AGENTS.md"
    )
    assert "including PyTorch3D" in data_guidance
    assert "efm3d.aria.aria_constants" in data_guidance

    rollout_guidance = _read(ROOT / "aria_nbv" / "aria_nbv" / "rollouts" / "AGENTS.md")
    for owner in (
        "aria_nbv.targets.protocol",
        "aria_nbv.oracle.target_selection",
        "data_handling.vin_store.dataset.VinOfflineSample",
        "data_handling.vin_store.batch.VinOracleBatch",
    ):
        assert owner in rollout_guidance

    assert not (ROOT / "scripts" / "quarto_generate_agent_docs.py").exists()


def test_thesis_context_and_context7_routing() -> None:
    context_path = ROOT / ".agents" / "skills" / "aria-nbv-context" / "SKILL.md"
    context = _read(context_path)
    for owner in (
        "docs/typst/thesis/main.typ",
        "docs/typst/shared/glossary.typ",
        "docs/typst/shared/symbols.typ",
        "docs/typst/shared/equations.typ",
        "docs/notation.yml",
        ".agents/skills/aria-nbv-context/references/context7_library_ids.md",
        ".agents/skills/aria-nbv-context/references/context_map.md",
        ".agents/skills/aria-nbv-context/references/semantic-memory-boundary.md",
    ):
        assert (ROOT / owner.partition("#")[0]).is_file()
    assert "owner hierarchy" in context
    assert "context7_library_ids.md" in context
    assert "context_map.md" in context
    assert "semantic-memory-boundary.md" in context

    context_map = _read(
        ROOT
        / ".agents"
        / "skills"
        / "aria-nbv-context"
        / "references"
        / "context_map.md"
    )
    assert "scripts/nbv_typst_includes.py --thesis --mode outline" in context_map
    assert "Derived Context Route Index" in context_map
    assert "never owns the facts it locates" in context_map

    for owner_label in (
        "Oracle evidence construction",
        "Oracle private scoring engine",
        "Scene-RRI scoring",
        "Target-RRI scoring",
        "Oracle label DTOs and retained evidence",
        "Oracle label-generation pipelines",
        "Candidate pose generation and orientation",
        "Camera projection, backprojection, and depth rendering",
        "VIN pose encoding and frame-conditioned inputs",
    ):
        assert owner_label in context_map

    indexed_paths = {
        token.split()[0].split("#", 1)[0].rstrip("/")
        for token in re.findall(r"`((?:docs|aria_nbv|scripts)/[^`]+)`", context_map)
    }
    for indexed_path in indexed_paths:
        if "*" in indexed_path:
            assert list(ROOT.glob(indexed_path)), indexed_path
        else:
            assert (ROOT / indexed_path).exists(), indexed_path

    literature_table = context_map.split("## Literature evidence routing", 1)[1]
    route_labels = {
        cells[0].strip("` ")
        for line in literature_table.splitlines()
        if line.startswith("|") and "---" not in line
        for cells in [[cell.strip() for cell in line.strip("|").split("|")]]
        if cells[0] != "Concept route"
    }
    assert route_labels


def test_active_skills_use_context7_plugin_not_docker_mcp() -> None:
    forbidden = {
        "mcp__MCP_DOCKER.resolve_library_id",
        "mcp__MCP_DOCKER.get_library_docs",
    }
    for skill in (ROOT / ".agents" / "skills").glob("*/SKILL.md"):
        text = _read(skill)
        assert not any(ref in text for ref in forbidden), skill

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
    assert "seed menu, not one broad\nquery" in context7_registry
    for graphify_seed in (
        "query, path, and explain command selection and output contracts",
        "post-commit and post-checkout hook installation behavior",
        "incremental code and Markdown quick-scan behavior versus explicit semantic refresh",
    ):
        assert graphify_seed in context7_registry

    typst_skill = _read(ROOT / ".agents" / "skills" / "typst-authoring" / "SKILL.md")
    assert not _context7_ids(typst_skill)
    for library_id in (
        "/websites/typst_app",
        "/typst-community/glossarium",
        "/cetz-package/cetz",
        "/jollywatt/typst-fletcher",
        "/touying-typ/touying",
    ):
        assert library_id in context7_registry

    mermaid_skill = _read(ROOT / ".agents" / "skills" / "aria-nbv-mermaid" / "SKILL.md")
    assert not _context7_ids(mermaid_skill)
    assert "/mermaid-js/mermaid" in context7_registry

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

    slides_result = subprocess.run(
        [sys.executable, str(outline_script), "--with-slides", "--mode", "outline"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "# docs/typst/seminar_slides/slides_1.typ" in slides_result.stdout
    assert (
        "# docs/typst/thesis_slides/advisor_meeting_2026_05_22.typ"
        in slides_result.stdout
    )


def test_fixture_tool_and_lrz_regressions_follow_owner_boundaries() -> None:
    routing = json.loads(
        _read(ROOT / "scripts" / "scaffold" / "fixtures" / "routing.json")
    )
    fixtures = {fixture["id"]: fixture for fixture in routing["fixtures"]}
    for fixture in fixtures.values():
        if fixture.get("expected_tool_refs"):
            owner_text = "\n".join(
                _read(ROOT / owner) for owner in fixture["expected_owner_paths"]
            )
            for tool_ref in fixture["expected_tool_refs"]:
                assert f"`{tool_ref}`" in owner_text, fixture["id"]
            for tool_ref in fixture.get("forbidden_tool_refs", []):
                assert tool_ref not in owner_text, fixture["id"]

    lrz_fixtures = [
        fixture
        for fixture in fixtures.values()
        if "lrz" in fixture["id"].lower()
        or any("lrz-ai-systems" in path for path in fixture["expected_owner_paths"])
    ]
    for fixture in lrz_fixtures:
        assert (
            ".agents/skills/lrz-ai-systems/SKILL.md" in fixture["expected_owner_paths"]
        ), fixture["id"]


def test_academic_owner_split_retains_typst_links_and_scientific_contract() -> None:
    typst_skill = _read(ROOT / ".agents" / "skills" / "typst-authoring" / "SKILL.md")
    academic_skill = _read(
        ROOT / ".agents" / "skills" / "academic-writing" / "SKILL.md"
    )
    scientific_skill = _read(
        ROOT / ".agents" / "skills" / "scientific-review" / "SKILL.md"
    )
    review_protocol = _read(
        ROOT
        / ".agents"
        / "skills"
        / "scientific-review"
        / "references"
        / "review-protocol.md"
    )
    thesis_writing = _read(
        ROOT
        / ".agents"
        / "skills"
        / "academic-writing"
        / "references"
        / "thesis-writing.md"
    )
    claim_discipline = _read(
        ROOT
        / ".agents"
        / "skills"
        / "academic-writing"
        / "references"
        / "claim-citation-discipline.md"
    )
    reader_exposition = _read(
        ROOT
        / ".agents"
        / "skills"
        / "academic-writing"
        / "references"
        / "reader-centred-exposition.md"
    )

    assert "Typst source edits" in typst_skill
    assert "references/workflow.md" in typst_skill
    assert "../../../docs/typst/shared/style.typ" in typst_skill
    assert (
        "references/empirical-reporting-and-reproducibility.md"
        in typst_skill
    )
    assert "ready-for-realization" in academic_skill
    assert "obtain scientific-review findings before marking" in academic_skill
    assert "literature-research" in academic_skill
    assert "references/reader-centred-exposition.md" in academic_skill
    assert "academic work phase transition" in academic_skill
    assert (
        "references/empirical-reporting-and-reproducibility.md"
        in academic_skill
    )
    assert "references/hm-scientific-practice.md" in academic_skill
    assert "HM/FK07 assessment work" in academic_skill
    assert (
        "../academic-writing/references/empirical-reporting-and-reproducibility.md"
        in scientific_skill
    )
    for review_route in (
        "claim/citation entailment",
        "research-question/estimand alignment",
        "mathematical, notation, or theoretical consistency",
    ):
        assert review_route in scientific_skill
    assert (
        "reader-centred-exposition.md#completion-and-review-lens"
        in scientific_skill
    )
    assert "reader-centred-exposition.md" in typst_skill
    for contract_term in (
        "epistemic dependency",
        "context-content-conclusion",
        "topic position",
        "main text self-contained",
        "takeaway density",
    ):
        assert contract_term in reader_exposition
    skill_guide = _read(ROOT / ".agents" / "skills" / "README.md")
    for phase in (
        "`proposed`",
        "`ready-for-realization`",
        "`realized`",
        "`scientifically released`",
    ):
        assert phase in skill_guide
    for gate in ("`blocking`", "`advisory`", "`clear`"):
        assert gate in review_protocol
    assert "`independence: independent`" in review_protocol
    assert "same-context advisory review cannot unlock" in review_protocol
    assert "independent scientific review" in skill_guide
    assert "optional source-discovery" in skill_guide
    assert (
        ROOT / ".agents" / "skills" / "literature-research" / "SKILL.md"
    ).is_file()
    assert not (ROOT / ".agents" / "skills" / "scientific-writing").exists()
    assert not (ROOT / ".agents" / "skills" / "reader-centred-writing").exists()
    assert "prose-draft" not in thesis_writing
    assert "prose-polish" not in thesis_writing
    assert "generated context artifact" not in claim_discipline
    claim_ledger = _read(
        ROOT
        / ".agents"
        / "skills"
        / "academic-writing"
        / "assets"
        / "templates"
        / "claim-ledger.md"
    )
    assert "defining code + focused tests + active configuration" in claim_ledger
    assert "code path or generated context" not in claim_ledger
    assert (
        ROOT
        / ".agents"
        / "skills"
        / "academic-writing"
        / "references"
        / "empirical-reporting-and-reproducibility.md"
    ).is_file()
    assert not (
        ROOT
        / ".agents"
        / "skills"
        / "scientific-review"
        / "references"
        / "empirical-reporting-and-reproducibility.md"
    ).exists()


if __name__ == "__main__":
    tests = [
        value for name, value in sorted(globals().items()) if name.startswith("test_")
    ]
    for test in tests:
        test()
    print(f"G002 governance migration tests passed: {len(tests)}")
