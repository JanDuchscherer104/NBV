---
id: 2026-08-26_reader_centred_scientific_writing
date: 2026-08-26
title: "Reader-centred scientific writing contracts"
status: done
topics: [scaffold, academic-writing, literature, scientific-review, typst]
confidence: high
canonical_updates_needed:
  - .agents/skills/literature-research/SKILL.md
  - .agents/skills/academic-writing/SKILL.md
  - .agents/skills/academic-writing/references/reader-centred-exposition.md
  - .agents/skills/scientific-review/SKILL.md
  - .agents/skills/typst-authoring/SKILL.md
touched_owner_paths:
  - .agents/skills/literature-research/SKILL.md
  - .agents/skills/literature-research/references/workflow.md
  - .agents/skills/academic-writing/SKILL.md
  - .agents/skills/academic-writing/references/reader-centred-exposition.md
  - .agents/skills/scientific-review/SKILL.md
  - .agents/skills/typst-authoring/SKILL.md
  - scripts/scaffold/fixtures/routing.json
  - scripts/scaffold/run_routing_trials.py
codex_thread: codex://threads/01a03d93-b37f-7643-be5d-b3afb21284be
repo_object_format: sha1
repo_head: 46c61ace8ba6280f1faa3fecf724f96a8034cf38
repo_branch: "codex/reader-centred-scientific-writing"
worktree_kind: linked
---

## Task

Refine the four scientific-writing lanes after PR #139 with a reader-centred,
argument-driven information-flow contract.

## Method

Added one progressively disclosed academic-writing reference for reader-state
progression, epistemic dependency order, context-content-conclusion,
known-to-new flow, narrative economy, and main-thread integrity. Kept discovery,
argument construction, frozen review, and Typst realization as separate owners.

## Findings

`literature-research` now exposes conceptual dependencies and disconfirming
evidence without deciding the narrative. `academic-writing` owns reader-state
and section/paragraph flow. `scientific-review` applies the shared contract to a
frozen candidate without rewriting it. `typst-authoring` preserves accepted
semantic order and returns meaning-changing layout work to academic-writing.

## Commits

- https://github.com/JanDuchscherer104/ARIA-NBV/commit/46c61ace8ba6280f1faa3fecf724f96a8034cf38

## Verification

Passed four skill quick validators, 111 targeted tests plus 62 subtests, G002
governance tests, scaffold audit, and scaffold self-test. An independent
read-only forward-test also passed pointer, owner, evidence-scope, absence of
thesis mutation, and no-fifth-skill checks. The optional live routing trial was not run
because `ARIA_NBV_ROUTING_TRIAL_PROXY_URL` was not configured.

## Canonical Owner Impact

The four skill lanes and deterministic routing fixtures now carry the durable
reader-centred behavior. No active thesis source, bibliography record,
literature manifest, release state, or scientific claim changed.
