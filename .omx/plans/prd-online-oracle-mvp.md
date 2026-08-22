---
kind: prd
status: locally-approved-receipt-blocked
slug: online-oracle-mvp
baseline: a121cd821f7748f979c2cddf0f7c3af0e0b6a5a7
ralplan_mode: deliberate
---

# PRD: online-capable oracle and hierarchical pose-policy MVP

## Goal

Deliver a minimal, owner-local path from existing finite-candidate rollout
evidence to a persisted target-conditioned multi-step value model, reproducible
online-discrete training rounds, and a later hierarchical bounded 5-DoF
proposal actor. The implementation must keep actor evidence, hard-oracle
supervision, live gradients, and immutable persistence structurally separate.

## Success criteria

The full requested system is successful when all of the following are true:

1. A production `TargetFiniteHorizonScorer` consumes the existing batched
   `QhActorTensors` contract and emits one continuous value per candidate row.
2. The scorer can be trained through the existing `QhLightningModule`, saved
   with exact scorer/actor/learning/EVL/target/candidate identities, restored on
   another process, and used in inference mode with identical masked rankings.
3. A presentation-free oracle episode reproduces current dense target-RRI
   rollout semantics, supports dense/subset/selected-only evaluation queries,
   commits selected transitions atomically through bound decision contexts,
   and independently evaluates endpoints. Only dense-valid labels enter the
   MVP learning contract.
4. A concrete Q_H score Adapter drives the existing replay selection contract
   and persists only detached behavior diagnostics. No autograd graph crosses
   the immutable round boundary.
5. An online training round freezes one behavior bundle, collects only on
   training scenes, writes a new immutable rollout shard with exact behavior
   provenance, retrains from immutable snapshots, and produces a new immutable
   bundle without mutating the policy used for that round.
6. A hierarchical actor can sample a semantic family and bounded local
   `(dx,dy,dz,dyaw,dpitch)` parameters while retaining fixed anchors, pass every
   attempted pose through existing hard feasibility/final-shell logic, and let
   the finite-horizon scorer rank the resulting candidate table.
7. Every scientific comparison uses the canonical hard oracle, matched
   candidate/action/budget/query contracts, untouched scene-level evaluation,
   and exact resource/query accounting.
8. No implementation or artifact promotes RQ5/RQ6 evidence before the M5/M6
   gates in the active thesis are satisfied.

## Non-goals

- No direct end-to-end gradient through the current hard renderer/RRI chain.
- No generic simulator, RL framework, model registry, replay service, or
  dashboard control plane.
- No trainable EVL in the MVP.
- No mutable global serving pointer or asynchronous collector fleet in the MVP.
- No subset/selected-only fitted-Q objective or same-step policy-gradient update
  in the MVP.
- No use of GT target geometry, association outcome, rendered candidate depth,
  or target crop as a `qh_cf0_v1` actor input.
- No replacement of canonical hard RRI by a learned or soft surrogate.
- No thesis claim that online or hierarchical policies improve performance
  until paired held-out evidence exists.

## RALPLAN-DR summary

### Principles

1. Preserve actor/oracle, training/inference, and transition/persistence
   separation in types and identities.
2. Deepen existing owners and share one replay transition kernel before adding
   a new facade, package, or abstraction.
3. Use dense-valid fitted-Q supervision, one immutable behavior bundle, and one
   immutable collection shard per MVP online round.
4. Keep hard validity separate from utility, label availability, and oracle
   query support.
5. Freeze and verify the M5 discrete kernel before M6 hierarchical proposal or
   pathwise refinement work.

### Decision drivers

1. Exact reuse of `QhActorTensors`, `QhLightningModule`, candidate tables, the
   replay transition owner, and immutable rollout stores.
2. Reproducible dense-valid learning and inference across processes without
   training-layer types leaking into replay.
3. Lowest owner-local implementation and scientific risk under the M5/M6 gates.

### Option A — one broad online learner/environment object

Pros:

- one convenient caller;
- initially little visible plumbing.

Cons:

- blends oracle caches, actor observations, replay writes, gradients,
  checkpoint publication, and training lifecycle;
- weak Locality and difficult failure recovery;
- a future proposer would depend on unrelated persistence/training methods.

Rejected.

### Option B — generic `rl` package with registries and interchangeable plugins

Pros:

- apparent flexibility for algorithms, backbones, and proposal policies.

Cons:

- creates a new truth surface before real alternative implementations exist;
- makes hash-bound scientific profiles depend on runtime registration;
- duplicates current owners and creates shallow forwarding APIs.

Rejected. Use closed local config unions only when a second concrete Adapter
exists.

### Option C — owner-local vertical slices around one episode seam

Pros:

- preserves current source order and testing owners;
- one scorer contract serves offline training and inference;
- one episode contract serves existing writer parity and online collection;
- immutable round boundaries make behavior provenance and rollback explicit;
- the hierarchical proposer can replace only candidate proposal behavior.

Cons:

- requires explicit composition at the pipeline boundary;
- online inference initially re-scores a short actor prefix instead of carrying
  a stateful model cache.

Chosen. The bounded `H` makes prefix inference acceptable for the MVP; model
state caching is a later measured optimization, not an interface prerequisite.

### Architecture synthesis

```text
immutable VIN/Q_H views
        |
        v
TargetFiniteHorizonScorer -- QhLightningModule --> immutable inference bundle
        |                                              |
        |                                 frozen behavior bundle per round
        v                                              v
pipeline-local Q_H score Adapter <--- decision context --- OracleNbvEpisode facade
        |                                      | prepare/evaluate/commit
        | detached selection record            | shared replay kernel + oracle
        v                                      v
detached policy record ----------------> immutable rollout shard
                                                   |
                                                   v
                                      next bounded training round

Later:
HierarchicalCandidateProposer -> existing CandidateSamplingResult -> Q_H ranker
Policy-gradient learner -> recompute log-probability from stored actor/action
```

## Public and internal interfaces

### 1. `TargetFiniteHorizonScorer`

Owner:

- new `aria_nbv/aria_nbv/vin/models/target_finite_horizon.py`;
- export only through `aria_nbv/aria_nbv/vin/models/__init__.py` after the
  concrete implementation is stable.

Interface:

```python
class TargetFiniteHorizonScorer(nn.Module):
    def forward(self, actor: QhActorTensors) -> Tensor:
        """Return Tensor[\"B S N\", float] aligned with action_mask."""
```

Configuration:

```python
class TargetFiniteHorizonScorerConfig(TargetConfig[TargetFiniteHorizonScorer]):
    hidden_dim: int
    pose_encoder: R6dLffPoseEncoderConfig
    scene_channels: tuple[str, ...]
    attention_heads: int
    dropout: float
    max_horizon: int
    experiment_profile: Literal["qh_cf0_v1"]

    @property
    def target_type(self) -> type[TargetFiniteHorizonScorer]: ...

    def setup_target(self) -> TargetFiniteHorizonScorer: ...
```

MVP internal structure:

1. encode persisted root EVL evidence and semidense context once per chain;
2. encode actor-visible target pose/extents;
3. encode each root-relative candidate pose through existing pose utilities;
4. encode causal selected-pose history and remaining budget;
5. combine state/target/history/budget context with candidate queries through a
   small candidate-to-state attention block;
6. emit one continuous root-gain return estimate per row;
7. validate output shape and finite values only on admitted rows.

Required invariants:

- candidate-row permutation equivariance;
- invalid/padded-row isolation;
- no candidate index embedding;
- no `QhSupervision` or `QhAudit` argument;
- fixed maximum horizon bound to config/checkpoint, with
  `horizon_remaining` as actor state;
- no CORAL/ordinal output in the Q_H path;
- avoid an unnecessary candidate-pose detach in the model path, but treat input
  pose gradients as a non-blocking compatibility probe until WP8 makes them a
  required pathwise-refinement gate.

The first implementation should reuse existing VIN pose encoding and compact
scene-field/pooling utilities. It should not subclass the one-step CORAL model
or add an independent generic scorer protocol: the injected `nn.Module` seam is
already executable.

### 2. Q_H experiment and immutable inference bundle

Owner:

- new `aria_nbv/aria_nbv/lightning/qh_experiment.py` for composition;
- minimal metadata hooks in `lightning/qh_module.py` only where Lightning must
  persist/restore optimizer and target-network state.

Interface:

```python
@dataclass(frozen=True, slots=True)
class QhInferenceBundleRef:
    bundle_path: Path
    schema_version: str
    manifest_sha256: str

class QhExperimentConfig(TargetConfig["QhExperiment"]):
    scorer: TargetFiniteHorizonScorerConfig
    module: QhLightningModuleConfig
    batch_size: int
    num_workers: int
    pin_memory: bool
    persistent_workers: bool

    @property
    def target_type(self) -> type["QhExperiment"]: ...

    def setup_target(self) -> "QhExperiment": ...

@dataclass(frozen=True, slots=True)
class QhCheckpointSelectionSpec:
    monitor: Literal["val/loss"] = "val/loss"
    mode: Literal["min"] = "min"
    tie_break: Literal["earliest_optimizer_update"] = (
        "earliest_optimizer_update"
    )

@dataclass(frozen=True, slots=True)
class QhFitRequest:
    train: QhDatasetConfig
    validation: QhDatasetConfig
    test: QhDatasetConfig
    resume_from: QhInferenceBundleRef | None
    checkpoint_selection: QhCheckpointSelectionSpec
    seed: int
    output_bundle_dir: Path

@dataclass(frozen=True, slots=True)
class QhFitResult:
    bundle: QhInferenceBundleRef
    training_receipt_path: Path
    training_receipt_sha256: str
    held_out_selection_receipt_path: Path
    held_out_selection_receipt_sha256: str

class QhExperiment:
    def fit(self, request: QhFitRequest) -> QhFitResult: ...
    @classmethod
    def load_for_inference(
        cls, ref: QhInferenceBundleRef, *, device: torch.device | str
    ) -> TargetFiniteHorizonScorer: ...
```

The experiment owns construction and reconstruction of the scorer, module,
DataModule, callbacks, and resolved artifacts. Each `QhDatasetConfig` binds an
ordered tuple of immutable rollout-store directories to one actor store; tuple
order remains the existing `QhChainKey.store_index` identity. The fit request
makes resume authority, checkpoint selection, seed, held-out manifests, and the
new immutable output directory explicit. An existing output directory is an
error. `QhLightningModule` remains scorer-independent. The public reference
exposes only bundle location, schema, and manifest hash; replay and oracle code
do not import Lightning types. The versioned bundle manifest includes:

- an internal Lightning resume checkpoint with online scorer, target scorer,
  optimizer/scheduler, optimizer-update count, and trainer state;
- an inference scorer state/config independent of the trainer object layout;
- resolved scorer config;
- exact actor/learning/geometry/candidate/target/EVL contracts and hashes;
- implementation revision and dependency identity;
- canonical train/validation/test dataset configs, ordered input-store hashes,
  resume-bundle identity, seed, and output identity;
- held-out validation receipt used to choose the checkpoint.

Inference loading must verify the manifest before opening payloads, reconstruct
the scorer from the closed config, load weights strictly, validate every
contract before scoring, move to the requested device, call `eval()`, and use
inference mode at the score Adapter boundary.

Do not add a global model registry or a mutable `current.json` pointer. Online
round manifests name an immutable bundle ref and persist only the behavior
bundle/model/config hashes required for provenance.

Both configs follow the repository `TargetConfig` config-as-factory convention:
`target_type` names the concrete owner and `setup_target()` constructs it
without executing training. `QhExperiment.fit(request)` remains the only run
entrypoint.

`QhCheckpointSelectionSpec` is deliberately closed in V1: the existing
`QhLightningModule` validation aggregate `val/loss` is minimized and an exact
tie selects the earliest optimizer update. A new metric, alias, or tie-break
rule is a new manifest mode, not a free-form monitor string.

### 2a. Dense-valid fitted-Q admission

Owners:

- extend `aria_nbv/aria_nbv/rollouts/qh_reader.py::QhDataContract`;
- extend `aria_nbv/aria_nbv/lightning/qh_datamodule.py::QhLearningContract`;
- enforce the tensor invariant in Q_H materialization/batching admission.

Minimal contract additions:

