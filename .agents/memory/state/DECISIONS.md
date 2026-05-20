---
id: decisions
updated: 2026-05-12
scope: repo
owner: jan
status: active
tags: [codex, workflow, architecture]
---

# Decisions

## Durable Repo Decisions
- Repo skills live in `.agents/skills/` and use progressive disclosure.
- Non-trivial coding, docs, scaffold, research, or memory edits start from the
  `agent-behavior` skill: state assumptions, prefer the simplest sufficient
  change, make surgical edits, and define verification.
- Repo-local skills carry routing metadata under the skill frontmatter
  `metadata` key: `applies_to`, `triggers`, `must_read`, and `verification`.
- Shared repo guidance must stay machine-portable; operator-specific interpreter or host paths belong in `.agents/references/` or user-local notes, not repo-root or nested `AGENTS.md` files.
- Canonical project memory lives in `.agents/memory/state/`; episodic notes live in `.agents/memory/history/`.
- Generated routing context under `docs/_generated/context/*.md` is derived
  output and remains untracked; tracked generated glossary/KG artifacts such
  as `docs/_generated/context/glossary.jsonl` are regenerated through the
  glossary pipeline.
- `make context` is the lightweight scaffold refresh for `source_index.md`, `literature_index.md`, and `data_contracts.md`.
- `make context-heavy` is explicit fallback for bundled heavy artifacts such as UML, bulk docstrings, and directory trees.
- `docs/_generated/context/source_index.md` is a compact routing index; broad file inventories stay discoverable through commands, not the hot path.
- The Codex hot path starts from role-split source order: thesis roadmap/questions plus canonical memory for active thesis direction, glossary source for terminology, proposal Typst for advisor wording, seminar paper only for historical implemented evidence, and generated context only for lightweight routing.
- Progressive disclosure routes from the root `AGENTS.md` into package, docs, and module-specific guides only after the touched surface is localized; agents should not load all nested guides up front.
- Broad scaffold routing is split by role: `aria-nbv-context` owns local
  deterministic file discovery, `aria-litkg-memory` owns KG-backed retrieval,
  claim checks, and consolidation, and `semantic-scholar-litkg` owns KG
  implementation/config/operation.
- `.agents/references/` holds operator aids and long-form conventions; those docs are on-demand references, not default bootstrap context.
- `docs/typst/seminar_paper/main.typ` is historical implemented evidence. Current thesis direction is owned by `docs/contents/thesis/roadmap.qmd`, `docs/contents/thesis/questions.qmd`, and `.agents/memory/state/`; do not let the older seminar paper override newer plans or promote planned work to implemented results.
- Native debriefs under `.agents/memory/history/` must include `canonical_updates_needed`; existing `status: legacy-imported` notes are grandfathered archive evidence.
- Ad hoc `.codex/*.md` notes are invalid; migrate them into `.agents/memory/history/` or archive them under `archive/codex-legacy/`.
- Verification in shared repo guidance is selected by touched surface rather than by a single global checklist.
- litkg keeps the consolidated `kg-*` command surface for agents; no
  `agent-route`/`agent-retrieve` aliases are introduced. The default subset and
  expected context-pack fields live in `.agents/references/litkg_quick_reference.md`.
- Advisor-facing proposal, thesis roadmap/question, and literature-synthesis
  claims require `kg-claim-check` before being treated as supported.
- Codex Desktop persists local session transcripts under
  `${CODEX_HOME:-$HOME/.codex}/sessions/YYYY/MM/DD/rollout-*.jsonl`; restored
  backup stores may be queried explicitly but are not canonical repo memory.
- Transcript mining must not check in full raw Codex transcripts. Repo memory
  may contain only user-authored extracts and reviewed candidate distillates
  under `.agents/memory/transcripts/`, where LitKG indexes them with lower
  authority than canonical memory.
- Plan-mode transcript answers mean the user's answers to `request_user_input`
  questions. Assistant `<proposed_plan>` text remains agent output and does not
  become a decision unless the user later accepts or restates it.
- Transcript distillation emits candidate and reviewed JSONL records. Reviewed
  transcript status is routing metadata for promotion/backlog review; it is not
  current truth until the item is accepted into canonical memory, backlog, docs,
  or code.

