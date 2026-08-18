# Comprehensive Peer Review Of The Current ARIA-NBV Thesis

Date: 2026-08-16
Reviewed surface: `docs/typst/thesis/main.typ` and every included file under
`docs/typst/thesis/sections/`
Verdict: **major revision; scientifically promising development draft, not a
submission-ready thesis**

## Executive Verdict

The manuscript already has an unusually strong audit spine. It separates
actor-visible state from oracle supervision, treats invalid actions as hard
constraints, scopes optimality to finite candidate support, refuses to infer
policy quality from fixture data, and exposes missing evidence honestly. These
are real strengths.

The largest problem is that the manuscript currently reads as a combined
requirements document, implementation ledger, design-space registry, and
conditional thesis. It does not yet read as one scientific argument whose
method has been frozen and whose research questions are answered by evidence.
The prose is often technically precise but *ascientific*: repository-local
types, masks, protocols, storage schemas, planned alternatives, and promotion
gates occupy the argumentative foreground. The reader repeatedly learns what
might be implemented, how data are stored, or which branch could be tried, but
not one stable method followed by evidence and interpretation.

The minimum credible target is not “polish the prose.” It is:

1. freeze one method, primary objective, actor-state protocol, and matched
   comparison set;
2. validate the metric and collect a confirmatory held-out evidence bundle;
3. make every research question resolve to an estimand, decision rule, result,
   and bounded answer;
4. move project-management and rejected-design material out of the submission
   render;
5. replace implementation vocabulary with scientific concepts except where an
   exact implementation anchor is needed;
6. make literature and result provenance deterministic at claim level; and
7. rewrite results, discussion, conclusion, and abstract from the frozen
   evidence rather than from the current outcome tree.

## Review Method And Evidence Boundary

This review inspected the active Typst include graph, development render,
submission gates, bibliography projection, available local TeX sources,
Graphify projection and graph, and representative implementation owners. The
development document compiled to 110 pages after the review markers were
added. Representative rendered pages from the introduction, oracle chapter,
method, experiments, results, discussion, and conclusion were inspected. The
typesetting is generally clean and readable; the problems are primarily
scientific structure, evidence, terminology, and submission-mode ownership.

Graphify was used while its freshness state was `structural-stale` but usable.
Its candidate relationships were therefore treated as navigation only and were
verified against exact Typst, bibliography, literature, and code sources. No
scientific claim in this review rests on Graphify output alone.

## Highest-Priority Findings

### P0 — The thesis does not yet have a single scientific method

The Method chapter explicitly says there is no production scorer, checkpoint,
or policy result and simultaneously carries several competing interfaces and
objectives (`docs/typst/thesis/sections/04-method/index.typ:13-15`). The value
model retains fixed-budget, requested-horizon, exact horizon-two, recursive
fitted-value, Double-Q, and behavior-return branches
(`04-method/04-05-finite-candidate-value-model.typ:24-30,76-140`). This is a
useful design record, but a submission Method must describe the method that was
actually evaluated, not a menu of candidate methods.

**Requirement:** freeze the scorer interface, state protocol, horizon
semantics, primary loss, selection rule, baselines, and ablations. Retain only
the requirements and theory exercised by that method. Move rejected branches
to the development diary or compress them into limitations/future work.

### P0 — The core research questions are unanswered

The Results chapter correctly refuses to promote a fixture to evidence
(`06-results.typ:67-79`) and reports only implementation readiness from
training-source attempts (`06-results.typ:99`). The Discussion states that no
held-out paired endpoint table, metric repeatability evidence, or implemented
finite-horizon comparison exists (`07-discussion.typ:16`). The Conclusion then
states that lookahead headroom and learned recovery remain unanswered
(`08-conclusion.typ:13-15`). This is honest, but it means the present document
cannot yet make a scientific contribution claim beyond protocol and
infrastructure design.

**Requirement:** produce a frozen confirmatory bundle with matched endpoint
evaluation, population and exclusion counts, run-level provenance, independent
replicates, uncertainty, failure records, and resource evidence. If headroom is
negligible, report the bounded negative result. If the metric is unstable, the
planning study is blocked and the thesis must center that finding explicitly.

### P0 — Empirical inference is not fully specified

The experimental design has strong conceptual gates, but the submission target
still needs an immutable analysis contract: eligible population, exclusions,
primary estimands, aggregation unit, independent-run definition, uncertainty
interval, minimum meaningful effect, multiplicity handling, model-selection
boundary, and equal-budget comparison rules. Without these, “meaningful
headroom” and “recovery” remain underspecified.

