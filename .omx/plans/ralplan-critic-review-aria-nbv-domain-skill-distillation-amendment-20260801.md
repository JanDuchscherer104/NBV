---
kind: ralplan-critic-review
status: approved
slug: aria-nbv-domain-skill-distillation
amendment: 2026-08-01
---

# Critic review: domain-skill plan amendment

## Verdict

APPROVE. The amendment is actionable and preserves the approved architecture.
Planning consensus may close in Architect -> Critic order. Implementation
remains `NO-GO` until the clean-baseline prerequisites pass.

## Quality audit

- Three dispositions cover all nine scoped skills: retain, merge, and
  route-only/prune.
- Separately distilled minimal, minimal merged, and route-only candidates are
  compared fairly; legacy bodies cannot bias identity decisions.
- The claim-type owner matrix, branch-local localization, and bounded-command
  rule prevent skills, README, and `AGENTS.md` from becoming parallel truth
  stores.
- Native probes use observed JSONL/tool events and actual under-probe paths as
  authority over response self-report.
- The shared smoke is tiny; affected pair-local probes carry the remaining
  coverage; repetition requires a predeclared identity-decisive stochastic case.
- `open` blocks deletion, inconclusive evidence retains, exact consumers remain
  atomic, and rollback stays independent.
- The execution preflight is concrete and the live dirty checkout is reported
  literally rather than used as WP0 evidence.

## Implementation gate

**IMPLEMENTATION GO/NO-GO: NO-GO.**

GO requires the amended plan and both amendment reviews to be tracked at one
selected revision, a clean dedicated worktree from that revision, isolation of
the concurrent scaffold/Graphify/MemPalace and staged-deletion state, and exit
zero from scaffold audit, scaffold self-test, and agent-memory validation.

## Required corrections

None.

Final wording reconfirmation: `APPROVE`. Probe diffs cover every candidate
disposition, and pruned skills require absence/replacement-route proof rather
than retained-skill structure.
