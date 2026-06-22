# Arch-Goal Thesis Peer-Review Completion Audit

Date: 2026-06-18

Active Codex goal: `$autoresearch-goal` arch-goal with at least ten useful
iterations, section-by-section thesis peer review, comparison against seminar
paper / litkg / theory docs / external literature, ranked inclusion candidates,
a conflict-citation-inclusion matrix, exact patch and dashy-marker map, followed
by implementation under `docs/typst/thesis`.

## Goal Checklist

| Requirement | Evidence | Verdict |
|---|---|---|
| Use an OMX autoresearch-goal mission for the arch-goal. | `.omx/goals/autoresearch/arch-goal-thesis-peer-review-with-at-least-ten-a/mission.json` and this audit. | Satisfied |
| At least ten useful iterations. | `.omx/specs/autoresearch-thesis-lit-review/report.md` contains Iterations 2-33; `.omx/specs/autoresearch-thesis-lit-review/result.json` records architect approval through Iteration 33. The ten most patch-relevant iterations are mapped below. | Satisfied |
| Peer-review every active thesis section and total coherence. | Current include graph in `docs/typst/thesis/main.typ:51-55`; detailed section log in `.omx/goals/autoresearch/arch-goal-thesis-peer-review-with-at-least-ten-a/section_peer_review_log.md`; draft/open-work moved to appendix via `docs/typst/thesis/appendix/index.typ:9`. | Satisfied |
| Compare against seminar paper, litkg, theory docs, and literature. | `.omx/goals/autoresearch/peer-review-and-patch-aria-nbv-thesis-sections-a/peer_review_matrix.md`; KG claim check evidence in same matrix; theory/literature iteration mapping below. | Satisfied |
| Rank inclusion candidates from `.omx/specs/autoresearch-thesis-lit-review`. | Ranked inclusion decisions in `peer_review_matrix.md`; refined iteration-to-thesis table below. | Satisfied |
| Produce conflict / citation / inclusion matrix. | `peer_review_matrix.md` plus this audit's conflict/source table. | Satisfied |
| Identify exact thesis patches and dashy TODO markers. | Patch map below references current thesis lines and marker calls. | Satisfied |
| Implement approved patch set in `docs/typst/thesis`. | Current files under `docs/typst/thesis` include new theory section, data-generation boundary, method/evaluation fixes, and appendix relocation. | Satisfied |
| Verify with current commands. | Verification section below. | Pending until final commands in this continuation pass complete |

## Ten-Plus Iteration Trace

