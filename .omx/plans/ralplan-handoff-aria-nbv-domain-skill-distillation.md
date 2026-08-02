---
kind: ralplan-handoff
status: complete
slug: aria-nbv-domain-skill-distillation
terminal_planning_state: complete
amended: 2026-08-01
implementation_go_no_go: go
ralplan_consensus_gate:
  complete: true
  order:
    - architect
    - critic
---

# Ralplan handoff: ARIA-NBV domain-skill distillation

## Planning artifacts

- Context:
  `.omx/context/aria-nbv-domain-skill-distillation-20260801T083021Z.md`
- Approved PRD:
  `.omx/plans/prd-aria-nbv-domain-skill-distillation.md`
- Approved test specification:
  `.omx/plans/test-spec-aria-nbv-domain-skill-distillation.md`
- Prior approving Architect review:
  `.omx/plans/ralplan-architect-review-aria-nbv-domain-skill-distillation-consensus-loop-3-iteration-2.md`
- Prior approving Critic review:
  `.omx/plans/ralplan-critic-review-aria-nbv-domain-skill-distillation-approved.md`
- Approving amendment Architect review:
  `.omx/plans/ralplan-architect-review-aria-nbv-domain-skill-distillation-amendment-20260801.md`
- Approving amendment Critic review:
  `.omx/plans/ralplan-critic-review-aria-nbv-domain-skill-distillation-amendment-20260801.md`

## Consensus outcome

1. Preserve the staged `python-docstrings` deletion as WP1 after WP0 freezes
   routing evidence; do not fold it into another cleanup.
2. Treat all nine scoped skills as model-invoked hypotheses whose independent
   identities are earned through leading-word, branch, and survivor-
   discoverability evidence.
3. Evaluate four in-scope mergers; keep docs-curator/Typst as a handoff-only
   boundary. Failure or inconclusive evidence retains separate skills.
4. Move facts to verified Typst/code/docstring/README/AGENTS owners in prerequisite
   packages before destructive skill distillation.
5. Introduce the temporary explicit `NATIVE_MINIMAL_SKILLS` discriminator so
   metadata absence cannot silently select the permissive schema.
6. Include exact routing/UI/current-backlog consumer bundles in candidate probes,
   merged workpackages, and rollback. WP14 verifies rather than repairs them.
7. If multiple mergers pass, run the bounded combined state and one rollback
   probe per selected merger; retain an implicated component on conflict or
   ambiguity.
8. Migrate the Rerun contract into package owners only after the rollout
   read-model seam is proven complete or explicitly open.
9. Give every scoped skill one of three evidence-gated dispositions: retain a
   separately distilled minimal skill, merge it into a minimal adjacent
   procedure, or route the branch through existing guidance/procedure and prune
   it. Pointer-only survivors must compete with pruning.
10. Compare separately distilled minimal skills, minimal merged candidates, and
    route-only/prune fallbacks symmetrically; the bloated legacy body is evidence,
    not the separate candidate.
11. Classify claims before migration: scientific meaning -> Typst/exact source;
    executable contracts -> code/config/docstrings/tests; durable subsystem
    orientation -> README; invariants/routing/verification -> nearest AGENTS;
    repeatable procedure -> skill.
12. Use branch-local owner localization and keep only minimal stable execution or
    verification commands in skills. Command inventories, semantics, schemas,
    versions, and defaults remain with their executable/documentation owners.
13. Treat observed JSONL/tool events and actual under-probe opened paths as the
    authority for native probes. Keep the shared smoke tiny and repeat trials
    only when stochastic invocation materially decides identity.

## Implementation gate

**IMPLEMENTATION GO/NO-GO: GO.**

The implementation preflight passed on 2026-08-01 in the clean dedicated
worktree `/home/jd/repos/ARIA-NBV-domain-skill-distillation`, branch
`codex/domain-skill-distillation`, at frozen baseline
`d1bfef7d904626bdd1e196377c34c99eefc516fa`. That revision tracks the approved
PRD, test specification, handoff, context, and approving reviews; the primary
checkout's unrelated dirty paths were not copied. `python-docstrings` is already
isolated in commit `773992f3712b5d1efb9f09066bbb63cea2f042a0`.

Fresh baseline commands all exited zero:

- `make scaffold-audit` (`21` warnings, no errors);
- `make scaffold-audit-self-test` (`11` passed, no failures, G002 `6` passed);
- `make check-agent-memory`.

Graphify freshness exited `1`, so implementation uses the approved exact-source
fallback. The prerequisites below are therefore satisfied at the selected
revision and WP0 may proceed.

### Prior blocked baseline

Live reinspection on 2026-08-01 found branch
`codex/mempalace-agent-scaffold` at `438bbb53f2569bf4f66766b0c0382a65428f7eb8`.
The approved plan artifacts are still untracked; the primary worktree contains
overlapping Graphify/MemPalace/scaffold edits and the staged
`python-docstrings` deletion. `make scaffold-audit` passes with 21 warnings,
while `make scaffold-audit-self-test` fails because the dirty tree removes
`.codex/config.example.toml`, and `make check-agent-memory` fails because the
dirty validator rejects the still-present vendored Graphify skill. Graphify
freshness exits 1, so exact sources remain the discovery fallback.

Implementation required all of these prerequisites at one selected revision:

1. the amended PRD, test specification, handoff, and approving amendment reviews
   are tracked/frozen;
2. a clean dedicated worktree is created from that revision and the primary
   checkout's unrelated dirty paths are classified but not copied;
3. the Graphify/MemPalace/scaffold cleanup and staged `python-docstrings` deletion
   are absent from the baseline or isolated into their explicitly owned
   workpackages;
4. `make scaffold-audit`, `make scaffold-audit-self-test`, and
   `make check-agent-memory` all exit zero in that clean worktree.

## Execution entry

After the implementation gate becomes GO, start with the execution preflight,
then WP0, WP1, and WP2 in dependency order. Use the approved test specification
as the evidence contract. No domain-skill or owner implementation work was
performed by this amendment.
