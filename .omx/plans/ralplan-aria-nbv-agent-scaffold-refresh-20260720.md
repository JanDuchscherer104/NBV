---
kind: plan
task_slug: aria-nbv-agent-scaffold-refresh
baseline_commit: 57457ec31e0d3b56da7cb6ebdbb9fde6166de434
revision: 2026-07-22
---

# RALPLAN: ARIA-NBV Agent Scaffold Refresh

**Branch:** `docs-update-latest`
**Context:** `.omx/context/agent-scaffold-refresh-20260720T110000Z.md`
**Test specification:** `.omx/plans/test-spec-aria-nbv-agent-scaffold-refresh-20260720.md`
**Supersedes:** `.omx/plans/ralplan-aria-nbv-agent-scaffold-simplification-20260714.md`
**Accepted predecessor plan digest:** `637b9cccb5673c5be33f96e185030f916156cf0d49520b0d39ea4a5d18784827`
**Accepted predecessor handoff:** `.omx/plans/ralplan-aria-nbv-agent-scaffold-simplification-20260714-handoff.json`
at SHA-256 `c2c9c9381e40fd2f63bfe7343cd2f56120437aa3e46f9a740ab79b250446d61e`
**Earlier scaffold-refresh revision digest:** `c66c907d98c55f9f3ffc85108c3fda7e5c7ba50869d6801fa823edb4ed96772b`

## Outcome

Replace the layered agent scaffold with a smaller source-owned system:

- one tracked, partitioned Graphify graph provides code, scaffold, thesis, and
  literature navigation;
  > Every piece of knowledge must have a single, unambiguous, authoritative representation within the system.
- exact source files remain authoritative and Graphify freshness is explicit;
- accepted OMX planning bundles are tracked through a compact promotion
  registry, superseded bundles remain tracked in an archive, and drafts and
  runtime state remain local;
- selected pinned Matt Pocock skills provide generic engineering disciplines;
- nine ARIA-local skills retain only project-specific operational workflows;
- `.agents/memory/state`, LitKG, and broad generated-context machinery are
  removed after evidence-led migration;
- active scaffold source LOC and model-visible skill-description bytes decrease.

This is a scaffold migration. It does not change Python package behavior,
scientific semantics, thesis claims, data schemas, checkpoints, or runtime
configuration formats. Implementation starts in a clean sibling worktree based
on the recorded baseline or an explicitly reviewed descendant. Working-tree
changes are excluded from the baseline. The existing scaffold-refresh worktree
is quarantined as non-authoritative implementation evidence until this successor
plan, its test specification, reviews, and handoff are accepted together.

## Successor Status

The accepted predecessor handoff binds its complete 17-artifact manifest,
including the accepted predecessor plan digest above. The earlier
scaffold-refresh revision also received local reviews but is not the accepted
predecessor bundle and transfers no authority to this revision. This 2026-07-22
successor incorporates the post-baseline `measured-autoresearch` skill and the
resolved cross-artifact grill decisions. Regenerate the test specification,
Architect review, Critic review, and handoff against this plan's new digest
before implementation resumes.

## Supersession Matrix

| Earlier decision | Successor disposition | Rationale |
| --- | --- | --- |
| Optional untracked Graphify profiles | Superseded by one tracked graph with four freshness partitions | One navigation surface with partition-local trust is preferred over profile federation. |
| Default or tracked Graphify wiki | Rejected; allow ignored on-demand export only | A generated prose projection duplicates source owners and increases stale-surface risk. |
| No automatic Graphify mutation | Superseded by a two-speed Graphify-only hook | Deterministic code refresh is automatic; semantic inference remains explicit and reviewable. |
| All `.omx` artifacts are local | Superseded by registered current bundles in native OMX paths and archived superseded bundles | Accepted decision evidence must survive fresh checkout; runtime and drafts remain local. |
| Delete the agents DB | Deferred; retain TOML records, CLI, skill, and CI validation | A second backlog migration would expand scope and remove a currently valid owner. |
| Seven-to-nine provisional skill range | Resolved to exactly nine retained ARIA skills | `measured-autoresearch` is a required ARIA operational sidecar. |
| Retain `diagnose-aria` and `counterfactual-rollout-planner` | Superseded after owner-led migration | Generic diagnosis comes from the pinned external skill set; rollout contracts move to package and thesis owners. |
| Event-triggered-only debriefs | Rejected for this migration | Preserve the current agents-DB and non-trivial-work debrief contract. |
| Stable manual `context_map.md` | Rejected | Fresh Graphify plus source order and exact-source fallback replace a stale hand-maintained route table. |
| Scoped UML operator command | Retained | It remains an explicit ignored visualization, never authority or a default generation step. |
| New repository-wide docstring checker | Deferred | Keep `python-docstrings` and Quartodoc validation without expanding this scaffold migration into broad source edits. |
| Package README inventory and curation | Deferred with policy retained | READMEs may orient humans but may not duplicate symbols, generated inventories, or agent routing. |
| Direct TeX/source claim verification | Retained and strengthened | LitKG removal must preserve source-backed advisor-facing claim checks without a replacement engine. |

## RALPLAN-DR

### Principles

1. **One fact, one owner.** Source, tests, package guides, thesis pages, and
   accepted decisions own truth; graphs and skills route to them.
