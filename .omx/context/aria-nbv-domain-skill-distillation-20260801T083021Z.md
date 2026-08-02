---
kind: ralplan-context
status: current
slug: aria-nbv-domain-skill-distillation
captured_at: 2026-08-01T08:30:21Z
git_branch: codex/mempalace-agent-scaffold
git_head: 779c9e3744e4dba5e2546502d5342ca456d41829
---

# ARIA-NBV domain-skill distillation context

## Task statement

Plan, but do not implement, the pruning, merging, and distillation of these
repo-local skills in accordance with the accepted scaffold target state and the
`writing-great-skills` invocation/progressive-disclosure model:

- `code-review-aria-nbv`
- `counterfactual-rollout-planner`
- `dataset-cache-ops`
- `diagnose-aria`
- `docs-curator`
- `entity-aware-rri`
- `nbv-geometry-contracts`
- `rerun-nbv-inspector`
- `zarr-python`

The user additionally requires removal of
`.agents/skills/python-docstrings/SKILL.md` and requires domain truth to remain
in the active Typst thesis sections, Python code/docstrings, module `README.md`
files, or the applicable `AGENTS.md`, rather than skills.

## Desired outcome

Keep only independently invocable procedural front doors, make the skill
description the precise activation pointer, load branch-specific material only
when needed, and ensure every scientific or implementation claim has a live
non-skill owner. Produce independently green workpackages with a baseline,
rollback boundary, and explicit retained/replaced/removed/deferred/open
dispositions.

## Known facts and evidence

- The target-state specification is accepted and owns this scaffold rework's
  requirements; later plans own sequencing only
  (`.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md:14-30`).
- The specification requires small default context, one durable owner, compact
  procedural skills, and exact-source fallback
  (`.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md:74-91`).
- Skills may own repeatable procedure, activation, handoffs, and verification;
  implementation/scientific facts remain in exact owners
  (`.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md:169-210`).
- A skill must have independent procedural value and a bounded path; split only
  for independent invocation or sequence isolation
  (`.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md:364-391`).
- Destructive consolidation requires the shared owner/progressive-disclosure/
  diagnostic/exact-source smoke set plus a bounded comparison for each removed
  capability (`.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md:572-584`).
- The nine scoped skill entrypoints currently total 1,157 lines. Frontmatter is
  46-57 lines per skill; descriptions range from 128 to 367 bytes.
- `code-review-aria-nbv` is 166 lines and `rerun-nbv-inspector` is 158 lines,
  both above the current 150-line hot-path warning threshold.
- Current `make scaffold-audit` reports 19 skills, 0 errors, and 22 warnings.
  Relevant warnings include semantic drift in counterfactual, docs, entity-RRI,
  and geometry skills and hot-path warnings for code review and Rerun.
- The only direct custom skill-metadata consumer is
  `scripts/scaffold_audit.py`; `scripts/scaffold/fixtures/routing.json` is an
  audit input, `scripts/tests/test_agent_governance_g002.py` checks that fixture,
  Make targets invoke the audit, and CI invokes the self-test. Policy statements
  also live in `.agents/skills/README.md` and
  `.agents/references/source_order.md`. `scripts/quarto_generate_agent_docs.py`
  renders a fixed guidance/context `DOC_SPECS` list and does not consume the nine
  skills or their custom metadata; it is scope-protection evidence, not a WP2
  migration target. Codex runtime discovery is driven by skill frontmatter. The
  audit currently requires nine custom metadata fields and is 994 lines
  (`scripts/scaffold_audit.py:21-41,392-523`).
- `writing-great-skills` is an external operator reference used to evaluate
  invocation mode, leading words, information hierarchy, and pruning. It is not
  an ARIA truth owner. The nine scoped skills currently need autonomous reach
  because root/nearest routing and adjacent-skill handoffs select them without an
  explicit `$skill` request; that model-invocation hypothesis must be frozen and
  tested per skill in WP0 rather than assumed from existing descriptions.
