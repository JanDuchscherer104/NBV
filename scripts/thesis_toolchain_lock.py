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
LOCK_NAME = "toolchain-lock.json"
RELEASE_LEDGER = "docs/typst/thesis/release-requirements.toml"
NONMATERIAL_SUFFIXES = (".pdf", ".png", ".jpg", ".jpeg", ".svg")
REPORT_SCHEMA_RE = re.compile(r"report-schema-version\s*=\s*\"([^\"]+)\"")
IMPORT_RE = re.compile(r"#import\s+\"(@preview/[^\"]+)\"")
FONT_RE = re.compile(r"(?:font\s*:\s*|body:\s*|sans:\s*)\"([^\"]+)\"")


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
    if (
        Path(path).name == LOCK_NAME
        or path == RELEASE_LEDGER
        or path.endswith(NONMATERIAL_SUFFIXES)
    ):
        return False
    if path.startswith(("docs/typst/thesis/", "docs/typst/shared/")):
        return True
    return path.startswith("docs/") and path.endswith((".bib", ".csl"))


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
        if _material_path(path):
            files[path] = oid
    return files


def _current_material(root: Path) -> dict[str, str]:
    untracked = sorted(
        path
        for path in _run(
            ["git", "ls-files", "--others", "--exclude-standard"], cwd=root
        ).splitlines()
        if _material_path(path)
    )
    if untracked:
        raise LockError("untracked material thesis inputs: " + ", ".join(untracked))
    tracked = _git_files(root)
    current: dict[str, str] = {}
    for path in tracked:
        full = root / path
        if not full.is_file():
            raise LockError(f"material thesis input is missing: {path}")
        current[path] = _sha256(full)
    return current


def _revision_material(root: Path, revision: str) -> dict[str, str]:
    entries = _git_files(root, revision)
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
    fonts: list[dict[str, Any]] = []
    for family in families:
        fc_match = shutil.which("fc-match")
        fc_list = shutil.which("fc-list")
        if not fc_match or not fc_list:
            raise LockError("font identity requires fc-match and fc-list")
        selected = _run(
            [fc_match, "-f", "%{family}|%{style}|%{file}", family], cwd=root
        )
        variants = _run(
            [fc_list, ":family=" + family, "-f", "%{family}|%{style}|%{file}\n"],
            cwd=root,
        )
        fonts.append(
            {
                "family": family,
                "selected": selected,
                "installed_variants": sorted(set(variants.splitlines())),
            }
        )
    executable = shutil.which(typst_bin) or typst_bin
    return {
        "compiler": {
            "executable": str(Path(executable).resolve()),
            "version": _run([typst_bin, "--version"], cwd=root),
        },
        "packages": [{"identity": package} for package in packages],
        "fonts": fonts,
        "csl": {"path": csl_relative, "sha256": _sha256(csl)},
        "rasterizer": {
            "backend": "typst png",
            "version": _run([typst_bin, "--version"], cwd=root),
            "render_script": render_script.relative_to(root).as_posix(),
            "render_script_sha256": _sha256(render_script),
            "ppi": ppi,
        },
    }


def _schema_validate(value: Any, schema: dict[str, Any], path: str = "$") -> None:
    if "const" in schema and value != schema["const"]:
        raise LockError(f"{path}: expected {schema['const']!r}")
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
