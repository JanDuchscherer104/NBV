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
policy-selected transition. Candidate centres, target-relative vectors, and
camera-forward directions use one target-aligned, world-Z-up basis: axis 0 is
the horizontal expansion-to-target direction, axis 1 points left, and axis 2
is world up. Positions are divided by the current three-dimensional target
distance; directions remain unit vectors. Its family `selected` counts mean
compact final action-shell membership, exactly as in the store-backed reducer.
The campaign preflight serializes these same benchmark records and reducer
output into one content-hashed evidence JSON; it does not reinterpret support.

### Current Phase-A evidence

The frozen 100-scene control is
[`candidate_family_phase_a_wp02.json`](../../../docs/contents/evidence/candidate_family_phase_a_wp02.json)
(artifact SHA-256 `6d33e9e3d68737c8a6a5589ae5117c1e4d7fcaa89056fcfcaec1d315e4509c83`;
compact file SHA-256
`843d1e6c41df7746db1187a92eb7b29f9f18263bb33cbb5e3b4efc9f1acea017`).
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
`4ae05a1e4066756a47f9ba00d914b8f4337321ae8dcd161a62228d02f71d0587`,
generation revision `a2ae86b7463930c9`, and the recorded CUDA runtime. It
satisfies issue #54's mechanism and all-100-scene evidence checklist: the
fail-closed gate exists and produced the required bounded no-go. Sampler
remediation and a later passing rerun remain separate follow-up work; this
artifact does not admit broad generation. The stored shells, support counts,
verdict, and execution revision are unchanged from the one real run.
Transformation `authenticated_target_frame_correction_no_candidate_rerun`
rotates only the stored candidate centres, target-relative vectors, and view
directions into the canonical target-aligned Z-up basis. Geometry correction
revision `phase-a-target-aligned-z-up-v1` and predecessor artifact
`60b271db515a5e665fcb7bbeeecb87e6acb4bac2ff8e28b26b7308911328759c`
bind that correction; no candidate generation or GPU population was rerun. The
corrected 100-record payload has SHA-256
`43a4fbba2e412c6a7d4b9a0c2a8b6f3d064dde4d9387566ea29f077365447c89`.

The current record key is the composite `(scene_key, state_key)`. This is
sufficient for the historical one-root Phase-A artifact. WP03/WP06 must extend
provenance with proposal/root/replica identity before repeated physical states
are admitted; state labels alone must not merge those future repetitions.

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
