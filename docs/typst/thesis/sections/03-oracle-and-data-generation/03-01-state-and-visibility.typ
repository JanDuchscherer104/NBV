#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs

== Information Boundary

The learned component predicts finite-horizon values for a hard-masked candidate
table, but its inputs come from only one layer of a larger information lattice.
The experiment distinguishes logged observations, evidence caused by selected
actions, and privileged counterfactual quantities. ASE contributes both
sensor-like streams and ground truth; EFM3D transforms only the logged subset
into local 3D evidence @ProjectAria-ASE-2025 @EFM3D-straub2024. Co-location in
one adapted sample or replay row never makes those layers equally observable.

// evidence:
// - @ProjectAria-ASE-2025 -> docs/contents/ase_dataset.qmd:216-225,257-260 (sensor-like streams and privileged GT products)
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/method.tex:1-42 (logged modalities, voxel lifting, and GT-supervised heads)

#figure(
  align(center, image(
    "../../figures/actor_oracle_boundary.pdf",
    width: 100%,
  )),
  caption: [Actor and oracle boundary. Legal #symb.rl.qh inputs are calibrated logged image evidence, poses, semi-dense geometry with uncertainty and observation support, frozen @egocentric-voxel-lifting:short features or predictions, an explicitly sourced target instruction, selected-view history, remaining budget, candidates, and masks. Reason codes remain audit evidence rather than scorer inputs. @ground-truth:short depth, segmentation, boxes, meshes, target crops, counterfactual renders, labels, and endpoint evaluation remain privileged.],
) <fig:qh-actor-oracle-contract>

The visibility boundary is protocol-relative and temporal. A dense render for an unselected candidate at the current decision step is oracle evidence. A render from an already selected action may enter a later state only under an explicitly named source protocol: privileged mesh-rendered depth, a declared sensor simulation, or an actor-visible observation. The same array shape can therefore denote different information, and source role must remain explicit.

=== Logged Observations

Following the conditional action-value definition in
@sec:thesis-sequential-decision-foundations, the target is treated as external
task context, so the value is conceptually $Q(s_t,e,a)$ rather than a
target-independent state value. The logged historic state contains the recorded
trajectory evidence,

$
  #eqs.rl.s_hist
$

Calibrated image streams, trajectory, camera models, and gravity establish the
spatial, metric, and temporal frame in which evidence is compared. EFM3D lifts
posed image features into a finite gravity-aligned voxel volume rather than a
complete world model @EFM3D-straub2024. An out-of-extent target or candidate
therefore has missing representation support, not a measured zero and not
automatically an invalid pose.

// evidence:
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/method.tex:15-33, docs/literature/tex-src/arXiv-EFM3D/supplemental_text.tex:113-124 (calibrated lifting and finite local voxel extent)

Semi-dense points add sparse surface evidence with uncertainty, timestamps, and
observation lineage. EFM3D uses their observing camera centers to distinguish
surface support from sampled free-space rays @ProjectAria-ASE-2025
@EFM3D-straub2024. That distinction is causal: a missing point is not evidence
that a voxel is free, and free-space evidence is justified only when its camera
lineage is retained.

// evidence:
// - @ProjectAria-ASE-2025 -> docs/contents/ase_dataset.qmd:216-225 (MPS-style semi-dense points and uncertainty)
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/method.tex:15-33 (surface and free-space voxel evidence)

The target and remaining budget are decision context rather than sensing
modalities. The current oracle task derives its target from a selected
@ground-truth:short box; an actor-visible target must instead come from a
declared observation-derived association path. The information role is fixed by
provenance, not by tensor shape.

=== Selected Causal Evidence

The conceptual counterfactual actor state retains the immutable logged substrate and adds only information causally available after selected actions,

$
  #eqs.rl.s_cf0
$

For the canonical model, this compact tuple is read together with the explicit ordered selected-view history:

#eqs.scene.actor_state_read

In #symb.rl.s_cf0, the root field remains fixed while the accumulated point set
may grow only through selected observations. Candidate rows contain poses and
proposal provenance, not observations from those poses. The action mask defines
admission, the ordered history retains the factual approach sequence, and
invalid-reason codes remain audit evidence rather than model input.

The current baseline materializes only root evidence and selected-pose history
(the implementation anchor is `qh_cf0_v1`), a deliberately weaker
`S0-pose` state:

$
  #eqs.rl.s_pose
$

It carries root evidence, the admitted target descriptor, current candidates and
hard mask, factual selected-pose prefix, and remaining budget. A richer state
would update causal geometry after each selected action:

