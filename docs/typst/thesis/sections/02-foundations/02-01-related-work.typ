#import "../../../shared/macros.typ": *
#import "@preview/booktabs:0.0.4": *

== Related Work

Classical and model-based NBV provide the control abstraction used here: represent the current reconstruction, propose feasible viewpoints, evaluate their utility, and select the next view. PB-NBV states this decomposition explicitly and replaces extensive ray-casting with a projection-based score over candidate views @PB-NBV-jia2025. This is a useful finite-candidate control, but its coverage objective does not establish target-conditioned reconstruction improvement or actor-visible target discovery. ARIA-NBV therefore holds candidate support fixed when comparing a one-step controller with bounded lookahead.

// evidence:
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/sections/related.tex:5-24 (object representation, candidate viewpoint proposal, and viewpoint selection)
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/jzz_2025_ral_resub.tex:55-70 (current-data NBV, candidate-view scoring, and projection-based replacement for ray-casting)

Quality-driven NBV changes the selection target from coverage to reconstruction improvement. VIN-NBV samples query cameras, predicts Relative Reconstruction Improvement from the current reconstruction and camera state, and repeats a greedy selection loop @VIN-NBV-frahm2025. Its RRI uses a ground-truth reconstruction for evaluation, so that oracle is a label or upper-reference path rather than an actor input @VIN-NBV-frahm2025. A bounded lookahead is consequently a testable planning extension, not an automatic consequence of using RRI: the Trajectory Transformer literature makes the receding-horizon operation explicit by executing the first action of a predicted sequence and replanning @TrajectoryTransformer-janner2021. ARIA-NBV uses that rationale to test finite-horizon headroom under the same candidate support instead of importing a guarantee from a different action space or reward.

// evidence:
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:18-20, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:36-44, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:78-92 (sampled greedy NBV, RRI definition, and ground-truth reconstruction metric)
// - @TrajectoryTransformer-janner2021 -> docs/literature/tex-src/arXiv-Trajectory-Transformer/text/method.tex:66-80, docs/literature/tex-src/arXiv-Trajectory-Transformer/text/method.tex:98-122 (offline sequence planning, first-action replanning, reward-to-go, and out-of-distribution action risk)

Target-conditioned NBV adds a second boundary: scene-wide information gain can be high while the selected entity remains poorly reconstructed. Object-centric 3DGS NBV assigns object features to Gaussians, computes candidate information gain, and gates confidence to zero when a Gaussian is not associated with the requested object @ObjectCentricNBV-jeong2026. EFM3D makes the related visibility and occlusion distinction explicit in its OBB metadata @EFM3D-straub2024. These sources support target-aware supervision and evaluation, not an actor-visible target-discovery contract. Defining an evaluation target is distinct from establishing actor-visible target discovery: a supplied mask, target vector, or GT OBB can define the evaluation target, but it does not show that a human request or an actor observation has identified it. ARIA-NBV therefore treats an observed or predicted target record as an upstream requirement for learned-policy claims.

// evidence:
// - @ObjectCentricNBV-jeong2026 -> docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:54-86 (object-vector features, Gaussian representation, and object-feature supervision)
// - @ObjectCentricNBV-jeong2026 -> docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:123-139 (candidate information-gain definition and uncertainty-based view scoring)
// - @ObjectCentricNBV-jeong2026 -> docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:249-258 (target-object confidence gate)
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/dataset.tex:15-30 (OBB visibility, observability, occlusion, calibrated annotation, and GT meshes)

Project Aria defines the calibrated multimodal egocentric sensing regime, while EFM3D builds OBB and mesh annotations on Aria Synthetic Environments and real Project Aria sequences @projectaria-engel2023 @EFM3D-straub2024. Its baseline consumes posed and calibrated RGB/greyscale streams and semidense points, and SceneScript shows how Aria-synthetic egocentric trajectories can support structured scene representations @EFM3D-straub2024 @SceneScript-avetisyan2024. These works are sensing and representation substrates, not NBV objectives: meshes, GT boxes, and counterfactual renders remain supervision or evaluation assets, while candidate selection must use logged observations and target evidence available to the actor.

// evidence:
// - @projectaria-engel2023 -> docs/literature/tex-src/arXiv-project-aria/intro.tex:24-26, docs/literature/tex-src/arXiv-project-aria/device.tex:12-15 (wearable egocentric multimodal capture and calibrated, time-aligned sensor streams)
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/intro.tex:42-50, docs/literature/tex-src/arXiv-EFM3D/dataset.tex:15-30 (Aria modalities, ASE/Project Aria data, OBB visibility, and GT meshes)
// - @SceneScript-avetisyan2024 -> docs/literature/tex-src/arXiv-scene-script/sections/introduction.tex:14-28, docs/literature/tex-src/arXiv-scene-script/sections/dataset.tex:1-18 (structured scene language and synthetic egocentric trajectories)