2. **One graph, partitioned trust.** A unified graph supports cross-domain
   navigation while partition revisions prevent stale evidence from leaking
   into claims.
3. **Independent reach earns a skill.** ARIA skills survive only for distinct
   project-specific operational workflows.
4. **Promotion makes planning durable.** Accepted OMX bundles are immutable,
   indexed decision evidence; drafts and runtime state remain local.
5. **Deletion follows closed evidence.** Every removed capability or statement
   has an owner, a verified replacement, or an explicit retirement rationale.

### Decision drivers

1. Reduce default context load and routing collisions.
2. Make architecture and planning lookup reproducible from a fresh checkout.
3. Remove stale mirrors and unused infrastructure without losing ARIA-specific
   scientific, geometry, data, and operational safeguards.

### Alternatives considered

#### Repair the existing scaffold

Keep twenty-one ARIA skills, four state journals, broad generated context, LitKG,
and the current Graphify policy. This has the lowest migration cost but preserves
the maintenance and source-authority failures that triggered the refactor.

#### Maintain several Graphify graphs and temporary LitKG parity

Separate code, scaffold, and literature graphs isolate freshness domains and a
read-only LitKG transition lowers rollback risk. This was rejected because it
adds profile/federation machinery, preserves duplicate retrieval systems, and
conflicts with the explicit decision to remove active LitKG.

#### Chosen: one partitioned graph and source-owned scaffold

Use one graph with independent partition revisions, exact-source fallback,
tracked canonical outputs, gated upstream skills, and nine operational ARIA
skills. This gives agents one navigation surface without treating the graph as
authority or preserving redundant context systems.

## Authority And Routing

Within an accepted planning bundle, authority is role-specific: the plan owns
decisions, the test specification owns acceptance criteria, context artifacts
provide source-backed evidence only, reviews bind exact artifact hashes, and the
handoff binds the accepted bundle and execution status. None of these roles
overrides current implementation or scientific source owners.

The final authority order is:

1. Root and nearest `AGENTS.md` invariants.
2. Runtime source, tests, configs, schemas, and package guides.
3. Thesis roadmap/questions, glossary, bibliography, and public docs.
4. Accepted OMX planning bundles for approved future work and archived bundles
   for superseded decision provenance.
5. Fresh Graphify evidence for navigation and impact analysis.
6. Current debriefs, historical debriefs, and Git history for task evidence and
   provenance only.

`.agents/memory/state` and generated context are removed from the authority
order. Graphify results and OMX artifacts never override current implementation
or scientific source owners.

Retain the current debrief paradigm: non-trivial work leaves a validated debrief
and agents-DB workflows may route episodic evidence there. This migration does
not replace it with an event-triggered-only policy.

`AGENTS.md` contains invariants, source precedence, and routing classes. It does
not enumerate the complete installed skill catalog. Machine-readable skill
activation belongs in project Codex configuration.

## Unified Graphify Architecture

### Pin and canonical artifacts

Pin:

- package: `graphifyy==0.9.22`;
- upstream commit: `abff1b1ca4052fcf9d955c5f6a034088723f4536`.

Track only canonical, portable output:

- `graphify-out/graph.json`;
- `graphify-out/manifest.json` and deterministic partition provenance;
- `graphify-out/GRAPH_REPORT.md`.

Ignore caches, `cost.json`, rendered HTML, generated wiki Markdown, query logs,
agent answers, reflections, learned query expansions, historical output
snapshots, converted sources, temporary chunks, extraction intermediates, and
machine-local interpreter pointers. An operator may generate an ignored wiki on
demand; it is never canonical or required.

Canonical graph content is source-derived only. Structural extraction produces
`EXTRACTED` edges; source-based resolution or semantic extraction may produce
`INFERRED` or `AMBIGUOUS` edges. Every edge records a categorical `origin`
(`EXTRACTED`, `INFERRED`, or `AMBIGUOUS`) separately from a numeric
`confidence_score`, exact corpus source locator(s), source content digest(s),
endpoint provenance, partition revision, extraction-configuration digest, and
tool version. Canonical generation rejects inferred or ambiguous edges whose
only provenance is a query, answer, reflection, log, runtime state, cache, or
non-corpus path. Agents use inferred edges to discover likely relationships,
then open the exact source owner before making implementation or scientific
claims. Query answers and agent-authored lessons never feed back into canonical
graph state.

Semantic extraction is proposal generation, not a deterministic build input.
An explicit graph-sync pass reviews proposed semantic edges, canonicalizes the
accepted records, and stores them in `graph.json` with the source digests above.
Clean-checkout regeneration never calls an LLM or provider: it deterministically
rebuilds structural content and reuses only accepted semantic records whose
source digests still match. Changed or missing sources invalidate those records
until a new explicit graph-sync review. Canonical JSON uses UTF-8, sorted object
keys, stable array ordering by persistent IDs, normalized finite numeric values,
and no mtimes, provider request IDs, timestamps, or unordered filesystem input.

### Source partitions

The graph contains four tagged partitions. Membership uses this first-match,
path-explicit classifier, so every included file has exactly one owner:

1. `literature`: `docs/contents/literature/**`,
   `docs/literature/sources.jsonl`, and manifest-selected section-bearing text
   under `docs/literature/tex-src/**`;
