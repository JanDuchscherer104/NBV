---
kind: context
status: current
slug: online-oracle-mvp
captured: 2026-08-22
branch: codex/online-oracle-mvp
baseline: a121cd821f7748f979c2cddf0f7c3af0e0b6a5a7
---

# Online oracle MVP context

## Requested outcome

Plan the smallest ARIA-NBV implementation that can:

1. train, persist, restore, and infer a target-conditioned finite-horizon
   candidate-value model over the existing `QhActorTensors` views;
2. collect new training transitions through the existing hard ASE oracle and
   update that model in bounded online-learning rounds;
3. later let an actor propose a hierarchical categorical-family plus bounded
   local 5-DoF camera pose, with the realized proposals ranked by the same
   multi-step value model; and
4. state exactly which paths must retain gradients and which remain hard,
   detached environment or persistence operations.

This record is planning evidence. It changes no thesis claim and authorizes no
implementation lane.

## Graphify gate

Graphify was refreshed before architecture work. The authoritative checker at
the baseline commit reported:

```json
{
  "fresh": true,
  "graph_revision": "a121cd821f7748f979c2cddf0f7c3af0e0b6a5a7",
  "head": "a121cd821f7748f979c2cddf0f7c3af0e0b6a5a7",
  "stale_sources": [],
  "state": "fresh",
  "usable": true
}
```

The rebuilt graph contains 7,196 nodes and 15,794 edges. Multigraph diagnosis
reported zero exact duplicate edges, zero missing or dangling endpoints, and
zero unverified nodes. Graphify was navigation; the exact owners below were
opened before making consequential claims.

## Measured-autoresearch gate

The requested `measured-autoresearch` sidecar requires exactly one active OMX
autoresearch or autoresearch-goal mission with a frozen evaluator, baseline,
budget, and keep/discard rule. No Codex goal or active mission exists in this
worktree, and no candidate-independent online-oracle evaluator has been frozen.
Therefore:

- the issue, repository, thesis, and primary-source synthesis in this record is
  ordinary planning research, not measured experimental evidence;
- no experiment row, baseline, or candidate result is invented; and
- the first executable work package must freeze the parity/performance evaluator
  before `measured-autoresearch` may optimize an implementation candidate.

## Exact current owners

### Actor and training views

- `aria_nbv/aria_nbv/data_handling/qh_data/views.py` owns immutable
  `QhActorTensors`, `QhSupervision`, actor-state profiles, root EVL context,
  selected-observation prefixes, and chain identity.
- `QhActorTensors` already separates actor-visible state from oracle labels and
  audit identity. It carries root pose, observed-target-relative pose and
  extents, candidate poses and masks, selected-pose history, remaining budget,
  root EVL fields, and an optional causal selected-observation prefix.
- `aria_nbv/aria_nbv/data_handling/qh_data/batching.py` owns the batched
  `[B,S,N]` projection.
- `aria_nbv/aria_nbv/lightning/qh_datamodule.py` owns stage admission,
  actor-state and learning-contract hashes, scene-disjointness, horizon
  agreement, and deterministic loaders.

### Finite-horizon optimization

- `aria_nbv/aria_nbv/lightning/qh_module.py` already accepts an injected
  `nn.Module(QhActorTensors) -> Tensor[B,S,N]`.
- It owns selected-action Huber loss, masked Double-Q selection/evaluation,
  optimizer transactions, target-network synchronization, lifecycle admission,
  and contract hashes.
- It does not own a production scorer architecture or a scorer-reconstructable
  inference checkpoint.
- `aria_nbv/aria_nbv/vin/models/target_finite_horizon.py` is named by issue #75
  but does not exist.
- `aria_nbv/aria_nbv/vin/models/target_myopic.py` is runnable only when the
  target descriptor width is zero; positive-width target conditioning raises
  `NotImplementedError`.

### EVL and one-step VIN