## Technical Decisions
- Runtime objects are instantiated through config `.setup_target()` factories.
- Pose and camera representations use `PoseTW` and `CameraTW`.
- Package verification uses `ruff format`, `ruff check`, and targeted `pytest`.
- The tracked Python workspace and package root are `aria_nbv/` and `aria_nbv/aria_nbv`; repo tooling and docs should refer to that layout.
- Documentation changes should update Quarto/Typst sources directly, not ad hoc notes under `.codex/`.
- The published Quarto site refreshes `aria_nbv` API reference pages from docstrings via `quartodoc` during the Pages workflow, with `docs/reference/index.qmd` as the human-authored landing page.
- Generated agent-scaffold pages are internal operator artifacts under
  `.agents/generated/agent_scaffold/`; the published Quarto site must not
  regenerate or render them.
- Retained public QMD pages remain renderable, but retired implementation
  scratch/history belongs under `.agents/archive/docs/`. Generated quartodoc/API
  implementation contracts replace retired manual impl pages in public docs.
  Current thesis pages use `docs/contents/thesis/`, past seminar material uses
  `docs/contents/seminar/`, and only curated public archive summaries use
  `docs/contents/archive/` with explicit `phase`, `audience`, `status`, and
  `owner` frontmatter.
- Environment/setup instructions live in setup docs such as `SETUP.md` or
  setup QMD pages; root and nested guidance should point there rather than
  duplicating host-specific setup detail.
- `docs/contents/ideas.qmd` is human-maintained scratch/history and read-only
  for agents unless the user explicitly requests edits. Treat it as idea
  evidence, not current thesis direction.
- `docs/typst/shared/glossary.typ` remains the glossary/terminology source of
  truth. YAML, QMD, Typst, and KG-facing glossary outputs are derived from it.
- Canonical generated docs artifacts that belong to the glossary, notation, or
  docs pipeline should be regenerated and tracked when their source changes.
  Generated context and KG-routing artifacts remain derived/untracked unless
  explicitly versioned.
- Human-owner preferences that are durable but not public narrative or workflow
  rules live in `.agents/references/human_owner_intent.md`.
- OMX remains optional operator orchestration; it does not own canonical memory,
  backlog, docs, or repo state.

## Working Project Decisions
- The thesis/system name is **ARIA-NBV**.

### 2026-05-06 Thesis Sharpening Decisions
- The thesis asks whether ARIA-NBV can perform **target-conditioned,
  RRI-based multi-step NBV**.
- Minimal thesis success requires training a discrete finite-candidate `Q_H`
  model; `Q_H` is not optional.
- `Q_H` is a candidate-query Transformer: encode scene, target, history, and
  candidate tokens, then output one masked finite-horizon Q value per
  candidate.
- `Q_H` predicts bounded cumulative root-normalized target gain from ASE oracle rollout traces;
  learned selected actions must be oracle-evaluated.
- Main actor-visible target protocol is V1 **OBS-SEL / PRED-Q / GT-EVAL**.
- Target input starts with observed/predicted OBB geometry plus class,
  confidence, projected area, semidense support, and EVL support.
- Compact actor-visible crop descriptors are the first planned target-input
  ablation after the observed/predicted OBB plus support first path; entity
  tokens remain later ablations.
- Counterfactual state is geometry-only: frozen logged EFM/EVL context plus
  accumulated rendered/fused points and selected-view history.
- Temperature-softmax is a rollout data-diversity policy over oracle/model
  scored candidates, not the final objective.
- Mandatory first rollout sources before `Q_H` are random-valid,
  oracle-greedy/lookahead, and oracle-scored temperature-softmax; Gumbel-Top-k
  remains preferred later evidence.
- Online discrete `Q_H` in the ASE mesh/oracle loop is the first bridge step
  after offline fitted `Q_H`; continuous actor-critic, external simulator, and
  online RL baselines are bridge/future work, not required quantitative thesis
  success.
- The proposal should be a compact approximately 2.5 content-page research
  contract with RQs/objectives, literature pointers, and a compact timeline.
- Source policy: add all cited sources to `docs/references.bib`; add to
  `docs/literature/sources.jsonl` only implementation-shaping local corpus
  sources.
- Local manifest additions for this pass are CQL, BCQ, and Decision
  Transformer. Keep POMCP and submodularity references bibliography-only unless
  later needed locally.
