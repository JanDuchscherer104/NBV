#import "../../../shared/macros.typ": *

== Reconstruction Quality Metrics <sec:thesis-reconstruction-metrics>

Let #symb.oracle.points be samples from a reconstructed surface, #symb.oracle.reference_geometry a reference mesh, and #symb.oracle.reference_samples a declared sample of that mesh. The distance from a point to the reference geometry is


$
  #eqs.metrics.point_to_reference_distance
$

It induces two directed errors,

$
  #eqs.metrics.directed_reconstruction_errors
$

Accuracy exposes unsupported or extraneous reconstructed geometry; completeness reverses the comparison and exposes missing geometry. Neither direction alone characterizes both failure modes.

A symmetric score can sum or average the two directed terms. This is often called a Chamfer-style distance, but the name does not make different formulations interchangeable: the value depends on the sampling distributions, whether the target is represented by points or triangles, and the chosen reductions. The directed terms should therefore remain available when diagnosing a symmetric aggregate.

At a declared tolerance #symb.oracle.tolerance, thresholded diagnostics summarize the same directional errors:

$
  #eqs.metrics.threshold_reconstruction_diagnostics
$

Threshold precision diagnoses reconstructed support near the reference, threshold recall diagnoses recovered reference support, and the F-score is their harmonic mean. These quantities depend on #symb.oracle.tolerance and the sampling protocol, so they are best retained as threshold-specific diagnostics rather than treated as substitutes for continuous distance.

The minimizing surface point is a closest-point _witness_. For a query point,
$
  #eqs.metrics.closest_point_witness
$

For a triangular mesh, the witness is the orthogonal projection when it lies inside the closest triangle and otherwise lies on its nearest edge or vertex. Witnesses make individual correspondences, outliers, and spatially concentrated errors inspectable instead of collapsing them immediately into one scalar.

For target-specific relative reconstruction improvement (RRI), the before-and-after errors must be evaluated on the same target crop, reference geometry, sampling rule, distance definition, and reduction. Only the reconstructed evidence should change when a candidate view is added. Otherwise, a changed evaluation support can masquerade as reconstruction improvement.
