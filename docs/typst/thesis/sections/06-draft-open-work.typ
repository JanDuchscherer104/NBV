#import "../draft_markers.typ": *

= Development Diary

#archive_note(
  [This marked diary is a development-only record. It is excluded from submission mode; only evidence-backed definitions, protocols, and results graduate into the thesis body.],
  source: [thesis mode contract],
)

== Decisions Retained

The thesis keeps the privileged oracle and actor-visible policy as separate contracts, evaluates finite candidate sets under a shared validity mask, and treats target-specific reconstruction improvement as the common comparison signal. Rollout stores retain selected transitions and provenance rather than becoming a second implementation of the oracle or training pipeline.

#decision_todo(
  [Freeze the scene-disjoint analysis population and the minimum evidence scale only when the resolved manifests and exclusion ledger are available.],
  source: [experimental-design contract],
  gate: [confirmatory bundle freeze],
)

== Failures That Changed the Plan

Early rollout attempts reached the mesh-rendering path but exceeded available accelerator memory when candidate views were rendered without a bounded batch. This failure narrowed the immediate claim to implementation readiness and made peak memory, throughput, failure provenance, and completed-store validation explicit scale gates.

#validation_todo(
  [Require completed stores, matching manifests, resource summaries, and recorded failures before extrapolating rollout bandwidth or storage demand.],
  source: [rollout attempt artifacts],
  gate: [cluster-readiness evidence],
)

== Rejected Scope

Continuous actions, online simulators, additional scene representations, and alternative reinforcement-learning families are excluded from the core study while the finite-candidate target-conditioned comparison remains unvalidated. They would change both the action contract and the supervision regime, so adding them now would weaken rather than extend the primary experiment.

#prune_todo(
  [Delete bridge material that cannot be tied to a concrete limitation or a matched follow-up experiment after the confirmatory analysis is complete.],
  source: [scope review],
  gate: [discussion freeze],
)

== Next Evidence Gates

The next admissible evidence is a validated report bundle that fixes the study population, records target and candidate exclusions, supplies paired endpoint outcomes with uncertainty, and joins runtime and storage statistics to the same manifests. Only then can the manuscript replace the present availability statements with policy comparisons.

#impl_todo(
  [Export the confirmatory report bundle, compile both thesis modes against it, and inspect the resulting tables and failure cases before freezing claims.],
  source: [reporting contract],
  gate: [claim freeze],
)