- First thesis-grade scale may be a scene-level held-out subset with multiple
  targets/trajectories, but coverage must report scenes, snippets, targets,
  trajectories, rollout seeds, transitions, and gaps separately.
- Scaling is an evidence protocol rather than a standalone research question:
  scene-level splits, target diversity, snippets, trajectories, rollout seeds,
  transitions, invalid gaps, coverage gaps, and ablation axes must be reported
  wherever empirical thesis claims are made.

### 2026-05-07 Rollout DTO And Store Decisions
- The first implemented rollout replay path is a standalone `rollouts.zarr`
  store, not counterfactual blocks embedded inside the VIN offline store.
- Masked temperature-softmax is a stochastic rollout data-diversity policy over
  valid oracle/model-scored finite candidates. It persists logits,
  probabilities, log-probabilities, entropy, selected log-probability,
  temperature, score source, and RNG metadata, but the environment transition is
  still the sampled discrete selected action.
- The first `Q_H` store materializes selected-action transition replay. Dense
  all-action oracle-Q arrays remain schema-ready, `NaN`, and masked until a
  later oracle-lookahead converter fills them.
- `Q_H` trainable one-step target labels require explicit target-RRI metric
  provenance. Scene RRI, model scores, random scores, and distance heuristic
  scores must not silently become target-RRI labels.

### 2026-05-07 VIN Offline Store V7 Decisions
- The immutable VIN offline dataset format is strict `OFFLINE_DATASET_VERSION =
  7`; readers accept only the current version and fail fast for older manifests.
- Premature VIN offline-store counterfactual hooks are removed. The format no
  longer includes `VinOfflineCounterfactuals`,
  `materialized_blocks.counterfactuals`, `include_counterfactuals`,
  `load_counterfactuals`, `load_counterfactuals_for_batch`, or
  `_build_counterfactuals`.
- Multi-step rollout replay belongs in standalone rollout artifacts such as
  `rollouts.zarr`, not in immutable VIN offline-store counterfactual blocks.
- The local default `vin_offline` store and one-sample Rerun smoke sidecar were
  upgraded to v7 manifests without leaving migration code or compatibility
  readers behind. The default store remains partial/interrupted diagnostic
  evidence, not final training-scale evidence.

### 2026-05-07 Top-K Target Selector Decisions
- The first automatic target selector returns top-K actor-visible
  observed/predicted OBB targets per snippet. `K` is configurable and defaults
  to 3.
- Default selection is `greedy_top_k` over confidence, projected visibility,
  semidense/EVL support, and support deficit; `temperature_softmax_top_k` is
  the stochastic target-diversity option.
- V1 refuses GT OBBs as selector input. GT OBBs are only V0 sanity input or
  post-selection matching/evaluation data for target-RRI labels.
- Rollout target rows preserve selector rank, score, policy, probability,
  temperature, target invalidity bits, and GT match metadata so target identity
  can be audited in `rollouts.zarr`.

### 2026-05-09 Typst Thesis Notation Decisions
- Shared Typst notation separates abstract mathematical objects from
  implementation tensors: `cal(...)` owns point sets, candidate sets, meshes,
  face sets, spaces, and geometric collections; `bold(...)` is reserved for
  coordinate vectors, matrices, tensors, feature fields, embeddings, images,
  voxel grids, and implementation arrays.
- Candidate notation reserves `Q_H` / `Q_(H,theta)` for value functions.
  Finite candidate sets are `cal(Q)_t`, candidate poses are `q_(t,i)`, and
  candidate feature tensors are `bold(X)_t^"cand"`.
- Abstract states are plain symbols such as `s_t^"obs"`, `s_t^"cf0"`, and
  `s_t^"oracle"`. Learned state/candidate embeddings use symbols such as
  `bold(h)_t` and `bold(u)_(t,i)`.
- Thesis-core ARIA-NBV reconstruction-quality equations use point-mesh error
  `D` with directional components `D_(P -> M)` and `D_(M -> P)`. `Delta_t^e`
  remains the target-error sum. Generic `CD(...)` and `cal(A)` / `cal(C)`
  component notation are historical/background only.
- The repo-local `typst-authoring` skill owns the convention and strict
  hygiene checks for advisor-facing Typst files. Compatibility keys may remain
  in `docs/typst/shared` temporarily, but their rendered notation must follow
  the locked convention.

