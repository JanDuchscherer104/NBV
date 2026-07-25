#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs

== State and Visibility Boundary

The thesis studies a masked finite-horizon candidate-decision process through offline, mesh-supervised counterfactual replay. Logged egocentric observations and frozen @egocentric-voxel-lifting:short evidence define the actor substrate, whereas @aria-synthetic-environments:short meshes, annotations, synthetic target instructions, rendered counterfactual geometry, and labels define privileged data generation @ProjectAria-ASE-2025 @EFM3D-straub2024 @VIN-NBV-frahm2025. An oracle product may supervise a loss or define an upper bound, but it may not enter the learned #symb.rl.qh actor unless the experiment is explicitly labelled privileged.

Here a *modality* is not identified only by its tensor type. It is an observation channel together with its acquisition time, coordinate frame, spatial support, uncertainty, and provenance. The same numerical depth array has different epistemic status when measured by an actor-visible sensor, simulated by a declared sensor model, or rendered from the complete @ground-truth:short mesh. Likewise, an absent EVL feature is not a measured zero, an unobserved voxel is not observed free space, and a padded candidate is not a geometrically invalid action. The state contract must therefore preserve modality-presence, padding, action-validity, and source-role masks as separate variables.

#figure(
  align(center, image(
    "../../figures/actor_oracle_boundary.pdf",
    width: 100%,
  )),
  caption: [Actor and oracle boundary. Legal #symb.rl.qh inputs are accumulated actor geometry, frozen @egocentric-voxel-lifting:short evidence, an explicitly declared target instruction, selected-view history, remaining budget, candidates, masks, and reason codes. @ground-truth:short geometry, target crops, dense counterfactual renders, labels, and endpoint evaluation remain privileged.],
) <fig:qh-actor-oracle-contract>

The visibility boundary is protocol-relative and temporal. A dense render for an unselected candidate at the current decision step is always oracle or teacher evidence. A render from an action already selected in the retained history may enter a later actor state only under an explicitly named protocol: `CF-GT` for privileged GT-mesh depth, `CF-sensor` for a declared sensor-like simulation, or V1 for an actually actor-visible observation. The same rule applies to backprojected points, normals, and free-space rays. Persisting selected depth does not by itself make that field a legal actor input.

=== Logged Multimodal Observation State

The target is treated as external task context, so the value is conceptually $Q(s_t,e,a)$ rather than a target-independent state value. The logged historic state contains the recorded trajectory evidence,

$
  #eqs.rl.s_hist
$

Each component of this tuple has a distinct information role:

*RGB appearance.* #symb.obs.img_rgb samples radiance along calibrated camera rays. It contains texture, colour, and semantic cues, but no metric 3D location by itself. Camera intrinsics and the pose stream #symb.obs.pose define the projection relation that locates an image measurement in the common world or root frame. Consequently, RGB values from different times cannot be fused merely by concatenation, and a hypothetical camera pose does not imply a hypothetical RGB observation.

*Calibrated poses and trajectory metadata.* These are geometric relations rather than visual measurements. They align observations across time, define the egocentric motion history, and allow candidates to be expressed relative to a reference pose. They do not reveal surfaces that were never sensed. The absolute world coordinates are therefore bookkeeping; candidate value should depend on physical relative geometry, viewing direction, gravity, and scale rather than an arbitrary choice of world origin.

*Semi-dense geometry.* #symb.obs.points_semi is a set of triangulated or otherwise reconstructed surface samples accumulated from the logged trajectory. It supplies metric occupied-surface evidence over the support of successful tracks. Sparsity, finite track support, and reconstruction uncertainty mean that absence of a point does not distinguish free from occluded or never-observed space. This set is therefore an observation-dependent geometric proxy, not a complete scene surface @projectaria-engel2023 @ProjectAria-ASE-2025.

*Frozen EVL evidence.* #symb.vin.field_v is a learned voxel-aligned feature field derived from logged egocentric evidence. Its occupancy, surface, count, centerness, and learned feature channels encode local spatial context within the persisted voxel pose and finite extent. The field is immutable within a rollout: it may be queried at a target or candidate where it has support, but it may not be extrapolated as fresh evidence at an unvisited pose. Outside its support the modality is missing, not zero and not invalid @EFM3D-straub2024 @EVL-Doc-2025.

*Target context.* #symb.rl.target specifies which entity the decision serves. It is separated from target-independent scene evidence because identical geometry can induce different candidate values for different targets. In V0 the descriptor is an explicitly privileged instruction derived from a selected @ground-truth:short box; in V1 it must be obtained from actor-visible detections or observations with confidence and availability recorded. The common descriptor shape does not erase this provenance difference.

*Remaining budget.* #symb.rl.budget is a control variable, not a sensor measurement. It makes the value horizon-dependent: an action can be favourable with several acquisitions remaining yet unfavourable as the terminal step. Step index, requested residual horizon, and budget must agree by protocol but are not interchangeable quantities.

The RGB stream, semi-dense points, and EVL field are complementary rather than redundant. RGB is appearance-rich but projective; semi-dense points are metric but spatially sparse; EVL is learned and locally dense but bounded by its voxel support. Calibration connects these modalities, while explicit availability and uncertainty prevent the actor from interpreting missing evidence as negative evidence.

