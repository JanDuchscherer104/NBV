---
kind: test-spec
task_slug: aria-nbv-agent-scaffold-refresh
baseline_commit: 57457ec31e0d3b56da7cb6ebdbb9fde6166de434
plan_sha256: 2f1e5d46cde77efceb1d47dcfb76ad1b570300b52c70e66e5feb53b655150e0c
revision: 2026-07-22
---

# Test Specification: ARIA-NBV Agent Scaffold Refresh

## Purpose

Prove that the scaffold refactor reduces active guidance and context load while
preserving source ownership, exact-source fallback, current and superseded
planning evidence, Graphify integrity, and ARIA-specific operational safeguards.

Bundle roles are explicit: the plan owns decisions, this test specification
owns acceptance criteria, context files provide evidence, reviews bind exact
artifact hashes, and the handoff binds bundle status and execution authority.

The tests do not permit package, thesis, schema, checkpoint, or scientific
semantic drift.

## WP0 Baseline Ledger

Record from a clean worktree at the approved baseline:

- commit, branch, worktree cleanliness, submodule state and excluded dirty paths;
- exactly 21 baseline ARIA skill names, including `measured-autoresearch`, plus
  LOC, descriptions and model-visible description bytes;
- active scaffold source LOC with explicit include/exclude rules;
- every root/nested guidance, reference, skill, hook, generated-context producer,
  context consumer, LitKG surface, state consumer, and OMX candidate;
- Graphify package/version, corpus, graph size, node/edge counts, manifest,
  current freshness failure and tracked/ignored outputs;
- current Codex project config and installed skill resolution without recording
  machine secrets or trust hashes;
- results of `make check-agent-memory`, scaffold checks, Graphify checks and root
  CI, including pre-existing failures.

Each pre-existing failure is recorded as an exact command, normalized failure
signature, output digest, owning workpackage, and expiry point. WP0 permits only
those exact failures and rejects any new, broader, or worsened failure.

The inventory is closed when each destructive surface has a row with owner,
status, destination or retirement rationale, verification, and rollback commit.

## OMX Lifecycle Tests

### Status model

Bundle IDs must match
`^[a-z0-9]+(?:-[a-z0-9]+)*--[0-9a-f]{16}$` and equal the normalized task slug
plus the first 16 hex characters of the full registered handoff SHA-256. Reject
collisions on the full hash, user-selected IDs, path separators, uppercase,
Unicode/normalization aliases, wrong prefixes, and wrong hash suffixes. Assert
the predecessor ID is
`aria-nbv-agent-scaffold-simplification--c2c9c9381e40fd2f`.

Registry status and path placement are tested independently. Registered bundles
have exactly one of two statuses: `current` or `superseded`. Draft and rejected
payloads are not registry members.

Fixtures cover:

```text
unregistered draft -> current
unregistered draft -> rejected/untracked
current -> superseded
```

All other transitions fail. Draft and rejected payloads remain ignored. Current
and superseded accepted payloads are immutable. Current accepted bundle members
remain in native OMX role paths such as `.omx/context`, `.omx/specs`, and
`.omx/plans`. Supersession requires an accepted successor, records a
tombstone/successor link, and moves the predecessor intact to
`.omx/archive/accepted-bundles/<bundle-id>` while preserving its role-relative
layout. Other children of `.omx/archive` are native OMX runtime archives and are
ignored, unregistered, and outside accepted-bundle lifecycle ownership.

### Promotion

Test that promotion:

- requires a complete bundle and explicit user-acceptance marker;
- requires the configured Architect then Critic review sequence when applicable;
- atomically records task, bundle, artifact role, path, source commit, hash,
  status, review links and supersession;
- tracks context/spec/plan/reviews/handoff only as bundle members;
- preserves superseded bundle bytes in the tracked archive;
- leaves runtime state and unrelated operator files unchanged;
- proves native OMX cleanup/archive operations cannot mutate or delete registered
  payloads under `.omx/archive/accepted-bundles`;
- is deterministic in dry-run mode.

