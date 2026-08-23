# Independent review protocol

Read this reference for a scientific red-team. Keep the candidate unchanged.

1. Freeze candidate identity, scope, and review question.
2. Choose only applicable validity checks; inspect exact code, data,
   configuration, source, and report owners rather than trusting summaries.
3. Record each finding as a closed `category`, `severity`, exact candidate-relative
   `evidence` span, `reason`, `impact`, and `action`. Preserve the exact
   candidate SHA-256 and host-generated reviewer provenance; author and reviewer
   identities must remain distinct. Judge severity within the evaluator's
   attested closed lower and upper bounds.
   Distinguish a confirmed defect, evidence gap, and question for the author.
   Do not convert an advisory finding into a release state.
4. Return findings with reviewer provenance and candidate identity. The owning
   lane decides whether and how to mutate the candidate, then may request a
   fresh review. A correction is a new exact candidate artifact: link it only
   after the original report is persisted, using the original trial ID,
   original candidate SHA-256, original report SHA-256, and category.

Review proves neither entailment nor novelty; it exposes risks for owner-led
resolution.
