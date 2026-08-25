# Independent review protocol

1. Freeze the candidate digest, scope, and review question. Record
   `independence: independent` only when a fresh reviewer context receives that
   packet and exact owner locators rather than the authoring rationale; record
   `independence: same-context` otherwise.
2. Choose applicable checks and inspect exact code, data, configuration, source,
   and report owners rather than summaries.
3. Record every finding as `severity`, `evidence`, `reason`, `action`, and
   `gate`: use `blocking` when the candidate's empirical protocol, estimand,
   evidence, or claim scope is unsound; use `advisory` for a non-blocking
   improvement; use `clear` when no finding blocks the reviewed scope.
4. Return findings with reviewer provenance, candidate identity, and
   independence. The owner decides whether and how to mutate, then may request
   a fresh review.

Review does not establish release, novelty, or a candidate's phase transition.
Only the authoring owner resolves a blocking finding; empirical-result content
cannot become `ready-for-realization` before a candidate-bound independent
review reports no blocking finding. `independence` is separate from a finding's
`gate`: a same-context advisory review cannot unlock that transition.
