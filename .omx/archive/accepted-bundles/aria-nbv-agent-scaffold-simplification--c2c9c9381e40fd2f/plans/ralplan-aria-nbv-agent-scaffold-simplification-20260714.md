# RALPLAN: ARIA-NBV Agent Scaffold Simplification

**Status:** APPROVED — Architect and Critic consensus
**Planning baseline:** `87cf587e9e64d536b78e8a12f5ddff0fc5636676`
**Context:** `.omx/context/agent-scaffold-consensus-20260714T081220Z.md`
**Test specification:** `.omx/plans/test-spec-aria-nbv-agent-scaffold-simplification-20260714.md`

## Requirements summary

Simplify ARIA-NBV's agent scaffold without losing source ownership, scientific
contracts, local discovery, documentation quality, literature traceability, or
operator workflows. The result must use a clean worktree, leave the current
dirty branch untouched, reduce the local catalog from 20 to 7–9 independently
reachable skills, remove hidden lifecycle mutation and optional-service
requirements, and make every permanent rule testable from its owning surface.

The generated OMX marker block inside root `AGENTS.md` is external/generated and
must remain byte-identical. Text budgets apply only to ARIA-owned guidance.

## RALPLAN-DR

### Principles

1. **One meaning, one owner.** Skills own repeatable process; code, nearest
   guides, docs, tests, state, bibliography, and backlog own durable truth.
2. **Independent reach earns invocation.** A skill survives only when it has a
   distinct autonomous trigger or required handoff.
3. **Derived tools are evidence.** Graphify, generated docs, external skills,
   and orchestration never override source owners.
4. **Explicit beats ambient.** No automatic commit/session refresh, transcript
   mining, hidden mutation, or silent runtime dependency.
5. **Deletion remains provable.** Lock unique behavior in owners/tests before
   retiring a skill or tool.

### Decision drivers

1. Predictable source ownership and routing.
2. Large reduction in always-loaded and maintained scaffold surface.
3. Safe migration without losing scientific invariants, backlog records,
   literature evidence, or user-owned work.

### Viable options

#### A. Harden the existing scaffold

Keep 20 skills, LitKG, agents DB, generated context, and lifecycle hooks; repair
CI and provenance.

- **Pros:** smallest immediate migration; preserves every command.
- **Cons:** retains overlapping authority, hidden lifecycle behavior, a
  1,038-line audit, and broad custom metadata; misses the 7–9 target.

#### B. Radical seven-skill minimum

Keep discovery, diagnosis, docs, data, remote compute, rollout planning, and
Rerun only.

- **Pros:** greatest context and maintenance reduction.
- **Cons:** removes the accepted Python-docstring workflow and makes
  advisor-facing planning depend too heavily on generic external behavior.

#### C. Chosen: nine independently reachable ARIA sidecars

Keep nine compact local skills, move scientific invariants into nearest
owners/tests, remove generic/infrastructure skills and LitKG/generated context,
and retain Graphify only as provenance-checked optional evidence.

- **Pros:** meets the budget while preserving every distinct ARIA workflow;
  matches `writing-great-skills` independent-reach, progressive-disclosure,
  completion-criterion, and single-owner rules.
- **Cons:** requires staged ledgers and integration; literature checks become
  more explicit/manual; shared routing/CI files must wait for lane integration.

## Target architecture

1. **Truth:** code/tests, seven first-party guides, active thesis/docs, canonical
   state, bibliography, and one compact active backlog.
2. **Dispatch:** the ARIA prefix of root `AGENTS.md` plus the nearest owner.
3. **Workflows:** 7–9 independently reachable local skills; invocation is decided
   per skill rather than inferred from retention.
4. **Discovery:** direct reads/`rg` for exact lookup; Graphify only for covered,
   provenance-current topology.
5. **Literature:** curated pages, BibTeX, `sources.jsonl`, local TeX/PDF source
   inspection, and optional selected-PDF Graphify.
6. **Validation:** a small structural scaffold checker, focused scientific tests,
   documentation renders, and stale-reference scans.

Permanent architecture excludes:

- the `agent-behavior` activation tax;
- LitKG submodule/config/skills/Make targets/hooks/Neo4j/claim coupling;
- canonical code-index or MemPalace routing;
- custom generated context and AST helper suites;
- agents-DB CLI and four active journals;
- automatic session/commit/Graphify/KG mutation;
- vendored Graphify or external generic skill copies;
- tracked `.omx` runtime/planning trees;
- ceremonial exact skill-array routing fixtures.

### Durable artifact policy

`.omx/**` is operator-local. Approved conclusions are explicitly promoted:

- scaffold policy → `.agents/references/agent_scaffold_contract.md`;
- current decision → `.agents/memory/state/DECISIONS.md`;
- actionable follow-up → `.agents/backlog.md`;
- reusable difficult diagnosis/handoff → event-triggered debrief.

Before execution, promote the approved plan and test contract as one
self-contained, content-addressed migration handoff under
`.agents/memory/history/YYYY/MM/`. It embeds the baseline, approved dirty inputs,
work-package graph, exclusive ownership, stop conditions, full verification
contract, and SHA-256 hashes of the local RALPLAN artifacts. `DECISIONS.md`
receives only the durable decision summary.

