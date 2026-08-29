= Conclusion <sec:thesis-conclusion>

This thesis formulates target-specific egocentric next-best-view planning as a
relational finite-action problem: value depends jointly on target, causal
information state, admissible candidate support, horizon, update rule, and
continuation policy. It contributes a target-cropped reconstruction outcome, an
explicit actor--oracle information boundary, a strict separation of feasibility
from utility, causal selected-transition replay, a scalar-horizon fitted-value
method, and a sequential evaluation from measurement validity to endpoint
recovery.

The current evidence does not yet answer RQ2. Metric repeatability, the held-out
target and action population, and actor-visible immediate-value recovery remain
unestablished; without those premises, neither oracle-lookahead headroom nor
learned exact-$Q_2$ and endpoint recovery are interpretable. Online interaction
and continuous control remain extensions of the setting rather than missing
parts of this evaluation.

Training-source rollouts establish that the pipeline reaches mesh rendering,
target-specific oracle scoring, selected-action replay, and the fitted-value
interface; renderer memory exposes a scale gate. These observations justify an
auditable method and study design, not policy superiority, a population effect,
deployment readiness, or a scale estimate.

The eventual conclusion is determined by the first failed gate. Unstable
measurement blocks planning claims; inadequate support blocks population
claims; negligible headroom is a setup-specific negative result; failed
actor-visible $Q_1$ or exact $Q_2$ localizes a learning prerequisite; and stable
headroom without endpoint recovery is a bounded learned-policy failure. This
ordering preserves informative negative outcomes without extending them beyond
the frozen finite-candidate experiment.
