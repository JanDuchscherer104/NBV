#!/usr/bin/env python3
"""Validate the final WP7 scaffold counts and tracked-output budgets."""

from __future__ import annotations

import fnmatch
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tomllib
from typing import cast


ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / ".agents/baselines/scaffold_wp0_baseline.json"
WP6_SKILLS = ROOT / ".agents/baselines/scaffold_wp6_skill_inventory.json"
MATT_MANIFEST = ROOT / ".agents/references/mattpocock_skills_manifest.toml"
CANONICAL_GRAPH = (
    ROOT / "graphify-out/graph.json",
    ROOT / "graphify-out/manifest.json",
    ROOT / "graphify-out/GRAPH_REPORT.md",
)
MAX_GRAPH_BYTES = 35 * 1024 * 1024
BASELINE_COMMIT = "57457ec31e0d3b56da7cb6ebdbb9fde6166de434"
OUTLINE_SCRIPT_NAMES = {
    "nbv_qmd_outline.py",
    "nbv_qmd_outline.sh",
    "nbv_typst_includes.py",
}


def git_tree(ref: str) -> dict[str, tuple[str, str]]:
    """Return ``path -> (mode, object id)`` for one committed Git tree."""
    output = subprocess.check_output(
        ["git", "ls-tree", "-rz", "--full-tree", ref], cwd=ROOT
    )
    tree: dict[str, tuple[str, str]] = {}
    for record in output.split(b"\0"):
        if not record:
            continue
        metadata, encoded_path = record.split(b"\t", 1)
        mode, object_type, object_id = metadata.decode().split()
        path = encoded_path.decode("utf-8", errors="surrogateescape")
        tree[path] = (mode, object_id if object_type == "blob" else "")
    return tree


def git_blob(object_id: str) -> bytes:
    """Read a blob by object id without consulting the worktree."""
    return subprocess.check_output(["git", "cat-file", "blob", object_id], cwd=ROOT)


def _matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def accounting_path_sets(
    tree: dict[str, tuple[str, str]], rules: dict[str, object]
) -> tuple[list[str], list[str]]:
    """Resolve exact included and explicitly excluded paths under frozen rules."""
    regular = sorted(
        path for path, (mode, _) in tree.items() if mode in {"100644", "100755"}
    )
    include_globs = rules["include_globs"]
    exclude_globs = rules["exclude_globs"]
    assert isinstance(include_globs, list) and isinstance(exclude_globs, list)
    included = [
        path
        for path in regular
        if _matches(path, include_globs) and not _matches(path, exclude_globs)
    ]
    excluded = [path for path in regular if _matches(path, exclude_globs)]
    return included, excluded


def is_active_scaffold_source(path: str) -> bool:
    """Return whether a path is included by the immutable WP0 accounting rules."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    rules = baseline["counting_rules"]["active_scaffold_source_loc"]
    return _matches(path, rules["include_globs"]) and not _matches(
        path, rules["exclude_globs"]
    )


def outline_scripts(tree: dict[str, tuple[str, str]]) -> list[str]:
    """Return retained root and ARIA context-owner outline scripts."""
    return sorted(
        path
        for path, (mode, _) in tree.items()
        if mode in {"100644", "100755"}
        and Path(path).name in OUTLINE_SCRIPT_NAMES
        and (
            path.startswith("scripts/")
            or path.startswith(".agents/skills/aria-nbv-context/scripts/")
        )
    )


def path_set_digest(paths: list[str]) -> str:
    """Hash an ordered path set with the WP0 ``path + NUL`` encoding."""
    return hashlib.sha256(
        b"".join(path.encode("utf-8") + b"\0" for path in paths)
    ).hexdigest()


def tree_loc(tree: dict[str, tuple[str, str]], paths: list[str]) -> int:
    """Count physical lines for committed blobs in ``paths``."""
    return sum(len(git_blob(tree[path][1]).splitlines()) for path in paths)


def frontmatter_fields(path: Path) -> tuple[str, bool]:
    """Read one skill description and its model-invocation posture."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise ValueError(f"missing YAML frontmatter: {path}")
    description: str | None = None
    model_visible = True
    for line in lines[1:]:
        if line == "---":
            break
        if line.startswith("description:"):
            value = line.partition(":")[2].strip()
            if value.startswith('"'):
                description = json.loads(value)
            elif value.startswith("'") and value.endswith("'"):
                description = value[1:-1]
            else:
                description = value
        elif line == "disable-model-invocation: true":
            model_visible = False
    if description is None:
        raise ValueError(f"missing skill description: {path}")
    return description, model_visible