This does not broaden the dirty-import gate. The two approved dirty imports are
repository content applied to the clean baseline. The ignored `.omx` context,
plan, test spec, and ordered Architect/Critic reviews are separately classified
as **read-only planning evidence**. WP0 runs `sha256sum` over those exact files,
creates
`.agents/memory/history/YYYY/MM/YYYY-MM-DD-agent-scaffold-migration-handoff.md`,
and embeds each file verbatim between unique `BEGIN/END <relative-path>
sha256=<digest>` markers. It then re-extracts each block to a temporary file and
compares SHA-256 before committing the handoff. The handoff records the two
repository-content imports separately and may not apply any other `.omx` or
dirty-worktree bytes.

The generated `<!-- OMX:AGENTS:START -->…<!-- OMX:AGENTS:END -->` overlay is a
tracked, externally generated block. Import it from the approved dirty input and
preserve it byte-for-byte (approved SHA-256
`1270d2c4a28e8488d75b814bd6662f64d28adff96c5ecea40d32eea111b3c180`). Its
`docs/guidance-schema.md` pointer is explicitly allowlisted as externally owned;
ARIA must not create a duplicate schema merely to satisfy a local link check.

## Provisional nine-skill portfolio and invocation audit

The chosen portfolio contains nine skills, but nine is not a permanently encoded
array. WP0/WP6 must prove that removed cross-cutting capabilities remain
discoverable before deletion. If proof fails, revise the ADR and finish with an
evidence-backed 7–9 skills rather than forcing the roster.

Applying D13's independent-reach audit currently makes all nine model-invoked:
each must be recognized autonomously from an ordinary task or is a named handoff.
Descriptions use one branch trigger per meaning, front-load a leading verb,
normally stay within 35 words, and share a ≤300-word model-invoked budget.

| Skill | Distinct branch | Autonomous handoff | Invocation | Rationale / disposition |
|---|---|---:|---|---|
| `aria-nbv-context` | Unknown owner, source family, or covered topology | Yes | Model | Localize before owner-specific work; sole discovery control plane |
| `diagnose-aria` | Concrete failure, traceback, bad metric, UI/docs/data artifact | Yes | Model | Failures bypass broad discovery; remove generic/KG doctrine |
| `aria-docs` | Quarto, Typst, bibliography, citations, Mermaid, docs boundary | Yes | Model | Merge three docs skills with branch-specific references |
| `dataset-cache-ops` | ASE/ATEK/download/store/manifest/split operation | Yes | Model | Distinct data lifecycle; absorb only ARIA Zarr operations |
| `rerun-nbv-inspector` | Rerun/`.rrd`/frusta/offline visual evidence | Yes | Model | Distinct visual evidence loop; absorb display-frame diagnostics |
| `lrz-ai-systems` | LRZ/DSS/Slurm/Pyxis remote work | Yes | Model | Environment-specific commands and failures |
| `counterfactual-rollout-planner` | Finite-candidate rollout, invalidity, stochastic branches, `Q_H` | Yes | Model | Distinct research contract; repair paths and trim roadmap truth |
| `plan-grill` | Advisor-facing/high-impact research decision | Yes | Model | Root autonomously hands high-impact choices to the ARIA evidence adapter |
| `python-docstrings` | Public Python/Quartodoc contract documentation | Yes | Model | Accepted workflow; compact through progressive disclosure |

### Disposition of all current skills

| Current skill | Target |
|---|---|
| `agent-behavior` | Delete; unique safety rules move once to root |
| `agents-db` | Delete after lossless local backlog migration |
| `aria-litkg-memory` | Delete with LitKG |
| `aria-nbv-context` | Keep/rewrite |
| `aria-nbv-mermaid` | Merge into `aria-docs` branch |
| `code-review-aria-nbv` | Delete; OMX owns review process, guides/tests own hazards |
| `counterfactual-rollout-planner` | Keep/compact |
| `dataset-cache-ops` | Keep/compact |
| `diagnose-aria` | Keep/compact |
| `docs-curator` | Merge into `aria-docs` |
| `entity-aware-rri` | Move unique rules to package guides/tests |
| `lrz-ai-systems` | Keep |
| `nbv-geometry-contracts` | Move unique rules to guides/GOTCHAS/docstrings/tests |
| `plan-grill` | Keep/compact |
| `python-docstrings` | Keep/compact with references |
| `rerun-nbv-inspector` | Keep/compact |
| `semantic-scholar-litkg` | Delete; standalone LitKG remains external |
| `simplification` | Delete; generic cleanup is external/OMX capability |
| `typst-authoring` | Merge into `aria-docs` |
| `zarr-python` | Delete; official API docs plus local store owners/tests |

### Text budgets

- ARIA prefix of root `AGENTS.md`: ≤80 lines and ≤900 words.
- `aria-nbv-context/SKILL.md`: ≤110 lines.
- `context_map.md`: ≤60 stable-concept lines.
- Each retained skill: hard maximum 150 lines, preferred ≤120.
- Retained 7–9 skills: ≤1,100 lines total.
- Top-level package/docs guide: ≤100 lines.
- Nested module guide: ≤70 lines.
- Generated OMX block is excluded and preserved byte-for-byte.

Every ordered step ends with an observable completion criterion. Branch-only
rules move behind precise context pointers; duplicate metadata, exact MCP names,
large `must_read` lists, and repeated verification prose are removed.

