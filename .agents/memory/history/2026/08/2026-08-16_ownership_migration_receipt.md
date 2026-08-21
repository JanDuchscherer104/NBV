---
id: ownership-migration-receipt-2026-08-16
date: 2026-08-16
title: Ownership migration receipt and review reconciliation
status: done
topics: [ownership, migration, review]
confidence: high
canonical_updates_needed: []
---

# Ownership migration receipt

This is a human-reviewable migration receipt, not a replacement owner. The
retired source bytes are addressed by immutable Git commit and blob IDs; no
scientific or implementation content is copied here.

## Review decisions

- Human review approved one intentional PR (#59) for the ownership
  consolidation; focused commits remain the rollback boundaries.
- The active RQ owner supersedes the earlier four-question extraction with six
  tiered questions: RQ1--RQ4 are the evaluated core, RQ5 is a conditional
  online bridge, and RQ6 is a lower-priority continuous/simulator escalation.
  This records scope and precedence only; the six questions live in Typst.

## Retired-source receipt

All rows use immutable deletion commit `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8`;
the blob is the exact parent-tree blob and the source anchor is a heading/span.
The table is deliberately ledger-only: it copies no theory or contract text.

| Row ID | Immutable source (commit/blob/heading or span) | Subject | Disposition | Exact destination path + anchor/symbol | Verification |
|---|---|---|---|---|---|
| retired-001-roadmap-thesis-outcome | `docs/contents/thesis/roadmap.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `96be4e83fdf77ba08d76b9cc4e12928c5c44ae94` / `roadmap-thesis-outcome` (49-74) | planned outcomes and RQ5/RQ6 scope | historical | `docs/typst/thesis/development/roadmap.typ#outcome` | verified: Typst marker/render checks |
| retired-002-roadmap-literature-grounding | `docs/contents/thesis/roadmap.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `96be4e83fdf77ba08d76b9cc4e12928c5c44ae94` / `roadmap-literature-grounding` (97-125) | primary claim and non-claims | historical | `docs/typst/thesis/sections/01-introduction.typ#introduction` | verified: Typst render |
| retired-003-roadmap-mathematical-model | `docs/contents/thesis/roadmap.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `96be4e83fdf77ba08d76b9cc4e12928c5c44ae94` / `roadmap-mathematical-model` (128-326) | mathematical model | historical | `docs/typst/thesis/sections/04-method/04-05-finite-candidate-value-model.typ#eqs.rl.finite_horizon_return` | verified: Typst equation checks |
| retired-004-roadmap-evidence-flow | `docs/contents/thesis/roadmap.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `96be4e83fdf77ba08d76b9cc4e12928c5c44ae94` / `roadmap-evidence-flow` (328-369) | evidence-flow diagrams | historical | `docs/typst/thesis/sections/03-oracle-and-data-generation/03-01-state-and-visibility.typ#fig:qh-actor-oracle-contract` | verified: Typst figure checks |
| retired-005-roadmap-milestones | `docs/contents/thesis/roadmap.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `96be4e83fdf77ba08d76b9cc4e12928c5c44ae94` / `roadmap-milestones` (371-636) | milestones, gates, pointers | historical | `docs/typst/thesis/development/roadmap.typ#milestones` | verified: development marker fixtures |
| retired-006-roadmap-ablations | `docs/contents/thesis/roadmap.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `96be4e83fdf77ba08d76b9cc4e12928c5c44ae94` / `roadmap-ablations` (637-652) | required ablations | historical | `docs/typst/thesis/development/roadmap.typ#ablations` | verified: development marker fixtures |
| retired-007-roadmap-evidence-contract | `docs/contents/thesis/roadmap.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `96be4e83fdf77ba08d76b9cc4e12928c5c44ae94` / `roadmap-evidence-contract` (653-705) | evidence reporting contract | historical | `docs/typst/thesis/development/roadmap.typ#evidence` | verified: development marker fixtures |
| retired-008-roadmap-risks | `docs/contents/thesis/roadmap.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `96be4e83fdf77ba08d76b9cc4e12928c5c44ae94` / `roadmap-risks` (706-717) | risk register | historical | `docs/typst/thesis/development/roadmap.typ#risks` | verified: development marker fixtures |
| retired-009-kg-authoring-rules | `docs/contents/thesis/roadmap.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `96be4e83fdf77ba08d76b9cc4e12928c5c44ae94` / `kg-authoring-rules` (718-733) | authoring rules | removed | `Git history/debrief provenance (removed; receipt commit 8fcabeffed7c898b6c7d0ec02c65e24097ea68d8)` | verified: removal/reference scan |
| retired-010-roadmap-verification | `docs/contents/thesis/roadmap.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `96be4e83fdf77ba08d76b9cc4e12928c5c44ae94` / `roadmap-verification` (735-751) | standing verification commands | historical | `docs/README.md#Commands-and-owners` | verified: docs owner exists |
| retired-011-rq-objectives | `docs/contents/thesis/questions.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `c3f846f7dadce878329739c5f1ca8388351f03ed` / `rq-objectives` (32-58) | objectives and evidence protocol | historical | `docs/typst/thesis/sections/01-research-questions.typ#rq-objectives` | verified: RQ contract |
| retired-012-rq-definitions | `docs/contents/thesis/questions.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `c3f846f7dadce878329739c5f1ca8388351f03ed` / `rq-definitions` (60-74) | RQ terminology definitions | removed | `Git history/debrief provenance (removed; receipt commit 8fcabeffed7c898b6c7d0ec02c65e24097ea68d8)` | verified: removal/reference scan |
| retired-013-rq-thesis-boundary | `docs/contents/thesis/questions.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `c3f846f7dadce878329739c5f1ca8388351f03ed` / `rq-thesis-boundary` (80-96) | thesis boundary | historical | `docs/typst/thesis/sections/01-introduction.typ#boundary` | verified: Typst render |
| retired-014-rq-proposal-freeze-gate | `docs/contents/thesis/questions.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `c3f846f7dadce878329739c5f1ca8388351f03ed` / `rq-proposal-freeze-gate` (98-120) | proposal freeze decisions | historical | `docs/typst/thesis/development/roadmap.typ#freeze` | verified: promotion fixtures |
| retired-015-rq1-objective | `docs/contents/thesis/questions.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `c3f846f7dadce878329739c5f1ca8388351f03ed` / `rq1-objective` (122-220) | RQ1 objective/reward | historical | `docs/typst/thesis/sections/01-research-questions.typ#rq1` | verified: RQ contract |
| retired-016-rq2-offline-qh | `docs/contents/thesis/questions.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `c3f846f7dadce878329739c5f1ca8388351f03ed` / `rq2-offline-qh` (223-333) | RQ2 offline finite-candidate Q_H | historical | `docs/typst/thesis/sections/01-research-questions.typ#rq2` | verified: RQ contract |
| retired-017-rq3-representation | `docs/contents/thesis/questions.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `c3f846f7dadce878329739c5f1ca8388351f03ed` / `rq3-representation` (335-424) | RQ3 target representation | historical | `docs/typst/thesis/sections/01-research-questions.typ#rq3` | verified: RQ contract |
| retired-018-rq4-support | `docs/contents/thesis/questions.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `c3f846f7dadce878329739c5f1ca8388351f03ed` / `rq4-support` (426-535) | RQ4 candidate/rollout support | historical | `docs/typst/thesis/sections/01-research-questions.typ#rq4` | verified: RQ contract |
| retired-019-rq5-online | `docs/contents/thesis/questions.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `c3f846f7dadce878329739c5f1ca8388351f03ed` / `rq5-online` (537-559) | RQ5 online bridge | historical | `docs/typst/thesis/sections/01-research-questions.typ#rq5` | verified: RQ contract |
| retired-020-rq6-continuous | `docs/contents/thesis/questions.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `c3f846f7dadce878329739c5f1ca8388351f03ed` / `rq6-continuous` (560-586) | RQ6 continuous/simulator escalation | historical | `docs/typst/thesis/sections/01-research-questions.typ#rq6` | verified: RQ contract |
| retired-021-rq-evidence-protocol | `docs/contents/thesis/questions.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `c3f846f7dadce878329739c5f1ca8388351f03ed` / `rq-evidence-protocol` (587-639) | shared evidence protocol | historical | `docs/typst/thesis/sections/01-research-questions.typ#protocol` | verified: RQ contract |
| retired-022-rq-matrix | `docs/contents/thesis/questions.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `c3f846f7dadce878329739c5f1ca8388351f03ed` / `rq-matrix` (640-651) | research matrix | historical | `docs/typst/thesis/sections/01-research-questions.typ#matrix` | verified: RQ contract |
| retired-023-rq-kg-writing | `docs/contents/thesis/questions.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `c3f846f7dadce878329739c5f1ca8388351f03ed` / `rq-kg-writing` (652-665) | question-writing rules | removed | `Git history/debrief provenance (removed; receipt commit 8fcabeffed7c898b6c7d0ec02c65e24097ea68d8)` | verified: removal/reference scan |
| retired-024-m1-status-summary | `docs/contents/thesis/m1_contract_report.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `3a2be94b278513fefcf376eba12013a450a70b2f` / `m1-status-summary` (19-33) | M1 status | historical | `docs/typst/thesis/development/m1-contract-report.typ#m1-status` | verified: marker fixtures |
| retired-025-m1-evidence-snapshot | `docs/contents/thesis/m1_contract_report.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `3a2be94b278513fefcf376eba12013a450a70b2f` / `m1-evidence-snapshot` (34-56) | M1 evidence snapshot | historical | `docs/typst/thesis/development/m1-contract-report.typ#m1-evidence` | verified: marker fixtures |
| retired-026-m1-contract-map | `docs/contents/thesis/m1_contract_report.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `3a2be94b278513fefcf376eba12013a450a70b2f` / `m1-contract-map` (57-72) | implementation contract map | code-owned | `aria_nbv/aria_nbv/data_handling/vin_store/source.py#VinOfflineSourceConfig` | verified: package contract tests |
| retired-027-m1-passing-checks | `docs/contents/thesis/m1_contract_report.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `3a2be94b278513fefcf376eba12013a450a70b2f` / `m1-passing-checks` (73-95) | checks and serialized facts | test-owned | `aria_nbv/tests/data_handling/test_public_api_contract.py#test_storage_and_training_contracts_are_documented_at_their_owners` | verified: focused test |
| retired-028-m1-blockers | `docs/contents/thesis/m1_contract_report.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `3a2be94b278513fefcf376eba12013a450a70b2f` / `m1-blockers` (96-113) | M1 blockers | deferred-action | `docs/typst/thesis/development/m1-contract-report.typ#m1-blockers` | verified: marker fixtures |
| retired-029-m1-command-ledger | `docs/contents/thesis/m1_contract_report.qmd` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `3a2be94b278513fefcf376eba12013a450a70b2f` / `m1-command-ledger` (114-160) | command/evidence ledger | historical | `docs/README.md#Commands-and-owners` | verified: docs owner exists |
| retired-030-goal-core-claim | `.agents/memory/state/PROJECT_STATE.md` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `470b9cfd54e4fcb34b4865dd199d32093c1b7fe8` / `goal-core-claim` (12-20) | core claim and implementation status | historical | `docs/typst/thesis/sections/01-introduction.typ#introduction` | verified: Typst render |
| retired-031-priorities | `.agents/memory/state/PROJECT_STATE.md` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `470b9cfd54e4fcb34b4865dd199d32093c1b7fe8` / `priorities` (22-33) | priorities and meeting decisions | historical | `docs/typst/thesis/development/roadmap.typ#priorities` | verified: marker fixtures |
| retired-032-issues-blockers | `.agents/memory/state/PROJECT_STATE.md` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `470b9cfd54e4fcb34b4865dd199d32093c1b7fe8` / `issues-blockers` (34-41) | issues and blockers | historical | `docs/typst/thesis/development/roadmap.typ#issues-and-blockers` | verified: marker fixtures |
| retired-033-next-steps | `.agents/memory/state/PROJECT_STATE.md` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `470b9cfd54e4fcb34b4865dd199d32093c1b7fe8` / `next-steps` (43-61) | next steps and contracts | historical | `docs/typst/thesis/development/roadmap.typ#promotion-queue` | verified: promotion fixtures |
| retired-034-extensions-pointers | `.agents/memory/state/PROJECT_STATE.md` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `470b9cfd54e4fcb34b4865dd199d32093c1b7fe8` / `extensions-pointers` (63-74) | deferred extensions and pointers | removed | Git history/debrief provenance (receipt commit `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8`) | verified: explicit removal evidence |
| retired-035-workflow | `.agents/memory/state/DECISIONS.md` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `0c72a15bd633f8c67fafd3b79204ac1c63200282` / `workflow` (12-39) | workflow/source-order decisions | historical | `.agents/skills/aria-nbv-context/SKILL.md#owner-hierarchy` | verified: guidance check |
| retired-036-scientific | `.agents/memory/state/DECISIONS.md` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `0c72a15bd633f8c67fafd3b79204ac1c63200282` / `scientific` (40-180) | thesis/RQ/reward decisions | historical | `docs/typst/thesis/sections/01-introduction.typ#introduction` | verified: Typst render |
| retired-037-implementation | `.agents/memory/state/DECISIONS.md` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `0c72a15bd633f8c67fafd3b79204ac1c63200282` / `implementation` (181-320) | storage/schema/rollout contracts | code-owned | `aria_nbv/aria_nbv/rollouts/trace.py#RolloutLineage` | verified: package tests |
| retired-038-ci | `.agents/memory/state/DECISIONS.md` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `0c72a15bd633f8c67fafd3b79204ac1c63200282` / `ci` (321) | CI/pre-commit policy | historical | `.github/workflows/ci.yml#workflow:name=Root Verification` | verified: CI config exists |
| retired-039-environment | `.agents/memory/state/GOTCHAS.md` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `ce680d4634ca5d3cc52ecdf572c6737d6ce9eb95` / `environment` (12-18) | environment/tooling gotchas | historical | `SETUP.md#5-offline-store-and-VIN-diagnostics` | verified: setup owner exists |
| retired-040-training-storage | `.agents/memory/state/GOTCHAS.md` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `ce680d4634ca5d3cc52ecdf572c6737d6ce9eb95` / `training-storage` (19-29) | training/offline-store contracts | code-owned | `aria_nbv/aria_nbv/data_handling/vin_store/source.py#VinOfflineSourceConfig` | verified: package tests |
| retired-041-geometry-config | `.agents/memory/state/GOTCHAS.md` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `ce680d4634ca5d3cc52ecdf572c6737d6ce9eb95` / `geometry-config` (30-42) | frames, EVL, Pydantic behavior | code-owned | `aria_nbv/aria_nbv/pose_generation/candidate_generation.py#CandidateViewGeneratorConfig` | verified: geometry contract tests |
| retired-042-advisor | `.agents/memory/state/OPEN_QUESTIONS.md` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `f391257d6aecbd2c0692be206ae13c50660b22d8` / `advisor` (12-16) | advisor-facing scale/Q_H decisions | historical | `docs/typst/thesis/development/roadmap.typ#promotion-queue` | verified: promotion fixtures |
| retired-043-matching | `.agents/memory/state/OPEN_QUESTIONS.md` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `f391257d6aecbd2c0692be206ae13c50660b22d8` / `matching` (17-21) | target matching/representation | historical | `docs/typst/thesis/sections/01-research-questions.typ#rq3` | verified: RQ contract |
| retired-044-qh | `.agents/memory/state/OPEN_QUESTIONS.md` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `f391257d6aecbd2c0692be206ae13c50660b22d8` / `qh` (22-30) | Q_H/offline RL choices | historical | `docs/typst/thesis/sections/01-research-questions.typ#rq2` | verified: RQ contract |
| retired-045-storage | `.agents/memory/state/OPEN_QUESTIONS.md` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `f391257d6aecbd2c0692be206ae13c50660b22d8` / `storage` (32-36) | storage/scale/reporting choices | code-owned | `aria_nbv/aria_nbv/data_handling/vin_store/store.py#VinOfflineStoreConfig` | verified: package tests |
| retired-046-representation | `.agents/memory/state/OPEN_QUESTIONS.md` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `f391257d6aecbd2c0692be206ae13c50660b22d8` / `representation` (38-42) | representation/ablation choices | historical | `docs/typst/thesis/development/roadmap.typ#promotion-queue` | verified: promotion fixtures |
| retired-047-locked | `.agents/memory/state/OPEN_QUESTIONS.md` / `8fcabeffed7c898b6c7d0ec02c65e24097ea68d8` / `f391257d6aecbd2c0692be206ae13c50660b22d8` / `locked` (44-50) | recently locked decisions | historical | `docs/typst/thesis/development/roadmap.typ#freeze` | verified: promotion fixtures |

## Deferred-action qualification

`deferred-action` is used only after the source block's durable content has an
existing canonical owner. The separate backlog record owns the follow-up action
metadata, not the scientific or implementation contract.

| Receipt row | Materialized canonical owner | Backlog ID | Action owner | Acceptance | Gate |
|---|---|---|---|---|---|
| retired-028-m1-blockers | `docs/typst/thesis/development/m1-contract-report.typ#m1-blockers` | `todo-007` | M1 data/cache/oracle contract lane | Fresh store, scene split, Rerun diagnostics, and throughput evidence are reviewable. | The acceptance and verification fields of `todo-007` pass before M1 closes. |

## Separate conditional-experiment tracking

The reviewed RQ5/RQ6 definitions are already materialized in Typst. Their
unimplemented experiments remain separate actionable records:

| Scope | Scientific owner | Active backlog record | Entry gate |
|---|---|---|---|
| RQ5 online discrete bridge | `docs/typst/thesis/sections/01-research-questions.typ#rq5` | `todo-095` | Stable offline Q_H headroom, replay support, and M1 evidence. |
| RQ6 continuous/simulator escalation | `docs/typst/thesis/sections/01-research-questions.typ#rq6` | `todo-006`; `todo-038` | RQ5 evidence plus an explicit simulator/scope decision. |

## Theory-QMD keep/thin/delete matrix

All eight stable URLs are deliberately retained as thin, deprecated public
navigation/background pages. The matrix records the content-led disposition;
it does not make this receipt or the QMDs current theory owners.

| Theory page | Disposition | Unique retained value | Canonical destination | Inbound links | Citation disposition |
|---|---|---|---|---|---|
| `candidate_sampling_target_selection.qmd` | thin | Stable sampling/target-selection reading-guide URL and literature navigation. | `docs/typst/thesis/sections/01-research-questions.typ#rq4`; Python pose-generation owners. | `docs/_quarto.yml`; theory peers; `docs/contents/literature/3dgs_instance_nbv.qmd`; agents DB pointers. | No citation keys in the source; removed design prose resolves to Typst/Python owners. |
| `candidate_view_dependence.qmd` | thin | DeepSets, Set Transformer, and geometric-learning background for finite candidate sets. | `docs/typst/thesis/sections/02-foundations/02-02-geometric-learning.typ#sec:thesis-geometric-learning-theory`. | `candidate_sampling_target_selection.qmd`; method-section source pointers; `docs/_quarto.yml`. | Retains `DeepSets-zaheer2017`, `SetTransformer-lee2019`, and `GeometricDeepLearning-bronstein2021`; source-only auxiliary keys remain bibliography/history evidence. |
| `efm3d_scene_embeddings.qmd` | thin | EFM3D/EVL background and navigation to actor-visible representation owners. | `docs/typst/thesis/sections/04-method/04-01-scene-representation-requirements.typ#sec:thesis-scene-representation`. | `docs/contents/literature/efm3d.qmd`; `semi-dense-pc.qmd`; glossary; method-section source pointers; `docs/_quarto.yml`. | Retains `EFM3D-straub2024`; ATEK/DeepSets/SetTransformer detail remains in bibliography, literature, or canonical thesis owners. |
| `nbv_background.qmd` | thin | Classical-to-learning NBV reading-guide URL with GenNBV and VIN-NBV background. | `docs/typst/thesis/sections/02-foundations/index.typ#sec:thesis-foundations`. | `docs/index.qmd`; `docs/contents/literature/pb_nbv.qmd`; glossary; `docs/_quarto.yml`. | Retains `GenNBV-chen2024` and `VIN-NBV-frahm2025`. |
| `rl_planning.qmd` | thin | Stable finite-candidate rollout/Q_H navigation URL. | `docs/typst/thesis/sections/04-method/index.typ#sec:thesis-method`; `docs/typst/thesis/sections/01-research-questions.typ#rq2`. | RL and NBV literature pages; glossary; agents DB; `docs/_quarto.yml`. | Formal RL citations and equations resolve to the thesis and `docs/contents/literature/rl_planning.qmd`; no citation keys remain on the thin page. |
| `rri_theory.qmd` | thin | RRI motivation and navigation to metric/background and executable owners. | `docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ#fig:target-rri-point-mesh-geometry`. | `docs/index.qmd`; literature pages; glossary; agents DB; `docs/_quarto.yml`. | Retains `VIN-NBV-frahm2025`; derivations and additional evidence resolve to Typst, literature, and Git history. |
| `semi-dense-pc.qmd` | thin | Project Aria semi-dense/inverse-distance background. | `docs/typst/thesis/sections/03-oracle-and-data-generation/03-01-state-and-visibility.typ`. | `docs/index.qmd`; Project Aria literature; EFM3D background; glossary; `docs/_quarto.yml`. | Retains `Engel2014LSD`; EFM3D and Hartley--Zisserman context remains in the EFM3D literature/thesis or bibliography. |
| `surface_metrics.qmd` | thin | Chamfer-style accuracy/completeness and F-score background. | `docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ#fig:target-rri-point-mesh-geometry`. | `docs/index.qmd`; `rri_theory.qmd`; glossary; `docs/_quarto.yml`. | Retains `VIN-NBV-frahm2025`; metric equations and acceptance behavior resolve to Typst and Python/tests. |

The source-level gates intentionally do not treat this receipt as a current
truth source. They only require the retired paths to stay absent and the
canonical destinations to remain reachable.