=== Counterfactual Actor State

The counterfactual actor state retains the immutable logged substrate and adds only information causally available after selected actions,

$
  #eqs.rl.s_cf0
$

For the canonical model, this compact tuple is read together with the explicit ordered selected-view history:

$
  s_t^"actor" = (s_t^"cf0", bold(H)_t)
$

In #symb.rl.s_cf0, the root EVL field remains fixed, whereas the accumulated point set $cal(P)_t$ is the geometry carrier that may grow with selected observations. The finite candidate table #symb.oracle.candidates_t is the current discrete action support: each row denotes a calibrated candidate pose and its generation provenance, not an observation taken from that pose. The hard mask #symb.rl.validity_mask defines membership in the admissible action set, while #symb.rl.invalid_reason explains why an excluded row violates a geometric or protocol constraint. Neither field is a utility estimate. The ordered selected-view history $bold(H)_t$ records how the state was reached and preserves directional and temporal information that an unordered point union may discard.

The richer geometry-updated state makes the selected observation channels explicit:

$
  #eqs.rl.s_cf_geom
$

Here selected *depth* #symb.obs.depth is a projective range measurement whose metric meaning depends on its valid-pixel mask and camera calibration. Backprojection converts valid depth samples into selected-view surface points #symb.obs.points_cf in a common frame; this operation changes representation, not provenance. Visibility #symb.obs.vis records which rays or elements were actually supported, and face normals #symb.obs.face_normal encode local surface orientation where it can be estimated or rendered. Retaining the corresponding rays can additionally distinguish observed free space before a hit from unknown space outside all observed rays. Surface points alone cannot represent that distinction.

These selected-observation modalities are action-indexed and causal: the transition from $t$ to $t+1$ may use only the observation produced by the chosen row $a_t$. It may fuse occupied-surface evidence, carve observed free space, update uncertainty and support, and record direction or recency. It may not synthesize RGB, DINO, detector, or EVL features for counterfactual points unless the declared protocol supplies a corresponding actor-visible observation. A missing-modality mask and a source-role tag must accompany any geometry whose photometric or learned descriptors are unavailable.

The counterfactual state is thus an *information state* for decision making, not automatically a complete Markov state of the physical scene. It becomes task-sufficient only if its retained root context, causal dynamic evidence, explicit history, target context, action support, and budget preserve every distinction needed to predict future target-specific return. A pose-only implementation updates #symb.rl.candidate_table, $bold(H)_t$, and #symb.rl.budget without acquiring new scene evidence; it is therefore a deliberately weaker `S0-pose` baseline rather than a realization of the geometry-updated state.

=== Privileged Oracle State

The oracle state adds complete or counterfactual quantities outside the actor input graph:

$
  #eqs.rl.s_oracle
$

$
  #eqs.rl.nbv_process_tuple
$

The scene mesh #symb.ase.mesh represents the privileged reference surface used to render views and evaluate reconstruction. Its target crop #symb.ase.mesh_target fixes the entity-specific evaluation support; it is not an actor-visible object segmentation. All-candidate depth #symb.oracle.depth_q and the corresponding backprojected point sets #symb.oracle.points_q answer counterfactual questions for rows that have not been selected. They are legal for label construction, oracle search, diagnostics, and explicitly privileged upper bounds, but illegal as contemporaneous student inputs. Finally, #symb.oracle.rri is a scalar derived by comparing reconstruction errors before and after adding candidate evidence. It is supervision or evaluation, not a sensed modality and not an action-validity signal.

Annotations occupy the same privileged side of the boundary. A @ground-truth:short OBB can define entity identity, metric extent, a crop, and a target-bearing instruction for controlled V0 data generation. Those uses do not demonstrate that a detector discovered the object, estimated its extent, or associated it consistently across views. A deployable V1 experiment must replace the instruction with an observation-derived target hypothesis while retaining GT identity and geometry only for matching and evaluation.

The state hierarchy therefore separates *what was logged*, *what a selected counterfactual history may causally add*, and *what only the oracle can know*. Its layers are related by controlled information projections, not by freely copying arrays between stores. In particular, an oracle tensor may be persisted beside actor tensors for efficient replay without becoming part of the actor state.

=== Visibility, Feasibility, and Utility

Visibility answers whether a modality contains evidence for a spatial element from a particular view; feasibility answers whether an action is admissible; utility answers how beneficial an admissible action is for the target. These concepts must not be collapsed. A target can be weakly visible from a geometrically valid candidate, a candidate can lie outside EVL support while remaining physically reachable, and an oracle render can fail even though the candidate pose itself is feasible.

Invalidity is a constraint rather than a reward value. Geometry-invalid candidates receive a hard action mask and a persisted candidate reason code before policy selection, stochastic normalization, loss construction, and bootstrap maximization. A geometrically feasible candidate may still have low or negative target gain. Failure of the separate oracle evaluation does not create a candidate reason code: depending on the configured recipe, the affected row or table is skipped, or its `oracle_label_mask` and `q_train_mask` are cleared and the oracle failure is reported separately. Oracle-derived feasibility must be distinguished from a deployable validity estimate whenever policy claims cross from V0 to V1.
