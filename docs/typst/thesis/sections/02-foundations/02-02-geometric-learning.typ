#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": *
#import "@preview/booktabs:0.0.4": *

== Geometric Learning and Candidate-Set Theory <sec:thesis-geometric-learning-theory>

The geometric-learning question in ARIA-NBV is not whether a more expressive scene backbone can be added to the system. The thesis object is a typed finite-candidate decision map: for a target task, selected history, partial geometry, and an unordered set of feasible candidate poses, predict which candidate will improve target reconstruction under oracle re-evaluation. The model should therefore match the symmetries of this map before it escalates to heavier point, sparse, recurrent, or equivariant modules @GeometricDeepLearning-bronstein2021.

The first required structure is candidate-row permutation equivariance. Reordering the rows of #symb.rl.candidate_table may reorder per-candidate #symb.rl.qh outputs, but it must not change the value assigned to the same physical candidate. Candidate-to-state queries are therefore the first context mechanism: each candidate reads the same target, map, history, budget, and local-EVL state tokens. Deep Sets supplies the minimal pooled context baseline for unordered candidate and support sets, while Set Transformer supplies masked candidate-candidate interaction once independent and candidate-to-state controls are calibrated @DeepSets-zaheer2017 @SetTransformer-lee2019. The thesis should not replace the row path with only a pooled scene embedding, because the policy selects a candidate row.

The minimum algebraic contract is therefore a row-wise map over a masked set. For any permutation matrix $Pi$ acting on candidate rows, the value model should satisfy

$
  #eqs.rl.candidate_row_equivariance
$

where $bold(X)_t = {bold(x)_(t,i)}_(i=1)^(N_q)$ stores per-candidate actor-visible descriptors and $bold(m)_t$ stores validity. Invalid rows are not low-quality actions; they are outside the admissible set. A masked scorer must therefore compute selection over

$
  #eqs.rl.masked_candidate_selection
$

The local-frame contract is a controlled gauge choice rather than a full invariance claim. Candidate features may use transforms such as $bold(T)^r_(c_q)$, target-relative bearings, and query-local relative encodings so that a global origin change does not change the physical row identity, while gravity alignment and camera-frustum geometry remain available task structure @zhou2019continuity @zhou2023query.

The second required structure is gauge discipline. Candidate, target, current camera, and selected-history poses should be encoded in local frames, with continuous rotation representations and query-local relative positional features where needed @zhou2019continuity @zhou2023query. This borrows the useful part of query-centric trajectory models: local relations and relative encodings. It does not import their forecasting decoder, road-agent priors, or online streaming claims. Full global $op("SE")(3)$ equivariance is also not the right default because the task is gravity aligned, camera-frustum limited, and tied to egocentric acquisition. Exact equivariant networks remain ablations for support encoders or candidate graphs, not the core claim @EGNN-satorras2021 @SE3Transformer-fuchs2020.

The third required structure is directional visibility memory. A candidate view is not only a posed pinhole pose; it is a directional field from which target-local surface regions may or may not have been observed. This suggests storing selected-view history on $bb(S)^2$ through a histogram, a second-moment summary, or low-order spherical harmonics before more specialized equivariant layers are introduced @e3nn-SphericalHarmonics-2025. Coverage and information-gain methods motivate support, overlap, and uncertainty features, but those features remain diagnostic channels unless they improve target-specific oracle @relative-reconstruction-improvement:short under the paired evaluation protocol @SCONE-guedon2022 @FisherRF-jiang2024.

#figure(
  table(
    columns: (0.82fr, 1.12fr, 1.28fr),
    toprule(),
    table.header([*Object*], [*Required structure*], [*Testable consequence*]),
    midrule(), [Candidate rows], [Permutation-equivariant per-row value map.],
    [Row-shuffle tests must satisfy $f_theta(Pi X, Pi m)=Pi f_theta(X, m)$ for every selection score.],
    [Invalid and padded rows],
    [Hard mask isolation.],

    [Invalid rows cannot change valid-row scores except through explicit valid-count or support features.],
    [Candidate-target geometry],
    [Target-local and candidate-local relative pose features.],

    [World-frame origin, yaw convention, and display-only camera transforms cannot become shortcuts.],
    [Selected-view history],
    [Directional memory on $bb(S)^2$.],

    [Novelty tests separate already-observed target directions from generic pose distance.],
    [Actor/oracle boundary],
    [Typed provenance for target descriptors, labels, and support features.],

    [@ground-truth:short meshes, crops, and all-candidate renders supervise labels/evaluation only.], bottomrule(),
  ),
  caption: [Minimum geometric-learning contract for the finite-candidate value model.],
) <tab:geometric-learning-contract>

