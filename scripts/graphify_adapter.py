"""Collect and materialize ARIA-NBV's temporary Graphify source corpus."""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import shlex
import shutil
import subprocess
import tempfile
import tomllib
from fnmatch import fnmatchcase
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from graphify_bridge import materialize

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".graphify.toml"
FAMILIES = ("code", "thesis", "literature")
UPSTREAM_KEYS = frozenset("edges hyperedges input_tokens nodes output_tokens".split())
_ARTIFACTS = ("graph.json", "manifest.json")
IMPLEMENTATION = ("scripts/graphify_adapter.py", "scripts/graphify_bridge.py")
_BRIDGE_SUFFIXES = {".typ", ".tex", ".bib"}
_LOCATION = re.compile(r"^L(\d+)(?:-L?(\d+))?$")
_TEX_INCLUDE = re.compile(r"\\(?:input|include)\s*\{([^}]+)\}")


class AdapterError(RuntimeError):
    pass


@dataclass(frozen=True)
class Source:
    path: str
    family: str
    sha256: str
    text: str


@dataclass(frozen=True)
class LiteratureContract:
    manifest: str
    roots: tuple[PurePosixPath, ...]


LineMap = Mapping[int, tuple[str, int]]
Mappings = Mapping[Path, LineMap]


def load_config(root: Path = ROOT) -> dict[str, Any]:
    path = root / CONFIG.name
    try:
        config = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise AdapterError(f"cannot load {path}: {exc}") from exc
    partitions = config.get("partition")
    if not isinstance(partitions, dict) or tuple(partitions) != FAMILIES:
        raise AdapterError("Graphify partitions must be code, thesis, literature")
    if any(not isinstance(partitions[name].get("patterns"), list) for name in FAMILIES):
        raise AdapterError("Graphify partition patterns must be lists")
    _literature_contract(config)
    return config


def _canonical_config_path(path: str, label: str) -> PurePosixPath:
    pure = PurePosixPath(path)
    if (
        pure.is_absolute()
        or not pure.parts
        or "\\" in path
        or {"", ".", ".."} & set(pure.parts)
        or any(character in path for character in "*?[")
    ):
        raise AdapterError(f"malformed literature {label}: {path!r}")
    return pure


def _literature_contract(config: Mapping[str, Any]) -> LiteratureContract:
    try:
        patterns = config["partition"]["literature"]["patterns"]
    except (KeyError, TypeError) as exc:
        raise AdapterError("missing literature patterns") from exc
    if (
        not isinstance(patterns, list)
        or not patterns
        or not all(isinstance(pattern, str) for pattern in patterns)
    ):
        raise AdapterError("literature patterns must be nonempty strings")
    manifests = [
        pattern
        for pattern in patterns
        if not any(character in pattern for character in "*?[")
        and pattern.endswith(".jsonl")
    ]
    recursive = [pattern for pattern in patterns if pattern.endswith("/**")]
    if not recursive or len(manifests) != 1 or len(recursive) != len(patterns) - 1:
        raise AdapterError(
            "literature patterns require one exact JSONL manifest and recursive roots"
        )
    manifest = str(_canonical_config_path(manifests[0], "manifest"))
    roots = tuple(
        _canonical_config_path(pattern.removesuffix("/**"), "root")
        for pattern in recursive
    )
    if any(
        left == right or left in right.parents or right in left.parents
        for index, left in enumerate(roots)
        for right in roots[index + 1 :]
    ):
        raise AdapterError("ambiguous overlapping literature roots")
    manifest_path = PurePosixPath(manifest)
    if any(root == manifest_path or root in manifest_path.parents for root in roots):
        raise AdapterError("literature manifest cannot be inside a paper root")
    return LiteratureContract(manifest, roots)


def _manifest_rows(
    text: str, label: str = "literature manifest"
) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    directories: set[str] = set()
    arxiv_ids: set[str] = set()
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AdapterError(f"{label}:{number}: malformed JSON") from exc
        if not isinstance(row, dict) or not isinstance(row.get("tex_dir", ""), str):
            raise AdapterError(f"{label}:{number}: malformed manifest row")
        directory = row["tex_dir"]
        if not directory:
            continue
        pure = PurePosixPath(directory)
        arxiv = row.get("arxiv_id")
        if (
            pure.is_absolute()
            or len(pure.parts) != 1
            or pure.name in {".", ".."}
            or not isinstance(arxiv, str)
            or not arxiv
        ):
            raise AdapterError(f"{label}:{number}: malformed paper family")
        if directory in directories or arxiv in arxiv_ids:
            raise AdapterError(f"{label}:{number}: duplicate paper family")
        directories.add(directory)
        arxiv_ids.add(arxiv)
        rows.append((directory, arxiv))
    return rows


