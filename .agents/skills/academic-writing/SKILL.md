---
name: academic-writing
description: Use for scientific or thesis prose, chapter or section structure, narrative cohesion, conceptual explanation, equation exposition, Related Work synthesis, or source-grounded argument construction; produce a teaching-first candidate before Typst realization.
---

# Academic Writing

Own the reader-facing scientific argument. Exact literature, code, experiment,
notation, and thesis sources own facts; this skill turns those facts into an
intelligible learning journey. `typst-authoring` owns realization and
`scientific-review` owns independent criticism.

## Teaching-first invariant

Teach the scientific idea before exposing its formal or implementation form.
A technically competent reader should first understand the phenomenon, the
question, and the mechanism; canonical notation then compresses that
understanding. Repository names, DTO fields, configuration discriminators,
artifact keys, and development gates are implementation mappings, not the
language of the argument.

## Workflow

1. **Locate the lesson.** Read the nearest docs guide, the exact destination,
   and the chapter record in
   `docs/typst/thesis/development/reader-state.toml`. For a paragraph or section,
   read [`section-contract.md`](assets/templates/section-contract.md); for
   chapter, outline, prose-flow, or equation-exposition work, also read
   [`reader-centred-exposition.md`](references/reader-centred-exposition.md).
   The step is complete when the incoming reader state, active reader question,
   one to three durable takeaways, teaching device, and outgoing dependency are
   explicit.
2. **Shape the explanation.** Build the shortest dependency chain that lets the
   reader answer the question. Start from a concrete geometric or empirical
   case, expose the mechanism, introduce the formal model, interpret it, and
   state its boundary. Use the ARIA-specific chapter roles in
   [`thesis-writing.md`](references/thesis-writing.md) and
   [`thesis-section-contracts.md`](references/thesis-section-contracts.md).
   The step is complete when every new concept has a prior motivation and every
   formal object has a conceptual job.
3. **Ground the claims.** Read only the exact sources needed by that chain and
   apply [`source-grounded-workflow.md`](references/source-grounded-workflow.md).
   Use the claim and evidence references below only for branches that need
   them. Keep scope, falsifier, provenance, and reviewer notes in the task-local
   contract; project the subset a reader needs to understand or assess the
   claim into the manuscript.
4. **Draft positive-first prose.** Define the selected construct in ordinary
   scientific language before comparing alternatives. Use conceptual wording
   in exposition, shared mathematical symbols in formal relations, and code
   identifiers only in an explicit implementation-correspondence sentence,
   table, or appendix. Give each paragraph one dominant move and a landing
   consequence the next paragraph can inherit.
5. **Run the reader test.** Check that a reader who knows only the recorded
   incoming state can explain the section without repository context. Verify
   every displayed equation through the motivation → concept → equation →
   symbol decoding → behavior/example → consequence loop. Remove unactivated
   alternatives, audit vocabulary, repeated definitions, and process narration.
   If the chapter's learning journey changed, update its ledger record.
6. **Hand off once.** Send a ready candidate to `typst-authoring`. Send leakage,
   confounding, unsupported claims, mathematical inconsistency, or exposition
   risks to `scientific-review`. Do not let layout work silently rewrite the
   argument.

## Conditional references

- Related Work or concept-centred source comparison:
  [`literature-synthesis.md`](references/literature-synthesis.md).
- Claim strength, citation entailment, or empirical results:
  [`claim-citation-discipline.md`](references/claim-citation-discipline.md) and
  [`empirical-reporting-and-reproducibility.md`](references/empirical-reporting-and-reproducibility.md).
- Source coverage, novelty, or screening:
  [`literature-research`](../literature-research/SKILL.md).
- Material source or conclusion change:
  [`change-impact.md`](references/change-impact.md).
- HM/FK07 scientific-practice or declaration compliance:
  [`hm-scientific-practice.md`](references/hm-scientific-practice.md).
- Scratch, shape, and beat mechanics:
  [`upstream-matt-writing.md`](references/upstream-matt-writing.md).
- Candidate realization:
  the shared [academic work phase transition](../README.md#academic-work-phase-transition).

## Handoff

State the destination and ledger entry, incoming and outgoing reader state,
plain-language answer, teaching device, formal objects introduced, source
identities, limitations, phase state, and required verification. The packet is
task-local; active sources remain the durable record.

## Completion

The candidate is ready only when:

- it realizes the recorded reader-state transition and one to three takeaways;
- its central answer can be stated in plain language before notation;
- at least one concrete example, counterexample, figure, or limiting case
  grounds every major abstract mechanism;
- every symbol and equation is locally motivated, decoded, and interpreted;
- internal identifiers appear only where implementation correspondence is the
  subject;
- alternatives are introduced only after the selected construct is understood;
- evidence strength and limitations remain accurate without turning the prose
  into an audit log; and
- the next unit can rely on the stated outgoing dependency without hidden
  prerequisites.
