---
id: 2026-04-30_litkg_agent_first_upgradability
date: 2026-04-30
title: "litkg Agent-First Upgradability"
status: done
topics: [litkg, kg, agent-contract, context-pack]
confidence: high
canonical_updates_needed:
  - AGENTS.md
files_touched:
  - AGENTS.md
  - .agents/skills/semantic-scholar-litkg/SKILL.md
  - .agents/external/litkg-rs/crates/litkg-core/src/inspect.rs
  - .agents/external/litkg-rs/crates/litkg-core/src/context_pack.rs
  - .agents/external/litkg-rs/crates/litkg-core/src/lib.rs
  - .agents/external/litkg-rs/crates/litkg-cli/src/main.rs
  - .agents/external/litkg-rs/crates/litkg-cli/tests/inspect_cli.rs
---

## Task

Implemented the agent-first backend upgradability slice for litkg-rs and made
ARIA-NBV route broad cross-surface work through the shared `litkg
context-pack`/`capabilities` contract.

## Method

Added static source/backend descriptors and deterministic conformance reporting
to litkg-rs, then exposed top-level `capabilities` and `context-pack` CLI
aliases for Codex/Gemini. Extended context packs with action plans, backend
status, missing leaves, risk flags, active backlog, symbol hints, and
profile-specific evidence routing.

## Output

ARIA guidance now requires a context pack for broad coding/docs/KG/thesis work
while exempting localized one-file edits. The `semantic-scholar-litkg` skill now
documents the shared Codex/Gemini JSON/text contract and concrete commands.

## Verification

Verified with `cargo fmt --all --check`, `cargo test --all-features`, `cargo
clippy --all-targets --all-features -- -D warnings`, and `make
agents-db-check` in litkg-rs. ARIA-NBV guidance and skill updates passed the
local skill validator, `make check-agent-memory`, and `make agents-db
AGENTS_ARGS='validate'`.

## Canonical State Impact

The durable agent policy is now that litkg-rs is the action/evidence compiler
for broad ARIA-NBV work, with backend readiness surfaced as explicit statuses
and repair commands rather than implicit agent guesswork.
