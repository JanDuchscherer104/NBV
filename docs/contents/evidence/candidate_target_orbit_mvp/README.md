# Target-orbit candidate MVP: two-scene CUDA pilot

## Scope

This evidence bundle compares the existing 60-row `realistic_core` candidate
mixture with an equal-budget challenger that replaces 12 target-bearing rows
with 12 deterministic, bilateral partial-orbit rows. The production mixture and
its nonzero 60°/30° seminar view jitter remain unchanged.

The new family preserves the current horizontal target standoff. For target
bearing $b$, world-up tangent $l$, standoff $d$, and signed angle $\alpha_i$,
the world-horizontal offset is

$$
o_i = d b - d\cos(\alpha_i)b + d\sin(\alpha_i)l.
$$

Negative and positive angle subsets are interleaved, so attempted proposals
cover both target sides. Collision, free-space, clearance, and motion rules may
still reject either side; this MVP does not implement family-aware refill.

## Result

The exact post-review candidate was evaluated on the first two real scenes in
[`rollout_campaign100_source_manifest.json`](../../../../.configs/rollout_campaign100_source_manifest.json)
with the CUDA campaign writer configuration and seed `20260728`.

The committed [`generate_store.py`](generate_store.py) is a historical
reproducer bound to implementation revision
[`8fafa02fdb3441c9f9823f620728f413c6ecca91`](https://github.com/JanDuchscherer104/ARIA-NBV/commit/8fafa02fdb3441c9f9823f620728f413c6ecca91).
It fails closed on newer checkouts because the active authoring schema has
changed; check out that exact revision to reproduce either raw CUDA store. The committed
[`candidate-rows.jsonl`](candidate-rows.jsonl) contains all 240 reduced fields
consumed by [`build_evidence.py`](build_evidence.py), so the summary and plots
can also be rebuilt without the private full-store paths:

```console
cd aria_nbv
python ../docs/contents/evidence/candidate_target_orbit_mvp/build_evidence.py
```

The exact generation and raw-store reduction commands, software versions,
profile composition, source hashes, and raw store-manifest hashes are frozen in
[`manifest.json`](manifest.json).

| Metric | `realistic_core` | target-orbit MVP | Interpretation |
| --- | ---: | ---: | --- |
| maximum actor-valid target-root gain, mean over states | 0.046999 | 0.048152 | +2.45% finite-support oracle opportunity; not policy performance |
| target-side count balance, mean over states | 0.000 | 0.500 | one-sided attempted target-conditioned support is reduced |
| circular target-orbit span, mean over states | 24.80° | 70.22° | broader attempted target-conditioned support |
| worst-state valid candidates | 21 | 26 | stronger minimum root support |
| actor-valid candidates | 74 / 120 | 72 / 120 | small aggregate-validity decrease |
| target centre inside calibrated image | 91 / 120 | 93 / 120 | modest framing increase; not occlusion-aware visibility |
| configured family/state pairs with zero valid rows | 1 / 6 | 1 / 8 | scale-up blocker remains; rates use each profile's configured denominator |
| nonzero jitter / bounded-cap compliance | 100% / 100% | 100% / 100% | seminar invariant and empirical cap compliance preserved |

Both profiles contain 24 positive-side, 24 negative-side, and zero neutral
target-conditioned rows after state alignment. Neither profile has an undefined
side-balance state or a state without evaluated target-centre projections. These
counts are persisted in `summary.json`; the balance remains a state-first macro,
so equal pooled side counts do not imply balanced support within each state.
Oracle opportunity and all jitter fractions are also computed per state before
the scene macro. This pilot has zero undefined opportunity, projection, jitter,
or bounded-compliance states; all 120 rows per profile carry jitter residuals
and declare bounded support.

The two target-relative rows above were recomputed after review from the common
`target_aligned_z_up` projection returned by `proposal_support_geometry`. For
each factual state, the target-to-candidate displacement is formed entirely in
that frame. The span is the shortest circular arc covering the target-conditioned
angles, rather than a linear maximum-minus-minimum. This replaces the invalid
frame-mixed values previously reported for those rows.

The observed valid-throughput result was 1.31 versus 1.66 candidates/s, but
renderer cold-start and compilation cost confound a two-run timing comparison;
it is not treated as a general speedup claim and is omitted from the portable
summary.

![Target-normalized candidate centers](candidate-centers.png)

The [interactive version](candidate-centers.html) and the Streamlit inspection
path use the same canonical proposal-support reducer. Streamlit automatically
separates the new `target_orbit` component by `component_name` and stable
`position_id=6`. The default figure remains uncluttered. Passing
`--view-directions` to `build_evidence.py` writes separately named exploratory
`candidate-centers-with-view-directions.{png,html}` assets; it does not overwrite
the hash-bound canonical figure. Enabling *Show valid-candidate view directions*
in Streamlit overlays the same short arrows. Their tails are valid candidate
centres, and each arrow is a fixed-length, ground-projected unit direction of
the camera `+Z` optical axis in the same target-aligned frame. An arrow is
preferable to a triangle glyph because it encodes both origin and direction
without implying another candidate class.

## Interpretation and limits

This is a positive endpoint-prior MVP, not evidence that people universally
orbit objects. It follows the higher-level pattern used by target-centric NBV
work: propose target-relative views, then restrict them by feasible motion. The
[OA-NBV preprint](https://arxiv.org/abs/2603.11072) combines target-centric
visibility scoring with traversable poses, while
[Where to Look Next](https://arxiv.org/abs/2203.02381) separates recommended
viewpoints from a dynamically feasible, collision-free local planner. These
robotics results ground the separation of proposal and feasibility; they do not
establish a wearable-human orbit distribution.

The highest-ROI realism follow-up is therefore empirical calibration against
Project Aria motion. Official [MPS trajectory documentation](https://facebookresearch.github.io/projectaria_tools/docs/ARK/mps)
provides high-frequency 6DoF trajectories, and
[Aria Digital Twin](https://openaccess.thecvf.com/content/ICCV2023/html/Pan_Aria_Digital_Twin_A_New_Benchmark_Dataset_for_Egocentric_3D_ICCV_2023_paper.html)
provides real egocentric sequences with continuous device poses. Those sources
can estimate conditional step-length, yaw-rate, lateral-motion, and dwell priors
without assuming that a mobile-robot trajectory model transfers directly to a
head-worn camera.

The remaining immediate blocker is not the orbit equation: one configured
family/state pair still has zero actor-valid actions in each profile. That
belongs to bounded family-aware refill and admission work, not this
proposal-family PR.

## Related owners and issues

- Config owners: [`build_rollouts_v1_realistic.toml`](../../../../.configs/build_rollouts_v1_realistic.toml), [`build_rollouts_v1_cuda_campaign_writer.toml`](../../../../.configs/build_rollouts_v1_cuda_campaign_writer.toml)
- Bounded target-orbit MVP: [#180](https://github.com/JanDuchscherer104/ARIA-NBV/issues/180)
- Broad candidate-family issue: [#69](https://github.com/JanDuchscherer104/ARIA-NBV/issues/69)
- Family-collapse evidence: [#54](https://github.com/JanDuchscherer104/ARIA-NBV/issues/54)
- Empirical Aria motion prior: [#70](https://github.com/JanDuchscherer104/ARIA-NBV/issues/70)
- Family-aware reservoir/refill: [#71](https://github.com/JanDuchscherer104/ARIA-NBV/issues/71)
- Equal-compute benchmark: [#73](https://github.com/JanDuchscherer104/ARIA-NBV/issues/73)
- Scale-up admission gate: [#120](https://github.com/JanDuchscherer104/ARIA-NBV/issues/120)

Machine-readable provenance and exact scalar results are in
[`manifest.json`](manifest.json).
