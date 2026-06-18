#import "../../shared/macros.typ": *
#import "@preview/booktabs:0.0.4": *

== Related Work

ARIA-NBV sits between classical view planning, learned reconstruction-quality scoring, and egocentric scene understanding. Classical @next-best-view work formalizes the generate-score-select loop for three-dimensional inspection and reconstruction, while submodular and adaptive-submodular active-sensing results explain why greedy policies can be strong when the utility has diminishing returns @ViewPlanningSurvey-scott2003 @KrauseSensorPlacement2008 @AdaptiveSubmodularity-golovin2011. This thesis uses that lineage as a baseline discipline rather than as a theorem claim: target-specific @relative-reconstruction-improvement depends on masks, object matching, candidate regeneration, occlusion, and changing support, so coverage-style approximation guarantees are treated as motivation for greedy controls, not as properties of the ARIA objective.

The closest objective precedent is VIN-NBV, which learns to rank sampled candidate views by oracle @relative-reconstruction-improvement instead of by pure coverage @VIN-NBV-frahm2025. ARIA-NBV keeps that reconstruction-quality signal but changes both the state and the unit of evaluation. The actor-visible state comes from Project Aria-style egocentric streams and @aria-synthetic-environments assets @projectaria-engel2023 @ProjectAria-ASE-2025, and the thesis target is @target-specific-rri rather than only scene-level gain. CORAL-style ordinal learning is therefore useful for a calibrated one-step scorer, but it is a control for label reliability and ranking, not the whole finite-horizon planning result @CORAL-cao2019.

Project Aria, @aria-synthetic-environments, and @egocentric-foundation-model-3d supply the substrate for this thesis. Project Aria defines the multimodal egocentric sensor regime and calibration assumptions, @aria-synthetic-environments provides mesh-supervised synthetic trajectories and annotations, and EFM3D/@egocentric-voxel-lifting contributes actor-visible local voxel evidence, lifted image features, and object hypotheses @projectaria-engel2023 @ProjectAria-ASE-2025 @EFM3D-straub2024. The thesis does not treat @egocentric-voxel-lifting as a complete world model. Its role is local target/support evidence; broader scene memory is represented through semi-dense or fused point support and, if needed, separate point-attached feature banks.

Coverage and information-based @next-best-view methods provide useful diagnostic channels but not the primary reward. SCONE and MACARONS estimate surface visibility or coverage from learned scene representations, while FisherRF and Next Best Sense use information gain and uncertainty in radiance-field or Gaussian-splatting settings @SCONE-guedon2022 @MACARONS-guedon2023 @FisherRF-jiang2024 @NextBestSense-strong2024. ARIA-NBV can adopt support, overlap, uncertainty, and directional-history features from this family, but the thesis compares those proxies against @target-specific-rri rather than replacing the mesh-supervised label. Object-centric and semantic Gaussian-splatting work similarly motivates target-aware utility and semantic failure analysis, while remaining a bridge once the mesh/oracle target protocol is stable @ObjectCentricNBV-jeong2026 @GaussianSplatting-kerbl2023.

Continuous-policy @next-best-view papers define an important boundary for the thesis. GenNBV learns a generalizable continuous policy for active reconstruction, PB-NBV emphasizes efficient projection-based candidate scoring, and Hestia introduces a hierarchical target-then-pose formulation with directional observability @GenNBV-chen2024 @PB-NBV-jia2025 @Hestia-lu2026. These works motivate later actor-critic, projection-shortlist, and hierarchy experiments. The core thesis remains narrower: finite candidate tables over @aria-synthetic-environments snippets, oracle target labels from @ground-truth-target-evaluation, and a masked #symb.rl.qh model whose selected actions are re-evaluated by the same oracle.