2. `scaffold`: root/nested `AGENTS.md`, retained `.agents` owners, registered OMX
   bundles, and scaffold scripts/tests, including guidance nested under `docs`;
3. `thesis`: remaining active `docs/**` Quarto/Typst, glossary, bibliography, and
   public documentation paths, excluding generated/reference/site outputs;
4. `code`: production code, tests, package metadata, active configs, package
   guides, and implementation docs not matched above.

An allowlist/denylist manifest makes generated, binary, archive, and inactive
paths explicit. Overlap or unclassified included paths fail validation.

| Partition    | Included sources                                                                                          | Refresh mode                                       |
| ------------ | --------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| `code`       | production code, tests, package metadata, active configs, package guides and implementation docs           | incremental post-commit plus explicit full rebuild |
| `scaffold`   | root/nested guidance, retained skills/references, agents DB, current/superseded OMX bundles, scaffold scripts/tests | explicit semantic refresh                     |
| `thesis`     | active Quarto/Typst, glossary, bibliography and public documentation                                      | explicit semantic refresh                          |
| `literature` | ARIA literature syntheses and manifest-selected section-bearing TeX/text                                  | explicit semantic refresh                          |

`docs/literature/sources.jsonl` is the literature paper allowlist. Include each
paper's section-bearing textual sources. Exclude figures, binaries, styles,
templates, generated files, and bundled bibliographies that do not represent
the paper's section structure.

Each node and edge records its source partition. Cross-partition bridge edges
record the partition revisions of both endpoints. Code nodes also carry a
`production`, `test`, `config`, or `guide` role. Ordinary queries rank production
owners first while retaining tests and active configs as supporting contract
evidence.

### Deterministic freshness

For each partition compute:

```text
partition_revision = sha256(
  sorted_input_manifest_digest
  + graphify_version
  + extraction_config_digest
  + graph_schema_version
  + semantic_mode
  + accepted_semantic_records_digest
)
```

Canonical output contains no wall-clock extraction timestamp. A
`semantic_complete` flag is deterministic for the partition revision.

A partition is fresh when its current sorted input manifest and configuration
recompute to its recorded revision. A bridge edge is fresh only when both
endpoint partitions are fresh and its recorded endpoint revisions match.

Query behavior:

- search may omit stale-partition results but must report every excluded
  partition;
- an answer may use only remaining fresh evidence;
- `path`, `explain`, and claims requiring a stale node fail closed;
- cross-partition results require all used partitions and bridge edges to be
  fresh;
- failed graph preflight opens exact source owners through targeted discovery.

### Post-commit and graph-sync state machine

Use upstream-aligned two-speed refresh. The post-commit hook asynchronously
refreshes deterministic code structure, preserves unaffected inferred edges,
and marks touched semantic partitions stale. It does not stage, commit, amend
history, persist agent-generated graph memory, or launch semantic extraction.
Graph-only commits skip the hook.

The explicit graph-sync pass refreshes every stale semantic partition touched
by its source workpackage, validates source-derived provenance, and prepares the
canonical graph artifacts for review.

During branch authoring:

1. A commit `S` changing any graph-corpus path must have an immediate graph-only
   child `G` before another corpus-changing commit follows.
2. `G` changes only canonical graph artifacts and provenance, refreshes every
   partition touched by `S`, and records the canonical corpus-tree digest after
   `S`; commit identity is audit metadata only.
3. Mixed source/graph commits fail validation.
4. A single `G` covers a multi-partition `S`.
5. Later commits touching no graph-corpus path may follow `G` without another
   graph commit.
6. Rebase requires regeneration only when the canonical corpus-tree digest or
   extraction configuration changes.
7. Regeneration at the final tree must produce no canonical diff.

The source-plus-graph pair is one reviewable authoring workpackage. Only a
sync-valid head is pushed or opened as a PR. Merge and squash products are
validated by final corpus-tree digest and deterministic no-diff regeneration,
not by preserving authoring commit adjacency. A combined source/graph merge
commit is therefore valid only when its recorded corpus-tree digest matches the
merged tree; ordinary authoring commits remain split for reviewability.

## OMX Artifact Lifecycle

`.agents/omx_artifacts.toml` is the compact tracked registry. It records task,
bundle, role, path, source commit, content hash, status, supersession, and review
links.

Canonical bundle IDs are
`<task-slug>--<first-16-hex-of-handoff-sha256>`. `task-slug` must match
`^[a-z0-9]+(?:-[a-z0-9]+)*$`; the complete ID must match
`^[a-z0-9]+(?:-[a-z0-9]+)*--[0-9a-f]{16}$`. The registry stores and collision-
checks the full handoff SHA-256, so the path abbreviation cannot alias another
bundle. The accepted predecessor ID is
`aria-nbv-agent-scaffold-simplification--c2c9c9381e40fd2f`; the successor ID is
derived only after its final handoff hash exists. User-provided IDs, separators,
path components, uppercase, and normalization aliases are rejected.

Registry status and filesystem placement are separate concerns. The registry
status enum is exactly `current` or `superseded`; local drafts and rejected
output are not registry members.

Lifecycle:

```text
local draft --validate + review + explicit acceptance--> current
current --accepted successor--> superseded + tombstone
local draft --reject--> untracked/deleted
```

Path mapping:

