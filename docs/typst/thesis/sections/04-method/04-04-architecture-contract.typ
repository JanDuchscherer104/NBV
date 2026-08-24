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
  source: "aria_nbv/aria_nbv/vin/models/target_finite_horizon.py; aria_nbv/aria_nbv/vin/modules/qh_state_fusion.py; aria_nbv/aria_nbv/lightning/qh_module.py; aria_nbv/tests/vin/test_qh_state_fusion.py; aria_nbv/tests/vin/test_target_finite_horizon.py; aria_nbv/tests/lightning/test_qh_module.py",
  gate: [retain permutation, subset, duplicate, padding, mask-independence, frame, source, and horizon tests for every admitted state protocol],
)[The implemented A0/A1 scorer uses independent candidate rows, candidate-relative target/current-pose geometry, scalar requested horizons, and adapter-owned hard masks. Permutation, duplicate, invalid-row isolation, mask independence, and horizon bounds are unit-tested for the shared public contract; scientific policy evidence and richer state protocols remain pending.]

Candidate order carries no task meaning. For a per-candidate scorer $f_theta$, jointly permuting row-aligned inputs by $Pi$ must permute outputs by the same amount:

$
  #eqs.rl.candidate_row_equivariance
$

Equivariance alone does not guarantee invalid-row isolation. Holding valid rows and the mask fixed while changing only invalid-row contents must satisfy

$
  #eqs.rl.candidate_mask_isolation
$

Mask ownership depends on the interaction. In implemented A0, each materialized candidate row is concatenated with the same five named state tokens and processed independently. In A1, materialized candidates are queries while scene, target, history, budget, and requested-horizon context are keys and values. `candidate_mask` sanitizes padding before either fusion. Neither scorer reads `action_mask`; Lightning uses it for Q-loss and bootstrap support, and online inference uses it for the final selectable set. Candidate masks become attention-key masks only in candidate-as-key architectures such as DeepSets context or a masked Set Transformer. Padding, action validity, Q-label support, feasibility-label support, and modality presence remain separate.

Duplicate-row and valid-count tests are required because candidate-set pooling or per-set normalization can otherwise change the absolute value of an unchanged physical candidate. A duplicate row may duplicate an output, but it must not silently change another row's value unless the tested architecture explicitly models candidate-set context.

Coordinate handling is deliberately weaker than exact $op("SE")(3)$ equivariance. World poses remain available for reproducibility, while model inputs use root-, target-, or candidate-relative geometry. Gravity, scale, height, yaw, camera direction, target orientation, motion limits, and frustum geometry remain physical variables. A global origin convention must not become a shortcut @GeometricDeepLearning-bronstein2021.

Actor/oracle provenance is the final acceptance condition. Target gains, GT associations, mesh distances, current candidate renders, and target crops may supervise or audit a model but may not enter its actor graph. Previously selected GT depth may enter only a `CF-GT` state branch. Source-dropout tests must show that removing an unavailable optional carrier changes only its masked branch.

The scalar requested-horizon interface adds its own acceptance contract: the mathematical boundary $Q_0=0$ is represented only by padded rows in the executable call; an $h=1$ target contains no bootstrap; $h>b_t$ is rejected rather than clamped; and a target for $h>1$ may depend only on a successor value requested at $h-1$ @FixedHorizonTD-deAsis2020. Public vectorization remains gated on real atomic callers, measured inadequacy of private batching, and scalar/vector parity tests. No monotonicity such as $Q_(h+1)>=Q_h$ is assumed because valid actions may have negative immediate gain.

=== Orthogonal architecture ladder

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@DeepSets-zaheer2017 @SetTransformer-lee2019 @zhou2023query @EGNN-satorras2021 @SE3Transformer-fuchs2020 @GATr-brehmer2023 @UVFA-schaul2015],
  source: "aria_nbv/aria_nbv/data_handling/qh_data/views.py; docs/contents/theory/candidate_view_dependence.qmd",
  gate: [measure identical-feature A0 versus A1 under the same fit/evaluation contract, then promote a level only after lower interaction controls pass on the same scene carrier and target/source protocol],
)[A0 independent-row MLP and A1 candidate-to-state cross-attention are implemented over the same `S0-pose` root-moments inputs and decoder seam. A1 remains the default; comparative evidence, richer scene carriers, and candidate interaction remain orthogonal measurements.]

The shared A0/A1 query contains root- and current-relative candidate pose, an explicit candidate--target transform, and global root-scene moments. Target, scene, causal pose-history summary, remaining budget, and requested horizon are supplied as the same ordered state-token tuple. A0 maps `[query; vec(tokens)]` to one context with a row-shared MLP; A1 maps the query and tuple to the same context width with cross-attention. Both then expose `[query; context; query times context]` to the configured value decoder. This is feature matching, not parameter matching; every comparison reports parameters, runtime, and the frozen decoder/training identity. The physical trunk and feasibility head precede target/horizon conditioning. Candidate provenance and generator-family identity remain audit-only by default. Ordered history tokens and spatial scene memory replace internal representations behind the same scorer interface when their ablations justify the added capacity @UVFA-schaul2015.

#figure(
  text(size: 8.2pt, table(
    columns: (0.45fr, 1.02fr, 1.63fr),
    toprule(),
    table.header([*Level*], [*Interaction model*], [*Scientific role*]),
    midrule(),
    [A0], [Independent per-row MLP], [Locks target/candidate descriptors, time context, and label learnability for a fixed scene carrier; adapters retain hard masks.],
    [A1], [Candidate-to-state cross-attention], [Each candidate query independently reads shared target, scene, history, and budget context.],
    [A2], [DeepSets candidate context], [Tests whether an unordered summary of valid candidates adds information without pairwise attention.],
    [A3], [Masked Set Transformer], [Tests candidate--candidate interaction while preserving row equivariance and mask isolation.],
    [A4], [Query-local relation bias], [Tests QCNet-style target, history, and candidate relations without importing its forecasting decoder.],
    [A5], [Temporal/recurrent state read], [Tests whether ordered long-horizon history remains informative after explicit dynamic scene memory.],
    [A6], [Residual value head], [Tests finite-horizon recovery over a calibrated continuous one-step root-gain control.],
    [A7+], [Exact-equivariant or graph interaction], [Escalates only after local-frame controls reveal a symmetry-related failure.],
    bottomrule(),
  )),
  caption: [Interaction-architecture ladder. A0 and A1 are implemented; scene carrier, target/source protocol, time-query contract, decoder, and learning target stay fixed for their comparison.],
) <tab:geometric-learning-ladder>

Candidate-to-candidate attention is not required by the core task. It may improve relative policy context or diversity, but unrelated sampled rows must not silently redefine the absolute value of candidate $q_(t,i)$. Exact equivariant layers are similarly scoped to diagnosed support encoders or candidate graphs after local-frame scalar controls. This ordering favors reusable context encodings and keeps scalar requested-horizon conditioning separate from candidate-set interaction.