**Requirement:** preregister these choices before inspecting confirmatory
results and preserve the validation-to-test firewall. Every result sentence
must resolve scope, artifact, uncertainty, and immutable run identity.

### P0 — Development and submission content were not consistently separated

Before this review, TODO markers failed submission compilation, but
`thesis_status` editorial boxes were deliberately allowed in submission. That
would have placed implementation/evidence badges and project promotion gates
inside the submitted thesis. Ordinary prose, equations, figures, and includes
also had no explicit default-mode rule. The appendix used a bespoke mode
conditional for the development diary instead of the shared explicit wrapper.

The revised mode contract now states:

- unguarded content is submission-facing;
- `development_only(() => [...])` lazily owns every nested development-only
  object so included files are not evaluated in submission mode;
- `submission_only(() => [...])` is available for rare final-only content;
- both unresolved TODO markers and editorial `thesis_status` blocks fail in
  submission mode; and
- the development diary has one include owner in the appendix and is explicitly
  wrapped with `development_only`
  (`docs/typst/thesis/appendix/index.typ:1-6,108-110`,
  `docs/typst/thesis/draft_markers.typ:12-19,65-78`).

This is the right invariant. Scientific limitations currently held inside
status boxes must be rewritten as ordinary prose before those boxes are
removed.

### P1 — Literature citations lack claim-level provenance

The active Graphify projection contains 99 citation occurrences using 45
unique bibliography keys. Only 12 of those keys currently resolve through the
projection to a `docs/literature/sources.jsonl` literature record; 33 do not.
Only a few visible status blocks mention exact local TeX locators, and those
locators are editorial content rather than a deterministic authoring ledger.

A single file-wide provenance block would be too remote from the claims it is
supposed to support. A rendered Typst macro would create mode leakage and a
second source of truth. The recommended canonical form is one non-rendered
comment block per claim-bearing paragraph, figure, table, or equation:

```typst
// evidence:
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:82-92 (RRI definition)
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:122-129 (oracle labels and ordinal target)
```

The BibTeX key remains the identity; the locator records which primary-source
passage was checked for the local claim. Use an exact TeX line range when
available, otherwise PDF page/section/figure/table. Missing local source
material must remain an explicit provenance gap. A development macro may later
render the parsed ledger, but only as a derived view.

Two verified examples show the value of exact locators:

- VIN-NBV defines RRI at
  `docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:82-92` and describes
  ground-truth rendering/oracle labels and ordinal training at lines 122-129.
- EFM3D describes its gravity-aligned lifted field and heads at
  `docs/literature/tex-src/arXiv-EFM3D/method.tex:4-40`, the OBB head at 58-64,
  occupancy supervision at 75-83, and the 4 m local grid at line 104.

The convention is now owned by
`.agents/skills/typst-authoring/references/claim-citation-discipline.md`.

#### Active citation-provenance ledger

The source column gives the first active thesis occurrence and the total source
occurrence count. `manifest-unmatched` means the BibTeX entry does not have a
deterministic join through `docs/literature/sources.jsonl`; a similarly named
local asset is recorded only as a candidate until its identity and supporting
passage are verified. `claim-level locator pending` means the manifest identity
is joined but the exact passage for every thesis claim has not yet been audited.

