#import "../../shared/symbols.typ": symb
#import "../draft_markers.typ": thesis_status, scientific_core_todo, prune_todo

= Discussion <sec:thesis-discussion>

The available evidence supports an implementation conclusion, not a policy
conclusion. ARIA-NBV represents target-specific finite actions, separates
actor-visible inputs from oracle supervision, applies invalidity as a hard
constraint, records factual selected transitions, and reports observed values
without replacing missing evidence. These properties make the proposed study
auditable. They do not establish metric repeatability, held-out population
support, non-myopic headroom, learned value accuracy, or endpoint improvement.

The current evidence supports a narrow implementation conclusion. ARIA-NBV has an executable finite-candidate path that keeps oracle gains, meshes, associations, and candidate renders outside the scorer graph, applies invalidity as a hard decision constraint, evaluates target-specific reconstruction change offline, and exposes the resulting store through one typed reporting seam. The selected experiment still conditions on privileged `v0_gt_input` target geometry; the actor-visible `v1_observed` path is implemented but not frozen or evaluated. This establishes that the proposed experiment can be represented and audited; it does not establish deployability or that one candidate family, rollout policy, representation, or learned model performs better than another.

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

The actor-protocol audit is interpretable independently of oracle headroom: it
tests target matching, the complete actor-input path, and actor--oracle leakage.
Conditional on that audit, actor-visible $Q_1$ evaluates whether the selected
learner recovers immediate target value from the declared information state.
Failure does not by itself show that the state lacks signal; model
misspecification, optimization, capacity, and finite-sample error remain viable
explanations alongside target association, representation support, and
calibration. Passing $Q_1$ but failing exact $Q_2$ narrows the diagnostic to
successor coverage, state aliasing, recursive targets, or bootstrap estimation.
Only after those prerequisites pass does failed endpoint recovery become
evidence about planning under the admitted model and replay support. Even then,
the endpoint estimate alone does not identify the failed mechanism.

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
action, safety, and cost assumptions and remain outside the present evidence.

== Evidence-conditioned architecture bridges

#thesis_status(
  implementation: "exploratory",
  evidence: "pending",
  source: [@tab:thesis-counterfactual-state-protocols; @tab:architecture-feature-integration-ladder],
  gate: [a measured limitation that the proposed bridge directly tests],
)[Alternative representations and policies remain part of the thesis design registry, but they are promoted only as responses to diagnosed bottlenecks.]

If the local EFM3D field is the limiting variable, broad semidense memory, sparse occupied/free/unknown state, target-centred re-lifting, or logged appearance features provide progressively stronger representation tests. If the current query contains the necessary geometry but A1 fails to recover candidate--target or candidate--history relations, the planned candidate-relative relation embedding is the smallest architectural test. If errors instead remain correlated with the sampled admissible set, DeepSets or masked candidate interaction becomes relevant. If selected-view history fails specifically by approach direction, signed first- plus second-moment memory, followed only if needed by spherical harmonics, becomes the targeted ablation. A renderable 3DGS state is appropriate only when candidate rendering or soft instance membership is itself the measured missing capability.

Continuous and hierarchical policies change the action contract rather than merely increasing model capacity. A target-then-pose policy could first select or mask a target token and then condition pose queries on target, horizon, and step; multiple targets can share scene encodings and be evaluated in parallel. This remains post-core work because continuous pose generation requires separate feasibility, safety, support, and simulator-realism evidence. The finite-candidate model is retained as the calibrated control even if a continuous policy is later introduced.

Sequence or recurrent models are similarly conditional. They become scientifically motivated when errors persist after explicit history, time, horizon, and scene-memory conditioning, not simply because the dataset contains trajectories. Looping or recurrent refinement must preserve causal masks and candidate-row equivariance and must be compared against the same fixed-budget endpoint oracle evaluation.

#scientific_core_todo(
  domain: "architecture",
  priority: "C2",
  readiness: "contingent",
  claim: [which representation or interaction limitation explains residual held-out value error],
  source: [method design-space registry],
  gate: [artifact-backed failure analysis],
)[After the primary evidence chain is complete, promote only bridges tied to a measured failure: EVL support, target observability, directional history, valid-set interaction, long-horizon credit, or action-support mismatch.]

The next evidential step remains procedural: complete validated stores under
resolved manifests, freeze the eligible population and exclusions, establish
oracle stability and headroom, train the matched controls, and only then
interpret architectural differences. The registry preserves concrete follow-up
hypotheses without presenting them as validated conclusions.

The conceptual contribution is consequently a diagnostic admissibility
structure for target-specific view planning. View value is relational,
invalidity is distinct from utility, privileged support is distinct from actor
visibility, and each scientific claim is attached to the evidence and
prerequisites required to admit it. This structure narrows alternative
explanations without claiming causal identification and remains useful whether
the eventual policy result is positive, negative, or blocked.