### 2026-05-20 Target-First RRI And Rollout Alignment Decisions
- The thesis objective hierarchy is target-first: rollout ranking, learned
  `Q_H`, and primary endpoint evaluation use root-normalized target gain.
  Scene-level RRI remains a diagnostic bridge to the seminar oracle pipeline,
  not a hidden training or ranking objective.
- The old seminar scene-RRI computation remains historical implemented
  evidence. Current thesis labels separate actor-visible semi-dense/EVL state
  from homogeneous oracle evaluation geometry and use target-specific crops for
  the optimized reward.
- Target selection is a three-stage contract: hard actor-visible eligibility,
  target-interest ranking or sampling, and deterministic class-compatible 3D
  IoU GT matching. Support and projected visibility are eligibility/audit
  fields rather than GT-match ranking multipliers.
- Target projected-area feasibility uses one clipped visible image-overlap
  field. Raw projected extents outside the image are not part of the main V1
  target selector/store contract.
- The thesis-scale target sampling default is deferred until selector coverage
  audits are available. Stratified target sampling over support, projected
  visibility, distance, and class is the leading candidate; greedy top-K and
  robust softmax remain comparison policies.
- The main candidate-generation profile is `v1_realistic_3family`:
  `forward_local`, `target_bearing_local`, and `lateral_target_bypass` under
  stricter local egocentric motion limits. `local_refinement`,
  `revisit_backtrack`, and `upper_bound_free_shell` are named ablations.
- Candidate full-shell count remains fixed, but thesis-scale generation gates
  low-valid-action roots and reports blocked roots, valid counts, invalid
  reasons, selected counts, and target gain by `position_id`.
- H>1 rollout traces are the canonical data product. H=1/myopic target labels
  are derived views over materialized rollout states; H=1-only generation is a
  smoke/preflight mode, not the thesis-scale artifact.
- Selected/parent rendered depth becomes actor-visible successor-state history
  after an action is selected. Training-core stores persist it at canonical
  configured resolution with renderer lineage; full-resolution depth is an
  audit/profile option.
- Target-eval crop point payloads are sampled/audit retention. Training-core
  stores scalar target distances, supports, root gain/RRI diagnostics, crop
  policy, fusion/eval-source lineage, masks, and provenance.
- Thesis-scale rollout generation requires scene-level split manifests before
  shard grouping. Sample-key splits remain smoke evidence only.
- Stochastic rollout evidence uses normal torch/numpy/random seeding once per
  job or shard, plus persisted seed, shard manifest/order identity, and sampled
  outcomes. Per-step derived seed trees are not required.
- The next rollout Zarr schema is an incompatible `1.0` target-rollout-core
  style contract with no migration readers; stale stores are regenerated.

### 2026-05-11 Transcript-Mined Project Decisions
- Rollout and `Q_H` stores keep full scene meshes as external
  path/hash/version references and may embed high-detail target mesh crops once
  per target with crop metadata. Lean training shards and richer
  validation/audit retention profiles are distinct store profiles.
- The first multi-step rollout payload is geometry-first and typed. Selection
  policy uses a typed enum such as `StrEnum` and records configurable
  temperature/noisy-softmax, beam width, valid-candidate score source, and
  sampling provenance.
- VIN/offline training-facing tensors use padded dense arrays with explicit
  lengths or `candidate_count` masks, preserving full candidate width through
  model-facing paths while masking padded tails. The canonical VIN offline
  store remains manifest/sample-index/split/shard based.
- ARIA-NBV keeps first-class sample, dataset, and rollout inspection utilities
  through repo-native summary, Rerun, and Streamlit surfaces. Compatibility
  with external viewers such as VS Code Scientific Data Viewer is optional
  operator convenience, not a canonical project contract.
- Rerun inspectors should use native Rerun component types such as
  `Transform3D`, `Pinhole`, and `Boxes3D` whenever available instead of
  reconstructing cameras or OBBs from primitive line/point geometry.

