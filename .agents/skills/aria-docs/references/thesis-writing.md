# Thesis And Proposal Writing Contract

Read this file for thesis/proposal prose, section structure, literature claims,
captions that make scientific claims, or advisor-facing revisions.

## Document Roles

- The active thesis rooted at `docs/typst/thesis/main.typ` is the sole owner of
  scientific narrative and interpretation: research questions, priorities,
  interpretation, and calibrated claim wording.
- The roadmap, research-question, and M1 pages under `docs/contents/thesis/` are
  navigation/reference indexes only.
- The seminar paper records historical implemented evidence; it does not define
  the current thesis target.
- Archived proposal and advisor sources are provenance, not competing current
  owners.
- Code/tests own executable behavior; immutable manifests and evidence bundles
  own empirical measurements and validity; exact external papers own literature
  claims. The thesis cites and interprets these direct sources.

Preserve these roles. Do not copy an older claim into the thesis without
checking current code/tests, empirical artifacts, exact papers, and the active
Typst thesis.

## Claim Discipline

Classify each substantive sentence as a definition, literature claim,
implementation fact, design decision, empirical result, limitation, or
hypothesis/future work. If it has no clear role, remove or rewrite it.

- Literature claims require a resolved key in `docs/references.bib` and an
  exact primary-source locator.
- Implementation claims resolve to current code, tests, and configs.
- Empirical claims resolve to immutable manifests and evidence bundles.
- Empirical claims name the split, metric, direction, aggregation, and
  uncertainty or limitation needed to interpret them.
- Planned target-conditioned scoring, finite-horizon value learning, and
  bridge work must not be described as implemented evidence.
- Use "shows" or "demonstrates" only for direct evidence; use "suggests" or
  explicit hypothesis language for limited evidence. Do not stack hedges.

Apply `.agents/references/direct_source_claim_checklist.md` to advisor-facing
claims. Citations support the claim; they do not replace the ARIA-NBV-specific
mechanism or limitation.

## Prose

1. Outline claims, evidence, scope, limitations, and citations.
2. Convert each coherent cluster into paragraphs.
3. Start each paragraph with its job or claim, then evidence, explanation, and
   transition.
4. Keep final thesis prose in paragraphs unless the template genuinely calls
   for a list.
5. Prefer mechanisms, quantities, comparisons, and limitations over generic
   fluency.

Avoid marketing language and filler such as "revolutionary", "holistic",
"seamless", "pivotal", "delve", or "it is well known". Use "significant" only
for statistical significance.

## Terms And Links

- Write `ARIA-NBV`, not `ARIA NBV`.
- Define next-best view and Relative Reconstruction Improvement on first use;
  use Glossarium-native references for durable terms.
- Keep terms such as candidate pose, candidate view, semi-dense point cloud,
  target-specific RRI, VIN scorer, and oracle label semantically distinct.
- Use `#gh` only for final-worthy pinned code anchors. Use `#gh-wip` and
  `#gh-symbol` as removable drafting aids, following
  `.agents/references/thesis_code_links.md`.
- Code links are navigation and reproducibility aids, not substitutes for
  equations, citations, or experiment manifests.

Compile and inspect all affected pages after multi-paragraph, citation,
cross-reference, glossary, or structural changes.