## Closed workpackage-local contracts (O10–O14)

### O10 — UML

The sole command is:

```bash
make uml UML_ROOT=aria_nbv/aria_nbv/<package-or-module-dir> UML_OUT=/absolute/untracked/output.mmd
```

`UML_ROOT` is required, must resolve inside `aria_nbv/aria_nbv`, and defaults to
no value. Whole-package generation requires explicit `UML_FULL=1`. `UML_OUT`
must be absolute and outside tracked paths (an ignored
`graphify-out/uml/*.mmd` path is allowed). The existing installed generator is
`aria_nbv/.venv/bin/python -m syrenka classdiagram "$UML_ROOT"`; output is
written to a temporary sibling, linted with
`tools/mermaid/scripts/aria_mermaid_lint.py`, then atomically renamed. Delete
`scripts/filter_mermaid.py`: required source scoping replaces heuristic output
filtering. UML is never called by CI, context refresh, docs render, or hooks.

### O11 — public-docstring enforcement

The blocking module set is exactly
`aria_nbv/.venv/bin/python scripts/quartodoc_expand_config.py --print-modules`.
Within it, public top-level exports are names in a static literal `__all__`; if
absent, non-underscore classes/functions defined in that module. A public class
needs a docstring. Its declared method/property needs a docstring when it is
public and has more than three AST statements, is async/a generator, or is
decorated as a property, abstract method, context manager, or cached property;
trivial accessors and inherited methods are exempt. Exported dataclass,
`msgspec.Struct`, Pydantic/config, DTO, protocol, and enum fields need either an
immediately following string literal or a matching class `Attributes:` entry.
Module docstrings block only for modules with a public export. Private symbols
over the same complexity thresholds produce warnings, never CI failures. The
checker operates on the complete blocking set at the final gate; temporary
migration exceptions must name symbol, reason, owner, and removal package and
must be empty in WP8 acceptance.

### O12 — README retention

WP7 inventories every package README. Retention requires a named human audience
and at least one durable operator workflow, file-format contract, or onboarding
sequence not already owned by API docs. Symbol matrices, agent routing, refactor
status, and generated inventories fail retention. Current evidence nominates
only `aria_nbv/aria_nbv/data_handling/README.md`; the manifest, not this
nomination, decides its final keep/merge/delete result.

### O13 — exact Graphify corpora and literature selection

The default production/design profile contains only: `Makefile`,
`aria_nbv/pyproject.toml`, `aria_nbv/aria_nbv/**/*.py`, `docs/index.qmd`,
`docs/contents/**/*.qmd`, `docs/typst/shared/**/*.typ`,
`docs/typst/thesis/**/*.typ`, `docs/figures/diagrams/**/*.svg`,
`docs/references.bib`, `docs/literature/README.md`,
`docs/literature/sources.jsonl`, and top-level `docs/literature/*.qmd`. It
excludes tests, scripts, generated/reference/site output, plans, archives,
runtime state, guides, skills, backlog, work records, TeX sources, PDFs, and all
external repositories.

The scaffold profile is built from an isolated staging corpus containing only
the seven active guides, active `.agents/references/*.md`,
`.agents/memory/state/*.md`, `.agents/backlog.md`, retained
`.agents/skills/*/SKILL.md` plus their referenced files, lifecycle hooks,
scaffold checker/tests/fixtures, `.gitignore`, `.graphifyignore`, and the
relevant client examples. A sorted newline-delimited manifest of actual copied
paths is hashed and stored in the sidecar.

Selected-PDF invocation accepts one or more bibliography citation keys. WP3
adds a unique `citation_key` to each retained `sources.jsonl` record and the
validator requires a matching BibTeX entry, `pdf_file`, and `tex_dir` when
present. The staging corpus contains only the selected PDFs plus `selection.json`.
The selection hash is the first 16 hex characters of SHA-256 over canonical
UTF-8 JSON containing sorted citation keys, each PDF SHA-256, Graphify version,
and profile/config hash. Output is
`graphify-out/literature/<selection-hash>/`; the sidecar stores the same JSON.
Graph results may locate evidence but every reported claim must cite citation
key, PDF hash, page/chunk locator if supplied, and a direct TeX `path:line`
verification or an explicit `tex_source_unavailable` reason.

### O14 — direct TeX discovery

Delete the misrooted literature-search wrappers; no replacement wrapper earns
ownership. `aria-docs` documents these literal commands, with `<tex_dir>` taken
from the validated `sources.jsonl` record:

```bash
rg -n -i --glob '*.tex' --glob '*.bib' --glob '*.sty' -- '<term>' "docs/literature/tex-src/<tex_dir>"
rg -n -i --glob '*.tex' -- '\\(part|chapter|section|subsection|subsubsection)\*?\{[^}]*<term>[^}]*\}' "docs/literature/tex-src/<tex_dir>"
rg -n -F '{<citation_key>,' docs/references.bib
```

Record `path:line`, surrounding section heading, citation key, and calibrated
claim wording in the claim fixture. If no TeX directory exists, inspect the
validated local PDF or upstream authoritative source and record that exception.

## Work packages

### WP0 — Clean baseline and deletion ledgers

**Dependencies:** none; serial prerequisite.