| Key | First thesis source | Bibliography owner | Available local locator | Audit status |
| --- | --- | --- | --- | --- |
| `ActivePerception-bajcsy1988` | `docs/typst/thesis/sections/01-introduction.typ:6` (2 occurrences) | `docs/references.bib:816` | `none` | manifest-unmatched; no deterministic local locator |
| `ActiveVision-aloimonos1988` | `docs/typst/thesis/sections/01-introduction.typ:6` (2 occurrences) | `docs/references.bib:828` | `none` | manifest-unmatched; no deterministic local locator |
| `BCQ-fujimoto2019` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:26` (3 occurrences) | `docs/references.bib:685` | `docs/literature/tex-src/arXiv-BCQ` | manifest-unmatched; local asset candidate needs identity and claim verification |
| `CORAL-cao2019` | `docs/typst/thesis/sections/04-method/04-05-finite-candidate-value-model.typ:19` (2 occurrences) | `docs/references.bib:318` | `none` | manifest-unmatched; no deterministic local locator |
| `CQL-kumar2020` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:26` (3 occurrences) | `docs/references.bib:675` | `docs/literature/tex-src/arXiv-CQL` | manifest-unmatched; local asset candidate needs identity and claim verification |
| `CurriculumLearning-bengio2009` | `docs/typst/thesis/sections/02-foundations/02-02-geometric-learning.typ:75` (1 occurrence) | `docs/references.bib:576` | `none` | manifest-unmatched; no deterministic local locator |
| `DeepGamblers-liu2019` | `docs/typst/thesis/sections/02-foundations/02-02-geometric-learning.typ:68` (2 occurrences) | `docs/references.bib:596` | `none` | manifest-unmatched; no deterministic local locator |
| `DeepSets-zaheer2017` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:28` (6 occurrences) | `docs/references.bib:348` | `docs/literature/tex-src/arXiv-Deep-Sets` | manifest-unmatched; local asset candidate needs identity and claim verification |
| `DoubleDQN-vanHasselt2015` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:26` (5 occurrences) | `docs/references.bib:643` | `docs/literature/tex-src/arXiv-Double-DQN` | manifest-matched; claim-level locator pending |
| `e3nn-SphericalHarmonics-2025` | `docs/typst/thesis/sections/02-foundations/02-02-geometric-learning.typ:33` (2 occurrences) | `docs/references.bib:292` | `none` | manifest-matched; no local TeX/PDF locator; claim verification pending |
| `EFM3D-straub2024` | `docs/typst/thesis/sections/01-introduction.typ:8` (14 occurrences) | `docs/references.bib:165` | `docs/literature/tex-src/arXiv-EFM3D/method.tex:4-40,58-64,75-83,104` | manifest-matched; representative claims verified |
| `EGNN-satorras2021` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:30` (2 occurrences) | `docs/references.bib:92` | `docs/literature/tex-src/arXiv-EGNN` | manifest-matched; claim-level locator pending |
| `EVL-Doc-2025` | `docs/typst/thesis/sections/02-foundations/index.typ:3` (2 occurrences) | `docs/references.bib:258` | `none` | manifest-unmatched; no deterministic local locator |
| `FisherRF-jiang2024` | `docs/typst/thesis/sections/02-foundations/02-02-geometric-learning.typ:33` (1 occurrence) | `docs/references.bib:929` | `docs/literature/tex-src/arXiv-FisherRF` | manifest-matched; claim-level locator pending |
| `FittedQIteration-ernst2005` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:26` (5 occurrences) | `docs/references-qh.bib:1` | `none` | manifest-unmatched; no deterministic local locator |
| `FixedHorizonTD-deAsis2020` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:26` (9 occurrences) | `docs/references-qh.bib:11` | `none` | manifest-unmatched; no deterministic local locator |
| `GATr-brehmer2023` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:30` (2 occurrences) | `docs/references.bib:84` | `none` | manifest-unmatched; no deterministic local locator |
| `GenNBV-chen2024` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:32` (3 occurrences) | `docs/references.bib:1` | `docs/literature/tex-src/arXiv-GenNBV` | manifest-unmatched; local asset candidate needs identity and claim verification |
| `GeometricDeepLearning-bronstein2021` | `docs/typst/thesis/sections/02-foundations/02-02-geometric-learning.typ:15` (5 occurrences) | `docs/references.bib:74` | `docs/literature/tex-src/arXiv-Geometric-Deep-Learning` | manifest-matched; claim-level locator pending |
| `Hestia-lu2026` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:32` (3 occurrences) | `docs/references.bib:30` | `docs/literature/tex-src/arXiv-Hestia` | manifest-unmatched; local asset candidate needs identity and claim verification |
| `KPConv-thomas2019` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:30` (1 occurrence) | `docs/references.bib:157` | `docs/literature/tex-src/arXiv-KPConv` | manifest-matched; claim-level locator pending |
| `LFF-li2021` | `docs/typst/thesis/sections/04-method/04-02-descriptor-and-encoding-plan.typ:100` (1 occurrence) | `docs/references.bib:308` | `none` | manifest-unmatched; no deterministic local locator |
| `MinkowskiEngine-choy2019` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:30` (1 occurrence) | `docs/references.bib:141` | `docs/literature/tex-src/arXiv-MinkowskiEngine` | manifest-unmatched; local asset candidate needs identity and claim verification |
| `OANBV-hu2026` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:22` (1 occurrence) | `docs/references.bib:38` | `none` | manifest-unmatched; no deterministic local locator |
| `ObjectCentricNBV-jeong2026` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:22` (3 occurrences) | `docs/references.bib:797` | `docs/literature/tex-src/arXiv-Instance-NBV` | manifest-matched; claim-level locator pending |
| `ObjViewBench-pan2026` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:22` (1 occurrence) | `docs/references.bib:48` | `none` | manifest-unmatched; no deterministic local locator |
| `PB-NBV-jia2025` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:20` (1 occurrence) | `docs/references.bib:886` | `docs/literature/tex-src/arXiv-PB-NBV` | manifest-unmatched; local asset candidate needs identity and claim verification |
| `PointNeXt-qian2022` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:30` (1 occurrence) | `docs/references.bib:508` | `none` | manifest-unmatched; no deterministic local locator |
| `PointTransformerV3-wu2024` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:30` (1 occurrence) | `docs/references.bib:149` | `docs/literature/tex-src/arXiv-Point-Transformer-V3` | manifest-unmatched; local asset candidate needs identity and claim verification |
| `PowerSpherical-deCao2020` | `docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ:66` (1 occurrence) | `docs/references.bib:399` | `none` | manifest-unmatched; no deterministic local locator |
| `ProjectAria-ASE-2025` | `docs/typst/thesis/sections/01-introduction.typ:8` (7 occurrences) | `docs/references.bib:250` | `none` | manifest-unmatched; no deterministic local locator |
| `projectaria-engel2023` | `docs/typst/thesis/sections/01-introduction.typ:8` (2 occurrences) | `docs/references.bib:410` | `docs/literature/tex-src/arXiv-project-aria` | manifest-matched; claim-level locator pending |
| `PyTorch3D-Cameras-2025` | `docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ:31` (1 occurrence) | `docs/references.bib:284` | `none` | manifest-unmatched; no deterministic local locator |
| `RecedingHorizonNBV-bircher2016` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:18` (1 occurrence) | `docs/references.bib:864` | `none` | manifest-unmatched; no deterministic local locator |
| `SceneScript-avetisyan2024` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:32` (2 occurrences) | `docs/references.bib:20` | `docs/literature/tex-src/arXiv-scene-script` | manifest-matched; claim-level locator pending |
| `SCONE-guedon2022` | `docs/typst/thesis/sections/02-foundations/02-02-geometric-learning.typ:33` (1 occurrence) | `docs/references.bib:58` | `docs/literature/tex-src/arXiv-SCONE` | manifest-unmatched; local asset candidate needs identity and claim verification |
| `SE3Transformer-fuchs2020` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:30` (2 occurrences) | `docs/references.bib:104` | `docs/literature/tex-src/arXiv-SE3-Transformer` | manifest-unmatched; local asset candidate needs identity and claim verification |
| `SelectiveNet-geifman2019` | `docs/typst/thesis/sections/02-foundations/02-02-geometric-learning.typ:68` (1 occurrence) | `docs/references.bib:584` | `none` | manifest-unmatched; no deterministic local locator |
| `SetTransformer-lee2019` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:28` (5 occurrences) | `docs/references.bib:357` | `docs/literature/tex-src/arXiv-Set-Transformer` | manifest-matched; claim-level locator pending |
| `SubmodularNBV-lauri2020` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:18` (1 occurrence) | `docs/references.bib:759` | `none` | manifest-unmatched; no deterministic local locator |
| `UVFA-schaul2015` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:26` (6 occurrences) | `docs/references-qh.bib:23` | `none` | manifest-unmatched; no deterministic local locator |
| `ViewPlanningSurvey-scott2003` | `docs/typst/thesis/sections/01-introduction.typ:6` (2 occurrences) | `docs/references.bib:840` | `none` | manifest-unmatched; no deterministic local locator |
| `VIN-NBV-frahm2025` | `docs/typst/thesis/sections/01-introduction.typ:8` (7 occurrences) | `docs/references.bib:10` | `docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:82-92,122-129` | manifest-matched; representative claims verified |
| `zhou2019continuity` | `docs/typst/thesis/sections/02-foundations/02-02-geometric-learning.typ:31` (2 occurrences) | `docs/references.bib:493` | `none` | manifest-unmatched; no deterministic local locator |
| `zhou2023query` | `docs/typst/thesis/sections/02-foundations/02-01-related-work.typ:30` (7 occurrences) | `docs/references.bib:616` | `docs/literature/pdf/Zhou_Query-Centric_Trajectory_Prediction_CVPR_2023_paper.pdf` | manifest-unmatched; local asset candidate needs identity and claim verification |