The planned value model also borrows structure from set and geometric learning. Deep Sets gives the minimum symmetry contract for unordered candidate or point sets; Set Transformer supplies masked candidate-candidate interaction; and query-centric trajectory forecasting motivates local relative positional encodings without importing a motion-forecasting decoder @DeepSets-zaheer2017 @SetTransformer-lee2019 @zhou2023query. Geometric deep learning frames the broader design question as matching model symmetries to the output map, not making the whole system invariant @GeometricDeepLearning-bronstein2021. For ARIA-NBV this means candidate-row permutation equivariance for #symb.rl.qh scores, mask isolation for invalid rows, explicit target/current/candidate frames, and gravity-aware rather than full rotation-invariant features. Section @sec:thesis-geometric-learning-theory turns those literature roles into the architecture ladder and acceptance tests.

Point and sparse scene encoders are best treated as representation ablations after the simpler support contract is measured. Point Transformer, PointNeXt, Point Transformer V3, KPConv, and sparse-convolutional encoders offer local geometric interaction, density handling, scalability, or sparse-volume computation @point-transformer-zhao2021 @PointNeXt-qian2022 @PointTransformerV3-wu2024 @KPConv-thomas2019 @MinkowskiEngine-choy2019. They become relevant if compact target, frustum, support, and lifted-feature pools leave a measurable bottleneck for @target-specific-rri ranking or finite-horizon #symb.rl.qh. They are not first-line replacements for EFM3D because a thesis backbone must still provide actor-visible OBB hypotheses and reusable scene conditioning.

Finally, offline and recurrent decision-modeling papers inform the training and ablation ladder without changing the problem definition. Double DQN and dueling heads motivate selector/evaluator separation and value/advantage structure for finite candidate tables @DoubleDQN-vanHasselt2015 @DuelingDQN-wang2016. IQL, CQL, and BCQ motivate explicit support constraints and skepticism about out-of-distribution bootstrapping, not an immediate switch away from the finite-candidate replay contract @IQL-kostrikov2021 @CQL-kumar2020 @BCQ-fujimoto2019. Trajectory Transformer, Decision Transformer, and Gumbel-Top-k provide vocabulary for sequence modeling, return conditioning, and stochastic branch generation only after the target/candidate/mask/evaluation contract is shared with the simpler baselines @TrajectoryTransformer-janner2021 @DecisionTransformer-chen2021 @GumbelTopK-kool2019. Deja View suggests a bounded weight-tied refinement ablation for candidate-context tokens, but not a claim that reconstruction-loop recurrence transfers directly to ARIA-NBV planning @dejaviewloopingtransformersburzio2026.

#figure(
  table(
    columns: (1.0fr, 1.45fr, 1.45fr),
    toprule(),
    table.header([*Literature family*], [*Useful contribution*], [*ARIA-NBV boundary*]),
    midrule(),
    [VIN-NBV and ordinal scoring],
    [Oracle @relative-reconstruction-improvement labels, one-step candidate ranking, and CORAL-style calibration.],
    [Adopt as target-specific label/scorer controls; do not stop at myopic ranking if oracle lookahead exposes headroom.],
    [Aria, ASE, EFM3D/@egocentric-voxel-lifting],
    [Egocentric streams, calibration, semi-dense support, local voxel evidence, and OBB hypotheses.],
    [Use as actor-visible substrate; keep @ground-truth:short meshes and target crops for labels/evaluation only.],
    [SCONE, MACARONS, FisherRF, 3DGS NBV],
    [Coverage, support, uncertainty, information gain, and directional novelty channels.],
    [Use as diagnostics or candidate-token features; do not replace @target-specific-rri as the thesis objective.],
    [Set/geometric models],
    [Permutation structure, masked attention, query-local relative encodings, and typed symmetry tests.],
    [Use for finite-candidate #symb.rl.qh controls before point/sparse backbone escalation.],
    [Continuous and recurrent bridges],
    [GenNBV/Hestia continuous or hierarchical policies; Deja View-style refinement.],
    [Defer to bridge/ablation work after finite-candidate labels, masks, and replay are trustworthy.],
    bottomrule(),
  ),
  caption: [Adopted roles and explicit boundaries for the literature used by the thesis.],
) <tab:related-work-roles>
