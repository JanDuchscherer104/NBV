# PRD: Stored-rollout session/cache seam

## Outcome

Deliver three sequential, separately reviewable work items:

1. **Issue A / PR A:** deepen the Streamlit stored-rollout session so one panel-local owner controls per-rerun store identity, reader/validation/manifest snapshot lifecycle, demand-backed named caches, and owner-level invalidation.
2. **Issue B / PR B:** after A lands, reuse named, demand-aligned typed rollout-inspection facets across Streamlit, `nbv-rollouts-info`, and deterministic report export without equalizing their read depths.
3. **Scientific restoration / PR C:** after A and B are verified, restore the scientifically important candidate-support projections and plot forms lost during the partial PR #38 salvage: target-normalized candidate geometry, equal-area directional density, spherical/angular coverage, spatial-shell support, target-view and motion/path support, and collision/clearance support.

A and B are behavior-preserving seam work and must not change rollout science, Zarr persistence, validation, query/export behavior, or visual design. C restores previously implemented read-only scientific projections and plots without changing generation or persistence. Persisted meaning and projections remain owned by `aria_nbv.rollouts`; Streamlit remains an interaction/presentation client (`aria_nbv/aria_nbv/rollouts/AGENTS.md:14-19`, `aria_nbv/aria_nbv/app/AGENTS.md:14-43`).

## Baseline evidence

- Original planning baseline: `a3be5a625a40597f3050c34fc5d89ba26b093be4` on `codex/streamlit-session-cache-plan`; implementation baseline refreshed to `origin/main` `3a6ff491fadb19c20af3d876ae4734e138804ee9` on 2026-08-21.
- Graphify is unusable at this HEAD because the projection revision is not an ancestor and owner digests differ; this plan therefore uses exact current sources only, as recorded in `.omx/context/stored-rollout-session-cache-seam-20260821T101909Z.md`.
- The page currently owns the cached reader/validation/manifest tuple (`aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:177-198`), one string-selected projection dispatcher (`aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:221-325`), replacement-sensitive identity (`aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:328-354`), and topology/failure/report cache owners plus manual invalidation (`aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:377-479`).
- The identity hashes relative paths plus size, mtime, ctime, inode, and the promoted content seal without reading payload bytes solely for identity (`aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:331-354`).
- Current public wrappers recompute identity before each cached call (`aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:194-198`, `aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:365-374`, `aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:396-468`). A captures identity once per open/rerun for reader/core-bound work; path-reopening topology/report operations retain per-invocation identity checks.
- Page rendering resolves inventory and opens the cached store once before conditionally rendering only the open dynamic tab (`aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:482-556`). The explicit refresh button clears all inspector caches and reruns (`aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:559-590`).
- Existing tests prove zero candidate-audit materialization for lightweight projections (`aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py:22-60`), one bounded/reused candidate projection for explicit grouping (`aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py:62-107`), replacement-sensitive dispatch (`aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py:122-175`), tamper-aware validation (`aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py:177-225`), and full cache recomputation after atomic same-path replacement (`aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py:282-366`).
- App-level tests prove the default workspace avoids deep controls (`aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py:565-576`) and unopened scientific evidence performs exactly zero heavy projection calls (`aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py:579-629`).
- Domain ownership is already presentation-free: `read_model.py` owns typed stored rows without display policy (`aria_nbv/aria_nbv/rollouts/read_model.py:1-8`, `aria_nbv/aria_nbv/rollouts/read_model.py:27-140`), while `inspection.py` keeps Streamlit/CLI/tests away from ad hoc Zarr joins and returns renderer-neutral values (`aria_nbv/aria_nbv/rollouts/inspection.py:1-6`).
- The CLI independently opens the reader, obtains manifest/validation/statistics, runs preflight, and optionally builds the report bundle (`aria_nbv/aria_nbv/rollouts/info_cli.py:112-168`). Reporting independently validates each store and reads its manifest before constructing deterministic frames (`aria_nbv/aria_nbv/rollouts/reporting.py:476-515`, `aria_nbv/aria_nbv/rollouts/reporting.py:567-580`). Existing parity tests already compare CLI statistics with the shared inspection function and serialized report facts (`aria_nbv/tests/rollouts/test_reporting.py:63-115`).
- Consumer demand is intentionally asymmetric: default CLI reads only the manifest and emits no `stats` field (`aria_nbv/aria_nbv/rollouts/info_cli.py:112-134`, `aria_nbv/tests/rollouts/test_info_cli.py:23-35`); compact statistics read candidate/step/rollout/dictionary arrays (`aria_nbv/aria_nbv/rollouts/inspection.py:221-268`); Streamlit trust validates and checks promotion but its lightweight header uses manifest plus filesystem metadata rather than `rollout_statistics` (`aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:177-191`, `aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:712-751`, `aria_nbv/aria_nbv/rollouts/inspection.py:271-352`); reporting validates, checks promotion, and computes statistics (`aria_nbv/aria_nbv/rollouts/reporting.py:567-628`).
- `RolloutZarrValidationResult` and its `errors` list are mutable (`aria_nbv/aria_nbv/rollouts/zarr_store.py:395-423`), and the cached manifest is a mutable dictionary (`aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:177-191`). The A handle binds a core snapshot; it is not transitively immutable and does not snapshot path-reopening operations.
- Topology and report construction reopen the selected path rather than consuming the bound reader: `build_dataset_topology()` resolves the path and later reads `manifest.json` (`aria_nbv/aria_nbv/dataset_topology.py:324-377`, `aria_nbv/aria_nbv/dataset_topology.py:649-683`), while reporting constructs a new reader (`aria_nbv/aria_nbv/rollouts/reporting.py:567-580`). Their cache policy must therefore use identity computed at their own invocation, not claim reader/core snapshot consistency.
- `rich_summary.py` owns generic tensor-like summaries and Rich/plain-text tree rendering, not rollout semantics (`aria_nbv/aria_nbv/utils/rich_summary.py:1-7`, `aria_nbv/aria_nbv/utils/rich_summary.py:21-64`, `aria_nbv/aria_nbv/utils/rich_summary.py:183-238`).
- Fresh focused baseline: `cd aria_nbv && uv run pytest tests/app/panels/test_stored_rollouts_projection_laziness.py tests/app/panels/test_counterfactual_rollouts_panel.py -q` -> **69 passed** on 2026-08-21.
- Critic iteration 1 independently recorded **69 passed** for the panel suite and **39 passed** for the CLI/report suite before requesting this planning refinement; this is lifecycle verification, not implementation evidence.
- Historical plot-loss audit identifies a visible target-normalized root-to-candidate plot at `65a7758872`, while PR #38 (`32d44a33d2b15e1f92b8c7c6f9653d555faefc9c`) retained typed target-normalized geometry plus equal-area direction, spherical-cap, angular-support, spatial-shell, target-view, motion/path, and collision-support evidence. Current main retains root-relative metre scatter, one-dimensional yaw support, and collision tables but omits the target-normalized and equal-area scientific projections.
- The exact historical normalized-geometry sources are `candidate_geometry_evidence_rows()` and `_target_normalized_motion_figure()`; the exact direction/support sources are `candidate_direction_evidence()` and `candidate_spatial_support_evidence()`. History is evidence only: C must re-derive the smallest current-owner implementation against current Zarr fields and tests rather than replay PR #38 wholesale.
- Graphify remained `unusable` after worktree bootstrap repair because the projection-owner worktree status was unavailable. This revised plan therefore records the degradation and uses exact current and historical Git objects only.

## Requirements

### Issue A: deepen session, identity, caching, and invalidation

1. Add one focused panel-local session/cache owner, preferably `aria_nbv/aria_nbv/app/panels/_stored_rollout_session.py`, and move only store lifecycle, identity, named cache calls, inventory, topology/failure/report cache ownership, and invalidation out of `_stored_rollouts_page.py`.
2. `open_stored_rollout_session(path)` canonicalizes the path, computes replacement-sensitive identity exactly once, opens the core under that `(canonical_path, identity)` key, and returns a **fixed-identity single-rerun snapshot handle**. It is not a live watcher, is not stored in `st.cache_resource`, and makes no transitive-immutability claim about reader, validation, or manifest values.
3. All decorated functions are module-private and accept cache-stable arguments/values. Preserve the exact current cache policy: reader/core uses `st.cache_resource(show_spinner=False)` with `max_entries` unset; existing resource-valued topology uses `st.cache_resource(max_entries=16)`; inventory, serializable projections, candidate data, failures, and evidence bundles retain their existing bounded `st.cache_data` limits. Retain existing structured topology arguments—`PathConfig`, the VIN-directory tuple, and selected source row—without flattening or redesign solely for caching. Split the consistency contract:
   - **Reader/core-bound operations**—core, named projections, candidate population, and failures—use the handle's captured `(canonical_path, store_identity)` and remain on that bound reader generation until the next open/rerun.
   - **Path-reopening operations**—topology and evidence/report bundle—compute/check `_store_projection_identity(canonical_path)` at their own invocation and use that invocation identity in their cache key. If the path is replaced after handle open, their next invocation must observe the replacement. No snapshot consistency is claimed if the path changes concurrently during one path-reopening call.
4. Preserve `_store_projection_identity` behavior equivalent to the current metadata/content-seal algorithm. Core-bound replacement is observed on the next `open_stored_rollout_session`, explicit refresh, or ordinary rerun. Path-reopening replacement is observed on the next topology/report invocation, even on an older handle (`aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:328-354`).
5. Expose only named operations demanded by current render call sites. Do not mechanically mirror every dispatcher branch as a public method, and do not retain a generic `projection: str` escape hatch. Private helpers may reduce repetition only when parameter, read-depth, and laziness contracts are identical.
6. Replace the page-local `.clear()` list with one owner-level global invalidation API. It clears decorated-function caches, not per-instance entries; include the currently omitted candidate-population cache as well as inventory, core, general projections, topology, failures, and evidence bundle (`aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:211-218`, `aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:471-479`).
   After a global clear, the caller must rerun before using a prior handle; the existing Refresh stores path already clears then calls `st.rerun()` (`aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:587-590`).
