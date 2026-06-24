#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": *
#import "@preview/booktabs:0.0.4": *

== Objectives and Hypotheses

The first aim defines target-specific oracle @relative-reconstruction-improvement while keeping target selection and model input actor-visible. V1 uses observed or predicted target descriptors #symb.entity.target_desc. @ground-truth:short crops, boxes, meshes, and all-candidate renders are restricted to labels, upper bounds, and evaluation. The required evidence is target eligibility, match score, unmatched/ambiguous counts, endpoint #symb.entity.endpoint_gain, separate scene @relative-reconstruction-improvement:short, and acquisition cost.

The render-path boundary in @fig:qh-teacher-student-render-path makes this restriction explicit for render-derived training signals.

#figure(
  align(center, image(
    "../../figures/qh_teacher_student_render_path.pdf",
    width: 100%,
  )),
  caption: [Teacher/student render path for leakage-safe training. The student branch consumes actor-visible state and current-belief render products, while privileged @ground-truth:short meshes, target crops, and dense candidate renders may produce oracle returns, teacher values, or distillation targets only. Dense @ground-truth:short candidate depth is therefore label or teacher evidence, not a V1 actor input.],
) <fig:qh-teacher-student-render-path>

The second aim trains a VIN-style myopic scorer over the same candidate table that later feeds #symb.rl.qh. The scorer predicts target @relative-reconstruction-improvement:short from actor-visible scene, target, and candidate features. It is the required learned one-step control, evaluated by rank correlation, top-$k$ oracle hit rate, calibration, selected-candidate oracle @relative-reconstruction-improvement:short, target visibility, invalid fraction, and grouped failures.

The third aim first estimates whether bounded oracle lookahead has headroom over one-step oracle greedy:

$
  #eqs.entity.lookahead_headroom
$

Only if this headroom is positive is #symb.rl.qh expected to recover part of it from offline rollout traces:

$
  #eqs.entity.q_recovery
$

Success is measured by oracle-rescored selected actions, not predicted values. If oracle lookahead itself has little headroom, the thesis reports that the current objective and candidate distribution are effectively myopic. If lookahead has headroom but #symb.rl.qh fails to recover it, the analysis reports whether the limiting factor is target observability, candidate support, rollout coverage, reward definition, or model capacity.

#figure(
  table(
    columns: (0.86fr, 1.32fr, 1.48fr),
    toprule(),
    table.header([*Claim*], [*Primary evidence*], [*Decision rule*]),
    midrule(),
    [Target utility],
    [#symb.entity.endpoint_gain, #symb.entity.return_h, scene @relative-reconstruction-improvement:short, cost],

    [#symb.entity.endpoint_gain decides endpoint quality; #symb.entity.return_h trains and ranks rollouts.],
    [Input safety],
    [actor-visible #symb.entity.target_desc, match score, support, leakage checks],

    [@ground-truth:short is label/evaluation only for the V1 result.],
    [Myopic control],
    [target-rank metrics, selected-candidate oracle @relative-reconstruction-improvement:short, calibration],

    [One-step target scoring is the comparator for #symb.rl.qh, not the final policy claim.],
    [Planning headroom],
    [#symb.entity.lookahead_headroom and recovered fraction #symb.entity.q_recovery],

    [#symb.rl.qh is meaningful only relative to measured oracle-lookahead headroom.], bottomrule(),
  ),
  caption: [Objective-to-evidence matrix.],
) <tab:thesis-objective-evidence>