```python
QhOracleQueryMode = Literal["legacy_unspecified", "dense_valid"]
QhLabelSupportSemantics = Literal[
    "subset_of_action_v1",
    "equals_action_on_realized_steps_v1",
]

@dataclass(frozen=True, slots=True)
class QhDataContract:
    # existing fields remain
    oracle_query_mode: QhOracleQueryMode = "legacy_unspecified"
    label_support_semantics: QhLabelSupportSemantics = "subset_of_action_v1"

@dataclass(frozen=True, slots=True)
class QhLearningContract:
    # existing fields remain
    objective_profile: Literal[
        "legacy_selected_rows_v1",
        "qh_dense_valid_fitted_q_v1",
    ] = "legacy_selected_rows_v1"
```

The deployable online MVP requires the triple `dense_valid`,
`equals_action_on_realized_steps_v1`, and `qh_dense_valid_fitted_q_v1`. Metadata
is necessary but not sufficient. The DataModule selects a profile-aware
collation path. After ordinary width/step padding, the dense-only path
canonicalizes both supervision tensors and then proves:

```python
expected = actor.action_mask & actor.step_mask[..., None]
candidate_reward = torch.where(
    expected,
    supervision.candidate_reward,
    torch.full_like(supervision.candidate_reward, float("nan")),
)
one_step_target_rri = torch.where(
    expected,
    supervision.one_step_target_rri,
    torch.full_like(supervision.one_step_target_rri, float("nan")),
)
torch.equal(supervision.label_mask, expected)
torch.isfinite(candidate_reward[expected]).all()
torch.isfinite(one_step_target_rri[expected]).all()
torch.isnan(candidate_reward[~expected]).all()
torch.isnan(one_step_target_rri[~expected]).all()
```

This canonicalization occurs only for `qh_dense_valid_fitted_q_v1`; it covers
candidate-width padding, step padding, and hard-invalid realized rows without
changing the current finite-zero `candidate_reward` padding used by legacy
collation. Any missing label on an actor-valid realized row, nonfinite value on
support, mixed contract, or metadata/tensor disagreement fails during dataset/
batch admission before the first scorer forward or optimizer step. Existing
legacy/subset stores remain readable only under their existing objective
identity; they cannot be pooled into or exported as the deployable dense-valid
bundle. The manifest records this versioned legacy-to-dense identity change and
never implies learning-contract hash continuity.

### 3. Pipeline-local Q_H score Adapter over replay policy

Owner:

- private composition inside new
  `aria_nbv/aria_nbv/oracle/pipelines/online_qh.py`;
- keep the generic score callback, `CandidateScores`, selection records, and
  built-in enum policies in `rollouts/replay` unchanged.

Interface:

```python
class _QhCandidateScoreAdapter:
    def __init__(
        self,
        scorer: TargetFiniteHorizonScorer,
        *,
        behavior_model_hash: str,
        behavior_config_hash: str,
    ) -> None: ...

    def __call__(
        self,
        context: OracleDecisionContext,
    ) -> CandidateScores: ...
```

The online-Q_H pipeline constructs this private concrete Adapter from an
inference-loaded scorer and injects it into the existing generic replay score
callback/selection path. It converts only the identity-bound context's actor
view, executes in inference mode, validates alignment with the candidate
table/action mask, and returns existing `CandidateScores`. Existing replay code
performs deterministic or keyed stochastic selection and emits the existing
detached selection/step records. Replay never imports oracle or Q_H pipeline
types; cross-owner composition points from `oracle.pipelines` into replay.

No new one-implementation policy Protocol or stored-policy DTO is introduced.
Random-valid and hard-oracle baselines retain their existing policy vocabulary.
If a later policy-gradient algorithm is authorized, a separate training-mode
learner recomputes logits/log probability from stored actor/action data; it does
not persist or resurrect autograd graphs from collection.

### 4. `OracleNbvEnvironment` and `OracleNbvEpisode`

Owner:

- new `aria_nbv/aria_nbv/oracle/environment.py`;
- extract one owner-internal replay step kernel under
  `aria_nbv/aria_nbv/rollouts/replay/` from the current engine;
- reuse exact scoring/rendering/evidence owners rather than copying algorithms.

Entry interface:

```python
@dataclass(frozen=True, slots=True)
class OracleEpisodeRequest:
    sample: VinOfflineSample
    target: OracleTargetTask
    candidate_config: CandidateViewGeneratorConfig | CandidateMixtureViewGeneratorConfig
    replay_policy: RolloutPolicySpec
    target_scorer: TargetRriScorerConfig
    successor_observation_mode: QhSelectedObservationProtocol
    source_manifest_hash: str
    split_manifest_hash: str

@dataclass(frozen=True, slots=True)
class OracleDecisionContext:
    episode_id: str
    state_hash: str
    table_hash: str
    actor_hash: str
    trajectory: CounterfactualTrajectory
    candidates: CandidateSamplingResult
    actor: QhActorTensors

    def to_qh_actor(self) -> QhActorTensors: ...

@dataclass(frozen=True, slots=True)
class OracleQuery:
    mode: Literal["dense_valid", "subset", "selected_only"]
    shell_indices: tuple[int, ...] = ()

@dataclass(frozen=True, slots=True)
class OracleEndpointEvaluation:
    episode_id: str
    state_hash: str
    acquisitions: int
    terminal: bool
    terminal_reason: str
    target_rri: float
    root_gain: float
    oracle_query_count: int

class OracleNbvEnvironment:
    def open(self, request: OracleEpisodeRequest) -> OracleNbvEpisode: ...

class OracleNbvEpisode:
    def prepare_decision(
        self, candidates: CandidateSamplingResult | None = None
    ) -> OracleDecisionContext: ...
    def evaluate(
        self,
        context: OracleDecisionContext,
        query: OracleQuery,
    ) -> OracleCandidateEvaluation: ...
    def commit(
        self,
        context: OracleDecisionContext,
        evaluation: OracleCandidateEvaluation,
        selected_shell_index: int,
    ) -> EvaluatedRolloutStep: ...
    def endpoint(self) -> OracleEndpointEvaluation: ...
    def close(self) -> None: ...
```

