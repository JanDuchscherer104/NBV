# Rollouts

`aria_nbv.rollouts` owns finite-candidate replay, standalone rollout Zarr
stores, QH chain reading, manifests, audits, and presentation-free inspection
projections. Dataset generation is composed by `aria_nbv.oracle.pipelines`;
immutable actor roots remain in `aria_nbv.data_handling.vin_store`.

## Stored Contract

A rollout store contains factual tables for targets, rollout chains, realized
steps, candidate rows, selected actions, source lineage, optional selected
depth, and a validated derived `q_h/` view. The factual tables remain
authoritative; the QH view is a training-hot projection that readers validate
against them.

Candidate support has several distinct meanings:

- materialized candidate rows;
- hard action-valid rows;
- oracle-labelled rows;
- selected transition rows;
- storage padding.

Invalid targets or actions remain masks and reason codes. They are never
fabricated low-RRI or zero-Q labels.

## Generate and Inspect

Run from `aria_nbv/`:

```sh
uv run nbv-build-rollouts \
  --config-path ../.configs/build_rollouts_v1_smoke.toml \
  --dry-run
uv run nbv-build-rollouts \
  --config-path ../.configs/build_rollouts_v1_smoke.toml

uv run nbv-rollouts-info \
  --store ../.data/offline_cache/rollouts_v1_smoke.zarr \
  --validate
uv run nbv-rollouts-info \
  --store ../.data/offline_cache/rollouts_v1_smoke.zarr \
  --json
```

For sharded campaigns, use `nbv-plan-rollout-shards`,
`nbv-status-rollout-shards`, and `nbv-rollout-campaign`. Each completed shard
must pass validation and carry its success/owner sidecars before it is treated
as reusable input.

## Read a Store

```python
from aria_nbv.rollouts import RolloutZarrStoreReader

reader = RolloutZarrStoreReader("rollouts.zarr")
validation = reader.validate()
if not validation.ok:
    raise ValueError(validation.errors)

manifest = reader.manifest()
qh_arrays = reader.q_h_view()
```

Use `read_model.py` for typed, presentation-free projections consumed by
Streamlit and Rerun. Use `QhRolloutReader` when the consumer needs complete
validated QH chains, target protocol identity, source references, and optional
selected-depth evidence.

## Replay and Online Scores

`rollouts.replay` owns in-memory rollout state, policy specifications,
`CandidateScores`, and finite-candidate transition generation. Persisted Zarr
encoding belongs to `zarr_store.py` and `trace.py`.

The online finite-horizon adapter lives in
`aria_nbv.oracle.pipelines.online_qh`. It validates a bundle against the current
decision context, evaluates raw conditional Q, then passes only hard-valid
values into `CandidateScores`. Learned feasibility does not replace the policy
mask.

## Ownership Map

| Module | Responsibility |
| --- | --- |
| `replay` | Policies, in-memory states, score DTOs, and transition engine. |
| `trace` | Normalize replay results into factual persisted rows. |
| `zarr_store` | Store schema, writer, strict reader, and validation. |
| `qh_reader` | Multi-store QH chain decoding and learning/data identity. |
| `qh_geometry` | Stored relative-pose composition into actor tensors. |
| `read_model` | Presentation-free typed projections. |
| `inspection` / `reporting` | Rollout-owned read-only summaries, evidence tables, validation, and compatibility strata. |
| `s2_reporting` | Canonical target-frame S² Plotly encoding shared by Streamlit and immutable report export. |
| `audits` | Provenance, validity, path, entropy, and order diagnostics. |

Target-frame S² inspection separates three observables: selected camera
displacement, selected optical-axis direction, and calibrated proxy-surface
frustum support. `inspection.py` owns the complete equal-solid-angle reducer;
`s2_reporting.py` owns only the deterministic Plotly encoding. The target OBB
normalizer is the geometric mean of its semi-axis lengths, not an
OBB-volume-equivalent sphere radius. Calibrated support uses the half-pixel
continuous image rectangle and remains geometric potential visibility until
depth or mesh intersection establishes true visible target surface.

Detailed table schemas, shapes, and validation failures live in source
docstrings and the [generated API reference](../../../docs/reference/index.qmd).
The shared [scientific reporting module](../reporting/README.md) wraps these
canonical frames into immutable cross-source snapshots; it does not own or
reimplement rollout calculations, Zarr admission, or compatibility decisions.

## Verification

```sh
cd aria_nbv
uv run ruff check aria_nbv/rollouts
uv run pytest tests/rollouts
uv run pytest tests/data_handling/test_qh.py
```

Include Oracle generation, Streamlit, or Rerun tests when changing their
consumer boundary.
