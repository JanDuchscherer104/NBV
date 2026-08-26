# Pilot rollout candidate-diversity and data-quality audit

**Historical snapshot:** 2026-08-24, PR116 source/review commit
`52e9d262577260074bae25134fbd61c2bfda0533` (the exact commit on which the
measurements below were collected). This report is retained as historical
evidence, not current implementation state.

**Current-truth anchor:** `origin/main` at salvage branch point
`db8c8812aca8fdae4be9565183e5e7ca66de53b6`. For the accepted architecture
digest, see [the tracked candidate-generation architecture debrief](../../../.agents/memory/history/2026/08/2026-08-26_candidate_generation_architecture_digest.md).
The clean replacement/disposition is [PR #153](https://github.com/JanDuchscherer104/ARIA-NBV/pull/153).

**Validation:** independent `prompt-architect-artifact` review required

**Scope:** read-only audit; no generator, configuration, rollout, Git, or GitHub mutation

## Executive verdict

Do **not** begin broad generation or training from the present pilot contract.
The fastest path to trustworthy scale is not a larger random sweep: first make
the oracle/label path valid, then repair candidate support and measure proposal
regret on a frozen benchmark.

The headline “100 pilot rollouts” conflates two different populations:

- The immutable V10 **source population** contains exactly 100 rows from 100
  scenes, one selected snippet per scene.
- The actual paired rollout pilot uses only **five** source snippets, two
  candidate profiles, and four temperature chains per work unit: ten work
  units and at most **40 rollout chains**. The historical corrected-V10 pilot
  contains 40 chains but is bound to the old V8 source. The historical V11
  pilot is the first V10-bound pilot. It finished during this audit with 40
  chains, although the owner status cross-check still rejects its terminal
  evidence.

The historical writer explicitly set
azimuth, elevation, total-angle, and roll jitter to zero, and the orientation
builder returns the deterministic base orientations under that contract. Each
60-row candidate table therefore has only 37 distinct forward axes by
construction: 24 forward-rig rows share one axis, while the other 36 rows use
deterministic target look-at. This was a systematic support restriction, not a
sampling accident. It was also inconsistent with the accepted
seminar-generation precedent:
the final seminar paper and slide deck share a single labeler configuration
with `view_max_azimuth_deg = 60.0`, `view_max_elevation_deg = 30.0`, and
`view_roll_jitter_deg = 0.0`. The historical zero-jitter pilot fact/config is
revision-bound to PR116 commit `52e9d262577260074bae25134fbd61c2bfda0533`.
The retained corrected-V11 plan preserves source/work-unit/lineage identity
only; it delegates to the canonical writer, so rerunning now uses seminar
60°/30°/0° and does not reproduce that historical candidate contract. “View jitter must never be zero” means nonzero azimuth
and elevation; zero roll is intentional for the 5-DoF action space.

Four changes dominate expected return before scale:

1. Close the camera/depth/unprojection and target-RRI validation gates in
   [#79](https://github.com/JanDuchscherer104/ARIA-NBV/issues/79) and
   [#80](https://github.com/JanDuchscherer104/ARIA-NBV/issues/80). Diverse
   candidates cannot rescue corrupted supervision.
2. Replace depth-only candidate seeding with state-keyed, replica-aware streams
   ([#68](https://github.com/JanDuchscherer104/ARIA-NBV/issues/68)). Every
   observed divergent-history group in the completed V10 artifact reused one
   candidate seed at the same depth (44/44 groups).
3. Restore the final seminar view-jitter contract—`60°` azimuth, `30°`
   elevation, `0°` roll—in the base generator and every component override,
   then add explicit same-center/different-gaze and orbit/peek families
   ([#69](https://github.com/JanDuchscherer104/ARIA-NBV/issues/69)). A zero-
   azimuth or zero-elevation bounded-box profile is invalid, not an
   experimental baseline. Zero-cap legacy `uniform_sphere` and
   `forward_powerspherical` modes are a separate uncapped spherical support
   contract: they retain visible residuals on fixed yaw `[-180°, 180°]` and
   pitch `[-90°, 90°]` axes, with no box envelope.
4. Generate a bounded oversampled reservoir, refill starved families, and
   downselect for task-space diversity
   ([#71](https://github.com/JanDuchscherer104/ARIA-NBV/issues/71)). The
   historical pilot discarded 51.9% of candidates and target-bearing support
   survived at only 20.7%.

## Evidence language

This report uses five labels:

- **Implementation fact:** current configuration, source, or tests say it.
- **Artifact observation:** measured directly from persisted rollout data.
- **Live observation:** measured from V11 process, event, status, and promoted
  shard state during this audit.
- **Inference:** the conclusion follows from facts/observations but has not
  been tested as an intervention.
- **Literature lead:** an external primary source motivates an experiment; it
  does not prove the ARIA-NBV outcome.

## What the “100” artifact actually is

The authoritative source population is
`vin_offline_rollout_campaign100_v10_rebuilt/sample_index.jsonl`. It has 100
rows, 100 unique scenes, and one `sample_key`/snippet per row. Its tracked
[source manifest](../../../.configs/rollout_campaign100_source_manifest.json)
records:

| Field | Value |
| --- | --- |
| manifest | `rollout-source-manifest-v2` |
| rows / scenes | `100 / 100` |
| source version | `10` |
| source store | `vin_offline_rollout_campaign100_v10_rebuilt` |
| source-manifest hash | `605453ba11869e40` |
| split-manifest hash | `4780c7cde1b811bf` |

The rollout pilot plan selects five train snippets and binds each to both
profiles:

| Snippet | Profiles |
| --- | --- |
| `ASE_81286_Atek_000112` | `realistic_core_60`, `rich_local_60` |
| `ASE_81483_Atek_000048` | same |
| `ASE_81625_Atek_000000` | same |
| `ASE_82902_Atek_000000` | same |
| `ASE_83577_Atek_000072` | same |

Each work unit runs a horizon-eight, branch-one, beam-one temperature-softmax
recipe at temperatures `0.5, 1.0, 2.0, 4.0`. A successful unit therefore
persists four chains. “One snippet per available scene” describes the 100-row
source population, not the generated pilot coverage.

The V11 plan binds this population with plan hash `303b18f930d60331`, campaign
config hash `4b968f5a48ce519c`, writer config hash `6039d1c474831647`, and full
portable-manifest SHA-256
`d6e771d1582394cde9005be3185dc9cfbb875cab5fc004f184922a25dc996f56`.
Its generation revision records clean commit `52e9d262…`, tree `5d4be416…`,
content-bundle hash `38d2f6e6…`, and revision hash `0474fb6ea2e74792`.

### Lineage table

| Artifact | Source identity | Intended/completed shape | Evidential status |
| --- | --- | --- | --- |
| V10 immutable source | V10, 100 scenes | 100 source rows | Current source population |
| `cuda-rollouts-v1-pilot-corrected-v10` | Historical V8 source | 5 snippets × 2 profiles × 4 chains = 40 chains | Completed historical audit artifact; not current campaign evidence per [#56](https://github.com/JanDuchscherer104/ARIA-NBV/issues/56) |
| `cuda-rollouts-v1-pilot-corrected-v11` | Current V10 source | 5 snippets × 2 profiles × 4 chains = 40 chains | Completed current paired pilot; owner status cross-check fails |

The current operator inventory explicitly calls V10 rollout shards historical
and the historical V11 pilot the first V10-bound destination. This provenance
correction is consequential: both pilot names are historical evidence, not
current campaign state.

## How the samples were generated

The exact operator sequence is recorded in the tracked
[configuration inventory](../../../.configs/README.md):

1. Build the strict V10 offline VIN source with
   [`build_vin_offline_rollout_campaign100_v10.toml`](../../../.configs/build_vin_offline_rollout_campaign100_v10.toml).
2. Reconcile the portable source manifest with `nbv-plan-rollout-source`.
3. Plan and smoke the paired V11 pilot from
   [`build_rollouts_v1_cuda_campaign_pilot_corrected_v11.toml`](../../../.configs/build_rollouts_v1_cuda_campaign_pilot_corrected_v11.toml).
4. Run at most ten work units and inspect campaign status.

The active owners are:

| Contract | Exact owner |
| --- | --- |
| source, scoring, rules, persistence | [`build_rollouts_v1_cuda_campaign_writer.toml`](../../../.configs/build_rollouts_v1_cuda_campaign_writer.toml) |
| profile mixtures and recipes | [`build_rollouts_v1_cuda_campaign.toml`](../../../.configs/build_rollouts_v1_cuda_campaign.toml) |
| accepted seminar view-jitter values | [`paper_figures_oracle_labeler.toml`](../../../docs/typst/shared/data/paper_figures_oracle_labeler.toml), imported by [`slides_4.typ`](../../../docs/typst/seminar_slides/slides_4.typ) and [`05-oracle-rri.typ`](../../../docs/typst/seminar_paper/sections/05-oracle-rri.typ) |
| campaign expansion and provenance | [`campaign.py`](../../../aria_nbv/aria_nbv/oracle/pipelines/campaign.py) |
| mixture assembly | [`candidate_mixture.py`](../../../aria_nbv/aria_nbv/pose_generation/candidate_mixture.py) |
| center generation | [`candidate_generation.py`](../../../aria_nbv/aria_nbv/pose_generation/candidate_generation.py) and [`positional_sampling.py`](../../../aria_nbv/aria_nbv/pose_generation/positional_sampling.py) |
| gaze/orientation generation | [`orientations.py`](../../../aria_nbv/aria_nbv/pose_generation/orientations.py) |
| feasibility rules | [`candidate_generation_rules.py`](../../../aria_nbv/aria_nbv/pose_generation/candidate_generation_rules.py) |
| rollout candidate seeding | [`engine.py`](../../../aria_nbv/aria_nbv/rollouts/replay/engine.py) |
| store schema/linkage validation | [`zarr_store.py::validate_rollout_zarr_store`](../../../aria_nbv/aria_nbv/rollouts/zarr_store.py) |

The closest executable contract tests are
[`test_campaign.py`](../../../aria_nbv/tests/oracle/test_campaign.py),
[`test_orientations.py`](../../../aria_nbv/tests/pose_generation/test_orientations.py),
[`test_candidate_mixture.py`](../../../aria_nbv/tests/pose_generation/test_candidate_mixture.py),
and
[`test_diverse_rollout_profile.py`](../../../aria_nbv/tests/rollouts/test_diverse_rollout_profile.py).

### Effective candidate profiles

| Profile | 60-row mixture |
| --- | --- |
| `realistic_core_60` | 24 forward-local, 24 target-bearing-local, 12 lateral-target-bypass |
| `rich_local_60` | 18 target-bearing-local, 18 forward-local, 12 lateral-target-bypass, 6 local-refinement, 6 revisit/backtrack |

Shared writer parameters include radius `0.25–1.1 m`, elevation
`-12°–18°`, azimuth span `100°`, PowerSpherical concentration `8`, maximum
step `1.0 m`, maximum height delta `0.25 m`, backward step `0.25 m`, and yaw
delta `70°`. Collision, free-space, clearance, and motion rules are active.
These are independent bounded rules, not a learned or empirical joint
head-motion distribution.

## Quantitative pilot audit

### Completed V10 historical artifact

The immutable historical pilot contains 10 shards, 40 chains, 298 rollout
steps, and 17,880 candidate rows.

| Measure | Result |
| --- | --- |
| valid candidates | 8,603 / 17,880 = **48.12%** |
| invalid reasons | 7,679 clearance-too-small; 1,598 path-segment collision |
| valid candidates per step | median 26; range 1–54 |
| starved steps | 41/298 below 15 valid; 26/298 below 10; 0 empty |
| selected translation | median 0.443 m; p95 0.876 m; max 0.996 m |
| selected yaw | median 0°; p75 25.36°; p95 62.64°; max 68.48° |
| selected height delta | median 0.029 m; p95 0.229 m; max 0.248 m |
| actor-valid candidate-center nearest neighbor within each rollout step | median 0.0442 m; p05 0.00761 m; min 0.000496 m |
| exact actor-valid center duplicates at `1e-6` within a step | 0 |
| final cumulative target-root gain | median 0.126; p95 0.699; max 0.860 |

The nearest-neighbor statistic pools one distance per actor-valid candidate,
computed against other actor-valid centers in the same rollout step; it does
not mix scene coordinate frames or count invalid rows. Candidate-center
duplicates are not the dominant failure: the problem is
support quality, gaze degeneracy, feasibility attrition, and state-independent
resampling.

#### Family survival and use

| Family | Valid / proposed | Valid rate | Selected |
| --- | ---: | ---: | ---: |
| target-bearing-local | 1,281 / 6,192 | **20.69%** | 28 |
| forward-local | 4,777 / 6,192 | 77.15% | 116 |
| lateral-target-bypass | 1,173 / 3,576 | **32.80%** | 85 |
| local-refinement | 477 / 960 | 49.69% | 19 |
| revisit/backtrack | 895 / 960 | 93.23% | 50 |

The validity collapse is family-dependent. Aggregate `valid >= 15` can pass
while the target-aware portion nearly disappears, exactly the preflight defect
tracked by [#54](https://github.com/JanDuchscherer104/ARIA-NBV/issues/54).
That issue says to preserve a root threshold of 10, while current campaign and
writer configs specify 15. This is unresolved contract drift; the implementation
must choose and test one canonical threshold rather than silently adopting
either number.

Target-root gain is also heavy-tailed. Selected per-step gain ranges slightly
negative to strongly positive (minimum approximately `-0.0067`, median
`0.0051`, p95 `0.182`). Persisted target projected-area, semidense-support, and
EVL-support audit fields are all zero, but [#55](https://github.com/JanDuchscherer104/ARIA-NBV/issues/55)
defines those zeros as unavailable sentinels rather than measurements. The
pilot therefore cannot currently be stratified truthfully by initial target
visibility/support.

### Historical completed V11 pilot using the V10 source

V11 finished with 9 succeeded units, 1 validated skip, 10 promoted shard
directories, 40 chains, 291 steps, and 17,460 candidates over all five planned
scenes. Every promoted shard independently passes `validate_rollout_zarr_store`
with zero validation errors. The complete population has 8,415 actor-valid
candidates (**48.20%**), with 7,386 clearance failures and 1,659 path-collision
failures. Family survival remains weak: 21.56% target-bearing, 76.68% forward,
32.47% lateral, 49.58% local-refinement, and 92.40% revisit/backtrack. Thirty-
nine of 291 steps have fewer than 15 valid candidates; 23 have fewer than 10;
none is empty. Median final cumulative target-root gain is 0.123 (p95 0.701).

Despite the completed raw status and individually valid shards, the public
`status` command still fails with `invalid campaign status`, caused by
`terminal success/skip lacks validated shard evidence`. This is a real
pre-scale operational blocker, directly related to
[#53](https://github.com/JanDuchscherer104/ARIA-NBV/issues/53): no broad launch
should rely on ad hoc parsing of `progress.jsonl` when the owner status
validator rejects its own terminal evidence.

### Confirmed diversity and realism defects

1. **Zero view jitter — historical implementation fact and contract
   violation.** The historical V11 pilot writer set all four view caps to
   `0.0`, including component overrides.
   `OrientationBuilder.build()` returns base poses when no cap/strategy is
   active. Both profiles consequently produce 37 distinct forward axes from 60
   candidate rows per table. The required repair is already specified by the
   final seminar owner: `60°` azimuth, `30°` elevation, `0°` roll. Production
   Production bounded-box preflight must reject an effective azimuth or
   elevation cap of zero. This does not apply to the explicitly uncapped
   legacy spherical modes described above.
2. **Candidate streams ignore selected history — implementation fact plus
   artifact observation.** The replay engine derives candidate seeds from the
   recipe seed, step, and frontier index. Among 44 V10 rollout-depth groups
   whose selected histories had already diverged, 44 reused a single candidate
   seed. The same holds in all 46 such completed-V11 groups inspected. Sharing a
   table is appropriate for matched policies at the *same physical state*;
   sharing after state/history divergence is not.
3. **Target-aware family attrition — artifact observation.** Target-bearing
   and lateral families lose roughly 79% and 67% of rows, respectively, in V10.
   The fixed 60-row table has no bounded refill or family-survival contract.
4. **Feasibility is a coarse proxy — implementation fact.** Free-space is an
   AABB support check. The path rule samples a straight centerline, without
   head/body volume. Motion realism is a set of independent marginal limits.
   None establishes that a human wearing Aria can occupy and traverse the pose.
5. **Pilot population is narrow — artifact observation.** The paired pilot has
   five scenes and only three physical target classes: tables, cabinet, and
   chair. It cannot establish class-, geometry-, room-, or visibility-level
   robustness for the 100-scene population.
6. **Proposal probabilities are not truthful — implementation fact.** The
   recorded sampler probability behaves as `1/N`, not the actual mixture draw
   probability, obstructing importance-aware training and diagnosis; tracked
   by [#71](https://github.com/JanDuchscherer104/ARIA-NBV/issues/71).
7. **Oracle supervision is not yet a trusted invariant — active gate.** Camera,
   depth, rasterization/unprojection, crop/fusion, and density/tessellation
   robustness remain P0 issues [#79](https://github.com/JanDuchscherer104/ARIA-NBV/issues/79)
   and [#80](https://github.com/JanDuchscherer104/ARIA-NBV/issues/80).

## Related GitHub issue map

All issues below were open at the 2026-08-24 snapshot.

### Direct candidate-support work

The current replacement context also includes [#117](https://github.com/JanDuchscherer104/ARIA-NBV/issues/117) (proposal identity and unique-state oracle reuse), [#118](https://github.com/JanDuchscherer104/ARIA-NBV/issues/118) (orientation-span semantics; closed after follow-up), [#119](https://github.com/JanDuchscherer104/ARIA-NBV/issues/119) (bounded scoring and renderer-parity throughput), and [#120](https://github.com/JanDuchscherer104/ARIA-NBV/issues/120) (phased equal-compute pre-scale gate). The repaired [PR #122](https://github.com/JanDuchscherer104/ARIA-NBV/pull/122), [PR #126](https://github.com/JanDuchscherer104/ARIA-NBV/pull/126), and [PR #127](https://github.com/JanDuchscherer104/ARIA-NBV/pull/127) provide the current merged contract context. They supersede any assumption that the historical pilot contract is the immediate scale-up target.

| Issue | Why it matters here | Priority |
| --- | --- | --- |
| [#67 candidate-support epic](https://github.com/JanDuchscherer104/ARIA-NBV/issues/67) | Umbrella contract for support quality and learned proposals | Epic |
| [#68 state-keyed low-discrepancy streams](https://github.com/JanDuchscherer104/ARIA-NBV/issues/68) | Fixes depth-only seed reuse; adds roots/replicas/substreams | P0 support diversity |
| [#69 decouple centers and gaze](https://github.com/JanDuchscherer104/ARIA-NBV/issues/69) | Direct fix for deterministic gaze and missing orbit/peek/turn pairs | P0 support realism |
| [#70 history/budget schedules and empirical motion](https://github.com/JanDuchscherer104/ARIA-NBV/issues/70) | Replaces independent static bounds with state- and budget-aware priors | P1 |
| [#71 bounded reservoir/refill/diversity/provenance](https://github.com/JanDuchscherer104/ARIA-NBV/issues/71) | Repairs family starvation and enables truthful sampling evidence | P0 |
| [#72 endpoint and swept-volume feasibility](https://github.com/JanDuchscherer104/ARIA-NBV/issues/72) | Repairs AABB/point/centerline realism proxies | P1 |
| [#73 frozen candidate-support benchmark](https://github.com/JanDuchscherer104/ARIA-NBV/issues/73) | Supplies proposal-regret and family-survival promotion evidence | P0 gate |
| [#54 fail preflight on target-family collapse](https://github.com/JanDuchscherer104/ARIA-NBV/issues/54) | Aggregate support currently hides target-aware collapse | P0 gate |

### Data-quality and evaluation prerequisites

| Issue | Relationship to scale decision |
| --- | --- |
| [#53 validated artifacts and truthful status](https://github.com/JanDuchscherer104/ARIA-NBV/issues/53) | Direct owner for the terminal-evidence/status failure observed in completed V11 |
| [#55 preserve unavailable audit diagnostics](https://github.com/JanDuchscherer104/ARIA-NBV/issues/55) | Required for honest visibility/support stratification |
| [#56 reject legacy stores](https://github.com/JanDuchscherer104/ARIA-NBV/issues/56) | Explains why completed V8-bound V10 shards cannot prove readiness for a current campaign |
| [#57 reuse audit projections](https://github.com/JanDuchscherer104/ARIA-NBV/issues/57) | Makes repeated large-campaign inspection bounded; not a generator-quality fix |
| [#79 validate camera/depth geometry](https://github.com/JanDuchscherer104/ARIA-NBV/issues/79) | P0 label-validity prerequisite |
| [#80 robust target-RRI labels](https://github.com/JanDuchscherer104/ARIA-NBV/issues/80) | P0 supervision-stability prerequisite |
| [#81 separate evaluation and training acquisition](https://github.com/JanDuchscherer104/ARIA-NBV/issues/81) | Prevents policy-induced/stratified acquisition from contaminating evaluation |
| [#82 freeze target admission/association/uncertainty](https://github.com/JanDuchscherer104/ARIA-NBV/issues/82) | Prevents detector/association noise from being mislabeled as proposal quality |
| [#106 discounting/path penalty](https://github.com/JanDuchscherer104/ARIA-NBV/issues/106) | Useful after support and labels are valid; premature as a P0 generator fix |

### Downstream learning work in the candidate-support epic

These are related but deliberately **not** workarounds for the present pilot:

| Issue | Dependency boundary |
| --- | --- |
| [#74 reusable online NBV environment](https://github.com/JanDuchscherer104/ARIA-NBV/issues/74) | Starts only after target/RRI and finite-support contracts validate |
| [#75 learned masked selector](https://github.com/JanDuchscherer104/ARIA-NBV/issues/75) | Compares selectors on frozen matched candidate tables; cannot repair proposal regret |
| [#76 learned family/residual proposals](https://github.com/JanDuchscherer104/ARIA-NBV/issues/76) | Changes action support and therefore depends on #68–#75 provenance/benchmark gates |
| [#77 surrogate-guided refinement](https://github.com/JanDuchscherer104/ARIA-NBV/issues/77) | P2 research after hard-oracle endpoint validation; not required for the finite-candidate pilot |

## High-ROI intervention sequence

### Gate 0 — establish trustworthy evidence

1. Make `nbv-rollout-campaign status` accept the historical V11 pilot's exact terminal evidence
   under #53. All ten shard stores validate independently; repair and test the
   cross-check rather than relabeling V8-bound V10 output or bypassing status.
2. Close #79 and #80 using fixed camera/depth fixtures and density/tessellation/
   crop/fusion perturbation tests. Until then, treat score/gain comparisons as
   diagnostic, not training-grade labels.
3. Restore explicit unavailable values for #55 and freeze target admission and
   association under #82.

**Launch gate:** no broad generation if the exact-head campaign status is not
terminal-valid, camera/depth fixtures fail, or target-RRI rank/order is unstable
under the accepted perturbation budget.

### Gate 1 — repair proposal support

1. **State-keyed streams (#68).** Key candidate draws by current pose/state,
   selected history, root, replica, and draw round; give mixture components
   separate substreams. Use Sobol/stratified streams where the parameterization
   supports them. Preserve shared tables only for exact matched-state policy
   comparisons.
2. **Mandatory seminar view jitter.** Set the resolved base and component
   configuration to `view_max_azimuth_deg=60.0`,
   `view_max_elevation_deg=30.0`, and `view_roll_jitter_deg=0.0`, matching the
   final seminar model. Add a fail-closed preflight/test that rejects zero
   effective azimuth or elevation for bounded-box profiles. Empirical AEA/ASE residuals may later
   challenge the seminar values in a separately versioned experiment, but
   zero-jitter generation is not an admissible control.
3. **Center/gaze factorization (#69).** Add paired candidates at the same center:
   forward-rig, target-look, and small fitted residual. Add orbit, stand-off,
   lateral-peek, and turn-in-place families without giving any actor proposal
   oracle-only target geometry beyond its declared protocol.
4. **Bounded reservoir/refill (#71).** Draw a 256–512 reference reservoir,
   apply hard rules, refill starved families within a fixed budget, then select
   60 rows by family quotas plus a normalized SE(3)/task-space farthest-first or
   Poisson-disk subset. Retain a bounded quota of near-boundary invalid rows in
   a separate masked diagnostic/training surface; never label invalid rows as
   low-RRI valid actions.
5. **Family-aware preflight (#54).** Require minimum final/raw and valid support
   by target-aware family, plus no unexplained zero-action growth. Resolve the
   10-vs-15 root-threshold drift explicitly.

### Gate 2 — improve physical and behavioral realism

1. Fit the joint `(translation, yaw, height, backward motion)` distribution
   from AEA/ASE trajectories and condition it on history and remaining budget
   (#70). Retain hard safety caps as outer guards.
2. Deepen the current mesh/rule seam with endpoint occupancy, head-height, and
   swept capsule/volume tests (#72). A navmesh may be a useful feasibility
   oracle or diagnostic, but adopting Habitat-Sim is not justified until a
   bounded comparison proves value over the existing mesh owner.
3. Apply appearance/sensor randomization separately from feasible motion. Pose
   randomization should be justified by the empirical motion/support benchmark,
   not by generic domain-randomization precedent.

## Frozen benchmark and experiment matrix

Freeze `candidate-support-v1` only after Gates 0–1 make its diagnostics
truthful. Its population and randomness are fully specified:

- **Population:** the current V10 train source and one admitted target per
  scene under the frozen #82 target contract. Select exactly 12 scenes by
  sorting eligible `(class_name, scene_id, snippet_id)` rows by
  `sha256("candidate-support-v1" || source_identity_hash)`, round-robin across
  classes with a maximum of three scenes per class, then fill any remainder in
  hash order. Persist that 12-row manifest; never reselect it per arm.
- **States:** exactly two deterministic roots per target (`root_replica=0,1`)
  and two candidate replicas per root (`candidate_replica=0,1`): 48 matched
  root states per arm. A missing second valid root fails the benchmark build; it
  does not silently reduce the denominator.
- **Tables:** exactly 60 final actor candidates per state. A separate evaluator
  reservoir contains exactly 384 candidates from all enabled proposal families
  under the same state and hard rules. It is never exposed to the actor.
- **Randomness:** every draw is keyed by campaign revision, state pose/history,
  target identity, root replica, candidate replica, family, and draw round.
  Exact matched states share keys across arms; divergent states must not.
- **View jitter:** freeze the final seminar values for every arm:
  `view_max_azimuth_deg=60.0`, `view_max_elevation_deg=30.0`, and
  `view_roll_jitter_deg=0.0`. Resolve and persist the effective component
  values; any zero azimuth/elevation override fails bounded-box benchmark
  construction. Legacy zero-cap spherical modes use uncapped fixed yaw/pitch
  axes and remain annotated as uncapped spherical support.
  Roll remains zero because the action space is 5-DoF.
- **Refill budget:** production arms may draw at most 240 raw rows (4× the final
  table), in at most two refill rounds. The 384-row evaluator reservoir is an
  offline benchmark surface, not the production draw budget.

### Root-table screen

Run all five arms on the 48 matched states before any rollout:

| Arm | Exact intervention | Isolated question |
| --- | --- | --- |
| A | current `realistic_core_60` mixture with mandatory seminar jitter `60°/30°/0°`, current depth-keyed RNG | Compliant jitter baseline |
| B | A + state/history/root/replica keyed component substreams | Does state-faithful randomness improve support independently of jitter? |
| C | B with an exact 60-row mix: 12 forward-local; 12 target-bearing-local; 6 shared centers each represented by one forward and one target-look pose (12 rows); 12 orbit/stand-off; 6 lateral-peek; 6 turn-in-place | Does center/gaze factorization improve framing and directional coverage? |
| D | C + raw budget 240, at most two family-aware refills, then task-normalized farthest-first downselection to 60 | Does bounded refill/diversity repair family survival and proposal regret? |
| E | D + joint AEA/ASE motion-quantile schedule and swept head-volume feasibility | Do improvements survive the stricter realism contract? |

The task-pose distance for D is fixed before execution: current-root-relative
XY displacement divided by `1.0 m`, height by `0.25 m`, gaze geodesic angle by
`30°`, target-bearing angle by `30°`, and log target range by `log(1.1/0.25)`;
use Euclidean distance over those five normalized terms. This is a benchmark
metric, not a scientific claim that the weights are optimal.

Record per scene/root/candidate-replica/arm:

- proposed, valid, final, and selected counts by family;
- invalid reason and signed boundary margin;
- number of forward-axis clusters at a `0.5°` angular tolerance, angular
  spread, and within-state actor-valid SE(3) nearest-neighbor distribution;
- target angular error, projected area/framing, range, occlusion, and support,
  with unavailable values represented explicitly;
- `proposal_regret = best_valid_target_root_gain(384 reference) -
  best_valid_target_root_gain(60 actor)`;
- candidate-seed uniqueness for distinct state histories;
- candidate-generation/rule wall time, full-stage wall time, peak VRAM,
  persisted bytes, raw draw count, and refill rounds.

Use paired differences on the 48 state instances. Report the median and p90;
form 95% confidence intervals with a deterministic 10,000-replicate block
bootstrap over the 12 scenes (seed `20260824`), keeping the four root/replica
rows of each scene together.

### Root-table promotion gates

An arm can challenge A only if all gates pass:

1. **Validity:** 48/48 states retain at least 15 actor-valid rows; no family
   configured with at least six rows has zero valid survivors in any state.
2. **Target support:** every state has at least 12 valid target-bearing/orbit/
   peek rows in aggregate and at least two target-aware families survive.
3. **Gaze diversity:** every state has at least 50 forward-axis clusters at
   `0.5°`; zero effective azimuth or elevation is a construction failure before
   this metric is evaluated.
4. **Regret:** median proposal regret improves by at least 20% and p90 regret
   by at least 10% versus A; the 95% block-bootstrap interval for the paired
   scene-median regret difference lies entirely below zero.
5. **Physical feasibility:** zero endpoint/swept-volume violations among final
   actor-valid rows, and no increase in failed/missing roots.
6. **No oracle leakage:** static dependency/field-access tests prove the actor
   proposal path consumes only the declared actor-visible target protocol;
   the 384-row oracle reservoir remains evaluator-only.
7. **Bounded cost:** candidate generation plus hard rules is at most `2.0×`
   A wall time; peak VRAM at most `1.10×` A; final production artifact bytes at
   most `1.25×` A. Reference-reservoir audit bytes are reported separately.

If no arm passes, keep A only as a diagnostic baseline and revise one failed
contract at a time; do not choose the least-bad arm.

### Rollout confirmation

Promote the best gate-passing arm by lowest median regret, breaking ties by
p90 regret and then full-stage wall time. Run only A and that winner through
the four frozen temperatures on the same 12 scenes × 2 roots × 2 candidate
replicas: 48 work units and 192 chains per treatment. Require:

- no terminal-status, validation, empty-action, or Q_H admission failures;
- at least 10% improvement in paired median final cumulative target-root gain,
  with its 95% scene-block-bootstrap interval entirely above zero;
- no regression greater than 5% in p10 final cumulative gain;
- selected translation/yaw/height p01–p99 within the frozen empirical/hard
  motion bounds; and
- full rollout wall time at most `1.20×`, peak VRAM at most `1.10×`, and stored
  bytes per chain at most `1.25×` A.

These thresholds are promotion decisions, not retrospective tuning targets;
changing one requires a new benchmark version.

## External evidence and its limits

| Primary source | Grounded use | Limitation |
| --- | --- | --- |
| [Project Aria Everyday Activities dataset](https://facebookresearch.github.io/projectaria_tools/docs/open_datasets/aria_everyday_activities_dataset) | 143 recordings, accurate trajectories, semidense points, calibration: fit an empirical egocentric motion/view residual prior | Observed behavior is not an oracle NBV policy and may under-cover useful exploration |
| [ASE data format](https://facebookresearch.github.io/projectaria_tools/docs/open_datasets/aria_synthetic_environments_dataset/ase_data_format) | GT trajectories, RGB fisheye, ray depth, semidense data: validate geometry and fit synthetic-domain motion statistics | Synthetic trajectories and rendering still require cross-domain checks |
| [Habitat-Sim PathFinder](https://aihabitat.org/docs/habitat-sim/classesp_1_1nav_1_1PathFinder.html) | Navigability, obstacle distance, islands, feasible steps, and geodesics are useful stronger-feasibility reference capabilities | Static gravity-aligned cylinder/navmesh is not headset/body realism; new dependency cost is unproven |
| [Bridson Poisson-disk sampling](https://www.cs.ubc.ca/~rbridson/docs/bridson-siggraph07-poissondisk.pdf) | Efficient minimum-separation sampling for a bounded diversity subset | Geometric spread does not imply visibility, feasibility, or reconstruction value |
| [Gonzalez farthest-first traversal](https://doi.org/10.1016/0304-3975%2885%2990224-5) | A simple k-center diversity selector after hard filtering | Requires a justified normalized task-pose metric |
| [Hestia, WACV 2026](https://openaccess.thecvf.com/content/WACV2026/html/Lu_Hestia_Voxel-Face-Aware_Hierarchical_Next-Best-View_Acquisition_for_Efficient_3D_Reconstruction_WACV_2026_paper.html) | Supports hierarchical 5DoF search and factorizing positional feasibility from view orientation | Object/drone reconstruction is not direct evidence for indoor egocentric motion |
| [SCONE](https://arxiv.org/abs/2208.10449) | Occupancy-conditioned visibility/coverage can be a proposal feature or diagnostic | It must not replace the target-RRI scientific owner without separate validation |
| [FisherRF](https://arxiv.org/abs/2311.17874) | Information gain is a useful comparison diagnostic | NeRF uncertainty is not the current target metric |
| [VIN-NBV](https://arxiv.org/abs/2505.06219) | Direct reconstruction-improvement ranking motivates best-of-reservoir/regret tests | Object-centric preprint; transfer to ARIA-NBV is a hypothesis |
| [BCQ](https://proceedings.mlr.press/v97/fujimoto19a.html) and [IQL](https://arxiv.org/abs/2110.06169) | Offline-RL literature supports treating behavior/proposal support mismatch as consequential | These algorithms do not repair poor or mislabeled candidate data |
| [Domain Randomization](https://arxiv.org/abs/1703.06907) | Motivates separating sensor/appearance nuisance variation from geometry | It does not justify arbitrary physically implausible pose jitter |

Issue bodies also identify current comparison leads—[OA-NBV](https://arxiv.org/abs/2603.11072),
[ObjView-Bench](https://arxiv.org/abs/2605.10707), and
[PB-NBV](https://arxiv.org/abs/2501.10663). They are useful benchmark/design
inputs, not substitutes for the frozen local evaluator.

## Reproducibility and evidence gaps

The numerical results in this report are bound to the historical source/review
SHA above. The current `origin/main` tree contains subsequent paired-gaze and
provenance fixes, so historical pilot claims are not current implementation
evidence. The retained configs are lineage records and operator inputs, not a
request to change production candidate behavior in this salvage lane.

- Config/source links above describe the exact local checkout at audited commit
  `52e9d262…`; this salvage branch additionally anchors current review to
  `origin/main` above. No generated source/store directory is present in this
  isolated checkout, so store-level validation is explicitly not claimed here.
- The completed V10 and V11 metrics came from persisted Zarr candidate/step/
  rollout arrays and shard manifests. All ten V11 shards pass the presentation-
  free store validator; the separate campaign terminal cross-check still fails.
- Graphify was attempted first. The local projection was rebuilt at the current
  code revision, but semantic refresh found 92 code, 302 documentation, and 3
  paper changes and could not complete without an external LLM backend. All
  consequential claims were therefore re-grounded in exact owners, tests,
  artifacts, and live GitHub state rather than made from the stale graph.
- The final seminar `60°/30°/0°` jitter values are the mandatory baseline, not
  an inference from the pilot. Any future empirical AEA/ASE challenger still
  requires an exact camera/base-frame convention and a new benchmark version.
- The live V11 campaign was not interrupted. It finished during the audit; raw
  status/events and all shard validators were rechecked after worker exit.

## Pre-scale decision

The pre-scale decision is **NO-GO** until all of the following are true:

1. Historical V11 terminal evidence is accepted by the campaign status owner.
2. #79 and #80 provide exact-head camera/label validation evidence.
3. #55/#82 make target support/admission/association auditable.
4. Every resolved rollout component uses the final seminar view-jitter contract
   (`60°` azimuth, `30°` elevation, `0°` roll); bounded-box preflight rejects
   zero effective azimuth/elevation. Legacy zero-cap spherical modes are
   explicitly uncapped and are not represented by an envelope rectangle.
5. #68/#69/#71/#117/#118 eliminate history-independent tables, deterministic gaze
   collapse, and target-family starvation on the frozen #73 benchmark.
6. The promoted 60-row profile improves proposal regret and coverage per
   scene/root without feasibility, oracle-leakage, or resource regressions.
7. #81/#120 freezes evaluation scenes/population separately from enriched training
   acquisition.

Only after those gates should #70/#72 refinements and #106 reward shaping be
promoted into a larger generation campaign.

The old 12-scene/48-state/fixed-384 benchmark and the 10-vs-15 root threshold
are superseded by the accepted replacement program: all-100 Phase A, 24-scene
Phase B/C, optional 128/256/512/1024 budgets, and threshold
`max(12, ceil(0.25*Nq))`.