| Registry status | Allowed placement |
| --- | --- |
| not registered | ignored native draft/runtime paths only |
| `current` | native role paths under `.omx/context`, `.omx/specs`, and `.omx/plans` |
| `superseded` | `.omx/archive/accepted-bundles/<bundle-id>/` with role-relative layout preserved |

Rules:

- drafts, rejected output, runtime state, logs, sessions, goals, and temporary
  reports remain ignored;
- context, plans, specs, reviews, and handoffs are tracked only as members of a
  current or superseded accepted bundle;
- promotion is an explicit command and atomically registers the complete bundle;
- promotion requires schema validation, required review verdicts, and explicit
  user acceptance;
- current and superseded accepted artifacts are immutable;
- current bundle members remain in their native OMX role paths, including
  `.omx/context`, `.omx/specs`, and `.omx/plans`; acceptance is registry state,
  not relocation into a synthetic acceptance directory;
- supersession requires an accepted successor, moves the predecessor intact to
  `.omx/archive/accepted-bundles/<bundle-id>/` while preserving its role-relative
  layout, and
  records a registry tombstone and successor link without deleting the archived
  payload;
- native OMX runtime archives elsewhere under `.omx/archive` remain ignored and
  unregistered; validators reject registered payloads outside the reserved
  `accepted-bundles` namespace and must not let native cleanup/archive operations
  mutate registered accepted-bundle payloads;
- CI rejects tracked or unignored unregistered payloads, broken links, path
  escapes, invalid source commits, hash drift, invalid transitions, credentials,
  and machine-local runtime identifiers;
- current and superseded accepted artifacts are decision evidence, not
  current-code truth.

WP1 has a one-time bootstrap transaction because no registry command exists
before WP1. After final acceptance, a seed exporter runs in an isolated temporary
directory and copies only artifacts listed by the exact accepted successor
handoff and the predecessor handoff's embedded 17-artifact manifest. It verifies
every source hash before writing a deterministic POSIX tar ordered by role/path,
with fixed uid/gid/mode/mtime and a manifest containing path, role, bytes,
SHA-256, baseline/source commit, review order, and intended `current` or
`superseded` status. The tar is named by its SHA-256; bootstrap recomputes that
digest and verifies the embedded handoff and artifact manifests before use. WP1
bootstrap accepts only this content-addressed seed; it never reads the dirty main
worktree or quarantined implementation worktree.

The two baseline-tracked pre-policy standalone plans are not accepted bundles and
do not enter the registry or accepted-bundle archive. WP1 records their exact
baseline hashes and dispositions, then untracks them in the bootstrap commit:

- `measured-autoresearch-sidecar.md` at SHA-256
  `b8ef95044b200d58d5ae4e96a9d1968fb6597c2eb630d379b2461e0d76ad45c6`
  is superseded by the retained implemented skill plus its tests;
- `thesis-method-registry-restoration-ledger.md` at SHA-256
  `e7a8d6600df470f1f388f107118f6dc0d45568786cc417111a0ab52269052c68`
  is completed historical planning evidence superseded by the current thesis
  sources and Git history.

No other tracked `.omx` path may remain outside the bootstrap manifests.

Bootstrap requires a clean Git index and no declared-path collision in the clean
baseline worktree. It does not create a commit or move a Git ref. The transaction
boundary ends after native successor paths, reserved predecessor archive, and
registry are published and a replacement index containing only the declared
staged additions is installed. Before mutation it resolves the worktree-specific
recovery directory with `git rev-parse --git-path omx-bootstrap`, then writes a
versioned journal and byte-for-byte backups there, including the original index
checksum and declared destination state. Files are prepared on the destination
filesystem, fsynced, and renamed into place; the replacement index is installed
last. On process restart, an incomplete journal triggers idempotent rollback
before any new operation. Success deletes the journal only after a
post-transaction hash and index-tree verification. Commit creation is a separate
normal Git step after validation.

History-aware validation binds each registered artifact to its later registration
commit and rejects content mutation in later commits. The only legal path change
is a byte-identical `current` to `superseded` move in the same commit that
registers its accepted successor and tombstone. Failure-injection tests cover
validation, copy, archive, registry-write, rename, index-install, and
post-verification failures
and prove no partial registry, archive, native-path removal, index mutation, or
ref movement. Because bootstrap never commits, there is no commit-boundary
rollback claim.

Native-operation isolation is pinned to `oh-my-codex@0.20.3` with npm integrity
`sha512-7wlSTA1Nc9c31WX9w8THYPwlaleWV1dk/0WXqRgxpph34EI4oJM+Z4Egv04Nn8wN2SLI9K2LMfeOpNKI+06LGg==`.
In temporary repositories, test exactly `omx cleanup --dry-run`, `omx cleanup`,
`omx ultragoal create-goals --force --brief <fixture> --json`, and `omx cancel`.
Before/after hashes of the registry and every
`.omx/archive/accepted-bundles/**` payload must be identical. Version/integrity
drift or a newly discovered native cleanup/archive mutator blocks WP1 until the
operation set is reviewed and pinned again.

