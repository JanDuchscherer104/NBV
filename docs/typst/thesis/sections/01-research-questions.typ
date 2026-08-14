== Research Questions <sec:thesis-research-questions>

#import "../draft_markers.typ": thesis_status
#import "../../shared/equations.typ": eqs

The thesis asks whether ARIA-NBV can perform target-conditioned, quality-driven
multi-step @next-best-view (NBV) selection with a finite candidate action space.
The utility is target-specific @relative-reconstruction-improvement (RRI), and
every learned action is re-evaluated with the oracle under the same candidate
support, validity rules, and acquisition budget. @ground-truth:short (GT) geometry
defines target tasks, labels, and evaluation; it is not an ordinary actor input.

=== Objectives and scope <objectives>

The work has six linked objectives. First, validate the geometry, candidate-label,
invalidity, split, and oracle-RRI contracts on a trusted ASE subset before scale-up.
Second, define the V1 observed-target-selection / predicted-target-$Q$ /
GT-evaluation protocol. Third, establish a learned one-step target-conditioned
scorer as the required myopic control. Fourth, validate mixed candidate sets and
rollout support before training a finite-horizon value model. Fifth, train
$Q_(H, theta)$ from ASE oracle rollouts as a finite-candidate value model, first
using candidate-to-state queries. Finally, grow support from trusted subsets to
scene-level ASE evidence only while preserving mesh-supervised target RRI.

Online discrete $Q_H$ is a deferred RQ5 bridge; continuous or simulator-backed
actor--critic control is RQ6 and is not required for the finite-candidate thesis
result. The active quantitative core is therefore RQ1--RQ4 below.

#thesis_status(
  implementation: "planned",
  evidence: "pending",
  gate: [V1 observed/predicted target matching and target-conditioned scoring are not yet implemented; current V0 GT tasks remain the only available protocol],
)[The V1 descriptor and deterministic 3D-IoU matching below are a planned
hypothesis and acceptance protocol, not an implemented result.]

=== RQ1 — Objective and endpoint contract <rq1>

Can target-conditioned, finite-candidate NBV improve endpoint quality for a
selected target under a fixed acquisition budget while keeping training return,
endpoint evaluation, and acquisition cost separate? For a rollout rooted at
$s_0$ with target $e$, let $cal(P)_t$ be the accumulated fused points and
$cal(M)_e^"GT"$ the matched target surface. The oracle-only target crop gives

$$
  Δ_t^e = D_(P → M,t)^e + D_(M → P,t)^e;
  J_H^e = (Δ_0^e - Δ_H^e)/(Δ_0^e + ε).
$$

The primary fixed-budget metric is endpoint gain $J_H^e$. The default
multi-step reward is root-normalized target gain,

$$
  r_(t,"root")^e = (Δ_t^e - Δ_(t+1)^e)/(Δ_0^e + ε);
  G_0^(H) = ∑_(t=0)^(H-1) γ^t r_(t,"root")^e.
$$

State-relative target RRI remains a diagnostic and VIN-compatible one-step
label; log-error gain and motion or feasibility costs are explicit ablations.
Invalid candidates are hard constraints, never the lowest-RRI class. Report
endpoint gain, cumulative root gain, diagnostic target RRI, scene RRI, view count,
path length, invalid-action rate, and runtime at matched budgets.

=== RQ2 — Offline finite-candidate planning <rq2>

Does bounded oracle lookahead have positive endpoint-quality headroom over
one-step oracle-greedy selection, and can an offline $Q_(H, theta)$ policy recover
a measurable fraction of it? The first comparison fixes target tasks, roots,
candidate support, validity, horizon, and budget. Define

$$
  #eqs.entity.lookahead_headroom
$$

If this headroom is indistinguishable from zero for the evaluated support, the
result is a setup-specific negative finding, not a claim that target RRI is
universally myopic. When it is positive, $Q_(H, theta)$ is trained from ASE oracle
rollout traces and compared with random-valid, one-step oracle greedy, learned
one-step scoring, bounded oracle lookahead, and oracle-scored temperature-softmax
traces. The learned model emits one masked bounded-horizon value per finite
candidate; GT meshes, crops, and oracle values remain supervision/evaluation only.
Gumbel-Top-$k$ is later diversity evidence, not a prerequisite for the first run.

=== RQ3 — Actor-visible target representation <rq3>

Which actor-visible target descriptor and matching protocol support one-step and
finite-horizon scoring without privileged target geometry or all-candidate oracle
renders at decision time? The proposed V1 protocol is observed or predicted
target selection, predicted-target conditioning, and GT target-crop evaluation.
The first descriptor contains observed/predicted OBB centre, extents,
orientation, class, confidence, projected area, relative pose, semi-dense point
support, and EVL support. A compact crop descriptor from actor-visible spatial
evidence is the first ablation; entity tokens and appearance features are later
ablations. V0 GT-OBB input is a sanity or upper-bound path only.

If implemented, observed targets will be matched to GT targets by compatible class and a deterministic
geometry-first 3D-IoU rule, with visibility, projected area, and semi-dense/EVL
support reported as eligibility and audit fields. Unmatched, unsupported, or
ambiguous targets are protocol-invalid cases, not low-RRI examples.

=== RQ4 — Candidate, rollout, and scale support <rq4>

Do mixed target-centric and default-exploration candidates, controlled rollout
branching, and scale-aware replay evidence improve reliability over pure generic
or pure target-point sampling? The thesis-core finite table combines target-point,
radial-away, radial-towards, and forward-rig directions with bounded jitter and
supported shell position samplers. Every row retains strategy provenance, a hard
validity mask, and explicit invalid-reason codes. Branch, beam, and stochastic
temperature controls widen data support; they do not replace the RRI objective.

Scale proceeds causally: a small trusted subset first establishes geometry,
matching, invalidity, and replay correctness; a scene-level held-out or full
ASE GT-mesh subset then supplies thesis evidence; external substrates are
eligible only when they preserve target-specific mesh/oracle supervision.
Report scenes, snippets, targets, trajectories, anchor poses, candidates,
rollout seeds, transitions, split boundaries, invalid gaps, and missing coverage
separately. Sample-level splits across snippets from one scene are not sufficient
for final claims.

=== Shared evidence protocol <protocol>

Invalidity is a shared constraint across all questions: collision, out-of-bounds,
missing depth, bad frusta, outside-EVL extent, and impossible oracle evaluation
are hard masks with reason codes. Report invalid fractions and reason distributions,
target-visible fractions, masked and unmasked rank metrics, and selected-action
oracle evaluation. Equal budget means equal horizon, candidate count, candidate
distribution, and validity constraints; path length, runtime, and oracle calls
are separate measurements. Coverage, calibration, stage shift, and storage
lineage are evidence qualifiers rather than proxy objectives.

=== Research matrix <matrix>

#table(
  columns: (1.1fr, 0.8fr, 2.5fr),
  inset: 6pt,
  align: (left, left, left),
  [*Question*], [*Gate*], [*Primary evidence*],
  [RQ1], [M1, M5], [Endpoint target gain, cumulative root gain, diagnostic RRI, and acquisition-cost curves.],
  [RQ2], [M4, M5], [One-step gate, oracle lookahead, rollout traces, endpoint gain, and recovered headroom.],
  [RQ3], [M3, M4], [Actor-visible target encoding and leakage-safe crop ablation.],
  [RQ4], [M2--M7], [Candidate mixtures, branching diversity, validity statistics, scale, and coverage reports.],
)

The matrix is a reporting map, not a second source of contracts: implementation
semantics remain owned by code, tests, and the linked development reports.
