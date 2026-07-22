# Agent Scaffold Consensus Context

## Task

Reconstruct inherited thread `019f4cdc-c90c-7ac3-a16a-1aa5d92fcbdf`, read its
important scaffold artifacts, and produce a `$ralplan` consensus plan for all
supported changes to ARIA-NBV agent guidance, routing, discovery, skills,
Graphify/context tooling, LitKG integration, runtime-state boundaries, and
validation. Work packages should be self-contained and parallelizable where the
dependency graph permits.

## Desired outcome

- One approved planning artifact with a concrete target scaffold.
- A 7–9 skill portfolio classified by independent reach.
- A dependency-aware work-package graph, not a monolithic migration.
- Explicit boundaries between repo-owned truth, OMX/runtime state, optional
  accelerators, generated evidence, and external generic skills.
- Testable acceptance criteria and a durable Architect -> Critic consensus gate.

## Current baseline

- Active branch: `aria-nbv-refactor`.
- Current HEAD: `87cf587e9e64d536b78e8a12f5ddff0fc5636676`.
- Worktree is heavily dirty and contains user-owned staged deletions and unrelated
  code/docs changes. Implementation must use a clean branch/worktree and must not
  absorb current dirt.
- `.gitignore` has a staged change making all `.omx/` operator-local. The inherited
  decision record is force-tracked despite that policy, so durable promotion must
  be resolved explicitly.
- Repo-owned root guidance is 129 lines before the generated OMX overlay; total
  root `AGENTS.md` is 355 lines. The OMX marker block is generated/external and is
  not part of the ARIA text budget.
- There are 20 repo-local skills totaling 2,415 `SKILL.md` lines.
- `scripts/scaffold_audit.py` is 1,038 lines and is not part of `make ci`.
- The generated context suite contains a 256 KB combined snapshot plus large UML,
  docstring, contract, tree, source, and literature catalogs.
- The tracked post-commit hook exits through LitKG before its Graphify block and
  contains a developer-specific interpreter path.
- The default Graphify corpus excludes skills, tests, scripts, configs, root
  `AGENTS.md`, runtime state, and generated artifacts. Current Graphify query
  results therefore cannot fully answer scaffold-impact questions.

## Inherited decisions and evidence

Primary durable sources:

- `.omx/specs/aria-nbv-agent-scaffold-simplification-20260711/decision-record.md`
- `.agents/work/agents-scaffold/ARIA-NBV-agent-scaffold-review-07-11-gpt56pro-1.md`
- `.agents/work/agents-scaffold/ARIA-NBV-agent-scaffold-review-07-11-gpt56pro-2.md`
- `.agents/work/agents-scaffold/ARIA-NBV-agent-scaffold-review-07-11-gpt56pro-3.md`
- `.agents/work/agents-scaffold/mattpocock-skills-integration-gpt55pro.md`
- `/home/jd/.agents/skills/writing-great-skills/SKILL.md`
- inherited rollout summary
  `/home/jd/.codex/memories/rollout_summaries/2026-07-10T16-29-25-AXMj-aria_nbv_scaffold_review_vs_decision_record_20260711.md`

The inherited grill accepted:

- `aria-nbv-context` as discovery control, not a project handbook;
- retirement of `agent-behavior`;
- exact/direct lookup separated from scoped Graphify topology lookup;
- a worktree-aware Graphify provenance gate;
- deletion of the custom generated context suite and custom AST helper;
- explicit-only UML and optional Graphify wiki;
- docstrings plus Quartodoc as Python API documentation owners;
- contract-tiered docstring coverage and a compact retained
  `python-docstrings` skill;
- conceptual/stable `context_map.md`;
- event-triggered debriefs;
- independent-reach skill classification;
- thin root and nested-owner guidance;
- behavior/capability routing fixtures rather than ceremonial exact arrays;
- selective package READMEs;
- production/design-focused default Graphify corpus;
- removal of LitKG from ARIA required/default paths;
- curated literature plus on-demand selected-PDF Graphify and direct source
  inspection as the replacement research path.

The later review comparison strengthened the plan with:

- a firm 7–9 custom-skill budget;
- runtime/privacy cleanup and hook removal before conceptual restructuring;
- removal of code-index from canonical policy (operator-local accelerator only);
- explicit durable-artifact allowlist and runtime denylist;
- use of the current scaffold audit only as a migration guard, followed by a
  small structural checker in CI;
- an optional scaffold Graphify profile and measurable text budgets.

## External skill-writing constraints

Apply `writing-great-skills` as the design standard:

- predictability is the root virtue;
- keep one meaning in one owner;
- model invocation is earned only by independent reach;
- user-invoked skills spend cognitive rather than context load;
- inline only steps every branch needs; use context pointers and progressive
  disclosure for branch-specific reference;
- every step needs a checkable completion criterion;
- delete duplication, sediment, no-ops, and weak negation-heavy prose;
- split only by invocation or sequence when that improves process reliability.

## Planning assumptions

- The target retained local catalog is nine skills unless consensus finds a
  stronger evidence-backed alternative:
  `aria-nbv-context`, `diagnose-aria`, `aria-docs` (merged docs workflow),
  `dataset-cache-ops`, `rerun-nbv-inspector`, `lrz-ai-systems`,
  `counterfactual-rollout-planner`, `plan-grill`, and `python-docstrings`.
- Geometry and entity/RRI invariants move to nearest package guides and tests;
  generic Zarr behavior moves to official docs plus local store owners.
- `agents-db`, generic simplification/review/preflight skills, and LitKG skills
  are candidates for removal. Any backlog migration must be lossless and local;
  this plan does not create external GitHub issues.
- External generic skills such as `writing-great-skills` and `codebase-design`
  remain user-installed/operator capabilities, not vendored ARIA truth owners.
- The generated OMX overlay inside root `AGENTS.md` is preserved byte-for-byte;
  ARIA edits stay outside its markers.

## Likely touchpoints

- `AGENTS.md`, `aria_nbv/AGENTS.md`, `docs/AGENTS.md`, and four nested package
  guides.
- `.agents/skills/**`, `.agents/references/source_order.md`,
  `skill_style_guide.md`, `scaffold_routing_fixtures.json`,
  `verification_matrix.md`, `human_owner_intent.md`, and tool-boundary docs.
- `.gitignore`, `.gitmodules`, `.configs/litkg.toml`, `.graphifyignore`,
  `Makefile`, `scripts/scaffold_audit.py`, context/KG scripts, and tracked hooks.
- `docs/_generated/context/**`, `.agents/kg/**`, and LitKG generated/integration
  surfaces after a consumer ledger proves deletion safety.
- Backlog TOMLs and `agents-db` implementation only in the dedicated lossless
  migration work package.

## Unknowns to resolve in the plan

- Exact nine-skill classification and invocation mode for each retained skill.
- Whether `agents-db` is retired now or in a later optional package.
- Exact durable planning artifact owner after `.omx/` becomes operator-local.
- Minimum Graphify provenance envelope available upstream versus a tiny local
  check; no large wrapper is allowed.
- Exact selected-PDF literature-graph location and claim-verification checklist.
- Which package READMEs have durable human value.

## Stop conditions

- No implementation edits during `$ralplan`.
- No source work on the dirty current branch.
- No execution handoff until Planner, Architect, and Critic consensus is recorded
  in Architect -> Critic order.
- Reject any package that adds a new service, graph backend, parallel truth
  surface, hidden lifecycle mutation, or larger scaffold machinery to replace a
  smaller deleted mechanism.