### One-time bootstrap

Before ordinary lifecycle commands exist, export a deterministic content-addressed
POSIX tar in an isolated temporary directory from the exact accepted successor
handoff and the accepted predecessor handoff at SHA-256
`c2c9c9381e40fd2f63bfe7343cd2f56120437aa3e46f9a740ab79b250446d61e`.
The predecessor handoff must bind its complete 17-artifact manifest and plan
digest `637b9cccb5673c5be33f96e185030f916156cf0d49520b0d39ea4a5d18784827`.
The tar uses fixed ordering, uid/gid/mode/mtime and is named by its recomputed
SHA-256. Bootstrap reads only this seed, never either dirty/quarantined worktree,
and tests one stage-only transaction. It must:

- record exact baseline hashes and remove the two pre-policy tracked standalone
  plans from the Git index: `measured-autoresearch-sidecar.md` must hash to
  `b8ef95044b200d58d5ae4e96a9d1968fb6597c2eb630d379b2461e0d76ad45c6`
  and is replaced by retained skill/tests;
- require `thesis-method-registry-restoration-ledger.md` to hash to
  `e7a8d6600df470f1f388f107118f6dc0d45568786cc417111a0ab52269052c68`
  before untracking it in favor of current thesis sources plus Git history;
- reject any other tracked `.omx` path outside the bootstrap manifests;

- keep successor members in native OMX role paths;
- place the byte-identical predecessor only under
  `.omx/archive/accepted-bundles/<bundle-id>`;
- require a clean index and reject declared-path collisions before mutation;
- resolve the worktree-specific recovery directory with
  `git rev-parse --git-path omx-bootstrap` and create the versioned journal and
  backups there;
- prepare/fsync destination-tree files, publish them by rename, then install the
  replacement index last;
- stage only declared registry and bundle paths and never move a Git ref or
  create a commit;
- restore filesystem and exact original index checksum after injected
  validation, copy, archive, registry-write, rename, index-install, and
  post-verification failures;
- recover an interrupted transaction idempotently on the next invocation;
- pass the interruption/recovery fixture in a real linked worktree whose `.git`
  is a file, proving journal isolation from the main worktree;
- bind each artifact to its registration commit for history-aware validation;
- permit only a byte-identical `current` to `superseded` move in the same commit
  that registers the successor and tombstone.

### Native OMX operation isolation

Require `oh-my-codex@0.20.3` with npm integrity
`sha512-7wlSTA1Nc9c31WX9w8THYPwlaleWV1dk/0WXqRgxpph34EI4oJM+Z4Egv04Nn8wN2SLI9K2LMfeOpNKI+06LGg==`.
In temporary repositories execute:

```text
omx cleanup --dry-run
omx cleanup
omx ultragoal create-goals --force --brief <fixture> --json
omx cancel
```

Snapshot the registry and every `.omx/archive/accepted-bundles/**` file before
each command and require byte-identical paths/hashes afterward. Reject
version/integrity drift and fail when a new native cleanup/archive mutator is
discovered without classification.

Classify `omx uninstall --purge` separately as an intentionally destructive
operation outside the ordinary-operation isolation guarantee. Create a temporary
parent containing a disposable repository, disposable `HOME`, disposable
`CODEX_HOME`, and a seed directory outside all three. Export and verify a
content-addressed seed of the registry plus all current/superseded bundles, run
exactly `omx uninstall --scope project --keep-config --purge` from the repository
with those environment variables, and assert repository `.omx` deletion. Restore
from the external seed and require exact registered path/hash recovery. Place
host-side sentinels outside the temporary parent and assert no path outside that
parent changes. Root routing must require explicit destructive authorization and
verified backup before purge; do not claim an upstream interlock that does not
exist.

### Rejection fixtures

Reject:

- tracked or unignored `.omx` payloads absent from the registry;
- duplicate current task/bundle/path IDs;
- missing, malformed, path-escaping or hash-mismatched artifacts;
- current- or superseded-content mutation;
- registered payloads in `.omx/archive` outside `accepted-bundles`;
- native runtime archives registered as accepted decision evidence;
- invalid source commits or review ordering;
- broken or cyclic supersession;
- runtime state, logs, sessions, goals, temporary reports and generated output;
- credentials, tokens, home/cache paths, local pane/session IDs and other
  machine-local runtime identifiers.

Repository checks:

```bash
git ls-files .omx
python3 scripts/scaffold/validate_omx_artifacts.py --check
make check-agent-memory
git diff --check
```

Every tracked `.omx` path must resolve through `.agents/omx_artifacts.toml` and
be either a `current` member at its native OMX role path or a `superseded`
member under `.omx/archive/accepted-bundles`.

## Graphify Tests

### Pin and canonical output

Require `graphifyy==0.9.22` and upstream commit
`abff1b1ca4052fcf9d955c5f6a034088723f4536` in the tracked capability record.

The canonical tracked allowlist contains only:

- graph JSON;
- manifest and deterministic partition provenance;
- `GRAPH_REPORT.md`.

Reject tracked caches, cost data, HTML, wiki Markdown, query logs, agent answers,
reflections, learned query expansions, snapshots, temporary chunks, converted
sources, extraction intermediates and interpreter pointers. An ignored on-demand
wiki export is permitted but never required.

### Corpus partition fixtures

Build fixtures for `code`, `scaffold`, `thesis`, and `literature`. Assert:

- first-match classification assigns `docs/contents/literature/**`, the
  literature manifest, and its selected section-bearing TeX/text to
  `literature`; root/nested `AGENTS.md`, retained agents, registered OMX, and
  scaffold tooling to `scaffold`; remaining active docs to `thesis`; and
  remaining code/tests/configs/guides to `code`;
- every included file appears exactly once in the expected partition;
- overlap and unclassified included paths fail;
- production code, tests, active configs and guides carry explicit role tags;
- ordinary query ranking prefers production owners over supporting tests/configs;
- excluded files never produce nodes;
- deleted and renamed files are evicted after refresh;
- literature membership follows `docs/literature/sources.jsonl`;
- section-bearing TeX/text is included;
- figures, binaries, styles, templates, generated files and bundled
  bibliographies are excluded;
- every node and edge has partition provenance;
- every edge declares categorical `origin` as `EXTRACTED`, `INFERRED`, or
  `AMBIGUOUS`, separately from a numeric `confidence_score`;
- every edge records exact corpus source locator(s), source content digest(s),
  endpoint provenance, partition revision, extraction-configuration digest, and
  Graphify version;
- positive fixtures prove source-backed inferred and ambiguous edges survive;
- negative fixtures reject inferred or ambiguous edges whose only provenance is
  a query, answer, reflection, log, runtime state, cache, or non-corpus path;
- canonical nodes and edges are source-derived rather than query-answer or
  reflection feedback;
- bridge edges record both endpoint partition revisions.

### Deterministic partition revision

Assert the canonical partition revision equals SHA-256 over:

```text
sorted input-manifest digest
+ Graphify version
+ extraction-config digest
+ graph-schema version
+ semantic mode
+ accepted-semantic-records digest
```

No wall-clock field may affect canonical output. Canonical JSON uses UTF-8,
sorted object keys, stable persistent-ID array ordering, and normalized finite
numeric values; mtimes, provider IDs, timestamps, and unordered filesystem input
are rejected. Clean-checkout regeneration never invokes an LLM: it rebuilds
structural content and reuses only reviewed semantic records whose source
digests still match. Source changes invalidate those records until explicit
semantic review. Rebuilding an unchanged corpus must produce a byte-identical
canonical tree. A semantic-complete flag changes only when semantic
content/configuration changes.

### Freshness and query behavior

Test normal, partial-stale and cross-partition cases:

- fresh single-partition search returns results normally;
- search omits stale-partition results and reports excluded partition IDs;
- search may answer only from remaining fresh evidence;
- `path`/`explain` requiring a stale node reject with a stable reason;
- a fresh cross-partition bridge succeeds;
- stale endpoint partition rejects the bridge;
- current endpoints with mismatched bridge revisions reject the bridge;
- rejected graph evidence triggers exact-source fallback;
- missing Graphify still permits targeted source discovery.

