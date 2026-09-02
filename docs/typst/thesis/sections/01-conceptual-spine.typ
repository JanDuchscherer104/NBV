#import "../../shared/macros.typ": *

== Geometric, temporal, and informational structure <ssec:thesis-conceptual-spine>

Target-conditioned NBV is a relational prediction problem over a changing
information state. A candidate camera has no context-free value: its utility
depends on what has already been observed, which object should improve, which
alternatives are feasible, how many acquisitions remain, and which later
observations the first action may enable. The first scientific question is
therefore whether target-specific reconstruction quality contains delayed
structure at all. Bounded oracle lookahead tests for that opportunity; the
learned problem begins only once an actor-visible state must recover part of it.
@sec:thesis-sequential-decision-foundations formalizes this relation, and
@sec:thesis-experimental-design turns it into matched endpoint comparisons
@POMDPRobotics-lauri2023 @FixedHorizonTD-deAsis2020.

// implementation:
// - finite-horizon semantics -> aria_nbv/aria_nbv/lightning/qh_module.py
// - endpoint comparison -> aria_nbv/aria_nbv/rollouts/reporting.py

The relation suggests a hierarchy of distinct objects. The target state
specifies what matters, the scene state represents what is known, and the
candidate set describes possible sensing interventions. Feasibility removes
actions that cannot be executed. A horizon-conditioned scorer then estimates
the future target-reconstruction consequence of choosing each surviving
candidate first. This factorization admits a heterogeneous set or graph model:
the target and current observer act as anchors, candidate views are exchangeable
query nodes, geometric evidence supplies spatial nodes, and selected
observations form an ordered event stream. Relative transforms, visibility,
uncertainty, and time differences define their relations. Chapters
@sec:thesis-oracle-data-generation and @sec:thesis-method make these information
and model boundaries operational.

// implementation:
// - factorized scorer -> aria_nbv/aria_nbv/vin/models/target_finite_horizon.py
// - actor/supervision split -> aria_nbv/aria_nbv/data_handling/qh_data/views.py

Generalization should arise by preserving physical relations while discarding
arbitrary representation choices. Two encodings should be treated as equivalent
when a relation-preserving map connects their observer, target, candidates, and
causal evidence. A passive change of world coordinates must leave candidate
ordering unchanged. Permuting candidate rows must permute their scores, while
reordering an unordered point or ray set must not change its geometric summary.
Temporal order must remain observable because the same visited poses in another
order can expose different evidence. For symmetric objects, target orientation
should be interpreted modulo the object's physical symmetry instead of being
forced into an arbitrary canonical axis. Active physical transformations remain
meaningful: gravity, metric scale, camera direction, target orientation,
occlusion, and motion direction can change the task. Current-camera,
target-centred, and candidate-local frames therefore provide useful charts for
the same underlying geometry. These principles motivate
@sec:thesis-egocentric-geometric-representations and the acceptance properties
in @sec:thesis-method-geometry-contract @GeometricDeepLearning-bronstein2021
@zhou2023query @DeepSets-zaheer2017 @SetTransformer-lee2019.

// implementation:
// - relative pose features and row-equivariant output -> aria_nbv/aria_nbv/vin/models/target_finite_horizon.py
// - interaction controls -> aria_nbv/aria_nbv/vin/modules/qh_state_fusion.py

The target and scene require complementary representations. A deployable target
state is an observation-derived entity belief combining semantic or appearance
identity with pose, extent, confidence, observed support, and association
uncertainty. The scene state must preserve surface evidence, observed free
space, unknown space, recency, uncertainty, and source while remaining causally
updateable. EVL contributes a strong local perceptual chart by co-locating
lifted appearance, occupancy, free-space, and object-related evidence in a
gravity-aligned voxel field. Its lattice also fixes resolution and extent,
aliases continuous geometry, and does not provide global temporal memory. A
stronger planning state is therefore hybrid: local EVL features where supported;
sparse point-and-ray memory beyond the grid; target-centred directional support;
and coarse entity or room context. Candidate queries can read this memory
through relative poses and calibrated frusta. @sec:thesis-scene-representation
develops this design space from the currently available carriers
@EFM3D-straub2024 @SceneScript-avetisyan2024.

