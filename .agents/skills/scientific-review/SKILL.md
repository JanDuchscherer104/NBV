---
name: scientific-review
description: Use when independently red-teaming an exact scientific candidate for leakage, confounding, split integrity, uncertainty, baseline parity, compute, artifact freshness, or claim escalation; advisory and non-mutating by default.
---

# Scientific Review

Red-team the exact candidate independently. Review is advisory and
non-mutating by default: preserve the candidate, identify evidence-bounded
findings, and return severity, rationale, and an actionable next step. Do not
rewrite prose, promote claims, or become owner of code, experiments,
literature, bibliography, or Typst sources.

## Workflow

1. Capture candidate identity and read its nearest owner guidance.
2. Read [`review-protocol.md`](references/review-protocol.md), then load only
   the applicable validity branch in
   [`empirical-validity.md`](references/empirical-validity.md).
3. Check the candidate against relevant evidence and report findings with
   severity, exact locator, rationale, and repair action. Separate evidence
   from inference.
4. Return findings to the owning author or implementation lane. A review can
   recommend a change but cannot apply it or certify scientific truth.

## Completion

Review is complete when the unchanged candidate has a reproducible identity,
all applicable checks have an evidence-bounded result, and unresolved risks
are explicit for the owner.
