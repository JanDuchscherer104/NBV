# Thesis Structure And Include-Graph Autoresearch

Date: 2026-06-18

## Executive Result

`docs/typst/thesis/main.typ` does include the active numbered body, but the
source structure is too implicit and too coarse for the thesis seed's current
scope. The appendix is included through `template/layout/thesis_template.typ`
rather than from `main.typ`, and several distinct scientific concerns are
compressed into large files, especially `sections/03-method.typ`. This makes
the thesis look incomplete even when Typst can reach every current section.

The best next structure is not a generic IMRAD rewrite. ARIA-NBV should use a
computer-science thesis spine with explicit chapters for problem formulation,
oracle/data generation, model architecture, experimental design/results, and
discussion. The active RQ order remains the owner: RQ1 objective/reward, RQ2
offline finite-candidate `Q_H`, RQ3 representation, RQ4 support/scale, RQ5
online discrete bridge, and RQ6 continuous bridge.

## Current Include Graph

| Source | Reachability | Current issue |
| --- | --- | --- |
| `sections/01-introduction.typ` | Directly included by `main.typ`. | Too short for final thesis; needs explicit RQs, contributions, and thesis organization. |
| `sections/02-background.typ` | Directly included by `main.typ`. | Includes related work and geometric-learning theory, but the chapter blends substrate, literature, and theory. |
| `sections/02-01-related-work.typ` | Included transitively from `02-background.typ`. | Correctly reachable; likely should become a larger standalone related-work subsection. |
| `sections/02-02-geometric-learning.typ` | Included transitively from `02-background.typ`. | Correctly reachable; may deserve a dedicated theory chapter or a formal subsection under foundations. |
| `sections/03-method.typ` | Directly included by `main.typ`. | Overloaded: formal state, data generation, backbone/scene encoder, descriptors, candidate replay, architecture, and value model. |
| `sections/03-01-formal-state.typ` | Included transitively from `03-method.typ`. | Correctly reachable; should be promoted to a problem-formulation chapter. |
| `sections/03-02-data-generation.typ` | Included transitively from `03-method.typ`. | Correctly reachable; should be its own oracle/data-generation chapter. |
| `sections/04-evaluation.typ` | Directly included by `main.typ`. | Correctly reachable; should split design, results placeholders, and failure interpretation. |
| `sections/05-conclusion.typ` | Directly included by `main.typ`. | Correctly reachable; final wording must stay conditional until evidence exists. |
| `sections/06-draft-open-work.typ` | Included through `appendix/index.typ`, which is hard-coded inside `thesis_template.typ`. | Reachable but hidden from `main.typ`; this is the main include-graph clarity problem. |
| `appendix/index.typ` | Included by `template/layout/thesis_template.typ` via `include("../../appendix/index.typ")`. | Works, but hides appendix ownership and makes `main.typ` look incomplete. |

## External Writing Guidance Synthesis

The external guidance supports a direct, evidence-oriented thesis structure:

- HM assessment guidance weights content, methodology, results, structure, and
  citation/formatting; the thesis needs clear owner chapters for method and
  results, not only a long method draft.
- TUM CIT records the Informatics master's-thesis processing time as six
  months; the structure should therefore be realistic for a bounded scientific
  report rather than an open-ended system manual.
- General thesis-structure and research-process guidance emphasizes a focused
  research question, background/literature review, method, results,
  discussion, conclusion, and a research design that can answer the question.

Repo-local guidance refines this for ARIA-NBV: current thesis docs and
canonical memory own direction; the seminar paper is historical evidence;
`main.typ` owns thesis prose; claims need close citations and `kg-claim-check`
when advisor-facing.

## Recommended Chapter Tree

Use explicit `main.typ` includes for every numbered chapter and make the
appendix inclusion visible at the root. Prefer chapter index files for larger
chapters so `main.typ` stays readable.

