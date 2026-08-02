---
id: 2026-08-01_domain_skill_distillation
date: 2026-08-01
title: "Domain Skill Distillation"
status: done
topics: [scaffold, skills, progressive-disclosure, ownership]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/skills/
  - .agents/references/source_order.md
  - scripts/scaffold_audit.py
  - scripts/scaffold/fixtures/routing.json
  - scripts/tests/test_agent_governance_g002.py
  - aria_nbv/aria_nbv/rollouts/
  - aria_nbv/aria_nbv/rerun_inspector/
---

# Task

Implement the approved domain-skill distillation handoff from a frozen, clean
worktree. Remove skill-owned scientific and implementation truth while
preserving predictable autonomous routing, procedural branches, verification,
and rollback boundaries.

# Method

- Froze the approved PRD, test specification, handoff, context, and approving
  reviews at baseline `d1bfef7d904626bdd1e196377c34c99eefc516fa` on
  `codex/domain-skill-distillation`.
- Passed the clean-baseline gate before edits: scaffold audit, scaffold audit
  self-test, and agent-memory validation all exited zero.
- Compared each identity against a route-only fallback and the four planned
  adjacent mergers. No merger or prune established stronger autonomous reach,
  narrower owner load, and equivalent completion criteria. Under the approved
  retain-on-inconclusive rule, all nine identifiers remain separate.
- Converted those nine skills to the temporary native-minimal schema, moved the
  Rerun inspector contract to package owners, and deleted superseded skill-local
  references.
- Committed the bridge and owner migration separately, then committed each
  skill together with its `NATIVE_MINIMAL_SKILLS` opt-in so every conversion has
  an independent rollback boundary.
- Ran fresh read-only Codex probes with ignored user configuration and structured
  JSON output. JSONL command events confirmed the reported skill paths were
  opened inside the isolated worktree.
- Closed independent-review findings by resolving Markdown owners relative to
  each skill directory and rejecting every native-minimal frontmatter key except
  `name` and `description`.

# Invocation dispositions

| Skill | Disposition | Leading procedure | Reason separate identity remains |
| --- | --- | --- | --- |
| `code-review-aria-nbv` | retained | review | Diff findings can complete without entering a causal reproducer. |
| `diagnose-aria` | retained | diagnose | Symptom work requires a red loop and cause evidence. |
| `counterfactual-rollout-planner` | retained | plan | Finite-horizon comparison loads rollout and experiment owners. |
| `entity-aware-rri` | retained | validate target evidence | Target-label evidence precedes, but does not imply, rollout evaluation. |
| `dataset-cache-ops` | retained | operate | Existing-store operation is distinct from storage implementation. |
| `zarr-python` | retained | round trip | API/layout/codec changes require current upstream evidence and a writer-reader proof. |
| `nbv-geometry-contracts` | retained | verify geometry | Semantic frame evidence must remain separate from observer presentation. |
| `rerun-nbv-inspector` | retained | inspect | Rerun is an observer-artifact procedure with offline and rollout branches. |
| `docs-curator` | retained | curate | Quarto/navigation/public-boundary work hands Typst authoring to its existing skill. |

The review/diagnosis, target-RRI/rollout, dataset/Zarr, and geometry/Rerun merger
candidates remained inconclusive or weaker because they combined different first
owners and completion criteria. Route-only candidates likewise did not prove an
equivalent autonomous procedure after removal. No compatibility aliases were
added.

# Claim-level ownership dispositions

Line references below identify the frozen `d1bfef7d` baseline. A row may group
adjacent sentences only when they share one claim type, owner, and proof.

