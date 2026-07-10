# ARIA-NBV Counterfactual Rollout Generation Thesis Handoff

## Scope

This handoff reviews the current counterfactual rollout generation substrate for thesis Chapter 03 and the connected method/experiment sections. It covers the active thesis sources under `docs/typst/thesis/sections/03-oracle-and-data-generation`, the shared tree helpers in `docs/typst/shared/data-layout-trees.typ`, the historical seminar evidence under `docs/typst/seminar_paper`, the implementation owners in `aria_nbv/aria_nbv/data_handling` and `aria_nbv/aria_nbv/rollouts`, and the live local stores:

- `.data/offline_cache/vin_offline`
- `.data/offline_cache/rollouts_v1_realistic_35_train_20260621.zarr`

The thesis-facing rule is: main text should explain the scientific data contract, actor/oracle separation, masks, labels, and replay evidence. Exact shard internals, CLI recipes, and Slurm-scale processing belong in an appendix or implementation note unless they affect reproducibility or validity.

## Source Order

- Current thesis prose owner: `docs/typst/thesis/main.typ` and included sections.
- Current data-handling implementation owners:
  - `aria_nbv/aria_nbv/data_handling/_offline_store.py`
  - `aria_nbv/aria_nbv/data_handling/_offline_writer.py`
  - `aria_nbv/aria_nbv/rollouts/dataset_writer.py`
  - `aria_nbv/aria_nbv/rollouts/zarr_store.py`
- Historical evidence, not current thesis priority: `docs/typst/seminar_paper/main.typ` and included sections.
- Generated context refreshed by `make context`: `docs/_generated/context/source_index.md`, `docs/_generated/context/literature_index.md`, `docs/_generated/context/data_contracts.md`.

## Already Covered

- `03-01-state-and-visibility.typ` already defines the actor-visible, counterfactual actor, and privileged oracle state boundary. It correctly treats GT meshes, GT OBBs, GT crops, dense all-candidate renders, target labels, and endpoint metrics as oracle/evaluation assets, not actor inputs.
- `03-02-target-task-and-rri-labels.typ` already covers target descriptors, seminar-to-thesis adaptation, target selection, the target-aware candidate mixture, branch sampling recipes, hard invalidity, and target-specific RRI equations.
- `04-method/04-03-candidate-and-replay-contract.typ` already states that model inputs are derived from canonical replay facts rather than making the current tensor encoding the immutable store contract.
- `05-experimental-design/05-02-learning-objective-and-replay-evidence.typ` already separates all-candidate one-step labels from selected-transition Q_H replay rows.

## Missing Or Weak

- Chapter 03 does not yet explain why two stores are required: immutable VIN offline source rows versus standalone target-conditioned rollout replay. Without this, the reader can mistake the rollout store for a mutation of VIN offline data or mistake one-step all-candidate labels for finite-horizon replay.
- The thesis does not yet show the data-layout trees that already exist in `docs/typst/shared/data-layout-trees.typ`.
- `vin-offline-tree` still describes an older `numeric_blocks.zarr/` hierarchy, but the live v7 store writes Zarr arrays directly inside each shard group plus indexed MessagePack record blocks.
- Chapter 03 should briefly state which layout details belong in the master thesis body and which belong in an appendix: normalized row groups and masks are scientifically relevant; exact chunking, local paths, and Slurm job mechanics are reproducibility/appendix details.
- Streamlit-supported diagnostics are not yet surfaced as thesis evidence slots. The app already supports target audit plots, candidate validity/rejection diagnostics, rollout objective traces, selected-depth quicklooks, and candidate geometry distributions; the thesis should mention these as required figures/tables before final results are interpreted.

## Live Dataset Evidence

### VIN offline source store

Command:

```bash
cd aria_nbv && uv run nbv-offline-info summary --store /home/jd/repos/ARIA-NBV/.data/offline_cache/vin_offline
cd aria_nbv && uv run nbv-offline-info tree --store /home/jd/repos/ARIA-NBV/.data/offline_cache/vin_offline
```

Observed facts:

- Store version: 7.
- Rows: 48 samples, 38 train and 10 validation.
- Materialized blocks: backbone, candidate point clouds, and depths are present; detected OBB, GT OBB, and trajectory blocks are not materialized in the manifest.
- Numeric footprint: 396.85 MiB.
- Core row shapes include EVL/VIN backbone fields such as `backbone.occ_pr`, `backbone.occ_input`, `backbone.cent_pr`, and `backbone.counts` with `[row, 1, 1, 48, 48, 48]`-style local voxel support; `backbone.pts_world`; one-step oracle candidates/depths/RRI; and `vin.points_world` / `vin.t_world_rig`.
- Physical layout: `manifest.json`, `sample_index.jsonl`, split arrays, and `shards/shard-*`. Each shard has a `zarr.json`, direct Zarr arrays, and indexed MessagePack record blocks such as `backbone__payload.msgpack`, `oracle__candidates.msgpack`, `oracle__candidate_pcs.msgpack`, and `oracle__depths_payload.msgpack`.

