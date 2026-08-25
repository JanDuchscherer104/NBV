---
name: scientific-review
description: Use to independently review an exact scientific candidate for claim, citation, argument, mathematical, research-question, or empirical-validity risks; return advisory findings without mutation.
---

# Scientific Review

Red-team an exact candidate independently. Preserve it, identify
evidence-bounded findings, and return severity, rationale, and an actionable
next step. This skill neither rewrites prose nor owns code, experiments,
literature, bibliography, or Typst sources.

## Workflow

1. Capture the candidate identity, scope, and review question; read its nearest
   owner guidance.
2. Read [`review-protocol.md`](references/review-protocol.md), then select only
   the applicable branch:
   - empirical protocol, leakage, confounding, parity, uncertainty, or artifact
     freshness: academic-writing's
     [`empirical-reporting-and-reproducibility.md`](../academic-writing/references/empirical-reporting-and-reproducibility.md)
     and [`empirical-validity.md`](references/empirical-validity.md);
   - computational model, policy, rollout, or reported-result evidence: the
     [`computational evidence profile`](references/review-profiles.md#computational-evidence);
   - claim/citation entailment, Related Work, contribution scope, or argument
     coherence: academic-writing's
     [`claim-citation discipline`](../academic-writing/references/claim-citation-discipline.md)
     and [`thesis section contracts`](../academic-writing/references/thesis-section-contracts.md);
   - research-question/estimand alignment: the active
     [`research questions`](../../../docs/typst/thesis/sections/01-research-questions.typ)
     plus the applicable section contract;
   - mathematical, notation, or theoretical consistency: the exact local source
     plus [`equations.typ`](../../../docs/typst/shared/equations.typ),
     [`symbols.typ`](../../../docs/typst/shared/symbols.typ), or Typst's
     [`notation policy`](../typst-authoring/references/aria-nbv-notation.md).
   - a derived figure, table, or displayed quantity: the
     [`display provenance profile`](references/review-profiles.md#display-provenance).
3. Inspect exact evidence owners and report each finding with severity, locator,
   rationale, repair action, gate, and review independence. Separate evidence
   from inference.
4. Return findings to the owning author or implementation lane. This review
   never advances a phase state; the owner decides whether to mutate, realize,
   or request a fresh review.

## Completion

The unchanged candidate has a reproducible identity, recorded review
independence, all applicable checks have an evidence-bounded result, and
unresolved risks are explicit for its owner.
