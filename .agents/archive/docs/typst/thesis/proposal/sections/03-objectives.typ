#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "_style.typ": *

= Objectives and Hypotheses

The thesis objective is a leakage-safe target-aware #gls("next-best-view") stack whose selected
views reduce target point-mesh error under a fixed acquisition budget. The
endpoint metric #symb.entity.endpoint_gain is primary, and the additive return #symb.entity.return_h is the
training target for value learning.

== Aim 1: Target Oracle and Leakage Boundary

Define target-specific oracle #gls("relative-reconstruction-improvement") while keeping target selection and model
input actor-visible. V1 uses observed or predicted target descriptors
#symb.entity.target_desc. GT crops, boxes, meshes, and all-candidate renders are restricted
to labels, upper bounds, and evaluation. The required evidence is target
eligibility, match score, unmatched/ambiguous counts, endpoint #symb.entity.endpoint_gain, and
separate scene #RRI and acquisition cost.

== Aim 2: Target-Conditioned One-Step Control

Train a VIN-style myopic scorer over the same candidate table that later feeds
#symb.rl.qh. The scorer predicts target #RRI from actor-visible scene, target, and
candidate features. It is the required learned one-step control, evaluated by
rank correlation, top-$k$ oracle hit rate, calibration, selected-candidate
oracle #RRI, target visibility, invalid fraction, and grouped failures.

== Aim 3: Non-Myopic Finite-Candidate Planning

First estimate whether bounded oracle lookahead has headroom over one-step
oracle greedy:

#block[#align(center)[#eqs.entity.lookahead_headroom]]

Only if this headroom is positive is #symb.rl.qh expected to recover part of it from
offline rollout traces. The candidate-query model emits one masked value per
candidate:

#block[#align(center)[#eqs.rl.qh_candidate_token]]

#block[#align(center)[#eqs.rl.qh_candidate_value]]

#block[#align(center)[#eqs.rl.qh_masked_argmax]]

Success is measured by oracle-rescored selected actions, not predicted values.
If oracle lookahead itself has little headroom, the thesis reports that the
current objective and candidate distribution are effectively myopic. If
lookahead has headroom but #symb.rl.qh fails to recover it, the analysis reports
whether the limiting factor is target observability, candidate support, rollout
coverage, reward definition, or model capacity.

#figure(
  table(
    columns: (0.86fr, 1.32fr, 1.48fr),
    table.header([*Claim*], [*Primary evidence*], [*Decision rule*]),
    [Target utility],
    [#symb.entity.endpoint_gain, #symb.entity.return_h, scene #RRI, cost],
    [#symb.entity.endpoint_gain decides endpoint quality; #symb.entity.return_h trains and ranks rollouts.],

    [Input safety],
    [actor-visible #symb.entity.target_desc, match score, support, leakage checks],
    [GT is label/evaluation only for the V1 result.],

    [Myopic control],
    [target-rank metrics, selected-candidate oracle #RRI, calibration],
    [One-step target scoring is the comparator for #symb.rl.qh, not the final policy claim.],

    [Planning headroom],
    [#symb.entity.lookahead_headroom and recovered fraction #symb.entity.q_recovery],
    [#symb.rl.qh is meaningful only relative to measured oracle-lookahead headroom.],
  ),
  caption: [Objective-to-evidence matrix.],
) <tab:proposal-objective-evidence>
