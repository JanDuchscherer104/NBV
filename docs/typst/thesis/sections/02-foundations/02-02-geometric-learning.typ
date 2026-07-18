#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "@preview/booktabs:0.0.4": *

== Geometric Learning and Candidate-Set Theory <sec:thesis-geometric-learning-theory>

The learned object in ARIA-NBV is a typed finite-candidate decision map: given a target record, selected history, partial actor-visible geometry, and an unordered table of feasible candidate poses, assign one score to each candidate for selection under later oracle re-evaluation. The model must respect the symmetries and information boundary of this map before architectural capacity is interpreted @GeometricDeepLearning-bronstein2021.

The first required structure is candidate-row permutation equivariance. Reordering #symb.rl.candidate_table may reorder per-candidate #symb.rl.qh outputs, but it must not change the value assigned to the same physical candidate. Deep Sets supplies a pooled symmetry baseline, while Set Transformer supplies candidate interaction without assigning semantic meaning to row order @DeepSets-zaheer2017 @SetTransformer-lee2019. Both retain a row-level scoring path because the policy selects a candidate row.

For any permutation matrix $Pi$ acting on candidate rows, the value model should satisfy

$
  #eqs.rl.candidate_row_equivariance
$

where $bold(X)_t = {bold(x)_(t,i)}_(i=1)^(N_q)$ stores per-candidate actor-visible descriptors and $bold(m)_t$ stores validity. Invalid and padded rows are outside the admissible action set, not low-utility examples. Selection is therefore

$
  #eqs.rl.masked_candidate_selection
$

The second required structure is frame discipline. Candidate, target, current-camera, and history poses use reference- or query-local relative features such as $bold(T)^r_(c_q)$ and continuous rotation encodings @zhou2019continuity @zhou2023query. This prevents an arbitrary world origin or row order from becoming a shortcut while preserving gravity alignment and camera-frustum geometry. It is a controlled coordinate choice, not a claim of full global $op("SE")(3)$ invariance.

The third required structure is explicit selected-view history. A camera pose also defines a viewing direction from which target-local surfaces may or may not have been observed. A compact history on $bb(S)^2$ can therefore distinguish directional novelty from generic pose distance @e3nn-SphericalHarmonics-2025. Coverage, overlap, and uncertainty remain diagnostic features unless paired oracle evaluation shows that they improve target-specific @relative-reconstruction-improvement:short @SCONE-guedon2022 @FisherRF-jiang2024.

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

    [GT-defined tasks, meshes, crops, and all-candidate renders supervise data generation and evaluation only.], bottomrule(),
  ),
  caption: [Minimum geometric-learning contract for the finite-candidate value model.],
) <tab:geometric-learning-contract>

These requirements become replay-field and model acceptance tests in Chapter @sec:thesis-method-geometry-contract. Row shuffles must permute outputs, invalid-row perturbations must leave valid scores unchanged, and equivalent local-frame encodings must preserve physical candidate identity. Architectural comparisons are interpretable only after those contracts hold.