```text
docs/typst/thesis/main.typ
docs/typst/thesis/sections/
  01-introduction.typ
  02-foundations/
    index.typ
    02-01-egocentric-reconstruction-nbv.typ
    02-02-quality-metrics-rri.typ
    02-03-related-work.typ
    02-04-geometric-learning-and-set-models.typ
  03-problem-formulation/
    index.typ
    03-01-research-questions.typ
    03-02-state-action-and-target-contract.typ
    03-03-objective-and-reward.typ
  04-oracle-and-data-generation/
    index.typ
    04-01-ase-and-seminar-substrate.typ
    04-02-target-task-sampling-and-matching.typ
    04-03-candidate-generation.typ
    04-04-rri-labels-and-invalidity.typ
    04-05-rollout-store-and-replay.typ
  05-method/
    index.typ
    05-01-backbone-and-scene-encoder.typ
    05-02-descriptor-and-encoding-plan.typ
    05-03-candidate-set-architecture.typ
    05-04-finite-horizon-qh.typ
  06-experimental-design/
    index.typ
    06-01-gates-and-hypotheses.typ
    06-02-baselines-and-ablations.typ
    06-03-policy-comparison-and-statistics.typ
    06-04-failure-interpretation.typ
  07-results.typ
  08-discussion.typ
  09-conclusion.typ
docs/typst/thesis/appendix/
  index.typ
  a-seminar-substrate-details.typ
  b-geometry-and-frame-contracts.typ
  c-implementation-and-manifest-tables.typ
  d-open-work-and-bridges.typ
```

The existing files can be moved incrementally rather than rewritten in one
large patch. The minimum useful first patch is:

1. Make appendix inclusion explicit from `main.typ` or pass appendix content to
   the template instead of hard-coding it inside `thesis_template.typ`.
2. Split `03-method.typ` into problem formulation, oracle/data generation, and
   model/method chapters.
3. Split `04-evaluation.typ` into experimental design and a results placeholder.
4. Keep `06-draft-open-work.typ` in the appendix and preserve `dashy-todo`
   markers.

## Chapter Goals And RQ Mapping

| Chapter | Scientific job | RQ mapping | Owner sources |
| --- | --- | --- | --- |
| Introduction | Motivate target-conditioned finite-candidate NBV, state contributions, list RQs, and describe thesis organization. | All RQs at summary level. | `roadmap.qmd`, `questions.qmd`, current `01-introduction.typ`. |
| Foundations and Related Work | Explain active/NBV lineage, Project Aria/ASE/EFM3D, RRI, finite-candidate value learning, geometric/set learning. | Supports RQ1-RQ4. | Current `02-background.typ`, `02-01-related-work.typ`, `02-02-geometric-learning.typ`, lit-review artifact. |
| Problem Formulation | Define target task, state split, action set, reward/return, validity, and leakage boundaries. | RQ1 primarily; prerequisites for RQ2-RQ6. | `03-01-formal-state.typ`, `questions.qmd`, shared equations/glossary. |
| Oracle and Data Generation | Separate data-generation oracle from actor inputs: target sampling/matching, candidate generation, target-RRI labels, invalidity, rollout storage. | RQ1 plus RQ4 support. | `03-02-data-generation.typ`, seminar paper as historical substrate, target-selection autoresearch. |
| Method | Describe scene encoder/backbone, descriptors, candidate-set architecture, and finite-horizon `Q_H`. | RQ2-RQ3. | Current `03-method.typ`, geometric-learning section, lit-review iterations. |
| Experimental Design | Define hypotheses, evidence gates, baselines, ablations, paired policy comparisons, scale reporting, and failure interpretation. | RQ2-RQ5. | Current `04-evaluation.typ`, roadmap/questions. |
| Results | Placeholder now; later report actual target-label audits, scorer metrics, headroom, `Q_H`, ablations, and scale/storage results. | RQ1-RQ5 once evidence exists. | Generated manifests, experiments, KG-backed claims. |
| Discussion | Interpret positive, negative, or partial results; separate support/data/model limitations from future bridges. | RQ4-RQ6. | Current conclusion, future-work notes, roadmap. |
| Conclusion | Conditional final claim and scoped future work. | All RQs. | Current `05-conclusion.typ`. |
| Appendix | Preserve derivations, frame contracts, implementation details, seminar-substrate adaptation, manifest tables, and open-work intake. | Supporting evidence, not primary claim flow. | `appendix/index.typ`, `06-draft-open-work.typ`, seminar sources. |

## Research Question Shape

The current research-question spine is usable, but it should appear in the
thesis body in a compact form rather than being implicit in Quarto:

1. **RQ1 Objective and oracle contract.** Can target-specific RRI be defined,
   labeled, and evaluated without leaking GT assets into actor-visible inputs?
2. **RQ2 Offline finite-candidate planning.** Does bounded oracle lookahead show
   non-myopic target-RRI headroom, and can `Q_H` recover part of it?
3. **RQ3 Representation and architecture.** Which actor-visible target,
   history, candidate, and geometric/set encodings are necessary for calibrated
   candidate values?
