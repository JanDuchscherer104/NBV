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

- `data_handling/qh.py` joins rollout transitions with typed VIN evidence and
  admits the framework-neutral train/validation/test corpus.
- `qh_datamodule.py` owns Lightning-partitioned train/validation/test loaders.
  Distributed-sampler padding can duplicate rows in any stage; reported metrics
  represent Lightning's emitted stream rather than a deduplicated exact corpus.
- `qh_module.py` owns selected-action fitted Double-Q loss and the frozen hard-
  synchronized target network.
- `qh_experiment.py` and `qh_cli.py` compose the dedicated stack behind
  `nbv-train-qh` without widening `VinLightningModule`.

Use `.configs/train_qh_v0_smoke.toml` locally and
`.configs/train_qh_v0_lrz.template.toml` with
`scripts/templates/lrz/qh_training_one_node.sbatch` on one LRZ node. Replace
all `/ABS/PATH/...` placeholders and set a nonblank `LRZ_CONTAINER_IMAGE`
before running. Resume or evaluate from an explicit Lightning checkpoint with
`--ckpt-path`; set `stage = "val"` or `stage = "test"` in the strict TOML and
configure the corresponding scene-disjoint corpus.

Before constructing the scorer or Trainer, launcher rank zero create-only writes
`run_manifest.json` with the effective resolved config and hash, corpus and
runtime provenance, and any content-addressed parent-checkpoint reference. This
preflight artifact does not claim the Trainer's actual topology. After the loop,
global zero create-only writes `run_result.json` with success or failure, actual
world size, sampler padding, effective emitted batch size, global step, and
content-addressed parent/evaluated/best/last checkpoint references.

`Q_H` currently admits only the Oracle-GT `v0_gt_input` target protocol and a
two-acquisition horizon. Candidate/history tensors are right-padded; `-1` ids,
false presence/action masks, world/root/camera transform directions, and metre
units are documented on `data_handling.qh.QhInputs`. Invalid actions are
hard-masked and never reinterpreted as low-RRI supervision.
