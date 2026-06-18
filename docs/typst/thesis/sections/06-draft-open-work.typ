#import "../../shared/macros.typ": *
#import "../draft_markers.typ": *
#import "@preview/booktabs:0.0.4": *

= Draft Intake and Open Work

#archive_note(
  [This chapter preserves substantive planning material from the retired proposal and advisor handout. It is part of the thesis seed, not final thesis prose. Each item should either graduate into the main chapters, move to an appendix, or be removed after its source decision is resolved.],
  source: [archived proposal and advisor handout],
)

== Schedule and Risk Control

The planned thesis window runs from 29 April 2026 to 30 September 2026. The roadmap owns the detailed Gantt chart; this draft keeps milestone exit conditions for traceability.

#figure(
  table(
    columns: (0.9fr, 1.15fr, 1.82fr),
    toprule(),
    table.header([*Dates*], [*Milestone*], [*Exit condition*]),
    midrule(),
    [2026-04-29 to 2026-05-10],
    [M0 proposal contract],
    [Proposal, roadmap, research questions, and source policy state the same finite-candidate thesis claim.],
    [2026-05-11 to 2026-05-31],
    [M1 data/oracle],
    [Offline-store, split, pose/frame, depth/backprojection, invalidity, Rerun, and throughput checks pass before target scale-up.],
    [2026-06-01 to 2026-06-21],
    [M2 one-step baseline],
    [Scene-level VIN baseline, calibration plots, LRZ sharding plan, and Zarr rollout/Q schema are ready.],
    [2026-06-22 to 2026-07-12],
    [M3 target oracle],
    [Target @relative-reconstruction-improvement:short, V1 @observed-target-selection:short / @predicted-target-q:short / @ground-truth-target-evaluation:short, and observed-only target selection are trusted on a small subset.],
    [2026-07-13 to 2026-08-09],
    [M4 target scorer],
    [Target-conditioned one-step scoring is compared with scene-level scoring and oracle target labels.],
    [2026-08-10 to 2026-08-30],
    [M5 headroom/$Q_H$],
    [Oracle lookahead headroom is measured; $Q_H$ is trained and oracle-evaluated if the headroom is positive.],
    [2026-08-31 to 2026-09-13],
    [M6 follow-up design],
    [Online discrete $Q_H$, IQL, actor-critic, hierarchy, and simulator paths are written as follow-up designs or post-M5 ablations.],
    [2026-09-14 to 2026-09-27],
    [M7 experiments/writing],
    [Final tables, figures, failure cases, coverage report, and thesis narrative are frozen.],
    [2026-09-28 to 2026-09-30],
    [M8 release],
    [Configs, smoke checks, demo path, and final PDF artifacts are reproducible.],
    bottomrule(),
  ),
  caption: [Retained milestone exit criteria from the proposal.],
) <tab:thesis-draft-schedule>

#conflict_todo(
  [The absolute dates are retained from the proposal source but must be checked against the current roadmap before they appear as final thesis text.],
  source: [proposal schedule; current roadmap],
  gate: [roadmap synchronization],
)

== Preliminary Thesis Outline