def selected_literature_dirs(
    root: Path = ROOT, config: Mapping[str, Any] | None = None
) -> set[str]:
    contract = _literature_contract(config or load_config(root))
    path = root / contract.manifest
    return {directory for directory, _ in _manifest_rows(path.read_text())}


def classify_path(
    path: str, config: Mapping[str, Any], selected: set[str]
) -> str | None:
    pure = PurePosixPath(path)
    if pure.is_absolute() or "\\" in path or {"", ".", ".."} & set(pure.parts):
        raise AdapterError(f"non-canonical source path: {path!r}")
    partitions = config.get("partition", {})
    if tuple(partitions) != FAMILIES:
        raise AdapterError("unknown source families in config")
    literature = _literature_contract(config)
    for family in FAMILIES:
        if not any(
            fnmatchcase(path, pattern) for pattern in partitions[family]["patterns"]
        ):
            continue
        if family == "code" and pure.suffix == ".py":
            return family
        if family == "thesis" and pure.suffix in {".typ", ".bib"}:
            return family
        if family == "literature":
            if path == literature.manifest:
                return family
            for root in literature.roots:
                try:
                    relative = pure.relative_to(root)
                except ValueError:
                    continue
                if (
                    pure.suffix == ".tex"
                    and len(relative.parts) >= 2
                    and relative.parts[0] in selected
                ):
                    return family
    return None