These are the only new public episode DTOs: request, bound decision context,
query, and endpoint. `CandidateSamplingResult`, `CounterfactualTrajectory`,
`CounterfactualStepResult`, `CandidateScores`, `OracleCandidateEvaluation`, and
`EvaluatedRolloutStep` are reused unchanged. `prepare_decision(None)` asks the
shared replay kernel to regenerate the table; passing a materialized table is
reserved for the later proposer and must match the current reference pose and
candidate contract.

The runtime request is not serialized with its rich sample/mesh attachments.
`episode_id` is the stable hash of source sample/shard identity, source and
split manifest hashes, resolved target identity, root pose, candidate/replay/
scorer config hashes, and successor-observation mode. `state_hash` hashes the
root, selected `CounterfactualStepResult` prefix, remaining budget, and episode
identity. `table_hash` hashes the serialized `CandidateSamplingResult` plus the
state hash. `actor_hash` hashes the actor-safe tensor projection and profile
identity. `to_qh_actor()` must reproduce it exactly on the deterministic CPU
fixture.

All three hashes use one canonical detached CPU representation: repository
typed-payload serialization, explicit dtype/shape metadata, contiguous tensor
bytes, normalized config values, and stable field order. Device placement and
autograd flags never enter identity. CPU/GPU construction of the same admitted
facts must hash equally, and a fresh process must reproduce the same hashes.

The frozen context is intentionally a shallow runtime envelope around existing
mutable dataclasses. Immediately before `evaluate` and `commit`, the episode
recomputes state, table, and actor hashes from the nested trajectory,
`CandidateSamplingResult`, and actor tensors and compares them with the bound
values. Any in-place nested mutation is a stale-context error before oracle
work or state mutation. The binder never relies on Python object identity alone.

`OracleQuery` validation is closed: `dense_valid` requires empty
`shell_indices` and evaluates every hard-valid shell row; `subset` requires a
nonempty ordered unique valid subset; `selected_only` requires exactly one
valid shell row. Evaluation preserves compact-valid order and returns the
existing `OracleCandidateEvaluation`. `commit` returns the existing
`EvaluatedRolloutStep`, whose `CounterfactualStepResult` remains the replay/
writer transition owner. Endpoint fields are scalar, detached, JSON-safe, and
included in the round receipt under the endpoint contract hash.

`OracleNbvEnvironment.open()` is the only construction entrypoint. The episode
is a deep identity-bound facade that owns:

- immutable source/target/root identity;
- cached renderer, mesh, target crop, root error/evidence, and canonical fusion
  state under exact contract hashes;
- lifecycle and transaction admission around current replay state;
- explicit successor observation mode;
- transactional selected-state update;
- independent endpoint evaluation and cleanup.

The extracted replay kernel remains the single owner of pose/history/budget,
candidate regeneration, selected-action trajectory semantics, and deterministic
state transition. Both the existing offline engine and the oracle episode call
that kernel. The episode adds cache lifetime, hard-oracle evaluation, identity
binding, query budgets, transactional commit, and cleanup; it does not
reimplement the replay state machine.

It does not own:

- policy inference or optimizer state;
- rollout/Zarr persistence;
- campaign skip/resume or shard promotion;
- UI, CLI, scheduling, or worker pools;
- mutable VIN sources.

`OracleDecisionContext` immutably binds actor-safe observation data, the exact
candidate table, `episode_id`, `state_hash`, and `table_hash`.
`context.to_qh_actor()` is the only one-way Adapter to the existing
`QhActorTensors` chain-prefix contract. It cannot expose candidate labels,
target errors, rendered depth, GT association fields, or oracle caches.
`evaluate` and `commit` reject stale, foreign-episode, cross-state,
cross-table, or already-consumed contexts before any mutation.

The environment supports `DENSE_VALID`, `SUBSET`, and `SELECTED_ONLY` query
modes for explicit compute/evaluation roles. Only `DENSE_VALID` is admitted to
the MVP Q_H learning contract. Query mode and label-support semantics enter the
data/learning contract hash; mixed-mode pooling fails closed. A coarse fidelity
is deferred until it has a separate metric and cache identity.

Step semantics are atomic. For one frozen state/table/action identity, a repeat
returns the same committed transition or a typed already-consumed error. Any
exception before validation leaves state unchanged. Cache identity includes
camera, renderer, crop, fusion, target-RRI, target protocol, and implementation
hashes.

The existing replay callback remains exactly:

```python
def score_candidates(
    candidates: CandidateSamplingResult,
    trajectory: CounterfactualTrajectory,
    step_index: int,
) -> CandidateScores:
    context = episode._bind_replay_decision(
        candidates=candidates,
        trajectory=trajectory,
        step_index=step_index,
    )
    return score_context(context)
```

Both `prepare_decision()` and this pipeline-local closure call the same private
context binder. `_bind_replay_decision` verifies current episode, trajectory
prefix, step index, reference pose, and candidate-table identity before
building actor tensors. The closure is created in `online_qh.py`; it is passed
to the unchanged `CounterfactualEvaluatorFn` seam and is not exported.

### 5. Online collection round

Owner:

- new `aria_nbv/aria_nbv/oracle/pipelines/online_qh.py`;
- keep `online_vin.py` as the one-step label-stream owner.

Interface:

```python
@dataclass(frozen=True, slots=True)
class OnlineQhRoundRequest:
    behavior_bundle: QhInferenceBundleRef
    training_population_manifest: Path
    acquisition_round: int
    proposal_policy_manifest_sha256: str
    selection_policy: RolloutPolicySpec
    oracle_query_budget: int
    query_mode: Literal["dense_valid"] = "dense_valid"

@dataclass(frozen=True, slots=True)
class OnlineQhRoundCounts:
    proposed: int
    valid: int
    queried: int
    labeled: int
    selected: int
    persisted: int
    rejected: int

@dataclass(frozen=True, slots=True)
class OnlineQhRoundResult:
    shard_dir: Path
    shard_manifest_sha256: str
    behavior_bundle_manifest_sha256: str
    proposal_policy_manifest_sha256: str
    oracle_query_policy_id: Literal["dense_valid_v1"]
    selected_action_policy_sha256: str
    round_receipt_path: Path
    round_receipt_sha256: str
    counts: OnlineQhRoundCounts

class OnlineQhCollector:
    def collect(self, request: OnlineQhRoundRequest) -> OnlineQhRoundResult: ...
```

