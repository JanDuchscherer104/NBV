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