def collect_sources(
    root: Path = ROOT, config: Mapping[str, Any] | None = None
) -> list[Source]:
    config = config or load_config(root)
    selected = selected_literature_dirs(root, config)
    output = subprocess.check_output(
        ["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=root
    )
    sources: list[Source] = []
    for raw in sorted(filter(None, output.split(b"\0"))):
        path = raw.decode("utf-8", errors="strict")
        family = classify_path(path, config, selected)
        absolute = root / path
        if family is None or not absolute.is_file():
            continue
        data = absolute.read_bytes()
        sources.append(
            Source(path, family, hashlib.sha256(data).hexdigest(), data.decode())
        )
    return sources


def source_digest(sources: Iterable[Source]) -> str:
    records = sorted(f"{s.path}\0{s.family}\0{s.sha256}" for s in sources)
    return hashlib.sha256("\n".join(records).encode()).hexdigest()


def _paper_map(
    config: Mapping[str, Any], manifest: Source, sources: list[Source]
) -> dict[str, str]:
    contract = _literature_contract(config)
    tex_paths = {source.path for source in sources if source.path.endswith(".tex")}
    papers: dict[str, str] = {}
    for directory, arxiv in _manifest_rows(manifest.text, manifest.path):
        matches: list[tuple[str, list[str]]] = []
        for root in contract.roots:
            prefix = f"{root}/{directory}/"
            choices = sorted(path for path in tex_paths if path.startswith(prefix))
            if choices:
                matches.append((prefix, choices))
        if not matches:
            raise AdapterError(f"missing paper family: {directory}")
        if len(matches) != 1:
            raise AdapterError(f"ambiguous paper family: {directory}")
        prefix, choices = matches[0]
        main = prefix + "main.tex"
        papers[arxiv] = main if main in choices else choices[0]
    return papers


def _bridge_source(source: Source, paths: set[PurePosixPath]) -> Source:
    path = PurePosixPath(source.path)
    text = source.text
    if path.suffix == ".tex":
        text = re.sub(r"(?m)^\s*%.*$", "", text)

        def keep_resolved(match: re.Match[str]) -> str:
            joined = PurePosixPath(
                posixpath.normpath(str(path.parent / match.group(1).strip()))
            )
            return match.group() if {joined, joined.with_suffix(".tex")} & paths else ""

        text = _TEX_INCLUDE.sub(keep_resolved, text)
    if path.stem.endswith("-overrides"):
        text = re.sub(r"(?m)^(\s*)key(\s*:)", r"\1override_key\2", text)
    if path.stem.endswith("-overrides") or path.stem.startswith("glossary"):
        text = re.sub(r"(?m)^(\s*#let\s+[\w-]+\s*=\s*)\(\s*$", r"\1list(", text)
    return Source(source.path, source.family, source.sha256, text)


def materialize_corpus(
    root: Path, sources: Iterable[Source], destination: Path
) -> Mappings:
    items = list(sources)
    by_path = {source.path: source for source in items}
    if len(by_path) != len(items):
        raise AdapterError("duplicate source path")
    config = load_config(root)
    literature = _literature_contract(config)
    selected = selected_literature_dirs(root, config)
    for source in items:
        if classify_path(source.path, config, selected) != source.family:
            raise AdapterError(f"unknown source path or family: {source.path}")
    families = {source.family for source in items}
    if missing := next((family for family in FAMILIES if family not in families), None):
        raise AdapterError(f"empty source family: {missing}")
    manifest = by_path.get(literature.manifest)
    if manifest is None or manifest.family != "literature":
        raise AdapterError("missing literature manifest")

    result: dict[Path, LineMap] = {}
    bridge_paths = {
        PurePosixPath(source.path)
        for source in items
        if PurePosixPath(source.path).suffix in _BRIDGE_SUFFIXES
    }
    bridged = [
        _bridge_source(source, bridge_paths)
        for source in items
        if PurePosixPath(source.path).suffix in _BRIDGE_SUFFIXES
    ]
    try:
        converted = materialize(
            bridged, destination, paper_by_arxiv=_paper_map(config, manifest, items)
        )
    except (TypeError, ValueError) as exc:
        raise AdapterError(f"cannot materialize Graphify bridge: {exc}") from exc
    result.update(converted.line_map)

    prefix = "aria_nbv/aria_nbv/"
    for source in sorted(
        (s for s in items if s.family == "code"), key=lambda s: s.path
    ):
        output = destination / "aria_nbv" / source.path.removeprefix(prefix)
        if output in result:
            raise AdapterError(f"duplicate materialized path: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(source.text, encoding="utf-8")
        source_map = {
            line: (source.path, line)
            for line in range(1, max(1, len(source.text.splitlines())) + 1)
        }
        result[output] = source_map
    return dict(sorted(result.items(), key=lambda item: str(item[0])))


def graphify_command() -> list[str]:
    configured = os.environ.get("GRAPHIFY_COMMAND")
    command = shlex.split(configured) if configured else ["graphify"]
    if not command or shutil.which(command[0]) is None:
        raise AdapterError("Graphify CLI is unavailable")
    return command


def ensure_graphify_pin(command: Sequence[str], root: Path = ROOT) -> None:
    expected = load_config(root)["graphify_version"]
    try:
        result = subprocess.run(
            [*command, "--version"],
            check=True,
            capture_output=True,
            text=True,
            cwd=root,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise AdapterError(f"cannot run Graphify version check: {exc}") from exc
    match = re.search(r"\bgraphify\s+([^\s]+)", result.stdout)
    if match is None or match.group(1) != expected:
        actual = match.group(1) if match else result.stdout.strip() or "unknown"
        raise AdapterError(f"Graphify version {actual} does not match pin {expected}")


def _mapped_location(location: Any, source_map: LineMap) -> tuple[str, str]:
    if not isinstance(location, str) or not (match := _LOCATION.fullmatch(location)):
        raise AdapterError(f"unmapped upstream source location: {location!r}")
    start = int(match.group(1))
    end = int(match.group(2) or start)
    mapped: list[tuple[str, int]] = []
    for line in range(start, end + 1):
        value = source_map.get(line)
        if value is None:
            raise AdapterError(f"unmapped upstream source location: L{line}")
        mapped.append(value)
    paths = {path for path, _ in mapped}
    if len(paths) != 1:
        raise AdapterError(f"source range crosses authoritative files: {location}")
    lines = [line for _, line in mapped]
    rewritten = (
        f"L{lines[0]}" if len(set(lines)) == 1 else f"L{min(lines)}-L{max(lines)}"
    )
    return mapped[0][0], rewritten


def _rewrite_graph(
    graph: Mapping[str, Any],
    mappings: Mappings,
    temporary: Path | None = None,
) -> dict[str, Any]:
    if set(graph) != UPSTREAM_KEYS:
        raise AdapterError("unexpected upstream graph schema")
    temporary = temporary or Path("/")
    lookup = {
        key: (output, source_map)
        for output, source_map in mappings.items()
        for key in (output.relative_to(temporary).as_posix(), str(output))
    }
    incident: dict[Any, list[tuple[str, str]]] = {}
    for link in graph.get("edges", []):
        source_file = link.get("source_file")
        source_location = link.get("source_location")
        if source_file in lookup and isinstance(source_location, str):
            for endpoint in (link.get("source"), link.get("target")):
                incident.setdefault(endpoint, []).append((source_file, source_location))
    rewritten = dict(graph)
    for collection in ("nodes", "edges"):
        records = graph.get(collection)
        if not isinstance(records, list):
            raise AdapterError(f"upstream {collection} must be a list")
        output_records: list[dict[str, Any]] = []
        for raw in records:
            if not isinstance(raw, dict):
                raise AdapterError(f"upstream {collection} entry must be an object")
            source_file = raw.get("source_file")
            source_location = raw.get("source_location")
            if collection == "nodes" and not source_file:
                candidates = incident.get(raw.get("id"), [])
                if candidates:
                    source_file, source_location = min(candidates)
            if not isinstance(source_file, str) or source_file not in lookup:
                raise AdapterError(f"unmapped upstream source: {source_file!r}")
            output, source_map = lookup[source_file]
            authoritative, location = _mapped_location(source_location, source_map)
            record = dict(raw)
            record["source_file"] = authoritative
            record["source_location"] = location
            suffix = PurePosixPath(authoritative).suffix
            if collection == "nodes" and output.suffix == ".py" and suffix != ".py":
                for field in ("label", "norm_label"):
                    value = record.get(field)
                    if isinstance(value, str) and value.endswith(".py"):
                        record[field] = value[:-3] + suffix
            output_records.append(record)
        rewritten[collection] = output_records
    rewritten["nodes"] = sorted(rewritten["nodes"], key=lambda node: str(node["id"]))
    rewritten["edges"] = sorted(
        rewritten["edges"],
        key=lambda link: (
            str(link["source"]),
            str(link["target"]),
            str(link.get("relation", "")),
        ),
    )
    return rewritten


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode()


def _source_commit(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise AdapterError(f"cannot resolve source commit: {exc}") from exc


def implementation_digest(files: Iterable[tuple[str, bytes]]) -> str:
    digest = hashlib.sha256()
    for path, content in files:
        digest.update(path.encode() + b"\0" + content + b"\0")
    return digest.hexdigest()


def _adapter_digest(root: Path) -> str:
    try:
        return implementation_digest(
            (relative, (root / relative).read_bytes()) for relative in IMPLEMENTATION
        )
    except OSError as exc:
        raise AdapterError(
            f"cannot hash Graphify adapter implementation: {exc}"
        ) from exc


def _manifest(
    root: Path,
    sources: list[Source],
    graph: Mapping[str, Any],
    source_commit: str,
) -> dict[str, Any]:
    config = load_config(root)
    return {
        "adapter_sha256": _adapter_digest(root),
        "adapter_schema_version": 2,
        "built_source_commit": source_commit,
        "config_sha256": hashlib.sha256((root / CONFIG.name).read_bytes()).hexdigest(),
        "graphify_version": config["graphify_version"],
        "edge_count": len(graph["edges"]),
        "node_count": len(graph["nodes"]),
        "source_digest": source_digest(sources),
        "sources": [
            {"family": source.family, "path": source.path, "sha256": source.sha256}
            for source in sorted(sources, key=lambda source: source.path)
        ],
    }


def generate(
    root: Path = ROOT, command: Sequence[str] | None = None
) -> dict[str, bytes]:
    root = root.resolve()
    command = list(command or graphify_command())
    ensure_graphify_pin(command, root)
    sources = collect_sources(root)
    source_commit = _source_commit(root)
    if {source.family for source in sources} != set(FAMILIES):
        raise AdapterError(
            "source corpus must contain nonempty code, thesis, and literature"
        )
    with tempfile.TemporaryDirectory(prefix="aria-graphify-") as name:
        temporary = Path(name)
        mappings = materialize_corpus(root, sources, temporary)
        invocation = [
            *command,
            "extract",
            str(temporary),
            "--code-only",
            "--no-cluster",
            "--no-gitignore",
        ]
        environment = os.environ.copy()
        environment.update(
            {
                "PYTHONHASHSEED": "0",
                "OMP_NUM_THREADS": "1",
                "OPENBLAS_NUM_THREADS": "1",
                "MKL_NUM_THREADS": "1",
            }
        )
        try:
            subprocess.run(
                invocation,
                check=True,
                capture_output=True,
                text=True,
                cwd=root,
                env=environment,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            detail = exc.stderr.strip() if hasattr(exc, "stderr") else str(exc)
            raise AdapterError(f"Graphify failed: {detail}") from exc
        upstream = temporary / "graphify-out"
        graph = _rewrite_graph(
            json.loads((upstream / "graph.json").read_text(encoding="utf-8")),
            mappings,
            temporary,
        )
        artifacts = {
            "graph.json": _json_bytes(graph),
            "manifest.json": _json_bytes(
                _manifest(root, sources, graph, source_commit)
            ),
        }
        if any(str(temporary).encode() in value for value in artifacts.values()):
            raise AdapterError("temporary path remains in Graphify output")
    validate(artifacts, root)
    return artifacts


def validate(artifacts: Mapping[str, bytes], root: Path = ROOT) -> None:
    if set(artifacts) != set(_ARTIFACTS):
        raise AdapterError("Graphify output must contain graph and manifest")
    try:
        graph = json.loads(artifacts["graph.json"])
        manifest = json.loads(artifacts["manifest.json"])
    except (KeyError, json.JSONDecodeError) as exc:
        raise AdapterError(f"invalid Graphify output: {exc}") from exc
    if (
        set(graph) != UPSTREAM_KEYS
        or not isinstance(graph.get("nodes"), list)
        or not isinstance(graph.get("edges"), list)
    ):
        raise AdapterError("invalid native Graphify schema")
    source_commit = manifest.get("built_source_commit")
    if not isinstance(source_commit, str):
        raise AdapterError("manifest lacks built source commit")
    expected = _manifest(root, collect_sources(root), graph, source_commit)
    if manifest != expected:
        raise AdapterError("manifest does not match current source selection")
    paths = {source["path"] for source in manifest["sources"]}
    for record in [*graph["nodes"], *graph["edges"]]:
        if record.get("source_file") not in paths or not _LOCATION.fullmatch(
            str(record.get("source_location", ""))
        ):
            raise AdapterError(
                "graph contains an invalid authoritative source reference"
            )
    family_by_path = {
        source["path"]: source["family"] for source in manifest["sources"]
    }
    node_families = {family_by_path[node["source_file"]] for node in graph["nodes"]}
    if not set(FAMILIES) <= node_families:
        raise AdapterError("graph must contain at least one node from each family")


def _read(root: Path) -> dict[str, bytes]:
    return {name: (root / "graphify-out" / name).read_bytes() for name in _ARTIFACTS}


def _write(artifacts: Mapping[str, bytes], root: Path = ROOT) -> None:
    validate(artifacts, root)
    output = root / "graphify-out"
    output.mkdir(parents=True, exist_ok=True)
    staged: list[tuple[Path, Path]] = []
    try:
        for name in _ARTIFACTS:
            handle, raw = tempfile.mkstemp(prefix=f".{name}.", dir=output)
            path = Path(raw)
            with os.fdopen(handle, "wb") as stream:
                stream.write(artifacts[name])
                stream.flush()
                os.fsync(stream.fileno())
            staged.append((path, output / name))
        for source, target in staged:
            os.replace(source, target)
    finally:
        for source, _ in staged:
            source.unlink(missing_ok=True)


def is_fresh(root: Path = ROOT) -> bool:
    try:
        artifacts = _read(root)
        validate(artifacts, root)
    except (AdapterError, OSError):
        return False
    return True


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("sync")
    subparsers.add_parser("check")
    args = parser.parse_args(argv)
    try:
        if args.action == "check":
            if not is_fresh(ROOT):
                raise AdapterError("Graphify output is stale or invalid")
        else:
            _write(generate(ROOT), ROOT)
    except (AdapterError, OSError) as exc:
        parser.exit(1, f"graphify-adapter: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