The request and result are frozen and JSON-serializable except for the nested
existing config object, which is serialized canonically through repository
config utilities. The round receipt is the serialization owner for request,
counts, per-episode endpoint summaries, failure denominators, timing/resource
metrics, and the promoted shard/bundle hashes. It names proposal-policy
manifest, `dense_valid_v1` oracle-query policy, and selected-action-policy hash
as three separate provenance fields. Counters are explicit integers; none is
derived from another at read time. Shard promotion succeeds only after the
store validator and receipt hash pass.

The collector composes the environment, concrete Q_H score Adapter, existing
replay selection path, and immutable writer/campaign contracts. It is thin
orchestration. It must:

1. load and verify one immutable behavior bundle before the round;
2. use training scenes only and bind to #81 population/acquisition manifests;
3. keep proposal policy, oracle-query policy, and selected-action policy as
   separate provenance;
4. collect dense-valid labels under a fixed successor observation mode and
   query budget; sparse modes fail learning-contract admission;
5. write a new immutable shard, never append into prior stores;
6. bind every transition to behavior model/config hashes and round identity;
7. close episodes safely and report proposed, valid, queried, labeled,
   selected, persisted, rejected, resource, and timing counts;
8. return the validated immutable shard reference.

A subsequent `QhExperiment.fit()` reads an explicit tuple of prior and new
shards. It may resume trainer state from the bundle's internal resume artifact
but emits a new immutable bundle. No collection worker sees updated weights
during its round.

### 6. Hierarchical bounded 5-DoF proposer

Owner:

- new `aria_nbv/aria_nbv/pose_generation/hierarchical_proposer.py` only after
  the finite-candidate selector gate;
- integrate through existing candidate generation, pruning, and
  `CandidateSamplingResult` owners.

Interface:

```python
@dataclass(frozen=True, slots=True)
class CandidateProposalState:
    root_pose_world: PoseTW
    target_pose_relative_root: PoseTW
    target_extents: Tensor
    root_scene_features: Tensor
    root_scene_mask: Tensor
    history_pose_relative_root: PoseTW
    history_mask: Tensor
    horizon_remaining: Tensor
    actor_state_contract_hash: str

class HierarchicalCandidateProposer(nn.Module):
    def propose(
        self,
        state: CandidateProposalState,
        *,
        generator: torch.Generator,
    ) -> CandidateProposalAttempt: ...

@dataclass(slots=True)
class CandidateProposalAttempt:
    family_logits: Tensor
    family_index: Tensor
    local_parameters_5d: Tensor
    attempted_log_probability: Tensor
    generator_key: int
    proposer_manifest_sha256: str

class HierarchicalProposalMaterializer:
    def materialize(
        self,
        attempt: CandidateProposalAttempt,
        *,
        anchors: CandidateSamplingResult,
    ) -> CandidateSamplingResult: ...
```

`CandidateProposalState` is actor-safe and candidate-free. Its shapes are
`root_pose_world[12]`, `target_pose_relative_root[12]`, `target_extents[3]`,
`root_scene_features[P,C]`, `root_scene_mask[P]`, history pose `[H,12]`, history
mask `[H]`, and scalar `horizon_remaining`. A pipeline-local Adapter projects
the admitted Q_H root/history carrier into this DTO; `pose_generation` does not
import oracle or Q_H DTOs. Serialization stores detached CPU tensors plus the
actor-state contract hash. A distinct feature schema or backbone changes that
hash and the proposer manifest.

One `propose()` call emits exactly `K=config.num_attempts` attempts over
`F=config.num_families`: shared `family_logits[F]` are float32, sampled
`family_index[K]` is int64, `local_parameters_5d[K,5]` is float32 in the
declared bounded local frame, and `attempted_log_probability[K]` is float32.
All tensors share one device; the three float tensors may carry gradients in a
training-mode proposer call, while family indices, generator key, and manifest
hash never do. Leading dimensions must agree and every family index must be in
`[0,F)`. `CandidateProposalAttempt` is a runtime-only gradient carrier: it has
no serializer and cannot enter a writer directly.

`HierarchicalProposalMaterializer` detaches attempts before hard pose
construction and projects their provenance into the existing full-shell
`CandidateSamplingResult.extras` keys:

- `is_learned_attempt: Tensor["N", bool]`;
- `attempt_family_id: Tensor["N", int64]`, using `-1` for anchors;
- `attempt_local_parameters_5d: Tensor["N 5", float32]`, using NaN for anchors;
- `attempt_log_probability: Tensor["N", float32]`, using NaN for anchors;
- `attempt_generator_key: Tensor["N", int64]`, using `-1` for anchors; and
- constant `proposer_manifest_sha256: str`.

The existing `CandidateSamplingResult.to_serializable()/from_serializable()`
path owns CPU projection and round-trip storage. Tensor rows stay aligned with
the full shell before pruning; hard masks and compact-valid indices remain
separate. The candidate-table hash includes these extras, so changed attempt
provenance cannot alias the same realized table.

The stochastic action is the categorical family and bounded local parameters,
not an unspecified density over world-frame `PoseTW`. The deterministic
constructor maps `(family, local_parameters_5d)` to physical poses with fixed
roll. Persist the attempted parameter-space log probability and separately
record hard-feasibility/final-shell inclusion.

The learned attempt contains only differentiable parameter-space facts. The
owner-local materializer combines attempts with a nonzero fraction of keyed
fixed anchors, constructs poses, applies existing hard pruning/reservoir rules,
and emits the ordinary full-shell result. The first training path is
AWR/elite-weighted supervised proposal learning while the Q_H selector is
frozen. Alternate frozen selector and proposer phases until support and
objective drift are understood. A score-function proposer is deferred to its
own training-mode work package.

The realized candidate table is ranked through the pipeline-local Q_H score
Adapter and the existing replay selection path; the proposer does not call the
oracle or change Q_H training semantics.

## Differentiability contract

### Required now

- `TargetFiniteHorizonScorer` parameters through selected-action Huber loss.
- online-scorer parameters only; target-network values and Bellman targets are
  detached;
- collection and selection execute in inference mode and persist detached
  diagnostics only.

### Required by the later hierarchical AWR work package

- proposer family logits and bounded local-parameter distribution during the
  separate training-mode likelihood/AWR update;
