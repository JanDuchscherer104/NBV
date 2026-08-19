#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status, research_todo, prune_todo
#import "@preview/booktabs:0.0.4": *

== Geometric Learning and Candidate-Set Theory <sec:thesis-geometric-learning-theory>

#prune_todo(
  [Separate method-independent requirements that the final scorer must satisfy from speculative representation ladders and curricula. Retain only theory that is tested by the frozen method or needed to interpret its failures.],
  source: [this section and @sec:thesis-method],
  gate: [one implemented scorer contract and matching acceptance tests determine the surviving theory],
)

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
    [Separate feasibility head, trained on every non-padding row; RRI/value loss only on rows certified valid. Hard action masking is the initial policy, with a later calibrated soft feasibility gate.],

    [Invalid rows cannot change valid-row scores except through explicit valid-count or support features.],
    [Candidate-target geometry],
    [Target-local and candidate-local relative pose features.],

    [World-frame origin, yaw convention, and display-only camera transforms cannot become shortcuts.],
    [Selected-view history],
    [Directional memory on $bb(S)^2$.],

    [Novelty tests separate already-observed target directions from generic pose distance.],
    [Actor/oracle boundary],
    [Typed provenance for target descriptors, labels, and support features.],

    [GT-defined tasks, meshes, crops, and all-candidate renders supervise data generation and evaluation only.],
    bottomrule(),
  ),
  caption: [Minimum geometric-learning contract for the finite-candidate value model.],
) <tab:geometric-learning-contract>

The implemented hard mask defines $m_(t,i)=0$ as exclusion from the action set, not as a numerical return. An invalid row's RRI is undefined: it must be neither forced to zero nor assigned a synthetic negative target, because zero can be a legitimate valid-row RRI and either choice would conflate feasibility with quality.

#thesis_status(
  implementation: "planned",
  evidence: "pending",
  citation: [@SelectiveNet-geifman2019 @DeepGamblers-liu2019],
  source: "aria_nbv/aria_nbv/rollouts/zarr_store.py; planned finite-horizon scorer",
  gate: [implement feasibility head and evaluate held-out calibration without weakening the hard mask],
)[A separate feasibility head is planned. It is not part of the current scorer or training module.]

For each non-padding row, the planned model emits a feasibility probability and an RRI/value estimate. Binary cross-entropy supplies negative evidence on invalid rows, while the RRI loss is evaluated only when $m_(t,i)=1$. This factorization treats feasibility as a reject decision rather than an artificial low-RRI target.

The hard mask remains the deployment safety constraint. A soft feasibility score is only a training and ranking ablation: after held-out feasibility calibration, compare a score proportional to predicted validity times the conditional valid-row value against the hard-mask baseline, while retaining the hard mask wherever it is available. The abstention literature likewise models rejection as a separate outcome rather than a continuous-regression target @DeepGamblers-liu2019. The curriculum hypothesis is therefore to train feasibility from the first batch, warm up the value head only on oracle-valid rows, and then introduce the calibrated soft-gate ablation @CurriculumLearning-bengio2009. It must never reintroduce an RRI target or RRI gradient for invalid rows.

#research_todo(
  [Compare hard masking against a calibrated feasibility-times-value ranking only after feasibility calibration is measured. The hard mask remains the safety constraint in every comparison.],
  source: [invalid-row supervision hypothesis],
  gate: [feasibility calibration and policy ablation],
)

These requirements become replay-field and model acceptance tests in Chapter @sec:thesis-method-geometry-contract. Row shuffles must permute outputs, invalid-row perturbations must leave valid scores unchanged, and equivalent local-frame encodings must preserve physical candidate identity. Architectural comparisons are interpretable only after those contracts hold.
