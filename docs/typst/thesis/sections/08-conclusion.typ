= Conclusion <sec:thesis-conclusion>

This thesis formulates target-specific egocentric next-best-view planning as a
relational finite-action problem: value depends jointly on target, causal
information state, admissible candidate support, horizon, update rule, and
continuation policy. It contributes a target-cropped reconstruction outcome, an
explicit actor--oracle information boundary, a strict separation of feasibility
from utility, causal selected-transition replay, a scalar-horizon fitted-value
method, and a sequential evaluation from measurement validity to endpoint
recovery.

The current evidence answers the four core research questions only at the level
of implemented study design. For RQ1, the target-cropped endpoint objective is
specified, but confirmatory repeatability has not established it as an
admissible comparison metric. For RQ2, neither meaningful equal-budget oracle
headroom nor learned endpoint-gap closure is established. For RQ3, the declared
actor-visible protocol and scorer are executable, but held-out target matching,
input-identity and leakage audits, scene-clustered uncertainty, ranking, and
calibration remain unestablished. For RQ4, candidate, replay, and validity
diagnostics exist, but no validated held-out scene--target population passes the
frozen support rule. These are unresolved answers, not negative empirical
results.

Training-source rollouts establish that the pipeline reaches mesh rendering,
target-specific oracle scoring, selected-action replay, and the fitted-value
interface; renderer memory limits the evaluated scale. These observations
justify an auditable method and study design, not policy superiority, a
population effect, deployment readiness, or a scale estimate.

The eventual conclusion follows the prerequisite graph rather than a single
undifferentiated score. Unstable measurement blocks policy comparison;
inadequate support blocks population claims; a failed actor protocol blocks
actor-visible interpretation; negligible headroom is a setup-specific negative
result; and failed $Q_1$, exact $Q_2$, or endpoint recovery progressively
narrows—but does not uniquely identify—the learned-control limitation. RQ5 and
RQ6 remain conditional extensions: online interaction and continuous control
change the evidence, action, safety, and cost assumptions and are not missing
parts of the present offline finite-candidate evaluation.