### P1 — Implementation terminology dominates the scientific narrative

Examples include `QhActorTensors`, `CandidateSupervision`, `q_train_mask`,
`CF-GT`, `CF-sensor`, `V0`, `V1`, `S0-pose`, store group names, and exact DTO
or directory vocabulary. These identifiers are useful audit anchors, but they
are not scientific concepts unless defined, motivated, and necessary to
reproduce the experiment. The existing comments in
`04-method/04-01-scene-representation-requirements.typ:23-28,56` already flag
the same problem.

**Requirement:** lead with information roles: actor observation, privileged
supervision, selected-observation update, hard action validity, and endpoint
evaluation. Put implementation identifiers in a reproducibility appendix or a
single pinned code anchor. If a short term survives, define it in the glossary
or shared symbols and use it consistently.

### P1 — The common narrative thread is present but repeatedly interrupted

The strongest through-line is:

> target-specific metric validity → finite-support oracle headroom → learned
> recovery under actor-visible inputs → support and scale limits.

That thread appears in the Introduction and Experimental Design, but the middle
of the thesis repeatedly detours into architecture surveys, state-carrier
ladders, schema details, and future bridges. The result is a reader journey
from problem to design registry rather than from question to controlled
evidence.

**Requirement:** make every chapter advance one link in the chain. A paragraph
that cannot be assigned to a research question, required methodological
assumption, result, limitation, or transition should be moved or deleted.

