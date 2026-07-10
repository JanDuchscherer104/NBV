# ARIA-NBV Scene Encoding Consolidation Plan

Date: 2026-06-22
Mode: `$plan` direct mode
Owner lane: docs/thesis planning now; later implementation crosses `aria_nbv/` data-handling, rendering, and VIN contracts.

## Requirements Summary

Consolidate the current EFM3D/EVL, Cube R-CNN, semidense geometry, DINO-on-point, and candidate-query representation work into one execution-ready plan. The result should align internal docs, public Quarto thesis pages, Typst thesis sections/equations, and the later Python feature-bank prototype.

The thesis-facing decision is:

- EFM3D/EVL remains the primary actor-visible Aria-native target/support substrate.
- Cube R-CNN is an auxiliary detector, target-proposal, and ROI-descriptor baseline, not scene memory.
- The first serious broad scene-memory upgrade is a derived semidense/fused point bank with optional compressed DINO descriptors sampled only from logged observations.
- EVL voxel extent should be an explicit support/coverage feature and ablation, not the default fix for missing broad scene context.
- Counterfactual rollout state may accumulate selected geometry, but must not assume fresh RGB, DINO, EVL, or detector outputs at unvisited candidate poses.

## Evidence Base

Primary local evidence:

- `docs/contents/literature/efm3d.qmd:37-49` already ranks backbone requirements, including actor-visible targets, permutation/mask contracts, broad scene support beyond EVL extent, logged visual semantics, uncertainty, and provenance.
- `docs/contents/literature/efm3d.qmd:82-92` states that EFM3D internals are salvageable as local evidence while broad memory should come from semidense/fused points and logged DINO-on-point.
- `docs/contents/literature/efm3d.qmd:94-121` frames Cube R-CNN as detector/ROI baseline and explicitly rejects treating it as a full scene encoder.
- `docs/contents/theory/efm3d_scene_embeddings.qmd:60-90` defines the planned point token shape with world point, compressed DINO descriptor, uncertainty, observation count, and history metadata.
- `docs/contents/theory/efm3d_scene_embeddings.qmd:91-138` already defines target, candidate-frustum, and target-candidate intersection pooling.
- `docs/contents/thesis/roadmap.qmd:135-190` currently defines `s_t^obs`, `s_t^oracle`, planner state, hard masks, and root-normalized target-gain return.
- `docs/contents/thesis/questions.qmd:136-192` defines accumulated counterfactual point state, target-cropped oracle error, endpoint gain, root-normalized rewards, and invalidity semantics.
- `docs/typst/thesis/sections/03-method.typ:15-122` already contains the backbone ladder and the core historic/counterfactual modality asymmetry.
- `docs/typst/thesis/sections/03-method.typ:251-261` states that selected candidate geometry is added autoregressively while root EVL remains fixed unless a later ablation recomputes it.
- `docs/typst/shared/equations/features.typ:47-82` owns shared `Q_H` scene-memory and candidate-query-pool equations used by the thesis method section.

Primary code evidence:

- `aria_nbv/aria_nbv/vin/types.py:28-129` exposes `EvlBackboneOutput` with voxel pose/extent, EVL head/neck tensors, `pts_world`, `feat2d_upsampled`, and `token2d`.
- `aria_nbv/aria_nbv/vin/backbone_evl.py:221-313` extracts `feat2d_upsampled`, `token2d`, voxel fields, EVL heads, predicted OBBs, voxel pose, and voxel extent from the EFM3D model output.
- `external/efm3d/efm3d/model/lifter.py:360-375` projects world voxel centers into logged cameras and samples 2D feature maps with `sample_images`.
- `external/efm3d/efm3d/utils/image_sampling.py:39-136` is the upstream sampling primitive that rescales camera intrinsics to the feature-map resolution and returns sampled features plus valid masks.
- `aria_nbv/aria_nbv/data_handling/efm_views.py:352-444` collapses semidense world points across time and can append inverse distance standard deviation and observation count.
- `aria_nbv/aria_nbv/vin/experimental/model_v2.py:816-985` already projects semidense points into candidate cameras and computes candidate-conditioned semidense visibility/depth statistics.
- `aria_nbv/aria_nbv/rendering/unproject.py:1-20` centralizes candidate-depth unprojection equations and frame conventions.
- `aria_nbv/aria_nbv/rendering/candidate_pointclouds.py:67-101` converts candidate depth renders to world point clouds and joins them with collapsed semidense geometry.
- `aria_nbv/aria_nbv/rri_metrics/eval_pointclouds.py:116-165` separates actor-visible semidense geometry from root oracle evaluation point clouds.
- `aria_nbv/aria_nbv/pose_generation/counterfactuals.py:700-835` fuses root eval points with selected-history candidate point clouds for autoregressive rollout evaluation.