Offline value learning supplies the reason to make support and horizon explicit. Continuous NBV variants such as GenNBV and Hestia use 5-DoF actions with coverage-oriented rewards or hierarchical look-at actions @GenNBV-chen2024 @Hestia-lu2026. BCQ identifies extrapolation error in fixed-batch learning and constrains decisions toward batch-supported actions, while CQL penalizes values for unsupported actions @BCQ-fujimoto2019 @CQL-kumar2020. Double DQN separates action selection from value evaluation to reduce maximization bias @DoubleDQN-vanHasselt2015. ARIA-NBV therefore fixes a finite horizon as a design decision: it bounds the return and makes the candidate-support protocol auditable. This choice is compatible with the support and bias concerns above, but it is not a consequence or guarantee of BCQ, CQL, or Double DQN. Every selected trajectory must still be re-evaluated by endpoint target quality rather than accepted on predicted value alone.

// evidence:
// - @BCQ-fujimoto2019 -> docs/literature/tex-src/arXiv-BCQ/example_paper.tex:134-163, docs/literature/tex-src/arXiv-BCQ/example_paper.tex:406-426 (finite-batch extrapolation error and batch-constrained action selection)
// - @CQL-kumar2020 -> docs/literature/tex-src/arXiv-CQL/introduction.tex:3-12, docs/literature/tex-src/arXiv-CQL/method.tex:1-20 (offline distribution shift and conservative value learning)
// - @DoubleDQN-vanHasselt2015 -> docs/literature/tex-src/arXiv-Double-DQN/DoubleDQN_aaai2016_total.tex:112-124 (decoupled action selection and value evaluation)
// - @GenNBV-chen2024 -> docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:25-33, docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:40-49, docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:76-91 (5-DoF action, updated occupancy state, and coverage reward)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:14-18, docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:30-44, docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:99-129 (5-DoF MDP, state/visibility memory, and hierarchical action)


The representation ablation is an escalation ladder. Deep Sets and Set Transformer provide permutation-safe aggregation for unordered candidate rows, while query-centric encoding supplies local or relative coordinates @DeepSets-zaheer2017 @SetTransformer-lee2019 @zhou2023query. Point Transformer, KPConv, and Minkowski Engine cover point and sparse-grid alternatives @point-transformer-zhao2021 @KPConv-thomas2019 @MinkowskiEngine-choy2019. EGNN and the SE(3)-Transformer provide stronger equivariant alternatives @EGNN-satorras2021 @SE3Transformer-fuchs2020. Exact equivariance remains an ablation under the same actor-visible input, hard validity mask, and endpoint evaluation.

// evidence:
// - @DeepSets-zaheer2017 -> docs/literature/tex-src/arXiv-Deep-Sets/nips_2017.tex:103-106 (permutation-invariant set functions)
// - @SetTransformer-lee2019 -> docs/literature/tex-src/arXiv-Set-Transformer/03_main.tex:49-65 (permutation-equivariant set attention and pooling)
// - @zhou2023query -> docs/literature/tex-src/arXiv-QCNet/main.tex:159-161 (query-centric local spacetime frames, global-coordinate independence, and relative positions)
// - @point-transformer-zhao2021 -> docs/literature/tex-src/arXiv-Point-Transformer/tex/introduction.tex:1-4, docs/literature/tex-src/arXiv-Point-Transformer/tex/method.tex:21-27, docs/literature/tex-src/arXiv-Point-Transformer/tex/method.tex:55-62 (point-set structure, local neighborhoods, and relative position encoding)
// - @KPConv-thomas2019 -> docs/literature/tex-src/arXiv-KPConv/egpaper_final.tex:75-76, docs/literature/tex-src/arXiv-KPConv/egpaper_final.tex:98-99 (point-cloud convolutions and local kernel points)
// - @MinkowskiEngine-choy2019 -> docs/literature/tex-src/arXiv-MinkowskiEngine/sections/1_intro.tex:53-62 (sparse representation, predefined coordinates, and computational savings)
// - @EGNN-satorras2021 -> docs/literature/tex-src/arXiv-EGNN/sections/model.tex:6-20, docs/literature/tex-src/arXiv-EGNN/sections/model.tex:42-60 (relative-coordinate message passing and E(n) equivariance)
// - @SE3Transformer-fuchs2020 -> docs/literature/tex-src/arXiv-SE3-Transformer/EA4PC.tex:116-127, docs/literature/tex-src/arXiv-SE3-Transformer/EA4PC.tex:143-145 (SE(3)-equivariant attention and preserved relative positional information)

ARIA-NBV's niche is decision-specific: it combines target-conditioned endpoint quality, a finite masked candidate set, actor-visible Aria evidence, and offline value learning with an explicit oracle boundary @VIN-NBV-frahm2025 @EFM3D-straub2024 @BCQ-fujimoto2019. This remains a design hypothesis until horizon, support, target-discovery, and endpoint experiments establish headroom; no cited family establishes it alone.

