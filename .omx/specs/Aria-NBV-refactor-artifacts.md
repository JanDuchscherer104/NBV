# Aria NBV refactor artifacts

## Purpose

Persistent entry point for autoresearch and planning about the planned
`aria_nbv` package refactor. The listings below are intentionally a compact
`ls -lat` inventory of the relevant plan, spec, and context artifacts.

Start with live post-PR15 source, package `AGENTS.md`, and Graphify; these
artifacts provide historical evidence and decisions, not a replacement for
current imports, tests, or public contracts.

## Recency And Retention Rules

- Newer artifacts have higher default weight because they reflect newer source
  and may explicitly correct earlier proposals.
- Recency is not automatic supersession. Later artifacts can omit relevant
  constraints, evidence, rejected alternatives, or unresolved decisions.
- When aggregating, read the newest applicable artifact first, then trace each
  material decision through earlier artifacts before discarding it.
- Discard an earlier claim only when current source disproves it or a newer
  artifact explicitly supersedes it; record the reason in the new plan.
- Resolve conflicts against live source, package guidance, and tests, never by
  recency alone.

## ~/repos/ARIA-NBV/.omx/plans

-rw-------  1 jd jd  4765 Jul 10 09:09 autopilot-aria-nbv-oracle-metrics-refactor-20260709T165010Z.md
-rw-------  1 jd jd 23224 Jul  9 18:10 ralplan-rri-rollouts-oracle-pipelines-architecture-20260709T115007Z.md
-rw-------  1 jd jd 25347 Jul  9 18:06 plan-aria-nbv-oracle-module-refactor-20260709T123231Z.md
-rw-------  1 jd jd 10230 Jul  9 14:19 ralplan-rri-rollouts-oracle-pipelines-architecture-handoff-20260709T115007Z.json
-rw-------  1 jd jd  1639 Jul  9 14:19 ralplan-rri-rollouts-oracle-pipelines-architecture-critic-review-20260709T115007Z.md
-rw-------  1 jd jd  2128 Jul  9 14:15 ralplan-rri-rollouts-oracle-pipelines-architecture-architect-review-20260709T115007Z.md
-rw-------  1 jd jd 21537 Jul  9 13:17 ralplan-rri-metrics-architecture-20260709T094553Z.md


## ~/repos/ARIA-NBV/.omx/specs

drwx------  2 jd jd  4096 Jul 10 10:34 autoresearch-aria-nbv-module-pruning-20260709
drwx------  2 jd jd  4096 Jul 10 09:09 autoresearch-aria-nbv-module-pruning-revision-20260710
drwx------  2 jd jd  4096 Jul  9 15:22 autoresearch-aria-nbv-oracle-boundaries-20260709
-rw-------  1 jd jd 12249 Jul  9 13:59 rri-rollouts-oracle-pipelines-architecture-review-20260709T115007Z.html
-rw-------  1 jd jd 10364 Jul  9 12:26 rri-metrics-architecture-review-20260709T094553Z.html
drwx------  2 jd jd  4096 Jul  8 11:54 autoresearch-aria-nbv-refactor-evidence-20260708

## ~/repos/ARIA-NBV/.omx/context

-rw-------  1 jd jd   2983 Jul  9 18:56 autopilot-aria-nbv-oracle-metrics-refactor-20260709T165010Z.md
-rw-------  1 jd jd   8289 Jul  9 13:59 rri-rollouts-oracle-pipelines-architecture-20260709T115007Z.md
-rw-------  1 jd jd   6483 Jul  9 12:24 archive-rl-interpretability-20260709T100521Z.md
-rw-------  1 jd jd   4622 Jul  9 11:46 rri-metrics-architecture-20260709T094553Z.md
-rw-------  1 jd jd   6069 Jul  8 19:33 post-pr15-architecture-refactor-20260708T173316Z.md
