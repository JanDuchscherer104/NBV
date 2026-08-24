# SENPAI

## Performance

Use `$oh-my-codex:performance-goal`. The evaluator writes immutable
`result.json`; `record_performance_checkpoint.py` checkpoints it, then publishes
and reads back W&B. Complete only after that run is named `[senpai] <title>`,
grouped `senpai`, and has its immutable provenance. Series use `series_axis`;
endpoints are summaries.

## Adoption

Retain mission contracts, immutable candidate evidence, event-driven evaluation,
and confirmed-winner promotion. Keep SENPAI runtime and control plane external.
For the upstream pin and update route, read
[`senpai-adoption-updates.md`](senpai-adoption-updates.md).
