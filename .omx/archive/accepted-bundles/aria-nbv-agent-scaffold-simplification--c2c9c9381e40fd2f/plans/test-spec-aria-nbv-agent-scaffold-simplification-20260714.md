# Test Specification: ARIA-NBV Agent Scaffold Simplification

## Success claim

The migrated scaffold is smaller and more predictable, preserves accepted
ARIA-specific capabilities and scientific contracts, works without optional
services, leaves the inherited dirty worktree byte-stable, and introduces no
hidden mutation or competing truth surface.

## Baseline and contamination gates

- Build only in a clean sibling worktree at
  `87cf587e9e64d536b78e8a12f5ddff0fc5636676`.
- Record staged, unstaged, untracked-planned-path, submodule, and generated-OMX-
  block manifests separately; hash each before execution and at final handoff.
- Import only the staged `.omx/**` ignore hunk and the generated root OMX block.
  Negative fixtures reject the unstaged `.codex` hunk, dirty LitKG checkout, or
  any unrelated user path.
- Assert the OMX block SHA-256 is
  `1270d2c4a28e8488d75b814bd6662f64d28adff96c5ecea40d32eea111b3c180` and
  byte-identical after migration. Allow its externally owned
  `docs/guidance-schema.md` pointer without creating a local duplicate.
- Verify the promoted content-addressed migration handoff embeds hashes of this
  plan/test spec and ordered reviews and matches them before implementation
  begins. Treat these `.omx` files as read-only planning evidence, not a third
  repository-content import; re-extract every `BEGIN/END` block and compare its
  SHA-256.
- Validate every lane manifest under
  `.omx/tmp/agent-scaffold-migration/<plan-sha256>/wpN/manifest.json`: canonical
  schema, baseline/plan hash, owned paths, shared-edit preimage/patch/consumer,
  artifact hashes, local checks, and recomputed lane hash. Consumers must reject
  mismatches. WP8 must remove the root after embedding final evidence; no
  coordination manifest becomes tracked truth.
- WP1/WP3 package-local checks scan only their owned active surfaces and exclude
  historical roots. Their manifests must enumerate repository-wide residual
  findings and historical-allowlist candidates; WP5/WP8 apply/resolve them and
  own the final repository-wide active/historical absence checks.

## Structural unit checks

- Common scaffold checker positive/negative fixtures and production size
  target of at most 300 lines.
- Exactly seven active guide paths:
  `AGENTS.md`, `aria_nbv/AGENTS.md`,
  `aria_nbv/aria_nbv/data_handling/AGENTS.md`,
  `aria_nbv/aria_nbv/rollouts/AGENTS.md`,
  `aria_nbv/aria_nbv/rri_metrics/AGENTS.md`,
  `aria_nbv/aria_nbv/vin/AGENTS.md`, and `docs/AGENTS.md`; archive/runtime copies
  are excluded.
- Retained catalog range 7–9, not an exact roster; each retained skill appears
  once in an invocation matrix with positive, adjacent-negative, fallback, and
  handoff fixtures.
- Root/guide/skill/description/context-map text budgets and valid context
  pointers.
- Active references cannot treat external generic skills, code-index,
  MemPalace, LitKG, Graphify, OMX, or MCP names as repo-owned truth.
- Active-vs-historical allowlist checks for retired names and paths.
- Duplicate backlog IDs, dangling dependencies, missing mapped fields, and
  invalid resolved references fail.
- Literature validator fixtures cover duplicate/missing bibliography/source
  keys and missing source paths; it does not claim semantic entailment.
- Public-docstring checker fixtures reject trivial narration and accept
  contract-bearing docs at the configured tiers.
- UML negative fixtures reject missing/out-of-package `UML_ROOT`, tracked or
  relative `UML_OUT`, and full-package generation without `UML_FULL=1`; the
  positive fixture runs scoped Syrenka generation, Mermaid lint, and atomic
  rename without `scripts/filter_mermaid.py`.
- Docstring discovery golden fixtures cover literal `__all__`, fallback public
  definitions, method AST/decorator thresholds, exported dataclass/msgspec/
  Pydantic/config fields, and advisory-only private findings. Compare the module
  set to `scripts/quartodoc_expand_config.py --print-modules`.

## Graphify 0.9.9 provenance matrix

Use isolated temporary repositories and absolute `GRAPHIFY_OUT`; querying uses
explicit `--graph`.