Prior generated artifacts:

- `.omx/goals/autoresearch/aria-nbv-efm3d-scene-representations-beyond-limi/report.md` ranks semidense plus compressed DINO-on-point as the best first representation beyond fixed EVL extent.
- `.omx/goals/autoresearch/efm3d-representation-backbone/completion.json` records that `docs/contents/literature/efm3d.qmd` was already patched and verified for ranked requirements, EFM3D internals, Cube R-CNN role, and voxel extent handling.
- Transcript `019eea90-7925-7b62-88f3-46be5740c081` records the DINO-to-semidense strategy at session line 7508: project semidense world points into logged RGB frames, sample `rgb/feat2d_upsampled` with EFM3D `sample_images`, pool valid multi-view samples, and keep Cube R-CNN ROI features as a later target-descriptor ablation.

## Acceptance Criteria

Documentation and thesis:

- `docs/contents/literature/efm3d.qmd` remains consistent with the primary decision and does not duplicate low-level equations already owned by theory/Typst pages.
- `docs/contents/theory/efm3d_scene_embeddings.qmd` includes explicit equations for logged-frame feature projection, projection-valid masks, weighted multi-view DINO pooling, descriptor compression, and leakage boundaries.
- `docs/contents/thesis/roadmap.qmd` and `docs/contents/thesis/questions.qmd` state the same actor/oracle/counterfactual state split and explicitly name semidense plus optional DINO-on-point as a planned representation rung, not implemented evidence.
- `docs/typst/shared/equations/features.typ` owns reusable Typst equations for point-feature projection, DINO pooling, feature-bank state, query pools, and EVL support coverage.
- `docs/typst/thesis/sections/03-method.typ` consumes those shared equations and explains that EVL extent enlargement is an ablation, while broad memory is semidense/fused point support plus logged descriptors.
- All public claims about EFM3D, Cube R-CNN, DINO, and semidense geometry cite existing bibliography entries or add missing entries to `docs/references.bib`.

Python prototype:

- A first feature-bank primitive samples logged `feat2d_upsampled` at semidense world points using EFM3D camera/pose conventions and returns features plus projection-valid masks.
- The primitive is read-only with respect to rollout/offline schemas in the first slice.
- Outputs carry provenance fields: point coordinates, point/support metadata, source frame ids or indices, feature source, compression id, valid-frame count, and actor/oracle source role.
- Tests cover empty points, all-invalid projections, mixed valid frames, fixed-order determinism, permutation-invariant pooling, and leakage rejection of GT/oracle fields.
- Existing EVL/semidense features continue to work when the feature bank is absent.

## Implementation Plan

### 1. Documentation Consolidation

Patch `docs/contents/theory/efm3d_scene_embeddings.qmd`.

Add a section after the current semidense point-token section that defines:

```tex
p_{j,c,\tau} = T_{c_\tau \leftarrow w} p_j
u_{j,\tau}, v_{j,\tau}, \alpha_{j,\tau} =
\pi_{\kappa_\tau}(p_{j,c,\tau})
```

where `alpha` is the projection-valid mask produced by the calibrated camera projection. Then define:

```tex
f_{j,\tau} = Sample(F^{2D}_\tau, u_{j,\tau}, v_{j,\tau})
w_{j,\tau} = alpha_{j,\tau} q_j r_{j,\tau}
\bar f_j = Compress(
  sum_tau w_{j,\tau} f_{j,\tau} / (sum_tau w_{j,\tau} + eps)
)
```

Keep terms actor-visible: `F^{2D}` comes from logged EFM3D/DINO maps, `q_j` from semidense uncertainty/support, and `r_{j,tau}` from optional view/recency weights. State that no GT mesh, GT OBB crop, oracle RRI, all-candidate render, or unvisited candidate RGB/DINO may enter `bar f_j`.

Patch `docs/contents/literature/efm3d.qmd` only if the theory patch introduces new terminology that needs a one-paragraph pointer. Avoid a second literature rewrite because the current page already owns the high-level verdict.

### 2. Thesis Roadmap and Research-Question Alignment

Patch `docs/contents/thesis/roadmap.qmd`.

Update the mathematical model near `s_t^{obs}` and `s_t^{cf0}` to distinguish:

- `P_t^{semi/fused}`: broad actor-visible point state.
- `F_0^{EVL}`: root local EVL evidence, fixed across counterfactual rollout unless recomputed by a named ablation.
- `F_t^{DINO@pt}`: optional logged feature-bank descriptor attached to semidense/fused points.
- `O_t^{pred}`: observed or predicted target hypotheses, including EVL first and Cube R-CNN only as auxiliary target proposals.

Patch `docs/contents/thesis/questions.qmd`.

Add the same representation rung to RQ2/RQ3 without turning it into a hard thesis deliverable before implementation evidence. The target wording should say the first `Q_H` result can start with implemented EVL/VIN plus semidense geometry, while semidense plus DINO-on-point is the best planned representation upgrade and ablation.

### 3. Typst Equations and Method Prose

Patch `docs/typst/shared/equations/features.typ`.

Add shared equations for:

- logged-frame projection of a world point into a camera;
- 2D feature sampling from logged feature maps;
- projection-valid weighted multi-view pooling;
- compressed point descriptor;
- feature-bank state and query pools.

Patch `docs/typst/thesis/sections/03-method.typ`.

Use the shared equations in the "Backbone and Scene-Encoder Requirements" / "Descriptor and Encoding Plan" areas. Keep three distinctions explicit:

- EVL is local evidence and an OBB-capable target anchor.
- semidense/fused plus logged DINO-on-point is broad scene memory.
- counterfactual successors only add selected geometry/support/history unless a future renderable modality generator is validated.

Patch `docs/typst/thesis/sections/03-02-data-generation.typ` only if target descriptor language needs the same provenance or support wording. Avoid duplicating the full feature-bank derivation there.

### 4. Feature-Bank Prototype API

Open `aria_nbv/aria_nbv/vin/AGENTS.md` and `aria_nbv/aria_nbv/data_handling/AGENTS.md` before implementation because the prototype spans VIN descriptors and immutable data sources.

Add a small, read-only module rather than modifying rollout schema first. Candidate location:

- `aria_nbv/aria_nbv/vin/scene_feature_bank.py` if the primitive is consumed only by VIN/Q_H readers.
- `aria_nbv/aria_nbv/data_handling/scene_feature_bank.py` if it becomes an offline-store derived artifact reader/writer.

Recommended first API:

```python
def sample_logged_image_features_at_world_points(
    *,
    points_world: Tensor,
    feat2d: Tensor,
    cameras: CameraTW,
    t_world_camera: PoseTW,
    point_weights: Tensor | None = None,
) -> PointFeatureBank:
    ...
```

The implementation should mirror `external/efm3d/efm3d/model/lifter.py:369`:

```python
points_cam = t_world_camera.inverse() * points_world
features, valid = sample_images(feat2d, points_cam, cameras, ...)
```

