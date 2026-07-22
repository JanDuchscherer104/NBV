#!/usr/bin/env python3
"""Validate and render ARIA's pinned Matt Pocock skill policy."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tomllib
from typing import Any, Iterable
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / ".agents/references/mattpocock_skills_manifest.toml"
BASELINE_PATH = ROOT / ".agents/baselines/scaffold_wp0_baseline.json"
CONFIG_START = "# BEGIN ARIA-NBV MANAGED MATT SKILLS"
CONFIG_END = "# END ARIA-NBV MANAGED MATT SKILLS"
FRONTMATTER = re.compile(r"\A---\r?\n(?P<body>.*?)\r?\n---(?:\r?\n|\Z)", re.DOTALL)
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\((?P<target>[^)]+)\)")
FENCED_BLOCK = re.compile(r"^```.*?^```[ \t]*$", re.MULTILINE | re.DOTALL)
SKILL_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_COMMIT = "ed37663cc5fbef691ddfecd080dff42f7e7e350d"
EXPECTED_REPO = "mattpocock/skills"
EXPECTED_URL = "https://github.com/mattpocock/skills.git"
EXPECTED_INSTALLER_VERSION = "1.5.20"
EXPECTED_INSTALLER_INTEGRITY = "sha512-lPl5KzMfTW+qwHFwc8t6R+wAqmdmSHw1+HWbGdJ/FZYbWLdB34bAZNFWiencM5DVoRaKAgXArmfTWMlNAbl9Gg=="
EXPECTED_ALLOWLIST = [
    "ask-matt",
    "codebase-design",
    "diagnosing-bugs",
    "domain-modeling",
    "grill-with-docs",
    "grilling",
    "handoff",
    "improve-codebase-architecture",
    "resolving-merge-conflicts",
    "tdd",
    "teach",
    "writing-great-skills",
]


class PolicyError(ValueError):
    """Raised when the pinned Matt policy is invalid."""


@dataclass(frozen=True)
class SkillRecord:
    """Tracked closure and invocation metadata for one selected skill."""

    name: str
    upstream_path: str
    closure_sha256: str
    closure_files: tuple[str, ...]
    metadata_path: str
    metadata_sha256: str
    model_visible: bool
    description_bytes: int


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    """Load the tracked policy manifest."""
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _frontmatter(path: Path) -> dict[str, str | bool]:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER.match(text)
    if not match:
        raise PolicyError(f"missing YAML frontmatter: {path}")
    values: dict[str, str | bool] = {}
    for raw_line in match.group("body").splitlines():
        if not raw_line or raw_line.startswith((" ", "\t", "#")) or ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        value = value.strip()
        if value in {"true", "false"}:
            values[key] = value == "true"
        else:
            values[key] = value.strip("\"'")
    return values


def _repo_relative(path: Path, root: Path) -> str:
    try:
        relative = path.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (FileNotFoundError, ValueError) as exc:
        raise PolicyError(
            f"path escapes or is missing from installation root: {path}"
        ) from exc
    return relative.as_posix()


def _link_target(raw_target: str) -> str | None:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    else:
        target = target.split(maxsplit=1)[0]
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    return unquote(parsed.path)


def markdown_closure(checkout: Path, start_path: str) -> tuple[str, ...]:
    """Return the sorted repo-relative closure of Markdown references."""
    root = checkout.resolve(strict=True)
    start = (root / PurePosixPath(start_path)).resolve(strict=True)
    _repo_relative(start, root)
    pending = [start]
    closure: set[Path] = set()
    while pending:
        current = pending.pop()
        if current in closure:
            continue
        closure.add(current)
        if current.suffix.lower() != ".md":
            continue
        text = FENCED_BLOCK.sub("", current.read_text(encoding="utf-8"))
        for match in MARKDOWN_LINK.finditer(text):
            target = _link_target(match.group("target"))
            if target is None:
                continue
            candidate = (current.parent / PurePosixPath(target)).resolve()
            relative = _repo_relative(candidate, root)
            if candidate.is_dir():
                raise PolicyError(f"ambiguous directory reference from {relative}")
            if candidate not in closure:
                pending.append(candidate)
    return tuple(sorted(_repo_relative(path, root) for path in closure))


def closure_digest(checkout: Path, paths: Iterable[str]) -> str:
    """Hash sorted ``path + NUL + raw bytes`` closure records."""
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update((checkout / PurePosixPath(path)).read_bytes())
    return digest.hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover_catalog(checkout: Path) -> dict[str, str]:
    """Map every upstream skill id to exactly one repo-relative SKILL.md path."""
    catalog: dict[str, str] = {}
    duplicates: set[str] = set()
    root = checkout.resolve(strict=True)
    for skill_path in sorted(root.glob("skills/**/SKILL.md")):
        name = _frontmatter(skill_path).get("name")
        if not isinstance(name, str) or not SKILL_ID.fullmatch(name):
            raise PolicyError(f"invalid Matt skill id in {skill_path}: {name!r}")
        if name in catalog:
            duplicates.add(name)
        catalog[name] = _repo_relative(skill_path, root)
    if duplicates:
        raise PolicyError(f"duplicate Matt skill ids: {sorted(duplicates)}")
    return catalog


def manifest_records(manifest: dict[str, Any]) -> dict[str, SkillRecord]:
    records: dict[str, SkillRecord] = {}
    for raw in manifest.get("skill", []):
        name = raw.get("name")
        if not isinstance(name, str) or name in records:
            raise PolicyError(f"duplicate or invalid selected Matt id: {name!r}")
        records[name] = SkillRecord(
            name=name,
            upstream_path=raw["upstream_path"],
            closure_sha256=raw["closure_sha256"],
            closure_files=tuple(raw["closure_files"]),
            metadata_path=raw["metadata_path"],
            metadata_sha256=raw["metadata_sha256"],
            model_visible=raw["model_visible"],
            description_bytes=raw["description_bytes"],
        )
    return records


def validate_manifest(manifest: dict[str, Any], checkout: Path) -> list[str]:
    """Validate pin, allowlist, recursive closures, metadata and budget."""
    errors: list[str] = []
    source = manifest.get("source", {})
    commit = source.get("commit")
    if source.get("repo") != EXPECTED_REPO or source.get("url") != EXPECTED_URL:
        errors.append("Matt source repository differs from the approved upstream")
    if commit != EXPECTED_COMMIT:
        errors.append(f"source.commit must be exactly {EXPECTED_COMMIT}")
    else:
        try:
            observed = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=checkout, text=True
            ).strip()
            if observed != commit:
                errors.append(
                    f"wrong Matt commit: expected {commit}, observed {observed}"
                )
        except (OSError, subprocess.CalledProcessError) as exc:
            errors.append(f"cannot verify Matt checkout commit: {exc}")

    installer = manifest.get("installer", {})
    if (
        installer.get("package") != "skills"
        or installer.get("version") != EXPECTED_INSTALLER_VERSION
    ):
        errors.append(f"installer must be exactly skills@{EXPECTED_INSTALLER_VERSION}")
    integrity = installer.get("npm_integrity")
    if integrity != EXPECTED_INSTALLER_INTEGRITY:
        errors.append("installer npm integrity differs from the approved pin")

    try:
        catalog = discover_catalog(checkout)
        records = manifest_records(manifest)
    except (OSError, PolicyError, KeyError, TypeError) as exc:
        return errors + [str(exc)]

    allowlist = manifest.get("policy", {}).get("allowlist", [])
    if allowlist != EXPECTED_ALLOWLIST:
        errors.append("Matt allowlist differs from the approved 12-skill set")
    if set(allowlist) != set(records):
        errors.append("Matt allowlist and tracked skill records differ")

    visible_bytes = 0
    visible_names: list[str] = []
    for name, record in records.items():
        upstream_path = catalog.get(name)
        if upstream_path is None:
            errors.append(f"selected Matt id has no upstream path: {name}")
            continue
        if upstream_path != record.upstream_path:
            errors.append(
                f"ambiguous or changed upstream path for {name}: "
                f"expected {record.upstream_path}, observed {upstream_path}"
            )
            continue
        try:
            closure = markdown_closure(checkout, upstream_path)
            digest = closure_digest(checkout, closure)
        except (OSError, PolicyError, UnicodeError) as exc:
            errors.append(f"invalid closure for {name}: {exc}")
            continue
        if closure != record.closure_files:
            errors.append(
                f"closure file mismatch for {name}: "
                f"expected={list(record.closure_files)}, observed={list(closure)}"
            )
        if (
            not SHA256.fullmatch(record.closure_sha256)
            or digest != record.closure_sha256
        ):
            errors.append(
                f"closure hash mismatch for {name}: "
                f"expected {record.closure_sha256}, observed {digest}"
            )
        metadata_path = checkout / PurePosixPath(record.metadata_path)
        try:
            metadata_digest = file_digest(metadata_path)
        except OSError as exc:
            errors.append(f"missing invocation metadata for {name}: {exc}")
            continue
        if metadata_digest != record.metadata_sha256:
            errors.append(f"invocation metadata hash mismatch for {name}")
        values = _frontmatter(checkout / PurePosixPath(upstream_path))
        model_visible = values.get("disable-model-invocation") is not True
        description = values.get("description")
        description_bytes = (
            len(description.encode("utf-8")) if isinstance(description, str) else 0
        )
        if model_visible != record.model_visible:
            errors.append(f"invocation posture mismatch for {name}")
        if description_bytes != record.description_bytes:
            errors.append(f"description byte count mismatch for {name}")
        if model_visible:
            visible_names.append(name)
            visible_bytes += description_bytes

    budget = manifest.get("budget", {})
    if visible_names != budget.get("model_visible_allowlist"):
        errors.append(
            "model-visible Matt allowlist differs from invocation metadata: "
            f"observed={visible_names}"
        )
    if visible_bytes != budget.get("selected_description_bytes"):
        errors.append(
            "model-visible Matt description byte count differs: "
            f"observed={visible_bytes}"
        )
    maximum = budget.get("maximum_description_bytes")
    if not isinstance(maximum, int) or visible_bytes > maximum:
        errors.append(
            f"model-visible Matt descriptions exceed budget: {visible_bytes} > {maximum}"
        )
    return errors


def validate_installation(
    manifest: dict[str, Any], checkout: Path, skills_root: Path
) -> tuple[list[str], dict[str, Path]]:
    """Validate installed selected closures without trusting path precedence."""
    errors = validate_manifest(manifest, checkout)
    root = skills_root.resolve(strict=True)
    installed: dict[str, Path] = {}
    duplicates: set[str] = set()
    for skill_path in sorted(root.glob("**/SKILL.md")):
        try:
            _repo_relative(skill_path, root)
            name = _frontmatter(skill_path).get("name")
        except (OSError, PolicyError, UnicodeError) as exc:
            errors.append(str(exc))
            continue
        if not isinstance(name, str):
            continue
        if name in installed:
            duplicates.add(name)
        installed[name] = skill_path
    if duplicates:
        errors.append(f"duplicate installed skill ids: {sorted(duplicates)}")

    records = manifest_records(manifest)
    catalog = discover_catalog(checkout)
    for name, record in records.items():
        skill_path = installed.get(name)
        if skill_path is None:
            errors.append(f"selected Matt id has no installed path: {name}")
            continue
        expected_dir = root / name
        if skill_path.parent.resolve() != expected_dir.resolve():
            errors.append(f"ambiguous installed path for {name}: {skill_path}")
            continue
        upstream_dir = (checkout / PurePosixPath(catalog[name])).parent
        for repo_path in record.closure_files:
            relative = Path(repo_path).relative_to(upstream_dir.relative_to(checkout))
            source_file = checkout / PurePosixPath(repo_path)
            installed_file = expected_dir / relative
            if not installed_file.exists() and not installed_file.is_symlink():
                errors.append(
                    f"missing installed closure file for {name}: {installed_file}"
                )
                continue
            try:
                _repo_relative(installed_file, root)
            except PolicyError as exc:
                errors.append(f"installed closure path invalid for {name}: {exc}")
                continue
            if not installed_file.is_file():
                errors.append(
                    f"missing installed closure file for {name}: {installed_file}"
                )
            elif installed_file.read_bytes() != source_file.read_bytes():
                errors.append(
                    f"installed closure mismatch for {name}: {installed_file}"
                )
        metadata_relative = Path(record.metadata_path).relative_to(
            upstream_dir.relative_to(checkout)
        )
        installed_metadata = expected_dir / metadata_relative
        if not installed_metadata.is_file():
            errors.append(f"missing installed invocation metadata for {name}")
        elif file_digest(installed_metadata) != record.metadata_sha256:
            errors.append(f"installed invocation metadata mismatch for {name}")

    return errors, installed


def _toml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_config_block(
    manifest: dict[str, Any], checkout: Path, skills_root: Path
) -> str:
    """Render path-specific enablement for the complete pinned Matt catalog."""
    records = manifest_records(manifest)
    catalog = discover_catalog(checkout)
    lines = [CONFIG_START, "# Generated by scripts/scaffold/matt_skills_policy.py."]
    root = skills_root.resolve()
    for name in sorted(catalog):
        lines.extend(
            [
                "",
                "[[skills.config]]",
                f"path = {_toml_quote(str(root / name / 'SKILL.md'))}",
                f"enabled = {'true' if name in records else 'false'}",
            ]
        )
    lines.extend(["", CONFIG_END])
    return "\n".join(lines) + "\n"


def update_project_config(path: Path, block: str | None) -> None:
    """Replace or remove only the managed Matt block in project config."""
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if (
        existing.count(CONFIG_START) != existing.count(CONFIG_END)
        or existing.count(CONFIG_START) > 1
    ):
        raise PolicyError(f"ambiguous managed Matt config markers in {path}")
    if CONFIG_START in existing:
        start = existing.index(CONFIG_START)
        end = existing.index(CONFIG_END, start) + len(CONFIG_END)
        existing = (existing[:start] + existing[end:]).strip()
    pieces = [piece for piece in (existing, block.strip() if block else "") if piece]
    if pieces:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n\n".join(pieces) + "\n", encoding="utf-8")
    elif path.exists():
        path.unlink()


def validate_project_config(
    path: Path, manifest: dict[str, Any], checkout: Path, skills_root: Path
) -> list[str]:
    """Require exactly one enabled/disabled entry for every pinned Matt path."""
    errors: list[str] = []
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [f"invalid project config: {exc}"]
    entries = payload.get("skills", {}).get("config", [])
    expected_names = discover_catalog(checkout)
    selected = set(manifest_records(manifest))
    expected: dict[str, bool] = {
        str(skills_root.resolve() / name / "SKILL.md"): name in selected
        for name in expected_names
    }
    observed: dict[str, bool] = {}
    duplicates: set[str] = set()
    for entry in entries:
        raw_path = entry.get("path")
        enabled = entry.get("enabled")
        if not isinstance(raw_path, str) or not isinstance(enabled, bool):
            continue
        resolved = str(Path(raw_path).resolve())
        if resolved in observed:
            duplicates.add(resolved)
        observed[resolved] = enabled
    if duplicates:
        errors.append(f"duplicate Matt config paths: {duplicates}")
    for skill_path, enabled in expected.items():
        if observed.get(skill_path) is not enabled:
            errors.append(
                f"Matt config mismatch for {skill_path}: expected enabled={enabled}"
            )
    return errors


def prompt_skill_entries(payload: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    """Extract model-visible skill names and descriptions from prompt-input JSON."""
    text = "\n".join(
        content.get("text", "")
        for message in payload
        for content in message.get("content", [])
        if content.get("type") == "input_text"
    )
    roots = {
        match.group("alias"): match.group("path")
        for match in re.finditer(
            r"^- `(?P<alias>r\d+)` = `(?P<path>[^`]+)`$", text, re.MULTILINE
        )
    }
    pattern = re.compile(
        r"^- (?P<name>[^:]+): (?P<description>.*?) "
        r"\(file: (?P<path>[^)]+/SKILL\.md)\)$",
        re.MULTILINE,
    )
    entries: list[tuple[str, str, str]] = []
    for match in pattern.finditer(text):
        raw_path = match.group("path")
        first, separator, remainder = raw_path.partition("/")
        path = (
            str(Path(roots[first]) / remainder)
            if separator and first in roots
            else raw_path
        )
        entries.append((match.group("name"), match.group("description"), path))
    return entries


def validate_prompt_input(
    manifest: dict[str, Any],
    payload: list[dict[str, Any]],
    skills_root: Path,
    matt_catalog: set[str],
) -> list[str]:
    """Validate model-visible selected Matt entries and their byte budget."""
    errors: list[str] = []
    entries = prompt_skill_entries(payload)
    matt_entries = [
        (name, description)
        for name, description, path in entries
        if Path(path).resolve().is_relative_to(skills_root.resolve())
        and name in matt_catalog
    ]
    expected_names = manifest["budget"]["model_visible_allowlist"]
    observed_names = sorted(name for name, _ in matt_entries)
    if observed_names != expected_names:
        errors.append(
            "model-visible selected Matt skills differ: "
            f"expected={expected_names}, observed={observed_names}"
        )
    observed_bytes = sum(
        len(description.encode("utf-8")) for _, description in matt_entries
    )
    if observed_bytes != manifest["budget"]["selected_description_bytes"]:
        errors.append(
            "model-visible selected Matt description bytes differ: "
            f"observed={observed_bytes}"
        )
    if observed_bytes > manifest["budget"]["maximum_description_bytes"]:
        errors.append("model-visible selected Matt descriptions exceed the WP0 budget")
    return errors


def validate_codex_binary(baseline_path: Path = BASELINE_PATH) -> list[str]:
    """Require the WP0 Codex version and executable digest for prompt measurement."""
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))[
        "codex_environment"
    ]
    errors: list[str] = []
    version = subprocess.check_output(["codex", "--version"], text=True).strip()
    executable = shutil.which("codex")
    if executable is None:
        return ["codex executable is unavailable"]
    digest = file_digest(Path(executable).resolve())
    if version != baseline["codex_version"]:
        errors.append(
            f"Codex version differs from WP0: expected {baseline['codex_version']}, observed {version}"
        )
    if digest != baseline["codex_executable_sha256"]:
        errors.append("Codex executable digest differs from WP0")
    return errors


def _print_errors(errors: list[str]) -> int:
    if errors:
        print("Matt skill policy validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Matt skill policy valid")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--source-checkout", type=Path, required=True)
    validate.add_argument("--skills-root", type=Path)
    validate.add_argument("--project-config", type=Path)
    validate.add_argument("--prompt-input", type=Path)

    render = subparsers.add_parser("render-config")
    render.add_argument("--source-checkout", type=Path, required=True)
    render.add_argument("--skills-root", type=Path, required=True)
    render.add_argument("--output", type=Path, default=ROOT / ".codex/config.toml")

    rollback = subparsers.add_parser("rollback")
    rollback.add_argument(
        "--project-config", type=Path, default=ROOT / ".codex/config.toml"
    )

    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    if args.command == "render-config":
        block = render_config_block(manifest, args.source_checkout, args.skills_root)
        update_project_config(args.output, block)
        print(f"Rendered Matt project policy to {args.output}")
        return 0
    if args.command == "rollback":
        update_project_config(args.project_config, None)
        print(f"Disabled project Matt policy in {args.project_config}")
        return 0

    errors = validate_manifest(manifest, args.source_checkout)
    if args.skills_root:
        install_errors, _ = validate_installation(
            manifest, args.source_checkout, args.skills_root
        )
        errors.extend(error for error in install_errors if error not in errors)
    if args.project_config:
        if not args.skills_root:
            errors.append("--project-config requires --skills-root")
        else:
            errors.extend(
                validate_project_config(
                    args.project_config,
                    manifest,
                    args.source_checkout,
                    args.skills_root,
                )
            )
    if args.prompt_input:
        if not args.skills_root:
            errors.append("--prompt-input requires --skills-root")
        else:
            errors.extend(validate_codex_binary())
            payload = json.loads(args.prompt_input.read_text(encoding="utf-8"))
            errors.extend(
                validate_prompt_input(
                    manifest,
                    payload,
                    args.skills_root,
                    set(discover_catalog(args.source_checkout)),
                )
            )
    return _print_errors(errors)


if __name__ == "__main__":
    sys.exit(main())