| Iteration | Source Evidence | Useful Finding | Thesis Adoption |
|---:|---|---|---|
| 2 | `.omx/specs/autoresearch-thesis-lit-review/report.md:224` | Candidate-query architecture should separate Set Transformer, QCNet-style RPE, Deja View recurrence, and point-backbone roles. | `docs/typst/thesis/sections/02-02-geometric-learning.typ:43-75`; `03-method.typ:296-324` |
| 3 | `report.md:319` | Referenced papers support bounded latent support memory, fusion ablations, recurrence tests, and geometry representation transfer, but not a broad backbone replacement. | `03-method.typ:15-166` |
| 4 | `report.md:403` | `Q_H` is an offline finite-action value estimator; Double-Q, support, replay rows, and headroom are required. | `04-evaluation.typ:52-134` |
| 5 | `report.md:469` | Target-RRI remains the objective; coverage, uncertainty, semantic masks, and hierarchy are support signals or bridges. | `02-01-related-work.typ`; `05-conclusion.typ:6-10` |
| 6 | `report.md:546` | Symmetry contract and exact-equivariance escalation must be explicit. | `02-02-geometric-learning.typ:9-83`; `03-method.typ:216-236` |
| 7 | `report.md:624` | Architecture stages need rollouts.zarr fields, pass/fail evidence, and production preflight gates. | `04-evaluation.typ:56-108`; `03-02-data-generation.typ:120-124` |
| 8 | `report.md:700` | Candidate distribution must be an experimental variable; realistic V1 motion support differs from free-shell upper bounds. | `03-method.typ:176-188`; `03-02-data-generation.typ:49-53` |
| 9 | `report.md:820` | Target-descriptor reliability, target matching, and OBS-SEL/PRED-Q/GT-EVAL audits precede target-conditioned `Q_H` claims. | `03-02-data-generation.typ:7-84`; `04-evaluation.typ:11-13` |
| 10 | `report.md:935` | Actor-visible state should progress from compact query pools to EVL internals, recurrence, and point/sparse backbones. | `03-method.typ:15-166` |
| 11 | `report.md:1049` | Behavior-policy support, stochastic branch provenance, and offline backup diagnostics gate `Q_H` interpretation. | `04-evaluation.typ:52-82`; `04-evaluation.typ:120-134` |
| 12 | `report.md:1161` | Online bridge and simulator work are RQ5/RQ6 escalations after offline finite-candidate evidence. | `05-conclusion.typ:8` |
| 13 | `report.md:1258` | Frame-aware invariance separates permutation, local-frame invariance, and gravity/egocentric semantics. | `02-02-geometric-learning.typ:13-15`; `03-method.typ:218-230` |
| 16 | `report.md:1550` | EVL is local actor-visible evidence; semidense/fused point banks precede point/sparse backbones. | `02-background.typ`; `03-method.typ:15-166` |
| 23 | `report.md:2151` | Geometric invariance needs a transformation and acceptance test matrix. | `02-02-geometric-learning.typ:17-41`; `03-method.typ:230-236` |
| 31 | `report.md:3133` | Target source, eligibility, ranking, GT-evaluation matching, and crop labeling must remain separate. | `03-02-data-generation.typ:55-124` |
| 32 | `report.md:3263` | TD backup ownership and all-invalid successor handling are trainer/replay facts, not prose-only assumptions. | `04-evaluation.typ:82-134` |
| 33 | `report.md:3388` | Sequence-model RL bridges and Gumbel-Top-k rollout diversity must not replace the finite-candidate proof burden. | `02-01-related-work.typ`; `05-conclusion.typ:8` |

## Section Coverage

| Thesis Surface | Review Result | Patch / Current Evidence |
|---|---|---|
| `main.typ` | Main body now ends at the conclusion; draft/open-work intake no longer appears as a numbered chapter. | `docs/typst/thesis/main.typ:51-55`; `appendix/index.typ:9` |
| Introduction | Needed clearer target-task sampler vs actor-visible V1 target protocol and less clustered bridge literature. | `01-introduction.typ:10-19` |
| Background / Related Work | Needed a dedicated geometric-learning theory section and tighter related-work role split. | `02-background.typ:9-11`; `02-01-related-work.typ`; `02-02-geometric-learning.typ` |
| Geometric Theory | Missing as a dedicated file before this pass. | New `02-02-geometric-learning.typ:7-83` |
| Formal State | Already had the actor/oracle split; no extra patch needed in this continuation. | Included through `03-method.typ:11` |
| Data Generation / Target RRI | Needed seminar-substrate boundary, oracle target-task sampler ownership, invalid crop handling, and manifest/runtime TODOs. | `03-02-data-generation.typ:7-124` |
| Backbone / Scene Encoder | Needed EFM3D/EVL as anchor, not a broad world-model claim; feature banks and backbones gated. | `03-method.typ:15-166` |
| Candidate / Replay | Needed all-candidate oracle scoring vs selected-transition storage clarity and default mixture vs legacy free-shell split. | `03-method.typ:168-214` |
| Architecture / `Q_H` | Needed acceptance tests and a caveat that seminar VINv3 is myopic substrate, not implemented finite-horizon `Q_H`. | `03-method.typ:216-330` |
| Evaluation | Needed seminar-to-thesis evidence gates, manifest count TODOs, paired policy comparison, and failure interpretation. | `04-evaluation.typ:5-172` |
| Conclusion | Already preserves conditional success / negative-result / failure-analysis structure and bridge boundaries. | `05-conclusion.typ:6-16` |
| Appendix | Raw TODO replaced with dashy marker and draft/open-work relocated. | `appendix/index.typ:1-9` |

The full section-by-section reviewer log is persisted in
`.omx/goals/autoresearch/arch-goal-thesis-peer-review-with-at-least-ten-a/section_peer_review_log.md`.