Implementation anchors:

- `aria_nbv/aria_nbv/data_handling/_offline_store.py` owns the immutable on-disk layout and reader.
- `OFFLINE_DATASET_VERSION = 7`.
- `VinOfflineShardWriter.write_numeric_block` writes arrays directly into the shard Zarr group.
- `VinOfflineShardWriter.write_record_block` writes indexed per-row MessagePack diagnostics.

### Standalone rollout replay store

Command:

```bash
cd aria_nbv && uv run nbv-rollouts-info --store /home/jd/repos/ARIA-NBV/.data/offline_cache/rollouts_v1_realistic_35_train_20260621.zarr --validate --stats --json
```

Validation and manifest facts:

- Validation passed with `errors=[]`.
- Schema: `aria_nbv.rollout_zarr_q_invalidity`, version `1.0-target-rollout-core`.
- Created: 2026-06-21T15:25:04Z.
- Counts: 16 sources, 16 targets, 96 rollouts, 160 steps, 9600 candidates, 9600 candidate diagnostics, 160 selected-depth rows, 160 persisted `q_h` states, 60 max candidates, 0 target-eval crop rows.
- Reward/return contract: `q_h_reward_metric=target_root_gain`, `return_semantics=cumulative_target_root_gain`, `q_h_horizon=2`.
- Retention: `field_retention_policy=compact_selected_heavy`; selected depth is enabled at 240 x 240, float16 depth and bool validity mask; target eval crops are disabled and empty in this store.
- Source coverage: 16 train sources from scene 81286 across four VIN offline shards.

Diagnostic facts:

- Full shell candidates: 9600.
- Valid candidates: 3757, valid fraction 0.391.
- Invalid reasons: `CLEARANCE_TOO_SMALL=5174`, `PATH_SEGMENT_COLLISION=669`.
- Valid per step: mean 23.48, median 22, min 2, max 40.
- Valid component counts: `forward_local=1846`, `target_bearing_local=1685`, `lateral_target_bypass=226`.
- Selected component counts: `forward_local=84`, `target_bearing_local=66`, `lateral_target_bypass=10`.

Implementation anchors:

- `aria_nbv/aria_nbv/rollouts/dataset_writer.py` reads strict-v7 VIN offline rows with live snippets/meshes, selects targets, generates target-aware finite candidate tables, scores target-cropped oracle labels, and writes a separate rollout store.
- `aria_nbv/aria_nbv/rollouts/zarr_store.py` owns the standalone row-table schema, derived `q_h/` view, invalidity masks, selected-depth retention, and validation.

## Streamlit-Supported Thesis Diagnostics

Existing app support can be used to generate result figures or explicit placeholders:

- `app/panels/target_audit.py`: target validity, class/source histograms, target support/projection scatter.
- `app/panels/candidates.py`: candidate centers/frusta, position and direction distributions, rule masks, rejection bars.
- `app/panels/counterfactual_rollouts.py`: live rollout target selection, invalid-reason bars, candidate score scatter/histogram, selected-depth visualizations.
- `app/panels/stored_rollouts.py`: rollout store validation, objective traces, policy/branch summaries, selected-depth quicklooks, target audit, validity waterfall, candidate audit, geometry distributions.
- `app/panels/depth.py`: all-candidate depth grids and depth histograms for rendered oracle candidates.

The thesis patch should not claim final results from these plots until final experiment manifests exist. It should define them as required diagnostics and use the current 35-sample store as audit-scale evidence.

## Patch Targets

1. Update `docs/typst/shared/data-layout-trees.typ` so the VIN offline tree matches v7 shard layout and the rollout tree says schema `1.0-target-rollout-core`, not the older schema note.
2. Add a new Chapter 03 subsection file, `03-03-replay-stores-and-diagnostics.typ`, that:
   - explains the two-store design,
   - includes data-layout trees for VIN offline, store relation, and rollout replay,
   - states the live audit counts,
   - separates main-thesis versus appendix detail,
   - defines the required diagnostic figure/table slots.
3. Include the new subsection from `03-oracle-and-data-generation/index.typ`.
4. Add brief cross-chapter wording only if needed so Chapter 04 and Chapter 05 clearly consume the replay evidence rather than redefining it.

## Verification Before Patch

- `make context` completed and refreshed generated context.
- `nbv-rollouts-info --validate --stats --json` completed with validation `ok=true`.
- `nbv-offline-info summary/tree/samples` completed for `.data/offline_cache/vin_offline`.
- Known warning: the Python environment emits a `pkg_resources` deprecation warning from TorchMetrics imports; it does not affect the data-store validation.

