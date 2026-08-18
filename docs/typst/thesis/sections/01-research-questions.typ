== Research Questions <sec:thesis-research-questions>

#import "../draft_markers.typ": thesis_status, development_only
#import "../../shared/equations.typ": eqs

The thesis asks whether ARIA-NBV can perform target-conditioned, quality-driven
multi-step @next-best-view (NBV) selection with a finite candidate action space.
The utility is target-specific @relative-reconstruction-improvement (RRI), and
every learned action is re-evaluated with the oracle under the same candidate
support, validity rules, and acquisition budget. @ground-truth:short (GT) geometry
defines target tasks, labels, and evaluation; it is not an ordinary actor input.

=== Objectives and scope <ssec:rq-objectives>

The work has six linked objectives. First, validate the geometry, candidate-label,
invalidity, split, and oracle-RRI contracts on a trusted ASE subset before scale-up.
Second, define the observed-target-selection / predicted-target-$Q$ /
GT-evaluation protocol. Third, establish a learned one-step target-conditioned
scorer as the required myopic control. Fourth, validate mixed candidate sets and
rollout support before training a finite-horizon value model. Fifth, train
$Q_(H, theta)$ from ASE oracle rollouts as a finite-candidate value model, first
using candidate-to-state queries. Finally, grow support from trusted subsets to
scene-level ASE evidence only while preserving mesh-supervised target RRI.

Online discrete $Q_H$ is a deferred RQ5 bridge; continuous or simulator-backed
actor--critic control is RQ6 and is not required for the finite-candidate thesis
result. The active quantitative core is therefore RQ1--RQ4 below.

#development_only(() => [
  *Development provenance and reconciliation.* The reviewed Quarto source
  (the reviewed historical QMD at `origin/main`) supplied the six-tier
  ordering: RQ1 objective, RQ2 offline finite-candidate planning, RQ3
  actor-visible target representation, RQ4 candidate/rollout/scale support, RQ5
  online discrete $Q_H$, and RQ6 continuous or simulator escalation. The base
  Typst formulation on this branch had consolidated the first four questions
  but omitted the two explicitly gated extensions. The current formulation
  preserves the reviewed ordering, makes RQ1--RQ4 the evaluated core, and
  states RQ5/RQ6 as conditional bridges. The Quarto page remains historical
  review input; this section and the executable Python/configuration owners
  define current terminology and implementation status.
])

#thesis_status(
  implementation: "planned",
  evidence: "pending",
  gate: [Observed/predicted target matching and target-conditioned scoring remain future work; the current oracle-task protocol is the available baseline],
)[The actor-visible descriptor and deterministic 3D-IoU matching below are a planned
hypothesis and acceptance protocol, not an implemented result.]

=== RQ1 — Objective and endpoint contract <ssec:rq1>

Can target-conditioned, finite-candidate NBV improve endpoint quality for a
selected target under a fixed acquisition budget while keeping training return,
endpoint evaluation, and acquisition cost separate? For a rollout rooted at
$s_0$ with target $e$, let $cal(P)_t$ be the accumulated fused points and
$cal(M)_e^"GT"$ the matched target surface. The oracle-only target crop gives

#eqs.entity.endpoint_gain

The primary fixed-budget metric is endpoint gain $J_H^e$. The default
multi-step reward is root-normalized target gain,

#eqs.rl.target_rri_reward
#eqs.rl.finite_horizon_return

State-relative target RRI remains a diagnostic and VIN-compatible one-step
label; log-error gain and motion or feasibility costs are explicit ablations.
Invalid candidates are hard constraints, never the lowest-RRI class. Report
endpoint gain, cumulative root gain, diagnostic target RRI, scene RRI, view count,
path length, invalid-action rate, and runtime at matched budgets.

=== RQ2 — Offline finite-candidate planning <ssec:rq2>

Does bounded oracle lookahead have positive endpoint-quality headroom over
one-step oracle-greedy selection, and can an offline $Q_(H, theta)$ policy recover
a measurable fraction of it? The first comparison fixes target tasks, roots,
candidate support, validity, horizon, and budget. Define

#eqs.entity.lookahead_headroom

If this headroom is indistinguishable from zero for the evaluated support, the
result is a setup-specific negative finding, not a claim that target RRI is
universally myopic. When it is positive, $Q_(H, theta)$ is trained from ASE oracle
rollout traces and compared with random-valid, one-step oracle greedy, learned
one-step scoring, bounded oracle lookahead, and oracle-scored temperature-softmax
traces. The learned model emits one masked bounded-horizon value per finite
candidate; GT meshes, crops, and oracle values remain supervision/evaluation only.
Gumbel-Top-$k$ is later diversity evidence, not a prerequisite for the first run.

=== RQ3 — Actor-visible target representation <ssec:rq3>

Which actor-visible target descriptor and matching protocol support one-step and
finite-horizon scoring without privileged target geometry or all-candidate oracle
renders at decision time? The proposed protocol separates observed or predicted
target selection, predicted-target conditioning, and ground-truth target-crop evaluation.
The first descriptor contains observed/predicted @oriented-bounding-box centre, extents,
orientation, class, confidence, projected area, relative pose, semi-dense point
support, and EVL support. A compact crop descriptor from actor-visible spatial
evidence is the first ablation; entity tokens and appearance features are later
ablations. A ground-truth target box is retained only as a privileged sanity or
upper-bound path, not as an actor-visible deployment input.