This guarantee covers only the enumerated ordinary runtime operations. It does
not claim protection from the explicitly destructive `omx uninstall --purge`,
which intentionally removes the project `.omx` tree. Root guidance classifies
that command as destructive: before an authorized purge, export and verify a
content-addressed seed containing every current/superseded registered bundle and
registry; after purge, restoration must reproduce all registered path/hash pairs
before repository work resumes. The drill uses a disposable repository,
disposable `HOME`, disposable `CODEX_HOME`, explicit
`omx uninstall --scope project --keep-config --purge`, and seed storage outside
the repository `.omx` and both disposable homes. It places host-side sentinels
outside the enclosing temporary parent and proves no path outside that parent
changes. No
wrapper may silently reinterpret or block upstream purge; the protection is
explicit authorization plus verified backup/recovery.

## Codex And Matt Skills

### Project configuration

Codex project-local `.codex/config.toml` activates the selected skills. Keep
machine trust hashes and runtime state local. Track a portable logical allowlist,
example configuration, bootstrap command, and validator. Do not duplicate the
catalog in `AGENTS.md`.

Generated `.codex/agents/*.toml` files remain OMX/Codex setup-owned and
untracked. Track only compact role/model policy inputs when needed.

### Matt installation and pin

An operator may globally install the complete `mattpocock/skills` collection.
ARIA depends only on the validated project allowlist at upstream commit:

`ed37663cc5fbef691ddfecd080dff42f7e7e350d`

Exact allowlist:

1. `ask-matt`
2. `codebase-design`
3. `diagnosing-bugs`
4. `domain-modeling`
5. `grill-with-docs`
6. `grilling`
7. `handoff`
8. `improve-codebase-architecture`
9. `resolving-merge-conflicts`
10. `tdd`
11. `teach`
12. `writing-great-skills`

Do not run `setup-matt-pocock-skills` in this repository and do not vendor Matt
skill bodies. Existing ARIA docs, issue, planning, glossary, and package owners
remain authoritative.

The bootstrap clones the exact commit and invokes `skills@1.5.20` with npm
integrity
`sha512-lPl5KzMfTW+qwHFwc8t6R+wAqmdmSHw1+HWbGdJ/FZYbWLdB34bAZNFWiencM5DVoRaKAgXArmfTWMlNAbl9Gg==`
against that local checkout for a global Codex installation. No `latest` or
unpinned equivalent is allowed. The validator:

1. starts from each selected `SKILL.md`;
2. recursively follows repository-relative Markdown references;
3. rejects missing paths and references escaping the checkout;
4. sorts repository-relative closure paths;
5. hashes `path + NUL + raw file bytes` records with SHA-256;
6. compares the installed closure to the tracked manifest;
7. maps each selected ID to exactly one installed path;
8. rejects duplicate Matt IDs/paths;
9. disables every discovered Matt skill outside the allowlist for this project.

The Matt isolation rule applies only to skills originating from
`mattpocock/skills`. Retained ARIA skills and plugin/system/user skills are
governed separately. Name/path collisions fail rather than relying on precedence.

Repository invariants and output-location contracts override external skill
conventions. Conflict fixtures cover `CONTEXT.md`, ADR and ticket trees,
teaching artifacts, merge abort/escalation safety, repository writes, and
runtime state. Rollback disables the project Matt entries without deleting the
operator's global installation.

## ARIA Skill Architecture

Retain exactly nine operational skills:

1. `aria-nbv-context`
2. merged `aria-docs`
3. `agents-db`
4. `dataset-cache-ops`
5. `lrz-ai-systems`
6. `plan-grill`
7. `python-docstrings`
8. `rerun-nbv-inspector`
9. `measured-autoresearch`

`measured-autoresearch` remains the ARIA operational sidecar to OMX
`autoresearch` and `autoresearch-goal`. It owns measurement contracts and
keep/discard evidence for iterative model or system improvement while the OMX
workflow owns mission lifecycle and completion. Keep its helper and tests;
compact its `SKILL.md` through progressive disclosure to satisfy the shared
entrypoint budget.

Retained skills route executable project-specific workflows. Stable contracts
move first to the nearest source owner:

- package `AGENTS.md` for agent-facing invariants and concise `README.md` files
  only for durable human subsystem orientation;
- tests and typed APIs for executable contracts;
- docstrings for symbol-local semantics;
- thesis/docs for scientific rationale and roadmap scope;
- root guidance for repository-wide safety and source precedence.

Before deleting or merging a skill, a source-to-owner ledger classifies every
unique rule as migrated, already owned, duplicate, or obsolete. Deletion is
blocked by unresolved rows.

Target limits:

- preferred retained `SKILL.md`: at most 120 lines;
- hard maximum: 150 lines unless an explicit progressive-disclosure exception
  is approved;
- concise descriptions with one trigger per branch;
- no copied formulas, schema fields, roadmap status, or package contracts.

Package READMEs must not contain symbol matrices, generated inventories,
refactor status, or agent routing. A package-by-package README audit is deferred
outside this migration.

## State-Journal Retirement

Retire:

- `.agents/memory/state/DECISIONS.md`;
- `.agents/memory/state/GOTCHAS.md`;
- `.agents/memory/state/OPEN_QUESTIONS.md`;
- `.agents/memory/state/PROJECT_STATE.md`.

Use a selective source-backed salvage ledger, not a byte-exact parser. Each
heading or coherent fact category receives:

- destination owner and verification evidence; or
- an explicit stale, duplicate, historical, or unsupported discard rationale.

