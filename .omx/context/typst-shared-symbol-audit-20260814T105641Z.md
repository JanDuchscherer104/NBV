---
kind: audit-context
status: current
slug: typst-shared-symbol-audit
captured_at: 2026-08-14T10:56:41Z
git_base: origin/main@745f6687064563bee6c5867942e1ed23ddccaf0c
git_head_before_artifact: af20eb36f4423fade81315b571e56d720d788b4b
---

# Context: shared Typst symbol documentation and relevance audit

## Task statement

Ensure that every symbol defined under `docs/typst/shared/symbols/*.typ` has an
immediately adjacent explanation, gather enough owner and consumer context to
describe it accurately, and flag entries that appear unused, redundant, or
inconsistent without changing notation semantics.

## Ownership and method

- `docs/typst/shared/symbols/*.typ` owns the executable Typst symbol facades.
- `docs/notation.yml` owns stable portable symbol keys, TeX forms, descriptions,
  and generated-notation metadata.
- Active thesis sections and shared equation modules are the authoritative
  authored consumers inspected for direct `symb.<module>.<key>` references.
- Generated notation mirrors and the defining symbol modules were excluded from
  direct-use counts, because they establish registry presence rather than an
  authored mathematical use.
- All `docs/notation.yml` Typst mappings resolve to existing shared keys, and
  `docs/typst/shared/symbols.typ` imports and exports every domain module.
- Graphify was not used: `graphify-out/graph.json` is absent and
  `python3 scripts/check_graphify_freshness.py --quiet` exits nonzero. All
  findings therefore come from exact sources and repository-wide searches.

## Implemented result

Every module binding and every tuple entry under
`docs/typst/shared/symbols/*.typ` now has a one-line semantic comment immediately
above it. Existing keys, expressions, module boundaries, and compatibility
aliases were preserved. A comment-stripped comparison against `origin/main`
contains no changes.

## Zero-direct-use review candidates

The audit found 79 keys without a direct authored Typst call site. This is a
review signal, not proof of irrelevance: some entries are portable-notation
registry members, shape vocabulary, compatibility aliases, or notation reserved
for planned thesis equations.

- `entity` (4): `B_pred`, `B_gt`, `rri_total`, `rri_e`.
- `obs` (15): `img_gray`, `meta`, `points_semi_t`, `points_next`,
  `points_cand_ti`, `ray_memory_t`, `ray_memory_next`, `selected_rays_ti`,
  `points_tensor_t`, `points_tensor_cand_ti`, `grid`, `lookat`, `face_vis`,
  `face_vis_step`, `voxel_center`.
- `oracle` (5): `points_t`, `points_tensor`, `candidate_tensor`, `dir`,
  `offset`.
- `rl` (14): `transition`, `s_obs`, `s_cf0_next`, `state_emb`,
  `reward_target`, `return_h`, `qh_target`, `e`, `acquisition_cost`,
  `candidate_set`, `candidate_mask`, `invalid_reasons`, `candidate_features`,
  `td_target`.
- `shape` (12): `Himg`, `Wimg`, `Gproj`, `Fpe`, `Fq`, `Ftau`, `Fproj`,
  `Fcnn`, `Ftok`, `Ffr`, `Fpt`, `Faux`.
- `spatial` (3): `ref_pose`, `pose_6d`, `dir_unit`.
- `vin` (26): `token`, `n_obs_max`, `inv_dist_std_min`,
  `inv_dist_std_p95`, `dist_std`, `cov_frac`, `traj_feat`, `cent_pr_nms`,
  `field_evl_t`, `scene_memory_t`, `evl_local`, `evl_support_frac`,
  `evl_support_token`, `target_pool`, `frustum_pool`,
  `target_frustum_pool`, `ray_query_ti`, `render_query`, `field_q`, `pose_6d`,
  `dir_unit`, `dir_memory`, `dir_moment`, `sh_basis`, `candidate_pose_feat`,
  `candidate_dir_feat`.

No direct-use candidates were found in `ase`, `frame`, `model`, or `scene`.

## Consistency findings

### Inconsistent compatibility rendering

`spatial.dir_memory` renders as `bold(h)^"dir"` and `spatial.dir_moment` as
`bold(M)^"dir"`, while their VIN compatibility counterparts render as
`bold(h)_"dir"` and `bold(M)_"dir"`. Compatibility aliases should either render
identically to their canonical owner or be renamed and documented as distinct
quantities. The VIN aliases have no direct authored uses, so canonicalizing or
removing them should be low-risk after checking generated notation consumers.

### Redundant ownership and aliases

- `entity.target_reward` and `rl.reward_target` both render as `r_t^e`;
  `entity.return_h` and `rl.return_h` both render as `G_t^((H))`. The entity
  forms are directly used, while the RL duplicates are not.
- `rl.candidate_table`, `rl.candidate_set`, and `oracle.candidates_t` all render
  as `cal(Q)_t`. `rl.candidate_set` is the unused compatibility name.
- `oracle.points_t` and `obs.points_t` both render as `cal(P)_t`; the observation
  module is the directly used actor-visible owner.
- `obs.ray_memory_t` / `obs.ray_memory_next` duplicate the corresponding
  `scene` entries. The scene module is the directly used composite-memory owner.
- The VIN block from `scene_memory_t` through `render_query` duplicates the
  canonical `scene` module and has no direct authored use.
- VIN also duplicates several `spatial` entries (`pose_6d`, `dir_unit`,
  `dir_memory`, `dir_moment`, `sh_basis`, and `candidate_pose_feat`). The
  spatial module is the clearer domain owner, subject to resolving the
  subscript/superscript mismatch above.
- `oracle.dist_pm` / `oracle.acc` and `oracle.dist_mp` / `oracle.comp` are exact
  compatibility pairs. Unlike the VIN aliases, the older `acc` and `comp` keys
  still have direct consumers and should not be removed without migration.

### Context-sensitive visual collisions

Namespacing prevents API-level collisions, but the rendered forms can be
ambiguous when domains meet in one equation:

- `H` denotes both RL horizon and image height.
- `D` denotes both aggregate reconstruction error and a generic feature
  dimension.
- `T` denotes both the RL transition operator and trajectory length; bold `T`
  is separately used for transforms.
- Plain `r`, `c`, `v`, and `w` have frame, reward, coverage, validity, and weight
  meanings across modules.

These generic forms are not necessarily wrong, but mixed-domain equations
should prefer qualified subscripts or prose-local definitions.

## Recommended dispositions

1. Fix or remove the unused VIN directional compatibility aliases so their
   rendering cannot silently disagree with `spatial`.
2. Select `entity`, `obs`, `scene`, and `spatial` as the canonical owners for
   their duplicated domain quantities, then migrate consumers before pruning
   aliases.
3. Retain `oracle.acc` and `oracle.comp` until their existing consumers are
   migrated to `dist_pm` and `dist_mp`.
4. Feed the 79 zero-direct-use entries through the existing thesis prune audit;
   do not equate zero direct use with irrelevance.
5. When a zero-use key is intentionally reserved, add its planned owner or
   registry rationale to the prune triage rather than keeping it indefinitely
   without a disposition.

## Verification evidence

- Immediate-comment adjacency audit: passed with zero missing entries.
- Comment-stripped diff against the base: clean.
- `typst compile typst/thesis/main.typ /tmp/aria-symbol-comments-thesis.pdf
  --root .`: passed from `docs/`.
- `make check-agent-memory`: passed.
- `git diff --check`: passed.