The planned matcher first requires compatible semantic
class, then applies deterministic 3D IoU with an explicit threshold
$tau_"IoU"$. If the best and second-best compatible matches are separated by
less than the explicit ambiguity margin $tau_"gap"$, the proposal is rejected
as ambiguous; below-threshold matches are unmatched. Visibility, projected
area, and semi-dense/EVL support are audit-only evidence fields for this
association rule, not association scores. Unmatched or ambiguous targets are
protocol-invalid cases, not low-RRI examples.

=== RQ4 — Candidate, rollout, and scale support <ssec:rq4>

Do mixed target-centric and default-exploration candidates, controlled rollout
branching, and scale-aware replay evidence improve reliability over a narrower
candidate family? The thesis-core finite table is the executable 60-row mixture:
  forward-local (24), target-bearing-local (24), and
  lateral-target-bypass (12). Legacy radial-away/radial-towards and unrestricted
free-shell directions are explicit ablations, not thesis-core families. Every
row retains strategy provenance, a hard validity mask, and explicit
invalid-reason codes. Branch, beam, and stochastic temperature controls widen
data support; they do not replace the RRI objective.

Scale proceeds causally: a small trusted subset first establishes geometry,
matching, invalidity, and replay correctness; a scene-level held-out or full
ASE GT-mesh subset then supplies thesis evidence; external substrates are
eligible only when they preserve target-specific mesh/oracle supervision.
Report scenes, snippets, targets, trajectories, anchor poses, candidates,
rollout seeds, transitions, split boundaries, invalid gaps, and missing coverage
separately. Sample-level splits across snippets from one scene are not sufficient
for final claims.

=== Shared evidence protocol <ssec:protocol>

Invalidity is a shared constraint across all questions. Only physical or
explicit admissibility failures (for example collision, out-of-bounds pose,
bad frustum, or a contract-defined motion violation) clear action validity;
outside-EVL extent, missing semidense/appearance support, and similar evidence
gaps remain support fields unless the executable feasibility contract says
otherwise. A failed oracle evaluation does not make the action physically
invalid: it clears oracle-label validity and Q-training eligibility and is
reported as a label/evaluation failure. Keep the mask taxonomy explicit:
*action validity* gates selectable candidate rows;
*actor evidence/support* records whether observed target or local semidense/EVL
evidence exists; *target validity* records whether the target task and identity
state are admissible; *oracle-label validity* records whether ground-truth
evaluation produced a finite label; and *Q-training eligibility* is the strict
intersection required by the learning contract.
Report invalid fractions and reason distributions,
target-visible fractions, masked and unmasked rank metrics, and selected-action
oracle evaluation. Equal budget means equal horizon, candidate count, candidate
distribution, and validity constraints; path length, runtime, and oracle calls
are separate measurements. Coverage, calibration, stage shift, and storage
lineage are evidence qualifiers rather than proxy objectives.

=== RQ5 — Conditional online discrete $Q_H$ bridge <ssec:rq5>

After offline finite-candidate evidence is stable, does online interaction over
the same discrete candidate contract improve endpoint target gain or calibration
over the offline $Q_H$ policy? RQ5 reuses the actor-visible state, candidate
mixture, hard action mask, target protocol, horizon, and oracle re-evaluation of
RQ1--RQ4. It is attempted only when offline headroom and replay support are
positive; it is not required to establish the finite-candidate thesis result.
Online training must not silently expand the action space, change the target
protocol, or treat GT renders as actor evidence.

=== RQ6 — Lower-priority continuous and simulator escalation <ssec:rq6>

If the finite-candidate and online-discrete evidence is stable, does a
continuous or hierarchical target-then-pose policy, potentially in a simulator,
provide measurable headroom over the best finite-candidate policy under the same
target-specific objective? RQ6 is a time-permitting escalation, not a substitute
for the offline $Q_H$ result. Any comparison must preserve target conditioning,
matched budgets or cost curves, explicit feasibility handling, and independent
oracle endpoint evaluation; no continuous-control result is implied by the
current finite-candidate implementation.

=== Research matrix <ssec:matrix>

#table(
  columns: (1.1fr, 0.8fr, 2.5fr),
  inset: 6pt,
  align: (left, left, left),
  [*Question*], [*Gate*], [*Primary evidence*],
  [RQ1], [M1, M5], [Endpoint target gain, cumulative root gain, diagnostic RRI, and acquisition-cost curves.],
  [RQ2], [M4, M5], [One-step gate, oracle lookahead, rollout traces, endpoint gain, and recovered headroom.],
  [RQ3], [M3, M4], [Actor-visible target encoding and leakage-safe crop ablation.],
  [RQ4], [M2--M7], [Candidate mixtures, branching diversity, validity statistics, scale, and coverage reports.],
  [RQ5], [M6, conditional], [Online discrete $Q_H$ under the unchanged finite-candidate contract.],
  [RQ6], [M6, lower priority], [Continuous or simulator escalation against the best discrete policy.],
)

The matrix is a reporting map, not a second source of contracts: implementation
semantics remain owned by code, tests, and the linked development reports.
