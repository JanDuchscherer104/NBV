# ARIA-NBV Thesis Notation And Geometric Descriptor Review

## Verdict

The current thesis narrative has the right representation story: actor-visible target hypotheses, sparse/queryable scene memory, candidate-row equivariance, local-frame geometry, and directional visibility memory. The shared notation is not yet clean enough for a thesis. It overloads glyphs across data records, learned tokens, transforms, ray queries, and pooled descriptors, and the current candidate-pose equation mixes gauge-dependent pose, target relation, support, and sampler provenance in one vector.

The notation repair should be done as a small coordinated patch across shared symbols, shared equations, `docs/notation.yml`, generated notation, and `docs/typst/thesis/sections/04-method/04-02-descriptor-and-encoding-plan.typ`. The foundations section can mostly stay as conceptual background.

## Highest-Priority Conflicts

1. `phi_"target"` is used as a target-descriptor constructor while `#symb.entity.target_desc` is the target descriptor. This conflicts with common ML usage where `phi` is often an encoder/map. Prefer a descriptor vector such as `bold(z)_e^"tgt"` or, if the thesis wants entity representations to use phi, `bold(phi)_e`. Use `psi_"tgt"` or `op("Enc")_"tgt"` for the constructor.
2. `bold(T)_e` is used for the selected-target token, while `bold(T)` is also the SE(3) transform symbol. Rename the learned target token to `bold(h)_e^"tgt"` or `bold(tau)_e^"tgt"`.
3. `bold(z)_e` denotes both the actor-visible target descriptor and the pooled target-support descriptor. Rename query pools to `bold(g)_e^"tgt"`, `bold(g)_(t,i)^"fr"`, and `bold(g)_(t,e,i)^"cap"`, or another consistently non-target-descriptor glyph.
4. `bold(R)_(t,i)^"ray"` conflicts with rotation matrices. Use `bold(g)_(t,i)^"ray"` or `bold(h)_(t,i)^"ray"` for ray-query features, and reserve `cal(R)` or `cal(R)_(t,i)^"sel"` for sets of selected rays.
5. `alpha` appears as a projection-valid mask in logged feature sampling and as a candidate-target angle/alignment term in pose features. Keep projection validity as `m_(j,tau)^"proj"` and use `cos theta_(t,e,i)^"opt"` or `beta_(t,e,i)^"bear"` for candidate-target orientation.
6. `hat(p)_e` in the target descriptor is ambiguous with point/position symbols. Use `hat(pi)_e` or `hat(s)_e` for class/detector confidence, and use `bold(c)_e` or `bold(mu)_e` for the target center.
7. Broad scene/feature symbols currently live under `symb.vin`; keep VIN for EVL/VIN heads and move representation symbols into `scene`, `spatial`, `features`, and `model`/`rl` namespaces.

## Candidate Descriptor Critique

The current equation

```text
x_pose(q_ti) = concat(t_ti, R_ti^6D, ||t_ti - t_e||^2, alpha_ti^e, l_ti^OBB-overlap, c_ti^sampler)
```

is not a pure pose descriptor. It mixes an absolute candidate pose, a target relation, overlap/support, and sampler provenance. It is also gauge-sensitive because raw translation and rotation can expose arbitrary root/world coordinate conventions. For the model path, use relative and local descriptors by default:

```text
h_ti^pose = Enc_pose(xi_(r_t -> q_ti), R6D(R_(r_t -> q_ti)), up/frustum scalars)
h_tei^rel = Enc_rel(R_qti^T (c_e - c_qti), ||c_e - c_qti||, bearing, elevation, optical-axis alignment)
h_ti^prov = Emb(source/sampler family)        # separate, ablated/dropout-controlled
x_ti = concat(h_ti^pose, h_tei^rel, h_ti^support, h_ti^ray, h_ti^hist, h_ti^valid, h_ti^prov)
```

The reference pose `r_t` is the gauge anchor for the current decision state: for logged roots it can be the last historic/root pose, and for counterfactual successors it should be the preceding selected/counterfactual pose. It makes candidate transforms comparable without making the model depend on arbitrary world origin or yaw. Use candidate-local coordinates for target/current/history relations when those relations are consumed by candidate-query attention, following the transferable part of QCNet.

Not every descriptor should be fully SE(3)-invariant. ARIA-NBV is gravity-aligned, frustum-limited, and egocentric; therefore up direction, pitch, height, distance, field-of-view, and incidence are physical signals. The thesis should claim gauge discipline and tested row equivariance, not blanket exact equivariance.