Then pool valid features per point with weighted mean and valid-frame count. Use `EfmPointsView.collapse_points(include_inv_dist_std=True, include_obs_count=True)` for point metadata. Keep compression as an explicit strategy object or small pure function so 32, 64, 128, raw, PCA, and random-projection variants are auditable.

Do not write this into the rollout Zarr schema in the first implementation. Store derived cache artifacts only behind an explicit prototype command/config after tests and visualization pass.

### 5. Query Pooling and Q_H Reader Integration

After the primitive is tested, add a reader-side descriptor assembly layer.

Inputs:

- `EvlBackboneOutput` from `aria_nbv/aria_nbv/vin/types.py`.
- collapsed semidense/fused points from `EfmPointsView` / `VinSnippetView`.
- observed/predicted target OBB descriptors from the target-selection contract.
- finite candidates and masks from rollout/VIN reader state.

Outputs:

- `z_e`: target OBB support token.
- `z_i_fr`: candidate-frustum support token.
- `z_ei_cap`: target-candidate intersection token.
- `s_i_EVL`: local EVL read plus coverage/out-of-extent flag.
- provenance and masks: empty support, out-of-EVL, missing descriptor, ambiguous target, actor-visible only.

Start with masked mean/max/count/std pooling. Add point/sparse encoders only after pooled descriptors beat or fail a documented baseline.

### 6. Tests

Add focused tests before broad integration.

Recommended files:

- `aria_nbv/tests/vin/test_scene_feature_bank.py`
- `aria_nbv/tests/vin/test_feature_bank_pooling.py`
- `aria_nbv/tests/vin/test_feature_bank_leakage.py`

Test cases:

- projection parity with a tiny synthetic camera/point setup;
- empty point set returns zero-length descriptors and true empty masks;
- all invalid projections return zero descriptors plus `missing_descriptor` masks;
- mixed valid frames produce the expected weighted mean and valid-frame count;
- point order and frame order are deterministic or explicitly canonicalized;
- target/frustum/intersection pooling is permutation invariant over points;
- provenance rejects or refuses GT mesh, GT OBB crop, oracle RRI, all-candidate rendered depth, and unvisited candidate frame descriptors as actor features.

### 7. Visual and Diagnostics Checks

Add a small Rerun or plotting diagnostic after tests pass:

- EVL voxel extent versus semidense map extent.
- semidense points colored by valid-frame count and descriptor norm.
- target OBB support, candidate frustum support, and target-frustum intersection.
- out-of-EVL fraction as coverage metadata rather than invalidity.

Use existing Rerun inspector surfaces when possible instead of adding a separate viewer.

### 8. Guidance and Durable Capture

Apply `agent-behavior` during execution:

- Every later changed file must map to this plan, root `AGENTS.md`, `docs/AGENTS.md`, or `aria_nbv/AGENTS.md`.
- If a reusable feature-bank workflow is created, capture the repeatable workflow in the smallest correct owner: likely a compact `.agents/skills/*/SKILL.md` only if it becomes a repeatable agent workflow, otherwise package docs and code docstrings are enough.
- If feature-bank implementation changes current thesis truth, update `.agents/memory/state/` or leave a debrief with `canonical_updates_needed`.
- Do not update root `AGENTS.md` for scientific details; source order says durable thesis truth belongs in Quarto/Typst docs and package contracts.

## Risks and Mitigations

Risk: EVL extent enlargement looks simpler than feature banking.
Mitigation: Document it as an ablation only. A larger dense cube increases compute and sparsity and still does not create logged visual descriptors for observed points outside the original support.

Risk: DINO-on-point leaks future or oracle information.
Mitigation: The projection primitive only samples logged frame features. Tests must reject GT/oracle fields and unvisited candidate frame descriptors.

Risk: Projection frame conventions drift from EFM3D.
Mitigation: Reuse `PoseTW`, `CameraTW`, and EFM3D `sample_images`; test against synthetic geometry and the existing candidate-depth unprojection convention docs.

