#import "../../../shared/macros.typ": *

== Related Work

Next-best-view work exposes a tension between cheap coverage-oriented selection and endpoint reconstruction quality. PB-NBV makes the finite generate--score--select abstraction explicit: it samples candidate viewpoints because direct 6-DOF optimization is difficult, then evaluates candidates with a projection-based quality function and reports point-cloud coverage and computation time @PB-NBV-jia2025. VIN-NBV keeps the same sequential greedy candidate-selection structure for its coverage baseline, but replaces the coverage score with predicted Relative Reconstruction Improvement and evaluates reconstruction quality with point-level error @VIN-NBV-frahm2025. These results motivate a matched comparison, not a universal preference: ARIA-NBV treats coverage or one-step quality as a comparator and asks whether target-specific endpoint quality changes under the same finite candidate support.

// evidence:
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/sections/related.tex:17-24 (finite candidate proposal)
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/jzz_2025_ral_resub.tex:57-70 (projection selection and coverage objective)
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/4_experiments.tex:47-59 (coverage baseline and sequential greedy comparison)
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/4_experiments.tex:63-67 (oracle quality and endpoint metric)

Quality supervision creates a second tension: the label can use information that the actor must not receive. VIN-NBV defines an oracle variant by replacing the learned score with ground-truth RRI, making the distinction between a quality label and a decision-time observation explicit @VIN-NBV-frahm2025. EFM3D supplies the complementary egocentric substrate: Aria sequences, oriented-box metadata, calibrated spatial annotations, and ground-truth meshes support controlled supervision and evaluation @EFM3D-straub2024 @projectaria-engel2023. The resulting separation is useful for ARIA-NBV, but it does not solve target discovery: a geometry-defined target task can provide an oracle crop and label while a deployable actor would still need an observed or predicted target record.

// evidence:
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/4_experiments.tex:63-67 (ground-truth RRI oracle and evaluation)
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/dataset.tex:15-30 (egocentric data, OBB metadata, and ground-truth meshes)
// - @projectaria-engel2023 -> docs/literature/tex-src/arXiv-project-aria/device.tex:12-15 (egocentric multimodal sensors, calibration, and time alignment)
// - @projectaria-engel2023 -> docs/literature/tex-src/arXiv-project-aria/mps.tex:27-38 (spatial trajectories and time-varying calibration outputs)

Offline value learning exposes a third tension between a finite behavior-supported dataset and a learned lookahead maximum. CQL identifies distributional shift and bootstrapping from out-of-distribution actions as sources of optimistic value estimates, and its conservative objective is tied to the dataset action distribution @CQL-kumar2020. BCQ makes the same boundary operational by constraining selected actions toward those present in the batch @BCQ-fujimoto2019, while Double DQN separates action selection from action evaluation to reduce maximization bias @DoubleDQN-vanHasselt2015. For ARIA-NBV, these works support a bounded methodological question rather than a result: a learned finite-horizon scorer must be checked against logged candidate support and endpoint re-evaluation, because an extrapolated high value is not evidence of a better target endpoint.

// evidence:
// - @CQL-kumar2020 -> docs/literature/tex-src/arXiv-CQL/introduction.tex:3-12 (offline distribution shift and conservative values)
// - @CQL-kumar2020 -> docs/literature/tex-src/arXiv-CQL/method.tex:4-15 (OOD actions and dataset action distribution)
// - @BCQ-fujimoto2019 -> docs/literature/tex-src/arXiv-BCQ/example_paper.tex:400-402 (plausible batch actions, value selection, and rare-state penalty)
// - @DoubleDQN-vanHasselt2015 -> docs/literature/tex-src/arXiv-Double-DQN/DoubleDQN_aaai2016_total.tex:112-124 (selection/evaluation decoupling)

Representation capacity creates a fourth tension with the bounded evidence available to an egocentric actor. Deep Sets and Set Transformer provide permutation-aware processing for unordered candidate sets @DeepSets-zaheer2017 @SetTransformer-lee2019, while Point Transformer V3 and Minkowski sparse convolutions show two ways to increase point-cloud receptive field or compute only on occupied coordinates @PointTransformerV3-wu2024 @MinkowskiEngine-choy2019. EGNN adds translation, rotation, and permutation equivariance to coordinate-bearing graph features @EGNN-satorras2021. These mechanisms address order, geometry, or efficiency, but they do not supply observations that were never logged: in ARIA-NBV, richer encoders remain conditional ablations whose value must be established under the same actor-visible evidence, finite candidate table, and endpoint evaluation.

// evidence:
// - @DeepSets-zaheer2017 -> docs/literature/tex-src/arXiv-Deep-Sets/nips_2017.tex:103-106 (permutation-invariant set functions)
// - @SetTransformer-lee2019 -> docs/literature/tex-src/arXiv-Set-Transformer/03_main.tex:11-14 (set attention and higher-order interactions)
// - @SetTransformer-lee2019 -> docs/literature/tex-src/arXiv-Set-Transformer/03_main.tex:49-53 (permutation equivariance)
// - @PointTransformerV3-wu2024 -> docs/literature/tex-src/arXiv-Point-Transformer-V3/section/1_introduction.tex:10-18 (scalable point-cloud representation)
// - @MinkowskiEngine-choy2019 -> docs/literature/tex-src/arXiv-MinkowskiEngine/sections/1_intro.tex:53-62 (sparse coordinates, memory, and computation)
// - @EGNN-satorras2021 -> docs/literature/tex-src/arXiv-EGNN/sections/model.tex:6-15 (coordinate and permutation equivariance)