### P1 — Related work is too catalogue-like

The first half of Related Work has good comparison logic. Its architecture and
scene-memory paragraphs become lists of models and representation families
(`02-foundations/02-01-related-work.typ:30-32`). They say many things are
possible but do not narrow the evaluated method.

**Requirement:** organize around decisions the thesis actually makes. For each
retained source, state its contribution, incompatible assumption or unresolved
gap, and the concrete control/design consequence for ARIA-NBV. Remove sources
whose only role is membership in an architecture catalogue.

### P1 — Results, Discussion, and Conclusion are development artifacts

The current Results is an evidence-availability report; Discussion is an
implementation-readiness assessment plus conditional architecture registry;
Conclusion is an outcome tree. All three are valuable during development and
appropriately cautious, but none yet performs its final scientific section
job.

**Requirement:** Results reports measurements without mechanism speculation;
Discussion interprets those measurements and alternatives; Conclusion answers
RQ1-RQ4 directly and briefly. Do not convert missing evidence into polished
negative prose.

### P2 — Prose density and sentence function need a final scientific pass

The render is visually clean, but several pages contain long, clause-heavy
paragraphs with multiple contracts, exceptions, and caveats. The writing is
usually grammatical; its scientific weakness is that one sentence often mixes
definition, implementation fact, design decision, limitation, and future work.

**Requirement:** give each paragraph one scientific job and each sentence a
classifiable role. Prefer claim → evidence → interpretation → scope. Replace
abstract nouns such as “substrate,” “seam,” “carrier,” “bridge,” and “gate” when
the concrete data, method, comparison, or condition can be named directly.

## Section-By-Section Review