### Hook behavior

Assert the post-commit hook:

- runs only for relevant code changes;
- launches deterministic code refresh asynchronously and preserves unaffected
  inferred edges;
- marks touched semantic partitions stale;
- does not stage, commit, amend history or modify source;
- does not persist agent answers, reflections or query expansions;
- does not run semantic refresh for scaffold/thesis/literature;
- skips graph-only commits;
- skips merge/rebase/cherry-pick unsafe states according to upstream behavior;
- records failures without blocking Git completion.

### Graph commit state machine

Use temporary Git repositories for authoring-history and final-tree fixtures:

| History | Expected |
| --- | --- |
| `S(corpus) -> G(graph-only, corpus_tree_digest=tree(S))` | pass |
| `S(corpus)` | fail |
| `S -> G -> T(corpus)` | fail until `T -> G2` exists |
| mixed source and graph authoring commit | fail |
| `S -> G -> N(non-corpus)` | pass |
| one multi-partition `S -> G` refreshing all touched partitions | pass |
| rebased `S` with unchanged corpus/config digest | pass without semantic rerun |
| rebased `S` with changed corpus/config digest | fail until regenerated `G` |
| squash/merge product with matching final corpus-tree digest | pass |
| squash/merge product with stale final corpus-tree digest | fail |
| graph-only commit that changes noncanonical output | fail |

At the final tree, forced regeneration must produce no canonical diff.

## Codex And Matt Tests

### Pin and closure

Require `mattpocock/skills` commit
`ed37663cc5fbef691ddfecd080dff42f7e7e350d` and this exact allowlist:

Require installer CLI `skills@1.5.20` with npm integrity
`sha512-lPl5KzMfTW+qwHFwc8t6R+wAqmdmSHw1+HWbGdJ/FZYbWLdB34bAZNFWiencM5DVoRaKAgXArmfTWMlNAbl9Gg==`;
reject `latest`, version drift, and integrity mismatch.

```text
ask-matt
codebase-design
diagnosing-bugs
domain-modeling
grill-with-docs
grilling
handoff
improve-codebase-architecture
resolving-merge-conflicts
tdd
teach
writing-great-skills
```

For each selected skill, recursively follow repo-relative Markdown references
from `SKILL.md`, reject missing/escaping references, sort paths and hash
`path + NUL + raw bytes` records. Test known hash vectors.

Reject:

- wrong upstream commit;
- changed, missing or extra closure files;
- duplicate Matt IDs or ambiguous paths;
- a selected ID with no installed path;
- an unlisted Matt skill left enabled for the project;
- a selected Matt path outside the validated installation root.

ARIA, plugin, system and user skills are outside the Matt allowlist and must not
be disabled by Matt isolation.

### Bootstrap and project configuration

In a temporary Codex home:

- clone the exact Matt commit;
- invoke exactly `npx --yes skills@1.5.20` against the local checkout after npm
  integrity verification;
- install globally for Codex;
- render project `.codex/config.toml` activation from the portable allowlist;
- verify model-visible input exposes exactly the selected Matt skills according
  to their invocation metadata;
- verify unlisted Matt skills are disabled;
- verify machine trust hashes and runtime state are not committed;
- verify rollback disables project Matt entries without deleting global skills.

### Convention conflicts

Fixtures prove repository invariants win for:

- no new root `CONTEXT.md` or generic ADR tree;
- no unapproved ticket or issue hierarchy;
- teaching output only in an explicitly selected teaching workspace;
- merge/rebase escalation and abort safety;
- dirty-worktree preservation;
- no hidden writes to runtime state or operator configuration;
- accepted OMX owners used for durable plans/handoffs.

### Context budget

