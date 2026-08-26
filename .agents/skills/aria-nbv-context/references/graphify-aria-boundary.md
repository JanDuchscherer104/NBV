# ARIA Graphify Boundary

Read this before an eligible Graphify query, build, refresh, or semantic
reconciliation. Graphify is mandatory navigation in Codex worktrees; exact
repository owners remain authoritative for behavior and scientific claims.

## Mandatory Worktree Route

1. When Codex supplies `CODEX_SOURCE_WORKSPACE_PATH`, setup uses that exact fork
   parent. Project-created worktrees may omit it, so the Codex bridge resolves
   the query-admissible canonical primary. If that primary is unusable, the
   bridge considers only registered, non-prunable same-repository siblings that
   are ancestors of the destination: an exact destination `HEAD` wins, then the
   nearest ancestor; equally ranked usable siblings fail as ambiguous. It never
   selects by worktree-list order. Before running a parent executable or
   mutating the child, the setup owner proves that both paths are registered,
   distinct worktrees in the same Git common directory and that the selected
   parent's graph is query-admissible. It then copies that generation locally,
   links the canonical primary's content-addressed `semantic` and
   `semantic-deep` namespaces, rebuilds the deterministic child projection only
   when its owners changed, then runs setup-owned upstream incremental maintenance
   before reporting readiness.
2. Mutable projection, graph, manifest, stat, interpreter, root, run, and
   provenance state are worktree-local regular-file copies. Only the two
   content-addressed cache namespaces are shared; neither cache identity nor a
   matching commit alone proves graph validity.
3. Setup admits a session only after its internal admission check succeeds.
   Models query the admitted graph and do not perform freshness repair. CI and
   maintainers may inspect admission diagnostics, but that is not a normal
   agent action.
4. Query the byte-identical upstream Graphify skill first for `fresh` and
   `usable-stale`. Then open exact repository owners; for `usable-stale`, verify
   every consequential path in the exact bounded `stale_sources` list.
5. For `unusable`, repair or reinitialize the bootstrap before the eligible
   query. If repair still cannot produce a usable artifact, report the state and
   use direct sources only. Never query the unusable artifact.

The public states are exhaustive. `fresh` has intact artifacts, valid owner and
detector checks, and a mandatory detector-proven zero-delta corpus. Matching
recorded or locally derived Git trees establishes non-ancestor identity but
never bypasses that detector requirement. `usable-stale` has an exact bounded
`stale_sources` list or owner reasons; full-tree equality may retain this state
for a bounded worktree delta. Every other incomplete, corrupt, wrong-root, true
corpus mismatch, missing-object, or unscoped result is `unusable`. These states
govern navigation only; Graphify never owns the located fact.

The checker records and accepts only canonical full hexadecimal commit OIDs and
derives trees from objects independently verified as commits. It always scans
the mutable worktree with Graphify's pinned detector. When the recorded
projection and graph trees do not equal `HEAD`, it also scans a fail-closed,
read-only `git archive HEAD` snapshot with the local generated projection
overlaid; committed and overlay deltas are combined without reproducing
Graphify's hashing, ignore, or type rules. A non-ancestor committed corpus
delta is `unusable`; an ancestor committed delta or bounded overlay delta is
`usable-stale`.

## Freshness And Refresh

Setup owns the ordinary session reconciliation: it rebuilds the deterministic
child projection only for owner changes and invokes upstream's incremental
extractor for every declared active mode. A
receipt, matching semantic counts, or matching Git commit never substitutes for
the pinned upstream detector and ancestry checks. A parent whose detector result
is unbounded or otherwise unusable requires a factual semantic refresh before a
new session can start. Strict state diagnostics are internal CI and pre-push
owners, not ordinary model actions. A Git HEAD mismatch alone is not staleness when the
recorded graph and projection revisions are ancestors and indexed bytes still
match. Semantic refreshes use `fork_turns="none"` and account for every
dispatched file. Incomplete or unreconciled semantic refreshes remain strict-gate
stale, retain the last valid snapshot for navigation, and require direct
verification of affected sources.

## Upstream Lifecycle And Hooks

- ARIA pins Graphify 0.9.48 and keeps the Codex skill byte-identical to the
  upstream source registered as `graphify-skill-bundle` in
  `.agents/skill-sources.toml`. The grounding ID never activates upstream
  maintenance.
- `graphify hook install` is the upstream post-commit and post-checkout
  no-LLM accelerator. It refreshes changed code and the pinned executable may
  AST-quick-scan changed Markdown headings. It does not semantically refresh
  documents or images or prove their freshness. ARIA's automatic
  `graphify-maintain` completion and pre-commit ownership handles declared-mode
  semantic maintenance; ordinary models do not refresh semantic inputs manually.
- The vendored `../../graphify/references/hooks.md` still says document and image changes are
  ignored. Preserve that upstream byte, but follow verified `0.9.48` executable
  behavior and treat either outcome as non-semantic navigation only.
- Upstream intentionally skips hook rebuilds inside linked Git worktrees. ARIA
  therefore keeps worktree-local seeding, state classification, and repair in
  this route; hook presence or success never proves worktree freshness.
- `graphify codex install` supplies generic always-on guidance, but ARIA's root
  dispatcher already owns the narrower source-order and exact-owner contract.
  Do not install a second generated Graphify section over that owner.

## Corpus And Upstream Ownership

- ARIA owns the freshness preflight, `.graphifyignore`, the ignored Markdown
  projection, and source-scoped degradation metadata. Freshness validation must
  not disable a structurally valid graph globally.
- Setup owns deterministic projection maintenance; use the repository root as
  Graphify's corpus root.
- Do not patch, overlay, append to, or add helper scripts beneath the upstream
  Graphify skill bundle. Use its lifecycle, dispatch, cache, merge, manifest,
  and semantic-reconciliation behavior.

## Semantic Acceptance

- Prefer an upstream-supported CLI backend for semantic refreshes.
- If an explicitly selected Codex role is used, provide a self-contained prompt
  with `fork_turns="none"`; explicit roles and inherited full history are not
  callable together.
- Accept a refresh only when upstream Graphify accounts for every dispatched
  file and excludes existing-file nodes outside the dispatched set. An
  incomplete refresh remains strict-gate stale, but the last valid graph stays
  queryable; verify any `stale_sources` result directly at `source_location`.

## Marker And Worktree Rules

- Graphify 0.9.48 writes `graphify-out/needs_update`, while the host-agent
  runbook also clears the historical `.needs_update` spelling. Remove
  `graphify-out/needs_update` only after refresh, coverage, and reconciliation
  all pass; leave it after partial, failed, or unverified work.
- Every linked worktree runs `scripts/setup_worktree_env.sh`. Only the shared
  `semantic` and `semantic-deep` content-addressed caches are linked. Mutable
  graphs, projections, manifests, AST state, and semantic run state are local
  copies; cache presence never proves freshness.
- The interpreter marker is advisory input only: checker and seeder validation
  anchor it to the independently discovered `graphify` CLI shebang, require
  canonical equality, and execute only that trusted interpreter for the pinned
  `graphifyy` version. Missing, unsafe, or mismatched setup state fails closed.
