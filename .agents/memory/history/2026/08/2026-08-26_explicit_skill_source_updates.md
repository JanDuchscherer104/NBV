---
id: 2026-08-26_explicit_skill_source_updates
date: 2026-08-26
title: "Explicit Skill Source Updates"
status: done
topics: [agent-scaffold, skills, provenance, upstream-maintenance]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - .agents/skill-sources.toml
  - .agents/skills/update-skill-sources/SKILL.md
  - scripts/skill_sources.py
  - scripts/tests/test_skill_sources.py
codex_thread: codex://threads/01a03d93-b37f-7643-be5d-b3afb21284be
repo_object_format: sha1
repo_head: c564b98dc7df29554110051477b822a01d50e7e6
repo_branch: codex/skill-source-updates
worktree_kind: linked
---

## Task

Provide one standardized route for checking and fetching changes to external
sources behind local skill adaptations, without placing update behavior in any
skill's default routing branch.

## Method And Findings

Added a narrow provenance manifest for six reviewed source bundles and one
explicit-only maintenance skill. The offline validator checks manifest shape,
safe paths, pins, and local consumers. Network checks report drift without
mutation; `fetch` materializes only declared paths at an exact revision into a
new checkout outside the repository. Consumer adaptation and branch creation
remain deliberate, owner-scoped steps.

Default consumers now carry compact grounding IDs and never activate upstream
maintenance. Graphify retains its dedicated byte-identical blob proof, tied to
the manifest pin. Live inspection found Matt writing/scaffold and Graphify
updates available; reviewing those sources remains separate one-source update
work.

## Verification

- `make agents-db-validate check-agent-memory scaffold-audit scaffold-audit-self-test skill-source-self-test ci-impact-self-test graphify-skill-upstream-self-test`
- `pytest -q scripts/tests/test_thesis_literature_provenance.py scripts/tests/test_typst_authoring_hygiene.py scripts/tests/test_routing_trials.py`
- Ruff on the changed Python tooling and tests
- live exact-revision materialization of Karpathy `program.md`

Graphify's local freshness gate remained unavailable because reconciliation of
the inherited semantic graph changed content. Exact source, scaffold, and
byte-identity checks supplied the bounded verification for this workpackage.

## Canonical-State Impact

The manifest, explicit maintenance skill, deterministic tooling, and tests are
the current owners. No separate source catalog or automatic update scheduler was
introduced.

## Commits

- [c564b98dc7df29554110051477b822a01d50e7e6](https://github.com/JanDuchscherer104/ARIA-NBV/commit/c564b98dc7df29554110051477b822a01d50e7e6)
