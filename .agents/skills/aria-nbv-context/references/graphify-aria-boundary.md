# ARIA Graphify Boundary

Read this before an eligible Graphify query, build, refresh, or semantic
reconciliation. Graphify is mandatory navigation in Codex worktrees; exact
repository owners remain authoritative for behavior and scientific claims.

## Mandatory Worktree Route

1. Initialize every Codex worktree through `scripts/setup_worktree_env.sh`.
   Mutable projection, graph, manifest, stat, interpreter, root, run, and
   provenance state must be worktree-local regular-file copies. Only
   content-addressed `semantic` and `semantic-deep` caches are shared.
2. Before an eligible architecture, relationship, ownership, or project-content
   question, run `scripts/check_graphify_freshness.py --json`.
3. Query the byte-identical upstream Graphify skill first for `fresh` and
   `usable-stale`. Then open exact repository owners; for `usable-stale`, verify
   every consequential path in the exact bounded `stale_sources` list.
4. For `unusable`, repair or reinitialize the bootstrap before the eligible
   query. If repair still cannot produce a usable artifact, report the state and
   use direct sources only. Never query the unusable artifact.

The public states are exhaustive. `fresh` has current provenance and intact
required artifacts. `usable-stale` is an ancestor snapshot with valid
provenance, a present ARIA projection node, intact artifacts, and an exact
bounded stale-source list. Every other incomplete, corrupt, wrong-root,
non-ancestor, or unscoped result is `unusable`. These states govern navigation
only; Graphify never owns the located fact.

## Freshness And Refresh

Freshness validates rather than globally gating reads: `make graphify-state-check`
is strict for scaffold and pre-push validation, while `make graphify-usable-check`
proves ordinary query safety. A Git HEAD mismatch alone is not staleness when the
recorded graph and projection revisions are ancestors and indexed bytes still
match. Refreshes regenerate the deterministic projection first; semantic refreshes
use `fork_turns="none"` and account for every dispatched file. Incomplete or
unreconciled refreshes remain strict-gate stale, retain the last valid snapshot for
navigation, and require direct verification of affected sources.

## Corpus And Upstream Ownership

- ARIA owns the freshness preflight, `.graphifyignore`, the ignored Markdown
  projection, and source-scoped degradation metadata. Freshness validation must
  not disable a structurally valid graph globally.
- Build the projection with `python3 scripts/build_graphify_projection.py
  --output graphify-input --aria-code-ref "$(git rev-parse HEAD)"`, then use the
  repository root as Graphify's corpus root.
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

- Graphify 0.9.31 writes `graphify-out/needs_update`, while the host-agent
  runbook clears the historical `.needs_update` spelling. Remove
  `graphify-out/needs_update` only after refresh, coverage, and reconciliation
  all pass; leave it after partial, failed, or unverified work.
- Every linked worktree runs `scripts/setup_worktree_env.sh`. Only the shared
  `semantic` and `semantic-deep` content-addressed caches are linked. Mutable
  graphs, projections, manifests, AST state, and semantic run state are local
  copies; cache presence never proves freshness.
