# ARIA Graphify Boundary

Read this only before a Graphify build, refresh, or semantic reconciliation.
Graphify is trusted navigation; exact repository owners remain authoritative.

## Freshness And Corpus

- The committed `graphify-out/{graph.json,GRAPH_REPORT.md,manifest.json,graph.html}`
  snapshot is the shared navigation baseline. The primary integration checkout
  publishes it; linked worktrees consume it and verify reported branch-local
  `stale_sources` directly.
- `make graphify-usable-check` validates ordinary worktree navigation and
  pre-push use. `make graphify-state-check` is an explicit strict diagnostic;
  `make graphify-publish-check` is the strict canonical-publication gate.
- A Git HEAD mismatch alone is not stale when recorded revisions are ancestors
  and indexed bytes match.
- ARIA owns `.graphifyignore`, the freshness checker, and the ignored Markdown
  projection. Build that projection with `python3
  scripts/build_graphify_projection.py --output graphify-input --aria-code-ref
  "$(git rev-parse HEAD)"`, then use the repository root as the corpus root.

## Upstream Lifecycle

- Keep `.agents/skills/graphify` byte-identical to upstream. Use upstream
  dispatch, cache, merge, manifest, and reconciliation behavior.
- Prefer an upstream-supported CLI backend. A Codex-native semantic run uses a
  self-contained prompt with `fork_turns="none"`.
- Accept a refresh only after every dispatched file is accounted for and
  existing-file nodes outside that set are excluded. Until then, keep the last
  valid graph queryable, leave the strict gate stale, and verify affected source
  locations directly.
- Keep the upstream post-commit and post-checkout worktree guard. Use
  `graphify hook install` in the primary checkout; do not add an ARIA hook or
  writable shared graph directory. `make graphify-refresh` covers deterministic
  code-only integration refreshes and fails when semantic owners need the full
  upstream skill workflow.

## Marker And Worktrees

- Graphify 0.9.31 writes `graphify-out/needs_update`. Remove
  `graphify-out/needs_update` only after refresh, coverage, and reconciliation
  pass; leave it after partial, failed, or unverified work.
- Run `scripts/setup_worktree_env.sh` in linked worktrees. Only the
  content-addressed `semantic` and `semantic-deep` caches are shared; projection,
  AST, and run state stay worktree-local. The committed graph and manifest are
  read as the branch baseline; generated updates remain local until the primary
  integration checkout deliberately publishes them.
