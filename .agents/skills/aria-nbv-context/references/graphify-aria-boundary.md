# ARIA Graphify Boundary

Read this only before a Graphify build, refresh, or semantic reconciliation.
Graphify is derived navigation; exact repository owners remain authoritative.

## Corpus And Upstream Ownership

- ARIA owns the freshness preflight, `.graphifyignore`, the ignored Markdown
  projection, and the read-side freshness gate.
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
  file and excludes existing-file nodes outside the dispatched set. Otherwise
  leave the graph stale and continue from exact sources.

## Marker And Worktree Rules

- Graphify 0.9.31 writes `graphify-out/needs_update`, while the host-agent
  runbook clears the historical `.needs_update` spelling. Remove
  `graphify-out/needs_update` only after refresh, coverage, and reconciliation
  all pass; leave it after partial, failed, or unverified work.
- Every linked worktree runs `scripts/setup_worktree_env.sh`. Only the shared
  `semantic` and `semantic-deep` content-addressed caches are linked. Graphs,
  projections, manifests, AST state, and semantic run state stay worktree-local;
  cache presence never proves freshness.
