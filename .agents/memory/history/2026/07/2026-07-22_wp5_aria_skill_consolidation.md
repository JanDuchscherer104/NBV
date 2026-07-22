---
id: 2026-07-22_wp5_aria_skill_consolidation
date: 2026-07-22
title: "WP5 ARIA Skill Consolidation"
status: done
topics: [scaffold, skills, routing, ownership]
confidence: high
canonical_updates_needed:
  - AGENTS.md
  - docs/AGENTS.md
  - aria_nbv/AGENTS.md
  - aria_nbv/aria_nbv/data_handling/AGENTS.md
  - aria_nbv/aria_nbv/rollouts/AGENTS.md
  - aria_nbv/aria_nbv/rri_metrics/AGENTS.md
  - .agents/references/skill_style_guide.md
  - .agents/references/scaffold_routing_fixtures.json
---

## Task

Implement approved WP5 after WP4: consolidate active ARIA skills to the exact
eleven-skill transitional boundary while preserving LitKG for WP6, measured
autoresearch helpers/tests, agents-DB ownership, and native debrief behavior.

## Method And Outcome

Closed every retiring skill rule family in
`.agents/baselines/scaffold_wp5_skill_dispositions.csv`, moved missing stable
primers to nearest package guidance, merged Quarto/Typst/Mermaid operations into
`aria-docs`, compacted retained entrypoints, and taught `scaffold_audit.py` to
enforce the inventory and disposition ledger. LitKG and generated-context
machinery were not removed.

## Verification

The local skill validator covered all eleven active skill directories. The
scaffold audit and negative self-test, measured-autoresearch helper tests,
agents-DB checks, agent-memory check, and Graphify source/graph commit sequence
were the completion gates for this workpackage.

## Canonical State Impact

Repository routing and nearest package/docs owners now preserve the retired
skill primers. No execution status was mirrored outside the Ultragoal runtime,
and no Ultragoal runtime file was edited.