| Case | Expected result |
|---|---|
| matching root/HEAD/config/version/graph hash, valid completion, clean covered paths | current |
| wrong root or worktree | stale; direct lookup fallback |
| changed HEAD | stale; no refresh |
| changed profile/config hash | stale; no refresh |
| changed Graphify version | stale; no refresh |
| changed graph hash | stale; no refresh |
| failed/incomplete build or invalid graph | unusable |
| dirty covered path | stale |
| dirty uncovered path | current with explicit warning |
| absent sidecar or Graphify binary | direct lookup fallback |

Run status with filesystem snapshots before/after to prove it never refreshes or
writes. Build default, scaffold, and two selected-PDF profiles concurrently and
assert output/cache isolation. Verify a failed build never publishes a complete
sidecar.

Assert the default manifest contains exactly the production/design globs named
in O13 and excludes guides/tests/scripts/runtime/archive/generated/TeX/PDF
surfaces. Assert the scaffold staging manifest contains only its named owner
surfaces. For selected PDFs, validate unique `citation_key` joins, canonical
selection JSON, PDF hashes, the first-16-hex selection hash recipe, and the
source-locator contract (`citation_key`, PDF hash, page/chunk, direct TeX
`path:line` or `tex_source_unavailable`).

## Backlog migration reconciliation

- Reconcile all 87 active and 61 resolved records from the baseline journals.
- Validate `wp2/resolved-classification.jsonl` has exactly 61 unique IDs and the
  required source/status/disposition/references/rationale/source-record-hash
  fields; embed its hash/result in final migration evidence before cleanup.
- Compute the union of all baseline TOML keys. For every serialized value,
  including `id`, `title`, `description`, `type`/kind, status, priority,
  dependencies, `issue_ids`, labels, context, references, implementation notes,
  acceptance, verification, `loc_min`, `loc_expected`, `loc_max`, `resolved_at`,
  `resolution_note`, and `resolved_from`, assert a destination or explicit
  per-record, per-field historical-only rationale.
- Smoke plain-file search, priority ranking, edit, resolve, dependency lookup,
  and `git show 87cf587:<path>` historical retrieval.
- If any mapping/count/retrieval gate fails, assert the rollback path retains
  the TOML journals and does not delete the agents-DB owner.
- Parse every canonical key-sorted JSON block in `.agents/backlog.md`; validate
  anchor/title/checkbox projections, dependency anchors, the allowed status
  transition graph including the 69 baseline `todo` and 18 baseline `open`
  records, required resolution fields, `migration_rationale`, and
  active-to-resolved movement.

## Scientific and documentation regression groups

- Run `cd aria_nbv && uv run pytest tests/rollouts/test_counterfactuals.py
  tests/data_handling/test_target_selection.py
  tests/rri_metrics/test_oracle_rri_chunking.py` for invalidity, visibility,
  target selection, and oracle contracts.
- Run `cd aria_nbv && uv run pytest
  tests/pose_generation/test_align_to_gravity.py
  tests/pose_generation/test_orientations.py
  tests/rendering/test_depth_backprojection_conventions.py
  tests/vin/test_geometry_helpers.py tests/vin/test_pose_encoding.py` for
  camera/pose/projection/CW90/frame boundaries.
- Run `cd aria_nbv && uv run pytest tests/rollouts/test_zarr_store.py
  tests/data_handling/test_vin_offline_store.py
  tests/rollouts/test_dataset_writer.py` for Zarr round-trip, version,
  chunk/codec, and store contracts.
- Deleted-skill routing fixtures, including geometry outside Rerun and outside
  the four nested packages.
- Fixed `tests/scaffold/fixtures/claim-check-vin-nbv.md` evidence fixture:
  citation resolution, authoritative section,
  exact locator, calibrated wording, curated-page consistency, and focused
  render. Validate the human semantic verdict separately in
  `tests/scaffold/fixtures/claim-check-vin-nbv-review.json`.
  WP7 exclusively authors both files; WP8 treats them as read-only inputs to the
  integrated checker/render gate.
- Execute the three literal direct-TeX `rg` recipes from O14 against the VIN-NBV
  record; assert `path:line`, heading, citation key, and calibrated wording are
  captured. The misrooted wrapper paths must not exist.
- Quartodoc generation, focused Quarto render, Typst compile, and Mermaid
  lint/render smoke.
- README keep/merge/delete manifest: every retained section names a human
  consumer/value; stale symbol matrices fail.

