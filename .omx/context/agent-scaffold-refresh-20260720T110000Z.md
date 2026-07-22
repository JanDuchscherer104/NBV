---
kind: context
task_slug: aria-nbv-agent-scaffold-refresh
baseline_commit: 57457ec31e0d3b56da7cb6ebdbb9fde6166de434
revision: 2026-07-22
---

# ARIA-NBV Agent Scaffold Refresh Context

## Role

This file is source-backed planning evidence for the successor scaffold plan. It
does not own decisions or acceptance criteria. Within the bundle, the plan owns
decisions, the test specification owns acceptance criteria, reviews bind exact
artifact hashes, and the handoff binds the accepted bundle.

## Task

Produce a consensus implementation plan for simplifying and updating the
ARIA-NBV agent scaffold on branch `docs-update-latest` without resuming the
quarantined implementation work.

## Baseline

- Branch: `docs-update-latest`
- Commit: `57457ec31e0d3b56da7cb6ebdbb9fde6166de434`
- Working-tree changes are excluded from the baseline. Implementation starts in
  a clean sibling worktree or an explicitly reviewed descendant.
- Prior approved scaffold plan:
  `.omx/plans/ralplan-aria-nbv-agent-scaffold-simplification-20260714.md`
- Accepted predecessor handoff:
  `.omx/plans/ralplan-aria-nbv-agent-scaffold-simplification-20260714-handoff.json`
  at SHA-256 `c2c9c9381e40fd2f63bfe7343cd2f56120437aa3e46f9a740ab79b250446d61e`;
  its embedded 17-artifact manifest and hashes define the predecessor bundle.
- Prior decision record:
  `.omx/specs/aria-nbv-agent-scaffold-simplification-20260711/decision-record.md`
- The existing scaffold implementation worktree remains quarantined until the
  successor context, plan, test specification, reviews, and handoff agree by
  exact hash.

## Resolved Direction

1. Current accepted OMX bundle members remain tracked in their native role
   paths under `.omx/context`, `.omx/specs`, and `.omx/plans`; acceptance is
   registry state, not relocation.
2. Superseded accepted bundles remain tracked under the reserved
   `.omx/archive/accepted-bundles/<bundle-id>/` namespace. Native OMX runtime
   archives elsewhere under `.omx/archive` remain ignored and unregistered.
3. WP1 receives planning bytes only through a deterministic content-addressed
   seed exported from the exact approved handoff manifest. Bootstrap never reads
   the dirty main worktree or quarantined implementation worktree.
4. Graphify becomes the primary project navigation and impact-analysis layer
   when its partition freshness and provenance gates pass. Exact source remains
   authoritative.
5. The canonical graph is one tracked graph with `code`, `scaffold`, `thesis`,
   and `literature` partitions. A generated wiki is neither tracked nor
   required.
6. Canonical graph content is derived only from corpus sources. Agent answers,
   reflections, query expansions, runtime state, and learned lessons are not
   graph inputs.
7. Selected pinned Matt Pocock skills provide generic engineering disciplines.
   ARIA skills retain project-specific operational contracts only.
8. Retain exactly nine ARIA skills, including `agents-db` and
   `measured-autoresearch`.
9. Keep the current agents-DB and non-trivial-work debrief policy. Retire
   `.agents/memory/state` only after selective, source-backed migration.
10. Remove active LitKG and broad generated-context machinery only after closed
   capability and consumer inventories prove replacement or intentional
   retirement.

## Current Evidence

- The baseline contains 21 model-visible ARIA-local skills. The successor target
  is nine: `aria-nbv-context`, `aria-docs`, `agents-db`, `dataset-cache-ops`,
  `lrz-ai-systems`, `plan-grill`, `python-docstrings`,
  `rerun-nbv-inspector`, and `measured-autoresearch`.
- `measured-autoresearch` is an ARIA sidecar for measurement-gated OMX research
  loops and retains its helper and tests.
- `.agents/memory/state` is stale relative to active code, docs, and agents-DB
  owners. Its unique current facts require a selective disposition ledger; Git
  history is sufficient for discarded journal history.
- The agents-DB TOMLs remain active owners and are not part of state-journal
  retirement.
- Graphify freshness currently fails, so the existing graph cannot establish
  current architecture truth. The successor plan must preserve exact-source
  fallback and define deterministic partition freshness.
- Existing `.omx/archive` entries include native OMX runtime archives. A tracked
  accepted-bundle archive therefore requires a reserved child namespace rather
  than treating all of `.omx/archive` as registry-owned.
- The baseline tracks two pre-policy standalone plans:
  `.omx/plans/measured-autoresearch-sidecar.md` and
  `.omx/plans/thesis-method-registry-restoration-ledger.md`. Neither is an
  accepted bundle. WP1 untracks both after recording hashes and verified source
  replacements; Git history preserves their provenance.
- Broad `make context` and `context-heavy` outputs duplicate navigation. Narrow
  source inspection remains useful for contracts, QMD/Typst outlines and
  includes, bounded trees, and a scoped package-only UML command.
- LitKG currently overlaps navigation, claim checking, literature ingestion,
  enrichment, export/runtime, MCP, and refresh wiring. Every capability requires
  an explicit replaced, preserved, or retired disposition before deletion.

## Prior Decisions Retained

- Root `AGENTS.md` remains the dispatcher and nearest `AGENTS.md` files own
  domain invariants.
- Delete the universal `agent-behavior` activation tax only after its unique
  safeguards move to root guidance.
- Collapse ARIA-local skills to a small operational portfolio.
- Remove stale generated context after replacement evidence exists.
- Treat generated graphs as navigation evidence, never source authority.
- Preserve the current non-trivial-work debrief contract and agents-DB routing.
- Keep `python-docstrings` and Quartodoc validation; defer a repository-wide
  docstring checker.
- Permit durable human-oriented READMEs, but not symbol inventories, generated
  matrices, or agent-routing duplication.

## Superseded Decisions

- `.omx/**` is not purely operator-local: accepted current bundle members and
  superseded accepted bundles are versioned through a registry.
- Accepted current bundles do not move to a synthetic acceptance tree; they stay
  in native OMX role paths.
- Superseded accepted bundles do not share an undifferentiated archive namespace
  with runtime archives; they use `.omx/archive/accepted-bundles/`.
- Graphify is no longer an optional untracked side channel, but no generated
  wiki becomes canonical.
- Matt skills are selected generic disciplines rather than reference material.
- Event-triggered-only debriefs are not adopted.
- `context_map.md`, AST inventories, generated indexes, aggregate snapshots,
  broad UML integration, and custom literature wrappers are not retained.

## Constraints

- Planning artifacts only; no scaffold implementation in this revision.
- Do not modify operator-owned generated guidance or commit operator-specific
  absolute plugin-cache paths.
- Preserve source authority in code, tests, package guides, thesis/docs owners,
  tracked accepted decisions, and the agents DB.
- Graphify and skills route to owners; they do not become semantic owners.
- Do not replace stale state journals with another hand-maintained status mirror.
- Prefer independently reviewable workpackages and phased gates that account for
  known baseline failures.

## Required Successor Outputs

- Source-order and bundle-internal authority model.
- Exact disposition of all 21 ARIA-local skills.
- Selected Matt skill portfolio and invocation posture.
- Native-path current OMX lifecycle plus collision-safe superseded archive.
- Graphify corpus, provenance, freshness, commit-pair, and fallback contracts.
- Migration map for `.agents/memory/state` and LitKG capabilities.
- Ordered WP0-WP7 packages, phased tests, rollback and stop conditions.
- Exact-hash Architect then Critic review and successor handoff.
