= Experimental Design <sec:thesis-experimental-design>

The experiment is a claim-admissibility graph rather than one aggregate model
score. Repeatable measurement and minimum factual population/action support are shared
foundations. From them, one lane tests whether the finite setup exposes oracle
headroom, while a second tests actor-visible one-step value and learned-versus-
exact two-step agreement. Endpoint recovery is interpretable only where both
lanes meet. Each gate has its own evidence, decision rule, and claim boundary:
a measured non-pass remains auditable, but cannot make a dependent claim
admissible.

#figure(
  align(center, image(
    "../../figures/qh_learning_evidence_loop.pdf",
    width: 100%,
  )),
  alt: "Two shared foundation gates feed separate oracle-headroom and actor-visible learned-value lanes. The lanes converge through an AND prerequisite before endpoint recovery. Evidence may be unavailable, measured as a non-pass, or passed; a claim is admissible only when its own gate and every predecessor pass.",
  caption: [Evidence-gated claim graph. A non-passing prerequisite blocks only claims that depend on it: separately measured diagnostics remain reportable, but cannot rescue the blocked claim or be re-encoded as zero.],
) <fig:qh-learning-evidence-loop>

#include "05-01-objectives-and-hypotheses.typ"

#include "05-02-learning-objective-and-replay-evidence.typ"

#include "05-03-policy-comparison-and-failure-interpretation.typ"