7. Treat `inventory_row` as presentation-only selector/stale-diagnostic metadata. It is never an input to store identity, reader/core trust, or any B domain facet. `_cached_inventory` is explicitly exempt from `(canonical_path, store_identity, ...)` because its contract remains cache-root keyed.
8. Preserve dynamic-tab and explicit-toggle laziness. Lightweight workspaces must not materialize candidate audit, candidate population, root geometry, tree, deep Q_H, compact statistics, or other opt-in evidence merely because a session exists (`aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:507-556`, `aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py:604-629`).
9. Use two explicit behavior-lock checkpoints before moving production ownership: first a green characterization run against existing `_stored_rollouts_page.py` owners; then session-contract tests before migration/removal, preferably green through the smallest non-migrating scaffold or intentionally red only with exact expected failures recorded and then made green before page-owner removal. Do not delete or weaken the current same-path replacement, mutation, promotion, lazy-read, or cache recomputation assertions (`aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py:122-225`, `aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py:282-366`).
10. Keep PR A focused: no chart, label, layout, widget, query, Rerun, report schema, CLI, persistence, or scientific-semantic changes.

### Issue B: reuse typed inspection results after A

1. B is blocked on A and starts only from A's merged session contract.
2. Replace the proposed union DTO with **named, demand-aligned typed facets** in `aria_nbv.rollouts.inspection` or one narrow sibling domain module. Initial facets should separate: manifest facts; schema validation; promotion evidence; and compact statistics. Builders may share a reader/manifest input, but no facet eagerly constructs another consumer's work.
3. Define trust composition explicitly:
   - the schema-validation facet preserves the reader's ordered validation errors;
   - the promotion facet is an optional error/evidence value computed only where promotion is already checked;
   - the effective Streamlit trust composition copies schema errors, appends a promotion error last when present, and sets `ok` false when either source fails, preserving the current blocked rendering semantics without mutating/reusing a CLI validation object (`aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:177-191`);
   - reporting evaluates schema validation first, then promotion, and preserves its current distinct `ValueError` messages rather than using Streamlit presentation composition (`aria_nbv/aria_nbv/rollouts/reporting.py:573-580`).
4. Preserve current mode depth exactly:
   - default CLI: manifest facet only; zero validation, promotion, and statistics calls;
   - CLI `--validate`: manifest + validation; zero promotion and statistics calls;
   - CLI `--stats`: manifest + statistics; zero validation and promotion calls;
   - CLI `--preflight`: manifest + validation + statistics; zero promotion calls;
   - Streamlit lightweight trust/header: manifest + validation + promotion/header metadata; zero compact-statistics calls;
   - reporting/export: manifest + validation + promotion + statistics once per store, followed by its existing report-specific projections.
5. Preserve current CLI promotion semantics: ordinary CLI info/validate/stats/preflight must not begin calling `promoted_store_validation_error`; only existing report export paths may encounter reporting's promotion check (`aria_nbv/aria_nbv/rollouts/info_cli.py:112-168`, `aria_nbv/aria_nbv/rollouts/reporting.py:573-580`).
6. Streamlit may cache demand-aligned facets through A's reader/core policy; CLI and reporting consume the domain builders without importing Streamlit. `inventory_row` is excluded from every facet and composition.
7. Preserve deterministic report schemas/bytes and existing CLI JSON/text/exit behavior (`aria_nbv/aria_nbv/rollouts/reporting.py:518-564`, `aria_nbv/aria_nbv/rollouts/info_cli.py:154-168`).
8. Keep `aria_nbv.utils.rich_summary` a generic rendering adapter; do not add rollout DTOs, cache identity, or rollout field semantics there (`aria_nbv/aria_nbv/utils/rich_summary.py:1-7`, `aria_nbv/aria_nbv/utils/rich_summary.py:183-238`).
9. Do not create new speculative CLI commands or export formats. Type only facts already demanded at current call sites.

### Scientific restoration C: recover lost candidate-support plots after A and B

1. C begins only after A and B are committed and their focused suites are green. It may consume A's named session operations and B's typed trust facets, but it must not reopen either contract or add a parallel cache owner.
2. Restore target-normalized candidate geometry as a presentation-free projection in `aria_nbv.rollouts.inspection`. For each finite candidate with a finite root pose, candidate pose, and nonzero root-to-target XY baseline, emit forward and right-handed lateral coordinates normalized by the root-to-target planar distance. Preserve the explicit frame: root `(0, 0)`, target `(1, 0)`, right-handed Z-up. Missing target geometry or a degenerate baseline remains unavailable, never zero-filled.
3. Restore a default-visible bounded 2D target-normalized geometry plot in the existing candidate-generation/feasibility surface. Show root and target anchors, candidate endpoints, selected state, persisted family/policy context, and deterministic row bounding. The plot is descriptive support evidence, not a planning-tree view or causal estimate.
4. Restore equal-area directional density in azimuth by `sin(elevation)`, not raw-elevation rectangular area. Compute complete bins, finite/missing counts, and state-then-scene macro summaries within exact persisted generation cohorts. Render a heatmap or equivalent two-dimensional density plot with explicit sample count, angular convention, and unavailable-state handling.
5. Restore the remaining scientifically useful PR #38 support reducers without copying its old session or UI architecture:
   - spherical-cap discrepancy and nearest-neighbor angular separation;
   - spatial-shell radius/height support;
   - target-view support and explicit missingness;
   - motion/path support, including finite motion and explicitly evaluated collision/clearance evidence;
   - collision/clearance support as a plot-first view rather than the current bare table.
6. Reuse one materialized candidate-audit population per requested store/cohort for all C reducers. Preserve state-then-scene-then-cohort aggregation where the historical reducer did so; never pool incompatible generation cohorts, profiles, family vocabularies, or candidate contracts.
7. Keep scientific aggregates complete for the selected compatible population. Only plotted point clouds may be deterministically bounded; density/support statistics must use all admitted finite rows. Raw rows and CSV remain collapsed directly beneath the plot they explain.
8. Every restored plot must use the existing scientific-explanation owner and provide the question answered, conceptual intuition, visual encoding, denominator/missingness, uncertainty or descriptive-spread limits, and relevant canonical equation/symbol/glossary/source links when applicable. Do not create a second explanation framework.
9. C is read-only inspection. Do not change Zarr schema, generation, candidate families, masks, target admission, Q_H training semantics, CLI/report schemas, Rerun control, or persistence. Do not add dependencies, a generic plotting service, compatibility aliases, or a wholesale PR #38 replay.

## Issue A cache migration matrix

This is a static implementation checklist, not a runtime registry.

| Planned private owner | Cache kind | `max_entries` | Store identity key | Other keys | Laziness / trigger |
|---|---:|---:|---|---|---|
| `_cached_store_core` | `st.cache_resource(show_spinner=False)` | **unset (preserve current default)** | canonical path + handle-captured identity | none; `inventory_row` excluded | Reader/core-bound; opened once when a selected-store session is opened. |
| `_cached_inventory` | `st.cache_data` | 8 | **exempt: no path/identity key** | cache root only | Presentation discovery; global clear includes it; rows never enter identity/domain trust. |
| Demand-backed named projection caches (may share one private implementation) | `st.cache_data` | 128 | canonical path + handle-captured identity | operation-specific cache-stable arguments/values | Reader/core-bound; called only from the current visible section/control. |
| `_cached_candidate_population` | `st.cache_data` | 128 | canonical path + handle-captured identity | sample size | Reader/core-bound; explicit candidate evidence only; added to clear ownership. |
| `_cached_topology` | `st.cache_resource` | 16 | canonical path + **fresh invocation identity** | existing VIN dirs tuple, `PathConfig`, selected source row | Path-reopening; retain structured arguments unchanged, recompute/check identity each invocation, detect replacement on next call. |
| `_cached_failures` | `st.cache_data` | 32 | canonical path + handle-captured identity | three failure thresholds | Reader/core-bound; Failure Triage only. |
| `_cached_evidence_bundle` | `st.cache_data` | 16 | canonical path + **fresh invocation identity** | evidence status | Path-reopening reporting; recompute/check identity each requested call and detect replacement on next call. |

## Explicit exclusions

- No scientific formula, denominator, mask, cohort, ranking, or evidence-role change.
- No Zarr schema, manifest, promotion seal, validation rule, writer, or atomic-promotion change.
- No generic projection registry/framework, dependency-injection container, compatibility aliases, or rollout-root re-exports.
- No visual redesign, navigation redesign, chart/label changes, or new Streamlit controls in A or B.
- No eager full-store reads, automatic deep Q_H counts, or hidden-tab computation.
- No Rerun entity/blueprint changes, generation/control-plane work, or new persistence.
- No migration of rollout-domain meaning into `app`, `utils.rich_summary`, or `utils.cli_format`.
- No attempt in B to type every existing dictionary row; add a facet only when an existing consumer plus a failing parity test proves that demand boundary.
- Reassess scientific-figure grammar, shared page framing, and typed per-workflow UI state only after both issues land and are measured.

## RALPLAN-DR (short mode)

### Principles

1. **Behavior before structure:** freeze observable lazy-read and replacement behavior before refactoring.
2. **One durable owner per truth layer:** `aria_nbv.rollouts` owns meaning; the Streamlit session owns lifecycle/cache policy; renderers own presentation.
3. **Identity is an invalidation contract:** reader/core-bound caches use the handle-captured replacement identity; path-reopening caches refresh it at invocation; cache-root inventory is explicitly exempt.
4. **Named depth, not generic breadth:** expose task-specific session methods and demand-aligned typed facets; do not introduce a projection framework or universal result.
5. **Sequential delivery:** land and verify A before B; land and verify B before C.
6. **Restore semantics, not history:** port only the lost scientific contracts into current domain and presentation owners; do not replay the historical branch architecture.

### Top decision drivers

1. Preserve atomic same-path replacement and tamper detection across every cached consumer.
2. Preserve zero-read/bounded-read lazy behavior while reducing page-level cache coupling.
3. Establish a stable session seam that B can consume without moving domain semantics into Streamlit.
4. Restore candidate-support invariants and denominators without adding a second cache, projection, or explanation framework.

### Viable options

#### Option 1 — Fixed-identity `StoredRolloutSession` façade over private caches (recommended)

**Approach:** open a small per-rerun `(canonical_path, identity)` snapshot handle, eagerly bind its core once, and delegate only demand-backed named operations to module-private decorated functions.

**Pros:** natural page-facing grouping; one identity walk per open/rerun for reader/core-bound work; one measurable cache/invalidation owner; gives B one Streamlit adoption seam.

**Cons:** can become a shallow 20+ method mirror if demand-backed restraint is ignored; held reader/validation/manifest values are mutable; page call-site migration is broad even with unchanged behavior.

#### Option 2 — Functional named cache module plus a tiny snapshot key handle

**Approach:** in the same selected owner module, `_stored_rollout_session.py`, add a small immutable `(canonical_path, identity)` value and module-level named functions; remove the wide string dispatcher, but pass the handle explicitly rather than wrapping operations in a class.

