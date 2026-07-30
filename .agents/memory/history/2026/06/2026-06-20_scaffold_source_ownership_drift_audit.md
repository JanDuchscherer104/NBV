---
id: 2026-06-20_scaffold_source_ownership_drift_audit
date: 2026-06-20
title: "Scaffold Source Ownership Drift Audit"
status: done
topics: [scaffold, skills, source-order, validation]
confidence: high
canonical_updates_needed: []
files_touched:
  - Makefile
  - scripts/scaffold_audit.py
  - .agents/references/scaffold_routing_fixtures.json
  - .agents/references/source_order.md
  - .agents/references/skill_style_guide.md
  - .agents/references/verification_matrix.md
---

## Task

Implemented the next scaffold alignment slice after the conservative
prune/merge verdict: detect skill truth leakage without auto-deleting prose,
make source-order review routine, and add negative probes for routing and
canonical-source invariants.

## Output

`scripts/scaffold_audit.py` gained warning-only semantic drift checks for
formula detail, roadmap claims, future-work plans, and implementation contract
detail in skill bodies. `make scaffold-audit-self-test` now runs negative
fixtures for canonical-source escape, missing anchors, malformed routing
fixtures, incorrect KG/local lookup routing, incorrect geometry/entity routing,
and planned thesis detail placed in a skill body.

The scaffold references now state that skills own activation, routing,
read-first evidence, handoffs, and verification loops only. Durable truth must
live in the owning thesis, docs, package source, package `AGENTS.md`, or memory
state surface and be referenced through `metadata.canonical_sources`.

## Verification

- `make scaffold-audit`
- `make scaffold-audit-self-test`
- `cd aria_nbv && uv run ruff check ../scripts/scaffold_audit.py`
- `aria_nbv/.venv/bin/python -m py_compile scripts/scaffold_audit.py`
- `make agents-db AGENTS_ARGS='validate'`
- `make check-agent-memory`
- `git diff --check -- Makefile scripts/scaffold_audit.py .agents/references/scaffold_routing_fixtures.json .agents/references/skill_style_guide.md .agents/references/source_order.md .agents/references/verification_matrix.md .agents/skills/code-review-aria-nbv .agents/skills/code-review`
