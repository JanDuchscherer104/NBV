---
id: 2026-08-26_wp01_candidate_benchmark
date: 2026-08-26
title: "WP01 Candidate Benchmark Contract"
status: current
topics: [candidate-generation, benchmark, rollouts, evidence]
confidence: high
canonical_updates_needed: []
codex_thread: codex://threads/01a033a6-100a-73d2-83bb-4a4153903cc4
repo_object_format: sha1
repo_head: 28cba376f6c370607700112fc24c64f3c1219bd8
repo_branch: "codex/candidate-benchmark-contract"
worktree_kind: linked
---

# WP01 candidate benchmark contract

Implementation review and delivery: [PR #154](https://github.com/JanDuchscherer104/ARIA-NBV/pull/154).

- Implemented an immutable candidate benchmark DTO and strict JSON/Parquet bundle reader/writer.
- Candidate facts are built from `rollouts.inspection.candidate_audit_rows`, preserving scene, rollout/step state, family applicability, candidate IDs, target-normalized coordinates, and lineage.
- The stored-rollout panel constructs the benchmark only after explicit dispatch and renders deterministic 2D/3D support plots plus export.
- Two validated real stores (scenes 83393 and 81807) produced a 16-state, 960-candidate smoke bundle; this is unchanged-control evidence only, not a training result.
- Validation used the repository shared venv and `PYTHONPATH` pointed at this worktree; Chapter 2 and seminar jitter/config files were untouched.
- The report exporter accepts an optional validated benchmark attachment and serializes canonical records/families/points; absent attachment callers are unchanged.
- The two-store smoke bundle binds the promoted store seals for `test-04356473cc0fafe4` and `test-ab79bb5b17ff7779` with the tested `sha256-canonical-json-v1` aggregate recorded in its manifest and metadata.
- The committed two-scene HTML artifact is `docs/contents/evidence/candidate_benchmark_wp01_smoke.html` (SHA-256 `76e60d8b17f419975c81374fa0f75c976cb94688e0939f660d8aea3584d6d8e8`). Its implementation source-tree hash is `1e5692e5d74d16bf1c75d968254f2010785098940662d0e9de03b23eeb56b9e6`; generator source revision is `26fa386`, CUDA device is RTX 3080 Ti, and inspection is CPU/read-only.