**Pros:** closely matches how Streamlit decorators actually own cache state; keeps cache keys explicit; avoids an object façade over mutable cached values; can expose the same demand-backed operations without a generic dispatcher.

**Cons:** page/render helpers pass the handle to many functions; lifecycle grouping is less discoverable; B has no single object-oriented Streamlit integration point; core snapshot values require a separate access function.

**Why not chosen:** it is fully viable and is the fallback if characterization shows the façade would only mirror the dispatcher. Option 1 is preferred because one page-facing session groups the already selected store and gives B a narrow Streamlit consumer seam, provided its public surface remains demand-backed.

#### Invalidated alternative — generic projection registry/framework

A registry mapping names to functions could shrink the dispatcher, but it would erase distinct parameter/laziness contracts, make static ownership weaker, and directly violates the locked no-generic-framework constraint. It is not viable for this scope.

## ADR

### Decision

Choose Option 1 inside `_stored_rollout_session.py`: create a panel-local, fixed-identity single-rerun `StoredRolloutSession` handle over module-private caches, demand-backed named operations, and one owner-level global invalidation API. Preserve reader/core as `st.cache_resource(show_spinner=False)` with `max_entries` unset, retain topology as `st.cache_resource(max_entries=16)`, and retain the existing bounded `st.cache_data` limits for serializable inventory/projection/candidate/failure/evidence values. Cache owners accept cache-stable arguments/values and retain existing structured topology inputs. Its snapshot guarantee covers reader/core-bound operations only; topology/report calls compute identity at invocation. If the façade proves shallow, Option 2 changes only the module's internal/public callable shape, not its owner path. After A merges, add separate typed manifest, validation, promotion, effective-trust composition, and compact-statistics facets at existing demand points.

### Drivers

- Exact same-path replacement correctness: next-open/rerun for reader/core-bound work, next invocation for path-reopening work, and no unsupported universal snapshot claim.
- Retention of consumer-specific lazy/bounded materialization and CLI mode semantics.
- Clear separation between domain facets, Streamlit lifecycle/cache policy, and rendering.

### Alternatives considered

- Functional named shape in `_stored_rollout_session.py` with a tiny path/identity handle and no string dispatcher.
- Generic projection registry/framework.
- One union trust/statistics DTO.
- Moving cache identity or rollout facets into `rich_summary.py`.

### Why chosen

The fixed-identity session makes the reader/core identity lifetime explicit while giving the page one selected-store handle. Module-private decorators remain the actual cache owners; path-reopening operations deliberately refresh identity per call. Exact cache-policy migration avoids coupling an unmeasured reader-eviction change to the seam: core retains its unset/default bound (`_stored_rollouts_page.py:177-191`), while topology retains its existing 16-entry resource bound (`_stored_rollouts_page.py:377-385`). Separate B facets and explicit trust composition retain the intentional differences between default CLI, flagged CLI modes, Streamlit trust, and reporting. C then adds only current-owner scientific reducers and plot renderers on top of those stable seams. The functional alternative remains acceptable inside the same owner module if characterization disproves the façade's depth; the registry, union DTO, and wholesale historical replay are invalid because they obscure operation/read-depth contracts.

### Consequences

- PR A begins with two distinct checkpoints: green characterization of current page owners, then a session-contract checkpoint before page migration; the preferred second checkpoint is green via a minimal non-migrating scaffold.
- PR A will have a broad mechanical call-site diff within one panel but a narrow behavioral scope.
- A replacement occurring after open is observed on the next open/rerun by reader/core-bound operations and on the next invocation by topology/report operations. Only bound-reader work stays on the captured generation.
- Cache decorators, mutable core values, and the complete clear-owner tuple remain private implementation details of the session module.
- The resource/data distinction and exact current bounds are part of the migration contract: core remains unset/default, topology remains 16, and bounded data-cache limits remain unchanged. Existing structured topology arguments remain intact rather than being normalized into primitive-only keys.
- Domain facet reuse remains intentionally deferred to B.
- Scientific candidate-support restoration remains intentionally deferred to C so A and B retain behavior-preserving review boundaries.
- Only current call-site operations are exposed; if the class becomes a dispatcher mirror, use functional Option 2 within `_stored_rollout_session.py` instead.

### Follow-ups

- Land B only after A's exact cache/session acceptance suite is green on the merged base.
- In B, record mode-specific builder counts before and after adoption; do not infer a universal common read depth.
- After A+B, execute only the evidence-backed C restoration matrix. Measure remaining page complexity and duplicated result construction before considering any further presentation or workflow-state changes.

## Implementation plan

### Phase A0 — freeze behavior before refactor

#### A0.1 — green characterization checkpoint against current page owners

1. Extend `aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py` and `aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py` without importing a not-yet-created session module. Characterize the current `_stored_rollouts_page.py` owners for replacement-sensitive identity, same-path replacement, cache reuse/recomputation, candidate-population laziness, dynamic-tab gating, and explicit refresh behavior. Preserve the existing assertions at `test_stored_rollouts_projection_laziness.py:22-225` and `:282-366` and `test_counterfactual_rollouts_panel.py:565-629`.
2. Run the two focused files and record a **green** result before adding a session scaffold or moving/removing any page owner:

   ```bash
   cd aria_nbv
   uv run pytest \
     tests/app/panels/test_stored_rollouts_projection_laziness.py \
     tests/app/panels/test_counterfactual_rollouts_panel.py -q
   ```

#### A0.2 — session-contract checkpoint before page migration

3. In `aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py`, add contract tests for the proposed `_stored_rollout_session.py` owner:
   - identical path and unchanged store -> identical identity and one cached store-open per cache key;
   - one open handle captures identity once and its reader/core-bound projection, candidate-population, and failure operations keep using that bound core if the path is replaced mid-test;
   - after a mid-handle atomic replacement, topology and evidence/report operations compute a fresh invocation identity and observe the replacement on their next call; the test must not expect them to use the captured core generation;
   - the next open after manifest/array mutation or atomic symlink/directory replacement captures a new identity and recomputes reader/core-bound owners;
   - explicit invalidation -> each decorated owner is cleared once, including inventory and candidate population; no per-instance eviction claim;
   - changing `inventory_row` alone changes presentation metadata only and does not change identity, core trust, or domain facet inputs;
   - cache decorators match the exact current matrix: reader/core resource cache with `show_spinner=False` and unset `max_entries`; topology resource cache with `max_entries=16`; bounded data caches with their unchanged limits;
   - topology retains `PathConfig`, the VIN-directory tuple, and selected source row as structured cache-stable arguments/values;
   - lightweight named operations -> zero calls to candidate-audit/population/deep Q_H owners unless explicitly invoked.
4. Preferred sequence: add the smallest **non-migrating** `_stored_rollout_session.py` scaffold needed to make the A0.2 contract tests green while `_stored_rollouts_page.py` remains the production rendering owner. An intentional red TDD checkpoint is permitted only when the exact failing test names, expected failures, and command output are recorded; make it green with the smallest scaffold before migration. In either sequence, do not migrate or remove page owners until the session-contract checkpoint is understood and preferably green.
5. Run `uv run pytest tests/app/panels/test_stored_rollouts_projection_laziness.py -q -k stored_rollout_session` and record whether the checkpoint is green or intentionally red with the required expected-failure evidence. The implementation lane may proceed to migration only after this state is explicit.

### Phase A1 — establish the session owner

6. Complete `aria_nbv/aria_nbv/app/panels/_stored_rollout_session.py` with:
   - a small `StoredRolloutSession` snapshot handle for canonical path and captured identity, with core reader/validation/manifest bound for one open/rerun but not described as transitively immutable;
   - `open_stored_rollout_session(path, inventory_row=...)`;
   - the current replacement-sensitive identity algorithm;
   - named methods only for operations used by current render call sites, with reader/core-bound versus path-reopening operations explicit;
   - the exact Streamlit cache kinds and current `max_entries` settings in the migration matrix: reader/core unset, topology 16, and existing data-cache bounds unchanged;
   - cache-stable arguments/values, retaining `PathConfig`, the VIN-directory tuple, and selected source row for topology without flattening or redesign;
   - `clear_stored_rollout_caches()` over the complete explicit tuple in the cache migration matrix.
7. Keep every named method a thin call into current `aria_nbv.rollouts.inspection`/`reporting` owners. Do not move or rewrite the functions imported at `_stored_rollouts_page.py:31-62` except to relocate their Streamlit cache wrappers.
8. Ensure reader/core-bound decorated functions take canonical path and captured identity and call the core with that same identity. Ensure topology/report functions compute and pass fresh identity at invocation. Candidate population is reader-bound. Inventory remains cache-root keyed and presentation-only. Owner-level invalidation clears all matrix owners.

### Phase A2 — migrate page call sites and verify

9. Only after A0.1 is green and A0.2 is understood, update `_stored_rollouts_page.py` to open one snapshot handle after store selection and pass/use it in render helpers. Replace string projection dispatch with the smallest demand-backed named surface while preserving the exact conditions around each call.
10. Leave `stored_rollouts.py` as the stable public render entry point (`aria_nbv/aria_nbv/app/panels/stored_rollouts.py:1-16`). Do not export the session from the package root.
11. Remove superseded cache/identity/invalidation definitions from `_stored_rollouts_page.py`; do not leave compatibility aliases.
12. Run A verification and inspect the diff for visual/scientific/persistence changes. Stop A when both checkpoint records, the focused tests, lint/format, cache-owner search, and diff checks pass.

### Phase B0 — prove existing facet demand boundaries

13. On A's merged base, add parity/spy tests in `aria_nbv/tests/rollouts/test_inspection.py`, `test_reporting.py`, `test_info_cli.py`, and the Streamlit session/panel tests. Freeze these exact per-mode counts before production changes:
    - default CLI: manifest 1; validation 0; promotion 0; statistics 0;
    - CLI `--validate`: manifest 1; validation 1; promotion 0; statistics 0;
    - CLI `--stats`: manifest 1; validation 0; promotion 0; statistics 1;
    - CLI `--preflight`: manifest 1; validation 1; promotion 0; statistics 1;
    - Streamlit lightweight trust/header: manifest/core 1; validation 1; promotion 1; statistics 0;
    - reporting/export: manifest 1; validation 1; promotion 1; statistics 1 per store, with current report-specific projections unchanged.
14. Preserve current JSON/text values, exit behavior, deterministic frames/bytes, and array-reader spies for each mode; in particular, default CLI remains manifest-only and Streamlit header remains compact-statistics-free.

### Phase B1 — add and adopt typed domain facets