| File | Current role and strength | Required target state |
| --- | --- | --- |
| `01-introduction.typ` | Clear bounded task, actor/oracle distinction, and four research questions. Contributions are still prospective. | End with one contribution per RQ, each linked to an estimand and final result; shorten infrastructure exposition. |
| `02-foundations/index.typ` | Concise dependency map. | Retain after child sections are narrowed; add claim-level locators for ASE/EFM3D statements. |
| `02-01-related-work.typ` | Good local contrasts early; later architecture and memory catalogues are over-broad. | Synthesize only literature that determines the final method, baselines, or interpretation. |
| `02-02-geometric-learning.typ` | Strong permutation/mask/frame requirements; mixes final theory with planned feasibility heads and representation ladders. | Keep only invariants tested by the production scorer; move speculative curricula and ladders to development/future work. |
| `03-oracle-and-data-generation/index.typ` | Strong explicit non-deployable oracle scope. | Retain as the chapter contract; ensure every child obeys the same vocabulary. |
| `03-01-state-and-visibility.typ` | Scientifically important information boundary; too many internal protocol names and tensor details. | Explain observability and causality first; relegate DTO/protocol identifiers to audit anchors. |
| `03-02-target-task-and-rri-labels.typ` | Detailed metric construction and a valuable tessellation-sensitivity fixture. | Validate repeatability and sampling sensitivity; distinguish inherited VIN definition from target-specific modifications with exact source locators. |
| `03-03-replay-stores-and-diagnostics.typ` | Good lineage, missingness, and immutability logic. | Keep reproducibility/leakage guarantees; move schemas, joins, directories, and codec-level detail to an appendix. |
| `04-method/index.typ` | Honest implementation status, but announces multiple unresolved methods. | Describe one frozen evaluated method and its justified controls. |
| `04-01-scene-representation-requirements.typ` | Rich state-design inventory; existing inline comments correctly identify terminology and abstraction problems. | Select one state protocol; remove or move untested carriers and internal labels. Preserve the user's existing comments until resolved. |
| `04-02-descriptor-and-encoding-plan.typ` | Good actor/supervision DTO separation; production descriptor remains planned. | Replace plan with the actual descriptor, dimensions, frames, missingness, normalization, and ablation rationale. |
| `04-03-candidate-and-replay-contract.typ` | Hard masks and replay transition ownership are precise. | Retain scientific action/transition semantics; reduce field-level vocabulary and clearly state whether the final state is Markov enough for the claim. |
| `04-04-architecture-contract.typ` | Useful acceptance tests; architecture is not implemented. | Report the implemented architecture and test outcomes; move alternative query/key arrangements out of Method. |
| `04-05-finite-candidate-value-model.typ` | Strong mathematical inventory and support caveats; too many objective/horizon alternatives. | Freeze one value definition and training procedure, then report only prespecified ablations. |
| `05-experimental-design/index.typ` | Excellent distinction between feasibility and policy evidence. | Retain, then make it operational through an immutable analysis manifest. |
| `05-01-objectives-and-hypotheses.typ` | Good headroom/recovery gate and held-out intent. | Specify population, estimands, aggregation, uncertainty, meaningful-effect rule, exclusions, and multiplicity. |
| `05-02-learning-objective-and-replay-evidence.typ` | Detailed, leakage-aware objective construction; heavy on field names and alternative backups. | Align exactly with the frozen method and move join/mask mechanics to implementation appendix unless inference depends on them. |
| `05-03-policy-comparison-and-failure-interpretation.typ` | Strong matched-policy and failure-classification intent. | Turn planned rows into actual methods, budgets, run counts, exclusions, and decision rules before result inspection. |
| `06-draft-open-work.typ` | Useful development diary with one appendix-owned, development-only include. | Keep explicitly development-only; promote only evidence-backed content to canonical sections. |
| `06-results.typ` | Robust schema/missingness gate and honest fixture handling. | Populate with confirmatory evidence and rewrite prose around RQ estimands, effect sizes, uncertainty, denominators, and artifacts. |
| `07-discussion.typ` | Honest limitation analysis; architecture bridges are speculative. | Rebuild from measured findings, alternative explanations, threats, and generalization limits. |
| `08-conclusion.typ` | Accurate statement of current non-result. | Answer each RQ directly after evidence exists; remove the conditional outcome tree from submission prose. |

## Mode Ownership Matrix

| Content | Default owner | Development-only treatment | Submission requirement |
| --- | --- | --- | --- |
| Headings and prose | submission | wrap the entire draft block | final scientific prose only |
| Equations | submission | wrap equation and explanatory text together | used by frozen method/result |
| Figures/tables/captions | submission | wrap the complete figure/table | evidence-backed, self-contained, traceable |
| TODO markers | development | marker macro | compile failure until resolved |
| `thesis_status` boxes | development | status macro | compile failure; rewrite substance as prose |
| Design registries/diary | development | lazy `development_only(() => [...])` include | excluded |
| Result data | mode-specific input | fixture/pilot allowed and labelled | explicit confirmatory evidence bundle |
| Scientific limitations | submission | may be drafted in a marker temporarily | ordinary bounded prose, never an editorial badge |

This matrix should be treated as a static audit contract. A future linter should
check that development-only includes use `development_only` and that no raw
project-management headings or unclassified status constructs bypass the
submission gate.

## Graphify Review

### What worked

The projection already provides deterministic pages for thesis files,
bibliography keys, literature manifest records, TeX roots, and selected code
anchors. It is useful for discovering candidate owners and for measuring
coverage gaps. The graph contains 6,143 nodes and 13,960 links in the reviewed
snapshot.

### What failed for research writing

The semantic graph did not preserve the most useful deterministic relationships:

- `Thesis Main` had only one inferred relation, to `Foundations`;
- no path was found from `Thesis Main` to `IQL TeX Root`;
- no path was found from `Foundations` to the VIN-NBV citation node; and
- no useful path was found from the thesis to `QhDataset` code nodes.

This is not evidence that the connections do not exist. Exact inspection showed
that generated Markdown already contains section-to-citation and, when the
manifest join exists, citation-to-literature-to-TeX-root links. The failure is
that Graphify's semantic extraction does not reliably materialize those
deterministic links as graph edges. File-level thesis nodes also lose the
paragraph/claim granularity needed for writing.

### Minimal improvements, in order