Migrate package contracts, glossary terms, current questions, actionable work,
and owner preferences only when current source evidence supports them. Git
history remains the archive. Remove all active consumers, promotion targets,
generated docs, hook routes, and guidance references before deleting the files.

## LitKG Retirement

Remove the active LitKG subsystem completely:

- `.agents/external/litkg-rs` submodule and Git metadata;
- `.configs/litkg.toml`;
- `aria-litkg-memory` and `semantic-scholar-litkg` skills;
- LitKG Make targets;
- KG scripts, hooks, compact filters, runtime, Neo4j, export and MCP wiring;
- live guidance and default routing.

Preserve literature manifests, TeX mirrors, bibliography, public literature
syntheses, and historical debriefs.

Before deletion, a closed capability-disposition table classifies:

| Capability family                        | Required disposition                                                                        |
| ---------------------------------------- | ------------------------------------------------------------------------------------------- |
| source/authority search and task routing | replaced by partitioned Graphify navigation plus exact source owners, or explicitly retired |
| claim checking                           | direct bibliography/literature/thesis verification with exact locators and render evidence   |
| provenance and consolidation             | retained source/OMX registries or intentional retirement                                    |
| paper ingestion/materialization          | preserved literature manifest/mirrors or intentional retirement                             |
| Semantic Scholar enrichment              | external research tooling or intentional retirement                                         |
| Neo4j export/runtime and MCP             | retire                                                                                      |
| auto-refresh hooks and generated docs    | retire (this does not include the quarto docs generated from the aria_nbv package)          |

No compatibility commands and no coexistence period remain after the deletion
workpackage. The pre-removal commit is the rollback boundary.

The replacement claim contract is intentionally small: resolve the citation
key; inspect the authoritative TeX section, local PDF, or upstream source;
record an exact path/line, page, or section locator; calibrate claim strength;
check consistency with curated literature and thesis owners; and render the
touched Quarto or Typst surface. The merged `aria-docs` skill and `docs/AGENTS.md`
own this checklist. Do not build a replacement claim engine or copy LitKG's TeX
parser into ARIA-NBV.

The fixed direct-source fixture manifest has four cases and a stable JSON
evidence schema:

- `supported_exact`: source fixture states that a method evaluates a finite
  candidate set; the calibrated matching claim passes;
- `overstated_generalization`: claim says the method is optimal for all scenes;
  fail with `wording_exceeds_source`;
- `missing_citation`: absent citation key; fail with `citation_unresolved`;
- `missing_locator`: resolved source without page/section/line; fail with
  `locator_required`.

Each evidence record contains fixture/claim ID, claim text, citation key,
authoritative source path and digest, locator type/value, extracted support,
wording verdict, expected/actual reason code, touched output paths, render
command, and render digest. This is a checklist schema and fixture suite, not a
general claim engine.

## Generated-Context Simplification

Remove broad generated navigation duplicated by Graphify, including aggregate
`make context`/`context-heavy` snapshots, bulk docstring/UML bundles, generated
source/literature indexes, and their default guidance routes.

Delete `aria-nbv-context/references/context_map.md`, custom AST package/module/
class/function/match inventories, generated source and literature indexes,
aggregate snapshots, custom literature wrappers, broad UML integration, and
their redundant Make targets.

Retain only these narrow source-reading capabilities:

- contract inspection;
- QMD and Typst outlines plus Typst include edges;
- package and documentation directory trees;
- direct `rg` over literature TeX/PDF source owners;
- one explicit `make uml UML_ROOT=<package-or-module-dir>
  UML_OUT=<absolute-ignored-path>` command.

The UML command requires a scoped root inside `aria_nbv/aria_nbv`, writes only
to an absolute ignored output, and is never called by CI, hooks, context refresh,
or documentation builds. Narrow inspection writes to stdout or ignored temporary
paths and is not authority.

Keep `python-docstrings` and current Quartodoc validation. A new repository-wide
docstring checker, method/field coverage gate, and broad source-documentation
migration are explicitly deferred.

## Workpackage Topology

```text
WP0 baseline and closed inventories
  -> WP1 OMX lifecycle
      -> WP2 unified Graphify contract
      -> WP3 Codex/Matt policy
          -> WP4 source owners and journal retirement
              -> WP5 ARIA skill consolidation
                  -> WP6 LitKG/generated-context removal
                      -> WP7 integration and budgets
```

WP2 and WP3 may execute in parallel only after WP1. Destructive migrations are
sequential because they share source-order, guidance, Makefile, and hook owners.

### WP0 - Baselines and closed inventories

**Deliverables:** pin baseline
`57457ec31e0d3b56da7cb6ebdbb9fde6166de434`; record all working-tree
exclusions; record the 21-skill baseline including `measured-autoresearch`;
measure active scaffold source LOC and model-visible description bytes; and
inventory Graphify version/corpus/output, OMX candidates, state consumers,
skill rules and owners, LitKG capabilities, generated-context
producers/consumers, hooks, and current verification failures. Record the
existing scaffold-refresh worktree as quarantined evidence, not accepted input.

**Gate:** inventory paths and counting rules are deterministic; no repository
behavior changes. `git diff --check` and the WP0 inventory validator pass. Known
baseline failures are captured as an exact command plus normalized failure
signature and digest; WP0 permits only those recorded failures and no new or
worsened failure.

### WP1 - OMX promotion contract