- no gradient through hard pose materialization, anchors, feasibility, final
  inclusion, or oracle reward.

### Explicitly detached/hard

- persisted EVL root fields and the EVL model in the MVP;
- `QhActorTensors` materialization and immutable replay readers;
- hard candidate generation, collision, feasibility, reason codes, masks, and
  reservoir/final-shell inclusion;
- masked argmax and sampled discrete action identity;
- hard renderer, z-buffer hit identities, backprojection masks, target crop,
  point fusion, voxelization, nearest-surface error, and RRI;
- oracle transition, endpoint evaluation, checkpoint serialization, and shard
  persistence;
- target-network evaluation and Bellman target.

### Deferred pathwise refinement

A future `LocalPoseRefiner` may optimize the same scorer as an actor-visible
surrogate with respect to bounded local 5-DoF parameters. It requires:

- an explicit scorer input-gradient compatibility gate that is non-blocking for
  WP1 but mandatory here;
- differentiable local pose construction;
- finite-difference agreement on the surrogate;
- local hard-oracle directional probes;
- OOD/support-aware trust regions;
- hard projection, feasibility, deduplication, and oracle re-evaluation after
  gradient steps;
- matched derivative-free controls such as random perturbation and bounded CEM.

A separate deferred score-function learner may recompute selected/proposal log
probabilities from stored actor/action data in training mode. It never persists
live collection graphs and has a distinct objective/manifest identity.

It is not part of the MVP kernel and must have a separate manifest mode.

## Work packages and dependency gates

### WP0a — mandatory functional golden parity

Dependencies: Graphify fresh; live issues inspected.

Deliver:

- deterministic CPU fixture and representative CUDA sample identity for the
  existing replay/oracle path;
- candidate, mask, transition, reward, endpoint, and stored-row golden outputs;
- field-specific equality/tolerance rules and a parity command independent of
  the future environment implementation;
- exact status ledger for #54, #68-#73, #79-#82, and #89;
- refresh `.omx/specs/online-oracle-issue-acceptance.md`, the concrete #74/#75
  acceptance-item ledger, with live issue revision/time and one of `compatible`,
  `needs_issue_amendment`, or `needs_follow_up_issue` for every row; in
  particular, resolve reset/step and live-`PolicyDecision` wording against the
  chosen `open/prepare_decision/evaluate/commit` and detached-inference
  contracts;
- explicit distinction between code-readiness tests and scientific promotion.

Exit: the functional golden fixture is reproducible. This is mandatory before
environment/replay extraction and cannot pass as "measurement blocked." WP4 or
WP5 completion must not close #74/#75 unless their broader live acceptance is
amended or a follow-up issue explicitly owns the deferred behavior.

### WP0b — measured performance evaluator

Dependencies: WP0a; one executable performance candidate; exactly one active
autoresearch/autoresearch-goal mission.

Deliver a frozen evaluator with baseline command, data hashes, resource
metrics, device synchronization, repeats, sample artifact, budget, and
keep/discard rule before the measured sidecar runs.

Exit: one valid baseline row exists. Planning and functional implementation may
continue while WP0b is blocked, but no performance candidate or claim may be
accepted without it.

### WP1 — production finite-horizon scorer

Deliver `TargetFiniteHorizonScorer`, config, owner-local exports, and focused
unit tests. Preserve `QhLightningModule` injection and existing views.

Exit: shape, mask, permutation, scorer-parameter gradient, leakage, and
deterministic evaluation tests pass on CPU fixtures; a bounded CUDA smoke passes
when available. Candidate-pose input gradients are non-blocking until WP8.

### WP2 — Q_H experiment, persistence, and inference

Deliver strict scorer construction, versioned inference-bundle manifest,
complete identity, resume, and inference loading. Use one immutable public
bundle reference that does not expose a Lightning type to replay.

Exit: train -> save -> new process load -> masked ranking parity; stale/missing
contract rejection; optimizer/target state resume parity; canonical shard order
and resume identity deterministically change the bundle manifest.

### WP3 — offline M5 policy evaluation

Train and evaluate on existing immutable stores. Compare random-valid,
one-step oracle greedy, one-step learned scoring, bounded oracle lookahead, and
finite-horizon Q_H under matched support and budget.

Exit: exact support/coverage report and paired held-out result. If oracle
headroom is nonpositive or candidate support is inadequate, stop RQ5/RQ6
promotion and fix prerequisite issues instead.

### WP4 — oracle environment extraction

Extract one shared replay step/trajectory kernel, then deliver the identity-
bound environment/episode facade, decision context, explicit query modes, cache
identities, transactional commit, endpoint, and cleanup. Adapt existing offline
rollout generation and the environment to the same kernel only after WP0a.

Exit: dense numerical/store parity, stale/cross-context rejection,
subset/selected lineage, incremental/full state parity, exception atomicity,
restart determinism, and bounded resource evidence.

### WP5 — concrete Q_H score Adapter and online round

Deliver inference-loaded Q_H scores through a pipeline-local Adapter into the
existing replay selection and
detached record contracts, a frozen-bundle dense-valid collector, immutable
per-round shard, and bounded fitted-Q retraining. Bind query mode/label support
to data and learning contracts and reject sparse/mixed training shards.

Exit: train-only collection, unchanged held-out manifests, exact behavior/query/
proposal provenance, bundle-generation isolation, and online-versus-offline
paired endpoint evaluation. This is the minimum online-capable oracle MVP.

### WP6 — hierarchical proposer controls

Dependencies: M5 and WP5 gates pass; #73 support benchmark is available.

Deliver typed family/5-DoF action, separate attempt/materializer, fixed anchors,
bounded black-box CEM control, attempted-density provenance, AWR/elite training,
and alternating frozen phases.

Exit: no collapse, bounded parameters, hard-feasibility survival, proposal
regret/support evidence, and downstream matched-table selector evaluation.

### WP7 — integrate hierarchical actor with Q_H ranking

Compose proposer -> ordinary candidate table -> Q_H score Adapter -> existing
replay selection -> hard-oracle episode. Compare against the fixed candidate
profile under matched total proposal, oracle-query, acquisition, runtime, and
endpoint budgets.