Create a clean sibling worktree from `87cf587`; never execute the migration in
the inherited worktree. Record a collision ledger partitioned into staged,
unstaged, untracked, submodule, and generated-overlay inputs. The only approved
dirty imports are the staged `.gitignore` hunk that makes `.omx/**`
operator-local and the generated OMX block in root `AGENTS.md`. Explicitly
exclude the unrelated unstaged `.codex` hunk, the dirty LitKG checkout, and all
other user changes.

Hash the original staged diff, unstaged diff, planned-path untracked manifest,
submodule status, and OMX block; compare those hashes again at handoff. Capture
baseline counts and consumer/replacement ledgers for generated context, LitKG,
backlog, skills, hooks, and tracked runtime state. Treat exactly these as active
guides: root `AGENTS.md`, `aria_nbv/AGENTS.md`,
`aria_nbv/aria_nbv/data_handling/AGENTS.md`,
`aria_nbv/aria_nbv/rollouts/AGENTS.md`,
`aria_nbv/aria_nbv/rri_metrics/AGENTS.md`,
`aria_nbv/aria_nbv/vin/AGENTS.md`, and
`docs/AGENTS.md`; archive/runtime copies are not active guidance.

Run a bounded Graphify capability spike before designing WP4, and promote the
approved content-addressed plan/test handoff described above before any
implementation package starts.

WP0 also creates the sole coordination root:
`.omx/tmp/agent-scaffold-migration/<plan-sha256>/`, where `plan-sha256` hashes
the approved plan, test spec, and ordered approval records. Each producing lane
writes `wpN/manifest.json` as canonical key-sorted JSON with `package`,
`baseline`, `plan_sha256`, `owned_paths`, `shared_edit_proposals` (path, action,
preimage SHA-256, patch SHA-256, consumer), `artifacts` (relative path and
SHA-256), `local_checks`, and `lane_sha256`. `lane_sha256` hashes the manifest
without that field plus all artifact hashes. Consumers verify plan/lane hashes
before applying anything. WP8 deletes the coordination root after final evidence
is embedded in the durable handoff; only explicitly promoted decisions/tests/
fixtures remain tracked.

**Acceptance:** the sibling worktree is clean at the recorded commit; the
collision ledger identifies every approved and rejected input; all five
original-state hashes are unchanged; the seven guide paths resolve; every
planned deletion has a replacement owner or zero-consumer evidence; and the
promoted handoff hashes match the approved RALPLAN artifacts.

### WP1 — Runtime, privacy, lifecycle, and external-tool boundary

**Dependencies:** WP0. **Parallel wave 1.**

Own `.gitignore`, tracked client hook/config examples, plugin wiring, the
post-commit hook in its entirety, debrief nudge, `CLAUDE.md`, and repo-only
MemPalace/code-index wiring. Make
`.omx` and local tool state operator-local; remove automatic memory/backlog/KG/
Graphify/transcript mutation; retain explicit checks and event-triggered debriefs.
The terminal hook contract is deletion: remove the tracked
`scripts/git_hooks/post-commit`, emit a reviewed `Makefile` installer-target
removal manifest for WP8, install no replacement, and leave any unrecognized
user-local Git hook untouched.

**Package-local acceptance:** `git ls-files` and scoped `rg` over WP1-owned
guidance, config, scripts, hooks, and runtime wiring—excluding all historical
roots—prove there is no tracked `.omx`/runtime/local config/mined transcript,
hidden session/commit mutation, or active absolute home path in those owned
surfaces. The tracked post-commit hook is absent, the hashed WP1 manifest contains
the installer-target proposal plus repository-wide residual findings and
historical-allowlist candidates for WP5/WP8, no matching installer-owned hook
exists in the clean sibling worktree, and package-local core checks pass under
an isolated `PATH`/config with Graphify, LitKG, code-index, MemPalace, and OMX
absent. WP5/WP8 own later repository-wide cleanup, allowlist application, and
final absence gates.

### WP2 — Lossless agents-DB retirement

**Dependencies:** WP0. **Parallel wave 1.**

Validate and freeze the four journals. Git history at baseline `87cf587` is the
immutable archive; do not create a duplicate TOML archive. Migrate the 87 active
records into `.agents/backlog.md` by first computing the union of every baseline
TOML key. Preserve every serialized value—including `id`, `title`, `description`,
`type`/kind, status, priority, dependencies, `issue_ids`, labels, context,
references, implementation notes, acceptance, verification evidence, `loc_min`,
`loc_expected`, `loc_max`, `resolved_at`, `resolution_note`, and
`resolved_from`—or record an explicit per-record, per-field rationale. Classify all
61 resolved records as either conversion-relevant references that remain linked
or historical-only records retrievable with `git show 87cf587:<path>`; prune the
latter only after the classification is reviewed.

Write the 61-record classification to
`wp2/resolved-classification.jsonl`; every row contains ID, source path, original
status, disposition (`linked_reference` or `historical_only`), retained
references, rationale, and canonical source-record SHA-256. It is hashed in the
WP2 manifest and embedded in final migration evidence before temporary cleanup.

Provide plain-file recipes for search, rank, edit, resolve, and historical
retrieve. Emit reviewed duplicate-ID and mapping checker specifications for WP8;
do not edit the common checker in this lane or create a replacement CLI. Delete
the agents-DB CLI, skill, wrappers, and commands
only after the gate passes. Do not create GitHub issues. If lossless conversion
cannot be proven, retain the TOML journals and narrow their policy instead.

