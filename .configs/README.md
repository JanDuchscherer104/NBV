# Configuration layout

Configuration files are grouped by their runtime owner:

- `generation/vin/`: immutable VIN offline-store writers.
- `generation/rollouts/`: rollout writers grouped by smoke, paired,
  campaign, benchmark, and template roles.
- `training/vin/` and `training/qh/`: Lightning experiment and binner configs.
- `inspection/`: Rerun and figure-generation configs.
- `infrastructure/`: LitKG and LRZ operator configs.
- `models/`: external model configuration assets.
- `evidence/`: reviewed manifests and measurement contracts referenced by
  configs; these are not selectable generation TOMLs.

Commands may use an explicit nested path or a unique TOML basename. Streamlit
selectors display paths relative to `.configs` so similarly named profiles do
not become ambiguous.
