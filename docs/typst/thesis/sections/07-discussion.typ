= Discussion <sec:thesis-discussion>

The available evidence supports an implementation conclusion, not a policy
conclusion. ARIA-NBV represents target-specific finite actions, separates
actor-visible inputs from oracle supervision, applies invalidity as a hard
constraint, records factual selected transitions, and exposes evidence through
an artifact-driven report seam. These properties make the proposed study
auditable. They do not establish metric repeatability, held-out population
support, non-myopic headroom, learned value accuracy, or endpoint improvement.

The evidence chain in @fig:qh-learning-evidence-loop makes this distinction
constructive. The first unresolved gate owns the current interpretation. Here,
repeatability and the held-out population are not established, so headroom,
actor-visible $Q_1$, exact $Q_2$, and endpoint recovery remain unavailable—not
negative. Treating them as zeros would collapse missing evidence into measured
failure and could make a pipeline limitation appear to answer the scientific
question.

== Interpreting future outcomes

The failure-attribution matrix in @tab:thesis-failure-attribution separates
mechanisms that an endpoint score alone cannot identify. Unstable measurement
invalidates every downstream comparison. Adequate measurement but insufficient
target or action support locates the problem in the study population rather
than the policy. Stable support with negligible oracle headroom means that the
frozen candidate generator, horizon, and metric expose little exploitable
non-myopic structure; it does not imply universal myopia.

If meaningful headroom exists, actor-visible $Q_1$ tests whether the declared
information state contains enough immediate target signal. Failure there
directs attention to target association, leakage, representation support, or
calibration before long-horizon architecture. Passing $Q_1$ but failing exact
$Q_2$ localizes the first non-myopic defect to successor coverage, state
aliasing, recursive targets, or bootstrap estimation. Only after those gates
pass does failed endpoint recovery become evidence about planning under the
admitted model and replay support. Even then, the endpoint estimate alone does
not identify which representation or optimization mechanism failed.

This logic also disciplines positive outcomes. Exact $Q_2$ would validate the
first recursive prediction on its admitted support, not the complete policy.
Endpoint recovery would remain conditional on the target protocol, finite
candidate generator, hard-validity regime, horizon, oracle metric, and ASE
population. The privileged bounded-lookahead policy is a reference within that
finite experimental world, not a representation-independent or deployable
upper bound.

== Systems and external-validity boundaries

Counterfactual scoring repeatedly renders a large mesh, so memory and latency
constrain branch factor and rollout volume before statistical efficiency can be
assessed. An out-of-memory event motivates batching and resource measurement;
it says nothing about candidate utility or planning value. Completed validated
stores are required before throughput, storage, failure rates, or population
coverage can be generalized.

The offline ASE setting additionally supplies geometry and target identity that
a deployed egocentric actor would have to infer. The thesis therefore separates
oracle task construction from actor-visible scoring end to end: target
instruction, candidate proposal, hard mask, selected observation, and scorer
input. Real-device or continuous-control claims would change observation,
action, safety, and cost contracts and remain outside the present evidence.

The conceptual contribution is consequently an identifiability structure for
target-specific view planning. View value is relational, invalidity is distinct
from utility, privileged support is distinct from actor visibility, and each
scientific claim is attached to the earliest evidence gate capable of
falsifying it. That structure remains useful whether the eventual policy result
is positive, negative, or blocked.
