#!/usr/bin/env python3
"""Validate and inspect explicitly maintained upstream skill sources."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / ".agents/skill-sources.toml"
SOURCE_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
GIT_REVISION = re.compile(r"[0-9a-f]{40}\Z")
KINDS = {"git-adaptation", "byte-identical"}


class ManifestError(ValueError):
    """Report an invalid skill-source manifest."""


@dataclass(frozen=True)
class Source:
    """One reviewed upstream source and its local consumers."""

    id: str
    title: str
    kind: str
    repository: str
    tracked_ref: str
    reviewed_revision: str
    source_paths: tuple[str, ...]
    consumers: tuple[str, ...]

    @property
    def compare_url(self) -> str:
        """Return the repository comparison prefix for a future revision."""
        return self.repository.removesuffix(".git") + "/compare/"


def _relative_path(value: object, field: str, source_id: str) -> str:
    if not isinstance(value, str) or not value:
        raise ManifestError(f"{source_id}: {field} entries must be non-empty strings")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ManifestError(f"{source_id}: unsafe {field} path: {value}")
    return value


def load_manifest(
    manifest_path: Path = DEFAULT_MANIFEST,
    *,
    repo_root: Path | None = None,
) -> tuple[Source, ...]:
    """Load and fully validate the manifest without network access."""
    root = repo_root or manifest_path.resolve().parents[1]
    try:
        data = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ManifestError(f"cannot read {manifest_path}: {error}") from error
    if data.get("schema_version") != 1:
        raise ManifestError("schema_version must be 1")
    raw_sources = data.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ManifestError("sources must be a non-empty array of tables")

    sources: list[Source] = []
    seen: set[str] = set()
    required = {
        "id",
        "title",
        "kind",
        "repository",
        "tracked_ref",
        "reviewed_revision",
        "source_paths",
        "consumers",
    }
    for raw in raw_sources:
        if not isinstance(raw, dict) or set(raw) != required:
            raise ManifestError(f"source fields must be exactly {sorted(required)}")
        source_id = raw["id"]
        if not isinstance(source_id, str) or not SOURCE_ID.fullmatch(source_id):
            raise ManifestError(f"invalid source id: {source_id!r}")
        if source_id in seen:
            raise ManifestError(f"duplicate source id: {source_id}")
        seen.add(source_id)
        if raw["kind"] not in KINDS:
            raise ManifestError(f"{source_id}: unsupported kind {raw['kind']!r}")
        parsed = urlparse(raw["repository"])
        if parsed.scheme != "https" or not parsed.netloc:
            raise ManifestError(f"{source_id}: repository must be an HTTPS URL")
        if not isinstance(raw["tracked_ref"], str) or not raw["tracked_ref"].startswith(
            "refs/heads/"
        ):
            raise ManifestError(f"{source_id}: tracked_ref must name refs/heads/*")
        if not isinstance(raw["reviewed_revision"], str) or not GIT_REVISION.fullmatch(
            raw["reviewed_revision"]
        ):
            raise ManifestError(f"{source_id}: reviewed_revision must be 40 lowercase hex")
        if not isinstance(raw["title"], str) or not raw["title"].strip():
            raise ManifestError(f"{source_id}: title must be a non-empty string")
        if not isinstance(raw["source_paths"], list) or not raw["source_paths"]:
            raise ManifestError(f"{source_id}: source_paths must be non-empty")
        if not isinstance(raw["consumers"], list) or not raw["consumers"]:
            raise ManifestError(f"{source_id}: consumers must be non-empty")
        source_paths = tuple(
            _relative_path(value, "source_paths", source_id)
            for value in raw["source_paths"]
        )
        consumers = tuple(
            _relative_path(value, "consumers", source_id) for value in raw["consumers"]
        )
        for consumer in consumers:
            if not (root / consumer).exists():
                raise ManifestError(f"{source_id}: missing consumer: {consumer}")
        sources.append(
            Source(
                id=source_id,
                title=raw["title"],
                kind=raw["kind"],
                repository=raw["repository"],
                tracked_ref=raw["tracked_ref"],
                reviewed_revision=raw["reviewed_revision"],
                source_paths=source_paths,
                consumers=consumers,
            )
        )
    return tuple(sources)


def _select(sources: tuple[Source, ...], ids: list[str]) -> tuple[Source, ...]:
    if not ids:
        return sources
    by_id = {source.id: source for source in sources}
    unknown = sorted(set(ids) - set(by_id))
    if unknown:
        raise ManifestError("unknown source ids: " + ", ".join(unknown))
    return tuple(by_id[source_id] for source_id in ids)


def remote_revision(source: Source) -> str:
    """Resolve exactly one configured remote branch without fetching content."""
    result = subprocess.run(
        ["git", "ls-remote", "--exit-code", "--refs", source.repository, source.tracked_ref],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or f"git ls-remote exited {result.returncode}"
        raise RuntimeError(f"{source.id}: {detail}")
    lines = [line.split() for line in result.stdout.splitlines() if line.strip()]
    if len(lines) != 1 or len(lines[0]) != 2 or lines[0][1] != source.tracked_ref:
        raise RuntimeError(f"{source.id}: expected exactly one {source.tracked_ref} result")
    revision = lines[0][0]
    if not GIT_REVISION.fullmatch(revision):
        raise RuntimeError(f"{source.id}: remote returned an invalid revision")
    return revision


def materialize_source(source: Source, revision: str, destination: Path) -> None:
    """Fetch declared paths at one exact revision into a new external checkout."""
    if not GIT_REVISION.fullmatch(revision):
        raise ManifestError("revision must be 40 lowercase hex")
    destination = destination.resolve()
    if destination.exists():
        raise ManifestError(f"destination already exists: {destination}")
    if not destination.parent.is_dir():
        raise ManifestError(f"destination parent does not exist: {destination.parent}")
    if destination.is_relative_to(ROOT.resolve()):
        raise ManifestError("destination must be outside the repository")

    with tempfile.TemporaryDirectory(
        prefix="aria-skill-source-", dir=destination.parent
    ) as temporary:
        checkout = Path(temporary) / "checkout"

        def run_git(*arguments: str, input_text: str | None = None) -> None:
            result = subprocess.run(
                ["git", *arguments],
                check=False,
                capture_output=True,
                text=True,
                input=input_text,
            )
            if result.returncode != 0:
                detail = result.stderr.strip() or f"git exited {result.returncode}"
                raise RuntimeError(f"{source.id}: {detail}")

        run_git("init", "--quiet", str(checkout))
        run_git("-C", str(checkout), "remote", "add", "origin", source.repository)
        run_git(
            "-C",
            str(checkout),
            "sparse-checkout",
            "set",
            "--no-cone",
            "--stdin",
            input_text="".join(f"/{path}\n" for path in source.source_paths),
        )
        run_git(
            "-C",
            str(checkout),
            "fetch",
            "--depth=1",
            "origin",
            revision,
        )
        run_git("-C", str(checkout), "checkout", "--detach", "FETCH_HEAD")
        missing = [path for path in source.source_paths if not (checkout / path).exists()]
        if missing:
            raise RuntimeError(
                f"{source.id}: revision omits declared paths: {', '.join(missing)}"
            )
        shutil.move(str(checkout), destination)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--repo-root", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="validate local metadata only")
    subparsers.add_parser("list", help="list registered sources")
    check = subparsers.add_parser("check", help="check configured upstream branches")
    check.add_argument("ids", nargs="*")
    compare = subparsers.add_parser("compare", help="print a comparison URL")
    compare.add_argument("id")
    compare.add_argument("revision")
    fetch = subparsers.add_parser(
        "fetch", help="materialize declared paths in a new external checkout"
    )
    fetch.add_argument("id")
    fetch.add_argument("--revision")
    fetch.add_argument("--destination", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        sources = load_manifest(args.manifest, repo_root=args.repo_root)
        if args.command == "validate":
            print(f"validated {len(sources)} skill sources")
        elif args.command == "list":
            for source in sources:
                print(f"{source.id}\t{source.kind}\t{source.reviewed_revision}")
        elif args.command == "check":
            for source in _select(sources, args.ids):
                revision = remote_revision(source)
                state = "current" if revision == source.reviewed_revision else "update-available"
                print(f"{source.id}\t{state}\t{revision}")
                if state != "current":
                    print(source.compare_url + source.reviewed_revision + "..." + revision)
        elif args.command == "compare":
            source = _select(sources, [args.id])[0]
            if not GIT_REVISION.fullmatch(args.revision):
                raise ManifestError("revision must be 40 lowercase hex")
            print(source.compare_url + source.reviewed_revision + "..." + args.revision)
        elif args.command == "fetch":
            source = _select(sources, [args.id])[0]
            revision = args.revision or remote_revision(source)
            materialize_source(source, revision, args.destination)
            print(f"materialized {source.id} at {revision} in {args.destination.resolve()}")
    except (ManifestError, RuntimeError) as error:
        print(f"skill-sources: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
