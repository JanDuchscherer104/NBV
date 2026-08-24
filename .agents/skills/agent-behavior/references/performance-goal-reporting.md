# Performance-goal reporting

Use this route for executable ARIA performance experiments. OMX
`$performance-goal` owns the evaluator contract, campaign state, checkpoints,
and completion. The evaluator writes one immutable `result.json`; ARIA's thin
bridge validates its version-one fields, digests the exact bytes, checkpoints
it with OMX, then publishes and reads back its W&B observation.

The result must name the goal, human-readable title, checkpoint status (`pass`,
`fail`, or `blocked`), baseline and candidate revisions, evaluator fingerprint,
summary, finite scalar metrics, boolean hard gates, and a named `series_axis`.
Formal bridge runs are always named `[senpai] <title>`, grouped as `senpai`, and
published to W&B; a publication error leaves the OMX checkpoint intact but
blocks goal completion. The bridge reads back the published identity and
immutable provenance before it returns a run ID. The existing W&B Runs page
shows only runs with the explicit `aria_autoresearch` config namespace and never
reads history for this table. When a result carries `evidence_series`, every
point has a strictly increasing one-based acquisition `step`, the same finite
metric-key set, and finite values. The bridge binds every series metric to the
hidden `aria_autoresearch/<series_axis>` custom x-axis; scalar result metrics
are W&B summary values, never one-point history plots.

Run the bridge explicitly from the package environment:

```sh
cd aria_nbv
uv run python scripts/record_performance_checkpoint.py result.json \
  --wandb-project aria-nbv
```

Use `--dry-run` to validate the result and render its digest-backed OMX evidence
without external side effects. For a formal SENPAI run, create/start the OMX
goal, run the evaluator, invoke this bridge, confirm its W&B run ID, then pass
the normal OMX completion audit and Codex-goal handoff. The bridge never
completes a goal.
