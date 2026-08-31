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

`candidate_benchmark.py` also owns the single candidate-family preflight
reducer consumed by the info CLI, campaign admission, Plotly figures, and the
stored-rollout panel. Its root floor is resolved and persisted as
`max(12, ceil(0.25 * Nq))`; this total-support test is separate from the
versioned family floor. Applicable families require selected support, while
inapplicable cells remain visible and non-failing and unknown legacy
applicability fails closed for deployment. Direct target-root-gain variation is
state-conditional: it is tested only over eligible factual states with at
least two compatible valid oracle labels, reports both label and eligible-state
denominators, and uses the manifest-owned `minimum-per-state-range`
aggregation revision. The Phase-A path has no reward labels, so `flat_gain` is
unavailable rather than inferred from geometry. This remains a no-render,
no-reward-label proposal-support audit with privileged GT target instruction
and mesh validity, not an oracle-free audit. Passing it does not authorize
broad generation: the later hash-bound issue-120/WP18 gate remains mandatory.

`benchmark_from_sampling_result` is the candidate-only Phase-A seam. It copies
the generator's full-shell component lineage, hard-valid mask, rule reason
bitsets, and available continuous margins, while assigning no oracle labels or
policy-selected transition. Its family `selected` counts mean compact final
action-shell membership, exactly as in the store-backed reducer. The campaign
preflight serializes these same benchmark records and reducer output into one
content-hashed evidence JSON; it does not reinterpret candidate support.

### Current Phase-A evidence

The frozen 100-scene control is
[`candidate_family_phase_a_wp02.json`](../../../docs/contents/evidence/candidate_family_phase_a_wp02.json)
(artifact SHA-256 `b04cf38ce1c7797d4cd660a89ccbcefabb2f5f0581fc73c1b7b569e99e48a65c`;
compact file SHA-256
`aad88d378e16114cb7108dd829c4f77abb21e3daea1cb90ce1c98ec96c5ba25a`).
It covers all 100 reviewed source rows, scenes, and target states with no
exclusions. Of 6,000 attempted rows, 3,146 entered the compact valid shell, but
the gate is a no-go: 44 state/family cells collapsed, 24 states missed the
non-forward target-family floor, and 8 states missed the root-support floor.
`flat_gain` is explicitly unavailable with label and eligible-state
denominators both zero because Phase A contains no reward labels. The full
[state-by-family heatmap](../../../docs/contents/evidence/candidate_family_phase_a_wp02_heatmap.html)
and [per-state funnels](../../../docs/contents/evidence/candidate_family_phase_a_wp02_funnels.html)
are derived from that same canonical reducer result. The artifact binds native
source-store identity `605453ba11869e40`, writer configuration SHA-256
`603c5785c2163833fff466a29b5bc6039a1d23a397f4774161368016fce33055`,
generation revision `a2ae86b7463930c9`, and the recorded CUDA runtime. It
satisfies issue #54's all-100-scene evidence step, but the failed sampler-pass
criterion means issue #54 remains open; it does not admit broad generation.

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
| `candidate_benchmark` / `candidate_support_plotting` | Immutable candidate evidence, canonical family preflight, and presentation-free Plotly construction. |
| `s2_analysis` | Validated S² reducer configuration, strict store acquisition, and evidence digests. |
| `s2_plotting` | Canonical target-frame S² Plotly encoding shared by Streamlit and immutable report export. |
| `audits` | Provenance, validity, path, entropy, and order diagnostics. |

Target-frame S² inspection separates three observables: selected camera
displacement, selected optical-axis direction, and calibrated proxy-surface
frustum support. `inspection.py` owns the complete equal-solid-angle reducer;
`s2_analysis.py` owns configured store acquisition and evidence identity;
`s2_plotting.py` owns only the deterministic Plotly encoding. The target OBB
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