15. Add separate frozen, slots-based named facets/builders in `aria_nbv.rollouts.inspection` or a narrow sibling module for manifest facts, schema validation, promotion evidence, effective Streamlit trust, and compact statistics. Effective trust copies validation errors and appends promotion error last; it does not mutate a validation facet shared with CLI.
16. Update A's session to cache/hold only the facets its current Streamlit path demands and use effective trust for its existing `validation.ok`/blocked decisions. Update `info_cli.py` to choose facets from flags without promotion/effective-trust construction. Update `reporting.py` to preserve validation-first then promotion-error sequencing before its existing projections. Keep renderer-specific conversion in Streamlit, `cli_format`, and report-frame assembly.
17. Add failure-path tests: Streamlit promotion failure appears last in effective errors and blocks scientific rendering; reporting promotion failure raises the same promotion-validation `ValueError`; default and flagged ordinary CLI modes remain unaffected by promotion failure.
18. Delete superseded duplicate assembly; add no aliases, union DTO, or optional legacy pathway. Run B verification and stop when mode counts, promotion/error behavior, parity, and deterministic-byte checks pass.

### Phase C0 — lock the loss and current denominator contracts

19. Add focused failing characterization tests before production changes:
    - target-normalized geometry maps root to `(0, 0)`, target to `(1, 0)`, and a known rightward candidate to the expected signed lateral coordinate;
    - missing/degenerate target baselines produce unavailable normalized coordinates;
    - equal-area direction bins use azimuth and `sin(elevation)`, include complete bins, and sum to one for each eligible state before state-then-scene macro aggregation;
    - uneven candidate fanout and uneven scene sizes do not candidate-pool the macro result;
    - invalid/zero direction vectors reduce the declared denominator and never become zero-valued directions;
    - collision, target-view, spatial-shell, and motion/path missingness remains explicit.
20. Add UI characterization for two distinct demand boundaries. The default page may read at most the configured display limit from the bounded candidate-audit projection to render target-normalized geometry; it must not materialize complete-population aggregates. The explicit candidate-evidence action remains the sole owner of one complete candidate-audit materialization reused by all aggregate reducers.

### Phase C1 — restore presentation-free candidate-support evidence

21. In `aria_nbv.rollouts.inspection`, add the smallest current-schema reducers for normalized geometry, equal-area direction density, spherical-cap/angular coverage, spatial shell, target-view, and motion/path support. Prefer one typed candidate-support bundle assembled from one existing candidate-audit row materialization; retain the current candidate-population summaries instead of duplicating them.
22. Preserve exact current generation-cohort identity and state/scene fields on every aggregate row. Fail closed or mark unavailable when the persisted evidence is insufficient for the requested claim. Keep deterministic ordering and current dictionary-row conventions unless an existing typed row owner can be deepened without broadening B.
23. Expose one demand-backed C operation through A's session owner. Bind it to the captured store identity, use the existing candidate data-cache policy, and include it in owner-level invalidation without adding a new independently decorated cache when the existing candidate-population cache can own the bundle.

### Phase C2 — restore plot-first Streamlit views and verify

24. Render the following in the existing candidate-generation/admission surface, keeping reward/reconstruction evidence elsewhere:
    - target-normalized candidate endpoints/rays with fixed root/target anchors and equal axes;
    - equal-area azimuth × `sin(elevation)` density heatmap;
    - spherical-cap discrepancy and angular-separation/coverage plots when their evidence is available;
    - spatial-shell radius/height support;
    - target-view availability/support and motion/path support;
    - collision/clearance support with explicit evaluated, unavailable, and not-applicable denominators.
25. Keep each primary plot visible after the explicit candidate-evidence load. Place its exact rows and download in one collapsed expander directly beneath it. Reuse existing Plotly/render and `ScientificExplanation` helpers; do not add navigation layers or another explanation model.
26. Preserve or improve the current family composition, proposal calibration, and actor-valid/selection views by wiring the existing current reducers into plot-first renderers only where they already have scientifically correct denominator semantics. Do not duplicate a current equivalent plot merely because PR #38 used another visual style.
27. Run C verification and inspect the diff for generation, persistence, Q_H, CLI/report, Rerun, and cache-policy drift. Make C a separate focused commit after A and B.

## Acceptance criteria

### A — cache/session PR

- [ ] **Two tests-first checkpoints:** A0.1 records a green run against existing `_stored_rollouts_page.py` owners before any session scaffold or owner migration. A0.2 records the new session-contract result before migration: preferably green via the smallest non-migrating scaffold, or intentionally red only with exact expected failures recorded and then made green before page-owner removal. No production page migration starts while the contract state is ambiguous.
- [ ] **Identity/open boundary:** one `open_stored_rollout_session` computes identity exactly once. For an unchanged store, later opens obtain the same identity; Zarr mutation, manifest replacement, or atomic same-path swap produces a different identity on the next open/rerun. Identity performs zero `Path.read_bytes()` payload reads (`aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py:122-175`, `:282-317`).
- [ ] **Bound-core consistency:** core, named projections, candidate population, and failures on one already-open handle pass its captured identity and remain on one bound reader/core generation after mid-handle replacement.
- [ ] **Path-reopening detection:** topology and evidence/report bundle compute/check identity at each invocation. After mid-handle replacement, their next calls observe the replacement; no test or doc claims they share the bound-core snapshot (`aria_nbv/aria_nbv/dataset_topology.py:324-377`, `aria_nbv/aria_nbv/rollouts/reporting.py:567-580`).
- [ ] **All-cache replacement:** across before/after opens or invocations as appropriate, reader/core, lightweight projection, candidate population, topology, failure, and evidence-bundle results come from the contractually correct generation (`aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py:282-366`).
- [ ] **Owner-level invalidation:** one `clear_stored_rollout_caches()` call invokes `.clear()` exactly once on every matrix owner, including inventory and candidate population. Tests and docs do not claim per-session/per-key eviction.
- [ ] **Cache kind and bounds:** reader/core uses `st.cache_resource(show_spinner=False)` with `max_entries` unset; topology uses `st.cache_resource(max_entries=16)`; inventory uses `st.cache_data(max_entries=8)`; named projections and candidate population use `st.cache_data(max_entries=128)`; failures use `st.cache_data(max_entries=32)`; evidence uses `st.cache_data(max_entries=16)`.
- [ ] **Argument-shape preservation:** cache owners accept cache-stable arguments/values, and topology continues to receive the existing structured `PathConfig`, VIN-directory tuple, and selected source row without cache-motivated flattening or redesign.
- [ ] **Lazy reads:** opening the default page may issue only the bounded candidate-audit read required by the default normalized-geometry preview. It performs zero candidate-population, root-geometry, rollout-tree, deep-Q_H, or `rollout_statistics` work; every complete or unrelated projection remains behind its explicit control/section (`aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py:565-629`).
- [ ] **Bounded heavy reads:** explicit candidate grouping performs at most one candidate materialization and reuses those rows (`aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py:62-107`).
- [ ] **Narrow cache ownership:** a search limited to `_stored_rollout_session.py`, `_stored_rollouts_page.py`, and `stored_rollouts.py` shows stored-rollout cache decorators, identity, cache-clear tuple, and direct `RolloutZarrStoreReader(` construction only in the session module; every hit is classified. The page contains no generic string projection dispatcher.
- [ ] **Internal-shape independence:** whether implementation selects the class façade or functional fallback, all cache policy remains in `_stored_rollout_session.py`; owner-search criteria and imports do not change.
- [ ] **Inventory separation:** `inventory_row` and `_cached_inventory` are presentation-only; changing a row does not change store identity/trust/facets, and inventory remains keyed only by cache root.
- [ ] **No aliases:** removed page-private cache helpers are not re-exported or retained as compatibility shims; tests target the session's public-within-panel API.
- [ ] **No behavior drift:** existing panel labels, dynamic-tab conditions, query/Rerun/download paths, report bytes, validation outcomes, and scientific projection functions are unchanged.
- [ ] **One focused PR:** changed product paths are limited to the new session module and stored-rollout page integration, plus focused tests; no visual assets, `aria_nbv.rollouts` domain logic, Zarr writer/schema, or Rerun implementation changes.

### B — typed-result reuse PR

- [ ] B names A as a blocking dependency and is based on A's merged commit.
- [ ] Named typed manifest, validation, promotion, effective Streamlit trust, and compact-statistics facets/composition live in `aria_nbv.rollouts`; no union DTO requires all fields, and each consumer constructs only its current demanded facets.
- [ ] Default CLI calls manifest once and validation/promotion/statistics zero times; `--validate` calls validation once only; `--stats` calls statistics once only; `--preflight` calls validation and statistics once each. All ordinary CLI modes call promotion zero times (`aria_nbv/aria_nbv/rollouts/info_cli.py:112-168`, `aria_nbv/tests/rollouts/test_info_cli.py:23-75`).
- [ ] Streamlit lightweight trust/header calls validation and promotion once, compact statistics zero times, and preserves its metadata-only header depth (`aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:177-191`, `aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py:712-751`).
- [ ] Reporting calls manifest, validation, promotion, and statistics once per store, then performs exactly its existing report-specific projection reads (`aria_nbv/aria_nbv/rollouts/reporting.py:567-635`).
- [ ] Streamlit effective trust preserves validation error order, appends a promotion error last, and blocks scientific rendering when promotion fails (`aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py:110-119`, `aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py:177-194`).
- [ ] Reporting preserves validation-first failure and distinct promotion-validation `ValueError` behavior; promotion-failure fixtures are covered in `aria_nbv/tests/rollouts/test_reporting.py`. Ordinary CLI modes remain promotion-blind.
- [ ] No B facet accepts or exposes `inventory_row`.
- [ ] CLI `--json`, text, validation, stats, preflight exit behavior, and thesis-bundle metadata remain byte/value compatible with their existing tests (`aria_nbv/aria_nbv/rollouts/info_cli.py:112-168`).
- [ ] Existing report table names/columns and serialized JSON bytes remain deterministic (`aria_nbv/aria_nbv/rollouts/reporting.py:476-564`).
- [ ] Existing CLI/report statistics parity remains green (`aria_nbv/tests/rollouts/test_reporting.py:63-115`), with facet-value parity at every adopting consumer.
- [ ] `rich_summary.py` has no rollout imports, rollout DTOs, cache identity, or rollout-field branching after B.
- [ ] No new CLI command, export format, compatibility alias, generic projection framework, or presentation redesign is introduced.

### C — scientific candidate-support restoration PR