// evidence:
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:36-44, docs/literature/tex-src/arXiv-VIN-NBV/sec/4_experiments.tex:43-47 (endpoint reconstruction quality and fixed candidate/coverage controls)
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/intro.tex:42-50 (actor-visible modalities versus GT annotations)
// - @BCQ-fujimoto2019 -> docs/literature/tex-src/arXiv-BCQ/example_paper.tex:146-163 (batch support and extrapolation limitation)

#figure(
  text(size: 8pt, table(
    columns: (1.15fr, 1.9fr, 2.0fr),
    toprule(),
    table.header([*Literature family*], [*Objective / target; action / horizon*], [*Actor-visible evidence / supervision / evaluation; ARIA boundary*]),
    midrule(),
    [Candidate / quality NBV @PB-NBV-jia2025 @VIN-NBV-frahm2025], [Coverage or reconstruction improvement; finite candidates, greedy one-step selection], [Current reconstruction and candidate views are actor-visible; coverage or GT-RRI supports evaluation. ARIA fixes support and tests endpoint target quality.],
    [Target-aware NBV + Aria substrate @ObjectCentricNBV-jeong2026 @projectaria-engel2023 @EFM3D-straub2024], [Target information gain or egocentric perception; candidate views versus sensor trajectories], [Calibrated streams and target records are actor-visible; masks, OBBs, and meshes stay on supervision/evaluation paths. ARIA keeps geometry oracle-side.],
    [Bounded planning + offline value learning @GenNBV-chen2024 @TrajectoryTransformer-janner2021 @BCQ-fujimoto2019], [Task reward or return/value estimate; multi-step sequences versus a fixed finite candidate horizon], [One masked support for horizon comparisons; report support, selection/evaluation split, and endpoint quality.],
    [Set/geometric encoders @DeepSets-zaheer2017 @zhou2023query @point-transformer-zhao2021 @EGNN-satorras2021], [Unordered candidate rows; local/relative geometry; point, sparse, or equivariant encoders], [Same actor-visible input, mask, provenance, and endpoint test; no backbone resolves target discovery.],
    bottomrule(),
  )),
  caption: [Four-family comparison of primary sources relevant to ARIA-NBV. Rows distinguish objective/target, action/horizon, actor-visible evidence, supervision/evaluation, and ARIA boundary.],
) <tab:related-work-comparison>

// evidence:
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/sections/related.tex:5-24, docs/literature/tex-src/arXiv-PB-NBV/jzz_2025_ral_resub.tex:55-70 (candidate decomposition and projection-based selection)
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:18-20, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:78-92 (greedy RRI prediction and quality objective)
// - @ObjectCentricNBV-jeong2026 -> docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:54-86, docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:123-139, docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:249-258 (object features, information gain, and target gate)
// - @projectaria-engel2023 -> docs/literature/tex-src/arXiv-project-aria/intro.tex:24-26, docs/literature/tex-src/arXiv-project-aria/device.tex:12-15 (egocentric multimodal and calibrated sensing)
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/intro.tex:42-50, docs/literature/tex-src/arXiv-EFM3D/dataset.tex:15-30 (Aria modalities, visibility/occlusion, OBBs, and meshes)
// - @GenNBV-chen2024 -> docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:25-33, docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:40-49, docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:76-91 (5-DoF action, updated occupancy state, and coverage reward)
// - @TrajectoryTransformer-janner2021 -> docs/literature/tex-src/arXiv-Trajectory-Transformer/text/method.tex:66-80, docs/literature/tex-src/arXiv-Trajectory-Transformer/text/method.tex:98-122 (receding-horizon and offline sequence planning)
// - @BCQ-fujimoto2019 -> docs/literature/tex-src/arXiv-BCQ/example_paper.tex:134-163, docs/literature/tex-src/arXiv-BCQ/example_paper.tex:406-426 (batch support and extrapolation risk)
// - @DeepSets-zaheer2017 -> docs/literature/tex-src/arXiv-Deep-Sets/nips_2017.tex:103-106 (permutation-invariant set functions)
// - @zhou2023query -> docs/literature/tex-src/arXiv-QCNet/main.tex:159-161 (local reference frames and relative positions)
// - @point-transformer-zhao2021 -> docs/literature/tex-src/arXiv-Point-Transformer/tex/method.tex:21-27, docs/literature/tex-src/arXiv-Point-Transformer/tex/method.tex:55-62 (local neighborhoods and learned relative position encoding)
// - @EGNN-satorras2021 -> docs/literature/tex-src/arXiv-EGNN/sections/model.tex:6-20, docs/literature/tex-src/arXiv-EGNN/sections/model.tex:42-60 (relative-coordinate E(n)-equivariant message passing)
