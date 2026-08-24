# Performance-goal reporting

Use this route for executable ARIA performance experiments. OMX
`$performance-goal` owns the evaluator contract, campaign state, checkpoints,
and completion. The evaluator writes one immutable `result.json`; ARIA's thin
bridge validates its version-one fields, digests the exact bytes, optionally
mirrors them to W&B, and calls `omx performance-goal checkpoint`.

The result must name the goal, human-readable title, checkpoint status (`pass`,
`fail`, or `blocked`), baseline and candidate revisions, evaluator fingerprint,
summary, finite scalar metrics, and boolean hard gates. W&B is optional
observational evidence: its artifact and run may fail without changing the OMX
checkpoint decision. Formal bridge runs are always named `[senpai] <title>` and
grouped as `senpai`. The existing W&B Runs page shows only runs with the explicit
`aria_autoresearch` config namespace and never reads history for this table.
When a result carries `evidence_series`, every point has a strictly increasing
one-based acquisition `step` and finite metrics; the bridge emits those exact
validated points to W&B only after OMX accepts the checkpoint. It binds every
series metric to the hidden `aria_autoresearch/acquisition_number` custom x-axis;
scalar result metrics are W&B summary values, never one-point history plots.

Run the bridge explicitly from the package environment:

```sh
cd aria_nbv
uv run python scripts/record_performance_checkpoint.py result.json \
  --wandb-project aria-nbv
```

Use `--dry-run` to validate the result and render its digest-backed OMX evidence
without external side effects. Complete the OMX goal only through its normal
passing-checkpoint and Codex-goal handoff; this bridge never completes a goal.