#figure(
  table(
    columns: (0.78fr, 1.45fr, 1.58fr),
    toprule(),
    table.header([*Chapter*], [*Purpose*], [*Expected evidence*]),
    midrule(),
    [Introduction],
    [Motivate target-conditioned, quality-driven @next-best-view:short for egocentric indoor reconstruction and state the finite-candidate thesis claim.],
    [Research questions, contribution boundary, and source-backed scope.],
    [Background],
    [Review active perception, @next-best-view:short, @relative-reconstruction-improvement:short, @aria-synthetic-environments:short/Project Aria, @egocentric-foundation-model-3d:short/@egocentric-voxel-lifting:short, target-aware 3DGS, and offline value learning.],
    [Literature synthesis with adoption/rejection decisions.],
    [Data and geometry contracts],
    [Describe snippets, calibration, frames, offline stores, candidates, rendered depths, backprojection, masks, and Rerun inspection.],
    [Geometry contract report, visual diagnostics, throughput, and known limitations.],
    [Oracle @relative-reconstruction-improvement:short and target @relative-reconstruction-improvement:short],
    [Define scene/target distances, crop matching, invalidity, and label generation.],
    [Label distributions, target crops, target/scene divergence, and failure cases.],
    [Target-conditioned scoring],
    [Present target-task encoding, candidate features, VIN-style model, ordinal/regression losses, and calibration.],
    [Held-out ranking, top-$k$ oracle hit, ablations, calibration, and target-specific failures.],
    [Bounded rollout and $Q_H$],
    [Compare random-valid, one-step greedy, learned one-step scorer, oracle lookahead, temperature-softmax traces, and candidate-query $Q_H$.],
    [Cumulative target @relative-reconstruction-improvement:short, endpoint target gain, scene @relative-reconstruction-improvement:short, cost, invalidity, runtime, and rollout visualizations.],
    [Discussion and conclusion],
    [Interpret limits, scale blockers, simulator gaps, semantic/global planning, and real-device follow-up paths.],
    [Scope-bound conclusion and reproducibility package.],
    bottomrule(),
  ),
  caption: [Retained preliminary chapter outline from the proposal.],
) <tab:thesis-draft-outline>

#research_todo(
  [Decide whether the final thesis keeps the current five-chapter skeleton or expands to the more detailed outline above.],
  source: [proposal outline; current main.typ skeleton],
  gate: [thesis structure freeze],
)

== Open Decisions and Questions

Open advisor decisions are the final scene-level split; symbolic target-match thresholds $(tau_mu, tau_"gap", tau_"support")$; the CORAL-to-#symb.rl.qh interface; the initial actor-visible crop descriptor ablation; the final evidence scale and subset rule; and whether any external or online scaling substrate preserves comparable mesh/oracle target-specific @relative-reconstruction-improvement:short labels. These choices affect the strength and scope of the final evidence, not the target-conditioned finite-candidate question.

#decision_todo([Lock final scene-level split and acceptable scale fallback.], source: [advisor handout; roadmap], gate: [M4/M5])

#decision_todo([Lock target-match thresholds, ambiguity gap, target eligibility, and target-invalid reporting.], source: [proposal problem; advisor handout], gate: [RQ2 protocol])

#decision_todo([Lock whether the myopic scorer freezes, slow-finetunes, or end-to-end fine-tunes when fitting residual #symb.rl.qh.], source: [advisor value-model section], gate: [Q_H training plan])

#question_todo([Can a privileged critic use @ground-truth:short mesh, OBB, or segmentation cues without weakening the non-privileged learned-policy result?], source: [advisor handout], gate: [critic/surrogate decision])

#question_todo([When, if ever, do RGB, semantics, or 3DGS enter the thesis core rather than a bridge study?], source: [proposal and advisor follow-up sections], gate: [M6 scope])

#impl_todo([Validate that Rerun examples, replay integrity, shuffled-candidate evaluation, duplicate-row robustness, and valid-count sensitivity are available for final evidence reporting.], source: [advisor evidence contract], gate: [evaluation implementation audit])

== Future Bridges Retained from Source Material

Continuous control, external simulators, 3DGS control, SceneScript, VLM planning, IQL, CQL, BCQ, sequence decoding, soft/energy policies, PPO, SAC, privileged-teacher distillation, distributional #symb.rl.qh heads, EGNN candidate graphs, sparse/point backbones, and Hestia-style target-then-pose policies remain future or post-M5 ablation material unless the finite-candidate rollout store is stable and preserves the target-specific @relative-reconstruction-improvement:short comparison.

#research_todo(
  [Route each bridge to final discussion, appendix, or deletion after the implemented evidence is known. Do not promote these bridges to thesis-core claims without matched target-specific @relative-reconstruction-improvement:short supervision and oracle re-evaluation.],
  source: [proposal method; advisor adoption ledger],
  gate: [discussion/future-work pass],
)
