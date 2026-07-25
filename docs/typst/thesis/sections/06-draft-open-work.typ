#import "../draft_markers.typ": *
#import "../../shared/symbols.typ": symb

= Development Diary

#archive_note(
  [This marked diary is a development-only record. It is excluded from submission mode; only evidence-backed definitions, protocols, and results graduate into the thesis body.],
  source: [thesis mode contract],
)

== Evidence Sequence

The current executable substrate is the finite-candidate oracle/data contract: target tasks, complete candidate tables, hard validity masks and reasons, target-specific oracle labels, selected transitions, and provenance can be represented without making privileged labels actor-visible. This establishes a data and evaluation interface, not a learned-policy result.

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  source: "finite-candidate oracle, replay, and reporting contracts",
  gate: [validated stores with matched manifests and support diagnostics],
)[The finite-candidate contract is the retained starting point. Its available artifacts support implementation readiness, while population-level rollout evidence remains absent.]

The next gate is actor-visible target selection followed by a target-conditioned myopic scorer over the same candidate table. The current GT target sampler defines oracle tasks and labels; it is not actor-visible matching. The scorer must therefore be evaluated only after observed or predicted targets are matched to GT evaluation targets and held-out ranking, calibration, and oracle-rescored selected actions are available.

#impl_todo(
  [Implement and validate observed/predicted target matching, then establish the actor-visible target-conditioned one-step scorer as the myopic control.],
  source: [RQ3 and M3--M4 contracts; repo:.agents/todos.toml\#todo-053],
  gate: [held-out target matching and myopic scorer evidence],
)

Only after that control is stable does bounded oracle lookahead test whether the fixed candidate support contains non-myopic endpoint-gain headroom over one-step oracle greedy. If the measured headroom is negligible, the correct result is a limitation of the evaluated split, targets, horizon, branch factor, and candidate distribution; model complexity does not repair absent headroom.

#validation_todo(
  [Measure bounded oracle-lookahead headroom under matched roots, candidate support, validity rules, and acquisition budgets.],
  source: [RQ2 and M5 contracts; repo:.agents/todos.toml\#todo-026],
  gate: [positive, uncertainty-qualified held-out headroom],
)

Finite-horizon #symb.rl.qh is trained and interpreted only if that headroom gate passes. Its selected actions must be re-evaluated by the same oracle, and its claim is limited to recovered headroom over the learned one-step scorer under matched support and budget. Confirmatory reporting then requires a frozen scene-disjoint held-out population, paired endpoint outcomes, uncertainty, exclusions, support counts, failures, runtime, and storage evidence joined through the same manifests.

#decision_todo(
  [Freeze claims only from a validated confirmatory report bundle with paired held-out policy outcomes and complete population accounting.],
  source: [experimental-design and reporting contracts; repo:.agents/todos.toml\#todo-037],
  gate: [confirmatory bundle freeze],
)

== Current Blockers and Failures

An unbounded candidate render exhausted accelerator memory on the first large candidate batch. Bounded rendering mitigates that specific failure mode, but it does not establish population throughput or policy evidence.

The prepared three-root H3--H8 campaign produced no rollout store because its configured source, candidate generator, and depth renderer required CUDA or an LRZ allocation that was unavailable for the run. The campaign remains configuration and provenance evidence only.

The current GT target sampler is not an actor-visible matching protocol. No validated confirmatory population rollout bundle with paired endpoint outcomes exists, so no held-out policy comparison is available.

#validation_todo(
  [Require completed stores, matching manifests, resource summaries, and recorded failures before extrapolating rollout bandwidth, storage demand, headroom, or policy quality.],
  source: [rollout attempts and H3--H8 campaign record; repo:.agents/todos.toml\#todo-089],
  gate: [validated campaign and confirmatory evidence],
)

== Rejected Scope

Online discrete #symb.rl.qh over the existing ASE mesh/oracle loop is deferred until offline finite-candidate evidence is stable. Continuous target-then-pose control, generic simulator integration, and external online reinforcement-learning frameworks are later work after the online-discrete gate; they do not substitute for the finite-candidate thesis result.

#prune_todo(
  [Keep online-discrete, continuous-control, and simulator material out of the core claim until their upstream finite-candidate evidence gates pass.],
  source: [RQ5--RQ6 and M6 contracts; repo:.agents/todos.toml\#todo-038],
  gate: [stable offline finite-candidate evidence],
)

== Directional-Memory Hypothesis

#research_todo(
  [Treat target-centred directional memory as an ablation hypothesis, not an established actor feature or contribution. It must be implemented, mask-audited, and compared against pose distance and overlap before any predictive claim enters the manuscript.],
  source: [RQ3 representation hypothesis; repo:.agents/todos.toml\#todo-060],
  gate: [paired held-out ablation],
)

#figure(
  align(center, image(
    "../figures/directional_memory_view_novelty.pdf",
    width: 100%,
  )),
  caption: [Development-only directional-memory fixture. The sphere and Mollweide panels show the same logged ASE camera directions in a target-object frame; the orange query is another logged pose used to inspect one prospective second-moment novelty definition. No smooth field, spherical-harmonic representation, or learned benefit is claimed.],
) <fig:directional-memory-hypothesis>

#include "06-draft-invariant-trees.typ"
