# ARIA-NBV Thesis Writing Guide

This is calibrated for a computer-science master thesis on target-conditioned
next-best-view planning, not for biomedical journal submission.

## Context7 Synthesis

Use the external scientific-writing skills as a pattern library, not as
authority over this thesis. Keep the practices that improve CS/ML thesis prose:

- Draft with bullet outlines, but finish in connected paragraphs.
- Treat IMRAD as reader flow: motivation and gap, reproducible method, factual
  results, bounded interpretation.
- Ground claims in repository artifacts, cited literature, experiments, or
  explicit hypothesis wording. Use `claim-citation-discipline.md` for the claim
  taxonomy and evidence gate.
- Prefer primary sources for specific method, dataset, benchmark, and metric
  claims. Use reviews only for broad context.
- Avoid citation clusters larger than two or three sources unless the sentence
  names what each source contributes.
- Design figures and tables around one takeaway, with captions that state the
  setting, evidence, and supported claim.
- Audit evidence before polishing: scope, strength, falsifier, key support,
  strongest alternative explanation, and limitation.

Do not import generic defaults that conflict with ARIA-NBV:

- mandatory AI-generated graphical abstracts or fixed figure quotas;
- generic "one figure per N words" rules when thesis evidence and page design
  should decide;
- biomedical reporting checklists such as CONSORT, STROBE, PRISMA, STARD, or
  CARE as defaults; use them only if a section genuinely has that study design;
- generic journal-submission framing when the advisor proposal and thesis
  contracts own the audience;
- mandatory external `research-lookup` workflows; use local source order, KG
  checks, and literature indexes when a claim needs evidence;
- image-generation-first workflows, including Nano Banana or generated
  schematic mandates, unless the task explicitly asks for generated bitmap
  figures.

## Writing Modes

Use these nested modes only inside `prose-draft` or `prose-polish`; they are
ARIA adaptations of Matt writing skills, not activated upstream owners. See
[upstream-matt-writing](upstream-matt-writing.md) for the pinned source links and update policy.

`fragment-capture`: use before structure exists. Collect scratch claims,
observations, advisor notes, possible phrasings, examples, objections, and
evidence gaps into a scratch pile. Do not write final thesis claims directly
from fragments; first classify scope, strength, evidence, limitation, and
terminology.

`shape-pass`: use when the input pile is fixed. Start from scoped
claims/evidence, establish what the reader already knows, and draft paragraph
by paragraph. Each paragraph must ground any new concept before later prose
depends on it. If the pile lacks an example, citation, metric, or limitation
the paragraph needs, mark the gap instead of fabricating.

`beat-pass`: use to improve reader journey, transitions, and narrative rhythm.
Advance one reader move at a time: motivation, gap, method consequence,
evidence, limitation, or transition. This is useful for introductions, related
work transitions, discussion, limitations, and advisor summaries; it must not
override method-section contracts, notation rules, or evidence gates.

## Proposal And Thesis Rhetoric

Use a compact ABT/CARS structure:

- AND / territory: active 3D reconstruction, NBV planning, AR guidance,
  semantic scene representations, and learned reconstruction proxies.
- BUT / niche: handheld AR needs target-aware view choice, efficient
  counterfactual candidate evaluation, and leakage-safe oracle supervision.
- THEREFORE / contribution: ARIA-NBV proposes a target-conditioned,
  quality-driven finite-candidate NBV stack and validates it under fixed
  acquisition budgets.

The gap must follow from the context. Do not bolt on "semantic relevance" as a
slogan; state the concrete failure mode it addresses.

## Section Jobs

Abstract or advisor summary: write after the section claims settle. State the
problem, gap, approach, current evidence status, contribution, and main
limitation in plain language.

Introduction: establish why interactive NBV matters, state the limitation of
geometry-only or scene-level framing, introduce ARIA-NBV, and end with precise
contributions.

Related work: organize by intellectual dependency, not a shopping list:
classical NBV, learned NBV, reconstruction-quality proxies/oracle labels,
entity-aware reconstruction, and why the thesis combination remains
non-trivial.

Method/system design: specify input/output contracts, frame conventions,
symbol/equation references, learned vs deterministic components, online vs
offline parts, reproducibility assumptions, and expected failure modes.

Experiments: report dataset/split assumptions, candidate sampling, oracle
labels, baselines, ablations, metrics, aggregation, runtime constraints,
limitations, and threats to validity.

Results: report what was measured before interpreting why it happened. Tie each
result to a metric, split, baseline, uncertainty or aggregation rule, and figure
or table when one carries the evidence.

Discussion: separate what experiments show, what the design suggests, what is
speculative, and what future AR-in-the-loop studies must validate.

## Scoped Claim Scaffold

Before drafting a major section, compress it to one to three scoped claims. For
each claim, record:

1. Claim: the sentence the thesis can defend.
2. Scope: dataset, split, method version, target protocol, metric, or section
   boundary where the claim holds.
3. Strength: established, supported, suggested, or hypothesis.
4. Falsifier: the result, citation, or implementation fact that would force a
   rewrite.
5. Key evidence: citation key, code path, experiment, table, figure, or explicit
   limitation.
6. Limitation: what the claim does not cover.

If this scaffold cannot be filled, write the point as an open question,
limitation, or planned experiment instead of a result.

## Paragraph Unit Test

For each paragraph, ask:

1. What is the paragraph's single job?
2. What concrete claim does it make?
3. What evidence supports it?
4. Which term or symbol must stay consistent with the shared library?
5. Does the last sentence set up the next paragraph?
6. Would a skeptical reader know the scope, evidence, and uncertainty level?

If the answer is unclear, rewrite before polishing.

## Style

Prefer sober, specific prose. Use active voice when it is clearer and shorter,
but do not contort method descriptions to avoid passive voice. Use "significant"
only for statistical significance; use "substantial", "measurable", or the
actual metric change for practical effects. Avoid hedge stacking: choose one of
"suggests", "may", or "could" when evidence is limited.

Bad:

> This work leverages semantic awareness to unlock a powerful and holistic AR reconstruction pipeline.

Good:

> ARIA-NBV scores candidate views by expected reconstruction improvement for the selected target, not only by scene-level surface coverage.

Avoid filler: crucial, pivotal, revolutionary, landscape, delve, holistic,
foster, underscore, pave the way, seamlessly, it is well known that.

## Outline-To-Prose Workflow

1. Write a bullet outline with claims, scope, evidence, limitations, and
   citations.
2. Convert each bullet cluster into paragraphs.
3. Start each paragraph with its job or claim, then add evidence, explanation,
   and transition.
4. Remove bullets from final manuscript sections unless the template requires
   them.
5. Replace generic fluency with mechanisms, metrics, comparisons, or
   limitations.
6. Review in this order: correctness, structure, evidence, then style.