- `aria_nbv/aria_nbv/vin/backbones/evl.py` owns the EVL adapter.
- The wrapper always sets EVL to evaluation mode and executes forward under
  `torch.no_grad()`, including when `freeze=False`. It therefore is not a
  fine-tuning path today.
- Returned EVL tensors do not carry checkpoint/config content identity. Any
  durable Q_H bundle must bind the actor-manifest and EVL config/checkpoint
  hashes outside those tensors.
- Existing pose encoders, scene-field projection, and pose-conditioned voxel
  pooling in `aria_nbv/aria_nbv/vin/` are reusable model internals.
- `aria_nbv/aria_nbv/vin/candidate_scorer.py` intentionally excludes Q_H from
  its CORAL one-step `VinPrediction` contract; Q_H keeps its dedicated
  continuous-value objective.

### Oracle and replay

- `aria_nbv/aria_nbv/oracle/target_rri.py` and
  `aria_nbv/aria_nbv/oracle/_scoring.py` own hard target-RRI evaluation.
- `aria_nbv/aria_nbv/rollouts/replay/engine.py` owns deterministic candidate
  regeneration, rollout traversal, and built-in selection behavior.
- Its score callback and `CandidateScores` DTO are detached persistence-facing
  contracts, not live gradient-bearing policy decisions.
- `aria_nbv/aria_nbv/oracle/pipelines/online_vin.py` streams newly computed
  one-step oracle labels to VIN training. Its word "online" means label
  generation, not an online policy-learning environment.
- The current rollout pipeline couples oracle episode state and cacheable work
  to store writing. There is no reusable presentation-free online episode API.
- Existing rollout/Zarr stores are immutable evidence. The minimal online loop
  should add one immutable collection shard per round rather than mutate a
  serving replay buffer in place.

### Candidate proposals

- `aria_nbv/aria_nbv/pose_generation/` owns full-shell candidate sampling,
  compact valid views, stable family/position IDs, hard masks, reason codes,
  and proposal provenance.
- Candidate selection and proposal generation are different learning problems.
  A selector compares policies on identical candidate tables; a proposer
  changes support and therefore requires proposal-regret and support evidence.

## Current scientific gates

The active thesis makes the ordering explicit:

- M5 is the required finite-candidate lookahead and Q_H gate.
- RQ5 online discrete Q_H is conditional on stable positive offline headroom
  and replay support and must keep the same finite action contract.
- RQ6 hierarchical or continuous pose control is lower-priority M6 bridge work
  after the discrete evidence is stable.
- The canonical value direction remains fixed maximum horizon with remaining
  budget in actor state until the source owner chooses a different horizon
  interface.

The implementation plan may build testable code before confirmatory evidence,
but it must not bypass these scientific promotion gates or rewrite the thesis
scope implicitly.

## GitHub issue dependency map

### Parent and prerequisites

- #67 separates candidate-support quality, learned finite-candidate selection,
  and learned proposal/refinement phases.
- #54 owns production target-family-collapse preflight.
- #68-#73 own deterministic proposal streams, decoupled center/gaze families,
  state-aware schedules, reservoir/diversity behavior, physical feasibility,
  and the proposal benchmark.
- #79 and #80 are P0 camera/depth and target-RRI fidelity gates.
- #81 separates untouched evaluation populations from adaptive or
  policy-induced training acquisition.
- #82 requires V1 observed/predicted actor descriptors to remain distinct from
  privileged GT association and target crops.
- #89 keeps raw selected CF-GT observation prefixes separate from a future
  derived `DynamicSceneState`.

Live issue set inspected for this plan:

- [#67](https://github.com/JanDuchscherer104/ARIA-NBV/issues/67),
  [#54](https://github.com/JanDuchscherer104/ARIA-NBV/issues/54),
  [#68](https://github.com/JanDuchscherer104/ARIA-NBV/issues/68),
  [#69](https://github.com/JanDuchscherer104/ARIA-NBV/issues/69),
  [#70](https://github.com/JanDuchscherer104/ARIA-NBV/issues/70),
  [#71](https://github.com/JanDuchscherer104/ARIA-NBV/issues/71),
  [#72](https://github.com/JanDuchscherer104/ARIA-NBV/issues/72), and
  [#73](https://github.com/JanDuchscherer104/ARIA-NBV/issues/73);
- [#74](https://github.com/JanDuchscherer104/ARIA-NBV/issues/74),
  [#75](https://github.com/JanDuchscherer104/ARIA-NBV/issues/75),
  [#76](https://github.com/JanDuchscherer104/ARIA-NBV/issues/76), and
  [#77](https://github.com/JanDuchscherer104/ARIA-NBV/issues/77);
- [#79](https://github.com/JanDuchscherer104/ARIA-NBV/issues/79),
  [#80](https://github.com/JanDuchscherer104/ARIA-NBV/issues/80),
  [#81](https://github.com/JanDuchscherer104/ARIA-NBV/issues/81),
  [#82](https://github.com/JanDuchscherer104/ARIA-NBV/issues/82), and
  [#89](https://github.com/JanDuchscherer104/ARIA-NBV/issues/89).

### Online and learned-control issues

- #74 proposes a reusable `OracleNbvEnvironment`, explicit dense/subset/
  selected-only oracle query modes, episode-local caches, atomic transitions,
  endpoint evaluation, and a collector above—not inside—the environment.
  These query modes do not imply one learning objective: the MVP fitted-Q
  contract requires dense valid labels, while sparse modes remain evaluation or
  separately versioned future objectives.
- #75 proposes a learned masked finite-candidate policy, a live
  gradient-bearing `PolicyDecision`, a separate detached storage projection,
  dense one-step then offline Q_H then optional online stages, and matched hard
  oracle evaluation. The MVP narrows this: inference collection uses the
  existing detached replay selection record, while any future policy-gradient
  learner must recompute log probability from stored actor/action data in a
  separate training-mode objective.
- #76 requires categorical semantic-family choice plus bounded local 5-DoF
  parameters/residuals, fixed anchors, exact attempted-proposal probability,
  and initially alternating frozen selector/proposer phases.
- #77 states the differentiability boundary: offline Q needs only scorer
  parameter gradients; policy gradients need selected log-probability;
  continuous proposals use score-function or a reparameterized surrogate; local
  refinement needs a differentiable local pose constructor and surrogate; the
  current hard oracle is not the first gradient path.

## Primary-source orientation

- VIN-NBV motivates direct learned prediction of reconstruction-quality
  improvement for candidate ranking.
- Double DQN motivates separating online-network action selection from delayed
  target-network evaluation; it does not solve offline support mismatch.
- DAgger motivates train-only aggregation of learner-induced states while
  leaving validation/test populations untouched.
- Advantage-Weighted Regression supports an initial off-policy proposer update
  from fixed replay or elite proposals.
- BCQ and CQL motivate explicit support constraints for offline value learning.
- Stochastic computation graphs justify score-function gradients with an opaque
  nondifferentiable environment reward.
- GenNBV and Hestia show that 5-DoF and hierarchical continuous NBV policies are
  meaningful comparison points, but both change the action-support contract.
- Soft Rasterizer and PyTorch3D show that differentiable rendering operators
  exist; they do not make the current hard render/crop/fuse/RRI chain a stable
  end-to-end gradient path.

### Primary-source bibliography

- [VIN-NBV](https://arxiv.org/abs/2505.06219) for direct candidate-wise
  reconstruction-improvement prediction.
- [GenNBV (CVPR 2024)](https://openaccess.thecvf.com/content/CVPR2024/html/Chen_GenNBV_Generalizable_Next-Best-View_Policy_for_Active_3D_Reconstruction_CVPR_2024_paper.html)
  and [Hestia (WACV 2026)](https://openaccess.thecvf.com/content/WACV2026/html/Lu_Hestia_Voxel-Face-Aware_Hierarchical_Next-Best-View_Acquisition_for_Efficient_3D_Reconstruction_WACV_2026_paper.html)
  for 5-DoF and hierarchical NBV comparison points.
- [Double DQN](https://arxiv.org/abs/1509.06461) for decoupled online-network
  selection and delayed-target evaluation.
- [DAgger](https://proceedings.mlr.press/v15/ross11a.html) for aggregation on
  learner-induced training-state distributions.
- [Advantage-Weighted Regression](https://arxiv.org/abs/1910.00177),
  [BCQ](https://proceedings.mlr.press/v97/fujimoto19a.html), and
  [CQL](https://proceedings.neurips.cc/paper/2020/hash/0d2b2061826a5df3221116a5085a6052-Abstract.html)
  for off-policy proposal updates and support-aware offline learning.
- [Stochastic Computation Graphs](https://arxiv.org/abs/1506.05254) for
  score-function gradients through nondifferentiable rewards.
- [Soft Rasterizer](https://openaccess.thecvf.com/content_ICCV_2019/html/Liu_Soft_Rasterizer_A_Differentiable_Renderer_for_Image-Based_3D_Reasoning_ICCV_2019_paper.html)
  and [PyTorch3D](https://arxiv.org/abs/2007.08501) for differentiable-rendering
  alternatives that remain outside the MVP hard-oracle contract.

## Codebase-design comparison

Three independent Design It Twice proposals were reviewed.

### Option A — put model, trainer, policy, and loop in Lightning

This has a tiny nominal public surface but weak Locality: oracle state,
selection, persistence, and optimizer behavior accumulate in one Module. It
also makes `QhLightningModule` interpret scorer and environment details that it
currently isolates through injection. Rejected except for retaining the
existing optimizer Adapter.

### Option B — introduce a new generic `rl` package and strategy composition

This gives future variant flexibility but creates a new truth surface before a
second real implementation exists. A registry or plugin factory would weaken
contract hashing and obscure existing `vin`, `oracle`, `rollouts`, and
`pose_generation` owners. Rejected. A closed scorer configuration union may be
introduced locally only when a second scorer is real.

### Option C — bound episode facade plus owner-local deep modules

Chosen synthesis:

- `TargetFiniteHorizonScorer` in `vin/models` is the deep learned Module.
- `QhLightningModule` remains its optimization Adapter.
- `OracleNbvEnvironment.open(request) -> OracleNbvEpisode` is the oracle Seam
  over one extracted replay transition kernel. Its
  `prepare_decision/evaluate/commit` protocol binds the episode, state, and
  candidate table so stale or cross-table calls fail closed.
- a private, pipeline-local Q_H score Adapter returns the existing detached
  `CandidateScores`; existing replay policies and selection records remain the
  only inference-selection vocabulary, and replay never imports oracle context
  types.
- a round collector under `oracle/pipelines` composes a frozen inference bundle,
  environment, and existing immutable rollout writer without moving those
  responsibilities into the environment.
- a hierarchical proposal attempt plus owner-local materializer stays in
  `pose_generation` and must emit the existing `CandidateSamplingResult`
  contract.

This option has the best Depth and Locality. The caller sees a small episode
vocabulary, while renderer caching, target evidence, state hashing, transaction
semantics, and cleanup remain hidden. Existing offline generation can later use
the same episode Adapter, giving Leverage and an equivalence oracle.

## Minimum differentiability matrix

| Path | Differentiable | Hard or detached |
| --- | --- | --- |
| Offline/round-based Q_H | scorer parameters; continuous value head | stored views, masks, candidate generation, oracle labels, target construction |
| Deterministic inference | nothing; use inference mode | masked argmax, checkpoint load, episode transition |
| MVP fitted-Q behavior collection | scorer parameters only during later replay training | collection inference, detached selection record, hard mask/index, oracle reward/environment |
| Deferred stochastic policy gradient | recomputed logits and selected log-probability in a training-mode learner | stored behavior record, hard mask/index, oracle reward/environment |
| Hierarchical proposer with AWR/REINFORCE | family logits and attempted-parameter log density | hard feasibility, reservoir inclusion, oracle reward |
| Surrogate pathwise proposal | bounded local 5-DoF parameters, differentiable pose constructor, surrogate score with respect to pose | hard projection semantics, collision/validity, final-shell selection, oracle |
| EVL in the MVP | downstream encoders may train on EVL tensors | EVL model and persisted root features |
| Persistence/publication | nothing | immutable shards, checkpoint serialization, hashes, manifests |

Target-network values and Bellman targets are detached. No gradient crosses GT
mesh rendering, discrete pixel/face hits, crop membership, voxelization,
nearest-surface assignment, hard validity, or replay storage.

## Scenario stress test

### Normal

A V1 observed target, 60-row finite candidate table, and `H=3` actor prefix are
scored by a frozen inference bundle. The episode prepares one bound decision
context, queries the hard oracle, commits one selected transition, and the
collector writes a new immutable training shard bound to the behavior bundle.
A later training phase reads that shard plus prior immutable stores and emits a
new bundle.

Expected: identical actor tensors with or without oracle evaluation, exact
candidate identity, no serving-model mutation during collection, and held-out
evaluation on untouched scenes.

### Boundary

Exactly one action is valid and the successor has no supported action, or the
episode is at the last budget step.

Expected: masked selection chooses the only valid row, bootstrap is zero,
terminal/no-successor semantics are explicit, and no NaN/invalid row reaches a
masked maximum.

### Failure

The oracle throws after rendering but before selected evidence is validated, a
checkpoint hash does not match the actor contract, or a learned proposer
collapses onto one family.

Expected: the episode state is unchanged, no partial transition is persisted,
the bundle is rejected before inference, and fixed anchors/family floors
keep the proposer from silently replacing the canonical support.

## Decisions frozen for the PRD

1. Implement the M5 finite-candidate scorer and inference bundle before online
   collection or a learned proposer.
2. Keep EVL frozen; consume the existing persisted root carrier.
3. Keep one fixed maximum horizon per learning/checkpoint contract and use
   `horizon_remaining` as state input; do not add a separate requested-horizon
   API in the MVP.
4. Use round-based online learning with dense-valid supervision only: frozen
   behavior bundle -> immutable training shard -> bounded fitted-Q
   retraining -> new immutable inference bundle. Sparse oracle-query modes do
   not enter this learning contract.
5. Do not introduce a mutable global replay buffer or a global "current model"
   pointer in the MVP.
6. Use an identity-bound stateful episode facade over the existing replay
   transition kernel. One prepared decision context binds actor observation,
   candidate table, episode, state, and table hashes before evaluation/commit.
7. Keep the hierarchical 5-DoF proposer as a later work package that emits the
   existing candidate-table contract and retains fixed anchors.
8. Treat pathwise surrogate refinement and a soft oracle as optional, separately
   named experiments after the hard-oracle selector/proposer gates.

## Assumptions and deferred decisions

Assumptions:

- existing immutable rollout/Q_H readers remain the training source;
- the first online learner is synchronous and single-policy-generation;
- the first production scorer targets `qh_cf0_v1` and V1 observed targets;
- selected CF-GT depth remains a privileged comparison profile, not the
  deployable default.

Deferred:

- asynchronous collectors and bounded checkpoint staleness;
- a mutable replay service;
- subset/selected-only offline objectives and same-step policy-gradient updates;
- trainable EVL or a second backbone;
- requested-horizon versus separate per-horizon model families;
- a derived actor-visible `DynamicSceneState` after issue #89;
- end-to-end soft-oracle differentiation;
- real-device dynamics or simulator-backed continuous control.
