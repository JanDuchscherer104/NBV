# Teaching-First Section Contract

Use this task-local worksheet before drafting a substantial thesis unit. Active
thesis, literature, notation, code, test, and evidence owners remain
authoritative.

## Reader transition

- Destination chapter and matching `reader-state.toml` record.
- Incoming reader state: what may safely be assumed.
- Active reader question: the uncertainty this unit resolves.
- One to three durable takeaways.
- Outgoing dependency: what the next unit may safely use.
- Main-text or appendix destination.

## Lesson shape

Record the explanation before writing paragraphs:

1. **Plain answer:** one or two sentences without project identifiers.
2. **Teaching device:** a concrete geometric case, worked example,
   counterexample, figure, or limiting case.
3. **Mechanism:** the causal, geometric, statistical, or algorithmic relation
   the example reveals.
4. **Formalism:** the minimum terms, symbols, equations, and assumptions needed
   to state that mechanism precisely.
5. **Interpretation:** what changes the quantity or behavior, what remains
   invariant or equivariant, and why the result matters.
6. **Boundary:** the limitation or alternative explanation that affects the
   reader's conclusion.

The order may be compressed, but a formal object cannot precede the intuition
that gives it a job.

## Claim and evidence notes

For each substantive claim, record scope, strength, exact evidence identity,
falsifier, and material limitation. This is construction machinery, not a
sentence template. Project only the qualifications needed for comprehension or
scientific assessment into the prose; keep hashes, schema keys, file paths,
gate states, and exhaustive provenance in their owning artifacts or an explicit
implementation/reproducibility surface.

## Language and notation

- Conceptual reasoning uses stable scientific terms.
- Formal relations use canonical owners in `docs/typst/shared`.
- Code or protocol names appear only when implementation correspondence is the
  subject, after the concept has been introduced.
- A comparison is active only when both alternatives are relevant to the
  current reader question.

## Ready bound

The contract is complete when a technically competent reader with only the
incoming state can follow the example, explain the mechanism, decode the
formalism, state the conclusion and limitation, and identify what the next unit
can now assume.