Exit: reproducible full loop with exact bundle/proposal provenance. Any
claim remains M6 bridge evidence.

### WP8 — optional surrogate local refinement

Dependencies: #77 gates and WP7 evidence.

Deliver only as a separate experiment with gradient validation, trust region,
hard feasibility/oracle validation, and derivative-free controls.

Exit: hard-oracle candidate-set and endpoint improvement under matched budgets;
otherwise discard without changing canonical RRI or the MVP interfaces.

## Binding issue and scientific gate matrix

| Owner | Work package(s) | Executable gate | Promotion gate |
| --- | --- | --- | --- |
| #67 | WP3, WP6-WP8 | phase separation remains explicit | no learned proposer before finite-support selector evidence |
| #54, #68-#73 | WP0a, WP3, WP6-WP7 | family-collapse and candidate-support evidence consumed, not duplicated | canonical challenger support and proposal benchmark accepted |
| #74 | WP0a, WP4-WP5 | environment parity, identity-bound commit, cache and cleanup tests | no environment claim beyond frozen ASE oracle contract |
| #75 | WP1-WP5 | production scorer, bundle, dense-valid objective, detached behavior records | M5 paired held-out Q_H result before RQ5 |
| #76 | WP6-WP7 | bounded typed family/5-DoF attempt, materializer, anchors, provenance | M6 bridge only after M5 and proposal benchmark |
| #77 | WP8 | gradient mode, input-gradient, finite-difference, OOD, hard-oracle controls | separately named ablation; never canonical RRI |
| #79/#80 | WP0a, WP3-WP8 | camera/depth and RRI contracts bind every cache/store/bundle | block scientific promotion until fidelity gates pass |
| #81 | WP3, WP5-WP8 | training acquisition and untouched evaluation manifests are disjoint | primary analysis remains scene-paired on frozen population |
| #82 | WP1-WP8 | V1 actor descriptor and privileged GT evaluation identities remain separate | deployable bundle rejects V0/GT actor inputs |
| #89 | deferred | raw causal prefix remains distinct; no substitute derived state owner | any DynamicSceneState is a separate named experiment |

If a live issue state or acceptance criterion changes before execution, WP0a
must refresh this matrix against the exact issue and source owners. A changed
issue does not silently rewrite an accepted contract.

## Architecture decision record

### Decision

Use dense-valid, round-based fitted Q learning over immutable shards and
inference bundles. Expose an identity-bound oracle episode facade over one
shared replay transition kernel. Keep hierarchical proposal and pathwise
refinement behind M5/M6 gates.

### Drivers

1. Preserve actor/oracle and replay/pipeline dependency direction.
2. Make the fitted-Q support, immutable inputs, resume authority, and behavior
   bundle identity reproducible across processes.
3. Reuse current Q_H, replay, candidate, and hard-oracle owners with the fewest
   new public interfaces.

### Alternatives considered

- one broad online learner/environment object;
- a generic `rl` package or registry;
- a second oracle/replay state machine;
- replay-owned Q_H policy/context types;
- mutable serving/replay state or sparse-query Q_H under the dense-valid
  objective.

### Why chosen

The selected vertical slices deepen existing owners: Lightning retains
optimization, VIN owns the scorer, replay retains generic transition/selection
semantics, `oracle.pipelines` owns cross-owner composition, and immutable
stores/bundles make each training round auditable and reversible. Bound decision
contexts close stale-table failure modes without reversing package dependencies.

### Consequences

- one extra explicit composition layer exists in `online_qh.py`;
- online collection is synchronous and bundle-frozen per round;
- inference initially recomputes a bounded actor prefix;
- sparse oracle queries cannot share the MVP fitted-Q identity;
- replay stays independent of oracle and Lightning packages.

### Follow-ups

- freeze WP0a before transition-kernel extraction;
- implement and validate WP1/WP2 before online collection;
- activate WP0b only inside one evaluator-frozen measured mission;
- revisit hierarchical proposal only after M5 and issue-owned support gates;
- revisit pathwise candidate-pose gradients only in WP8.

### Status

Locally approved by Architect iteration 6 and Critic iteration 3. Execution
remains no-go pending an official host-issued consensus receipt verified through
a documented non-user-mintable host surface.

## PR and commit strategy

The branch `codex/online-oracle-mvp` was created from live `origin/main` before
implementation. Publish an early draft planning PR containing only the accepted
context, PRD, test spec, reviews, and blocked/verified handoff. After a verified
official Ralplan receipt opens execution, keep reviewable rollback boundaries:

1. scorer and scorer tests;
2. experiment/inference bundle/resume;
3. environment extraction and parity;
4. policy/online collection round;
5. hierarchical proposer; and
6. optional refinement in a separate PR unless the accepted plan is amended.

Do not combine P0 oracle-fidelity fixes or candidate-support redesign with the
Q_H scorer commit. If those prerequisites require code, land their issue-owned
PRs first.

## Pre-mortem

| Failure | Earliest signal | Mitigation | Stop condition |
| --- | --- | --- | --- |
| Q_H appears good because target/GT data leaked | target-source dropout or actor/oracle dependency test changes ranking | type-separated views, dependency audit, V1-only main profile | any ordinary model input reaches GT crop/render/association outcome |
| Online improvement is only denser oracle supervision | query counts differ or dense labels enter one method only | persist query policy and match/report oracle budgets | comparison cannot be normalized or stratified by query budget |
| Environment extraction changes labels | fixture/GPU parity exceeds frozen tolerance | freeze evaluator before edits; reuse exact owners | numerical/store parity cannot be restored without changing canonical metric |
| Q_H exploits candidate family/provenance shortcuts | cross-profile or provenance-dropout performance collapses | dropout/ablation and matched candidate support | selected performance does not survive frozen challenger profile |
| Online rounds contaminate evaluation | scene/group ID appears in acquisition and holdout manifests | #81 manifest admission and scene-level checks | any validation/test episode enters aggregation |
| Inference bundle cannot be reconstructed | load needs caller-supplied hidden config or ranks differ | complete versioned manifest and strict loader | train/export/load/rank parity fails |
| Sparse labels silently change Q_H backup support | subset/selected-only shard is admitted or successor max support shrinks | dense-only MVP contract and query/label-support hashes | mixed/sparse shard reaches fitted-Q training |
| Decision context is stale or cross-composed | state/table hashes differ at evaluate/commit | identity-bound context and pre-mutation validation | foreign/stale context is accepted |
| Training/inference gradient modes are confused | inference-mode decision is expected to backpropagate | detached MVP collection and separate recomputation-based future learner | collection graph is persisted or required for update |
| Proposer collapses support | entropy/family survival/anchor fraction drops | fixed anchors, family floor, alternating phases | proposal benchmark regresses beyond frozen tolerance |
| Surrogate ascent worsens hard RRI | poor directional agreement or high degradation rate | OOD trust region and derivative-free controls | no matched-budget hard-oracle improvement |
| Scope bypasses M5 gates | online/proposer code precedes positive support/headroom evidence | work-package dependencies and separate PRs | requested thesis promotion lacks M5 receipt |