This contract implies an architecture ladder with conservative attribution. The independent scorer tests whether candidate self-features already solve the target task. Candidate-to-state cross-attention tests whether fixed target, map, history, and budget tokens explain finite-horizon value without candidate-candidate coupling. A pooled DeepSets context tests whether valid-set summaries help without pairwise attention. A masked Set Transformer tests candidate-candidate interaction. QCNet-style relative positional encoding tests whether local candidate-target/history relations are the missing signal. Directional support and overlap biases test whether visibility memory or surface-support hypotheses add value. Only after these controls pass should point backbones, sparse convolutions, exact equivariant graphs, or looped refinement be treated as thesis-relevant architecture changes @PointNeXt-qian2022 @PointTransformerV3-wu2024 @KPConv-thomas2019 @MinkowskiEngine-choy2019 @dejaviewloopingtransformersburzio2026.

#figure(
  table(
    columns: (0.52fr, 1.02fr, 1.45fr),
    toprule(),
    table.header([*Level*], [*Model*], [*Scientific role*]),
    midrule(),
    [A0],
    [Independent candidate scorer],
    [Locks target/candidate descriptors, CORAL calibration, and one-step ranking before context is added.],

    [A1], [Candidate-to-state query], [Tests fixed target, map, history, budget, and local-EVL context while preserving a per-candidate row path.],
    [A2], [Pooled DeepSets context], [Tests unordered valid-set summaries while preserving a per-candidate row path.],
    [A3],
    [Masked Set Transformer],
    [Tests candidate-candidate interaction under row-shuffle and mask-isolation checks.],

    [A4],
    [Query-local relative encoding],
    [Adapts QCNet-style local RPE for candidate-target, candidate-candidate, and selected-history relations.],

    [A5],
    [Directional/support bias],
    [Tests visibility memory, target-frustum support, overlap, and uncertainty as features rather than proxy rewards.],

    [A6],
    [Uncentred residual #symb.rl.qh],
    [Tests finite-horizon recovery in continuous return units over the calibrated myopic scorer with masked Double-Q backups.],

    [A7+],
    [Point/sparse/exact-equivariant/recurrent encoders],
    [Escalates only if compact descriptors bottleneck target-RRI ranking or #symb.rl.qh recovery.],

    [B0],
    [Online candidate-table refresh],
    [Bridge level after offline #symb.rl.qh evidence: tests whether the same finite-action contract survives streaming candidate regeneration.],

    [B1],
    [Continuous policy / simulator controller],
    [Post-thesis bridge only unless finite candidates fail; requires a separate action-parameterization, safety, and simulator-realism gate.],

    bottomrule(),
  ),
  caption: [Architecture ladder used to keep geometric-learning claims attributable.],
) <tab:geometric-learning-ladder>

The active method turns this theory into concrete replay fields, descriptor versions, and acceptance tests in Chapter @sec:thesis-method-geometry-contract. The literature review uses the same split: independent scoring and candidate-to-state queries are immediate model controls; Deep Sets, Set Transformer, and query-local relative encoding are interaction ablations; point, sparse, exact-equivariant, radiance-field, and recurrent models are scoped representation ablations or bridge work until the finite-candidate target-RRI protocol is stable.

#validation_todo(
  [Add measured row-shuffle, mask-isolation, duplicate-row, frame-transform, and valid-count stress-test results before claiming any geometric-learning module improves #symb.rl.qh.],
  source: [autoresearch thesis-lit-review report; docs/contents/theory/candidate_view_dependence.qmd],
  gate: [architecture ablation evidence],
)
