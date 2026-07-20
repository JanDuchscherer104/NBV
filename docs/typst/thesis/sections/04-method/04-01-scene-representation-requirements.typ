#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status
#import "@preview/booktabs:0.0.4": *

== Actor State and Representation Boundary <sec:thesis-scene-representation>

=== Implemented carrier and information boundary

#thesis_status(
  implementation: "implemented",
  evidence: "pending",
  citation: [@EFM3D-straub2024],
  source: "aria_nbv/aria_nbv/targets/descriptor.py; aria_nbv/aria_nbv/vin/candidate_scorer.py; aria_nbv/aria_nbv/rollouts/replay/state.py; aria_nbv/tests/rollouts/test_zarr_store.py",
  gate: [retain actor/oracle provenance checks in every reader],
)[The current carrier, replay masks, and target-task provenance are implemented and covered by schema tests. Frozen scientific validation remains pending. This status does not imply that the planned target-conditioned finite-horizon scorer is implemented.]

The implemented one-step scorer consumes an actor-visible snippet view, a row-aligned candidate table, a reference rig pose, calibrated candidate cameras, and optionally cached @egocentric-voxel-lifting:short output. Oracle @relative-reconstruction-improvement:short labels enter the loss after prediction and are not scorer inputs. The V0 target descriptor contains semantic identity, pose, positive metric extents, and reference-relative pose in an actor-safe shape, but its current values are derived from privileged @ground-truth:short target tasks. A deployable claim therefore still requires observed or predicted target fields with explicit provenance.

The replay transition stores the candidate result, selected row, selection policy, root-to-selected pose chain, remaining budget, and successor-table linkage. Candidate regeneration changes pose, history, budget, and the finite action table. It does not update a learned persistent scene representation after every selected action. Stored selected-depth maps are privileged GT-mesh counterfactual evidence unless a named experiment establishes a deployable observation source.

Three boundaries are invariant. Invalidity is a hard mask with versioned reason codes, not a small value. GT meshes, target crops, all-candidate renders, associations, and returns remain oracle or audit fields. Candidate rows remain tied to stable shell identities and documented coordinate frames.

=== Task-sufficient actor state

#thesis_status(
  implementation: "planned",
  evidence: "pending",
  citation: [@GeometricDeepLearning-bronstein2021 @DeepSets-zaheer2017],
  source: "docs/contents/theory/efm3d_scene_embeddings.qmd; docs/contents/theory/candidate_view_dependence.qmd",
  gate: [reader implementation, source-dropout tests, and held-out target-RRI ranking],
)[The thesis adopts a representation-independent readout contract. Particular scene carriers are promoted only when they preserve the information boundary and improve target-conditioned decisions.]

ARIA-NBV does not require one universal reconstruction format. It requires an actor-visible state from which a model can compare a target $e$ and candidate $q_(t,i)$ at decision step $t$ and requested horizon $H$:

$
  #eqs.scene.actor_state_read
$

Here #symb.scene.scene_memory_t denotes persistent scene evidence, #symb.model.target_token identifies the task, and $bold(H)_t$ records selected-view history. A useful representation must preserve distinctions that can change target-specific return, distinguish missing evidence from predicted free space, and admit a causal update after selection. This requirement is narrower than a globally dense or photorealistic reconstruction and stronger than a pooled scene vector with no spatial support or provenance.

The desired memory separates observed surface, observed free space, unknown space, uncertainty, support count, recency, and directional history. Candidate queries should read the same memory in target-local, candidate-local, and ray-relative coordinates. A common world translation or yaw convention must not change the physical candidate values, while gravity, scale, target extent, camera direction, occlusion, and temporal order remain observable task variables. Exact global $op("SE")(3)$ invariance is therefore neither required nor claimed.

=== Local EFM3D evidence and the coverage gap

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@EFM3D-straub2024 @EVL-Doc-2025],
  source: "docs/literature/tex-src/arXiv-EFM3D/method.tex, Sec. Egocentric Voxel Lifting, lines 2--44; docs/contents/literature/efm3d.qmd; docs/contents/theory/efm3d_scene_embeddings.qmd; aria_nbv/aria_nbv/data_handling/offline/writer.py",
  gate: [report target and candidate support against the persisted voxel pose and extent],
)[EFM3D fields, their voxel pose, and finite extent are persisted. A frozen target/candidate coverage artifact and their sufficiency as the only long-horizon scene representation remain pending.]

