#!/usr/bin/env python3
"""Generate and validate the deterministic thesis toolchain lock."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "scripts/scaffold/schemas/thesis-toolchain-lock.schema.json"
DEFAULT_OUTPUT = ROOT / "docs/typst/thesis/toolchain-lock.json"
EXCLUDED_PATHS = {
    "docs/typst/thesis/main.pdf",
    "docs/typst/thesis/toolchain-lock.json",
    "docs/typst/thesis/release-requirements.toml",
}
REPORT_SCHEMA_RE = re.compile(r"report-schema-version\s*=\s*\"([^\"]+)\"")
IMPORT_RE = re.compile(r"#import\s+\"(@preview/[^\"]+)\"")
LOCAL_SOURCE_RE = re.compile(r"#(?:import|include)\s+\"([^\"]+)\"")
ASSET_PATH_RE = re.compile(
    r"\"([^\"]+\.(?:svg|png|jpe?g|webp|gif|pdf))\"", re.IGNORECASE
)
FONT_RE = re.compile(r"(?:font\s*:\s*|body:\s*|sans:\s*)\"([^\"]+)\"")
FONT_VARIANT_RE = re.compile(
    r"^- Style: (?P<style>[^,]+), Weight: (?P<weight>\d+), "
    r"Stretch: FontStretch\((?P<stretch>\d+)\)$"
)


class LockError(RuntimeError):
    """Raised when a lock cannot be generated or verified."""


def _run(args: list[str], *, cwd: Path) -> str:
    try:
        result = subprocess.run(
            args, cwd=cwd, check=True, text=True, capture_output=True
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise LockError(f"command failed: {' '.join(args)}: {detail.strip()}") from exc
    return result.stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _material_path(path: str) -> bool:
    if path in EXCLUDED_PATHS:
        return False
    return path.startswith("docs/")


def _local_path(root: Path, source: Path, reference: str) -> Path | None:
    if reference.startswith("@"):
        return None
    base = root / "docs" if reference.startswith("/") else source.parent
    candidate = (base / reference.lstrip("/")).resolve()
    try:
        candidate.relative_to(root / "docs")
    except ValueError:
        return None
    if candidate.is_file():
        return candidate
    if candidate.suffix == "" and candidate.with_suffix(".typ").is_file():
        return candidate.with_suffix(".typ")
    return None


def _git_files(root: Path, revision: str | None = None) -> dict[str, str]:
    args = (
        ["git", "ls-files", "-s"]
        if revision is None
        else ["git", "ls-tree", "-r", revision]
    )
    text = _run(args, cwd=root)
    files: dict[str, str] = {}
    for line in text.splitlines():
        if revision is None:
            mode, oid, _stage, path = line.split(maxsplit=3)
            if mode == "160000":
                continue
        else:
            _mode, _kind, oid, path = line.split(maxsplit=3)
        files[path] = oid
    return files


def _source_closure(
    root: Path, *, revision: str | None = None
) -> tuple[set[str], set[str]]:
    all_files = _git_files(root, revision)
    pending = [root / "docs/typst/thesis/main.typ"]
    sources: set[str] = set()
    assets: set[str] = set()
    while pending:
        source = pending.pop()
        relative = source.relative_to(root).as_posix()
        if relative in sources:
            continue
        if relative not in all_files:
            raise LockError(f"active thesis source is not tracked: {relative}")
        if revision is None:
            if not source.is_file():
                raise LockError(f"active thesis source is missing: {relative}")
            text = source.read_text(encoding="utf-8")
        else:
            try:
                text = subprocess.run(
                    ["git", "show", f"{revision}:{relative}"],
                    cwd=root,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout
            except (OSError, subprocess.CalledProcessError) as exc:
                raise LockError(
                    f"cannot read active thesis source: {relative}"
                ) from exc
        sources.add(relative)
        for reference in LOCAL_SOURCE_RE.findall(text):
            child = _local_path(root, source, reference)
            if child is not None:
                pending.append(child)
        for reference in ASSET_PATH_RE.findall(text):
            asset = _local_path(root, source, reference)
            if asset is not None:
                assets.add(asset.relative_to(root).as_posix())
            elif reference.startswith(("/", "../", "./")):
                resolved = (root / "docs" / reference.lstrip("/")).resolve()
                try:
                    assets.add(resolved.relative_to(root).as_posix())
                except ValueError:
                    raise LockError(f"active thesis asset is outside docs: {reference}")
    return sources, assets


def _material_paths(root: Path, revision: str | None = None) -> set[str]:
    sources, assets = _source_closure(root, revision=revision)
    all_files = _git_files(root, revision)
    paths = sources | assets
    paths |= {
        path
        for path in all_files
        if path.startswith("docs/") and path.endswith((".bib", ".csl"))
    }
    return {path for path in paths if _material_path(path)}


def _current_material(root: Path) -> dict[str, str]:
    untracked = sorted(
        path
        for path in _run(
            ["git", "ls-files", "--others", "--exclude-standard"], cwd=root
        ).splitlines()
        if path in _material_paths(root)
    )
    if untracked:
        raise LockError("untracked material thesis inputs: " + ", ".join(untracked))
    tracked = _material_paths(root)
    current: dict[str, str] = {}
    for path in tracked:
        full = root / path
        if not full.is_file():
            raise LockError(f"material thesis input is missing: {path}")
        current[path] = _sha256(full)
    return current


def _revision_material(root: Path, revision: str) -> dict[str, str]:
    entries = _material_paths(root, revision)
    result: dict[str, str] = {}
    for path in entries:
        try:
            content = subprocess.run(
                ["git", "show", f"{revision}:{path}"],
                cwd=root,
                check=True,
                capture_output=True,
            ).stdout
        except (OSError, subprocess.CalledProcessError) as exc:
            raise LockError(
                f"cannot read material input at {revision}: {path}"
            ) from exc
        result[path] = hashlib.sha256(content).hexdigest()
    return result


def _thesis_sources(root: Path) -> list[Path]:
    paths = [p for p in (root / "docs/typst/thesis").rglob("*.typ")]
    paths += [p for p in (root / "docs/typst/shared").rglob("*.typ") if p not in paths]
    return sorted(paths)


def _typst_font_variants(output: str, family: str) -> list[dict[str, Any]]:
    current: str | None = None
    variants: list[dict[str, Any]] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not raw_line.startswith("-"):
            current = line
            continue
        match = FONT_VARIANT_RE.fullmatch(line)
        if current == family and match is not None:
            variants.append(
                {
                    "style": match.group("style"),
                    "weight": int(match.group("weight")),
                    "stretch": int(match.group("stretch")),
                }
            )
    unique = {json.dumps(item, sort_keys=True): item for item in variants}
    return sorted(
        unique.values(),
        key=lambda item: (item["style"], item["weight"], item["stretch"]),
    )


def _system_font_files(
    family: str, *, fc_list: str, root: Path
) -> list[dict[str, str]]:
    rows = _run([fc_list, "-f", "%{family}|%{file}\n"], cwd=root).splitlines()
    files: dict[str, str] = {}
    for row in rows:
        names, separator, filename = row.partition("|")
        exact_names = {name.strip() for name in names.split(",")}
        if not separator or family not in exact_names:
            continue
        path = Path(filename)
        if path.is_file():
            files[path.name] = _sha256(path)
    return [
        {"basename": basename, "sha256": digest}
        for basename, digest in sorted(files.items())
    ]


def _identities(
    root: Path, *, typst_bin: str, render_script: Path, ppi: int
) -> dict[str, Any]:
    sources = _thesis_sources(root)
    text = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    packages = sorted(set(IMPORT_RE.findall(text)))
    csl_paths = sorted(set(re.findall(r"style\s*:\s*\"([^\"]+\.csl)\"", text)))
    if not csl_paths:
        raise LockError(
            'no tracked CSL path selected: thesis template still uses builtin style "ieee"'
        )
    csl_relative = csl_paths[0].lstrip("/")
    if csl_paths[0].startswith("/"):
        csl_relative = f"docs/{csl_relative}"
    csl = root / csl_relative
    if not csl.is_file() or not csl_relative.startswith("docs/"):
        raise LockError(
            f"selected CSL is not a tracked repository path: {csl_paths[0]}"
        )
    families = sorted(set(FONT_RE.findall(text)))
    executable = shutil.which(typst_bin) or typst_bin
    executable_path = Path(executable).resolve()
    if not executable_path.is_file():
        raise LockError(f"compiler executable is not a file: {typst_bin}")
    version = _run([typst_bin, "--version"], cwd=root)
    binary_sha256 = _sha256(executable_path)
    fonts: list[dict[str, Any]] = []
    for family in families:
        fc_list = shutil.which("fc-list")
        if not fc_list:
            raise LockError("font identity requires fc-list")
        variants = _typst_font_variants(
            _run([typst_bin, "fonts", "--variants"], cwd=root), family
        )
        if not variants:
            raise LockError(
                f"requested font family is absent from Typst resolver: {family}"
            )
        system_files = _system_font_files(family, fc_list=fc_list, root=root)
        font: dict[str, Any] = {
            "family": family,
            "source": "system" if system_files else "embedded_in_compiler",
            "variants": variants,
            "system_files": system_files,
        }
        if not system_files:
            font["compiler_binding"] = {
                "version": version,
                "binary_sha256": binary_sha256,
            }
        fonts.append(font)
    return {
        "compiler": {
            "command": Path(typst_bin).name,
            "version": version,
            "binary_sha256": binary_sha256,
        },
        "packages": [{"identity": package} for package in packages],
        "fonts": fonts,
        "csl": {"path": csl_relative, "sha256": _sha256(csl)},
        "rasterizer": {
            "backend": "typst png",
            "version": version,
            "render_script": render_script.relative_to(root).as_posix(),
            "render_script_sha256": _sha256(render_script),
            "ppi": ppi,
        },
    }


def _schema_validate(value: Any, schema: dict[str, Any], path: str = "$") -> None:
    if "const" in schema and value != schema["const"]:
        raise LockError(f"{path}: expected {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise LockError(f"{path}: expected one of {schema['enum']!r}")
    if schema.get("type") == "object":
        if not isinstance(value, dict):
            raise LockError(f"{path}: expected object")
        required = schema.get("required", [])
        missing = [key for key in required if key not in value]
        if missing:
            raise LockError(f"{path}: missing required fields: {', '.join(missing)}")
        if schema.get("additionalProperties") is False:
            unknown = set(value) - set(schema.get("properties", {}))
            if unknown:
                raise LockError(f"{path}: unknown fields: {', '.join(sorted(unknown))}")
        for key, child in schema.get("properties", {}).items():
            if key in value:
                _schema_validate(value[key], child, f"{path}.{key}")
    elif schema.get("type") == "array":
        if not isinstance(value, list):
            raise LockError(f"{path}: expected array")
        if len(value) < schema.get("minItems", 0):
            raise LockError(f"{path}: expected at least {schema['minItems']} items")
        for index, item in enumerate(value):
            _schema_validate(item, schema["items"], f"{path}[{index}]")
    elif schema.get("type") == "string":
        if not isinstance(value, str):
            raise LockError(f"{path}: expected string")
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            raise LockError(f"{path}: does not match required pattern")
    elif schema.get("type") == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise LockError(f"{path}: expected integer")
        if value < schema.get("minimum", value):
            raise LockError(f"{path}: must be at least {schema['minimum']}")


def _build(root: Path, revision: str, *, typst_bin: str, ppi: int) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise LockError(f"source revision must be a full commit OID: {revision}")
    material = _current_material(root)
    recorded = _revision_material(root, revision)
    if material != recorded:
        changed = sorted(set(material) | set(recorded))
        raise LockError(
            "current material build inputs differ from source revision: "
            + ", ".join(changed)
        )
    render_script = root / ".agents/skills/typst-authoring/scripts/render_png.sh"
    report_match = REPORT_SCHEMA_RE.search(
        (root / "docs/typst/thesis/experiment_data.typ").read_text(encoding="utf-8")
    )
    if report_match is None:
        raise LockError(
            "thesis report schema version is not declared in experiment_data.typ"
        )
    return {
        "schema_version": "thesis-toolchain-lock-v1",
        "source_revision": revision,
        "material_sources": [
            {"path": path, "sha256": digest}
            for path, digest in sorted(material.items())
        ],
        "toolchain": _identities(
            root, typst_bin=typst_bin, render_script=render_script, ppi=ppi
        ),
        "report_schema_version": report_match.group(1),
        "build_commands": {
            "development": "typst compile --root docs docs/typst/thesis/main.typ docs/typst/thesis/main.pdf",
            "submission": "typst compile --root docs docs/typst/thesis/main.typ <submission-output.pdf> --input aria-thesis-mode=submission",
        },
    }


def _write_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("generate", "check"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source-revision")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--typst-bin", default=os.environ.get("TYPST_BIN", "typst"))
    parser.add_argument("--ppi", type=int, default=300)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.mode == "generate":
            revision = args.source_revision or _run(
                ["git", "rev-parse", "HEAD"], cwd=root
            )
            data = _build(root, revision, typst_bin=args.typst_bin, ppi=args.ppi)
            _schema_validate(data, json.loads(SCHEMA.read_text(encoding="utf-8")))
            _write_atomic(args.output.resolve(), data)
        else:
            actual = json.loads(args.output.read_text(encoding="utf-8"))
            _schema_validate(actual, json.loads(SCHEMA.read_text(encoding="utf-8")))
            revision = args.source_revision or actual["source_revision"]
            data = _build(root, revision, typst_bin=args.typst_bin, ppi=args.ppi)
            if actual != data:
                raise LockError("lock drift detected; run thesis-toolchain-lock")
    except (OSError, LockError, json.JSONDecodeError, AttributeError) as exc:
        print(f"thesis toolchain lock: {exc}", file=sys.stderr)
        return 1
    print(f"{args.mode}: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
