# Independent review protocol

Read this reference for a scientific red-team. Keep the candidate unchanged.

1. Freeze candidate identity, scope, and review question.
2. Choose only applicable validity checks; inspect exact code, data,
   configuration, source, and report owners rather than trusting summaries.
3. Record each finding as `severity`, `evidence`, `reason`, and `action`.
   Distinguish a confirmed defect, evidence gap, and question for the author.
   Do not convert an advisory finding into a release state.
4. Return findings with reviewer provenance and candidate identity. The owning
   lane decides whether and how to mutate the candidate, then may request a
   fresh review.

Review proves neither entailment nor novelty; it exposes risks for owner-led
resolution.