Use exactly `codex debug prompt-input` to record model-visible skill
descriptions. WP0 records `codex --version` and the SHA-256 of the resolved
`codex` executable; final measurement must use the identical command, version,
binary digest, config fixture, locale, and clean temporary Codex home. Final
default description bytes must be at most 40% of WP0 baseline, with no
collision, omission or truncation warning.

## ARIA Skill Tests

Final active ARIA skill set must be exactly:

```text
aria-nbv-context
aria-docs
agents-db
dataset-cache-ops
lrz-ai-systems
plan-grill
python-docstrings
rerun-nbv-inspector
measured-autoresearch
```

At the WP5 boundary the active set is exactly these nine plus
`aria-litkg-memory` and `semantic-scholar-litkg`. WP6 alone owns disposition and
deletion of those two LitKG skills; only its closure establishes the final nine.

For each retained skill:

- frontmatter validates;
- description has one distinct trigger per branch;
- positive and adjacent-negative routing fixtures pass;
- referenced files exist and are progressively disclosed;
- stable package/scientific facts resolve to external owners;
- body stays within the approved size budget or records an explicit exception.

`measured-autoresearch` retains its helper and tests while its `SKILL.md`
satisfies the shared metadata and progressive-disclosure budget.

For each removed skill, the source-owner ledger has no unresolved rows. Test
that package contracts are discoverable through nearest guidance/tests/docs
without loading a retired skill.

Generated `.codex/agents/*.toml` files must remain untracked.

## Execution Status Ownership

Assert the accepted handoff is immutable authorization only, Ultragoal is the
sole workpackage-progress ledger, and agents DB entries are durable backlog
records linked to goals without mirrored status. Debriefs may record evidence
and lessons but must not become a fourth execution-state surface.

## State-Journal Retirement Tests

Inventory exactly:

- `.agents/memory/state/DECISIONS.md`;
- `.agents/memory/state/GOTCHAS.md`;
- `.agents/memory/state/OPEN_QUESTIONS.md`;
- `.agents/memory/state/PROJECT_STATE.md`.

Every heading or coherent fact category must have either:

- destination owner plus verification evidence; or
- stale, duplicate, historical or unsupported discard rationale.

Block deletion on unresolved rows. After migration:

- root/nested guidance names no state journal as current truth;
- transcript tooling does not promote into removed journals;
- current non-trivial-work debrief behavior remains active;
- agents-DB workflows still route episodic evidence to validated debriefs;
- debrief templates point to actual owners/backlog;
- generated docs and hooks do not consume journals;
- historical advisor materials may mention old filenames only as historical
  evidence and are classified explicitly;
- active-tree stale-reference scan returns zero.

Git history is the only journal archive; do not create a replacement context or
ADR hierarchy.

## LitKG Retirement Tests

The capability-disposition table covers:

- authority-aware search and task routing;
- claim checking;
- provenance and consolidation;
- paper ingestion/materialization;
- Semantic Scholar enrichment;
- Neo4j export/runtime;
- MCP integration;
- auto-refresh hooks and generated documentation.

Every row is `replaced`, `preserved`, or `retired`, with evidence and a rollback
commit. Block deletion on unresolved rows.

After removal assert absence of:

- `.agents/external/litkg-rs` and its submodule metadata;
- `.configs/litkg.toml`;
- both LitKG skills and Claude aliases;
- LitKG Make targets;
- KG scripts, filters, runtime, Neo4j/export/MCP and hook wiring;
- active LitKG guidance/routing.

Preserve and validate literature manifests, TeX mirrors, bibliography, public
literature synthesis and historical debriefs. Exact-source literature lookup
must work without LitKG. The replacement checklist verifies citation-key
resolution, authoritative TeX/PDF inspection, exact locator, calibrated wording,
curated-owner consistency and touched-surface rendering. No replacement claim
engine or copied LitKG TeX parser is permitted.

Run a fixed fixture manifest with these expected outcomes:

| Fixture | Expected |
| --- | --- |
| `supported_exact` | pass |
| `overstated_generalization` | `wording_exceeds_source` |
| `missing_citation` | `citation_unresolved` |
| `missing_locator` | `locator_required` |

