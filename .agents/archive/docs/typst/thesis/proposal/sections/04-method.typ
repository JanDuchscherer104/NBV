#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "_style.typ": *

= Method

== Geometry, Targets, and One-Step Control

The geometry stage establishes the candidate poses, rig poses, rendered depths,
backprojected point clouds, semi-dense support, EVL fields, and Rerun
diagnostics that must agree in frame and indexing. Oracle labels use the
implemented point-mesh terms

$
  Delta_t = D_(P -> M,t) + D_(M -> P,t),
  quad
  #symb.entity.target_error = #symb.entity.target_error_pm + #symb.entity.target_error_mp,
  quad
  #symb.entity.target_reward =
  (#symb.entity.target_error - #symb.entity.target_error_next)
  /
  (#symb.entity.target_error_0 + epsilon).
$

State-relative one-step RRI keeps the current-error denominator and remains a
diagnostic / VIN-compatible label, not the default rollout or #symb.rl.qh
training reward.

The target stage adds the V1 contract. The selector returns a small top-$K$ set
of observed or predicted targets and refuses GT OBB input for the main result.
Target labels are attached only after matching to GT crops. The one-step
target-conditioned scorer keeps the current VIN-style ordinal setup, including
CORAL variants @CORAL-cao2019, and becomes the myopic learned control.

== Candidate and Replay Contract

Each decision state carries a finite candidate table #symb.rl.candidate_table, hard mask
$bold(m)_t$, invalid-reason vector $bold(rho)_t$, and the target descriptor
#symb.entity.target_desc. It also stores selected-view history and remaining
budget. Candidate generation is logged as a mixture over target-point, radial-shell, and forward-rig
families. Each row stores provenance, pose, target/scene support, path
increment, validity, reason code, and oracle labels. Candidate order has no
semantics, so shuffled-candidate evaluation is required.

A feature split avoids overloading pose codes with visibility history. Candidate
orientation uses a continuous 6D rotation code @zhou2019continuity, but
accumulated visibility is a directional memory over $S^2$, not a sum of R6D
vectors. For a target point or voxel center $bold(v)$ and a previously selected
camera center $bold(c)_k$, the observed direction is

#block[#align(center)[#eqs.features.direction_unit]]

The planned actor-visible feature branch stores this history either as
low-order spherical-harmonic coefficients @e3nn-SphericalHarmonics-2025,

#block[#align(center)[#eqs.features.direction_memory_sh]]

or as a second-moment summary,

#block[#align(center)[#eqs.features.direction_memory_moment]]

from which the candidate can read a directional novelty score:

#block[#align(center)[#eqs.features.direction_novelty]]

Thus R6D belongs to the pose branch, while directional observation history
belongs to the visibility branch. The candidate token receives both:

$
  #symb.vin.candidate_pose_feat (#symb.rl.candidate_qti)
  =
  [
    bold(t)_(t,i),
    bold(R)_(t,i)^"6D",
    bold(t)_(t,i) - bold(t)_e,
    alpha_(t,i)^e,
    l_(t,i),
    c_(t,i)^"strategy"
  ],
$

$
  bold(x)_(t,i)
  =
  [
    #symb.vin.candidate_pose_feat,
    #symb.vin.candidate_dir_feat,
    phi_"frustum" (#symb.vin.field_evl_0, #symb.rl.candidate_qti, #symb.entity.target_desc),
    phi_"valid" (m_(t,i), rho_(t,i)),
    bold(h)_t
  ].
$

The minimum replay row is

$
  bold(xi)_t =
  (
    bold(k)_"id",
    #symb.rl.s_cf0,
    #symb.entity.target_desc,
    #symb.rl.candidate_table,
    #symb.rl.candidate_mask,
    #symb.rl.invalid_reasons,
    a_t,
    #symb.entity.target_reward,
    #symb.rl.s_cf0_next,
    cal(Q)_(t+1),
    bold(m)_(t+1),
    bold(k)_"meta"
  ).
$

Here $bold(k)_"id"$ stores scene, snippet, target, and step identifiers, while
$bold(k)_"meta"$ stores policy, seed, and sampler provenance. This row
reproduces the mask, selected transition, value target, and oracle
re-evaluation.

== Rollout Policies and $Q_H$

The planning evaluation first compares deterministic one-step oracle greedy and
bounded oracle lookahead:

$ pi_"oracle-1" (s_t) =
  op("argmax", limits: #true)_(i in cal(A)_t) r_t^e (i), $

$ pi_"oracle-look" (s_t) =
  pi_0 (
    op("argmax", limits: #true)_(a_(t:t+H-1))
    sum_(k=0)^(H-1) gamma^k r_(t+k)^e
  ). $

Temperature-softmax traces are rollout-data diversity, not the final policy:

$ P(a_t=i | s_t)
  =
  exp(beta ell_(t,i)) / (sum_(j in cal(A)_t) exp(beta ell_(t,j))). $

The learned planner is a candidate-query Transformer over scene, target,
history, and candidate tokens @Transformer-vaswani2017 @DeepSets-zaheer2017
@SetTransformer-lee2019:

#block[#align(center)[#eqs.rl.qh_candidate_token]]

#block[#align(center)[#eqs.rl.qh_candidate_value]]

Invalid candidates are filled with $-infinity$ before argmax, softmax, loss
targets, and bootstrap maximization. With online parameters $theta$ and target
parameters $theta^-$, the first backup is masked Double-Q
#cite(label("DBLP:journals/corr/MnihKSGAWR13")) @DoubleDQN-vanHasselt2015:

#block[#align(center)[#eqs.rl.qh_doubleq_index]]

#block[#align(center)[#eqs.rl.qh_doubleq_target]]

#block[#align(center)[#eqs.rl.qh_loss]]

IQL, CQL, BCQ, sequence decoding, soft/energy policies, PPO, and SAC remain
later comparison references unless the finite-candidate rollout store is stable
@IQL-kostrikov2021 @CQL-kumar2020 @BCQ-fujimoto2019
@DecisionTransformer-chen2021 @DeepEnergyPolicies-haarnoja2017
@PPO-schulman2017 @SAC-haarnoja2018.

== Evaluation

All selected actions are oracle-evaluated under the same acquisition and
candidate budgets. The proposal uses one canonical comparison table:

#figure(
  table(
    columns: (0.92fr, 0.7fr, 0.7fr, 0.64fr, 1.22fr),
    table.header([*Policy*], [*Actor input?*], [*GT decision?*], [*Horizon*], [*Primary role*]),
    [$pi_"rand"$],
    [yes],
    [no],
    [1],
    [lower reference over valid candidates],
    [$pi_"learned-1"$],
    [yes],
    [no],
    [1],
    [myopic learned target scorer],
    [$pi_"oracle-1"$],
    [no],
    [yes],
    [1],
    [one-step oracle upper bound],
    [$pi_"oracle-look"$],
    [no],
    [yes],
    [$H$],
    [non-myopic headroom estimate],
    [$pi_Q$],
    [yes],
    [no],
    [$H$],
    [learned recovery of lookahead headroom],
  ),
  caption: [Policy comparison and leakage boundary. Report #symb.entity.endpoint_gain, #symb.entity.return_h, scene #RRI, cost, invalidity, runtime, and coverage for each row.],
) <tab:proposal-policy-eval>
