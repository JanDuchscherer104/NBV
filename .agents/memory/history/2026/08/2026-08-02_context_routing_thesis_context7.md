---
id: 2026-08-02_context_routing_thesis_context7
date: 2026-08-02
title: "Active Thesis and Context7 Context Routing"
status: done
topics: [scaffold, context-routing, typst, context7, graphify]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/skills/aria-nbv-context/SKILL.md
  - .agents/skills/aria-nbv-context/references/context_map.md
  - .agents/skills/aria-nbv-context/references/context7_library_ids.md
  - .agents/skills/aria-nbv-context/references/graphify-aria-boundary.md
  - .agents/skills/aria-nbv-context/scripts/nbv_context_index.sh
  - .agents/skills/aria-nbv-context/scripts/nbv_typst_includes.py
  - .agents/skills/typst-authoring/SKILL.md
  - .agents/skills/typst-authoring/references/packages/index.md
  - .agents/skills/aria-nbv-mermaid/SKILL.md
  - .agents/skills/python-standards/SKILL.md
  - .agents/skills/rerun-nbv-inspector/SKILL.md
  - docs/AGENTS.md
  - Makefile
  - scripts/nbv_typst_includes.py
  - scripts/scaffold/fixtures/routing.json
  - scripts/scaffold_audit.py
  - scripts/tests/test_agent_governance_g002.py
---

## Task

Make general context discovery promote the active thesis and shared scientific-language owners, make Context7 library routing useful without turning the general router into a dependency encyclopedia, and use Graphify only when its projection is eligible.

## Method

- Read the exact thesis, shared Typst, notation, skill, audit, and test owners.
- Ran the Graphify freshness gate before any graph-backed query.
- Resolved high-value Context7 IDs live and kept project-local behavior authoritative.
- Added a failing governance test before changing the routing surfaces.

## Findings

- The context route defaulted to the historical seminar paper and did not make the active thesis, glossary, shared symbols, shared equations, or notation registry a first-class lane.
- The documented root Typst include helper was missing even though the skill, Makefile, and context index referenced it.
- The central Context7 list was effectively an orphaned flat inventory. Two IDs were no longer resolvable, and the Zarr entry was a lower-coverage source than the current documentation surface.
- Context7 metadata had only syntax-level audit coverage and no registry-membership check.
- Graphify was structurally stale: its source revision and built commit did not match HEAD, and the shared glossary owner digest had changed. Exact sources were used instead.
- Detailed Graphify operating rules consumed the general router's hot-path budget despite being needed only after the freshness gate passes.

## Canonical Impact

- `aria-nbv-context` now exposes an active-thesis and shared-scientific-language lane, while `typst-authoring` remains the procedural owner for edits.
- Domain skills carry the small Context7 sets they actually use. The central registry is a fallback inventory and scaffold-audit authority, not a list agents should load eagerly.
- The Typst include helper defaults to the active thesis; the historical seminar route is explicit, with `--paper` retained as a compatibility alias.
- Detailed Graphify boundary rules moved to a one-hop reference so the router remains progressive and compact.

## Verification

- Governance migration tests cover active-thesis routing, shared language owners, Context7 registry membership, and thesis/seminar discovery behavior.
- The scaffold self-test covers unregistered Context7 metadata.
- Targeted Ruff, skill validation, shell syntax, thesis outline/include smoke tests, scaffold audit, memory validation, and whitespace checks were run after the changes.

## Preservation

Pre-existing edits to `AGENTS.md` and `.agents/references/source_order.md`, plus unrelated OMX context and planning artifacts, were not modified as part of this task.
