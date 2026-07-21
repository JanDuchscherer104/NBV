# Lightning

`aria_nbv.lightning` owns training lifecycle and source composition. It does
not own metric formulas, Oracle label generation, or immutable data codecs.

## Source Composition

`lit_datamodule.py` composes the discriminated online/offline source union.
Online generation is implemented by `oracle.pipelines.online_vin`; immutable
offline source configuration is implemented by
`data_handling.offline.source`.

| Symbol | Kind | Visibility | Before module | Current module | Final owner | Status |
|---|---|---|---|---|---|---|
| `VinDatasetSourceConfig` | alias | public | `data_handling._vin_sources` | `lightning.lit_datamodule` | `lightning.lit_datamodule` | moved: RWP03A |
| `VinDataModuleConfig` | config | public | `lightning.lit_datamodule` | `lightning.lit_datamodule` | `lightning.lit_datamodule` | already aligned |
| `VinDataModule` | class | public | `lightning.lit_datamodule` | `lightning.lit_datamodule` | `lightning.lit_datamodule` | already aligned |

The `kind = "online"` and `kind = "offline"` discriminators and all nested
TOML fields are frozen configuration contracts.

## Finite-Horizon Q_H Training

The target-conditioned rollout path is intentionally separate from the
scene-wise one-step CORAL stack:

- `qh_data.py` joins lazy rollout transitions with actor-only VIN evidence and
  owns padded distributed training plus replicated exact validation/test
  loading, avoiding uneven-rank DDP evaluation.
- `qh_module.py` owns selected-action fitted Double-Q loss and the frozen hard-
  synchronized target network.
- `qh_experiment.py` and `qh_cli.py` compose the dedicated stack behind
  `nbv-train-qh` without widening `VinLightningModule`.

Use `.configs/train_qh_v0_smoke.toml` locally and
`.configs/train_qh_v0_lrz.template.toml` with
`scripts/templates/lrz/qh_training_one_node.sbatch` on one LRZ node. Replace
all `/ABS/PATH/...` placeholders before running; resume from an explicit
Lightning checkpoint with `--resume`.