The canonical `.agents/backlog.md` schema is deterministic:

````markdown
## Active
<a id="backlog-<lowercase-id>"></a>
### <ID> — <title>
- [ ] <one-line description>
```json
{"id":"...","title":"...", ...all baseline keys..., "migration_rationale":{}}
```
````

The JSON object is the lossless record, UTF-8, one key-sorted object per fenced
block; the checkbox/title are a human projection checked against `id`, `title`,
`description`, and status. Dependencies and `issue_ids` are sorted arrays of
stable IDs and must resolve to anchors or reviewed historical Git references.
Preserve baseline status verbatim. Valid transitions are
`todo|open → in_progress|blocked|resolved`,
`in_progress → blocked|resolved`, and
`blocked → todo|open|in_progress|resolved`; `resolved` is terminal. Resolving
requires ISO-8601 `resolved_at`, non-empty `resolution_note`, and
`resolved_from`. Resolved records move to `## Resolved references`; they remain
while an active dependency/reference targets them, otherwise their baseline
record is retrieved from Git. `migration_rationale` maps each omitted or
normalized source key to a non-empty explanation. Search/rank/edit/resolve
recipes operate on these blocks; WP8's stdlib checker is the only parser.

**Package-local acceptance:** 87 active and 61 resolved inputs reconcile one-to-one; every
source field has a recorded destination or explicit historical-only rationale;
duplicate IDs fail; representative search/rank/edit/resolve/retrieve smokes
pass; Git retrieves each frozen input; and no record is lost or silently
reclassified.

### WP3 — LitKG removal and lightweight literature evidence

**Dependencies:** WP0. **Parallel wave 1.**

Record the LitKG gitlink commit and upstream URL from the clean baseline; do not
import or normalize the dirty checkout. Remove the gitlink/config/two skills/KG
generated state/scripts/commands/MCP/Neo4j integration while retaining
BibTeX, `sources.jsonl`, curated QMD, local TeX/PDF, and historical provenance.
The complete hook terminal contract already belongs to WP1. Emit only shared
`Makefile` deletions for WP8 rather than editing that shared surface in this lane.

Separate active stale-name scans from a narrow historical allowlist. Emit a
reviewed deletion manifest for stale generic-skill/LitKG contracts, Matt-Pocock
manifests, and adapter mappings; WP5/WP8 apply it on their owned surfaces.
Replace machine claim checking with a small validator for
duplicate/missing bibliography or source keys and missing source paths. Replace
human claim review with a fixed checklist specification: citation resolution →
authoritative section inspection → exact locator and calibrated wording →
curated-page consistency → touched-surface render. The checklist is owned by an
`aria-docs` reference and `docs/AGENTS.md`; WP3 emits the reviewed specification,
WP7 performs those shared-owner edits, and WP5 makes `plan-grill` point to it for
advisor-facing work.

**Package-local acceptance:** a fresh clone/submodule smoke does not require the
removed gitlink; WP3-owned active surfaces contain no LitKG/Rust/Neo4j/Ollama/
embedding/MCP requirement; the machine validator has positive/negative fixtures;
and the hashed WP3 manifest contains repository-wide residual findings,
historical-allowlist candidates, deletion manifests for WP5/WP8, and the claim-
checklist/direct-TeX/render specification for WP7. WP5/WP8 own repository-wide
cleanup, allowlist application, and integrated absence; WP7 owns the
representative human claim result.

### WP4 — Discovery, generated-context deletion, UML, and Graphify

**Dependencies:** WP0. **Parallel wave 1.**

Rewrite `aria-nbv-context`; delete generated context except glossary JSONL,
custom AST inventories, snapshots, wrappers, and default Make paths; keep direct
QMD/Typst outline tools; retain one explicit
scoped UML command; remove the vendored Graphify skill in favor of upstream
Graphify 0.9.9. List shared `Makefile` changes for WP8 rather than editing it.

Do not modify upstream Graphify. Add at most a 150-LOC atomic provenance/status
sidecar because 0.9.9 has no named profiles or reliable dirty/provenance status.
The sidecar records profile manifest, absolute scan root, `git -C <root>` HEAD,
config hash, Graphify version, graph hash, covered paths, dirty covered paths,
and completion only after exit 0 plus valid graph. Status reads the sidecar and
graph only; it never refreshes.

Define three isolated profiles:

- default production/design graph at `graphify-out/`;
- scaffold graph at `graphify-out/profiles/scaffold`, covering the seven active
  guides, active `.agents` references/state/backlog, skill metadata, hooks, and
  scaffold checker/fixtures;
- selected-PDF graphs at `graphify-out/literature/<selection-hash>`, built from
  an explicit staging corpus.

Use absolute `GRAPHIFY_OUT` during builds because `--out` alone can still write
root cache; query/path/explain use explicit `--graph`. Dirty uncovered paths are
allowed but reported; dirty covered paths fail currentness. Wrong root, commit,
config, tool version, graph hash, incomplete build, absent tool, or absent
sidecar fails closed to direct lookup or an explicit operator refresh.

**Package-local acceptance:** fixtures cover wrong-root, stale commit, changed config/version/
graph hash, incomplete/failed build, dirty-covered, dirty-uncovered, current,
and no-tool states; status is proven read-only; profile outputs/caches do not
collide; context output contains owner, guide, route, freshness, verification,
and next workflow; no comprehensive generated handbook remains; and exact lookup
plus CI succeed without Graphify.