## Namespace Moves

- Keep `eqs.entity.target_descriptor` in `entity`, but rename the constructor and/or target descriptor symbol.
- Move `qh_scene_memory`, `candidate_query_pools`, `candidate_ray_query`, and `ray_memory_update` to `eqs.scene` or `eqs.representation`.
- Move `candidate_pose_features`, `candidate_query_local_frame`, `candidate_query_rpe`, and directional-memory equations to `eqs.spatial` or `eqs.geometry`.
- Keep logged DINO projection/pooling and `point_dino_token` in `eqs.features` or a new `eqs.feature_bank`.
- Move `qh_target_token`, `qh_set_encoder`, `edge_conditioned_attention`, and candidate-state cross attention to `eqs.model` or `eqs.rl`.
- Add matching symbol namespaces: `symbols/scene.typ` for scene memory and support pools; `symbols/spatial.typ` for relative transforms and RPE; `symbols/model.typ` if the learned tokens should not live in `rl`.

## Terminology Standard

- `target descriptor`: actor-visible target record before a learned encoder.
- `target token`: learned embedding of the target descriptor plus scene support.
- `scene memory`: queryable actor-visible state object, not one dense tensor.
- `support`: observed evidence or pooled support statistics.
- `visibility`: geometric line-of-sight/frustum relation; projection validity is not sufficient.
- `candidate row` or `candidate view`: finite action row `q_(t,i)`; use `pose` only for the rigid transform component.
- `provenance`: source/sampler/lineage metadata; keep separate from geometry and ablate it to detect shortcuts.
- `low EVL support`: feature, uncertainty, or reporting stratum, not hard invalidity unless evaluation/state transition is impossible.

## External Literature Alignment

- QCNet supports local coordinate systems and query-relative positional embeddings, not importing trajectory decoders, forecasting losses, or streaming claims into ARIA-NBV.
- Deep Sets and Set Transformer support row-order discipline: candidate contexts may be invariant/pool-based or attention-based, but per-candidate `Q_H` remains row-preserving/equivariant.
- Zhou et al. 2019 supports continuous 6D rotation features, but R6D should encode relative rotations/transforms in this setting, not raw absolute pose by default.
- Geometric Deep Learning supports the distinction between symmetry assumptions and physical task structure. Gravity, up, frustum and egocentric constraints are real signals, so exact SE(3) equivariance is an ablation rather than the default claim.
- Spherical harmonics are an optional directional-memory ablation on `S^2`; the thesis-safe default is a second-moment or low-bin directional summary.

## Patch Order

1. Add `scene` and `spatial` symbol namespaces; keep backward aliases temporarily only if needed for compile.
2. Rename conflicting learned-token/query symbols (`T_e`, ray `R`, query-pool `z_e`, `phi_"target"`, `alpha`).
3. Split `equations/features.typ` into feature-bank, scene-memory, spatial-relation, and model equations, or at minimum expose facades under those namespaces.
4. Update `docs/notation.yml` and regenerate `docs/typst/shared/notation.generated.typ`.
5. Patch `04-02-descriptor-and-encoding-plan.typ` so it introduces descriptor families in this order: target descriptor/token, scene memory, feature bank, candidate self pose, candidate-target relation, support/ray pools, query-local RPE, directional history, row assembly.
6. Lightly adjust `04-03` and `04-04` to use the renamed target descriptor/token and candidate row notation.
7. Validate with Typst compile, notation/glossary validation, row-shuffle terminology search, and `git diff --check`.

## Key Local Evidence

- `docs/typst/shared/equations/entity.typ` defines `phi_"target"` and `target_desc`.
- `docs/typst/shared/equations/features.typ` defines scene memory, DINO point tokens, query pools, ray query, target token, candidate pose features, relation encodings, row assembly, and set/cross-attention equations in one namespace.
- `docs/typst/shared/symbols/vin.typ` currently mixes EVL/VIN heads with generic scene memory, support pools, ray query, directional memory, and candidate pose features.
- `docs/notation.yml` indexes broad scene-memory symbols under `vin.*`, including `vin.scene_memory_t`, `vin.target_pool`, `vin.frustum_pool`, and `vin.ray_query_ti`.
- `docs/typst/thesis/sections/04-method/04-02-descriptor-and-encoding-plan.typ` already has the right descriptor families but needs a clearer notation boundary and descriptor ordering.
- `.omx/specs/autoresearch-thesis-lit-review/report.md` already records the geometric learning gates and the critique that raw R6D+LFF absolute pose is too easy to misuse.