| Baseline skill/reference lines | Removed or rewritten claim | Type and disposition | Exact live owner and proof |
| --- | --- | --- | --- |
| `code-review-aria-nbv/SKILL.md:60-94` | Generic review harness and GitHub publication/thread mechanics | procedure; replaced | `AGENTS.md#routing` plus `.agents/skills/agent-behavior/references/external-actions.md#external-boundary`; final skill retains only ARIA diff grounding and handoff |
| `code-review-aria-nbv/SKILL.md:124-140` | Finding order, severity, evidence, and residual-risk rules | procedure; derived | final `code-review-aria-nbv/SKILL.md` steps 2-3 and root review routing; positive diff-review probe selected this skill and opened root `AGENTS.md` |
| `diagnose-aria/SKILL.md:64-69` | Exhaustive list of ARIA failure domains | routing; stale duplication removed | root `AGENTS.md#routing` and nearest package guides; positive diagnostic probe selected `diagnose-aria` without the catalogue |
| `diagnose-aria/SKILL.md:71-108` | Streamlit, store, docs, and package command catalogue | executable usage; already owned | root `Makefile`, `aria_nbv/pyproject.toml` entry points, and nearest `AGENTS.md#verification`; `make ci` and focused owner tests exercise those command owners |
| `diagnose-aria/SKILL.md:118-146` | Reproduce/minimize/hypothesize/probe/regress/cleanup sequence | procedure; derived | final `diagnose-aria/SKILL.md` steps 1-3; diagnostic and review near-miss probes preserved distinct completion criteria |
| `docs-curator/SKILL.md:67-81` | Public/internal boundary, QMD taxonomy, bibliography location, and archive placement | routing and docs policy; already owned | `docs/AGENTS.md#priorities`, `#default-workflow`, and `#writing-rules`; `make ci` rendered the 33-page core docs surface |
| `docs-curator/SKILL.md:85-90` | Quarto, Typst, outline, taxonomy, and memory command inventory | executable usage; replaced | `docs/AGENTS.md#commands`, `typst-authoring`, and root Make targets; Typst near-miss selected `typst-authoring`, not `docs-curator` |
| `counterfactual-rollout-planner/SKILL.md:67-71,81-86` | Rollout/Q_H scope, milestone gates, and research-question placement | scientific direction; already owned | `docs/typst/thesis/sections/04-method/04-03-candidate-and-replay-contract.typ`, `04-05-finite-candidate-value-model.typ`, and `05-experimental-design/05-03-policy-comparison-and-failure-interpretation.typ`; thesis files exist and are included by the active seed |
| `counterfactual-rollout-planner/SKILL.md:90-114` | Branch/beam semantics, sampling, modality materialization, masks, trace fields, and comparison budgets | executable or scientific; already owned | `aria_nbv/aria_nbv/rollouts/AGENTS.md#boundary-rules`, `rollouts/replay/`, `trace.py`, `zarr_store.py::{write_rollout_zarr_store,validate_rollout_zarr_store}`, and rollout tests; `make ci` passed 266 package-smoke tests |
| `entity-aware-rri/SKILL.md:68-82` | Target-selection, GT-label, V0/V1, and thesis-scope meaning | scientific direction; already owned | `docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ` and `04-method/04-03-candidate-and-replay-contract.typ` |
| `entity-aware-rri/SKILL.md:88-95` | Actor/oracle/evaluation separation, invalid-target treatment, and scene-versus-target reporting | executable/scientific; already owned | `aria_nbv/aria_nbv/rri_metrics/AGENTS.md#boundary-rules`, `rri_metrics/returns.py`, target protocol/source code, and focused RRI/data tests; entity positive and scene-RRI near-miss probes selected different owners |
| `dataset-cache-ops/SKILL.md:91-102` | Current dataset classes, writer, statistics helper, and strict store checks | executable; already owned | `data_handling/AGENTS.md#public-contracts`, `vin_store/dataset.py::VinOfflineDataset`, `store.py::{OFFLINE_DATASET_VERSION,VinOfflineStoreReader,VinOfflineShardWriter}`, and `diagnostics.py::collect_vin_offline_dataset_stats` |
| `dataset-cache-ops/SKILL.md:109-137` | Legacy rejection, rebuild/migration mechanics, atomic metadata edits, and cleanup rules | executable/hazard; already owned | `data_handling/AGENTS.md#boundary-rules`, `vin_store/{format.py,store.py,writer.py}`, and `tests/data_handling/test_vin_offline_store.py`; dataset routing probe opened the data-handling guide and retained rebuild/no-change disposition |
| `dataset-cache-ops/SKILL.md:142-146` | Downloader, summary, pytest, and grep catalogue | executable usage; already owned | CLI help/entry points, root Make targets, and `data_handling/AGENTS.md#verification`; final skill invokes owner-provided commands without copying options |
| `nbv-geometry-contracts/SKILL.md:89-95` | Frame/transform/camera ownership and display-only isolation | executable/scientific; already owned | `aria_nbv/AGENTS.md#core-rules`, typed pose/rendering/data-view docstrings and tests, and `docs/typst/thesis/sections/03-oracle-and-data-generation/03-01-state-and-visibility.typ` |
| `nbv-geometry-contracts/SKILL.md:108-116` | Pose, camera, depth, frustum, and Streamlit assertion matrix | executable; already owned | focused modules under `pose_generation/`, `rendering/unproject.py`, and `tests/rendering/{test_depth_backprojection_conventions.py,test_candidate_renderer_integration.py}`; geometry and display-only near-miss probes preserved the semantic/observer split |
| `rerun-nbv-inspector/SKILL.md:64-98` | Fixed upstream-query workflow and copied smoke command | procedure; partly derived, partly stale | final skill keeps conditional official-doc lookup; current invocation lives in `aria_nbv/aria_nbv/rerun_inspector/README.md#recording-and-verification` and CLI help |
| `rerun-nbv-inspector/SKILL.md:102-122` | Read-only behavior, scene basis, poses, camera/depth layout, candidate handling, entity cardinality, blueprints, and downsampling | executable/hazard; moved | `rerun_inspector/README.md#inputs-and-ownership` and `#display-contracts`, `_loggers.py::RerunOfflineLogger`, `_rollout_zarr.py::RerunRolloutZarrLogger`, and focused tests; 67 Rerun/offline-inventory tests passed |
| `rerun-nbv-inspector/SKILL.md:126-138` | Config, preflight ordering, candidate-prefix/all-invalid, resolution, depth, and artifact assertions | executable; moved | `_config.py::RerunOfflineInspectorConfig`, `_cli.py::RerunOfflineInspector`, `_session.py`, Rerun README, and `tests/rerun_inspector/{test_rerun_cli.py,test_frusta.py,test_loggers.py}` |
| `rerun-nbv-inspector/references/nbv-inspector-contract.md:11-19` | Inspector purpose and non-mutation boundary | subsystem orientation; moved | `rerun_inspector/README.md` opening and `_rollout_zarr.py::RerunRolloutZarrLogger` docstring |
| `rerun-nbv-inspector/references/nbv-inspector-contract.md:21-34` | Required offline sample inventory | executable; moved | `_metadata.py`, `_sample.py`, `data_handling/_offline_visual_inventory.py`, and `tests/data_handling/test_offline_visual_inventory.py` |
| `rerun-nbv-inspector/references/nbv-inspector-contract.md:36-45` | Candidate prefix, padding, validity, and empty/all-invalid behavior | executable; moved | Rerun README `#display-contracts`, logger/frusta code, and candidate/all-invalid focused tests |
| `rerun-nbv-inspector/references/nbv-inspector-contract.md:47-55` | Pose, camera, CW90, downsampling, mesh, and OBB display meaning | executable/scientific; moved to exact owners | Rerun README plus geometry code/tests and active state/visibility Typst section; the Rerun skill now hands semantic uncertainty to `nbv-geometry-contracts` |
| `rerun-nbv-inspector/references/nbv-inspector-contract.md:57-76` | CLI modes, smoke command, and incompatible-store behavior | executable usage; moved | `_cli.py`, `_session.py`, CLI help, Rerun README `#recording-and-verification`, and CLI/preflight tests |
| `rerun-nbv-inspector/references/nbv-inspector-contract.md:78-85` | Preferred test seams | verification routing; moved | Rerun README `#recording-and-verification` links the exact fake-Rerun, CLI, frusta, and rollout tests |
| `rerun-nbv-inspector/references/rerun-python-patterns.md:6-13` | Recording/sink lifecycle and artifact location | executable; moved | `_session.py`, `_cli.py`, Rerun README, and `test_loggers.py`/`test_rerun_cli.py` |
| `rerun-nbv-inspector/references/rerun-python-patterns.md:15-41` | Fixed entity-tree catalogue | executable presentation; stale catalogue removed | existing logger/entity code under `rerun_inspector/`; no fixed entity tree is retained outside code/tests |
| `rerun-nbv-inspector/references/rerun-python-patterns.md:43-67` | Coordinate, camera, RGB, and depth API facts | executable; moved to code/tests or conditional upstream evidence | `_geometry.py`, `_layers.py`, `_loggers.py`, geometry owners/tests, and official Rerun docs only when an SDK change requires them |
| `rerun-nbv-inspector/references/rerun-python-patterns.md:69-86` | Candidate layer, invalidity, labels, and blueprint rules | executable/hazard; moved | Rerun README `#display-contracts`, `_blueprint.py`, logger tests, and package-owned target/invalidity contracts |
| `rerun-nbv-inspector/references/context7-queries.md:1-58` | Hard-coded Context7 query inventory and local signature script | external reference; stale catalogue removed | final skill conditionally requests current official Rerun docs; installed signatures and official docs are evidence at use time, not repo truth |
| `rerun-nbv-inspector/references/official-examples-map.md:1-69` | Version-drifting Rerun example URL/use-case map | external reference; stale catalogue removed | current official Rerun examples are consulted conditionally; no durable repo owner is asserted |
| `zarr-python/SKILL.md:66-79` | Zarr API/layout branch catalogue and fixed read-first list | activation/procedure; derived | final `zarr-python/SKILL.md` description and steps 1-2; positive Zarr and dataset near-miss probes preserve the branch boundary |
| `zarr-python/SKILL.md:83-94` | Dependency, store ownership, helper names, mutation rules, and upstream API facts | executable; already owned | `aria_nbv/pyproject.toml`, data-handling and rollout `AGENTS.md`/README files, `vin_store/{store.py,writer.py}`, `rollouts/zarr_store.py`, and current official Zarr docs when required |
| `zarr-python/SKILL.md:108-111` | Guidance, offline, rollout, and CLI command catalogue | executable usage; already owned | root Make targets, nearest package verification sections, test files, and CLI help; final skill keeps only the round-trip completion criterion |

