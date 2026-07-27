# Frozen Q_H loader benchmark protocol

H and F use the byte-identical files in `qh_instrumentation_allowlist.json`.
Run the LOC audit in `baseline` phase at H, and in `final` phase only after the
three configured future symbols have been added exactly once. The baseline
must measure exactly 2,480 physical LOC.

Generate a truthful small V0 corpus with the existing rollout operator:

```sh
cd aria_nbv
uv run nbv-build-rollouts --config-path ../.configs/build_rollouts_qh_v0_baseline.toml
```

The configured output is untracked under the shared `.data` cache. Never
rename or relabel an existing `v1_observed` store. Record the source store,
resulting rollout-store digest, target protocol, command, hardware/allocation,
and H/F commit in external evidence.

For each batch size `[1, 2, 4, 8, 16, 32, 64]`, construct the same
non-shuffled DataLoader over one ordered key list. The benchmark uses one
`CyclingLoader`: five warmup calls, reset to the first key, then every measured
repetition continues until both 100 batches and 30 seconds have elapsed. Run
exactly three repetitions for every grid point with peak pinned host memory at
most 1 GiB; retain rejected points and their reason in the external JSON.

The caller supplies a small factory returning the existing legacy or future
DataLoader. The harness does not import production DTOs; it structurally reads
lineage keys plus `transition.row_train_mask` or `supervision.row_train_mask`.
Write output outside the source worktree, for example:

```sh
python scripts/qh_loader_benchmark.py \
  --config .configs/qh_loader_benchmark.json \
  --loader-factory operator_module:make_loader \
  --execution-commit "$(git rev-parse HEAD)" \
  --output /external/evidence/qh-h-loader.json
```
