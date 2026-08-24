# Performance-goal reporting

Use this route for executable ARIA performance experiments. OMX
`$performance-goal` owns the evaluator contract, campaign state, checkpoints,
and completion. The evaluator writes one immutable `result.json`; ARIA's thin
bridge validates its version-one fields, digests the exact bytes, optionally
mirrors them to W&B, and calls `omx performance-goal checkpoint`.

The result must name the goal, checkpoint status (`pass`, `fail`, or
`blocked`), baseline and candidate revisions, evaluator fingerprint, summary,
finite scalar metrics, and boolean hard gates. W&B is optional observational
evidence: its artifact and run may fail without changing the OMX checkpoint
decision. The existing W&B Runs page shows only runs with the explicit
`aria_autoresearch` config namespace and never reads history for this table.

Run the bridge explicitly from the package environment:

```sh
cd aria_nbv
uv run python scripts/record_performance_checkpoint.py result.json \
  --wandb-project aria-nbv --wandb-group <goal-slug>
```

Use `--dry-run` to validate the result and render its digest-backed OMX evidence
without external side effects. Complete the OMX goal only through its normal
passing-checkpoint and Codex-goal handoff; this bridge never completes a goal.