- The routing fixture covers code review, diagnosis, docs, entity-RRI, geometry,
  Zarr, and the Python-docstring replacement route, but lacks direct positive
  cases for counterfactual rollout, dataset-cache operations, and Rerun
  inspection (`scripts/scaffold/fixtures/routing.json`).
- `python-docstrings/SKILL.md` is already staged for deletion by pre-existing
  worktree state. Its complete former behavior was a 30-line compatibility
  handoff to `python-standards`; no live tracked consumer outside history/runtime
  artifacts references the deleted skill path.
- Graphify freshness fails at this HEAD, so this plan uses exact source files
  rather than graph output.
- `rerun-nbv-inspector` currently names three files under its own `references/`
  as canonical sources. `nbv-inspector-contract.md` contains ARIA sample,
  candidate, geometry, output, and test contracts, while the package has no
  module `README.md` or nested `AGENTS.md`.
- `counterfactual-rollout-planner` and `entity-aware-rri` still point to Quarto
  roadmap/theory pages and memory state as owners, although the accepted model
  makes `docs/typst/thesis/sections/` the active thesis narrative owner.
- `dataset-cache-ops` duplicates owner pointers and maintains implementation
  path/version/migration detail already suited to data-handling code, its module
  README, or its `AGENTS.md`.
- `docs-curator` overlaps `typst-authoring` on Typst authoring. Its independent
  invocation value is Quarto/bibliography/navigation/public-boundary curation.
- Dataset operations versus Zarr API/layout work, geometry contracts versus
  Rerun visualization, target-RRI semantics versus rollout planning, diagnosis
  versus review, and docs curation versus Typst authoring are distinct invocation
  branches; merging them would trade description count for a larger ambiguous
  branch surface.

## Constraints

- Planning mode only. Writes are limited to `.omx/context/`, `.omx/plans/`, and
  the durable consensus handoff.
- Preserve the staged `python-docstrings` deletion and all unrelated dirty or
  untracked user work; do not stage, revert, or modify implementation files.
- Do not silently resolve accepted-spec open decisions or change the accepted
  requirements.
- Prefer deletion and existing owner surfaces over new reference layers or
  custom machinery.
- Lock retained capability before any implementation-time prune or merge.
- One workpackage/PR must have one concern, one owner for each moved fact, focused
  verification, and an independent rollback boundary.
- Historical transcripts/debriefs remain evidence and need not be rewritten to
  remove old skill names.

## Open questions for implementation-time evidence

- Which Rerun contract sentences are already expressed in public code docstrings
  and tests, and which must move into a new package `README.md` or nearest
  `AGENTS.md` before the skill references can be demoted or deleted?
- Which Quarto roadmap/theory claims remain live but absent from the current
  Typst thesis sections? Those are owner-migration gaps, not skill-edit work.
- Can the custom metadata/audit surface be removed in one bounded PR while
  preserving the tiny routing smoke set, or should metadata simplification be a
  separate prerequisite PR?
- Are the large generated symbol matrices in module READMEs still intentional
  human/agent orientation, or later cleanup debt outside this skill-focused plan?

## Likely implementation touchpoints

- `.agents/skills/README.md`
- `.agents/skills/<scoped-skill>/SKILL.md`
- `.agents/skills/<scoped-skill>/agents/openai.yaml` where present
- `.agents/skills/rerun-nbv-inspector/references/*.md`
- `AGENTS.md`, `docs/AGENTS.md`, `aria_nbv/AGENTS.md`
- `aria_nbv/aria_nbv/{data_handling,rollouts,rri_metrics}/AGENTS.md`
- `aria_nbv/aria_nbv/{data_handling,rollouts,rri_metrics,rerun_inspector}/README.md`
- public Python docstrings in the exact `aria_nbv/aria_nbv/` owner modules
- `docs/typst/thesis/sections/03-oracle-and-data-generation/`
- `docs/typst/thesis/sections/04-method/`
- `docs/typst/thesis/sections/05-experimental-design/`
- `scripts/scaffold_audit.py`
- `scripts/scaffold/fixtures/routing.json`
- `scripts/tests/test_agent_governance_g002.py`