EFM3D encodes logged RGB frames before lifting selected evidence into a finite gravity-aligned voxel field anchored to a snippet pose. The stored voxel transform and extent define the support of lifted features and dense heads. They must not be interpreted as a global volume containing every region observed by the trajectory. A target or candidate outside this support can remain physically valid; it has missing local-EVL evidence rather than an ordinary zero feature or automatically invalid action.

The coverage limitation motivates a layered interface rather than repeated inference at hypothetical candidate poses. Local EVL features provide high-quality Aria-native evidence where supported. Broader semidense or fused point carriers can preserve observed surfaces beyond that volume. Sparse ray-aware state can distinguish occupied, free, and unknown regions and can be updated from selected geometry. Logged appearance descriptors can be attached to points only after visibility and source lineage are established. None of these carriers creates RGB, DINO, detector, or EVL evidence at an unvisited counterfactual pose.

=== Ranked representation design space

#thesis_status(
  implementation: "exploratory",
  evidence: "pending",
  citation: [@VIN-NBV-frahm2025 @GenNBV-chen2024 @ObjectCentricNBV-jeong2026 @SceneScript-avetisyan2024],
  source: "docs/literature/tex-src/arXiv-GenNBV/3-Method.tex, Secs. Formulation and Generalizable State Embedding, lines 10--49; docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex, Sec. Methods, lines 14--58; docs/literature/tex-src/arXiv-scene-script/sections/structured_scene_language.tex; docs/contents/literature/efm3d.qmd",
  gate: [promote only after matched support, leakage, runtime, and oracle-policy ablations],
)[The table is a ranked design space, not a claim that every carrier will be implemented. The canonical model consumes a typed scene-memory interface so representations can be exchanged without redefining candidate or target semantics.]

#figure(
  text(size: 8.2pt, table(
    columns: (0.78fr, 0.72fr, 1.18fr, 1.22fr),
    toprule(),
    table.header([*Carrier*], [*Status*], [*Inductive benefit*], [*Cost and promotion gate*]),
    midrule(),
    [Persisted EVL and snippet evidence], [active baseline], [Aria-native local features, OBB hypotheses, calibrated cameras, and explicit extent.], [Limited spatial support; retain only with coverage metadata.],
    [Semidense or fused point memory], [first broad-memory control], [Observed surfaces follow trajectory extent and support target/frustum pooling.], [No free/unknown state; test density and visibility sensitivity.],
    [Sparse ray-aware memory], [planned primary extension], [Separates surface, free, unknown, support, uncertainty, and causal updates.], [Requires deterministic fusion and counterfactual-source masks.],
    [Target-centred EVL re-lifting], [adaptation ablation], [Reuses logged frame features when the target lies outside the root field.], [Domain shift in the 3D neck; compare against simple logged-feature pooling.],
    [DINO-on-point], [appearance ablation], [Extends logged appearance to observed points beyond the EVL grid.], [Needs visibility gating, compression, and missing-descriptor masks.],
    [TSDF/SDF or sparse encoder], [geometry/encoder ablation], [Compact metric geometry or learned coordinate-bearing tokens.], [Must preserve observation weights and unknown-space semantics.],
    [Object-aware 3DGS], [renderable-memory ablation], [Candidate rendering, soft target membership, and primitive uncertainty.], [Per-scene optimization and mask supervision change the state contract.],
    [SceneScript], [global-context control], [Broad ASE-aligned layout and object hypotheses from semidense input.], [Not an ATEK drop-in and does not provide causal free/unknown updates.],
    bottomrule(),
  )),
  caption: [Ranked scene-representation design space. Status describes its role in the thesis method, not empirical superiority.],
) <tab:thesis-scene-representation-design-space>

Representation comparisons begin with the persisted carrier and explicit support summaries. Learned point, sparse, equivariant, or renderable encoders are introduced only when a simpler carrier demonstrably limits target-RRI ranking or finite-horizon recovery. This ordering keeps representation capacity separate from target identity, candidate support, and replay validity.
