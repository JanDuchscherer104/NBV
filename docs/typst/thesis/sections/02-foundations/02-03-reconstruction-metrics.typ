#import "../../../shared/macros.typ": *

== Reconstruction Quality Metrics <sec:thesis-reconstruction-metrics>

Let $cal(P)$ be samples from a reconstructed surface, $cal(M)$ a reference mesh, and $cal(S)$ a declared sample of that mesh. The distance from a point to target geometry $cal(A)$ is

$
  d(bold(x), cal(A)) = min_(bold(y) in cal(A)) norm(bold(x) - bold(y))_2.
$

It induces two directed errors,

$
  d_"acc"(cal(P) arrow.r cal(M)) =
  (1)/(abs(cal(P))) sum_(bold(p) in cal(P)) d(bold(p), cal(M)),
  quad
  d_"comp"(cal(M) arrow.r cal(P)) =
  (1)/(abs(cal(S))) sum_(bold(s) in cal(S)) d(bold(s), cal(P)).
$

Accuracy exposes unsupported or extraneous reconstructed geometry; completeness reverses the comparison and exposes missing geometry. Neither direction alone characterizes both failure modes.

A symmetric score can sum or average the two directed terms. This is often called a Chamfer-style distance, but the name does not make different formulations interchangeable: the value depends on the sampling distributions, whether the target is represented by points or triangles, and the chosen reductions. The directed terms should therefore remain available when diagnosing a symmetric aggregate.

At a declared tolerance $tau$, thresholded diagnostics summarize the same directional errors:

$
  "precision"_tau =
  (1)/(abs(cal(P)))
  sum_(bold(p) in cal(P)) bb(1)[d(bold(p), cal(M)) < tau],
$

$
  "recall"_tau =
  (1)/(abs(cal(S)))
  sum_(bold(s) in cal(S)) bb(1)[d(bold(s), cal(P)) < tau],
  quad
  F_tau = (2 "precision"_tau "recall"_tau)/("precision"_tau + "recall"_tau),
$

Precision diagnoses reconstructed support near the reference, recall diagnoses recovered reference support, and the F-score is their harmonic mean. These quantities depend on $tau$ and the sampling protocol, so they are best retained as threshold-specific diagnostics rather than treated as substitutes for continuous distance.

The minimizing surface point is a closest-point _witness_. For query $bold(p)$,

$
  bold(w)(bold(p)) =
  op("argmin", limits: #true)_(bold(x) in cal(M))
  norm(bold(p) - bold(x))_2.
$

For a triangular mesh, the witness is the orthogonal projection when it lies inside the closest triangle and otherwise lies on its nearest edge or vertex. Witnesses make individual correspondences, outliers, and spatially concentrated errors inspectable instead of collapsing them immediately into one scalar.

For target-specific relative reconstruction improvement (RRI), the before-and-after errors must be evaluated on the same target crop, reference geometry, sampling rule, distance definition, and reduction. Only the reconstructed evidence should change when a candidate view is added. Otherwise, a changed evaluation support can masquerade as reconstruction improvement.
