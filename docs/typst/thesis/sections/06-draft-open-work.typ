#import "../../shared/macros.typ": *
#import "../draft_markers.typ": *
#import "@preview/booktabs:0.0.4": *

= Draft Intake and Open Work

#archive_note(
  [This chapter preserves substantive planning material from the retired proposal and advisor handout. It is part of the thesis seed, not final thesis prose. Each item should either graduate into the main chapters, move to an appendix, or be removed after its source decision is resolved.],
  source: [archived proposal and advisor handout],
)

== Schedule and Risk Control

The planned thesis window from the proposal ran from 29 April 2026 to 30 September 2026. The roadmap owns the live schedule; this appendix keeps only the exit-condition logic. The work must progress from source-aligned proposal scope, through data/oracle validation, one-step target scoring, target-task rollouts, oracle-lookahead headroom, and #symb.rl.qh recovery, before bridge designs such as online discrete control or continuous policies are promoted. Final writing freezes only after manifests, coverage, failure cases, reproducible configs, and PDF artifacts are generated.

#conflict_todo(
  [The absolute dates are retained from the proposal source but must be checked against the current roadmap before they appear as final thesis text.],
  source: [proposal schedule; current roadmap],
  gate: [roadmap synchronization],
)

== Preliminary Thesis Outline

The active thesis body now uses the expanded chapter graph: foundations, oracle/data generation, method, experimental design, results, discussion, and conclusion. That split keeps oracle state, target-RRI labels, candidate validity, and rollout/replay stores out of the learned-method chapter, while Chapter 04 owns the scene representation, descriptor/query pools, candidate-row architecture, and finite-horizon #symb.rl.qh model.

#research_todo(
  [Freeze whether any remaining appendix-only draft material should be promoted into the active 01--08 chapter graph.],
  source: [proposal outline; current main.typ chapter graph],
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