Risk: Feature descriptors become unbounded storage churn.
Mitigation: Keep a prototype artifact first, require compression metadata, and avoid rollout schema changes until an ablation proves value.

Risk: Cube R-CNN is overclaimed.
Mitigation: Keep it as target-proposal and ROI descriptor baseline. Require ATEK/ASE adaptation and OBB quality evidence before it can compete with EVL target evidence.

Risk: Thesis docs present planned work as completed.
Mitigation: Every doc patch must label DINO-on-point, EVL internals/crop reads, and Cube R-CNN ROI features as planned ablations until code, visualizations, and quantitative ablations exist.

## Verification Plan

Docs:

- `make qmd-frontmatter-check`
- `cd docs && quarto render contents/literature/efm3d.qmd`
- `cd docs && quarto render contents/theory/efm3d_scene_embeddings.qmd`
- `cd docs && quarto render contents/thesis/roadmap.qmd`
- `cd docs && quarto render contents/thesis/questions.qmd`
- `cd docs && typst compile typst/thesis/main.typ --root .`
- `make kg-claim-check KG_CLAIM="EFM3D/EVL is the primary actor-visible local target-support substrate for ARIA-NBV, while semidense/fused points with logged DINO descriptors are a planned broad scene-memory ablation and Cube R-CNN is an auxiliary detector/ROI baseline."`

Python:

- `ruff format aria_nbv/aria_nbv/vin/scene_feature_bank.py aria_nbv/tests/vin/test_scene_feature_bank.py`
- `ruff check aria_nbv/aria_nbv/vin/scene_feature_bank.py aria_nbv/tests/vin/test_scene_feature_bank.py`
- `cd aria_nbv && uv run pytest tests/vin/test_scene_feature_bank.py`
- Add reader/pooling tests and run their focused pytest files if steps 5-6 are implemented.

Agent guidance and memory:

- `make check-agent-memory` if `.agents/**`, debriefs, memory state, or skills change.
- Validate any changed repo-local skill with:
  `python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" .agents/skills/<skill-dir>`

## Suggested Execution Order

1. Patch theory docs and Typst shared equations first, because they define the scientific contract.
2. Patch roadmap/questions/method prose to consume the shared equation contract.
3. Run focused docs verification and claim check.
4. Implement the read-only feature-bank primitive with tests.
5. Add pooling/query integration as reader-side derived descriptors.
6. Add visual diagnostics.
7. Only after tests, visuals, and a small ablation pass, decide whether a persisted derived cache schema is warranted.

## Stop Conditions

- Stop after docs if the implementation surface proves missing logged `feat2d_upsampled` in the active offline samples.
- Stop before rollout schema changes unless there is explicit evidence that derived reader-side descriptors are too expensive or non-reproducible.
- Stop before Cube R-CNN training unless existing ATEK/ASE weights or outputs fail the target-proposal/ROI baseline requirement.

## Follow-up Staffing Guidance

Default execution path: `$ultragoal` for durable state plus `$team` if parallelizing docs, equations, Python prototype, and verification.

Recommended lanes:

- `writer`: Quarto/Typst consolidation and citation hygiene.
- `executor`: feature-bank primitive and tests.
- `test-engineer`: projection, pooling, leakage, and determinism tests.
- `verifier`: docs render, claim check, targeted pytest, and memory/debrief checks.
- `critic`: final review for actor/oracle leakage and overclaimed thesis language.

Team launch hint:

```text
$team "Implement .omx/plans/scene-encoding-docs-thesis-feature-bank-20260622T152059Z.md with lanes for docs/equations, feature-bank prototype, tests, and verification."
```

Ultragoal launch hint:

```text
$ultragoal "Execute .omx/plans/scene-encoding-docs-thesis-feature-bank-20260622T152059Z.md; checkpoint docs, code prototype, tests, visual diagnostics, and claim-check evidence."
```

Ralph fallback: use only if a single persistent owner is preferred for sequential docs/code/verification after the plan is approved.
