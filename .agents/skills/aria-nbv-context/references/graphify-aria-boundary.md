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

Freshness validates rather than globally gating reads: `make graphify-state-check`
is strict for scaffold and pre-push validation, while `make graphify-usable-check`
proves ordinary query safety. A Git HEAD mismatch alone is not staleness when the
recorded graph and projection revisions are ancestors and indexed bytes still
match. Refreshes regenerate the deterministic projection first; semantic refreshes
use `fork_turns="none"` and account for every dispatched file. Incomplete or
unreconciled refreshes remain strict-gate stale, retain the last valid snapshot for
navigation, and require direct verification of affected sources.

## Upstream Lifecycle And Hooks

- The accepted bundle provenance and maintenance owner is the
  [manifest below](#accepted-bundle-manifest).
- `graphify hook install` is the upstream post-commit and post-checkout
  no-LLM accelerator. It refreshes changed code and the pinned executable may
  AST-quick-scan changed Markdown headings. It does not semantically refresh
  documents or images or prove their freshness; refresh those semantic inputs explicitly.
- The vendored `../../graphify/references/hooks.md` still says document and image changes are
  ignored. Preserve that upstream byte, but follow verified `0.9.48` executable
  behavior and treat either outcome as non-semantic navigation only.
- Upstream intentionally skips hook rebuilds inside linked Git worktrees. ARIA
  therefore keeps worktree-local seeding, state classification, and repair in
  this route; hook presence or success never proves worktree freshness.
- `graphify codex install` supplies generic always-on guidance, but ARIA's root
  dispatcher already owns the narrower source-order and exact-owner contract.
  Do not install a second generated Graphify section over that owner.

## Accepted Bundle Manifest

The accepted Graphify decision pins exactly this bundle; it does not establish
a policy for other external skills.

- Upstream repository: `https://github.com/Graphify-Labs/graphify`.
- Upstream ref: `b2cd36267456c166788c95be6e68574064a92a42`
  (Graphify 0.9.48).
- Upstream sources: `graphify/skill-codex.md` (blob
  `af3f723c7878b8ca9252af511270511002086ed4`) and
  `graphify/skills/codex/` (tree
  `2b19efe36ad87d1fe84e396dc7065de512b37bc3`).
- Local bundle: `.agents/skills/graphify/`; assembled Git tree
  `6943c772de908bdac1dc0d1b7f73fa7ed285433a`.
- Refresh: install `graphifyy==0.9.48`, then run
  `graphify install --project --platform agents` from the repository root.
- Integrity proof: `make graphify-skill-upstream-self-test` verifies the exact
  file set and every pinned Git blob without modifying the upstream bundle.

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
