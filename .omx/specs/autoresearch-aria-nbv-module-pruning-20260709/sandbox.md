# Sandbox Notes

Date: 2026-07-09

## Mode

Read-only architecture research over current source plus `.omx` artifacts. This pass only writes `.omx` planning artifacts and a native debrief.

## Worktree State

The worktree was already dirty before this pass, including source changes across `app`, `lightning`, `pipelines`, `rollouts`, `rri_metrics`, `tests`, and docs. Those source changes are treated as pre-existing user/agent drift and were not reverted.

## Skills And Evidence Surfaces

- `oh-my-codex:autoresearch` for validator-gated artifact structure.
- `oh-my-codex:code-review` for independent architecture/code-review evidence.
- `improve-codebase-architecture` and `codebase-design` for deep-module vocabulary and boundary criteria.
- `mempalace-aria-nbv:agent-behavior` for ARIA-NBV source-order and verification expectations.
- `mempalace-aria-nbv:graphify` for first-pass architecture graph evidence.
- `mempalace-aria-nbv:simplification` for pruning and redundancy triage.

## Graphify Evidence

Query used:

```bash
graphify query "Which ARIA-NBV modules currently overlap on data_handling, oracle RRI scoring, rollouts, rri_metrics, pipelines, target selection, endpoint gains, and dataset storage? Identify likely redundancy and pruning seams."
```

The graph surfaced the same coupled cluster as the source review: `rollouts.__init__`, `rollouts.counterfactuals`, `rollouts.target_counterfactuals`, `rollouts.dataset_writer`, `rollouts.zarr_store`, `pipelines.oracle_rri_labeler`, `data_handling._target_selection`, and `rri_metrics.metrics.multi_step`.

## Independent Lanes

- `architect` lane: found `BLOCK` architectural status because `rollouts` still owns scoring, generation, and replay/storage while `rri_metrics` still exports oracle scoring from the metric root.
- `code-simplifier` lane: identified concrete pruning targets including duplicate `_read_string_array`, generation code in `rollouts`, app panel pure logic, repeated rollout read helpers, and duplicate target invalid-reason decoding.
- `code-reviewer` lane: requested after the user invoked code-review; result is incorporated in `report.md` if available before final validation.

## Stop Condition

Stop after writing the report, HTML map, completion JSON, and debrief, then validating JSON syntax, required headings, and debrief memory checks.
