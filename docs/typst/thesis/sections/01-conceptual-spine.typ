#import "../../shared/macros.typ": *

== Geometric, temporal, and informational structure <ssec:thesis-conceptual-spine>

Target-conditioned NBV asks which feasible observation should be acquired next
when the objective is to improve the reconstruction of a requested object. The
value of a candidate is therefore relational: it depends on the current causal
evidence, the target, the available actions, the remaining acquisition budget,
and the observations that the first action may enable. The best immediate view
need not be the best first step of a sequence. Bounded oracle lookahead first
tests whether this non-myopic opportunity exists; only then does it become
meaningful to ask how much of it an actor-visible model can recover.
@sec:thesis-sequential-decision-foundations formalizes the value relation, and
@sec:thesis-experimental-design turns it into matched endpoint comparisons
@POMDPRobotics-lauri2023 @FixedHorizonTD-deAsis2020.

// evidence:
// - @POMDPRobotics-lauri2023 -> docs/literature/tex-src/arXiv-POMDP-Robotics-Survey/root.tex:505,589-606 (history-dependent policies and belief-state sufficiency)
// - @FixedHorizonTD-deAsis2020 -> docs/literature/tex-src/arXiv-Fixed-Horizon-TD/AAAI-DeasisK.9337.tex:245-290,331-339 (finite-horizon returns and shorter-horizon action-value recursion)
// implementation:
// - finite-horizon semantics -> aria_nbv/aria_nbv/lightning/qh_module.py
// - endpoint comparison -> aria_nbv/aria_nbv/rollouts/reporting.py

The decision has a natural hierarchy. The target state specifies what matters;
the scene state represents what is currently known; the candidate set describes
possible sensing interventions; and feasibility restricts which interventions
may be executed. A horizon-conditioned scorer then estimates the future target
improvement associated with choosing each candidate first. This factorization
suggests a heterogeneous set or graph representation: the observer and target
act as anchors, candidates are exchangeable query nodes, geometric evidence
forms spatial nodes, and selected observations form an ordered event stream.
Relative transforms, visibility, uncertainty, and time differences connect
these objects. Chapters @sec:thesis-oracle-data-generation and
@sec:thesis-method operationalize the hierarchy without collapsing its distinct
information roles.

// implementation:
// - factorized scorer -> aria_nbv/aria_nbv/vin/models/target_finite_horizon.py
// - actor/supervision split -> aria_nbv/aria_nbv/data_handling/qh_data/views.py

Geometry offers the strongest route to generalization under limited data. Two
encoded states are isomorphic for this task when a relation-preserving map
connects the same observer, target, candidate actions, and causal evidence. A
passive change of world coordinates should leave candidate ordering unchanged;
permuting candidate rows should permute their scores; and reordering an
unordered point or ray set should preserve its summary. Temporal order must
remain observable because the same poses visited in another order can expose
different evidence. Where object symmetries are known, a target representation
can treat symmetry-related frames as equivalent instead of selecting an
arbitrary canonical axis. These quotients must not remove physical variables:
gravity, scale, viewing direction, target orientation, occlusion, and motion
direction can all change the task. Current-camera, target-centred, and
candidate-local frames therefore provide useful charts for the same underlying
geometry @GeometricDeepLearning-bronstein2021 @zhou2023query
@DeepSets-zaheer2017 @SetTransformer-lee2019.
@sec:thesis-egocentric-geometric-representations and
@sec:thesis-method-geometry-contract develop the corresponding representation
and acceptance principles.

// evidence:
// - @GeometricDeepLearning-bronstein2021 -> docs/literature/tex-src/arXiv-Geometric-Deep-Learning/geometricpriors.tex:347-411,952-967 (invariance, equivariance, locality, and geometric priors)
// - @zhou2023query -> docs/literature/tex-src/arXiv-QCNet/main.tex:159-161 (query-centric local frames and relative spatial-temporal positions)
// - @DeepSets-zaheer2017 -> docs/literature/tex-src/arXiv-Deep-Sets/nips_2017.tex:103-106 (permutation-invariant set decomposition)
// - @SetTransformer-lee2019 -> docs/literature/tex-src/arXiv-Set-Transformer/03_main.tex:49-65 (permutation-equivariant self-attention)
// implementation:
// - relative pose features and row-equivariant output -> aria_nbv/aria_nbv/vin/models/target_finite_horizon.py
// - interaction controls -> aria_nbv/aria_nbv/vin/modules/qh_state_fusion.py

The target and scene require complementary representations. A deployable target
state is an observation-derived entity belief combining semantic or appearance
identity with pose, extent, confidence, observed support, and association
uncertainty. The scene state must preserve surfaces, observed free space,
unknown space, recency, uncertainty, and source while remaining causally
updateable. EVL supplies a strong local perceptual chart by aligning lifted
appearance, occupancy, free-space, and object evidence in a gravity-aligned
voxel field. Its finite lattice also fixes resolution and extent and cannot by
itself provide global temporal memory. This motivates a testable hybrid-state
hypothesis: local EVL features where supported, sparse point-and-ray memory
beyond the grid, target-centred directional support, and coarse entity or room
context. Candidate queries could read this memory through relative poses and
calibrated frusta. @sec:thesis-scene-representation develops this design space
from the currently available carriers @EFM3D-straub2024
@SceneScript-avetisyan2024.

