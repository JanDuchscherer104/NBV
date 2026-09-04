# Exposition Quality Review Profile

Use this profile for a frozen thesis paragraph, section, chapter, or whole-draft
review focused on educational value, prose, narrative cohesion, reader
knowledge, or equation exposition. Read the applicable record in
`docs/typst/thesis/development/reader-state.toml` before reviewing.

## Review procedure

1. **Reconstruct the reader journey.** State what the candidate assumes, the
   question it actually resolves, what it teaches, and what its successor must
   inherit. Compare that path with the ledger.
2. **Trace the concept dependency.** Mark every term, symbol, distinction, and
   equation used before motivation or definition.
3. **Inspect the teaching path.** For each major abstraction, look for a
   phenomenon or example, mechanism, formal model, interpretation, and boundary.
4. **Separate language layers.** Identify repository identifiers, DTO fields,
   protocol versions, report keys, hashes, masks, and development vocabulary
   that substitute for concepts or canonical notation.
5. **Audit alternatives.** Flag rejected or contrasting options introduced
   before the selected construct is understood or when the comparison does not
   answer the active reader question.
6. **Audit paragraph inheritance.** Give each paragraph one dominant move and
   verify that it lands a consequence used by the next paragraph or section.
7. **Audit equations.** Verify local motivation, conceptual definition, symbol
   decoding, frame/domain/units where relevant, behavior or worked example, and
   interpretive consequence.
8. **Test the summary.** A technically competent reader should be able to
   summarize the candidate without repository context and state the one to
   three durable takeaways.

## Severity

- **P0 — comprehension blocker:** a central conclusion depends on knowledge the
  ledger says the reader does not have; the chapter fails its principal
  question; or formalism is unusable without repository knowledge.
- **P1 — major educational defect:** an important mechanism lacks a teaching
  path; internal identifiers dominate the argument; alternatives bury the
  selected construct; or chapter/section dependencies are reversed.
- **P2 — local prose defect:** a paragraph lacks a landing consequence, repeats
  an owned definition, branches excessively, uses an unhelpful negative
  contrast, or needs a clearer local example.

## Output

For each finding, return severity, exact locator, violated reader-state or
teaching contract, observed effect on comprehension, and the smallest repair.
Separate structural repairs from sentence-level edits. Do not rewrite the
frozen candidate unless the authoring owner explicitly requests a new draft.