## Conflict / Citation / Inclusion Matrix

| Finding | Source Conflict Or Gap | Decision | Implemented Evidence |
|---|---|---|---|
| Seminar oracle RRI is scene-level implemented evidence, not current target-Q_H evidence. | Seminar paper vs active thesis target-RRI / rollout direction. | Include as substrate and label provenance; mark drift risk. | `03-02-data-generation.typ:19-53`; KG claim check supported the boundary |
| Legacy shell sampler is not the current default. | Seminar candidate generator vs current target-conditioned mixture contract. | Demote free-shell to historical upper-bound/stress ablation. | `03-method.typ:188` |
| One-step VINv3/CORAL does not implement finite-horizon target `Q_H`. | Seminar scorer vs planned target-conditioned residual value model. | Use as myopic control architecture and calibration substrate. | `03-method.typ:270`; `04-evaluation.typ:84-108` |
| Full-scale counts are planned contract, not manifest-backed final evidence. | Historical seminar subset counts are drift-prone. | Keep planned scale and add manifest validation TODO. | `04-evaluation.typ:138-144` |
| Geometric modules could be overcredited. | Literature supports structure, not ARIA-NBV gains. | Add theory section and require acceptance tests. | `02-02-geometric-learning.typ:79-83`; `03-method.typ:232-236` |
| Bridge literature can dilute thesis direction. | GenNBV/Hestia/3DGS/Deja View/point backbones are attractive but not thesis-core proof. | Keep as bridges, ablations, or diagnostics after target-RRI protocol is stable. | `02-01-related-work.typ`; `05-conclusion.typ:8` |

## Dashy Marker Map

| Marker | Purpose | Location |
|---|---|---|
| `#decision_todo` | Title/RQ/evidence freeze; target-threshold/gamma/open policy decisions. | `01-introduction.typ:22-26`; `03-02-data-generation.typ:114-118` |
| `#conflict_todo` | Prevent seminar scene-RRI / legacy sampler / VIN store / run logs from being copied as target-Q_H evidence. | `03-02-data-generation.typ:49-53` |
| `#validation_todo` | Geometric-learning stress tests, representation-ablation gates, manifest/runtime counts, final result tables. | `02-02-geometric-learning.typ:79-83`; `03-method.typ:162-166`; `03-02-data-generation.typ:120-124`; `04-evaluation.typ:140-144`; `04-evaluation.typ:168-172` |
| `#research_todo` | Bridge literature final placement and architecture ablation hypotheses. | `02-background.typ:61-65`; `03-method.typ:232-236`; `05-conclusion.typ:12-16` |
| `#impl_todo` | Appendix completion and final method implementation audit. | `appendix/index.typ:3-7`; `03-method.typ:326-330` |
| `#question_todo` | German abstract, acknowledgements, and appendix/open-work questions. | `main.typ:40-47`; `06-draft-open-work.typ` via appendix |

## Remaining Non-Blocking Gaps

- `docs/AGENTS.md` references `scripts/nbv_typst_includes.py`, but the file is
  not present in this worktree. This did not block the objective because the
  include graph was inspected directly from `main.typ`, `02-background.typ`,
  `03-method.typ`, and `appendix/index.typ`.
- The thesis still contains intentional dashy TODOs for open research decisions,
  final experiment results, and appendix detail. They are not blockers for this
  goal because the objective explicitly asked to flag current inconsistencies
  and TODOs rather than resolve all future thesis work.

## Verification Plan For Final Completion

- `cd docs && typst compile typst/thesis/main.typ --root . /tmp/thesis-arch-goal.pdf`
- `git diff --check`
- `make qmd-frontmatter-check`
- `make check-agent-memory`
- `rg -n "TODO: Add supplementary|#include \"sections/06-draft|gamma = 0\\.1|vin_offline\\.counterfactuals|online RL.*stretch|highest-level project ground truth" docs/typst/thesis .omx/goals/autoresearch`
- `make kg-claim-check KG_CLAIM="The seminar oracle RRI substrate is implemented evidence for one-step scene-level labels and not evidence that the target-conditioned finite-horizon Q_H model is already implemented."`
