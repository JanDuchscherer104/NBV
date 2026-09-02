# Reader-Centred Exposition

Read this for multi-paragraph, section, chapter, outline, prose-flow, or
equation-exposition work. Optimize for a technically competent reader who does
not possess the author's repository context.

## Reader-state ledger

For thesis work, begin with the matching record in
`docs/typst/thesis/development/reader-state.toml`:

`enters knowing X → asks Y → learns through example and mechanism → leaves
knowing Z → Z enables the next unit`

The ledger is authored editorial intent, not a summary generated from the
current prose. If prose and ledger disagree, determine which learning journey
is intended before polishing either. Update the ledger only when the chapter's
question, prerequisites, takeaways, teaching device, or outgoing dependency
changes.

## Teaching ladder

Prefer this epistemic order for a new abstract idea:

1. **Phenomenon:** show the concrete 3D, temporal, or empirical situation.
2. **Question:** state the uncertainty the reader should now care about.
3. **Mechanism:** explain the relation that resolves the uncertainty.
4. **Formal model:** introduce terms, symbols, and equations as compression.
5. **Interpretation:** explain behavior, edge cases, and scientific consequence.
6. **Boundary:** state the limitation or unresolved alternative that changes the
   conclusion.

Not every paragraph needs all six stages. Every major abstraction needs the
whole path somewhere before later reasoning depends on it.

## Intellectual spine

Expose the central problem, established premises, unresolved dependency, and
reason for the next unit. Order by epistemic dependency rather than research
chronology, repository layout, implementation call order, or source order.
Each chapter should resolve one principal reader question and leave one to
three durable takeaways.

Use synthesis bridges to state what a section established and why that result
makes the next section necessary. Repair coherence by changing reasoning order
before adding connective phrases.

## Paragraph and sentence flow

Give each paragraph one dominant move: motivate, define, explain, derive,
demonstrate, compare, qualify, interpret, or connect. Use
context → content → consequence:

1. orient from knowledge already established;
2. advance one explanation, derivation, comparison, or item of evidence;
3. land the consequence the next paragraph can inherit.

Keep known information in topic position and important new information toward
stress position. Split a sentence when it asks the reader to process several
new distinctions, caveats, or alternatives before reaching its main predicate.

## Positive definitions and active comparisons

State what the selected construct is, how it works, and why it is needed before
introducing alternatives. A comparison belongs only when the alternative is
already active in the reader's model or directly answers the current question.
Move design-space inventories and rejected options to a compact comparison,
appendix, development note, or outlook.

## Concept, symbol, and implementation layers

Use three explicit layers:

1. **Concept:** ordinary scientific language for reasoning.
2. **Formalism:** canonical mathematical notation for precise relations.
3. **Implementation mapping:** code names, protocol fields, configuration
   values, report keys, and artifact identities.

The main argument normally uses the first two. Introduce the concept before its
symbol, and both before an implementation mapping. Do not replace every code
identifier with a symbol; many implementation names should disappear from the
reader-facing prose.

## Equation exposition

For every consequential displayed equation:

1. motivate the ambiguity or question that requires it;
2. define the measured or predicted quantity conceptually;
3. display the equation;
4. decode symbols, indices, domain, frame, and units locally;
5. explain how the quantity behaves and give an example, edge case, or limiting
   case;
6. state the consequence for the following argument.

A glossary and list of symbols are reference aids, not substitutes for local
teaching.

## Main text and appendix

Keep a premise in the main text when it is required for the central conclusion,
method comprehension, validity assessment, or repeated reasoning. Move
exhaustive implementation mapping, provenance, diagnostics, alternatives, and
reproduction detail to an appendix or owning artifact. If ordinary reasoning
repeatedly requires an appendix, repair the abstraction boundary.

## Completion

The candidate is structurally ready when every substantial unit has an
incoming state, one principal question, one to three takeaways, a teaching
device, and an outgoing dependency; concepts precede uses; equations complete
the exposition loop; paragraphs land consequences; implementation vocabulary
is confined to explicit mappings; and the main text remains sufficient for the
central argument.