1. **Preserve deterministic typed edges.** Add a projection sidecar or supported
   relation syntax that imports the existing Markdown links as explicit edges
   before semantic inference. Do not ask the LLM extractor to rediscover them.
2. **Parse evidence comments.** Parse the new `// evidence:` grammar into
   `claim -> bibliography key -> source locator` edges.
3. **Add stable paragraph nodes.** Split thesis projection pages by heading and
   claim-bearing paragraph with source path and line range. Keep the file node
   as parent.
4. **Resolve implementation anchors structurally.** Continue parsing `#gh`,
   `#gh-wip`, and `#gh-symbol`, but also emit paragraph-to-code edges and parse
   validated development-source fields as non-authoritative navigation.
5. **Add bounded path tests.** Assert that representative paths exist:
   `section -> claim -> citation -> literature -> TeX locator` and
   `section -> implementation fact -> code symbol/test`.
6. **Measure coverage.** Report unresolved citation keys, locators without
   source files, code anchors without symbols, and paragraph nodes without
   evidence. Fail only explicit graph/projection checks; normal thesis work must
   still function without Graphify.

These are deliberately projection-layer improvements. Graphify remains a
freshness-gated derived navigator, never the owner of a scientific claim,
bibliography identity, code behavior, or thesis text.

## Authoring Invariants Added Or Recommended

The external best-practice review used current official or primary guidance
from the NeurIPS paper checklist, ICML reviewer and ethics guidance, MLSys
artifact evaluation guidance, ETH computer-science thesis guidance, and
reproducible-computational-research literature. The useful repository-local
invariants are:

1. claim strength and scope must match the available protocol and evidence;
2. every empirical sentence resolves scope, artifact, uncertainty, and run
   identity, otherwise it is a hypothesis, pilot observation, or limitation;
3. the experiment contract freezes data/split/preprocessing, method and
   selection choices, metrics, aggregation, uncertainty, and exclusions;
4. validation controls model/analysis selection and held-out evidence controls
   confirmatory inference;
5. comparisons use equal information, candidate/acquisition budgets, evaluation
   and comparable tuning effort, with compute differences disclosed;
6. negative results, failed runs, resource gates, and exclusions are reported
   under the same provenance discipline as positive results;
7. figures and tables are self-contained and traceable to immutable inputs and
   a generation command;
8. venue and institutional rules are dynamic external constraints, not fixed
   scientific owners; and
9. prose preserves the reader chain from question through method, evidence,
   uncertainty, interpretation, and limitation.

These are now captured in the compact `typst-authoring` router and the new
`references/empirical-reporting-and-reproducibility.md`, while detailed rules
remain outside the hot-path skill file.

Primary references consulted:

- NeurIPS Paper Checklist: <https://neurips.cc/public/guides/PaperChecklist>
- ICML 2026 Reviewer Instructions: <https://icml.cc/Conferences/2026/ReviewerInstructions>
- ICML 2026 Research Ethics: <https://icml.cc/Conferences/2026/ResearchEthics>
- MLSys 2026 Artifact Evaluation: <https://mlsys.org/Conferences/2026/CallForAEs>
- ETH Zurich CS MSc thesis memo: <https://ethz.ch/content/dam/ethz/special-interest/infk/department/Images%20and%20Content/Studies/Forms%20and%20Documents/Memo_MSc_Thesis_2025_2.pdf>
- Ten Simple Rules for Reproducible Computational Research: <https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1003285>

## Concrete Review Markers Added

Targeted Dashy-derived markers now identify the actionable issues in context:

- RQ-to-evidence alignment in the Introduction;
- catalogue pruning and claim-level citation provenance in Related Work;
- speculative-theory pruning in Geometric Learning;
- terminology and source provenance in the actor/oracle chapter;
- RRI validation and inherited-definition provenance;
- implementation-detail pruning in replay stores;
- one-method freeze across the Method chapter;
- architecture acceptance evidence and horizon/objective selection;
- preregistered inference requirements in Experimental Design;
- confirmatory provenance and uncertainty in Results;
- evidence-led rewrites of Discussion and Conclusion.

The existing user comments in
`04-method/04-01-scene-representation-requirements.typ` were preserved. No
attempt was made to silently resolve them by terminology substitution before
the method is frozen.

## Recommended Revision Sequence

1. Freeze the scientific contract: RQs, target protocol, metric, population,
   finite support, horizon, primary method, controls, estimands, and decision
   rules.
2. Complete metric validity and oracle-headroom pilots without using held-out
   policy evidence for design selection.
