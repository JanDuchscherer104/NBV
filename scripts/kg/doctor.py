#!/usr/bin/env python3
"""Health + drift checks for the litkg knowledge-graph subsystem.

Run from the repo root via `make kg-doctor` or directly. Probes Ollama,
Neo4j, the vector index, embedding coverage, refresh-stamp freshness,
bundle/source-file consistency, and one end-to-end retrieval smoke. Emits
a text table by default; JSON when `--format json` for hook consumption.

Exits non-zero on any red unless `--soft` is set. The Stop hook calls
this with `--soft --quiet` so a red doesn't break the session.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OLLAMA_URL = "http://127.0.0.1:11434"
NEO4J_HTTP_URL = "http://127.0.0.1:7474"
NEO4J_USER = os.environ.get("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "litkglocal")
NEO4J_DATABASE = os.environ.get("NEO4J_DATABASE", "neo4j")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "qwen3-embedding:4b")
EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "2560"))
VECTOR_INDEX_NAME = f"kg_embedding_index_{EMBEDDING_DIM}"


@dataclass
class CheckResult:
    name: str
    status: str  # green | yellow | red
    message: str
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def color(self) -> str:
        return {
            "green": "\033[0;32m",
            "yellow": "\033[1;33m",
            "red": "\033[0;31m",
        }.get(self.status, "")

    @property
    def reset(self) -> str:
        return "\033[0m" if self.color else ""


def neo4j_query(
    cypher: str, parameters: dict[str, Any] | None = None, timeout: float = 5.0
) -> dict[str, Any]:
    auth = base64.b64encode(f"{NEO4J_USER}:{NEO4J_PASSWORD}".encode()).decode()
    url = f"{NEO4J_HTTP_URL}/db/{NEO4J_DATABASE}/tx/commit"
    payload = json.dumps(
        {
            "statements": [
                {
                    "statement": cypher,
                    "parameters": parameters or {},
                    "resultDataContents": ["row"],
                }
            ]
        }
    ).encode()
    req = Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode())


def check_ollama_reachable() -> CheckResult:
    try:
        with urlopen(f"{OLLAMA_URL}/api/tags", timeout=1.0) as resp:
            json.loads(resp.read().decode())
        return CheckResult("ollama_reachable", "green", f"reachable at {OLLAMA_URL}")
    except (HTTPError, URLError, OSError, json.JSONDecodeError, TimeoutError) as exc:
        return CheckResult(
            "ollama_reachable",
            "red",
            f"unreachable: {exc}",
            {"hint": "bring up the SSH reverse tunnel or `ollama serve`"},
        )


def check_ollama_embedding_smoke() -> CheckResult:
    payload = json.dumps({"model": EMBEDDING_MODEL, "input": ["litkg doctor sentinel"]}).encode()
    req = Request(
        f"{OLLAMA_URL}/api/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=10.0) as resp:
            body = json.loads(resp.read().decode())
    except (HTTPError, URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
        return CheckResult("ollama_embedding_smoke", "red", f"embed call failed: {exc}")
    embeddings = body.get("embeddings") or []
    if not embeddings or not isinstance(embeddings[0], list):
        return CheckResult(
            "ollama_embedding_smoke",
            "red",
            "embed response missing embeddings[0]",
        )
    dim = len(embeddings[0])
    if dim != EMBEDDING_DIM:
        return CheckResult(
            "ollama_embedding_smoke",
            "red",
            f"embedding dim {dim} != expected {EMBEDDING_DIM}",
            {"hint": "EMBEDDING_DIM env or model swap mismatch"},
        )
    return CheckResult(
        "ollama_embedding_smoke",
        "green",
        f"dim={dim} via {EMBEDDING_MODEL}",
        {"dim": dim, "model": EMBEDDING_MODEL},
    )


def check_neo4j_http() -> CheckResult:
    try:
        with urlopen(NEO4J_HTTP_URL, timeout=1.0):
            return CheckResult("neo4j_http", "green", f"reachable at {NEO4J_HTTP_URL}")
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        return CheckResult(
            "neo4j_http",
            "red",
            f"unreachable: {exc}",
            {"hint": "make kg-up"},
        )


def check_neo4j_apoc() -> CheckResult:
    try:
        body = neo4j_query(
            "SHOW PROCEDURES YIELD name WHERE name STARTS WITH 'apoc.' RETURN count(name) AS n"
        )
    except (HTTPError, URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
        return CheckResult("neo4j_apoc", "red", f"query failed: {exc}")
    errors = body.get("errors") or []
    if errors:
        return CheckResult("neo4j_apoc", "red", f"cypher error: {errors[0].get('message')}")
    rows = body.get("results", [{}])[0].get("data", [])
    count = rows[0]["row"][0] if rows else 0
    if count < 100:
        return CheckResult(
            "neo4j_apoc",
            "red",
            f"APOC procedure count {count} < 100",
            {"hint": "ensure docker-compose loads NEO4J_PLUGINS='[\"apoc\"]'"},
        )
    return CheckResult("neo4j_apoc", "green", f"{count} APOC procedures available")


def check_neo4j_vector_index() -> CheckResult:
    try:
        body = neo4j_query(
            f"SHOW VECTOR INDEXES YIELD name, state WHERE name = '{VECTOR_INDEX_NAME}' RETURN state"
        )
    except (HTTPError, URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
        return CheckResult("neo4j_vector_index", "red", f"query failed: {exc}")
    errors = body.get("errors") or []
    if errors:
        return CheckResult(
            "neo4j_vector_index", "red", f"cypher error: {errors[0].get('message')}"
        )
    rows = body.get("results", [{}])[0].get("data", [])
    if not rows:
        return CheckResult(
            "neo4j_vector_index",
            "red",
            f"index {VECTOR_INDEX_NAME} does not exist",
            {"hint": "run make kg-enrich; index is created idempotently"},
        )
    state = rows[0]["row"][0]
    if state != "ONLINE":
        return CheckResult(
            "neo4j_vector_index",
            "yellow",
            f"index state={state}",
            {"hint": "wait for population to finish"},
        )
    return CheckResult(
        "neo4j_vector_index",
        "green",
        f"{VECTOR_INDEX_NAME} ONLINE",
        {"index": VECTOR_INDEX_NAME},
    )


def check_embedding_coverage(repo: Path) -> CheckResult:
    bundle_nodes = repo / ".agents/kg/generated/neo4j-export/nodes.jsonl"
    if not bundle_nodes.is_file():
        return CheckResult(
            "embedding_coverage",
            "yellow",
            "export bundle missing; run make kg-export-neo4j",
        )
    with bundle_nodes.open() as handle:
        bundle_count = sum(1 for line in handle if line.strip())
    try:
        body = neo4j_query(
            "MATCH (n:KGEmbeddingNode) WHERE n.kg_embedding IS NOT NULL RETURN count(n) AS n"
        )
    except (HTTPError, URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
        return CheckResult("embedding_coverage", "red", f"query failed: {exc}")
    rows = body.get("results", [{}])[0].get("data", [])
    embedded = rows[0]["row"][0] if rows else 0
    detail = {"bundle_nodes": bundle_count, "embedded_nodes": embedded}
    if embedded == 0:
        return CheckResult(
            "embedding_coverage",
            "red",
            "no embedded nodes; run make kg-enrich",
            detail,
        )
    # Bundle may include nodes that are not embedding candidates (e.g. Author,
    # Citation). Flag only when embedded count is much smaller than bundle.
    coverage_ratio = embedded / max(bundle_count, 1)
    if coverage_ratio < 0.3:
        return CheckResult(
            "embedding_coverage",
            "yellow",
            f"embedded {embedded}/{bundle_count} ({coverage_ratio:.1%})",
            detail,
        )
    return CheckResult(
        "embedding_coverage",
        "green",
        f"{embedded} embedded nodes (bundle has {bundle_count})",
        detail,
    )


def check_refresh_stamp_age(repo: Path) -> CheckResult:
    stamp = repo / ".agents/kg/.last-refresh"
    if not stamp.is_file():
        return CheckResult(
            "refresh_stamp_age",
            "yellow",
            "no stamp yet; run scripts/kg/auto_refresh.sh once",
        )
    age_seconds = time.time() - stamp.stat().st_mtime
    age_hours = age_seconds / 3600
    if age_hours > 24:
        return CheckResult(
            "refresh_stamp_age",
            "yellow",
            f"last refresh {age_hours:.1f}h ago (> 24h)",
            {"age_seconds": int(age_seconds)},
        )
    return CheckResult(
        "refresh_stamp_age",
        "green",
        f"last refresh {age_hours:.1f}h ago",
        {"age_seconds": int(age_seconds)},
    )


def check_refresh_lock_stale(repo: Path) -> CheckResult:
    lock = repo / ".agents/kg/.refresh.lock"
    if not lock.is_file():
        return CheckResult("refresh_lock_stale", "green", "no lock present")
    try:
        pid = int(lock.read_text().strip())
    except ValueError:
        return CheckResult(
            "refresh_lock_stale",
            "yellow",
            "lock has non-numeric pid; manually remove",
            {"lock_path": str(lock)},
        )
    proc_alive = Path(f"/proc/{pid}").exists()
    if not proc_alive:
        return CheckResult(
            "refresh_lock_stale",
            "red",
            f"lock pid {pid} not running; rm .agents/kg/.refresh.lock",
            {"pid": pid, "lock_path": str(lock)},
        )
    return CheckResult(
        "refresh_lock_stale",
        "yellow",
        f"refresh in flight (pid {pid})",
        {"pid": pid},
    )


def check_kg_search_smoke(repo: Path) -> CheckResult:
    # Call litkg-cli directly to avoid mixing make / cargo chatter into stdout.
    binary = repo / ".agents/external/litkg-rs/target/debug/litkg-cli"
    if not binary.is_file():
        return CheckResult(
            "kg_search_smoke",
            "yellow",
            "litkg-cli binary missing; build the workspace first",
            {"hint": "cd .agents/external/litkg-rs && cargo build -p litkg-cli"},
        )
    try:
        proc = subprocess.run(
            [
                str(binary),
                "kg",
                "find",
                "--config",
                str(repo / ".configs/infrastructure/litkg.toml"),
                "--repo-root",
                str(repo),
                "--limit",
                "3",
                "--format",
                "json",
                "--lexical-only",
                "RRI",
            ],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return CheckResult("kg_search_smoke", "red", f"kg-search failed: {exc}")
    if proc.returncode != 0:
        return CheckResult(
            "kg_search_smoke",
            "red",
            f"kg-search exit={proc.returncode}",
            {"stderr_tail": proc.stderr[-200:]},
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return CheckResult(
            "kg_search_smoke",
            "red",
            "kg-search JSON parse failed",
            {"stdout_head": proc.stdout[:200]},
        )
    results = payload.get("results", [])
    if not results:
        return CheckResult(
            "kg_search_smoke", "red", "kg-search returned 0 hits for 'RRI'"
        )
    return CheckResult(
        "kg_search_smoke",
        "green",
        f"{len(results)} hits for 'RRI'",
        {"hit_count": len(results)},
    )


CHECKS: list[tuple[str, Callable[..., CheckResult], bool]] = [
    ("ollama_reachable", lambda repo: check_ollama_reachable(), False),
    ("ollama_embedding_smoke", lambda repo: check_ollama_embedding_smoke(), False),
    ("neo4j_http", lambda repo: check_neo4j_http(), False),
    ("neo4j_apoc", lambda repo: check_neo4j_apoc(), False),
    ("neo4j_vector_index", lambda repo: check_neo4j_vector_index(), False),
    ("embedding_coverage", check_embedding_coverage, True),
    ("refresh_stamp_age", check_refresh_stamp_age, True),
    ("refresh_lock_stale", check_refresh_lock_stale, True),
    ("kg_search_smoke", check_kg_search_smoke, True),
]


def render_text(results: list[CheckResult], any_red: bool) -> str:
    lines = [
        f"{'STATUS':<7} {'NAME':<24} MESSAGE",
        "-" * 72,
    ]
    for r in results:
        marker = {"green": "OK", "yellow": "WARN", "red": "FAIL"}.get(r.status, "?")
        lines.append(f"{r.color}{marker:<7}{r.reset} {r.name:<24} {r.message}")
    lines.append("-" * 72)
    lines.append("doctor: " + ("FAIL (at least one check red)" if any_red else "OK"))
    return "\n".join(lines)


def render_json(results: list[CheckResult], any_red: bool) -> str:
    return json.dumps(
        {
            "ok": not any_red,
            "checks": [
                {
                    "name": r.name,
                    "status": r.status,
                    "message": r.message,
                    "detail": r.detail,
                }
                for r in results
            ],
        },
        indent=2,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="output format (default: text)",
    )
    parser.add_argument(
        "--soft",
        action="store_true",
        help="exit 0 even if a check is red (for hooks)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="suppress stdout (text mode); errors still go to stderr",
    )
    args = parser.parse_args(argv)

    repo_root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        or "."
    )

    results: list[CheckResult] = []
    for _, fn, needs_repo in CHECKS:
        try:
            results.append(fn(repo_root) if needs_repo else fn(None))
        except Exception as exc:  # never bubble — doctor must finish
            results.append(
                CheckResult(getattr(fn, "__name__", "?"), "red", f"unexpected: {exc}")
            )

    any_red = any(r.status == "red" for r in results)
    output = render_json(results, any_red) if args.format == "json" else render_text(results, any_red)
    if not args.quiet:
        print(output)
    return 0 if (not any_red or args.soft) else 1


if __name__ == "__main__":
    sys.exit(main())
