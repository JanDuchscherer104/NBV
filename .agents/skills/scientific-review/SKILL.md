---
name: scientific-review
description: Use to independently red-team an exact scientific candidate for leakage, confounding, split integrity, uncertainty, baseline parity, freshness, or claim escalation; return advisory findings without mutation.
---

# Scientific Review

Red-team an exact candidate independently. Preserve it, identify
evidence-bounded findings, and return severity, rationale, and an actionable
next step. This skill neither rewrites prose nor owns code, experiments,
literature, bibliography, or Typst sources.

## Workflow

1. Capture the candidate identity, scope, and review question; read its nearest
   owner guidance.
2. Read [`review-protocol.md`](references/review-protocol.md) and the shared
   scientific evidence contract in
   [`empirical-reporting-and-reproducibility.md`](references/empirical-reporting-and-reproducibility.md),
   then load only the applicable checks in
   [`empirical-validity.md`](references/empirical-validity.md).
3. Inspect exact evidence owners and report each finding with severity, locator,
   rationale, and repair action. Separate evidence from inference.
4. Return findings to the owning author or implementation lane. The owner, not
   this review, decides whether to mutate the candidate and may request a fresh
   review afterwards.

## Completion

The unchanged candidate has a reproducible identity, all applicable checks have
an evidence-bounded result, and unresolved risks are explicit for its owner.
