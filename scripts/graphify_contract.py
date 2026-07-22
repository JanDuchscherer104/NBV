#!/usr/bin/env python3
"""Build and validate ARIA-NBV's deterministic partitioned Graphify artifacts."""

from __future__ import annotations

from collections import defaultdict
import fnmatch
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import tomllib
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".graphify.toml"
OUT = ROOT / "graphify-out"
PARTITION_ORDER = ("literature", "scaffold", "thesis", "code")
ORIGINS = {"EXTRACTED", "INFERRED", "AMBIGUOUS"}
REFERENCE_PATTERNS = (
    re.compile(r"\[[^]]*\]\(([^)#?]+)"),
    re.compile(r"#(?:include|import)\s+\"([^\"]+)\""),
    re.compile(r"`((?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+)`"),
)


class ContractError(RuntimeError):
    """Raised when corpus or canonical graph contracts are violated."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _stable_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def load_config(root: Path = ROOT) -> dict[str, Any]:
    """Load and minimally validate the tracked Graphify capability record."""
    try:
        config = tomllib.loads((root / ".graphify.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ContractError(f"cannot load .graphify.toml: {exc}") from exc
    if tuple(config.get("partition", {})) != PARTITION_ORDER:
        raise ContractError(
            "Graphify partitions must be ordered literature, scaffold, thesis, code"
        )
    if config.get("graphify_version") != "0.9.22":
        raise ContractError(".graphify.toml must pin graphifyy==0.9.22")
    if config.get("graphify_upstream_commit") != (
        "abff1b1ca4052fcf9d955c5f6a034088723f4536"
    ):
        raise ContractError("unexpected Graphify upstream capability commit")
    activation = config.get("history", {}).get("activation_commit")
    if not isinstance(activation, str) or not re.fullmatch(r"[0-9a-f]{40}", activation):
        raise ContractError(
            "Graphify history activation_commit must be an immutable SHA"
        )
    return config


def config_digest(config: dict[str, Any], root: Path = ROOT) -> str:
    """Hash extraction config plus the upstream scanner boundary."""
    payload = _stable_json(config) + (root / ".graphifyignore").read_bytes()
    return _sha256_bytes(payload)


def _matches(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def selected_literature_dirs(root: Path = ROOT) -> set[str]:
    """Return TeX source directories selected by the tracked literature manifest."""
    selected: set[str] = set()
    manifest = root / "docs/literature/sources.jsonl"
    if not manifest.exists():
        return selected
    for line_number, line in enumerate(
        manifest.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ContractError(
                f"docs/literature/sources.jsonl:{line_number}: malformed JSON"
            ) from exc
        tex_dir = record.get("tex_dir")
        if isinstance(tex_dir, str) and tex_dir:
            selected.add(tex_dir)
    return selected


def classify_path(
    path: str,
    config: dict[str, Any],
    *,
    selected_literature_dirs: set[str] | None = None,
) -> str | None:
    """Return the unique first-match partition for a canonical repo path."""
    if (
        path.startswith("/")
        or "\\" in path
        or any(part in {"", ".", ".."} for part in path.split("/"))
    ):
        raise ContractError(f"non-canonical Graphify source path: {path!r}")
    corpus = config["corpus"]
    if _matches(path, corpus["exclude_patterns"]):
        return None
    extensionless_sources = {
        ".gitattributes",
        ".gitignore",
        ".graphifyignore",
        "Makefile",
        "scripts/git_hooks/post-commit",
    }
    if (
        Path(path).suffix.lower() not in set(corpus["text_extensions"])
        and path not in extensionless_sources
    ):
        return None
    matches = [
        name
        for name in PARTITION_ORDER
        if _matches(path, config["partition"][name]["patterns"])
    ]
    if not matches:
        return None
    partition = matches[0]
    if partition == "literature" and path.startswith("docs/literature/tex-src/"):
        parts = PurePosixPath(path).parts
        if len(parts) < 4:
            return None
        selected = selected_literature_dirs or set()
        if parts[3] not in selected:
            return None
    return partition


def source_role(path: str, partition: str, config: dict[str, Any]) -> str:
    """Classify code evidence so queries can rank production owners first."""
    roles = config["roles"]
    if _matches(path, roles["test_patterns"]):
        return "test"
    if _matches(path, roles["config_patterns"]):
        return "config"
    if _matches(path, roles["guide_patterns"]):
        return "guide"
    return "production" if partition == "code" else "guide"


def _git_paths(root: Path) -> list[str]:
    output = subprocess.check_output(
        ["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=root
    )
    return sorted(
        value.decode("utf-8", errors="surrogateescape")
        for value in output.split(b"\0")
        if value
    )


def collect_sources(
    root: Path = ROOT, config: dict[str, Any] | None = None
) -> list[dict[str, str]]:
    """Collect the tracked/worktree corpus with exact source digests."""
    config = config or load_config(root)
    selected = selected_literature_dirs(root)
    sources: list[dict[str, str]] = []
    for path in _git_paths(root):
        absolute = root / path
        if not absolute.is_file():
            continue
        partition = classify_path(path, config, selected_literature_dirs=selected)
        if partition is None:
            continue
        sources.append(
            {
                "path": path,
                "sha256": _sha256_bytes(absolute.read_bytes()),
                "partition": partition,
                "role": source_role(path, partition, config),
            }
        )
    return sources


def source_manifest_digest(sources: Iterable[dict[str, str]]) -> str:
    records = [
        f"{item['path']}\0{item['sha256']}\0{item['partition']}\0{item['role']}"
        for item in sources
    ]
    return _sha256_bytes("\n".join(sorted(records)).encode("utf-8"))


def corpus_tree_digest(sources: Iterable[dict[str, str]]) -> str:
    records = [f"{item['path']}\0{item['sha256']}" for item in sources]
    return _sha256_bytes("\n".join(sorted(records)).encode("utf-8"))


def _file_node_id(path: str) -> str:
    return "file:" + hashlib.sha256(path.encode("utf-8")).hexdigest()[:24]


def _edge_id(edge: dict[str, Any]) -> str:
    locators = edge.get("source_locators", [])
    key = {
        "source": edge["source"],
        "target": edge["target"],
        "relation": edge.get("relation", "related_to"),
        "origin": edge["origin"],
        "source_locators": locators,
    }
    return "edge:" + _sha256_bytes(_stable_json(key))[:24]


def _source_locator(source: dict[str, str], line: int | None = None) -> dict[str, str]:
    locator = f"L{line}" if line else "L1"
    return {"path": source["path"], "locator": locator, "sha256": source["sha256"]}


def _read_graph(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _upstream_extract(
    root: Path, graphify_command: list[str], temporary_root: Path
) -> dict[str, Any]:
    command = [
        *graphify_command,
        "extract",
        ".",
        "--code-only",
        "--no-cluster",
        "--no-gitignore",
        "--out",
        str(temporary_root),
    ]
    result = subprocess.run(command, cwd=root, text=True, capture_output=True)
    if result.returncode:
        raise ContractError(
            "Graphify structural extraction failed: "
            + (result.stderr.strip() or result.stdout.strip())
        )
    graph = _read_graph(temporary_root / "graphify-out/graph.json")
    if graph is None:
        raise ContractError("Graphify structural extraction produced no graph.json")
    return graph


def _endpoint_provenance(node: dict[str, Any]) -> dict[str, str]:
    return {
        "node_id": node["id"],
        "source_file": node["source_file"],
        "source_digest": node["source_digest"],
        "partition": node["partition"],
    }


def _canonical_edge(
    edge: dict[str, Any],
    *,
    nodes: dict[str, dict[str, Any]],
    source: dict[str, str],
    origin: str,
    confidence_score: float,
    line: int | None = None,
) -> dict[str, Any]:
    if origin not in ORIGINS:
        raise ContractError(f"invalid edge origin: {origin}")
    if edge["source"] not in nodes or edge["target"] not in nodes:
        raise ContractError("edge endpoint is absent from canonical nodes")
    if not math.isfinite(confidence_score) or not 0.0 <= confidence_score <= 1.0:
        raise ContractError("edge confidence_score must be finite and in [0, 1]")
    value = {
        "source": edge["source"],
        "target": edge["target"],
        "relation": str(edge.get("relation", "related_to")),
        "origin": origin,
        "confidence": origin,
        "confidence_score": confidence_score,
        "source_file": source["path"],
        "source_location": f"L{line}" if line else "L1",
        "source_locators": [_source_locator(source, line)],
        "endpoint_provenance": {
            "source": _endpoint_provenance(nodes[edge["source"]]),
            "target": _endpoint_provenance(nodes[edge["target"]]),
        },
        "partition": nodes[edge["source"]]["partition"],
    }
    value["id"] = _edge_id(value)
    return value


def _reference_edges(
    root: Path,
    sources: list[dict[str, str]],
    nodes: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    by_path = {item["path"]: item for item in sources}
    by_name: dict[str, list[str]] = defaultdict(list)
    for path in by_path:
        by_name[PurePosixPath(path).name].append(path)
    edges: list[dict[str, Any]] = []
    for source in sources:
        try:
            lines = (
                (root / source["path"])
                .read_text(encoding="utf-8", errors="strict")
                .splitlines()
            )
        except (OSError, UnicodeError):
            continue
        for line_number, line in enumerate(lines, start=1):
            references = [
                match.group(1).strip()
                for pattern in REFERENCE_PATTERNS
                for match in pattern.finditer(line)
            ]
            for reference in references:
                if reference.startswith(("http://", "https://", "#")):
                    continue
                relative = (PurePosixPath(source["path"]).parent / reference).as_posix()
                candidates: list[str] = []
                for candidate in (reference.lstrip("/"), relative):
                    normalized = PurePosixPath(candidate).as_posix()
                    if normalized in by_path and normalized not in candidates:
                        candidates.append(normalized)
                if not candidates and "/" not in reference:
                    candidates = sorted(by_name.get(reference, []))
                for candidate in candidates:
                    origin = "INFERRED" if len(candidates) == 1 else "AMBIGUOUS"
                    edges.append(
                        _canonical_edge(
                            {
                                "source": _file_node_id(source["path"]),
                                "target": _file_node_id(candidate),
                                "relation": "references",
                            },
                            nodes=nodes,
                            source=source,
                            origin=origin,
                            confidence_score=0.95 if origin == "INFERRED" else 0.5,
                            line=line_number,
                        )
                    )
    return edges


def _preserved_semantic_edges(
    old_graph: dict[str, Any] | None,
    sources: list[dict[str, str]],
    nodes: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if not old_graph:
        return []
    source_digests = {item["path"]: item["sha256"] for item in sources}
    preserved: list[dict[str, Any]] = []
    for edge in old_graph.get("edges", []):
        if not isinstance(edge, dict) or edge.get("origin") not in {
            "INFERRED",
            "AMBIGUOUS",
        }:
            continue
        if edge.get("source") not in nodes or edge.get("target") not in nodes:
            continue
        locators = edge.get("source_locators")
        if not isinstance(locators, list) or not locators:
            continue
        if any(
            not isinstance(locator, dict)
            or source_digests.get(str(locator.get("path"))) != locator.get("sha256")
            for locator in locators
        ):
            continue
        candidate = dict(edge)
        candidate.pop("partition_revision", None)
        candidate.pop("bridge_partition_revisions", None)
        preserved.append(candidate)
    return preserved


def _semantic_digest(edges: Iterable[dict[str, Any]], partition: str) -> str:
    records = []
    for edge in edges:
        if edge.get("origin") not in {"INFERRED", "AMBIGUOUS"}:
            continue
        if edge.get("partition") != partition:
            continue
        record = {
            key: edge.get(key)
            for key in (
                "id",
                "source",
                "target",
                "relation",
                "origin",
                "confidence_score",
                "source_locators",
            )
        }
        records.append(record)
    return _sha256_bytes(_stable_json(sorted(records, key=lambda item: item["id"])))


def _partition_revision(
    *,
    manifest_digest: str,
    config_sha256: str,
    schema_version: str,
    semantic_mode: str,
    accepted_semantic_digest: str,
    graphify_version: str,
) -> str:
    material = "\0".join(
        (
            manifest_digest,
            graphify_version,
            config_sha256,
            schema_version,
            semantic_mode,
            accepted_semantic_digest,
        )
    )
    return _sha256_bytes(material.encode("utf-8"))


def build_canonical(
    *,
    root: Path = ROOT,
    graphify_command: list[str] | None = None,
    old_graph: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Build canonical graph, manifest, and report without provider or time data."""
    config = load_config(root)
    config_sha256 = config_digest(config, root)
    sources = collect_sources(root, config)
    if not sources:
        raise ContractError("Graphify corpus is empty")
    by_path = {item["path"]: item for item in sources}
    graphify_command = graphify_command or ["graphify"]
    with tempfile.TemporaryDirectory(prefix="aria-graphify-") as directory:
        upstream = _upstream_extract(root, graphify_command, Path(directory))

    nodes: dict[str, dict[str, Any]] = {}
    for source in sources:
        node_id = _file_node_id(source["path"])
        nodes[node_id] = {
            "id": node_id,
            "label": PurePosixPath(source["path"]).name,
            "node_type": "source_file",
            "file_type": "source",
            "source_file": source["path"],
            "source_location": "L1",
            "source_digest": source["sha256"],
            "partition": source["partition"],
            "role": source["role"],
        }

    upstream_id_map: dict[str, str] = {}
    for raw in upstream.get("nodes", []):
        if not isinstance(raw, dict):
            continue
        path = str(raw.get("source_file", ""))
        if path not in by_path or by_path[path]["partition"] != "code":
            continue
        old_id = str(raw.get("id", ""))
        if not old_id:
            continue
        new_id = "ast:" + _sha256_bytes(f"{path}\0{old_id}".encode("utf-8"))[:24]
        upstream_id_map[old_id] = new_id
        source = by_path[path]
        nodes[new_id] = {
            "id": new_id,
            "label": str(raw.get("label", old_id)),
            "node_type": str(raw.get("type", raw.get("file_type", "symbol"))),
            "file_type": str(raw.get("file_type", "code")),
            "source_file": path,
            "source_location": str(raw.get("source_location", "L1")),
            "source_digest": source["sha256"],
            "partition": "code",
            "role": source["role"],
        }

    edges: list[dict[str, Any]] = []
    for raw in upstream.get("edges", []):
        if not isinstance(raw, dict):
            continue
        source_id = upstream_id_map.get(str(raw.get("source", "")))
        target_id = upstream_id_map.get(str(raw.get("target", "")))
        path = str(raw.get("source_file", ""))
        if source_id is None or target_id is None or path not in by_path:
            continue
        edges.append(
            _canonical_edge(
                {
                    "source": source_id,
                    "target": target_id,
                    "relation": raw.get("relation", "related_to"),
                },
                nodes=nodes,
                source=by_path[path],
                origin="EXTRACTED",
                confidence_score=1.0,
            )
        )
    for old_id, new_id in upstream_id_map.items():
        node = nodes[new_id]
        if node["node_type"] not in {"code", "source"} and not old_id.endswith(
            PurePosixPath(node["source_file"]).stem
        ):
            continue
        source = by_path[node["source_file"]]
        edges.append(
            _canonical_edge(
                {
                    "source": _file_node_id(source["path"]),
                    "target": new_id,
                    "relation": "contains",
                },
                nodes=nodes,
                source=source,
                origin="EXTRACTED",
                confidence_score=1.0,
            )
        )

    generated_references = _reference_edges(root, sources, nodes)
    preserved = _preserved_semantic_edges(old_graph, sources, nodes)
    edge_by_id = {
        edge["id"]: edge for edge in [*preserved, *generated_references, *edges]
    }
    edges = list(edge_by_id.values())

    partitions: dict[str, dict[str, Any]] = {}
    for name in PARTITION_ORDER:
        partition_sources = [item for item in sources if item["partition"] == name]
        manifest_sha256 = source_manifest_digest(partition_sources)
        semantic_sha256 = _semantic_digest(edges, name)
        semantic_mode = config["partition"][name]["semantic_mode"]
        partitions[name] = {
            "source_count": len(partition_sources),
            "source_manifest_sha256": manifest_sha256,
            "accepted_semantic_records_sha256": semantic_sha256,
            "semantic_mode": semantic_mode,
            "semantic_complete": True,
            "revision": _partition_revision(
                manifest_digest=manifest_sha256,
                config_sha256=config_sha256,
                schema_version=config["schema_version"],
                semantic_mode=semantic_mode,
                accepted_semantic_digest=semantic_sha256,
                graphify_version=config["graphify_version"],
            ),
        }

    for node in nodes.values():
        node["partition_revision"] = partitions[node["partition"]]["revision"]
    for edge in edges:
        source_partition = nodes[edge["source"]]["partition"]
        target_partition = nodes[edge["target"]]["partition"]
        edge["partition"] = source_partition
        edge["partition_revision"] = partitions[source_partition]["revision"]
        edge["extraction_config_sha256"] = config_sha256
        edge["graphify_version"] = config["graphify_version"]
        if source_partition != target_partition:
            edge["bridge_partition_revisions"] = {
                source_partition: partitions[source_partition]["revision"],
                target_partition: partitions[target_partition]["revision"],
            }

    source_tree_sha256 = corpus_tree_digest(sources)
    graph = {
        "schema_version": config["schema_version"],
        "graphify": {
            "package": config["graphify_package"],
            "version": config["graphify_version"],
            "upstream_commit": config["graphify_upstream_commit"],
        },
        "extraction_config_sha256": config_sha256,
        "corpus_tree_sha256": source_tree_sha256,
        "partitions": partitions,
        "nodes": sorted(nodes.values(), key=lambda item: item["id"]),
        "edges": sorted(edges, key=lambda item: item["id"]),
        "hyperedges": [],
        "input_tokens": 0,
        "output_tokens": 0,
    }
    manifest = {
        "schema_version": config["schema_version"],
        "graphify": graph["graphify"],
        "extraction_config_sha256": config_sha256,
        "corpus_tree_sha256": source_tree_sha256,
        "partitions": partitions,
        "sources": sources,
        "sync": {
            "refreshed_partitions": list(PARTITION_ORDER),
            "source_tree_sha256": source_tree_sha256,
        },
    }
    report_lines = [
        "# ARIA-NBV Graph Report",
        "",
        "Deterministic source-derived navigation index. Exact sources remain authoritative.",
        "",
        f"- Schema: `{config['schema_version']}`",
        f"- Graphify: `{config['graphify_package']}=={config['graphify_version']}`",
        f"- Corpus tree: `{source_tree_sha256}`",
        f"- Nodes: {len(nodes)}",
        f"- Edges: {len(edges)}",
        "",
        "## Partitions",
        "",
        "| Partition | Sources | Semantic complete | Revision |",
        "| --- | ---: | :---: | --- |",
    ]
    report_lines.extend(
        f"| {name} | {partitions[name]['source_count']} | yes | "
        f"`{partitions[name]['revision']}` |"
        for name in PARTITION_ORDER
    )
    report_lines.extend(
        [
            "",
            "## Provenance",
            "",
            "Edges are source-derived and label origin as `EXTRACTED`, `INFERRED`, "
            "or `AMBIGUOUS`; inferred evidence must be confirmed in its exact source.",
            "",
        ]
    )
    return graph, manifest, "\n".join(report_lines)


