= Experimental Design <sec:thesis-experimental-design>

The experiment is a graph of admissibility gates rather than one aggregate
model score. Measurement and population/action support are prerequisites for
policy comparison. After support is established, the actor-protocol audit is
reported independently of oracle headroom; actor-visible one-step value and
exact two-step recursion follow the protocol branch, while meaningful headroom
follows the oracle branch. Both branches are required before fixed-budget
endpoint gap closure is admitted. Each stage has its own population, estimate,
uncertainty, and stopping rule.

#figure(
  align(center, image(
    "../../figures/qh_learning_evidence_loop.pdf",
    width: 100%,
  )),
  caption: [Evidence-gated claim graph. A failed stage retains its own measured outcome but blocks claims that depend on it; missing evidence remains unavailable rather than becoming zero.],
) <fig:qh-learning-evidence-loop>

#include "05-01-objectives-and-hypotheses.typ"

#include "05-02-learning-objective-and-replay-evidence.typ"

#include "05-03-policy-comparison-and-failure-interpretation.typ"
