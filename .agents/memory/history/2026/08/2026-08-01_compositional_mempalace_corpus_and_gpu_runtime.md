---
id: 2026-08-01_compositional_mempalace_corpus_and_gpu_runtime
date: 2026-08-01
title: "Composition-Preserving MemPalace Corpus And GPU Runtime"
status: done
topics: [mempalace, scaffold, literature, codex, gpu]
confidence: high
canonical_updates_needed:
  - .agents/references/human_owner_intent.md
  - .agents/references/source_order.md
files_touched:
  - AGENTS.md
  - .agents/references/human_owner_intent.md
  - .agents/references/source_order.md
  - .agents/skills/aria-nbv-context/SKILL.md
  - .agents/skills/aria-nbv-context/references/mempalace-recall.md
  - .agents/memory/README.md
  - scripts/validate_agent_memory.py
  - scripts/scaffold/fixtures/routing.json
  - scripts/tests/test_agent_governance_g002.py
  - scripts/tests/test_validate_agent_memory.py
  - Makefile
artifacts:
  - ~/.mempalace/palaces/aria-nbv-compositional-v1
  - ~/.mempalace/corpora/aria-nbv/snapshots/773992f3712b5d1efb9f09066bbb63cea2f042a0
  - ~/.mempalace/corpora/aria-nbv/codex-history
  - ~/.mempalace/logs/compositional-v1-clean
---

## Task

Implement the accepted local MemPalace corpus and scaffold integration while
preserving repository source ownership, document composition, privacy, and the
upstream single-writer contract.

## Method

- Installed MemPalace 3.6.0 with the `gpu` and `extract` extras and selected
  EmbeddingGemma on CUDA.
- Built user-local wings for the current thesis, literature reviews, primary
  PDFs, other project documentation, native debriefs, and opt-in root ARIA
  Codex history.
- Used chapter, literature-domain, and authored-month rooms plus seven explicit
  literature-review-to-primary-paper tunnels.
- Kept code, tests, active configuration, child-agent sessions, and unrelated
  conversations outside the corpus.
- Updated only repository routing and policy owners; no MemPalace wrapper,
  runtime corpus, environment, or dependency was added to the repository.
- Kept the discovery router thin by disclosing corpus and runtime mechanics only
  when semantic recall is eligible.
- Added a debrief-validation ratchet so current records reject machine-local
  absolute artifact locators before review.

## Findings

- The completed palace contains 196,105 drawers. The 502-task opt-in history
  wing accounts for 184,945 drawers and is intentionally not a default search
  surface.
- An initial transcript staging defect admitted 73 sessions whose nested
  `session_meta.payload.source.subagent` metadata marked them as child tasks.
  The partial palace was archived, those projections were quarantined, and the
  production palace was rebuilt from scratch with zero such sessions.
- The final drawer index has zero SQLite/HNSW divergence. The closet index has
  one pending element, within the upstream flush-lag tolerance.
- Scoped searches retrieved the expected thesis method, VIN-NBV review,
  primary-paper, debrief, and Codex-history sources. Unrelated thesis and
  debrief rooms have no explicit cross-wing tunnels.
- Upstream `--read-only` is a tool-dispatch boundary, not a byte-immutable
  Chroma mode: searches may update internal database bookkeeping. The Codex
  allowlist supplies the second fail-closed boundary for agent-visible tools.

## Verification

- ONNX Runtime 1.26.0 exposed `CUDAExecutionProvider`; live mining used the RTX
  3080 Ti and reported `Device: cuda`.
- A second direct writer was rejected while mining. Two daemon submissions were
  observed as `running` plus `queued` and both completed in order in an isolated
  disposable palace.
- A fresh read-only MCP protocol probe exposed no mutating tools, and a direct
  `mempalace_mine` dispatch was refused with JSON-RPC error `-32003`.
- `scripts/tests/test_agent_governance_g002.py`: 6 passed.
- `scripts/tests/test_validate_agent_memory.py`: 3 passed.
- `make scaffold-audit`: zero errors; pre-existing warnings only.
- `make scaffold-audit-self-test`, `make check-agent-memory`, and
  `git diff --check`: passed.

## Canonical-State Impact

Human-owner corpus intent, exact implementation-source ownership, and the lazy
semantic-recall route now describe the accepted multi-wing corpus. MemPalace
remains optional evidence; exact repository owners still settle current truth.