def canonical_bytes(
    graph: dict[str, Any], manifest: dict[str, Any], report: str
) -> dict[str, bytes]:
    return {
        "graph.json": _stable_json(graph),
        "manifest.json": _stable_json(manifest),
        "GRAPH_REPORT.md": report.encode("utf-8"),
    }


def write_canonical(
    graph: dict[str, Any],
    manifest: dict[str, Any],
    report: str,
    out: Path = OUT,
) -> None:
    """Atomically write only the three canonical Graphify artifacts."""
    out.mkdir(parents=True, exist_ok=True)
    for name, content in canonical_bytes(graph, manifest, report).items():
        with tempfile.NamedTemporaryFile(dir=out, delete=False) as handle:
            handle.write(content)
            temporary = Path(handle.name)
        temporary.replace(out / name)


def validate_graph(graph: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    """Return canonical schema and source-provenance violations."""
    errors: list[str] = []
    nodes = {
        node.get("id"): node
        for node in graph.get("nodes", [])
        if isinstance(node, dict)
    }
    source_digests = {
        source.get("path"): source.get("sha256")
        for source in manifest.get("sources", [])
        if isinstance(source, dict)
    }
    if set(graph.get("partitions", {})) != set(PARTITION_ORDER):
        errors.append("graph does not contain exactly four canonical partitions")
    if graph.get("corpus_tree_sha256") != manifest.get("corpus_tree_sha256"):
        errors.append("graph and manifest corpus tree digests differ")
    for node_id, node in nodes.items():
        if not node_id or node.get("partition") not in PARTITION_ORDER:
            errors.append(f"node has invalid partition or id: {node_id!r}")
        partition = node.get("partition")
        if node.get("partition_revision") != graph.get("partitions", {}).get(
            partition, {}
        ).get("revision"):
            errors.append(f"node has stale partition revision: {node_id}")
    for edge in graph.get("edges", []):
        if not isinstance(edge, dict):
            errors.append("edge is not an object")
            continue
        if edge.get("origin") not in ORIGINS:
            errors.append(f"edge has invalid origin: {edge.get('id')}")
        confidence = edge.get("confidence_score")
        if not isinstance(confidence, (int, float)) or not math.isfinite(confidence):
            errors.append(f"edge has invalid confidence score: {edge.get('id')}")
        if edge.get("source") not in nodes or edge.get("target") not in nodes:
            errors.append(f"edge has missing endpoint: {edge.get('id')}")
        locators = edge.get("source_locators")
        if not isinstance(locators, list) or not locators:
            errors.append(f"edge lacks exact source locators: {edge.get('id')}")
            continue
        for locator in locators:
            if not isinstance(locator, dict) or source_digests.get(
                locator.get("path")
            ) != locator.get("sha256"):
                errors.append(f"edge source digest is not current: {edge.get('id')}")
        if edge.get("origin") in {"INFERRED", "AMBIGUOUS"} and any(
            str(locator.get("path", "")).startswith(
                ("graphify-out/", ".omx/state/", ".agents/memory/transcripts/")
            )
            for locator in locators
            if isinstance(locator, dict)
        ):
            errors.append(f"inferred edge uses non-corpus provenance: {edge.get('id')}")
    return errors


def load_canonical(out: Path = OUT) -> tuple[dict[str, Any], dict[str, Any]]:
    graph = _read_graph(out / "graph.json")
    manifest = _read_graph(out / "manifest.json")
    if graph is None or manifest is None:
        raise ContractError("canonical Graphify graph or manifest is absent/malformed")
    return graph, manifest