## Available agent types and future execution staffing

Only after a verified official host receipt. Suggested roster and reasoning:

- 1 `executor` at medium reasoning: one bounded owner-local implementation slice
  at a time;
- 1 `test-engineer` at medium reasoning: freeze evaluator/tests before each
  mutation-heavy slice;
- 1 `verifier` at high reasoning: independently validate bundle, parity, and
  provenance claims;
- 1 `code-reviewer` at high reasoning: final P0-P2 review of each PR-sized slice;
- 1 `architect` at xhigh reasoning only when a public interface or owner
  boundary changes;
- 1 `researcher` at high reasoning only for primary-source or current external
  API evidence;
- 1 `dependency-expert` at high reasoning only if a new package/SDK choice
  becomes necessary.

Use a persistent single-owner lane for WP1/WP2. Use coordinated parallel work
only after the contracts are frozen and file ownership is disjoint (for example,
environment parity tests versus scorer implementation). OMX Team is not the
default for the initial vertical slice.

### Requested future Goal-Mode handoff

After an official receipt, the user's requested execution lane is Ultragoal.
The durable goal graph should be:

1. Goal A: WP0a plus WP1 production scorer;
2. Goal B: WP2 inference bundle and offline M5 verification;
3. Goal C: WP4 shared replay kernel and oracle episode parity;
4. Goal D: WP5 dense-valid online round;
5. Goal E: WP6/WP7 hierarchical proposer only when the M5 and issue gates pass;
6. Goal F: WP8 only as an optional research goal.

Each goal must name its artifact/test exit and cannot mark a downstream goal
ready merely because code exists. WP0b becomes a measured-autoresearch sidecar
inside the first goal that has an executable performance candidate.

### Goal-Mode follow-up suggestions

- `$ultragoal` is the default future implementation ledger requested here; it
  owns sequential goal admission and durable completion evidence.
- `$autoresearch-goal` is appropriate only if a later task is reframed around a
  research deliverable and frozen evaluator, not as a substitute for WP1-WP5
  implementation.
- `$performance-goal` is appropriate only for a separately authorized WP0b
  latency/throughput/memory optimization mission after a functional candidate
  and evaluator exist.
- `$ultragoal` plus `$team` is appropriate for receipt-authorized, disjoint
  implementation lanes such as WP4; Team supplies coordinated execution
  evidence and Ultragoal remains the completion ledger.

### Team launch hint

Do not use Team for WP1/WP2. If WP4 reaches a receipt-authorized, contract-frozen
implementation state and an attached OMX tmux runtime is available, a possible
three-lane team is:

- executor: shared replay-kernel extraction;
- test-engineer: golden parity and stale-context fixtures;
- verifier: oracle cache/resource and store-equivalence evidence.

The leader retains integration and final verification. No worker edits the same
owner file concurrently, and implementation falls back to a single executor if
the runtime or host-authority checks fail.

Future receipt-authorized launch examples:

```bash
omx team 3:team-executor "Execute WP4 from .omx/plans/prd-online-oracle-mvp.md with disjoint kernel, parity-test, and verification lanes"
```

or `$team 3 "Execute receipt-authorized WP4 with disjoint owner paths and
return checkpoint-ready evidence to Ultragoal"` on the plugin surface.

Before Team shutdown, all assigned tasks must be terminal, WP0a parity and
focused owner tests must be read, no worker may still be writing, and the leader
must collect exact diff/test/artifact evidence. Ultragoal remains the durable
ledger owner: it checkpoints the resulting commit, bundle/store evidence,
review/verifier outcome, unresolved gaps, and downstream-goal readiness before
the next goal opens. Ralph is only a future explicit fallback for an
intentionally persistent single-owner verify/fix loop; it is not the default.

## Verification overview

The companion test specification is authoritative for proof. At each work
package:

1. state the exact claim;
2. run the narrowest test that proves it;
3. inspect output and immutable artifacts;
4. run owner-level lint/type/test checks;
5. obtain independent review before publication; and
6. keep unsupported scientific claims explicitly pending.

## Ralplan review changelog

- Iteration 1 separated mandatory functional parity from measured performance,
  fixed the MVP objective to dense-valid fitted Q, bound decision contexts,
  made bundles immutable, and separated inference records from future
  training-mode gradient recomputation.
- Iteration 2 moved context-aware Q_H composition out of replay and into the
  online-Q_H pipeline, made fit inputs/results explicit, completed the ADR, and
  added concrete future staffing, Goal Mode, Team launch, and verification
  guidance.
- Critic iteration 1 fixed the online-round dataclass, specified the minimal new
  episode/round/proposer DTOs and existing DTO reuse, made dense-valid tensor
  admission executable, pinned the private replay callback bridge, and added
  an explicit #74/#75 acceptance-handoff ledger.
- Architect iteration 5 completed the `K`-attempt runtime/provenance contract
  and isolated dense-profile post-padding canonicalization from legacy batches.
- Critic iteration 2 switched checkpoint selection to the real `val/loss` key,
  required nested-context rehashing, instantiated the #74/#75 ledger schema and
  rows, and made both new configs explicit `TargetConfig` factories.
- Architect iteration 6 confirmed those repairs and added canonical detached-
  CPU, cross-device/fresh-process hash identity as the remaining implementation
  safeguard.
- Critic iteration 3 approved the local lifecycle and made proposal, oracle-
  query, and selected-action policy provenance separate named receipt fields.