**Deliverables:** registry schema, exact-hash one-time bootstrap manifest and
transaction, status transitions, promotion/supersession commands, redaction,
history-aware immutability and failure rollback checks, accepted current bundle
recovery, tracked archive moves with tombstones/successor links, CI validator,
and transition fixtures.

**Gate:** every tracked `.omx` artifact resolves through the registry and is
either a `current` member at its native OMX role path or a `superseded` member
under `.omx/archive/accepted-bundles`; drafts and runtime state remain ignored;
registered payloads are immutable; native archive operations cannot mutate the
reserved accepted-bundle namespace; invalid transitions and unregistered files
fail.
The OMX lifecycle validator and `make check-agent-memory` are green from this WP
onward.

### WP2 - Unified Graphify contract

**Deliverables:** Graphify pin, unified corpus policy, partition provenance,
role-tagged tests/configs, tracked artifact allowlist without wiki output,
source-derived confidence/provenance policy, canonical semantic-record review and
reuse, deterministic JSON serialization, two-speed post-commit refresh,
semantic-staleness handling, corpus-tree-digest graph-sync validator,
exact-source fallback, merge driver, and deterministic regeneration tests.
Disable canonical query-answer, reflection, and learned-expansion feedback.

**Gate:** all commit-state, partition-staleness, bridge-edge, corpus deletion,
provenance-origin, source-locator, and no-diff fixtures pass. Canonical output is
within the size budget. Graphify integration and freshness gates are green from
this WP onward.

### WP3 - Codex and Matt policy

**Deliverables:** project allowlist, portable config example, pinned bootstrap,
closure manifest and validator, project activation, conflict/routing fixtures,
default model-visible budget, and rollback command.

**Gate:** clean-machine bootstrap succeeds; mismatched, missing, duplicate, and
unlisted Matt skills fail closed; npm CLI version/integrity mismatch fails;
unrelated skill families remain unaffected.

### WP4 - Source owners and state retirement

**Deliverables:** module-owner documentation needed by later deletions, complete
state salvage ledger, destination edits, consumer migration, and journal removal.

**Gate:** zero unresolved ledger rows and zero active journal references; current
facts resolve through their new owner and stale claims are not promoted.

### WP5 - ARIA skill consolidation

**Deliverables:** merged `aria-docs`, compact target skills including
`measured-autoresearch`, migrated domain primers, removed non-LitKG redundant
skills, invocation metadata, routing fixtures, and fresh skill inventory. Keep
the agents DB, current debrief workflow, and both LitKG skills temporarily until
WP6 closes their capability-disposition ledger.

**Gate:** exactly eleven active ARIA skills: the final nine plus
`aria-litkg-memory` and `semantic-scholar-litkg`. `measured-autoresearch`
satisfies the shared entrypoint and metadata contract without losing its
helper/tests; every WP5 deletion row is resolved; positive and adjacent-negative
routing tests pass.
`make scaffold-audit` and its self-test are green from this WP onward.

### WP6 - LitKG and generated-context removal

**Deliverables:** complete capability-disposition table, LitKG removal, broad
generated-context removal, `context_map.md` removal, hook/Make/guidance cleanup,
direct-source claim checklist, retained contract/outline/tree commands, one
scoped UML command, and stale-path tests. Record the docstring checker and
package README audit as deferred work.

**Gate:** exactly nine active ARIA skills and zero active LitKG or retired-context
routes; preserved literature owners, direct TeX/PDF verification, scoped UML,
and no-tool exact-source fallback work from a fresh checkout. LitKG/context
stale-reference scans and the direct-source checklist are green from this WP
onward.

### WP7 - Integration and budgets

**Deliverables:** final root/nested guidance, Make/CI wiring, registry and graph
sync, source-order cleanup, counts, independent review evidence, and PR-ready
commit series.

**Gate:** all final budgets and verification commands pass from the integrated
branch. Every source/graph workpackage pair is sync-valid.

## Verification Matrix

### Quantitative gates

- active ARIA skills: `21 -> 9`;
- active scaffold source LOC: strictly net-negative from WP0, excluding tests,
  generated Graphify output, and current/superseded OMX decision evidence;
- default model-visible skill-description bytes: at most 40% of WP0 baseline;
- canonical tracked Graphify output: at most 35 MB;
- reconsider Git LFS only if canonical output exceeds 50 MB;
- generated `.codex/agents` files tracked: zero.

### Required scenarios

OMX:

- every valid and invalid lifecycle transition;
- `current` and `superseded` immutability and supersession;
- native current paths and the reserved accepted-bundle archive namespace;
- isolation from native OMX runtime archive/cleanup operations;
- unregistered, runtime, path-escaping, secret-bearing and hash-drift rejection.

Graphify:

- clean bootstrap and exact corpus partitioning;
- production/test/config role tagging and production-first query ranking;
- source-derived `EXTRACTED`/`INFERRED`/`AMBIGUOUS` origin with separate numeric
  confidence, exact corpus locators/digests, endpoint provenance, partition
  revision, extraction-config digest, and tool version;
- rejection of inferred/ambiguous edges backed only by non-corpus or runtime
  provenance;