Evidence JSON must contain claim ID/text, citation key, source path/digest,
locator, extracted support, wording verdict, expected/actual reason, touched
outputs, render command, and render digest. Schema or expected-outcome drift
fails.

## Generated-Context Retirement Tests

The closed producer/consumer inventory covers Make targets, root/docs/package
guidance, `aria-nbv-context` scripts/references, generated documentation, hooks,
and LitKG routes.

Remove `context_map.md`, AST package/module/class/function/match inventories,
generated source/literature indexes, combined snapshots, bulk UML, bulk
docstring bundles and custom literature wrappers after Graphify replacement
passes.

Retained commands must be narrow, read sources directly, write to stdout or an
ignored temporary path, and never become authority. Test contract inspection,
QMD/Typst outlines and includes, bounded directory trees, direct TeX search, and
the scoped `make uml UML_ROOT=... UML_OUT=...` command with Graphify unavailable.
Assert a package or module directory resolving inside `aria_nbv/aria_nbv` passes.
Reject repository-root, docs, other outside-package, `..` traversal, and symlink-
escape roots. Assert UML output is absolute, ignored, outside tracked paths, and
absent from CI, hooks, context refresh, and documentation builds.

Do not add a new repository-wide docstring checker. Keep current Quartodoc
validation. Enforce only the README policy that retained READMEs contain durable
human orientation rather than symbol inventories or agent routing; defer the
package-by-package audit.

## Quantitative Gates

Record identical counting rules before and after:

- active ARIA skills: exactly `21 -> 9`;
- active scaffold source LOC: strictly net-negative;
- tests, generated Graphify output and current/superseded OMX decision evidence
  excluded from source-LOC accounting;
- model-visible skill-description bytes: at most 40% of baseline;
- canonical tracked Graphify output: at most 35 MB;
- trigger LFS decision review only above 50 MB;
- tracked generated `.codex/agents` files: zero.

## Per-Commit And Final Verification

Every implementation commit runs `git diff --check`, touched-owner tests, its WP
fixture suite, and comparison against the exact WP0 baseline-failure allowlist.
A mismatch, a new failure, or a worsened signature fails. Broad exemptions by
command name are forbidden.

Required gate phasing:

| From workpackage | Required green gates |
| --- | --- |
| WP0 | `git diff --check`, inventory validator, exact allowlist comparison |
| WP1 | OMX lifecycle suite and `make check-agent-memory` |
| WP2 | Graphify integration, freshness, provenance, and history suites |
| WP5 | `make scaffold-audit` and `make scaffold-audit-self-test` |
| WP6 | LitKG/context stale scans and direct-source checks |
| WP7 | every final integration command and root CI |

The allowlist entry for a gate is removed when its owning WP lands. A
graph-corpus source commit is not push-ready until its immediate graph-only child
exists and passes the history validator.

Final integration:

```bash
python3 scripts/check_graphify_freshness.py
make graphify-integration-self-test
make agents-db AGENTS_ARGS='validate'
make agents-db
make check-agent-memory
make scaffold-audit
make ci
```

Independent gates:

1. `code-reviewer` checks scope, source ownership and hidden compatibility.
2. `test-engineer` reruns WP and integration checks from the integrated commit.
3. `verifier` reconciles claims with raw evidence and quantitative ledgers.
4. `architect` checks final ownership/dependency direction.
5. `critic` checks plan/test satisfaction.
6. GitHub CI passes before a dependent PR begins.

## Stop Conditions

Stop and retain the old surface when:

- any state, skill, LitKG or context inventory row is unresolved;
- a current invariant has no verified source owner;
- Graphify corpus, freshness, bridge or deterministic-output tests fail;
- graph history is unsynchronized;
- Matt pin/isolation/conflict tests fail;
- OMX lifecycle or redaction cannot be established;
- package/thesis semantics would change;
- scaffold source LOC or context budgets regress without an approved paired
  deletion.

Do not add compatibility mirrors to bypass a stop condition.
