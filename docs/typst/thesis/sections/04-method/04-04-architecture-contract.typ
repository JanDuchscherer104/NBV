#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status
#import "@preview/booktabs:0.0.4": *

== Geometric and Mask Acceptance Tests <sec:thesis-method-geometry-contract>

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@GeometricDeepLearning-bronstein2021 @DeepSets-zaheer2017 @SetTransformer-lee2019 @FixedHorizonTD-deAsis2020],
  source: [#gh("aria_nbv/aria_nbv/vin/models/target_finite_horizon.py"); #gh("aria_nbv/tests/vin/test_target_finite_horizon.py"); #gh("aria_nbv/tests/rollouts/test_qh_reader.py")],
  gate: [end-to-end permutation, mask, duplicate, frame, source, and variable-horizon tests for every admitted state protocol],
)[The H=2 tracer covers candidate-row equivariance, local-frame geometry, invalid-row isolation, and deterministic selection. Dynamic selected-observation state, source-dropout, and variable-horizon acceptance tests remain pending.]

Candidate order carries no task meaning. For a per-candidate scorer $f_theta$, jointly permuting row-aligned inputs by $Pi$ must permute outputs by the same amount:

$
  #eqs.rl.candidate_row_equivariance
$

Equivariance alone does not guarantee invalid-row isolation. Holding valid rows and the mask fixed while changing only invalid-row contents must satisfy

$
  #eqs.rl.candidate_mask_isolation
$

Mask ownership depends on the interaction. In the canonical candidate-to-state model, candidates are queries and scene, target, history, and horizon context are keys and values. The action mask therefore sanitizes candidate queries, gates output selection, and gates supervised losses; it is not a key-padding mask for the shared state tokens. Candidate masks become attention-key masks only in later candidate-as-key architectures such as DeepSets context or a masked Set Transformer. Padding masks, action-validity masks, training masks, modality-presence masks, and horizon-availability masks must remain separate.

Duplicate-row and valid-count tests are required because candidate-set pooling or per-set normalization can otherwise change the absolute value of an unchanged physical candidate. A duplicate row may duplicate an output, but it must not silently change another row's value unless the tested architecture explicitly models candidate-set context.

Coordinate handling is deliberately weaker than exact $op("SE")(3)$ equivariance. World poses remain available for reproducibility, while model inputs use root-, target-, or candidate-relative geometry. Gravity, scale, height, yaw, camera direction, target orientation, motion limits, and frustum geometry remain physical variables. A global origin convention must not become a shortcut @GeometricDeepLearning-bronstein2021.

Actor/oracle provenance is the final acceptance condition. Target gains, GT associations, mesh distances, current candidate renders, and target crops may supervise or audit a model but may not enter its actor graph. Previously selected GT depth may enter only a `CF-GT` state branch. Source-dropout tests must show that removing an unavailable optional carrier changes only its masked branch.

The variable-horizon interface adds its own acceptance contract. The boundary query $h=0$ has value zero; an $h=1$ target contains no bootstrap; $h>b_t$ is rejected or masked rather than silently clamped; and a target for $h>1$ may depend only on a successor value requested at $h-1$ @FixedHorizonTD-deAsis2020. Vectorizing a horizon axis must reproduce independent calls for every admissible $h$, and candidate-row equivariance and mask isolation must hold separately at every horizon. Changing only $h$ may change values but must not expose future observations. Because a geometrically valid action may have negative immediate gain, monotonicity such as $Q_(h+1)>=Q_h$ is not imposed as a universal acceptance test.

=== Orthogonal architecture ladder

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@DeepSets-zaheer2017 @SetTransformer-lee2019 @zhou2023query @EGNN-satorras2021 @SE3Transformer-fuchs2020 @GATr-brehmer2023 @UVFA-schaul2015],
  source: [#gh("aria_nbv/aria_nbv/vin/models/target_finite_horizon.py"); #gh("docs/contents/theory/candidate_view_dependence.qmd")],
  gate: [promote a level only after lower interaction controls pass on the same scene carrier, target/source protocol, and horizon-query contract],
)[The development tracer implements candidate-to-state cross-attention over an `S0-pose` carrier. Scene-carrier upgrades from @tab:thesis-scene-representation-design-space and variable-horizon conditioning are orthogonal to the interaction ladder below.]

The canonical A1 query contains candidate-local information plus the requested-horizon condition: local pose, candidate--target relation, candidate-local support reads, and an embedding of $h$. Target, scene, ordered history, and any admitted budget context are supplied once as shared state tokens. Candidate provenance and generator-family identity are audit-only by default; using them as learned features requires a named ablation because they may encode generator shortcuts. A single conditional value approximator is preferred over unrelated per-horizon networks, while separate $Q_1,dots,Q_H$ heads remain a control for horizon interference @UVFA-schaul2015.

#figure(
  text(size: 8.2pt, table(
    columns: (0.45fr, 1.02fr, 1.63fr),
    toprule(),
    table.header([*Level*], [*Interaction model*], [*Scientific role*]),
    midrule(),
    [A0], [Independent masked MLP], [Locks target/candidate descriptors, masks, explicit horizon conditioning, and label learnability for a fixed scene carrier.],
    [A1], [Candidate-to-state cross-attention], [Each horizon--candidate query independently reads shared target, scene, history, and budget context.],
    [A2], [DeepSets candidate context], [Tests whether an unordered summary of valid candidates adds information without pairwise attention.],
    [A3], [Masked Set Transformer], [Tests candidate--candidate interaction while preserving row equivariance and mask isolation.],
    [A4], [Query-local relation bias], [Tests QCNet-style target, history, and candidate relations without importing its forecasting decoder.],
    [A5], [Temporal/recurrent state read], [Tests whether ordered long-horizon history remains informative after explicit dynamic scene memory.],
    [A6], [Residual value head], [Tests finite-horizon recovery over a calibrated continuous one-step root-gain control.],
    [A7+], [Exact-equivariant or graph interaction], [Escalates only after local-frame controls reveal a symmetry-related failure.],
    bottomrule(),
  )),
  caption: [Interaction-architecture ladder. Scene carrier, target/source protocol, horizon-query contract, and learning target are frozen independently for each comparison.],
) <tab:geometric-learning-ladder>

Candidate-to-candidate attention is not required by the core task. It may improve relative policy context or diversity, but unrelated sampled rows must not silently redefine the absolute value of candidate $q_(t,i)$. Exact equivariant layers are similarly scoped to diagnosed support encoders or candidate graphs after local-frame scalar controls. This ordering favors reusable context encodings: static scene tokens are computed once per root, target tokens once per target, candidate encodings once per candidate, and lightweight horizon--candidate queries independently for each requested $h$ before optional set interaction.