- The core thesis claim is target-conditioned, quality-driven NBV on ASE/EFM with strict M1 data/cache/oracle contracts.
- RRI is the primary project objective for next-best-view research in this repo. Coverage-style objectives remain baselines or diagnostics, not the main thesis target.
- The canonical training and evaluation surface remains finite candidate ranking/selection anchored on prerecorded ASE trajectory snippets with oracle supervision derived from GT meshes where available.
- The thesis-core simulator substrate is the ASE mesh/oracle counterfactual rollout loop. Habitat, Isaac, external datasets, online Gymnasium/SB3, continuous actor-critic policies, SceneScript, VLM planning, and real-device guidance are stretch or bridge work unless later evidence changes the scope.
- The proposal/thesis boundary has five roles: implemented substrate; prerequisite and evidence protocol covering proposal freeze, M1, V0/V1 target contracts, masks/reasons, rollout/Q storage, LRZ gates, scene-level splits, and coverage reporting; hard quantitative thesis core covering observed target selection, one-step target scorer baseline, mixed candidates, rollout sources, candidate-query Transformer `Q_H`, and scale generation with exact coverage reporting; mandatory bridge design covering online discrete `Q_H`, IQL, actor-critic, hierarchy, and simulator paths; and future-work extensions covering SceneScript, VLM/global planning, real-device guidance, and quantitative continuous-control experiments.
- Proposal freeze precedes M1 scale-up. The proposal must be a compact research contract, use primary metadata in the bibliography, remove generated/Wikipedia citation slop, render with `make proposal-pdf`, and track the generated proposal PDF once frozen.
- M1 is a hard stop before target/RL scaling: offline store, split, frame/CW90, candidate-label ordering, depth/backprojection, Rerun normal/boundary/failure recordings, and oracle throughput evidence must be reported in a public M1 contract artifact or explicit blockers.
- The final experiment scale bar is full 100 GT-mesh ASE scenes and 4,608 snippet windows after small-subset correctness. Final supervision coverage must be reported exactly, and train/validation/test boundaries must be scene-level; the exact held-out test split remains an advisor decision.
- LRZ deterministic sharding, Slurm/DSS staging, resumable writes, storage budgeting, and Zarr-first rollout/Q schema are hard M2/M3 gates before full-scale target/RL generation. No workstation should be assumed as the thesis scale path.
- The target contract separates actor input from oracle labels: V0 uses GT OBB input plus GT crop/evaluation as a sanity/upper-bound path; V1 is mandatory for the main result and uses observed/predicted OBB inputs matched to GT-OBB target-RRI labels.
- The main target protocol is OBS-SEL / PRED-Q / GT-EVAL: observed-only target selection, predicted/observed target-conditioned scoring or Q_H, and GT target-crop evaluation.
- Automatic target selection is mandatory and actor-visible only: use predicted OBBs/classes/confidence, projected area, current semidense/EVL point support, and related observed signals. GT is label/evaluation only.
- Target matching starts with compatible class, OBB IoU, visibility/support, projected area, and semidense/EVL point support. Extra criterion `X` is deferred.
- Candidate generation is a mandatory mixed observed candidate set with categorical-probability strategy hyperparameters. The thesis-core vocabulary follows the current ARIA-NBV generator modes: `TARGET_POINT`, `RADIAL_AWAY`, `RADIAL_TOWARDS`, `FORWARD_RIG`, `UNIFORM_SPHERE`, `FORWARD_POWERSPHERICAL`, and bounded view jitter. Frontier or missing-surface samplers are stretch unless implemented and validated.
- The one-step target-conditioned scorer is no longer a standalone research
  question. It is the required learned myopic baseline/control for the revised
  Q_H planning RQ, where `Q_H` must beat the learned one-step target scorer and
  one-step greedy/model scoring on cumulative root-normalized target gain under
  equal acquisition budget.
- Invalidity is a hard mask plus explicit reason-code contract, not a low RRI class. Validity heads or scalar penalty rewards are ablations after masks/reasons are reliable.
- The first thesis-grade non-myopic comparison is bounded oracle-RRI lookahead versus one-step greedy under equal acquisition and candidate budget; bounded oracle lookahead is an upper-bound baseline for learned Q_H.
- Rollout data before the first `Q_H` training must include random-valid,
  oracle-greedy/lookahead, and oracle-scored temperature-softmax traces with
  deterministic replay. Gumbel-Top-k traces remain preferred later evidence
  for diversity, but they are not a blocker for the first `Q_H` attempt.
