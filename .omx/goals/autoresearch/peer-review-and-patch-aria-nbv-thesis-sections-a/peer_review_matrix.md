# ARIA-NBV Thesis Peer-Review Matrix

Date: 2026-06-18

Scope: current `docs/typst/thesis/main.typ` include graph and included thesis sections, compared against the seminar paper, local theory docs, `.omx/specs/autoresearch-thesis-lit-review`, local literature TeX sources, litkg/source-order guidance, and targeted Semantic Scholar metadata search.

## Ranked Inclusion Decisions

| Rank | Item | Sources Checked | Thesis Placement | Decision | Patch / Marker |
|---:|---|---|---|---|---|
| 1 | Candidate-set geometric theory | `.omx/specs/autoresearch-thesis-lit-review/report.md`, `docs/contents/theory/candidate_view_dependence.qmd`, Deep Sets, Set Transformer, QCNet, GDL local TeX | `docs/typst/thesis/sections/02-02-geometric-learning.typ` | Include as dedicated theory section | Added architecture ladder and `#validation_todo` for row-shuffle/mask/frame tests |
| 2 | Seminar oracle labeler substrate | `docs/typst/seminar_paper/main.typ`, `sections/05-oracle-rri.typ`, `sections/12h-appendix-offline-cache.typ` | `docs/typst/thesis/sections/03-02-data-generation.typ` | Include compactly as label provenance, not as current target-Q_H evidence | Added seminar-substrate table and `#conflict_todo` |
| 3 | Target-specific RRI crop/invalidity | `docs/contents/theory/rri_theory.qmd`, target-selection artifacts, current data-generation section | `03-02-data-generation.typ` | Include in main method | Added empty/unsupported crop invalidity wording |
| 4 | Candidate sampling drift | seminar shell sampler vs current target-conditioned mixture docs/code review | `docs/typst/thesis/sections/03-method.typ` | Repair wording | Reworded default mixture and demoted radial free-shell sampler to historical/stress ablation |
| 5 | All-candidate scoring vs selected transition storage | seminar labeler, current rollout-store contract | `03-method.typ` | Repair wording | Clarified all valid candidates may be oracle-rendered for labels; selected/parent depth is actor-history state |
| 6 | CORAL/VINv3 seminar model | seminar `sections/07-training-objective.typ`, current method | `03-method.typ`, `04-evaluation.typ` | Include as myopic control/scorer substrate | Added caveat that seminar VINv3 is not already target-conditioned finite-horizon Q_H |
| 7 | Evaluation scale and historical subset counts | seminar dataset/evaluation sections, source-order contract | `04-evaluation.typ` | Keep planned scale but mark validation | Added manifest-statistics `#validation_todo` |
| 8 | Draft/open-work placement | thesis include graph, appendix template | `main.typ`, `appendix/index.typ` | Move out of numbered body | Removed `06-draft-open-work.typ` from main body and included it under appendix |
| 9 | Related-work citation clusters | thesis related work, local literature TeX | `02-01-related-work.typ` | Tighten claims and citations | Split offline RL/sequence-branching paragraph and linked to theory section |
| 10 | Raw appendix TODO | thesis appendix | `appendix/index.typ` | Replace with dashy marker | Added `#impl_todo` and appendix inclusion note |

## Conflict And Sharpening Matrix

| Finding | Conflicting / Weak Sources | Correct Owner | Resolution |
|---|---|---|---|
| Seminar scene-level RRI can be mistaken for current target-RRI evidence | Seminar paper is historical implemented evidence; current thesis data-generation owns target crops and target-task sampler | Active thesis method and data-generation section | Added conflict marker and table in `03-02-data-generation.typ` |
| Legacy free-shell candidate sampler can be mistaken for current default | Seminar sampler vs current target-conditioned mixture contract | Current candidate/replay method | Reworded method so free-shell is ablation/stress evidence |
| VINv3 one-step scorer can be overclaimed as Q_H | Seminar architecture and CORAL training are myopic one-step evidence | Finite-candidate value-model method and evaluation | Added explicit "control architecture/substrate" caveat |
| Full-scale dataset counts are not current generated evidence yet | Seminar subset counts are drift-prone and historical | Evaluation manifests / generated stats | Added validation TODO for current manifest-backed counts |
| Bridge literature can dilute thesis direction | GenNBV, Hestia, 3DGS, Deja View, point backbones are useful but not core | Related work and future/ablation sections | Kept them as boundary/ablation/bridge claims |
| Geometric modules can be credited without invariance tests | Literature motivates structures but does not prove ARIA-NBV gains | Dedicated theory plus method acceptance tests | Added theory section and acceptance-test TODOs |

## Citation And Literature Decisions

| Literature Family | Local / External Evidence | Use In Thesis | Status |
|---|---|---|---|
| VIN-NBV | Local TeX and `@VIN-NBV-frahm2025` | RRI and oracle-quality ranking precedent | Core citation, used close to RRI claims |
| EFM3D / Project Aria / ASE | Local EFM3D TeX, ASE docs, current refs | Actor-visible substrate, OBB/EVL anchor | Core citation, no backbone replacement claim |
| Deep Sets / Set Transformer | Local TeX and current refs | Candidate-row set controls and masked interaction | Core architecture lineage |
| QCNet / QCNeXt-style ideas | Local QCNet TeX and Semantic Scholar search | Relative local encoding motif only | Adapt, no forecasting decoder transfer claim |
| EGNN / SE(3)-Transformer / e3nn | Local TeX and current refs | Exact-equivariant ablation and directional memory vocabulary | Defer or ablate after simpler controls |
| SCONE / FisherRF / 3DGS NBV | Current refs and local TeX | Support, overlap, uncertainty, directional diagnostics | Diagnostic features, not reward replacement |
| Deja View | Local TeX and current ref | Weight-tied refinement ablation | Defer until fixed-depth baselines pass |
| ADT / ImVoxelNet / 3DETR / PointNet++ / GauSS-MI / VISTA / POp-GS / EgoLifter | Semantic Scholar metadata and local archive refs | Potential future bibliography additions for egocentric substrate, OBB baselines, point support, active 3DGS bridges | Not added to main text in this patch because active claims are already grounded by existing refs |

## Verification Evidence

- `cd docs && typst compile typst/thesis/main.typ --root . /tmp/thesis-peer-review.pdf`
- `git diff --check`
- `make qmd-frontmatter-check`
- `make check-agent-memory`
- `rg -n "TODO: Add supplementary|#include \"sections/06-draft|gamma = 0\\.1|vin_offline\\.counterfactuals|online RL.*stretch|highest-level project ground truth" docs/typst/thesis .omx/goals/autoresearch/peer-review-and-patch-aria-nbv-thesis-sections-a/peer_review_matrix.md`
- `make kg-claim-check KG_CLAIM="The seminar oracle RRI substrate is implemented evidence for one-step scene-level labels and not evidence that the target-conditioned finite-horizon Q_H model is already implemented."`

All passed. The stale-claim scan had no matches, and the KG claim check returned `supported (confidence=1.0)`.
