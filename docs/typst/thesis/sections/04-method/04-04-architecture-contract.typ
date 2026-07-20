#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status
#import "@preview/booktabs:0.0.4": *

== Geometric and Mask Acceptance Tests <sec:thesis-method-geometry-contract>

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@GeometricDeepLearning-bronstein2021 @DeepSets-zaheer2017 @SetTransformer-lee2019],
  source: "aria_nbv/aria_nbv/vin/types/prediction.py; aria_nbv/aria_nbv/vin/modules/heads.py; aria_nbv/tests/lightning/test_vin_batch_collate.py; aria_nbv/tests/rollouts/test_zarr_store.py",
  gate: [end-to-end finite-horizon permutation, mask, duplicate, and frame tests],
)[Replay and current VIN data surfaces cover part of the contract. The unimplemented finite-horizon model must pass the complete suite before architectural comparisons are interpretable.]

Candidate order carries no task meaning. For a per-candidate scorer $f_theta$, jointly permuting row-aligned inputs by $Pi$ must permute outputs by the same amount:

$
  #eqs.rl.candidate_row_equivariance
$

The current VIN path uses row-wise maps, shared-token queries, and symmetric normalization without candidate-index embeddings. Existing tests verify row-aligned collation and metric alignment, not an end-to-end finite-horizon equivariance claim.

Equivariance alone does not guarantee invalid-row isolation. Holding valid rows and the mask fixed while changing only invalid-row contents must satisfy

$
  #eqs.rl.candidate_mask_isolation
$

The valid-action mask gates selection, softmax, and successor maximization. The narrower training mask also requires a finite oracle target. Padding, invalid rows, and their undefined labels must not alter valid outputs or gradients. Duplicate-row and valid-count tests are required because attention normalization or per-set centering can otherwise change the absolute value of an unchanged physical candidate.

Coordinate handling is deliberately weaker than exact $op("SE")(3)$ equivariance. World poses remain available for reproducibility, while model inputs use root-, target-, or candidate-relative geometry. Gravity, scale, height, yaw, camera direction, target orientation, motion limits, and frustum geometry remain physical variables. A global origin convention must not become a shortcut @GeometricDeepLearning-bronstein2021.

Actor/oracle provenance is the final acceptance condition. Target gains, GT associations, mesh distances, rendered depth, and target crops may supervise or audit a model but may not enter its actor graph unless the experiment is explicitly privileged. Source-dropout tests must show that removing an unavailable optional carrier changes only its masked branch.

=== Conservative architecture ladder

#thesis_status(
  implementation: "planned",
  evidence: "pending",
  citation: [@DeepSets-zaheer2017 @SetTransformer-lee2019 @zhou2023query @EGNN-satorras2021 @SE3Transformer-fuchs2020 @GATr-brehmer2023],
  source: "docs/literature/tex-src/arXiv-Deep-Sets/nips_2017.tex; docs/literature/tex-src/arXiv-Set-Transformer/03_main.tex, Sec. Set Transformer, lines 2--51; docs/literature/tex-src/arXiv-QCNet/main.tex, Sec. Query-Centric Scene Encoder, lines 159--161; docs/literature/tex-src/arXiv-SE3-Transformer/EA4PC.tex, Sec. Introduction, lines 119--143; docs/contents/theory/candidate_view_dependence.qmd",
  gate: [promote a level only after all lower controls pass the same oracle-evaluated protocol],
)[The ladder orders hypotheses; it does not assign equal status to every model family. Candidate-to-state attention is the canonical planned core.]

#figure(
  text(size: 8.2pt, table(
    columns: (0.45fr, 1.02fr, 1.63fr),
    toprule(),
    table.header([*Level*], [*Model*], [*Scientific role*]),
    midrule(),
    [A0], [Independent masked MLP], [Locks reader, target/candidate descriptors, masks, and one-step or finite-horizon label learnability.],
    [A1], [Candidate-to-state cross-attention], [Canonical planned model: each candidate independently queries shared target, scene, history, budget, step, and horizon tokens.],
    [A2], [DeepSets context], [Tests whether unordered summaries of valid candidates add information without pairwise attention.],
    [A3], [Masked Set Transformer], [Tests candidate-candidate interaction while preserving row equivariance and mask isolation.],
    [A4], [Query-local relation bias], [Tests QCNet-style target, history, and candidate relations without importing its forecasting decoder.],
    [A5], [Directional/support memory], [Tests target-local view novelty, target-frustum support, overlap, and uncertainty as features.],
    [A6], [Uncentred residual $Q_H$], [Tests finite-horizon recovery over a calibrated myopic control in continuous return units.],
    [A7+], [Point, sparse, recurrent, or exact-equivariant encoder], [Escalates only if compact scene descriptors demonstrably bottleneck ranking or recovery.],
    bottomrule(),
  )),
  caption: [Architecture ladder for attributable geometric-learning claims.],
) <tab:geometric-learning-ladder>

Candidate-to-candidate attention is therefore not required by the core task. It may improve relative policy context or diversity, but unrelated sampled rows must not silently redefine the absolute value of candidate $q_(t,i)$. Exact equivariant layers are similarly scoped to support encoders or candidate graphs after local-frame scalar controls. This order favors reusable scene and target encodings: target-independent scene tokens are computed once, target tokens once per target, and candidate queries independently per candidate before optional set interaction.