- rejection of canonical query-answer, reflection, and learned-expansion nodes;
- no required or tracked wiki output;
- deterministic regeneration;
- stale partition exclusion and reporting;
- stale required evidence rejection;
- fresh and stale cross-partition bridge behavior;
- source `S -> G` pass;
- unpaired `S` fail;
- `S -> G -> T(corpus)` fail until `T` receives its own `G`;
- mixed source/graph commit fail;
- non-corpus commit after `G` pass;
- merge and rebase regeneration;
- deleted source eviction and no canonical diff.

Matt/Codex:

- exact pin and closure validation;
- missing, changed, duplicate and path-escaping closure failure;
- unlisted Matt skill disabled;
- ARIA/plugin/system/user skill isolation;
- output-location and merge-safety conflicts;
- rollback without deleting global installation;
- model-visible description budget.

Destructive migrations:

- zero unresolved state/skill/LitKG/context inventory rows;
- zero active stale references;
- current non-trivial-work debrief and agents-DB behavior remains reachable;
- exact-source fallback with Graphify and Matt absent;
- preserved literature and package-owner validation;
- rollback drill at each destructive boundary.

### Commands

Every implementation commit runs `git diff --check`, targeted checks for its
touched owner, and a comparison against WP0's exact baseline-failure allowlist.
No commit may add, broaden, or worsen an allowed failure. Gates become mandatory
green only after their owning workpackage:

| From workpackage | Required green gates |
| --- | --- |
| WP0 | `git diff --check`, WP0 inventory validator, no-new-failure comparison |
| WP1 | OMX lifecycle tests and `make check-agent-memory` |
| WP2 | Graphify integration, freshness, provenance, and history tests |
| WP5 | `make scaffold-audit` and `make scaffold-audit-self-test` |
| WP6 | LitKG/context stale scans and direct-source verification |
| WP7 | all root gates and `make ci` |

An allowlist entry contains the exact command, normalized failure signature,
output digest, owning workpackage, and expiry point. Broad command-level
exemptions are forbidden; an entry is deleted when its owning WP lands.

Final integration runs:

```bash
python3 scripts/check_graphify_freshness.py
make graphify-integration-self-test
make agents-db AGENTS_ARGS='validate'
make agents-db
make check-agent-memory
make scaffold-audit
make ci
```

The final PR requires independent code review, test-engineer reruns from the
integrated commit, verifier reconciliation against raw output, and green GitHub
checks.

## Stop Conditions

Stop a destructive workpackage when:

- an inventory row lacks an owner or explicit retirement rationale;
- a current invariant lacks source/test coverage after migration;
- Graphify cannot prove corpus, partition freshness, bridge validity, or
  deterministic output;
- a source commit lacks its graph-only child;
- Matt activation cannot isolate unlisted or conflicting skills;
- an OMX artifact cannot be classified or safely promoted;
- a change would modify package/thesis semantics;
- active scaffold LOC or model-visible description budgets regress without an
  approved paired deletion.

Do not create compatibility mirrors to bypass a stop condition.

## ADR

### Decision

Adopt one tracked partitioned Graphify graph, a compact accepted-OMX registry,
pinned project-scoped Matt activation, nine operational ARIA skills, and
source-owner migration followed by removal of stale state, LitKG, and broad
generated context. Canonical Graphify state is source-derived and excludes a
tracked wiki or agent-generated memory. Superseded OMX bundles remain tracked in
the archive.

### Consequences

- Graph artifacts become reviewed repository evidence and require graph-sync
  commits.
- Deterministic code refresh is automatic; semantic inference is explicit and
  stale partitions fail closed.
- Cross-domain navigation is simple, but partition freshness is explicit and
  fail-closed for required evidence.
- Operator-installed skills remain optional; the project trusts only a pinned
  allowlist.
- Current and superseded planning evidence is durable while drafts/runtime state
  remain local.
- Git history, source owners, and debriefs replace hand-maintained state journals.
- LitKG authority-sensitive capabilities are either replaced explicitly or
  intentionally retired rather than silently assumed equivalent to Graphify.

## Execution Handoff

The accepted handoff is immutable execution authorization, not a progress log.
Use `$ultragoal` as the sole WP execution-status ledger. The agents DB remains
the durable backlog/issue owner and links to Ultragoal goals without mirroring
their status. Debriefs record evidence and lessons without becoming progress
state. WP2 and WP3 may use `$team` after WP1; destructive WP4-WP6 remain
sequential. Each goal records its commit, graph-sync child where required,
targeted checks, rollback point, and inventory closure.

Available roles: `explore`, `dependency-expert`, `executor`, `test-engineer`,
`verifier`, `writer`, `git-master`, `architect`, and `critic`.

Recommended staffing:

- `explore`: WP0 closed inventories;
- `executor` + `test-engineer`: WP1 registry;
- `dependency-expert` + `executor`: WP2/WP3 capability and implementation;
- `writer` + `executor`: WP4/WP5 owner migration;
- `executor` + `git-master`: WP6 deletion and submodule/history hygiene;
- `verifier`, then `architect`, then `critic`: independent WP7 gates.

`$ralph` is reserved for an explicitly selected final single-owner verification
fallback. It is not the default execution lane.

No scaffold implementation resumes from this plan draft. First regenerate and
accept the hash-bound test specification, Architect review, Critic review, and
handoff. WP0/WP1 may then establish the baseline and registry bootstrap; WP2 and
later work remain blocked until the successor bundle and superseded predecessor
are registered consistently.