- Multi-step reward and Q targets start with bounded cumulative root-normalized target gain. Gamma remains symbolic in formulas, but the thesis-core comparison reports cumulative target-root gain and endpoint gain under equal acquisition budget. State-relative target RRI remains a diagnostic and VIN-compatible one-step label; log-improvement and scalar motion/rule/validity/diversity penalties are extensions.
- A target-conditioned candidate-query Transformer `Q_H` model over finite
  candidate sets is a mandatory M5 thesis deliverable, trained from ASE oracle
  rollout data. It predicts one masked bounded-horizon Q value per candidate
  and must beat one-step greedy/model scoring on cumulative target-root gain under
  equal acquisition budget, while oracle lookahead is reported as the upper
  bound.
- Fitted Double-Q-style targets are the first value-learning target family for
  `Q_H`. IQL is a second offline-RL ablation only after `Q_H` is stable; SB3
  DQN/PPO/SAC are deferred until an online Gymnasium simulator exists.
- Zarr is the first-choice rollout replay store. It should contain factual
  source, target, rollout, step, candidate, lineage, dictionary, target-eval
  crop, and metadata tables without duplicating raw ASE/ATEK; full meshes are
  external path/hash/version references, and `Q_H` tensors are validated
  derived training views.
- The current implemented rollout replay path uses standalone `rollouts.zarr`
  schema `0.7-root-gain-target-crops`, not VIN offline-store embedded
  counterfactual blocks. The production root contract is `VinOfflineSample`;
  `VinOracleBatch` remains a one-step VIN training DTO.
- Masked oracle temperature-softmax is the first stochastic rollout
  data-diversity policy. It samples discrete selected actions from valid
  candidate distributions and persists logits, probabilities, log-probs,
  entropy, temperature, score source, and RNG replay metadata.
- The first `Q_H` data view is selected-action transition replay derived from
  factual rollout rows. Dense all-action oracle-Q targets remain unavailable
  and `NaN`/masked until a later oracle-lookahead converter materializes them.
- The public glossary is a tiered math lookup table generated from `docs/typst/shared/glossary.typ`: core thesis math terms render first with shared symbol/equation refs, support terms remain normal glossary entries, and peripheral background terms stay linkable but visually demoted.
- CI/pre-commit becomes required before full-scale generation, not before proposal/M1 groundwork. GitHub issue mirroring remains a local TODO; `.agents/*.toml` stays the source of truth.

## litkg Decisions (2026-05-11/12)
- Semantic kg-search uses the Neo4j vector index as the canonical backend: `kg_embedding_index_2560` over `KGEmbeddingNode.kg_embedding` (HNSW, cosine, dim 2560). Lexical fallback is always available when Neo4j or the Ollama tunnel is down; the response surfaces `search_mode: hybrid|lexical_only` with `mode_reason`.
- BM25 (k1=1.5, b=0.75) replaces naive term-frequency as the lexical scorer. Porter stemming + a curated `[synonyms]` table in `.configs/litkg.toml` + Levenshtein distance-≤2 fuzzy fallback for zero-exact-hits round out the lexical layer.
- Agent-facing kg-* output is compact-by-default (≤14 lines). Verbose payloads require explicit opt-in via `KG_VERBOSE=1` or `KG_FORMAT=json`. The compact filters live at `scripts/kg/compact_*.jq` and must not surface `evidence_spans`, `backend_status`, `action_plan`, `assumptions`, `missing_leaves`, `missing_context_leaves`, `profile`, `budget_tokens`, or `truncated`.
- Auto-refresh on session Stop is enabled via `scripts/kg/auto_refresh.sh`, gated on Ollama tunnel reachability at `127.0.0.1:11434`. Optional `KG_NEO4J_AUTO_UP=1` warm-starts Neo4j Docker so the next session has hybrid search available.
- Graphiti (`[backends].graphiti = false` today) and MemPalace remain deferred. They are not the right home for paper/code retrieval; revisit only when temporal queries (Graphiti) or human-curated annotations (MemPalace) become explicit workflows. Tracked as `todo-068` and `todo-069`.
- `kg-query` and `kg-brief` were deleted as Makefile aliases for `kg-route`; `kg-related` was deleted as a subset of `kg-search`. `kg-ingest-docs-smoke` collapsed into `make kg-ingest-docs KG_SMOKE=1`. The agent-facing kg verb set is `kg-search`, `kg-route`, `kg-claim-check`, `kg-status`, `kg-capabilities`.