No removed fact points to another skill as its authority. The remaining direct
array reads in `rerun_inspector._rollout_zarr` for branch selection and Q_H
metadata summaries are explicitly open; this change does not claim a complete
read-model migration.

# Verification

- Nine `quick_validate.py` skill checks: passed.
- `make scaffold-audit`: passed with 13 warnings on unrelated legacy skills.
- `make scaffold-audit-self-test`: 22 passed, 0 failures.
- Governance G002: 7 passed.
- `make check-agent-memory`: passed.
- `make ci`: passed, including 266 package tests, 112 smoke tests, and the
  33-page documentation render.
- Rerun inspector plus offline visual inventory: 67 passed.
- Focused rollout read-model/Zarr owner slice: 37 passed.
- Full rollout suite: 184 passed, 1 pre-existing failure in
  `test_multihorizon_highgain_profile_selects_exact_ordered_cross_scene_roots`;
  its unchanged `v1_observed` configuration still selects the Oracle GT target
  source. This diff does not alter that configuration or behavior.
- Positive routing probes selected all nine retained skills; the public DTO
  docstring probe selected `python-standards`.
- Near-miss probes kept one-step VIN work out of rollout planning, display-only
  Rerun work out of geometry, Typst prose out of docs curation, scene RRI out of
  entity-aware RRI, and exact-owner lookup out of optional navigation tools.
- `git diff --check`: passed.

# Canonical-state impact

No project scientific state changed. The scaffold policy and package owners were
updated directly; no canonical memory update is needed.