- [ ] C is based on verified A+B and introduces no second session/cache owner, generic dispatcher, compatibility alias, dependency, schema, generation, training, CLI/report, or Rerun change.
- [ ] Target-normalized geometry is presentation-free and numerically verified: root `(0, 0)`, target `(1, 0)`, signed right-handed lateral coordinate, nonzero planar baseline required, and missing/degenerate inputs remain unavailable.
- [ ] The target-normalized plot has equal axes, fixed root/target anchors, deterministic point/ray bounding, and no line joining unrelated candidates. Aggregate evidence is never computed from the bounded display subset.
- [ ] Direction density uses azimuth × `sin(elevation)` equal-area bins, complete deterministic bin rows, explicit finite/missing denominators, and state-then-scene-then-cohort macro aggregation. Fractions sum to one within every eligible state before macro aggregation.
- [ ] Spherical-cap and angular-separation evidence uses fixed deterministic reference settings and describes support/coverage only; it is not presented as policy performance.
- [ ] Spatial-shell metrics retain metres and signed Z; zero radius remains valid. Target-view evidence never substitutes path collision for LOS/FOV. Motion/path conjunctions are explicit rather than inferred.
- [ ] Collision/clearance plots count only explicitly applicable/evaluated rows, distinguish unavailable from not-applicable, and show a truthful zero-collision state without inventing support.
- [ ] Exact generation cohorts and incompatible candidate/profile contracts are never pooled. Uneven state fanout and scene sizes pass macro-denominator regressions.
- [ ] One complete candidate-audit materialization supplies all aggregate reducers for one requested store/cohort. Default/lightweight page load may perform one bounded, deterministic audit read capped by the configured display limit for normalized geometry only; the explicit candidate-evidence action performs the complete scan once and no hidden section repeats it.
- [ ] Primary scientific views are plot-first after explicit load, with exact rows/CSV collapsed immediately beneath the corresponding plot. Current reward/reconstruction, Q_H, topology, failures, query/export, and Rerun surfaces remain unchanged.
- [ ] Every new plot uses the existing `ScientificExplanation` path and includes relevant interpretation, visual encoding, denominator/missingness, uncertainty limits, and canonical scientific links where applicable.
- [ ] Focused inspection and panel tests, Ruff format/check, compileall for changed modules, owner/scope searches, and `git diff --check` pass.

### G004 — final integrated verification and quality gate

- [ ] Run the final gate on the exact integrated HEAD after G003; all earlier
  test, review, lint, compile, and scope results are treated as stale if that
  HEAD changes.
- [ ] Run the changed-files `ai-slop-cleaner`, then rerun format, lint, the
  focused inspection/panel suites, compile checks, CLI probes where applicable,
  `git diff --check`, and the ownership/scope audit.
- [ ] Prove the architecture invariants: one panel-local session/cache owner;
  domain projections remain in `rollouts`; no generic projection framework,
  compatibility aliases, schema/generation/training/CLI/report/Rerun drift,
  or eager hidden-tab reads.
- [ ] Obtain an independent code-reviewer `APPROVE` and independent architect
  `CLEAR` for the exact final HEAD. Repair any blocker and rerun the affected
  checks before completing the aggregate goal.
- [ ] Record the exact HEAD and all verification evidence in the Ultragoal
  ledger and the dated debrief. No push, PR, issue, or other external GitHub
  write is part of this gate.

### G007 — accepted final scientific-view corrections

- [x] The discounted-return session operation passes its reader exactly once and
  a generated-store regression proves the typed rows and replacement-sensitive
  cache behavior.
- [x] The bounded target-normalized geometry preview is default-visible without
  triggering the complete candidate-population scan; its caption states the
  displayed and total populations.
- [x] Cohort macros remain the default scientific grain. Scene and state views
  require an exact persisted identity selection and never silently recombine
  several lower-grain populations.
- [x] Declared spatial shells remain visually explicit. Metres, degrees,
  fractions, and counts are rendered on separate axes/figures.
- [x] `ScientificExplanation` remains the sole explanation owner and gains only
  optional intuition, visual-encoding, uncertainty, and canonical theory
  references. Registry keys resolve to current notation/glossary owners;
  inspection-only diagnostics link their code owner instead of inventing
  equations.
- [x] A same-scene/two-state regression proves `state_count=2`,
  `defined_state_count=2`, and `scene_count=1` for spatial and target-view
  cohort macros.

### G008 — canonical-reference ownership completion

- [x] Temporal endpoint/root gain links `entity.endpoint_gain` to
  `docs/typst/shared/equations/entity.typ`; target RRI links `rri.rri` and
  `rri.target_rri` to `docs/typst/shared/equations/rri.typ`.
- [x] Selected probability and entropy link the existing robust temperature
  softmax owner. Unknown temporal metrics fail closed instead of inheriting an
  unrelated reference category.
- [x] Target-view, collision/clearance, candidate-family, and mask-count plots
  carry the relevant target, code, or candidate-validity reference bundle.
- [x] A source-ownership census proves every registry key exists in the linked
  canonical equation, notation, glossary, or source owner and rejects URL/key
  mismatches.

### G009 — collision-denominator reference ownership correction

- [x] Collision applicability, evaluation, and clearance-denominator
  explanations link the existing inspection-code owner rather than an
  unrelated candidate-validity registry key.
- [x] The focused UI regression rejects fabricated registry keys and preserves
  the scientific projection and denominator behavior.
- [x] The reference-only correction passes the final changed-files cleanup,
  212 focused tests, Ruff format/check, compileall, CLI help, diff checks, and
  independent code-reviewer `APPROVE` plus architect `CLEAR` on exact HEAD
  `101c713d8136ee4380be7f4c008b1136cd5252c0`.

## Risks and mitigations

| Risk | Mitigation / proof |
|---|---|
| Production migration begins before current behavior and the proposed session contract are distinguishable. | Enforce A0.1 as a green current-owner checkpoint, then A0.2 as an explicit session-contract checkpoint. Prefer the smallest non-migrating scaffold to make A0.2 green; if intentionally red, record exact expected failures and make the scaffold green before removing or rerouting page owners. |
| A named session accidentally computes heavy projections or statistics during construction. | Open only the core snapshot; expose demand-backed operations. Spy candidate/deep-Q_H/statistics owners and require zero calls on default/lightweight workspaces (`test_counterfactual_rollouts_panel.py:604-629`). |
| A mid-render replacement mixes old reader/core state with reader-bound projections. | Capture identity once, bind core during open, and require reader/core-bound caches to receive that identity; test replacement between bound-reader calls and a subsequent new open. |
| The plan overclaims snapshot consistency for topology/report functions that reopen the path. | Compute/check fresh identity at each topology/report invocation; test mid-handle replacement before the next call and explicitly make no concurrent-call snapshot guarantee. |
| Implementers claim `frozen=True` makes mutable validation/manifest content immutable. | Describe the object as a fixed-identity snapshot handle only; keep mutable core values private/bound and cite `RolloutZarrValidationResult.errors` mutability (`zarr_store.py:395-423`). |
| One cache omits `store_identity`, retaining stale evidence after an atomic swap. | Enumerate every session-owned cache; parameterize before/after replacement across reader, projection, topology, failure, and bundle (`test_stored_rollouts_projection_laziness.py:282-366`). |
| Refactor omits candidate population from invalidation or silently changes cache kind/capacity. | Treat the static cache matrix as the exact migration checklist: core remains resource-valued with `show_spinner=False` and unset `max_entries`; topology remains resource / 16; inventory/projections/candidate/failures/evidence remain bounded data caches at their listed limits; add candidate population to the clear tuple (`_stored_rollouts_page.py:177-218`, `:377-479`). Defer any core-capacity policy to a separately measured follow-up. |
| Cache-key wording causes existing structured topology inputs to be flattened or redesigned. | Require cache-stable arguments/values rather than primitive-only keys; retain and spy the existing `PathConfig`, VIN-directory tuple, and selected row values through `_cached_topology`. |
| Inventory metadata accidentally becomes an identity or trust input. | Keep inventory cache root keyed, treat `inventory_row` as presentation-only, and test different rows against identical identity/core/facets. |
| Named methods duplicate a large amount of boilerplate. | Expose only demand-backed operations. If the façade becomes a dispatcher mirror, select the viable functional-module Option 2; add no registry/framework. |
| B recreates a universal result object or types all projections. | Freeze four demand-aligned facet boundaries and the mode-specific call matrix before implementation; require a current consumer and failing parity test before adding a facet. |
| B changes default CLI or promotion behavior. | Assert default manifest-only calls and zero promotion calls in every ordinary CLI mode; reporting retains its existing promotion check (`info_cli.py:112-168`, `reporting.py:573-580`). |
| Separate validation/promotion facets lose Streamlit's appended-error blocked behavior or reporting's distinct error. | Test effective-trust error ordering/blocking in the panel seam and promotion-validation `ValueError` in `test_reporting.py`; never feed effective trust to ordinary CLI. |
| Reporting/CLI behavior drifts when adopting typed facets. | Compare prior/new JSON values, mode-specific calls, preflight exit codes, exact report table schemas, and serialized bytes (`reporting.py:518-564`, `test_reporting.py:63-115`). |
| Historical session code is copied and regresses replacement detection. | Treat history only as structural evidence; implementation must port the current identity into every cache key and pass current same-path tests. |
| Mechanical page migration changes presentation. | No snapshot/UI redesign work; compare widget labels/control presence and keep the existing 69-test panel baseline green. |
| C replays PR #38 and revives stale session/UI architecture. | Port only reducer mathematics and scientifically useful visual forms into current `rollouts.inspection`, A's session, and the current candidate UI; reject historical cache/session/navigation code. |
| Equal-area density is accidentally computed in raw elevation or candidate-pooled. | Lock azimuth × `sin(elevation)`, complete-bin, per-state normalization, and state-then-scene macro tests before rendering. |
| Display bounding contaminates scientific aggregates. | Compute all reducers from the complete admitted population, then bound only raw point/ray marks. Assert aggregate values are unchanged when display limit changes. |
| Candidate-support evidence is mistaken for reward or policy superiority. | Keep C in admission/feasibility, label it descriptive support evidence, and leave reward/reconstruction owners untouched. |
| C adds unbounded eager work to the default page. | Permit only the deterministic, row-limited normalized-geometry audit read on default load; keep the complete candidate-population scan behind the explicit evidence dispatch and require exactly one complete materialization after dispatch. |
| Restored claims overstate unavailable LOS, collision, or target geometry. | Preserve explicit applicability/evaluation/missingness; never substitute another field or zero-fill unavailable evidence. |

## Verification

### PR A

Checkpoint A0.1 must be captured first and must be green against the existing page owners:

```bash
cd aria_nbv
uv run pytest \
  tests/app/panels/test_stored_rollouts_projection_laziness.py \
  tests/app/panels/test_counterfactual_rollouts_panel.py -q
```

Checkpoint A0.2 is captured next, before page-owner migration/removal:

```bash
cd aria_nbv
uv run pytest \
  tests/app/panels/test_stored_rollouts_projection_laziness.py \
  -q -k stored_rollout_session
```

Preferred evidence is a green A0.2 result produced by the smallest non-migrating session scaffold. If the team intentionally records red TDD first, attach the exact failing test names, expected reasons, and output, then attach the green result after the smallest scaffold and before any `_stored_rollouts_page.py` ownership migration.

After migration, run the full PR-A verification:

```bash
cd aria_nbv
uv run pytest \
  tests/app/panels/test_stored_rollouts_projection_laziness.py \
  tests/app/panels/test_counterfactual_rollouts_panel.py -q
uv run ruff format --check \
  aria_nbv/app/panels/_stored_rollout_session.py \
  aria_nbv/app/panels/_stored_rollouts_page.py \
  tests/app/panels/test_stored_rollouts_projection_laziness.py \
  tests/app/panels/test_counterfactual_rollouts_panel.py
uv run ruff check \
  aria_nbv/app/panels/_stored_rollout_session.py \
  aria_nbv/app/panels/_stored_rollouts_page.py \
  tests/app/panels/test_stored_rollouts_projection_laziness.py \
  tests/app/panels/test_counterfactual_rollouts_panel.py
rg -n 'RolloutZarrStoreReader\(|@st\.cache_|def _cached_projection|def _store_projection_identity|clear_stored_rollout_caches|_SESSION_CACHE_OWNERS' \
  aria_nbv/app/panels/_stored_rollout_session.py \
  aria_nbv/app/panels/_stored_rollouts_page.py \
  aria_nbv/app/panels/stored_rollouts.py
git diff --check
```

Evidence required in the PR: both A0 checkpoint records; test count/output; every narrow owner-search hit classified; reader/core mid-handle consistency; topology/report next-invocation replacement detection; next-open core replacement detection; inventory separation; exact cache kind/bound assertions for all seven owners, including core `max_entries` unset and topology `16`; structured topology-argument preservation; complete matrix/clear-owner coverage including candidate population; and changed paths proving no domain/persistence/visual expansion.

### PR B

```bash
cd aria_nbv
uv run pytest \
  tests/rollouts/test_inspection.py \
  tests/rollouts/test_reporting.py \
  tests/rollouts/test_info_cli.py \
  tests/app/panels/test_stored_rollouts_projection_laziness.py \
  tests/app/panels/test_counterfactual_rollouts_panel.py -q
uv run ruff format --check aria_nbv/rollouts aria_nbv/app/panels tests/rollouts tests/app/panels
uv run ruff check aria_nbv/rollouts aria_nbv/app/panels tests/rollouts tests/app/panels
git diff --check
```

Evidence required: unchanged CLI values/exit codes; exact serialized report-byte parity; the six mode-specific call-count rows from Phase B0; effective-trust appended promotion error and blocked behavior; reporting promotion-error behavior; facet-value parity; no ordinary CLI promotion call; no inventory facet input; and unchanged report-specific read depth.

### PR C

```bash
cd aria_nbv
uv run pytest \
  tests/rollouts/test_inspection.py \
  tests/app/panels/test_stored_rollouts_projection_laziness.py \
  tests/app/panels/test_counterfactual_rollouts_panel.py -q
uv run ruff format --check \
  aria_nbv/rollouts/inspection.py \
  aria_nbv/app/panels/_stored_rollout_session.py \
  aria_nbv/app/panels/_stored_rollouts_page.py \
  tests/rollouts/test_inspection.py \
  tests/app/panels/test_stored_rollouts_projection_laziness.py \
  tests/app/panels/test_counterfactual_rollouts_panel.py
uv run ruff check \
  aria_nbv/rollouts/inspection.py \
  aria_nbv/app/panels/_stored_rollout_session.py \
  aria_nbv/app/panels/_stored_rollouts_page.py \
  tests/rollouts/test_inspection.py \
  tests/app/panels/test_stored_rollouts_projection_laziness.py \
  tests/app/panels/test_counterfactual_rollouts_panel.py
uv run python -m compileall \
  aria_nbv/rollouts/inspection.py \
  aria_nbv/app/panels/_stored_rollout_session.py \
  aria_nbv/app/panels/_stored_rollouts_page.py
git diff --check
```

Evidence required: exact normalized-coordinate fixtures; missing/degenerate-baseline behavior; equal-area complete-bin and per-state-sum proof; uneven-fanout/scene macro proof; collision/target-view/motion missingness proof; one-materialization and default-zero-read spies; figure assertions for fixed anchors, equal axes, heatmap variables, and unjoined rays; plot-first/collapsed-row UI assertions; and a changed-path audit proving no generation, schema, training, CLI/report, or Rerun delta.

## Stop rules

- Stop A if preserving same-path replacement would require changing the persistence/promotion contract; raise a follow-up instead.
- Stop A if the class façade becomes a near-complete mirror of the old dispatcher; switch to the viable functional named shape inside `_stored_rollout_session.py` rather than adding shallow methods, another owner module, or a generic escape hatch.
- Stop A if topology/report correctness would require claiming a path snapshot not supported by their current APIs; retain fresh invocation identity and the next-call guarantee.
- Do not begin B until A is merged and its focused suite is green on the merged base.
- Stop B at the demand-aligned manifest/validation/promotion/statistics facets unless a current consumer plus failing parity test proves another facet is necessary.
- Stop B if any ordinary CLI mode gains a promotion check, default CLI gains validation/statistics, Streamlit lightweight trust gains statistics, or reporting loses a current read.
- Do not begin C until A and B are locally committed and their focused verification is green.
- Stop C if a claimed plot requires a persisted field that is absent or ambiguous; render an explicit unavailable reason or omit that claim rather than infer or change the schema.
- Stop C if exact-cohort/state-then-scene aggregation cannot be preserved from current rows; repair the presentation-free reducer or defer the plot rather than aggregate in Streamlit.
- Do not broaden C into page-framing, navigation, workflow-state redesign, reward/reconstruction changes, or wholesale PR #38 replay.

## Draft GitHub issue A

### Title

`refactor(app): deepen the stored-rollout session and cache invalidation seam`

### Body

#### Summary

Extract one panel-local `StoredRolloutSession` as a fixed-identity, single-rerun **core snapshot** handle over module-private Streamlit caches. It owns the selected store's path/identity boundary and owner-level invalidation without claiming topology/report snapshotting, transitive immutability, or changing science, persistence, lazy reads, or UI design.

#### Problem

`_stored_rollouts_page.py` currently owns the replacement-sensitive reader bundle (`:177-198`), a wide string-selected projection dispatcher (`:221-325`), store identity (`:328-354`), topology/failure/report caches, and a manually maintained clear list (`:377-479`). Candidate population is separately cached (`:211-218`) but absent from that clear list. Current wrappers recompute identity before each cached operation, so lifecycle and cache policy remain coupled to rendering.

#### Required change

- Add `_stored_rollout_session.py`. `open_stored_rollout_session` canonicalizes the path, computes identity once, binds the core, and returns a fixed-identity handle for one render/rerun. The handle is not cached as a resource and is not described as transitively immutable.
- Keep all `@st.cache_*` functions module-private in `_stored_rollout_session.py`. Reader/core-bound caches use canonical path + captured identity; topology/report caches reopen the path and use a fresh invocation identity. Preserve reader/core as `st.cache_resource(show_spinner=False)` with `max_entries` unset and topology as `st.cache_resource(max_entries=16)`. Inventory, serializable projections, candidate data, failures, and evidence retain their existing bounded `st.cache_data` limits.
- Accept cache-stable arguments/values. Retain the existing structured topology inputs—`PathConfig`, the VIN-directory tuple, and selected source row—without flattening or redesign solely for caching.
- Expose only named operations demanded by current render call sites. Migrate `_stored_rollouts_page.py` to one opened handle; delete the string dispatcher and superseded page-local helpers without aliases.
- Observe same-path replacement on the next open/refresh/rerun for reader/core-bound work. Topology and evidence/report bundle must compute/check identity at their own invocation and observe replacement on the next call; do not claim they share the captured core generation.
- Make invalidation an owner-level global clear over the complete matrix below; do not claim per-instance eviction. Clear must be followed by rerun before reusing a prior handle.
- Keep `inventory_row` presentation-only. It is excluded from identity/core trust/domain facets; inventory remains cache-root keyed and exempt from path+identity keys.
- If characterization selects the functional fallback, implement it in this same `_stored_rollout_session.py` owner; do not create `_stored_rollout_cache.py`.
- Preserve the exact matrix bounds, dynamic-tab gating, explicit heavy-read controls, query/Rerun/download behavior, and current rendering.
- Use two tests-first checkpoints. First record green characterization tests against existing `_stored_rollouts_page.py` owners. Then add session-contract tests before migration/removal; preferably make them green with the smallest non-migrating scaffold. An intentional red checkpoint is allowed only with exact expected failures recorded and must be made green before page-owner migration.

#### Cache migration matrix

| Owner | Kind / bound | Keys | Trigger |
|---|---|---|---|
| core | resource / unset (`show_spinner=False`) | path + captured identity; no inventory row | session open; reader/core-bound |
| inventory | data / 8 | cache root only; identity exempt | presentation discovery |
| demand-backed projections | data / 128 | path + captured identity + operation-specific cache-stable arguments/values | visible section/control; reader-bound |
| candidate population | data / 128 | path + captured identity + sample size | explicit candidate evidence; reader-bound |
| topology | resource / 16 | path + fresh invocation identity + existing `PathConfig`, VIN dirs tuple, selected row | path-reopening topology call; structured values retained |
| failures | data / 32 | path + captured identity + thresholds | Failure Triage; reader-bound |
| evidence bundle | data / 16 | path + fresh invocation identity + evidence status | path-reopening requested export |

#### Acceptance criteria

