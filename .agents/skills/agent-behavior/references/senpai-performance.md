# SENPAI Modes

Use this reference for either selective adoption of W&B SENPAI mechanics or a
formal measured performance experiment. The nearest ARIA evaluator,
configuration, artifact, and test owners retain behavior authority.

## Formal Performance Mode

Use `$oh-my-codex:performance-goal`; OMX owns the evaluator contract, campaign
state, checkpoints, and completion. The evaluator writes one immutable
`result.json`; the ARIA bridge validates its version-one fields, digests the
exact bytes, checkpoints it with OMX, then publishes and reads back its W&B
observation.

The result names the goal, title, checkpoint status (`pass`, `fail`, or
`blocked`), baseline and candidate revisions, evaluator fingerprint, summary,
finite scalar metrics, boolean hard gates, and `series_axis`. Formal runs are
named `[senpai] <title>`, grouped as `senpai`, and published to W&B. A
publication error leaves the OMX checkpoint intact but blocks goal completion.

When `evidence_series` is present, every point has a strictly increasing,
one-based acquisition `step`, the same finite metric-key set, and finite values.
The bridge binds each series metric to hidden
`aria_autoresearch/<series_axis>`; scalar result metrics are W&B summaries.

```sh
cd aria_nbv
uv run python scripts/record_performance_checkpoint.py result.json \
  --wandb-project aria-nbv
```

Use `--dry-run` for local validation. For a formal run: create/start the OMX
goal, run the evaluator, invoke the bridge, confirm its W&B run ID, then finish
the normal OMX completion audit and Codex-goal handoff. The bridge never
completes a goal.

## Selective Adoption Mode

Adopt only these demonstrated mechanics:

- Write a concise mission contract: metric/direction, data identity, permitted
  edits, baseline, budget, stopping rule, and evidence.
- Bind candidates to an exact baseline and immutable result; preserve useful
  negative results and simplify a confirmed winner into the next baseline.
- Use event-driven evaluator status with bounded timeout, threshold/regression,
  stale-evidence, and terminal states.

Keep SENPAI's runtime separate. Its Kubernetes runner, OpenHands runtime,
GitHub coordination and token, persistent advisor/student processes, and direct
W&B/Weave control plane are excluded. For its pinned upstream maintenance route,
read [`senpai-adoption-updates.md`](senpai-adoption-updates.md).
