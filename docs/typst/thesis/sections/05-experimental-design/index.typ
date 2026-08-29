= Experimental Design <sec:thesis-experimental-design>

The experiment is a sequence of admissibility gates rather than one aggregate
model score. Measurement must be stable before a population can be interpreted;
population and action support must exist before oracle headroom can be measured;
headroom must be meaningful before learned recovery is relevant. The learned
path then separates actor-visible one-step value, exact two-step recursion, and
fixed-budget endpoint recovery. Each stage has its own population, estimate,
uncertainty, and stopping rule.

#figure(
  align(center, image(
    "../../figures/qh_learning_evidence_loop.pdf",
    width: 100%,
  )),
  caption: [Evidence-gated claim path. The first failed gate determines the admissible interpretation; later quantities remain unavailable rather than being treated as zero or pooled into a composite score.],
) <fig:qh-learning-evidence-loop>

#include "05-01-objectives-and-hypotheses.typ"

#include "05-02-learning-objective-and-replay-evidence.typ"

#include "05-03-policy-comparison-and-failure-interpretation.typ"
