#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb

== Geometric and Mask Acceptance Tests <sec:thesis-method-geometry-contract>

// implementation evidence: vin/types/prediction.py; vin/modules/heads.py; tests/lightning/test_vin_batch_collate.py; tests/rollouts/test_zarr_store.py
Candidate order carries no task meaning. For a per-candidate scorer $f_theta$, jointly permuting row-aligned candidate inputs by $Pi$ should therefore permute the outputs by the same amount,

$
  f_theta(Pi X_t, Pi bold(m)_t) = Pi f_theta(X_t, bold(m)_t).
$

The current VINv3 scorer uses row-wise maps, shared-token queries, and symmetric normalization without candidate-index embeddings, so its deterministic evaluation graph has this structural property. Supporting tests verify that candidate shuffling preserves row-aligned poses, cameras, labels, and the padded tail, and the metric implementation explicitly inverse-aligns a supplied permutation. These tests validate the data and metric surfaces; they are not yet an end-to-end permutation test for a finite-horizon model.

Masks have two distinct meanings. The valid-action mask gates selection and any successor maximization, whereas the narrower training mask also requires a finite oracle target. The replay-store tests establish that the training mask is a subset of the valid-action mask, padding rows are invalid, invalid rewards remain `NaN`, and selected temporal-difference rewards equal the selected row's target root gain. A future #symb.rl.qh implementation must apply the valid-action mask to argmax, softmax, and bootstrap operations, use the training mask for supervised losses, and ensure that padded or invalid rows cannot change valid values.

Coordinate handling is deliberately weaker than a claim of exact $op("SE")(3)$ equivariance. The store retains world poses for reproducibility and root-relative poses for model construction. The current task is gravity-aligned and metric, so range, height, yaw, camera direction, target orientation, and motion constraints are physical variables rather than nuisances. Local relative features may reduce dependence on the arbitrary world origin, but no exact global-equivariance result is claimed @GeometricDeepLearning-bronstein2021.

Actor/oracle provenance is the final acceptance condition. Target gains, GT associations, mesh distances, rendered depth, and target crops may supervise or audit a model but may not enter its actor graph unless the experiment is explicitly labelled privileged. The replay schema and reason-code versions make this boundary inspectable. An implemented finite-horizon model will require its own source-dropout, row-permutation, mask-isolation, duplicate-row, and local-frame tests before architectural comparisons are scientifically interpretable.