4. **RQ4 Support and scale.** Under which target/candidate/rollout support and
   storage conditions do the claims remain valid at ASE scale?
5. **RQ5 Online discrete bridge.** After offline `Q_H`, can the same
   finite-candidate contract support online discrete interaction?
6. **RQ6 Continuous bridge.** After the discrete contract is stable, what does a
   target-then-pose continuous policy require, and what remains future work?

## Content To Prune Or Move

| Content | Recommended home | Reason |
| --- | --- | --- |
| Schedule, risk-control draft, preliminary outline | Appendix open-work file. | Useful provenance, but not final numbered thesis argument. |
| Heavy implementation-flow diagrams and manifest tables | Appendix unless directly supporting a chapter claim. | Keeps main chapters readable and evidence-focused. |
| Seminar CORAL/offline-cache details | Oracle/data-generation appendix plus short main substrate summary. | Historical implemented evidence, not current target-`Q_H` result. |
| Generic Gymnasium/SB3/external simulator planning | Discussion/future work only. | Outside current finite-candidate thesis core. |
| Exact architecture ladder beyond validated controls | Method as hypotheses plus appendix details. | Avoids overclaiming unrun ablations. |

## Prometheus Strict Synthesis

### Metis Clearance

- Objective: produce a researched, implementable thesis-structure plan.
- Scope in: active `main.typ` include graph, chapter/source-file structure,
  section goals, RQ placement, validation and handoff.
- Scope out: immediate Typst refactor, new claims, generated PDFs, and
  irreversible archival moves.
- Acceptance: artifact names exact paths, include status, chapter tree, RQ map,
  and validation commands.
- Test strategy: Typst compile after later execution; pre-execution checks are
  read-only include graph and source-order evidence.
- Handoff target: direct execution or `$ultragoal` if the refactor is bundled
  with section rewrites.

### Momus Objections Resolved

- **Objection:** Splitting files may create churn without scientific benefit.
  **Resolution:** Split only overloaded ownership boundaries first: problem
  formulation, oracle/data generation, method/model, experimental design.
- **Objection:** External university guidance is generic and can conflict with
  ARIA source order. **Resolution:** Use it only for thesis reader flow; local
  roadmap/questions/memory own technical content and RQ order.
- **Objection:** Moving appendix inclusion out of the template could break the
  layout. **Resolution:** Treat it as an execution-time design choice: either
  pass appendix content into the template or add a clearly named template
  parameter, then compile immediately.

### Oracle Plan

1. Refactor the thesis include graph so `main.typ` makes all numbered chapters
   and appendix ownership visible.
2. Introduce chapter index files for large chapters; keep imports local and
   reuse shared macros/glossary/equations.
3. Move current content mechanically first, preserving text and labels; only
   then polish chapter openings and transitions.
4. Add a compact RQ section in the introduction or problem-formulation chapter
   using the current RQ spine.
5. Keep draft/open-work and seminar-detail material in appendix files with
   `dashy-todo` markers.
6. Compile `docs/typst/thesis/main.typ`; inspect the outline/table of contents;
   run hygiene checks and `kg-claim-check` only for newly strengthened claims.

## Validation Matrix For Follow-Up Patch

| Claim | Evidence |
| --- | --- |
| All source files reachable | `rg -n "#include|^=+\\s" docs/typst/thesis/main.typ docs/typst/thesis/sections docs/typst/thesis/appendix/index.typ` plus compiled TOC inspection. |
| Typst source remains valid | `cd docs && typst compile typst/thesis/main.typ --root . /tmp/thesis-structure.pdf`. |
| No hidden appendix ownership | `rg -n "appendix/index|include\\(\"../../appendix" docs/typst/thesis/main.typ docs/typst/thesis/template/layout/thesis_template.typ`. |
| RQ wording follows current truth | Compare against `docs/contents/thesis/questions.qmd` and `docs/contents/thesis/roadmap.qmd`. |
| Scientific claims are not strengthened silently | `make kg-claim-check KG_CLAIM="<new advisor-facing claim>"` for any new claim beyond moved prose. |
| General docs hygiene | `git diff --check`, `make qmd-frontmatter-check`, and `make check-agent-memory` if guidance/memory changes. |

## Recommended Handoff

Use direct execution if the next task is only the include/source-file refactor.
Use `$ultragoal` if the next task also rewrites chapter introductions, RQs,
and transitions from the research artifact.