### WP5 — Root routing, scaffold contract, and core skill portfolio

**Dependencies:** package-local accepted WP1–WP4 outputs and WP6 owner/test
migration; downstream integration gates are not prerequisites.

Own only the ARIA prefix of root `AGENTS.md`, `aria_nbv/AGENTS.md`, source-order
and skill-style references, non-doc retained skills except
`aria-nbv-context/**` (owned by WP4), and routing fixtures.
Preserve the OMX block byte-for-byte; fold unique preflight rules into root once;
route to one primary skill plus a second only for crossed boundaries; rewrite
the style guide around `writing-great-skills`; delete generic skills; finish
with an evidence-backed 7–9 local skills; keep external generic skills
user-installed/non-authoritative.

Replace fixtures with: task, primary owner/capability, required evidence,
forbidden route/tool class, expected handoff, and external-evidence policy. Use
exact skill names only for true single-owner capabilities.

**Package-local acceptance:** invocation rows justify every WP5-owned retained
skill; WP5-owned active manifests/references contain no external generic skill
as authority or retired dependency; root and WP5-owned skill budgets pass; and
each WP5-owned skill has positive, adjacent-negative, and fallback/handoff
coverage. The WP5 lane manifest emits the candidate catalog/range and residual
findings. WP8 alone assembles WP4/WP5/WP7 outputs and enforces final 7–9 catalog,
all invocation rows, global budgets, and repository-wide retired-dependency
absence.

### WP6 — Scientific/domain invariant migration

**Dependencies:** WP0. **Parallel wave 1.** Must finish before WP5 deletions.

Build a machine-readable sentence ledger for the three retiring cross-cutting
skills. Each row contains source skill/line, normalized rule, destination owner,
test or fixture, and retention/deletion rationale. Move unique entity/RRI,
geometry, and Zarr rules to the four existing nested guides, `GOTCHAS.md`,
source/docstrings, or focused tests; do not add a guide without repeated
ambiguity evidence.

Emit reviewed routing-fixture cases for tasks that previously named deleted
skills, including geometry work outside Rerun and outside the four nested
packages; WP5 performs the shared fixture edits. Name and run
the regression groups for hard invalidity/reason masks, actor/critic/oracle
visibility, entity selection/target-conditioning, camera/pose/projection/frame
boundaries, and Zarr store round-trip/version/chunk-codec behavior.

The baseline commands are fixed and may be extended only by the sentence ledger:

```bash
cd aria_nbv && uv run pytest tests/rollouts/test_counterfactuals.py tests/data_handling/test_target_selection.py tests/rri_metrics/test_oracle_rri_chunking.py
cd aria_nbv && uv run pytest tests/pose_generation/test_align_to_gravity.py tests/pose_generation/test_orientations.py tests/rendering/test_depth_backprojection_conventions.py tests/vin/test_geometry_helpers.py tests/vin/test_pose_encoding.py
cd aria_nbv && uv run pytest tests/rollouts/test_zarr_store.py tests/data_handling/test_vin_offline_store.py tests/rollouts/test_dataset_writer.py
```

**Package-local acceptance:** every source sentence has one destination or deliberate-deletion
rationale; every retained rule has a reachable owner and named test/fixture;
all named scientific regression groups pass; the hashed WP6 manifest contains
deleted-skill routing cases for WP5; and guide budgets pass. WP5 owns routing-
fixture implementation/passage, and WP8 owns the integrated gate.

### WP7 — Unified docs skill, Python API docs, and README curation

**Dependencies:** package-local accepted WP3 and WP6 outputs. May run alongside WP5 with exclusive
files: `docs/AGENTS.md`, `aria-docs/**`, `python-docstrings/**`, documentation
contract checker/fixtures, curated README/API-doc surfaces, and the two semantic
claim fixtures named below.

Merge the three docs skills into `aria-docs` with branch references and the
fixed claim-evidence checklist from WP3; compact `python-docstrings`; enforce
contract tiers for non-trivial modules, public Quartodoc entities/methods, and
public DTO/config/state fields while keeping private findings advisory. Build a
README keep/merge/delete manifest with named human consumers and value, then
curate the 952-line data-handling README to durable operator value instead of a
parallel API/symbol/agent-policy matrix.

**Acceptance:** Quarto/Typst/Mermaid/claim branches load only relevant references;
the claim fixture passes; docstring checker negative fixtures reject trivial
narration; Quartodoc/Quarto/Typst/Mermaid checks pass; and every retained README
section has an explicit consumer/value rationale while stale symbol matrices do
not remain.

### WP8 — Permanent validation, CI, and final simplification

**Dependencies:** all prior packages; serial integration.

Own the shared `Makefile`, CI workflows/path filters, verification matrix, common
scaffold checker/tests, adapter synchronization, and final stale-reference scan.
Apply only the reviewed Makefile change manifests from WP1/WP3/WP4. Use the current
audit only as a migration guard, then replace it with a focused structural
checker targeted at ≤300 production lines plus tests. Permanently check the
seven explicit active guide paths, 7–9 skill range, names/descriptions/context
pointers/budgets, fixture schema, forbidden tracked runtime/absolute paths, and
active-vs-historical retired-name rules. Exclude archive/runtime guide copies.