def measure() -> dict[str, object]:
    """Measure the complete active final scaffold against the immutable baseline."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    skills = json.loads(WP6_SKILLS.read_text(encoding="utf-8"))["active_skills"]
    matt = tomllib.loads(MATT_MANIFEST.read_text(encoding="utf-8"))
    baseline_ref = baseline["source_state"]["commit"]
    baseline_tree = git_tree(baseline_ref)
    head_tree = git_tree("HEAD")
    rules = baseline["counting_rules"]["active_scaffold_source_loc"]
    baseline_included, baseline_excluded = accounting_path_sets(baseline_tree, rules)
    head_included, head_excluded = accounting_path_sets(head_tree, rules)
    tracked = sorted(
        path for path, (mode, _) in head_tree.items() if mode in {"100644", "100755"}
    )
    live_skills = sorted(
        path.split("/")[-2]
        for path in tracked
        if fnmatch.fnmatchcase(path, ".agents/skills/*/SKILL.md")
    )
    aria_fields = [
        frontmatter_fields(ROOT / ".agents/skills" / name / "SKILL.md")
        for name in live_skills
    ]
    aria_visible = sum(
        len(description.encode("utf-8"))
        for description, model_visible in aria_fields
        if model_visible
    )
    matt_visible = sum(
        item["description_bytes"] for item in matt["skill"] if item["model_visible"]
    )
    baseline_description_bytes = baseline["codex_environment"][
        "model_visible_aria_description_bytes"
    ]
    maximum_description_bytes = baseline_description_bytes * 2 // 5
    return {
        "baseline_commit": baseline_ref,
        "baseline_skill_count": baseline["measurements"]["aria_skill_count"],
        "active_skill_count": len(live_skills),
        "active_skills": live_skills,
        "expected_active_skills": sorted(skills),
        "baseline_scaffold_source_loc": baseline["measurements"][
            "active_scaffold_source"
        ]["physical_lines"],
        "declared_baseline_scaffold_source_files": baseline["measurements"][
            "active_scaffold_source"
        ]["file_count"],
        "measured_baseline_scaffold_source_loc": tree_loc(
            baseline_tree, baseline_included
        ),
        "baseline_scaffold_source_paths": baseline_included,
        "baseline_scaffold_excluded_paths": baseline_excluded,
        "baseline_scaffold_source_paths_sha256": path_set_digest(baseline_included),
        "declared_baseline_scaffold_source_paths_sha256": baseline["measurements"][
            "active_scaffold_source"
        ]["resolved_paths_sha256"],
        "active_scaffold_source_paths": head_included,
        "active_scaffold_excluded_paths": head_excluded,
        "active_scaffold_source_files": len(head_included),
        "active_scaffold_source_loc": tree_loc(head_tree, head_included),
        "baseline_outline_scripts": outline_scripts(baseline_tree),
        "active_outline_scripts": outline_scripts(head_tree),
        "matt_skill_count": len(matt["skill"]),
        "matt_allowlist_count": len(matt["policy"]["allowlist"]),
        "baseline_description_bytes": baseline_description_bytes,
        "declared_baseline_description_bytes": matt["budget"][
            "baseline_description_bytes"
        ],
        "maximum_description_bytes": maximum_description_bytes,
        "declared_maximum_description_bytes": matt["budget"][
            "maximum_description_bytes"
        ],
        "aria_model_visible_description_bytes": aria_visible,
        "aria_model_visible_skill_count": sum(
            model_visible for _, model_visible in aria_fields
        ),
        "matt_model_visible_description_bytes": matt_visible,
        "matt_model_visible_skill_count": sum(
            item["model_visible"] for item in matt["skill"]
        ),
        "model_visible_description_bytes": aria_visible + matt_visible,
        "declared_matt_model_visible_description_bytes": matt["budget"][
            "selected_description_bytes"
        ],
        "declared_integrated_description_bytes": matt["budget"][
            "integrated_description_bytes"
        ],
        "canonical_graph_bytes": sum(path.stat().st_size for path in CANONICAL_GRAPH),
        "maximum_canonical_graph_bytes": MAX_GRAPH_BYTES,
        "tracked_generated_codex_agents": [
            path for path in tracked if path.startswith(".codex/agents/")
        ],
        "tracked_graphify_wiki": [
            path for path in tracked if path.startswith("graphify-out/wiki/")
        ],
    }


def validate(metrics: dict[str, object]) -> list[str]:
    """Return violations of the approved WP7 quantitative contract."""
    errors: list[str] = []
    baseline_paths = cast(list[str], metrics["baseline_scaffold_source_paths"])
    active_paths = cast(list[str], metrics["active_scaffold_source_paths"])
    baseline_excluded_paths = cast(
        list[str], metrics["baseline_scaffold_excluded_paths"]
    )
    active_excluded_paths = cast(list[str], metrics["active_scaffold_excluded_paths"])
    baseline_loc = cast(int, metrics["baseline_scaffold_source_loc"])
    active_loc = cast(int, metrics["active_scaffold_source_loc"])
    model_visible_bytes = cast(int, metrics["model_visible_description_bytes"])
    maximum_description_bytes = cast(int, metrics["maximum_description_bytes"])
    canonical_graph_bytes = cast(int, metrics["canonical_graph_bytes"])
    maximum_canonical_graph_bytes = cast(int, metrics["maximum_canonical_graph_bytes"])
    if metrics["baseline_commit"] != BASELINE_COMMIT:
        errors.append(f"WP0 baseline commit must be exactly {BASELINE_COMMIT}")
    if metrics["baseline_skill_count"] != 21:
        errors.append("immutable baseline must contain exactly 21 ARIA skills")
    if metrics["active_skill_count"] != 9:
        errors.append("final scaffold must contain exactly 9 ARIA skills")
    if metrics["aria_model_visible_skill_count"] != 9:
        errors.append("all 9 retained ARIA skills must be model-visible by default")
    if metrics["active_skills"] != metrics["expected_active_skills"]:
        errors.append("final ARIA skill names differ from the closed WP6 inventory")
    if metrics["matt_skill_count"] != 12 or metrics["matt_allowlist_count"] != 12:
        errors.append("final Matt policy must retain exactly 12 allowlisted skills")
    if (
        metrics["measured_baseline_scaffold_source_loc"]
        != metrics["baseline_scaffold_source_loc"]
        or len(baseline_paths) != metrics["declared_baseline_scaffold_source_files"]
        or metrics["baseline_scaffold_source_paths_sha256"]
        != metrics["declared_baseline_scaffold_source_paths_sha256"]
    ):
        errors.append("frozen baseline scaffold path set or LOC does not reproduce")
    if active_loc >= baseline_loc:
        errors.append(
            "active scaffold source LOC is not strictly below the WP0 baseline"
        )
    if not set(cast(list[str], metrics["baseline_outline_scripts"])) <= set(
        cast(list[str], metrics["active_outline_scripts"])
    ):
        errors.append("retained WP0 outline scripts are missing at HEAD")
    for label, paths in (
        ("baseline included", baseline_paths),
        ("HEAD included", active_paths),
    ):
        excluded_paths = (
            baseline_excluded_paths
            if label.startswith("baseline")
            else active_excluded_paths
        )
        if (
            paths != sorted(set(paths))
            or excluded_paths != sorted(set(excluded_paths))
            or set(paths) & set(excluded_paths)
        ):
            errors.append(f"{label} scaffold path set is not exact and disjoint")
        if any(
            path.startswith(("scripts/tests/", "graphify-out/", ".omx/"))
            for path in paths
        ):
            errors.append(
                f"{label} scaffold paths contain tests, graph output, or OMX evidence"
            )
    if (
        metrics["baseline_description_bytes"]
        != metrics["declared_baseline_description_bytes"]
        or metrics["maximum_description_bytes"]
        != metrics["declared_maximum_description_bytes"]
    ):
        errors.append("description budget declarations differ from the WP0 baseline")
    if (
        metrics["matt_model_visible_description_bytes"]
        != metrics["declared_matt_model_visible_description_bytes"]
    ):
        errors.append(
            "model-visible Matt description measurement differs from the manifest"
        )
    if (
        metrics["model_visible_description_bytes"]
        != metrics["declared_integrated_description_bytes"]
    ):
        errors.append("integrated description arithmetic differs from the manifest")
    if model_visible_bytes > maximum_description_bytes:
        errors.append("model-visible skill descriptions exceed the 40 percent budget")
    if canonical_graph_bytes > maximum_canonical_graph_bytes:
        errors.append("canonical Graphify output exceeds 35 MB")
    if metrics["tracked_generated_codex_agents"]:
        errors.append("generated .codex/agents files must not be tracked")
    if metrics["tracked_graphify_wiki"]:
        errors.append("Graphify wiki files must not be tracked")
    return errors


def main() -> int:
    metrics = measure()
    errors = validate(metrics)
    if errors:
        print("WP7 integration budget validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(
        "WP7 integration budgets valid: "
        f"skills={metrics['baseline_skill_count']}->{metrics['active_skill_count']}, "
        f"scaffold_loc={metrics['active_scaffold_source_loc']}"
        f"<{metrics['baseline_scaffold_source_loc']}, "
        f"description_crosscheck={metrics['aria_model_visible_description_bytes']}+"
        f"{metrics['matt_model_visible_description_bytes']}="
        f"{metrics['model_visible_description_bytes']}"
        f"<={metrics['maximum_description_bytes']}, "
        f"graph_bytes={metrics['canonical_graph_bytes']}"
        f"<={metrics['maximum_canonical_graph_bytes']}, "
        "tracked_agents=0, tracked_wiki=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
