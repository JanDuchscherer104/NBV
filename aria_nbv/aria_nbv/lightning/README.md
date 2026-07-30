# Lightning

`aria_nbv.lightning` owns training lifecycle and source composition. It does
not own metric formulas, Oracle label generation, or immutable data codecs.

## Source Composition

`lit_datamodule.py` composes the discriminated online/offline source union.
Online generation is implemented by `oracle.pipelines.online_vin`; immutable
offline source configuration is implemented by
`data_handling.vin_store.source`.

| Symbol | Kind | Visibility | Before module | Current module | Final owner | Status |
|---|---|---|---|---|---|---|
| `VinDatasetSourceConfig` | alias | public | `data_handling._vin_sources` | `lightning.lit_datamodule` | `lightning.lit_datamodule` | moved: RWP03A |
| `VinDataModuleConfig` | config | public | `lightning.lit_datamodule` | `lightning.lit_datamodule` | `lightning.lit_datamodule` | already aligned |
| `VinDataModule` | class | public | `lightning.lit_datamodule` | `lightning.lit_datamodule` | `lightning.lit_datamodule` | already aligned |

The `kind = "online"` and `kind = "offline"` discriminators and all nested
TOML fields are frozen configuration contracts.

## Finite-Horizon Q_H Training

The retained `Q_H` surface is an infrastructure seam, separate from the
scene-wise one-step CORAL stack:

- `data_handling.qh_data` and `rollouts.qh_reader` provide the leaf dataset and
  validated reader contracts.
- `qh_datamodule.py` admits compatible, scene-disjoint stage datasets and owns
  only their DataLoaders.
- `qh_module.py` owns scorer-independent fitted-Q optimization. Construct
  `QhLightningModule(config, scorer=...)` with a required scorer that maps
  `QhActorTensors` to `Tensor[B,S,N]` candidate values.
- A non-terminal selected row is excluded when the actor has a valid successor
  but no successor has label support. Terminal rows and states with no
  actor-valid successor keep their immediate-reward boundary target.
- Scorer outputs must be finite only where they participate in the selected
  loss or supported Double-Q backup; padded and unsupported values are ignored.

The package does not provide a production scorer, dedicated CLI, experiment
configuration, run-artifact lifecycle, checkpoint policy, or cluster launcher
for this seam. The reader, dataset, collation, and loader layers support varying
horizons, including mixed-horizon batches; this is not a scientific
claim that an `H >= 3` model has been implemented or evaluated.