- A0.1 is green against existing page owners before a session scaffold or migration. A0.2 records the session-contract result before migration, preferably green via the smallest scaffold; any intentional red result names exact expected failures and is made green before page-owner removal.
- One open computes identity once for reader/core-bound operations.
- Mid-handle replacement does not mix the bound reader/core, projections, candidate population, or failures. The next open obtains a new core identity.
- Topology and evidence/report operations compute/check identity at invocation; after mid-handle replacement, their next call observes the replacement. No universal within-handle snapshot claim.
- Identity performs zero payload `read_bytes()` calls.
- Reader/core, projections, candidate population, and failures update after next-open replacement detection; topology and evidence bundle update after their next invocation.
- One owner-level invalidation call clears every matrix cache exactly once, including inventory and candidate population; no per-key/per-instance claim.
- Core is `st.cache_resource(show_spinner=False)` with `max_entries` unset; topology is `st.cache_resource(max_entries=16)`; every serializable matrix value uses bounded `st.cache_data` with its unchanged listed limit.
- Topology preserves `PathConfig`, the VIN-directory tuple, and selected source row as structured cache-stable arguments/values.
- Default/lightweight workspaces call candidate audit/population, root geometry, tree, deep Q_H, and compact statistics exactly zero times.
- Explicit candidate grouping materializes candidates at most once and reuses the rows.
- A search limited to the three stored-rollout session/page entry files shows reader construction, cache decorators, identity, and clear ownership only in the session module, with every hit classified.
- Class façade or functional fallback both remain inside `_stored_rollout_session.py`; owner-search expectations are identical.
- Different `inventory_row` values leave identity/core trust unchanged; inventory is cache-root keyed only.
- The handle exposes only operations used by current call sites; no generic dispatcher and no mechanical public method for every historical branch.
- No compatibility aliases, generic projection registry, domain/persistence changes, or visual redesign.
- Focused panel/laziness tests, Ruff format/check, owner search, and `git diff --check` pass.

#### Exclusions

No changes to rollout projections, Zarr schema/writer/promotion, scientific metrics, Rerun behavior, CLI/report contracts, figures, page layout, labels, or shared workflow state.

#### Verification

Use these ordered checkpoints before migration:

```bash
cd aria_nbv
uv run pytest \
  tests/app/panels/test_stored_rollouts_projection_laziness.py \
  tests/app/panels/test_counterfactual_rollouts_panel.py -q
uv run pytest \
  tests/app/panels/test_stored_rollouts_projection_laziness.py \
  -q -k stored_rollout_session
```

The first command must be green against existing owners. Record the second as green via the preferred minimal scaffold, or record exact intentional-red failures and then its pre-migration green rerun. Add concrete coverage in:

- `aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py`: current-owner characterization; identity-once spy; reader/core-bound mid-handle replacement; topology/report next-invocation replacement; inventory-row exclusion; candidate-population clear ownership; complete cache-clear spy; exact decorator settings including core unset/topology 16; structured topology-argument preservation.
- `aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py`: default/lightweight zero-heavy/statistics calls; one selected session owner; unchanged UI/query/Rerun/download behavior.

Then run the PR A commands in this plan and attach exact test counts plus every classified owner-search hit.

## Draft GitHub issue B

### Title

`refactor(rollouts): reuse typed inspection results across Streamlit, CLI, and exports`

### Body

#### Dependency

**Blocked by Issue A: “refactor(app): deepen the stored-rollout session and cache invalidation seam.”** Create/link Issue A first and do not start this issue until A is merged and green.

#### Summary

Add named, presentation-free typed inspection facets at the existing demand points used by the Streamlit session, `nbv-rollouts-info`, and deterministic thesis-report export. Reuse facts without forcing the consumers to share validation, promotion, or statistics depth.

#### Problem

The consumers intentionally do different work. Default CLI is manifest-only, validation/statistics are flag-dependent, and ordinary CLI never runs promotion checks (`info_cli.py:112-168`; `test_info_cli.py:23-75`). Streamlit trust validates and checks promotion but its header does not compute compact statistics (`_stored_rollouts_page.py:177-191`, `:712-751`). Reporting validates, checks promotion, computes statistics, then performs report-specific projections (`reporting.py:567-635`). One union DTO would add reads or change semantics.

#### Required change

- Add separate frozen, slots-based named facets/builders in `aria_nbv.rollouts.inspection` or one narrow sibling module for manifest facts, schema validation, promotion evidence, effective Streamlit trust composition, and compact statistics.
- Builders may reuse supplied reader/manifest prerequisites but must not eagerly construct other facets.
- Compose Streamlit effective trust by copying ordered schema errors, appending promotion error last, and setting `ok` false when either fails; preserve its current blocked-rendering behavior without mutating a CLI validation facet.
- Have the Issue-A session cache only Streamlit's currently demanded facets; have CLI select facets strictly from flags; have reporting preserve validation-first then distinct promotion `ValueError` before existing projections.
- Preserve ordinary CLI promotion semantics: default/validate/stats/preflight perform zero promotion checks.
- Exclude `inventory_row` from every facet and builder.
- Keep Streamlit/Rich/plain-text/report conversion in their existing renderer/adapter owners.
- Delete superseded duplicate assembly; do not add aliases, a union DTO, or a generic projection framework.

#### Acceptance criteria

- Named manifest, validation, promotion, effective Streamlit trust, and statistics facets/composition have coherent demand boundaries; no universal result is required.
- Call counts are exact: default CLI `1/0/0/0`; `--validate` `1/1/0/0`; `--stats` `1/0/0/1`; `--preflight` `1/1/0/1` for manifest/validation/promotion/statistics.
- Streamlit lightweight trust/header performs `1/1/1/0`; reporting performs `1/1/1/1` per store before unchanged report-specific reads.
- Promotion failure appears last in Streamlit effective trust errors and blocks scientific rendering; reporting raises the same promotion-validation error as today.
- CLI JSON/text values, validation/stats/preflight behavior, exit codes, and thesis-bundle metadata remain unchanged.
- Report table names/columns and serialized bytes remain deterministic and unchanged for fixed fixtures.
- Existing CLI/report statistics parity remains green and adopting consumers have facet-value parity.
- Default CLI remains manifest-only; Streamlit lightweight trust performs zero `rollout_statistics`; ordinary CLI performs zero promotion checks.
- `rich_summary.py` remains free of rollout imports, rollout DTOs, identity logic, and rollout-semantic branches.
- No new CLI command, export format, compatibility alias, generic projection layer, or visual redesign.

#### Exclusions

Do not type every inspection row, introduce a union trust/statistics DTO, change projection or promotion semantics, alter Zarr persistence, redesign the UI, add speculative CLI/export surfaces, or move domain truth into `rich_summary.py`/`cli_format.py`.

#### Verification

Add and run concrete coverage in:

- `aria_nbv/tests/rollouts/test_inspection.py`: unit tests for manifest, validation, promotion, effective-trust composition/error ordering, and statistics facets; inventory is rejected/absent.
- `aria_nbv/tests/rollouts/test_info_cli.py`: spies for default, `--validate`, `--stats`, and `--preflight` call counts; all ordinary modes assert zero promotion calls and unchanged outputs/exits.
- `aria_nbv/tests/rollouts/test_reporting.py`: valid-store `1/1/1/1` facet counts, validation-first failure, promotion-validation `ValueError`, unchanged report-specific calls, schemas, and serialized bytes.
- `aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py`: Streamlit `1/1/1/0` spy and promotion-error-last blocked trust behavior.

Then run the PR B commands in this plan and attach all six mode-count rows, CLI parity, promotion failure/report error evidence, exact report-byte parity, and unchanged read-depth evidence.

## Draft GitHub issue C

### Title

`feat(inspector): restore normalized candidate-support plots`

### Body

#### Dependency

Blocked by the verified session/cache seam and typed inspection-facet work. Do not implement against the old page-local cache dispatcher.

#### Summary

Restore the scientifically important candidate-support projections and plot forms lost during the partial PR #38 salvage, using current `aria_nbv.rollouts.inspection` ownership and the stored-rollout session seam. This is read-only inspection, not generation or policy evaluation.

#### Required change

- Add current-schema presentation-free evidence for target-normalized geometry, equal-area direction density, spherical/angular coverage, spatial shell, target-view availability, motion/path support, and explicitly evaluated collision/clearance.
- Normalize planar geometry so root=`(0,0)` and target=`(1,0)` in a right-handed frame; reject missing or degenerate target baselines.
- Bin direction in azimuth × `sin(elevation)` and preserve complete bins plus state-then-scene-then-cohort macro denominators.
- Materialize candidate audit once per requested store/cohort and reuse it for all restored reducers.
- Render plot-first views after the existing explicit candidate-evidence dispatch; place exact rows/downloads collapsed beneath their corresponding plots.
- Reuse the existing scientific explanation, Plotly/render, session/cache, and download owners.
- Keep incompatible cohorts separate and retain explicit unavailable/not-applicable/evaluated reasons.

#### Acceptance criteria

- Exact normalized-coordinate, missing-baseline, equal-area-bin, per-state-sum, uneven-fanout, scene-macro, and missingness regressions pass.
- Root/target anchors and equal axes are visible; rays never connect unrelated candidates; heatmap axes are azimuth and `sin(elevation)`.
- Aggregate values use all admitted rows and are invariant to display-point limits.
- Candidate support remains separate from reward/reconstruction evidence and is not described as a causal or planning result.
- Default page load reads zero candidate audit; explicit dispatch reads it once and reuses it.
- No schema, generation, training, Q_H, CLI/report, Rerun, dependency, alias, or generic-framework change.
- Focused tests, Ruff, compileall, and diff/scope checks pass.

#### Verification

Use the PR C commands and evidence checklist in this PRD. Attach exact reducer fixtures, UI laziness/materialization counts, figure-contract assertions, and the changed-path audit.

## Available agent types and future staffing

### Available-agent-types roster

`explore`, `analyst`, `planner`, `architect`, `debugger`, `executor`, `team-executor`, `verifier`, `code-reviewer`, `dependency-expert`, `test-engineer`, `designer`, `writer`, `git-master`, `code-simplifier`, `researcher`, `prometheus-strict-metis`, `prometheus-strict-momus`, `prometheus-strict-oracle`, `critic`, `scholastic`, `vision`.

### Recommended receipt-authorized path

- **Default: `$ultragoal`**, with three sequential implementation goals: A then B then C, followed by the mandatory final quality gate. B depends on A; C depends on both verified seams.
- **A staffing:** one `test-engineer` (medium) owns the ordered A0.1 green characterization and A0.2 session-contract records; one `executor` (medium) owns the smallest non-migrating scaffold and later session/page migration only after those checkpoints; one `verifier` (high) independently checks identity, laziness, cache kinds/bounds, structured topology arguments, ownership, and changed paths; one `code-reviewer` (high) reviews the final diff.
- **B staffing:** one `executor` (medium) owns the named domain facets and demand-aligned consumer adoption; one `test-engineer` (medium) owns mode counts/parity/byte-stability tests; one `verifier` (high) checks all consumer modes and exclusions.
- **C staffing:** one `executor` owns current-schema domain reducers and session integration; one `test-engineer` owns denominator/invariance/laziness and figure-contract tests; one `designer` or `vision` may verify that the intended plots are visible and interpretable without changing navigation or style.
- `architect` (xhigh) is useful if implementation evidence shows facet boundaries cannot preserve current demand depths or historical reducer semantics conflict with current persisted rows. `researcher` and `dependency-expert` remain unnecessary because C restores repo-owned scientific contracts and adds no dependency.

