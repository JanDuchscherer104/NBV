# Rerun Inspector

`aria_nbv.rerun_inspector` is a read-only visual diagnostic for immutable VIN
offline samples and persisted rollout-Zarr chains. It does not recompute
labels, train models, mutate a VIN store, or mutate a rollout store.

## Inputs and ownership

Offline inspection selects an immutable `VinOfflineSample` through
`_sample.py`; `_metadata.py` checks the required visual inventory before Rerun
recording begins. Required visual layers need semidense points, a reference
pose, and candidate poses/frusta. Optional sample fields are represented as
inventory metadata or warnings rather than synthesized payloads.

For rollout inspection, `_rollout_zarr.py` uses the typed projections in
`aria_nbv.rollouts.read_model` for rollout rows, ordered full-shell candidates,
selected transitions, target rows, and selected depth. Rerun owns entities,
colours, timelines, layer policy, and display transforms. The remaining direct
array reads used for branch selection and Q_H metadata summaries leave a full
read-model migration open; they do not give this package ownership of the
rollout schema.

## Display contracts

- Offline candidate tensors use `candidate_count` as the valid prefix; padded
  candidate rows are not logged. A zero-candidate sample has no candidate
  layers. With an available validity mask, all-invalid candidates can be shown
  as invalid diagnostics but never produce a top-oracle layer.
- Candidate poses and frusta are world-frame display geometry. CW90 and image
  rotation helpers operate on copied display arrays only; deterministic
  downsampling is also display-only.
- GT mesh/OBB, oracle RRI, target-match, and selected-depth layers are labelled
  diagnostic or evaluation overlays. They do not become actor-visible state or
  alter source masks, ordering, values, or records.

## Recording and verification

`_cli.py` owns TOML loading, selection/output overrides, and viewer launch.
`_session.py` initializes Rerun and opens exactly one configured `save`,
`spawn`, or `connect` sink before entity logging; save mode writes the requested
`.rrd` destination only.

Focused test seams are fake-Rerun lifecycle and logger tests in
`tests/rerun_inspector/test_loggers.py`, public CLI override and preflight tests
in `tests/rerun_inspector/test_rerun_cli.py`, frustum/display tests in
`tests/rerun_inspector/test_frusta.py`, and rollout-Zarr consumption tests in
`tests/rerun_inspector/test_rollout_zarr_logger.py`.
