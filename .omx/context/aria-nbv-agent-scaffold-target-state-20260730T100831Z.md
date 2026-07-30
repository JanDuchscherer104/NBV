# Context: ARIA-NBV Agent Scaffold Target State

## Task

Distill the reviewed ARIA-NBV scaffold intents, invariants, goals, non-goals,
preferences, best practices, conflicts, and historical evidence into one
execution-ready requirements specification before implementation planning.

## Desired Outcome

- One concise, decision-lossless target-state specification.
- Every accepted current requirement, unresolved conflict, and capability at
  risk from destructive cleanup is retained or remains explicitly open.
- The specification is the planning input after explicit human acceptance.
- Existing reports and historical artifacts remain evidence rather than being
  copied into another handbook.

## Known Evidence

- `.agents/references/human_owner_intent.md`
- `.omx/specs/autoresearch-agent-scaffold-rework-20260729/report.md`
- `.omx/specs/autoresearch-agent-scaffold-external-best-practices-20260730/report.md`
- `.agents/references/scaffold_rework/` and its preserved evidence
- June scaffold deep-interview outputs recoverable at Git commit `d24bdd18`
- July simplification and refresh bundles recoverable at Git commit `2fda4412`
- PR #30 experimental branch at audited commit `2b02a3bf`
- Current repository guidance and exact implementation at the active worktree

The review corpus under `.agents/work/agents-scaffold/` has already been
synthesized by the tracked restart report. It is supporting evidence, not an
additional planning input or a reason to create another disposition ledger.

## Constraints

- Do not implement scaffold changes or derive workpackages in this step.
- Do not create a second glossary, ADR hierarchy, artifact registry, knowledge
  graph, transcript corpus, or natural-language policy engine.
- Do not copy raw transcripts, runtime identifiers, machine paths, or private
  evidence into the tracked specification.
- Preserve unresolved decisions as unresolved.
- Use native OMX `.omx/specs/deep-interview-*.md` planning handoff shape.
- Final authority requires explicit human acceptance.
- Keep source docstrings authoritative for Python contracts; Quartodoc is their
  generated human-facing projection.
- Reduce routing and custom scaffold machinery while preserving outcome-level
  capabilities through progressive disclosure and upstream-first reuse.

## Terminology Conflicts

- `context` has been used for startup prompt material, generated navigation,
  task evidence, and project orientation.
- `memory` has been used for current state, debrief history, retrieval, and model
  memory.
- `truth`, `canonical`, and `owner` have sometimes been applied to plans,
  generated views, and graphs that are evidence only.
- `skill` has been used for a capability, its router, and one implementation of
  that capability.

The target specification resolves these by defining owner, authority, evidence,
derived view, router, runtime state, human intent, decision record, plan,
capability, and supersession.

## Pressure Findings

- Single ownership does not mean one giant document; it means one owner for each
  meaning with progressive links between owners.
- Decision-lossless consolidation preserves accepted current intent, unresolved
  conflicts, and capabilities exposed to destructive cleanup. Superseded
  implementation hypotheses may be summarized by source family.
- Upstream-first is a decision rule, not a ban on measured local adapters.
- A passing validator or agent consensus does not confer human acceptance.
- PR #30 is evidence about capabilities and failure modes, not a migration base.
- Graphify must first be decoupled from required routing and then compared with
  exact-source and unmodified-upstream paths. Its final role remains a human
  decision after that experiment.
- Source-owned Typst, code, bibliography, and paper links must remain useful
  without Graphify.
- The final specification must not settle LitKG, state, external-skill, or other
  choices that still require experiments or human decisions. The current
  non-trivial-work debrief policy remains the default pending separate evidence.

## Prompt-Safe Summary Status

`recorded`: this context file is the bounded summary. Full sources remain at the
paths and Git objects listed above.