## Integration and absence checks

- Run the skill validator over the actual retained 7–9 catalog and validate all
  context pointers.
- Assemble WP4/WP5/WP7 lane outputs in WP8, then enforce the final 7–9 range,
  complete invocation matrix, global text budgets, and repository-wide retired-
  dependency absence; no parallel package may claim this final gate.
- Run the common checker/self-tests and `make check-agent-memory` under the new
  event-triggered debrief policy.
- Run `tests/scaffold/run_isolated_core_checks.py`, which provides temporary
  HOME/XDG/cache/output roots, logging wrappers for only required executables,
  a Python `sitecustomize.py` socket/write audit hook, before/after snapshots of
  the repository and controlled roots, and a local HTTP(S)-proxy trap. Wrappers
  reject remote/network subcommands and ordinary network clients are absent.
  Graphify, LitKG, code-index, MemPalace, and OMX are absent. Fail on a Python
  socket attempt, proxy-aware connection, write in observed roots outside
  declared outputs, repository hash change, unexpected cache, background log/
  stamp/watcher, silent refresh, or hidden skip. Do not claim OS-wide detection
  of arbitrary raw sockets or writes outside observed roots.
- Verify `.omx/**`, runtime state, local configs, and mined transcripts are not
  tracked with `git ls-files`; scan active guidance/config/scripts/hooks/runtime
  for absolute home paths and validate historical archives/debriefs only against
  `tests/scaffold/historical_allowlist.toml`. Each entry must contain `pattern`,
  `path_globs`, `reason`, and `owner`; reject path globs outside
  `.agents/memory/history/**` and `.agents/archive/**`.
- Assert `scripts/git_hooks/post-commit` and its installer target are absent,
  no installer-owned marker hook exists in the clean sibling, and no replacement
  post-commit hook is introduced; do not inspect or mutate unrelated user-local
  hooks in the inherited worktree.
- Record the removed LitKG gitlink and upstream URL, then run a fresh-clone/
  submodule smoke proving no removed submodule or Rust/Neo4j/Ollama/embedding/MCP
  service is required.
- Apply WP2 checker specifications only in WP8, WP3 claim-checklist
  specifications only in WP7, WP6 routing-fixture specifications only in WP5,
  and WP1/WP3/WP4 `Makefile` manifests only in WP8; compare every shared-owner edit
  to its reviewed input.
- Synchronize only adapters found in the repository's actual adapter catalog;
  assert no obsolete mapping remains.

## End-to-end routing scenarios

For each case assert one primary owner/capability, required evidence, forbidden
shortcut/tool class, expected handoff, fallback, and completion criterion:

1. known file/exact symbol lookup;
2. unknown architecture relationship with current scaffold Graphify;
3. unknown architecture with stale/wrong-root/no-tool Graphify;
4. concrete traceback or suspicious metric;
5. entity/RRI change;
6. geometry/frame change outside Rerun;
7. Zarr API/store change;
8. ASE/ATEK/offline-store operation;
9. Rerun inspection;
10. LRZ/DSS/Slurm/Pyxis job;
11. finite-candidate counterfactual rollout planning;
12. advisor-facing research decision and claim evidence;
13. Quarto/bibliography/source-manifest edit;
14. Typst/Mermaid edit;
15. public Python API docstring.

## Required final evidence

- `git diff --check` and complete final diff from the clean baseline.
- All five inherited-worktree hashes unchanged.
- Retained local skill validator, common checker, and negative self-tests.
- `make check-agent-memory`, affected Python tests, focused docs builds, then
  `make ci`.
- Repository-wide stale-name/path scan for retired skills, LitKG, generated
  context, agents DB, hook wiring, exact MCP identifiers, absolute home paths,
  and tracked `.omx`, split into active failures and historical allowlists.
- Before/after counts for skills, descriptions, hot-path lines, scripts, Make
  targets, hooks, submodules, generated artifacts, and required services.
- Named architectural review finding no new truth surface, backend, service,
  dependency, automatic mutation, or replacement framework.

## Team verification path

Each Team lane returns package-local command output, changed-file inventory, and
exclusive-ownership attestation. WP8 runs the full matrix from a clean state. A
separate `code-reviewer` evaluates the complete diff, then a `verifier` confirms
the success claim, baseline provenance, optional-tool absence, and contamination
hashes. Ultragoal checkpoints completion only after both approve.
