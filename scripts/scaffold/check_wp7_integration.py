#!/usr/bin/env python3
"""Validate the final WP7 scaffold counts and tracked-output budgets."""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path
import subprocess
import sys
import tomllib


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
GRAPHIFY_CONFIG = ROOT / ".graphify.toml"
LOC_EXCLUDE_PREFIXES = (".omx/",)


def tracked_files() -> list[str]:
    """Return regular tracked worktree files, excluding submodules and symlinks."""
    output = subprocess.check_output(
        ["git", "ls-files", "--stage", "-z"], cwd=ROOT
    ).decode()
    files: list[str] = []
    for record in output.split("\0"):
        if not record:
            continue
        metadata, path = record.split("\t", 1)
        mode = metadata.split(" ", 1)[0]
        if mode in {"100644", "100755"}:
            files.append(path)
    return sorted(files)


def is_active_scaffold_source(path: str) -> bool:
    """Return whether Graphify's canonical corpus assigns a path to scaffold."""
    config = tomllib.loads(GRAPHIFY_CONFIG.read_text(encoding="utf-8"))
    corpus = config["corpus"]
    if any(fnmatch.fnmatch(path, pattern) for pattern in corpus["exclude_patterns"]):
        return False
    return any(
        fnmatch.fnmatch(path, pattern)
        for pattern in config["partition"]["scaffold"]["patterns"]
    )


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
    tracked = tracked_files()
    scaffold = [
        path
        for path in tracked
        if is_active_scaffold_source(path) and not path.startswith(LOC_EXCLUDE_PREFIXES)
    ]
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
        "baseline_skill_count": baseline["measurements"]["aria_skill_count"],
        "active_skill_count": len(live_skills),
        "active_skills": live_skills,
        "expected_active_skills": sorted(skills),
        "baseline_scaffold_source_loc": baseline["measurements"][
            "active_scaffold_source"
        ]["physical_lines"],
        "active_scaffold_source_paths": scaffold,
        "active_scaffold_source_files": len(scaffold),
        "active_scaffold_source_loc": sum(
            len((ROOT / path).read_bytes().splitlines()) for path in scaffold
        ),
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
    if metrics["active_scaffold_source_loc"] >= metrics["baseline_scaffold_source_loc"]:
        errors.append(
            "active scaffold source LOC is not strictly below the WP0 baseline"
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
        > metrics["maximum_description_bytes"]
    ):
        errors.append("model-visible skill descriptions exceed the 40 percent budget")
    if metrics["canonical_graph_bytes"] > metrics["maximum_canonical_graph_bytes"]:
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
        f"description_bytes={metrics['aria_model_visible_description_bytes']}+"
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