Add the checker/self-tests to `make ci`; remove LitKG, agents-DB, and
generated-context CI dependencies; extend workflow path filters; synchronize
only the repository's actual adapter catalog. Require a named architectural
review that the final diff did not add a new truth surface, backend, service,
automatic mutation, or replacement framework.

Permanent scaffold fixtures live under `tests/scaffold/`. WP7 exclusively
authors `tests/scaffold/fixtures/claim-check-vin-nbv.md` and
`tests/scaffold/fixtures/claim-check-vin-nbv-review.json`; WP8 validates but does
not edit them. The reviewed
historical allowlist is `tests/scaffold/historical_allowlist.toml`, with entries
`pattern`, `path_globs`, `reason`, and `owner`; `path_globs` may target only
`.agents/memory/history/**` or `.agents/archive/**`. The representative semantic
fixture is `tests/scaffold/fixtures/claim-check-vin-nbv.md`; its human verdict is
`tests/scaffold/fixtures/claim-check-vin-nbv-review.json` with reviewer role,
date, citation key, exact locator, entailment verdict, calibrated wording, and
render command.

`tests/scaffold/run_isolated_core_checks.py` creates temporary HOME/XDG/cache/
output roots, a PATH of logging wrappers around only required executables, and a
`sitecustomize.py` Python socket/write audit hook. Wrappers reject remote/network
subcommands and all ordinary network clients are absent. It snapshots the
repository plus controlled HOME/XDG/cache/output roots before/after, and runs
`make scaffold-check`,
`make check-agent-memory`, and direct context fallbacks with all optional tools
absent. It fails on any Python socket attempt, proxy-aware connection, write in
the observed roots outside declared temporary outputs, repository hash change,
or unexpected cache file. HTTP(S)
proxy variables point to a local trap listener as a second network sentinel;
the listener log must remain empty. This proves the allowed core-command path,
not OS-wide absence of arbitrary raw sockets or writes outside observed roots.

**Acceptance:** the full test spec is green; checker positive/negative self-tests
prove the seven-path and 7–9-range contracts; before/after metrics show
reductions in skills, descriptions, hot-path LOC, scripts, targets, hooks,
submodules, and required services; adapter synchronization is exact; and the
architectural review finds no new dependency/service/backend/hidden mutation/
truth surface.

## Dependency graph

```text
WP0
 ├─ WP1 runtime/privacy ───────────────┐
 ├─ WP2 backlog migration ────────────┤
 ├─ WP3 LitKG/literature ───────┐     │
 ├─ WP4 context/Graphify ───────┤     ├─ WP5 root/routing/core skills ─┐
 └─ WP6 domain invariants ──────┼─────┘                                │
                                └─ WP7 docs/docstrings ─────────────────┤
                                                                       └─ WP8 CI/integration
```

Parallel lanes require exclusive files. Shared `Makefile`, root CI,
`verification_matrix.md`, and final stale-reference cleanup belong to WP8.

### Exclusive ownership manifest

| Package | Exclusive edit surface |
|---|---|
| WP1 | `.gitignore`, lifecycle/client hooks and examples, runtime/privacy wiring, `CLAUDE.md`; `Makefile` installer-removal manifest only |
| WP2 | backlog/journal migration surfaces and agents-DB deletion set; checker specification only |
| WP3 | LitKG gitlink/config/skills/scripts/generated KG/literature validator and claim-checklist specification; `Makefile` manifest only |
| WP4 | context skill/references, Graphify profile/provenance sidecar, generated-context/UML tooling; `Makefile` manifest only |
| WP6 | four nested package guides, domain `GOTCHAS.md`, scientific tests/fixtures, sentence ledger; routing-fixture specification only |
| WP5 | ARIA root prefix, `aria_nbv/AGENTS.md`, source order/style, routing fixtures, non-doc skills except WP4-owned `aria-nbv-context/**` |
| WP7 | `docs/AGENTS.md`, `aria-docs`, `python-docstrings`, doc checker/fixtures, README/API-doc curation, named semantic claim fixture/review |
| WP8 | `Makefile`, CI, verification matrix, common checker/tests except WP7-owned semantic fixtures, adapter sync, final catalog/stale scans |

Any discovered shared-file collision is escalated to WP8 or returned to
planning; lanes do not silently broaden ownership.

## Risks and mitigations

1. **Hidden consumer of a deleted subsystem.** Require consumer ledger,
   migration guard, stale-reference scan, and replacement smoke before deletion.
2. **Fewer skills but worse routing.** Require independent-reach matrix,
   leading-word descriptions, positive/negative/fallback fixtures, and invariant
   migration before deletion.
3. **Dirty-branch contamination or conflict-heavy integration.** Use exact-HEAD
   sibling worktree, exclusive ownership, path-scoped integration, and compare
   final diff to baseline and approved plan.
4. **Manual claim checking weakens evidence.** Machine checks cover only
   duplicate/missing keys and source paths; a named human review fixture covers
   semantic entailment, exact locators, calibrated language, curated-page
   consistency, and touched-surface rendering.
5. **Temporary migration guard becomes permanent machinery.** Put deletion of
   the 1,038-line audit and temporary allowlists in WP8 acceptance criteria.

## ADR

### Decision