// implementation:
// - target-source protocol -> aria_nbv/aria_nbv/targets/protocol.py
// - current root and selected-surface carriers -> aria_nbv/aria_nbv/vin/modules/qh_scene_encoders.py
// - target-frame directional diagnostics -> aria_nbv/aria_nbv/rollouts/inspection.py

The temporal update is an observation event, not merely another pose. At state
$t$, the actor may use only logged evidence and observations caused by earlier
selected actions. The oracle may render every feasible candidate to construct
immediate labels, but an unselected render must never enter the next actor
state. Even after selection, mesh-rendered depth remains privileged unless it is
replaced by a real observation, a validated sensor-like simulation, or a learned
observation model with explicit source and uncertainty. Leakage can also enter
before scoring when privileged target geometry or mesh-based feasibility shapes
the available candidates. The boundary in @fig:qh-actor-oracle-contract
therefore applies to the complete decision process: privileged information may
teach values or establish headroom, but it must not silently become student
state.

// implementation:
// - causal selected-observation prefix -> aria_nbv/aria_nbv/data_handling/qh_data/views.py
// - rollout state transitions -> aria_nbv/aria_nbv/rollouts/replay/engine.py
// - source-aware replay admission -> aria_nbv/aria_nbv/rollouts/qh_reader.py

This asymmetry determines how the limited data should be used. The local
mesh-backed corpus contains 100 scenes and 4,608 overlapping snippet windows,
so environmental diversity is governed primarily by the scene count. Sample
efficiency should come from structural sharing: frozen or lightly adapted
perceptual features; one model shared across targets, candidates, and horizons;
dense immediate labels for every evaluable candidate; a curriculum from
immediate to two-step and longer-horizon targets; coordinate-consistent
augmentation, candidate permutations, target resampling, causal sub-prefixes,
and source-aware modality dropout. Perception and memory can additionally be
pretrained on broader ASE geometry, semantic, and temporal-consistency tasks
that do not require mesh-based reconstruction-improvement labels. Synthetic
realism should likewise be factorized into scene and sensor realism, factual
wearer motion, and the counterfactual intervention distribution. A learned
prior over natural pose increments can anchor candidate generation, while an
explicit exploratory tail remains necessary to expose occluded target surfaces
@ProjectAria-ASE-2025 @projectaria-engel2023.

// evidence:
// - local mesh-backed snapshot -> docs/contents/ase_dataset.qmd
// implementation:
// - scene-disjoint learning stages -> aria_nbv/aria_nbv/lightning/qh_datamodule.py
// - dense immediate and selected-transition learning -> aria_nbv/aria_nbv/lightning/qh_module.py
// - mixed intervention support -> aria_nbv/aria_nbv/pose_generation/candidate_mixture.py

The current implementation realizes a deliberately coarse instance of this
factorization through a #gh-wip(
  "aria_nbv/aria_nbv/targets/protocol.py",
  body: [target-provenance boundary],
), a #gh-wip(
  "aria_nbv/aria_nbv/pose_generation/candidate_mixture.py",
  body: [mixed candidate generator],
), #gh-wip(
  "aria_nbv/aria_nbv/data_handling/qh_data/views.py",
  body: [causal actor and supervision views],
), separate #gh-wip(
  "aria_nbv/aria_nbv/vin/modules/qh_scene_encoders.py",
  body: [scene carriers],
) and #gh-wip(
  "aria_nbv/aria_nbv/vin/modules/qh_history_encoders.py",
  body: [history encoders],
), and a #gh-wip(
  "aria_nbv/aria_nbv/vin/models/target_finite_horizon.py",
  body: [finite-horizon scorer],
). The thesis need not identify a universally optimal representation. Its more
durable contribution is controlled evidence about which geometric relations,
temporal distinctions, and source boundaries must survive for non-myopic
egocentric view selection.
