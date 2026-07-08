# Upstream Matt Pocock Guidance For ARIA Code Review

Use this as reference-only inspiration from Matt `code-review`.

Borrow:

- separate Standards review from Spec review when both matter;
- treat code smells as judgement calls, not automatic blockers;
- compare against a fixed point or explicit review surface;
- preserve the originating spec, issue, PRD, or plan as evidence.

ARIA differences:

- `code-review-aria-nbv` owns ARIA severity, domain invariants, and local
  evidence.
- Concrete ARIA diffs route through this skill, not raw generic Matt
  `code-review`.
- Geometry, target-RRI, rollout, dataset/cache, docs, Typst, and KG findings
  hand off to the smallest ARIA owner.
- OMX or GitHub workflows own their own review mechanics when those surfaces are
  explicitly invoked.