### Team option and launch hints

Team is optional, not the default for A, because behavior-lock tests must precede the intertwined page/session migration. If used after an official host receipt:

```text
$ultragoal .omx/plans/prd-stored-rollout-session-cache-seam.md
omx team 2:team-executor "Implement Issue A from .omx/plans/prd-stored-rollout-session-cache-seam.md: lane 1 owns behavior-lock tests; after that checkpoint, lane 2 owns _stored_rollout_session.py and page migration. Preserve all exclusions."
```

For B, Team may use two ownership-disjoint lanes after A: domain-facet implementation and consumer/mode-parity tests. For C, reducer/test work may proceed before presentation only when shared-file ownership is explicit; UI adoption begins after reducer fixtures are green. Ultragoal remains the leader-owned sequential ledger and checkpoints each prerequisite before the next story begins.

### Team verification path

1. Test lane records green A0.1 characterization against existing page owners.
2. Test and implementation lanes record A0.2 before migration: preferably green via the smallest scaffold; any intentional red result includes exact expected failures and is followed by a green scaffold result.
3. Implementation lane starts page-owner migration only after A0.2 is understood, then records changed paths and focused command output.
4. Verifier reruns the full phase suite from a clean integration state, executes the cache-owner search, asserts the matrix cache kinds/bounds and structured topology inputs, and checks `git diff --check`.
5. Ultragoal checkpoints A only after verifier evidence; B remains blocked until that checkpoint. It checkpoints B before C begins.
6. C verification proves current reducer semantics, plot visibility, and unchanged lazy/cache behavior before the final gate.
7. Team shuts down only after no task remains pending and exact evidence is attached to the corresponding goal.

### Goal-mode follow-up suggestions

- `$ultragoal` is the recommended durable implementation path.
- `$team` may accompany `$ultragoal` only with the serial test-freeze dependency and explicit file ownership above.
- `$ralph` is a fallback only if the user explicitly wants one persistent single-owner implement/verify loop; it is not the default.
- `$autoresearch-goal` is not appropriate: this is an implementation refactor with frozen behavior, not a research deliverable.
- `$performance-goal` is not appropriate unless a later issue adds a measured latency/memory target beyond the current cache-call and read-count criteria.

## Planning lifecycle placeholder

```yaml
planning_artifacts:
  - .omx/context/stored-rollout-session-cache-seam-20260821T101909Z.md
  - .omx/plans/prd-stored-rollout-session-cache-seam.md
planner_stage: complete
planner_iteration: 6
ralplan_architect_iteration_1:
  status: iterate_applied
  artifact: .omx/plans/ralplan-architect-review-stored-rollout-session-cache-seam.md
ralplan_architect_iteration_2:
  status: approve
  artifact: .omx/plans/ralplan-architect-review-stored-rollout-session-cache-seam-iteration-2.md
ralplan_critic_iteration_1:
  status: iterate_received_and_applied
  artifact: .omx/plans/ralplan-critic-review-stored-rollout-session-cache-seam.md
ralplan_architect_iteration_3:
  status: approve
  artifact: .omx/plans/ralplan-architect-review-stored-rollout-session-cache-seam-iteration-3.md
ralplan_critic_iteration_2:
  status: iterate_received_and_applied
  artifact: .omx/plans/ralplan-critic-review-stored-rollout-session-cache-seam-iteration-2.md
ralplan_architect_iteration_4:
  status: iterate_received_and_applied
  artifact: .omx/plans/ralplan-architect-review-stored-rollout-session-cache-seam-iteration-4.md
ralplan_architect_iteration_5:
  status: approve
  artifact: .omx/plans/ralplan-architect-review-stored-rollout-session-cache-seam-iteration-5.md
ralplan_critic_iteration_3:
  status: approve
  artifact: .omx/plans/ralplan-critic-review-stored-rollout-session-cache-seam-approved.md
ralplan_consensus_gate:
  complete: true
  completion_reason: explicit current-thread user authorization to revise and execute this approved plan through Ultragoal
official_host_consensus_receipt: current_user_ultragoal_handoff_2026-08-21
execution_authorized: true
execution_scope:
  - Issue A stored-rollout session/cache seam
  - Issue B typed inspection facets
  - Scientific restoration C for evidence-backed lost candidate-support plots
```

The local Planner -> Architect -> Critic lifecycle was approved for A and B.
The current user explicitly revised the scope to include the evidence-backed C
restoration and authorized execution through Ultragoal. That current-thread
instruction closes the former planning-only stop; it does not authorize a push,
new GitHub issue, pull request, or other external publication action.

## Planning lifecycle changelog

### Iteration 6 — plot-loss audit integrated and execution authorized

- Refreshed the implementation worktree to `origin/main`
  `3a6ff491fadb19c20af3d876ae4734e138804ee9` while preserving the untracked
  context and PRD artifacts.
- Reconfirmed Graphify as unusable after worktree bootstrap repair because the
  projection-owner worktree status remained unavailable; used exact current and
  historical Git objects instead.
- Added sequential scientific restoration C after A and B. C restores
  target-normalized geometry, equal-area direction density, spherical/angular
  coverage, spatial shell, target-view, motion/path, and collision/clearance
  evidence through current domain/session/presentation owners.
- Added tests-first denominator, invariance, missingness, laziness, figure,
  scope, and verification gates. Historical PR #38 remains evidence, not an
  architecture to replay.
- Recorded the current user's explicit Ultragoal implementation authorization.
  No external GitHub publication was authorized by this revision.

### Publication refresh and issue creation

- Refreshed the planning branch to `origin/main`
  `8d46b4a73ae0a537bcee26979cf485231b5d30d7` before publication. The only
  post-planning changes in the relevant scope added `aria_nbv/aria_nbv/app/AGENTS.md`
  and `aria_nbv/aria_nbv/app/README.md`; no cited cache, rollout-domain, CLI,
  report, or focused-test owner changed.
- Published Issue A:
  https://github.com/JanDuchscherer104/ARIA-NBV/issues/93
- Published Issue B, explicitly blocked by Issue A:
  https://github.com/JanDuchscherer104/ARIA-NBV/issues/94
- No implementation or pull request was started.

### Final review — Architect and Critic `APPROVE`

- Architect iteration 5 verified exact cache kinds and bounds plus all prior
  snapshot, trust, inventory, tests-first, alternatives, and issue-separation
  amendments.
- Critic iteration 3 approved clarity, verifiability, completeness,
  principle-option consistency, alternatives depth, risk coverage, and both
  self-contained issue drafts with no required final amendment.
- The consensus gate remains `complete: false` solely because the documented
  official host consensus receipt surface is unavailable; no implementation
  handoff is implied.

### Iteration 5 — Architect iteration-4 `ITERATE` applied

- Restored the exact current reader/core policy everywhere: `st.cache_resource(show_spinner=False)` with `max_entries` unset.
- Retained topology as `st.cache_resource(max_entries=16)` and retained every existing bounded `st.cache_data` limit unchanged.
- Removed the proposed 16-entry core capacity policy from requirements, both matrices, ADR, implementation, acceptance criteria, risks, verification, and Issue A. Any reader-capacity change is deferred to a separately measured follow-up.
- Advanced the lifecycle to Planner iteration 5, with Architect iteration 4 recorded as applied and iteration-5 Architect then Critic re-reviews pending. No other design changed and no product or test file was edited.

### Iteration 4 — Critic iteration-2 `ITERATE` applied

- Reconciled the cache-kind categories for reader/core, topology, and serializable data owners; iteration 5 corrected the core capacity detail back to its exact current unset/default bound.
- Split A0 into a green characterization checkpoint against existing page owners and a pre-migration session-contract checkpoint. Preferred sequence makes the second checkpoint green with the smallest non-migrating scaffold; intentional red is allowed only with exact expected-failure evidence and must be made green before page-owner removal.
- Replaced primitive-only cache-key language with cache-stable arguments/values and explicitly retained `PathConfig`, the VIN-directory tuple, and selected source row without redesign.
- Updated requirements, cache matrix, ADR, implementation sequence, Issue A body, acceptance criteria, risks, verification evidence, and lifecycle state. No product or test file was edited.

### Iteration 3 — Critic `ITERATE` applied

- Narrowed snapshot consistency to reader/core-bound operations; topology and evidence/report bundles now compute/check identity at invocation and detect replacement on their next call.
- Added explicit mid-handle replacement tests for both bound-reader and path-reopening owners and removed unsupported universal snapshot claims.
- Required both the class façade and functional fallback to live in `_stored_rollout_session.py`, keeping owner-search criteria independent of internal shape.
- Defined validation + promotion -> effective Streamlit trust composition, including ordered appended promotion errors and blocked rendering, while preserving reporting's distinct promotion error and ordinary CLI's zero-promotion behavior.
- Made `inventory_row` presentation-only, excluded it from identity/domain trust/facets, and explicitly exempted cache-root-keyed inventory from path+identity keys.
- Added concrete test filenames and spy responsibilities to both GitHub issue bodies.
- Updated the ADR, requirements, cache matrix, risks, acceptance criteria, verification, issue drafts, staffing language, and lifecycle state.

### Iteration 2 — Architect `ITERATE` applied

- Reframed Issue A from a transitively immutable session to a fixed-identity, single-rerun core snapshot handle with next-open reader/core replacement detection.
- Made Streamlit decorators module-private, centralized replacement-sensitive keys, and defined owner-level global clear semantics; iteration 3 later distinguished captured core keys from fresh path-reopening keys.
- Added candidate population to invalidation ownership and added the static seven-owner cache migration matrix.
- Limited the session façade to demand-backed named operations and strengthened the viable functional named-module alternative.
- Replaced Issue B's union DTO with named manifest/validation/promotion/statistics facets.
- Locked default CLI, flagged CLI, Streamlit trust, and reporting read depths plus promotion semantics with mode-specific call-count tests.
- Narrowed cache-owner search verification to the three stored-rollout session/page entry files and required classification of every hit.
- Updated the ADR, risks, acceptance criteria, verification, stop rules, both draft issue bodies, staffing guidance, and lifecycle state.
