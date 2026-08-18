#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status, prune_todo
#import "@preview/booktabs:0.0.4": *

== Geometric and Mask Acceptance Tests <sec:thesis-method-geometry-contract>

#prune_todo(
  [Retain acceptance properties only for the architecture that is actually implemented and evaluated. Proposed architecture alternatives belong in development notes until a measured failure motivates them.],
  source: [this section; scorer implementation and tests],
  gate: [one production scorer passes the stated permutation, masking, frame, and horizon tests],
)

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@GeometricDeepLearning-bronstein2021 @DeepSets-zaheer2017 @SetTransformer-lee2019 @FixedHorizonTD-deAsis2020],
  source: "aria_nbv/aria_nbv/data_handling/qh_data/views.py; aria_nbv/tests/lightning/test_qh_module.py; aria_nbv/tests/rollouts/test_qh_reader.py",
  gate: [production scorer plus end-to-end permutation, mask, duplicate, frame, source, and horizon tests for every admitted state protocol],
)[The replay and fitted-Q infrastructure covers row-aligned masks, local-frame tensors, selected-transition admission, and deterministic Double-Q selection for an injected scorer. No candidate-to-state architecture or scorer-level equivariance contract is implemented.]

Candidate order carries no task meaning. For a per-candidate scorer $f_theta$, jointly permuting row-aligned inputs by $Pi$ must permute outputs by the same amount:

$
  #eqs.rl.candidate_row_equivariance
$

Equivariance alone does not guarantee invalid-row isolation. Holding valid rows and the mask fixed while changing only invalid-row contents must satisfy

$
  #eqs.rl.candidate_mask_isolation
$

Mask ownership depends on the interaction. In the candidate-to-state design candidate, candidates are queries and scene, target, history, and time context are keys and values. The action mask therefore sanitizes candidate queries, gates output selection, and gates supervised losses; it is not a key-padding mask for the shared state tokens. Candidate masks become attention-key masks only in candidate-as-key architectures such as DeepSets context or a masked Set Transformer. Padding masks, action-validity masks, training masks, and modality-presence masks must remain separate; a horizon-availability mask is added only if explicit horizon queries are selected.

Duplicate-row and valid-count tests are required because candidate-set pooling or per-set normalization can otherwise change the absolute value of an unchanged physical candidate. A duplicate row may duplicate an output, but it must not silently change another row's value unless the tested architecture explicitly models candidate-set context.

Coordinate handling is deliberately weaker than exact $op("SE")(3)$ equivariance. World poses remain available for reproducibility, while model inputs use root-, target-, or candidate-relative geometry. Gravity, scale, height, yaw, camera direction, target orientation, motion limits, and frustum geometry remain physical variables. A global origin convention must not become a shortcut @GeometricDeepLearning-bronstein2021.

Actor/oracle provenance is the final acceptance condition. Target gains, GT associations, mesh distances, current candidate renders, and target crops may supervise or audit a model but may not enter its actor graph. Previously selected GT depth may enter only a `CF-GT` state branch. Source-dropout tests must show that removing an unavailable optional carrier changes only its masked branch.

If the explicit requested-horizon interface is selected, it adds its own acceptance contract: the boundary query $h=0$ has value zero; an $h=1$ target contains no bootstrap; $h>b_t$ is rejected or masked rather than clamped; and a target for $h>1$ may depend only on a successor value requested at $h-1$ @FixedHorizonTD-deAsis2020. Vectorizing a horizon axis must reproduce independent calls for every admissible $h$ without exposing future observations. The fixed-H alternative instead requires separate tests across configured horizons and remaining budgets. Neither design assumes monotonicity such as $Q_(h+1)>=Q_h$ because valid actions may have negative immediate gain.

=== Orthogonal architecture ladder

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@DeepSets-zaheer2017 @SetTransformer-lee2019 @zhou2023query @EGNN-satorras2021 @SE3Transformer-fuchs2020 @GATr-brehmer2023 @UVFA-schaul2015],
  source: "aria_nbv/aria_nbv/data_handling/qh_data/views.py; docs/contents/theory/candidate_view_dependence.qmd",
  gate: [freeze the scorer time-query contract, then promote a level only after lower interaction controls pass on the same scene carrier and target/source protocol],
)[No level in the interaction ladder is implemented for finite-horizon scoring. Scene-carrier choice, fixed-H versus requested-horizon conditioning, and candidate interaction are orthogonal decisions to test after the scorer boundary is frozen.]

The proposed A1 query contains candidate-local pose, candidate--target relation, and candidate-local support reads. Target, scene, ordered history, and remaining-budget context are supplied once as shared state tokens. The requested-horizon design candidate additionally embeds $h$; the fixed-H alternative does not. Candidate provenance and generator-family identity are audit-only by default. Shared conditional and separate-horizon models remain alternatives for the source-owner decision rather than a frozen architecture @UVFA-schaul2015.

#figure(
  text(size: 8.2pt, table(
    columns: (0.45fr, 1.02fr, 1.63fr),
    toprule(),
    table.header([*Level*], [*Interaction model*], [*Scientific role*]),
    midrule(),
    [A0], [Independent masked MLP], [Locks target/candidate descriptors, masks, time context, and label learnability for a fixed scene carrier.],
    [A1], [Candidate-to-state cross-attention], [Each candidate query independently reads shared target, scene, history, and budget context.],
    [A2], [DeepSets candidate context], [Tests whether an unordered summary of valid candidates adds information without pairwise attention.],
    [A3], [Masked Set Transformer], [Tests candidate--candidate interaction while preserving row equivariance and mask isolation.],
    [A4], [Query-local relation bias], [Tests QCNet-style target, history, and candidate relations without importing its forecasting decoder.],
    [A5], [Temporal/recurrent state read], [Tests whether ordered long-horizon history remains informative after explicit dynamic scene memory.],
    [A6], [Residual value head], [Tests finite-horizon recovery over a calibrated continuous one-step root-gain control.],
    [A7+], [Exact-equivariant or graph interaction], [Escalates only after local-frame controls reveal a symmetry-related failure.],
    bottomrule(),
  )),
  caption: [Planned interaction-architecture ladder. Scene carrier, target/source protocol, time-query contract, and learning target are frozen independently for each comparison.],
) <tab:geometric-learning-ladder>

Candidate-to-candidate attention is not required by the core task. It may improve relative policy context or diversity, but unrelated sampled rows must not silently redefine the absolute value of candidate $q_(t,i)$. Exact equivariant layers are similarly scoped to diagnosed support encoders or candidate graphs after local-frame scalar controls. This ordering favors reusable context encodings and keeps optional requested-horizon conditioning separate from candidate-set interaction.