Adopt a 7–9-skill thin-dispatcher scaffold, provisionally the nine-skill
portfolio above; remove LitKG, generated context,
agents-DB machinery, canonical code-index/MemPalace wiring, vendored external
skills, and hidden lifecycle mutation; retain Graphify only as provenance-checked
optional evidence.

### Drivers

Predictable routing/source authority; lower maintenance/context load; preserve
ARIA-specific scientific and operational behavior.

### Alternatives considered

Harden everything; collapse to seven skills; keep LitKG optional-but-wired;
track selected `.omx` trees; replace LitKG with another claim/graph engine.

### Why chosen

The provisional nine are the smallest currently evidenced target that preserves
every independently reachable ARIA workflow while deleting generic or
infrastructure-owned behavior. Seven remains viable only if WP0/WP6 demonstrate
that docstrings and/or advisor-facing planning have safe owner routes without
premature completion; the checker enforces a range rather than freezing names.

### Consequences

Literature checks use explicit source inspection; backlog editing becomes simpler
but less queryable; stale Graphify falls back instead of refreshing implicitly;
guides/docstrings/tests carry more responsibility; OMX plans require promotion.

### Follow-ups

Measure routing quality on real tasks; split a skill only on observed collision
or premature-completion evidence; revisit external issue publication separately.

## Available agent types and staffing

Available roles include `explore`, `researcher`, `dependency-expert`, `planner`,
`architect`, `debugger`, `executor`, `test-engineer`, `verifier`, `critic`,
`code-reviewer`, `git-master`, `writer`, and `code-simplifier`.

- `git-master` (high): clean worktree and integration history.
- `explore` (low/medium): WP0 ledgers.
- four `executor`/`team-executor` lanes (medium/high): WP1–WP4, then WP6.
- `test-engineer` (high): WP6/WP7 regression and checker design.
- `writer` (high): WP5/WP7 guidance and skill consolidation.
- `researcher` (high): only if local Graphify/Quartodoc evidence is insufficient.
- `code-simplifier` (high): final helper/checker pruning.
- `code-reviewer` then `verifier` (high): integrated diff and evidence gate.
- `debugger` (high): only for failed migration checks.

## Goal-mode follow-up suggestions

Use **`$ultragoal` + `$team`**. Ultragoal owns the durable goal ledger and
dependencies; Team owns parallel execution waves and returns checkpoint-ready
evidence. Suggested goals are G0=WP0, G1–G5=WP1/WP2/WP3/WP4/WP6,
G6–G7=WP5/WP7, G8=WP8.

Example clean-worktree launch hint:

```bash
omx team 4:executor "Execute the approved ARIA-NBV scaffold plan. Respect exclusive WP file ownership, preserve the inherited dirty worktree, and return package-local verification evidence."
```

Team proves each work package's acceptance criteria and terminal task state;
the integration owner runs the full test spec; `code-reviewer` reviews the whole
diff; `verifier` checks baseline provenance and contamination; only then is Team
shut down and Ultragoal checkpointed complete.

`$ralph` is only a fallback for one narrow persistent final verification/fix
loop, not the default ledger.

## Stop conditions

Return to planning if a deletion lacks replacement evidence; backlog
reconciliation fails; bibliography/source validation fails; Graphify cannot fail
closed on stale evidence; a scientific invariant lacks an owner; the execution
worktree is dirty; the target falls outside 7–9 skills or adds a service/backend;
or Architect/Critic do not approve.

## Consensus changelog

- Initial Planner draft created from the inherited transcript, decision record,
  three reviews, current HEAD evidence, and `writing-great-skills`.
- Architect iteration 1 converted the exact-nine proposal into an invocation-
  justified 7–9 range; added dirty-input isolation, content-addressed handoff,
  explicit guide/ownership manifests, lossless backlog/LitKG contracts,
  Graphify 0.9.9 provenance design, sentence-level invariant migration, and
  stronger observable acceptance criteria.
- Architect iteration 2 corrected guide paths, eliminated three cross-lane edit
  overlaps through reviewed specifications, made backlog mapping key-union and
  value complete, and scoped absolute-path checks to active surfaces.
- Critic iteration 1 removed the remaining hook/context ownership overlaps;
  closed O10–O14; fixed the backlog serialization and resolution schema;
  separated read-only planning evidence from repository imports; and named
  concrete tests, fixtures, allowlists, and network/write sentinels.
- Architect iteration 3 assigned direct TeX exclusively to WP7, preserved the
  baseline `todo`/`open` statuses in an explicit transition graph, and replaced
  removed-hook behavior checks with an absence/no-replacement contract.
- Architect iteration 4 moved the shared `Makefile` installer-target edit from
  WP1 to a reviewed manifest applied by WP8.
- Critic iteration 2 split package-local and integration acceptance; removed the
  last ownership ambiguity; defined content-addressed lane artifacts and cleanup;
  added the resolved-record classification ledger; and narrowed isolation claims
  to observable sentinels.
- Architect iteration 5 removed WP1/WP3's remaining dependency on WP8 by making
  their scans owner-local and their cross-repository findings hashed outputs.
- Critic iteration 3 moved final catalog/global-absence enforcement from WP5 to
  WP8 and assigned semantic claim-fixture authorship exclusively to WP7.
- Final Critic review approved the Architect-approved plan with no blocking or
  high-severity findings.