$
  #eqs.rl.s_cf_geom
$

The implemented richer control stops earlier: it persists selected mesh-rendered
depth with calibration under the privileged `qh_cfplus_gt_depth_v1` source
protocol. The carrier is causal with respect to the selected action but remains
privileged and is not yet fused into surface, free-space, uncertainty, or a
refreshed EFM3D field. It therefore cannot be interpreted as the full
geometry-updated actor state.

The transition from $t$ to $t+1$ may use only the observation produced by the selected row $a_t$. It may fuse its surface and ray evidence and update support, uncertainty, direction, and recency. It may not attach image features, detections, or EVL descriptors unless the protocol also provides the calibrated camera streams from which EFM3D derives them. Counterfactual geometry must therefore retain a source role and explicit absence masks for unavailable image-derived channels.

The counterfactual state is thus an *information state* for decision making, not automatically a complete Markov state of the physical scene. It becomes task-sufficient only if its retained root context, causal dynamic evidence, explicit history, target context, action support, and budget preserve every distinction needed to predict future target-specific return. `qh_cf0_v1` is the deliberately weaker `S0-pose` baseline; `qh_cfplus_gt_depth_v1` is a privileged depth carrier, not yet a realization of the geometry-updated state.

=== Privileged Counterfactual Evidence

The oracle state adds complete or counterfactual quantities outside the actor input graph:

$
  #eqs.rl.s_oracle
$

$
  #eqs.rl.nbv_process_tuple
$

ASE provides per-frame metric @ground-truth:short depth aligned with RGB, per-pixel instance identifiers, class mappings, and the scene trajectory; the EFM3D release adds ASE OBB metadata and validation meshes for object-detection and surface-reconstruction supervision @ProjectAria-ASE-2025 @EFM3D-straub2024. EFM3D uses the depth channel to supervise occupancy at sampled free, surface, and behind-surface points, while visible OBBs supervise centerness, class, and box geometry @EFM3D-straub2024. These uses establish label provenance, not actor observability.

For ARIA-NBV, #symb.ase.mesh is the privileged reference surface used for candidate rendering and reconstruction evaluation, while #symb.ase.mesh_target fixes the selected entity's evaluation support. All-candidate depth #symb.oracle.depth_q and backprojected point sets #symb.oracle.points_q answer counterfactual queries for unselected rows. #symb.oracle.rri then compares target reconstruction error before and after adding that candidate evidence. Depth, points, crops, and RRI are legal for label generation, oracle search, diagnostics, and named upper bounds; none is a contemporaneous input to the student value model.

A @ground-truth:short OBB may define the current oracle identity, pose, extent, crop, and target-bearing instruction. It does not show that the actor detected or associated that object. A deployable protocol must obtain the target hypothesis from EVL predictions or another observation-derived path, retaining ASE identity, segmentation, OBBs, and meshes only for matching and evaluation.

The information lattice therefore separates *what was logged*, *what a selected
history causally adds*, and *what only the oracle can know*. Its layers are
connected by controlled projections, not by freely copying arrays between
stores. Persisting an oracle tensor beside actor evidence for efficient replay
never changes its information role.

=== End-to-End Actor Visibility

Visibility answers whether a modality contains evidence for a spatial element from a particular view; feasibility answers whether an action is admissible; utility answers how beneficial an admissible action is for the target. These concepts must not be collapsed. A target can be weakly visible from a geometrically valid candidate, a candidate can lie outside EVL support while remaining physically reachable, and an oracle render can fail even though the candidate pose itself is feasible.

Invalidity is a constraint rather than a reward value. Geometry-invalid candidates receive a hard action mask and a persisted candidate reason code before policy selection, stochastic normalization, loss construction, and bootstrap maximization. A geometrically feasible candidate may still have low or negative target gain. Failure of the separate oracle evaluation does not create a candidate reason code: depending on the configured recipe, the affected row or table is skipped, or its oracle-label validity and Q-training eligibility are cleared and the oracle failure is reported separately. Oracle-derived feasibility must be distinguished from a deployable validity estimate when a policy moves from privileged target tasks to an actor-visible target protocol.

Actor visibility is consequently an end-to-end property of the decision
protocol. It includes how the target instruction is obtained, how candidate
support is proposed, how the hard mask is computed, which selected observation
updates the next state, and which fields reach the scorer. A scorer can be free
of privileged tensors while still choosing from support oriented or pruned with
privileged geometry. Such a protocol is a valid bounded oracle or control
experiment, but its result cannot silently become a claim about independently
actor-constructed actions.
