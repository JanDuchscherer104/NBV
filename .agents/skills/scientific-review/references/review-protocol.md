# Independent review protocol

1. Freeze the candidate digest, scope, and review question. Independent means a
   fresh reviewer context receives only that packet and exact owner locators,
   rather than the authoring rationale; otherwise label the result advisory.
2. Choose applicable checks and inspect exact code, data, configuration, source,
   and report owners rather than summaries.
3. Record every finding as `severity`, `evidence`, `reason`, `action`, and
   `gate`: use `blocking` when the candidate's empirical protocol, estimand,
   evidence, or claim scope is unsound; use `advisory` for a non-blocking
   improvement; use `clear` when no finding blocks the reviewed scope.
4. Return findings with reviewer provenance and candidate identity. The owner
   decides whether and how to mutate, then may request a fresh review.

Review does not establish release, novelty, or a candidate's phase transition.
Only the authoring owner resolves a blocking finding; empirical-result content
cannot become `ready-for-realization` before a candidate-bound review reports
no blocking finding.
