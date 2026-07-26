# Writing And Claims

Use this branch for thesis or proposal prose, section structure, citations,
captions that make scientific claims, and advisor-facing revisions. The active
Typst thesis owns the narrative; direct code, evidence artifacts, and papers
own the facts it interprets.

## Drafting Modes

- **Fragment capture:** collect observations, candidate claims, objections,
  evidence gaps, and possible wording before structure exists.
- **Shape pass:** turn a fixed evidence set into scoped claims and paragraphs;
  mark missing support instead of fabricating it.
- **Beat pass:** improve the reader journey one move at a time: motivation,
  gap, method consequence, evidence, limitation, or transition.

Use the smallest mode that matches the draft state. Outline claims, scope,
evidence, limitations, and citations before polishing final paragraphs.
These modes adapt generic writing mechanics only; they remain subordinate to
the thesis evidence, notation, section, and submission contracts.

## Claim Discipline

Classify every substantive sentence as a definition, literature claim,
implementation fact, design decision, empirical result, limitation, or
hypothesis/future work. Unclassifiable prose is usually filler.

Keep discovery, drafting, verification, and submission approval distinct.
Search results, generated summaries, another work's bibliography, agent memory,
and fluent draft prose may locate evidence but do not verify a claim. Verification
opens the owning source or artifact, checks the exact proposition and locator,
and records unresolved or conflicting evidence instead of completing plausible
details.

- Literature claims resolve to an exact primary source and locator; never
  invent a citation key.
- Implementation claims resolve to current code, tests, and active configs.
- Empirical claims resolve to immutable evidence and name the split, metric,
  aggregation, uncertainty, and limitation needed for interpretation.
- Report measured facts before causal interpretation.
- Use strong verbs only for direct evidence; calibrate limited evidence as a
  suggestion or hypothesis.
- Preserve relevant negative, null, failed, blocked, unexpected, and
  inconclusive outcomes; do not curate only successful evidence.
- Apply `.agents/references/direct_source_claim_checklist.md` to
  advisor-facing claims.

Before submission-facing prose is accepted, reconcile repeated units,
denominators, populations, sample counts, labels, methods, configurations, and
reported results across text, figures, tables, code, and immutable evidence.
Name legitimate differences in analysis population or aggregation rather than
silently normalizing them.

Before drafting a major section, reduce it to one to three claim records. Each
record states the defensible claim, scope, strength (`established`, `supported`,
`suggested`, or `hypothesis`), falsifier, key evidence, and limitation. If any
field cannot be supplied, keep the point as an open question, limitation, or
planned experiment rather than a result.

Related-work paragraphs name the subfield, identify the cited contribution,
state the unresolved limitation relevant to the thesis, and use specific
sources. Avoid unassigned citation clusters and generic “many works” openings.

## Section Checks

- **Introduction:** concrete context, gap, scoped contribution, boundaries, and
  testable questions.
- **Related work:** intellectual dependencies and unresolved limitations, not
  a paper list.
- **Method/system:** inputs and outputs, observable versus privileged data,
  equations, learned versus deterministic components, reproducibility
  assumptions, and expected failure modes.
- **Experiments:** population and splits, baselines, ablations, metrics,
  aggregation, uncertainty, runtime constraints, and threats to validity.
- **Results:** measured facts before interpretation, tied to the exact metric,
  population, baseline, uncertainty, and evidence object.
- **Discussion/conclusion:** separate established results, design implications,
  limitations, blockers, hypotheses, and future work.

Reject a section when planned behavior is phrased as implemented evidence or
when unavailable evidence is hidden by fluent prose.

## Draft State

Use the typed owners in `docs/typst/thesis/draft_markers.typ`. Actionable
markers remain visible in development and fail the submission build; descriptive
`thesis_status` blocks may remain when implementation and evidence states are
explicit. Resolve markers into evidence-backed prose, reporting conditions, or
an honest deferred question. Never silently delete a marker or fabricate a
result to make submission mode compile.

Use `#gh` only for final-worthy pinned code anchors. Use `#gh-wip` and
`#gh-symbol` as removable drafting links under
`.agents/references/thesis_code_links.md`.

## Paragraph Check

Each paragraph needs one job, a concrete claim, supporting evidence, explicit
scope, consistent terms or notation, and a transition when another paragraph
follows. Finish in connected prose unless the document structure genuinely
calls for a list. Review in this order: correctness, structure, evidence, then
style.

Prefer sober mechanisms, quantities, comparisons, and limitations. Reserve
“significant” for statistical significance; avoid stacked hedges, marketing
claims, and filler such as “revolutionary”, “holistic”, “seamless”, “pivotal”,
“delve”, or “it is well known”.

The external practices selectively adapted here, and the generic manuscript
machinery deliberately rejected for this thesis, are recorded in
`upstream-scientific-practices.md`.