// evidence:
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/method.tex:15-42, docs/literature/tex-src/arXiv-EFM3D/supplemental_text.tex:113-124 (local voxel lifting, surface/free-space evidence, and finite spatial support)
// - @SceneScript-avetisyan2024 -> docs/literature/tex-src/arXiv-scene-script/sections/structured_scene_language.tex:19-49 (structured layout and object representation)
// implementation:
// - target-source protocol -> aria_nbv/aria_nbv/targets/protocol.py
// - current root and selected-surface carriers -> aria_nbv/aria_nbv/vin/modules/qh_scene_encoders.py
// - target-frame directional diagnostics -> aria_nbv/aria_nbv/rollouts/inspection.py

The temporal update is an observation event, not merely another pose. The
oracle may render every feasible candidate to construct immediate labels, but
only evidence produced by selected actions may enter the next actor state. Even
a selected mesh render remains privileged until it is replaced by a real
observation, a validated sensor-like simulation, or a learned observation model
with explicit uncertainty and source. Leakage can also enter before scoring
when ground-truth target geometry or mesh-based feasibility shapes the candidate
set. The boundary in @fig:qh-actor-oracle-contract therefore applies to the
complete decision process: privileged information may teach values and establish
headroom, but it must not silently become student state.

// implementation:
// - causal selected-observation prefix -> aria_nbv/aria_nbv/data_handling/qh_data/views.py
// - rollout state transitions -> aria_nbv/aria_nbv/rollouts/replay/engine.py
// - source-aware replay admission -> aria_nbv/aria_nbv/rollouts/qh_reader.py

This asymmetry also determines how the limited corpus should be used. The local
mesh-backed data contain 100 scenes and 4,608 overlapping snippets, so the
number of independent environments is much closer to 100 than to 4,608. Sample
efficiency should come from structure: shared parameters across targets,
candidates, and horizons; dense immediate labels; a curriculum from immediate
to two-step and then longer-horizon targets; coordinate-consistent augmentation;
candidate permutations; target resampling; causal sub-prefixes; and source-aware
modality dropout. Perceptual and memory components can additionally be
pretrained on broader ASE geometry, semantics, and temporal consistency without
requiring mesh-based reconstruction-improvement labels. Synthetic realism
should be separated into environment and sensor realism, factual wearer motion,
and the counterfactual intervention distribution. A learned prior over natural
pose increments can anchor candidate generation, while an exploratory tail
remains necessary to expose occluded target surfaces @ProjectAria-ASE-2025
@projectaria-engel2023.

// evidence:
// - local mesh-backed snapshot -> docs/contents/ase_dataset.qmd (100 scenes and 4,608 ATEK-EFM snippets)
// - @ProjectAria-ASE-2025 -> docs/contents/ase_dataset.qmd (procedural indoor scenes and simulated Aria sensor streams)
// - @projectaria-engel2023 -> docs/literature/tex-src/arXiv-project-aria/applications_new.tex:46-61 (curated scanning versus natural egocentric activity)

The current implementation exposes these ideas through a
#gh-wip("aria_nbv/aria_nbv/targets/protocol.py", body: [target-provenance boundary], ref: "f3016f0f66db7d0e77fe9832279cdc4a6e0af6f2", line: 1),
#gh-wip("aria_nbv/aria_nbv/pose_generation/candidate_mixture.py", body: [mixed candidate generator], ref: "f3016f0f66db7d0e77fe9832279cdc4a6e0af6f2", line: 1),
#gh-wip("aria_nbv/aria_nbv/data_handling/qh_data/views.py", body: [causal actor and supervision view], ref: "f3016f0f66db7d0e77fe9832279cdc4a6e0af6f2", line: 1),
#gh-wip("aria_nbv/aria_nbv/vin/modules/qh_scene_encoders.py", body: [scene-carrier seam], ref: "f3016f0f66db7d0e77fe9832279cdc4a6e0af6f2", line: 1),
#gh-wip("aria_nbv/aria_nbv/vin/modules/qh_history_encoders.py", body: [temporal-history seam], ref: "f3016f0f66db7d0e77fe9832279cdc4a6e0af6f2", line: 1), and
#gh-wip("aria_nbv/aria_nbv/vin/models/target_finite_horizon.py", body: [finite-horizon scorer], ref: "f3016f0f66db7d0e77fe9832279cdc4a6e0af6f2", line: 1).
The intended contribution is to determine, through controlled comparisons,
which geometric relations, temporal distinctions, and source boundaries are
necessary, useful, or redundant for recovering non-myopic value in this bounded
egocentric setting. Until those comparisons are complete, the hybrid state
remains a representation hypothesis rather than an established result.
