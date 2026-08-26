# SENPAI Performance Loop

Use `$oh-my-codex:performance-goal` as the single lifecycle owner. This local
adapter adds research roles and mandatory W&B evidence; it does not start a
second `$oh-my-codex:autoresearch-goal` or vendor SENPAI's runtime.

## Roles

- **Professor:** the leader freezes the evaluator and selects one hypothesis.
- **Researcher:** a separate `researcher` agent consolidates evidence without
  mutating the candidate. Use [`literature-research`](../../literature-research/SKILL.md)
  for scholarly discovery and `aria-nbv-context` for exact local/API owners.
- **Implementer:** an `executor` agent changes only the assigned candidate
  surface and returns the exact revision and evaluator output.
- **Critic:** a separate `critic` or `scientific-review` agent checks the
  hypothesis, evidence, gates, and claimed mechanism after measurement.
- **Verifier:** a `verifier` confirms retained bytes, tests, W&B read-back, and
  the final OMX gate.

Formal promotion requires separate Researcher, Implementer, and Critic
contexts. If role separation is unavailable, record the iteration as blocked.

## Iteration

1. **Freeze.** Create/start one performance goal with its evaluator command,
   metric direction, hard gates, mutable paths, budget, and plateau window.
   Start the Codex goal with the emitted objective verbatim and keep it unchanged
   so the completed snapshot matches the OMX workflow.
2. **Research.** Inspect prior experiments and local sources first:
   `docs/literature/sources.jsonl`, matching `tex-src/`, exact code/tests, and
   registered Context7 libraries. Use primary papers, official docs, and pinned
   upstream repositories only to fill an identified gap. Write a task-local
   research brief with exact locators, versions, mechanisms, conflicts, and
   candidate hypotheses.
3. **Assign.** The Professor selects one falsifiable hypothesis and writes one
   bounded assignment containing the baseline, causal change, editable paths,
   evaluator, budget, and stop rule. Hash the research brief and assignment.
4. **Implement.** The Implementer applies only that assignment. Evaluator,
   dataset/split, metric, and hard gates remain frozen.
5. **Measure.** The evaluator writes schema-v2 `result.json` with the iteration,
   hypothesis, brief/assignment hashes, versioned sources, revisions, metrics,
   gates, and optional rectangular `evidence_series`.
6. **Publish.** Run `aria_nbv/scripts/record_performance_checkpoint.py`. It
   leaves OMX blocked while W&B is pending, publishes and reads back the run,
   then records the evaluator verdict. Every run is named `[senpai] <title>`,
   grouped `senpai`, and tagged by goal, iteration, and status.
7. **Review.** The Critic returns `accept`, `revise`, or `reject`. Accept only a
   passing evaluator result with verified W&B provenance and a mechanism that
   survived review. Revision preserves the hypothesis lineage; rejection
   restores only the owned candidate patch.
8. **Continue.** After the declared plateau window without a retained gain,
   pause mutation and return to Research with the failed mechanisms and W&B
   evidence. Complete only after a retained winner, final Critic acceptance,
   and the normal performance-goal completion audit.

Canonical paper and engineering-source additions remain in
`docs/literature/sources.jsonl`; Context7 identities remain in its registry.
Mission briefs are evidence snapshots under the performance-goal root and W&B,
not another repository-wide source catalog.

External grounding is registered as `senpai-performance-loop` and
`karpathy-autoresearch-program` in `.agents/skill-sources.toml`. Those IDs are
provenance only and never activate upstream maintenance.
The retained [adoption provenance](senpai-adoption-updates.md) preserves the
historical debrief path but defines no update procedure.