3. Implement and acceptance-test one actor-visible scorer; move unused design
   branches to the development diary.
4. Freeze the confirmatory manifest and run matched comparisons with resource
   and failure provenance.
5. Generate immutable tables/figures and fill the claim/source locator ledger.
6. Rewrite Results, then Discussion and Conclusion, then Introduction and
   Abstract.
7. Remove every submission-blocking marker/status box and run both render modes,
   hygiene, citation/source coverage, and visual QA.

## Acceptance Criteria For A Good Target State

The thesis is ready for submission review only when:

- one implemented method is described consistently across foundations, method,
  experiments, and results;
- every RQ has an explicit estimand, decision rule, result, uncertainty, and
  bounded answer;
- every literature claim has a verified bibliography key and claim-level
  primary-source locator or an explicit provenance gap;
- every empirical result traces to an immutable bundle, run manifest, raw and
  derived artifacts, code revision, command, and environment;
- all baselines share the declared support, budgets, information, evaluation,
  and fair selection protocol;
- submission mode contains no TODO, status box, development diary, design
  registry, fixture result, or unresolved implementation choice;
- internal identifiers appear only when scientifically necessary or as compact
  implementation anchors;
- Results, Discussion, Conclusion, Introduction, and Abstract agree on the same
  evidence-calibrated claims; and
- development and submission builds, rendered-page inspection, citation/source
  audit, hygiene checks, and repository checks are fresh and green, with any
  remaining gap reported explicitly.

## Verification Record

Fresh verification after the edits:

- Development compile passed:
  `typst compile docs/typst/thesis/main.typ /tmp/aria-thesis-development-final.pdf --root docs --input aria-thesis-mode=development`.
  The result has 110 PDF pages, including one appendix-owned development diary.
  `pdftotext -layout` found `B Development Diary` in the contents and at PDF
  page 107 and found no main-chapter `6 Development Diary` duplicate.
- Representative marker, diary, result, discussion, conclusion, and corrected
  equation pages were rendered to PNG and inspected. No clipping, overflow, or
  attachment error was observed.
- Submission without an explicit evidence bundle stopped at
  `experiment_data.typ:45` with the intended publication-data assertion.
- Submission with a temporary test-only bundle carrying evidence role and
  confirmatory status proceeded past that gate and stopped at
  `01-introduction.typ:28` with the intended unresolved-marker panic. The
  temporary fixture was removed.
- Strict thesis hygiene passed after correcting the pre-existing
  `CrossAttn`/`Emb` math-attachment spacing. Two shared-notation findings remain
  advisory and are not new blocking errors.
- Typst skill example hygiene completed; reported anti-patterns are intentional
  bad examples. The system `quick_validate.py` reported `Skill is valid!`.
- `GIT_DIR=/home/jd/repos/ARIA-NBV/.git GIT_WORK_TREE=/home/jd/repos/ARIA-NBV make check-agent-memory`
  passed. The same environment-scoped form of `make scaffold-audit` reported
  zero errors and 13 existing cross-scaffold warnings; the changed Typst skill
  is below the 150-line hot-path budget.
- `env -u GIT_WORK_TREE -u GIT_DIR make scaffold-audit-self-test` passed 21
  checks plus 8 G002 governance tests. Unsetting the variables is required
  because this self-test creates temporary Git repositories.
- `env -u GIT_WORK_TREE -u GIT_DIR make graphify-projection-self-test` passed all
  42 tests for the same reason.
- With `aria_ref` resolved through `git --git-dir=/home/jd/repos/ARIA-NBV/.git
  rev-parse HEAD`, `GIT_DIR=/home/jd/repos/ARIA-NBV/.git
  GIT_WORK_TREE=/home/jd/repos/ARIA-NBV python3
  scripts/build_graphify_projection.py --check --aria-code-ref "$aria_ref"`
  validated 288 Markdown files.
- `GIT_DIR=/home/jd/repos/ARIA-NBV/.git
  GIT_WORK_TREE=/home/jd/repos/ARIA-NBV python3
  scripts/check_graphify_freshness.py --json` returned the expected nonzero
  stale verdict: `state=structural-stale`, `usable=true`, with exact dirty owner
  paths. It was not reported as a green freshness check.
- `git --git-dir=/home/jd/repos/ARIA-NBV/.git
  --work-tree=/home/jd/repos/ARIA-NBV diff --check` passed.

The stored semantic Graphify graph remains a derived, structurally stale
snapshot; it was intentionally not refreshed or treated as authority. All
Graphify-derived leads in this report were checked against exact local owners.
