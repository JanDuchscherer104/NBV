# PR 50 Graphify Mandatory, Upstream-First Remediation Plan

## Requirements Summary

Implement the unresolved PR 50 review work on top of exact commit
`d6a3082f3ea03a8cdf14fa2673f21ed4e3f1ea9f` without modifying the pinned
upstream Graphify skill bundle.

1. Supersede the accepted optional-Graphify decision in
   `.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md:61-112`
   and `.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md:457-500`.
   Graphify becomes a mandatory Codex-worktree navigation prerequisite while
   exact repository sources remain authoritative.
2. Make `scripts/setup_worktree_env.sh:5-125` initialize worktree-local
   `graphify-input/` and `graphify-out/` from the main/parent ARIA-NBV worktree.
   Mutable graph, manifest, projection, AST, and run state must be copied, never
   directory-symlinked; only content-addressed semantic caches remain shared.
3. Replace the custom hashing in `scripts/check_graphify_freshness.py:122-185`
   with `graphify.detect.detect_incremental()`: `kind="ast"` for code and
   `kind="semantic"` for documents, papers, and images. An empty
   `semantic_hash` is missing semantic coverage and cannot fall back to
   `ast_hash`.
4. Preserve a three-state public contract: `fresh`, `usable-stale`, and
   `unusable`. Only an ancestor snapshot with valid provenance, a present ARIA
   projection node, intact artifacts, and an exact bounded stale-source list is
   `usable-stale`.
5. Add `/graphify-labs/graphify` to Context7 routing and make the smallest
   top-level/narrow-skill additions needed to require Context7 for consequential
   external-library behavior. Context7 supplies current upstream documentation;
   installed source and local tests own behavior for the pinned version.
6. Run live scaffold validation in hosted CI and make CI-impact routing include
   every source, fixture, and test that can change the scaffold result.

## Acceptance Criteria

- The accepted spec contains an explicit later human supersession: mandatory
  Graphify in Codex worktrees, query-first routing for eligible codebase
  questions, exact-source authority, and direct-source fallback only for broken
  bootstrap or unusable artifacts.
- Root `AGENTS.md`, `.agents/references/source_order.md`, `aria-nbv-context`, and
  the Graphify boundary reference point to one non-duplicated mandatory contract.
- A new worktree setup seeded from a valid parent contains local regular-file
  copies of `graph.json`, `manifest.json`, `.graphify_python`, the
  manifest-backed `graphify-input/` Markdown, and required run/provenance
  metadata. Setup synthesizes child-local `.graphify_root` and a seed sentinel;
  the stat index is optional only, and durable AST temporary output is never
  inherited.
- Child mutation or refresh cannot change the parent's mutable Graphify files;
  semantic cache writes remain visible across worktrees.
- Setup fails with a precise diagnostic when mandatory parent artifacts are
  missing, invalid, or collide with non-owned child paths; `--check` validates
  the complete initialized contract without rewriting it.
- Freshness code imports and calls upstream `detect_incremental`; it contains no
  local MD5/SHA implementation for manifest drift and no semantic-to-AST hash
  fallback.
- Freshness calls `detect_incremental` twice over the full detected corpus with
  one absolute manifest path, then filters code results only from `kind="ast"`
  and document, paper, and image results only from `kind="semantic"`. A
  worktree-local temporary cache and output are isolated from inherited manifest
  and mutable worktree state.
- Tests prove code drift is detected with `kind="ast"`, semantic-source drift
  and empty `semantic_hash` with `kind="semantic"`, bounded ancestor drift is
  `usable-stale`, and corrupt, non-ancestor, deleted, excluded, unsupported,
  unscoped, or missing-projection cases are `unusable`.
- Context7 routing contains `/graphify-labs/graphify`, names both Docker MCP
  operations, requires consequential ID re-resolution unless an exact ID is
  supplied, and requires installed-source/test verification for pinned behavior.
- Hosted CI runs `make scaffold-audit`, `make scaffold-audit-self-test`, G002,
  Graphify upstream identity, freshness, setup, and CI-impact tests. Push/path
  filters cover live audit code, routing fixtures, governance tests, Graphify
  setup/freshness code, and their tests.
- The pinned `.agents/skills/graphify/` bundle remains byte-identical to upstream
  Graphify 0.9.31, `git diff --check` passes, and no unrelated package/thesis
  behavior changes.

## Implementation Workpackages

### WP1 — Mandatory Graphify contract

1. Add a dated accepted supersession to the target-state spec rather than
   rewriting historical decisions.
2. Update the source-order role split and human-owner intent if it carries the
   superseded preference.
3. Add a compact `## Graphify` root route: initialize through worktree setup,
   freshness-check, query first when usable, verify exact sources, repair an
   unusable bootstrap before Graphify-eligible work.
4. Align `aria-nbv-context` and its Graphify boundary reference; keep detailed
   mechanics behind the skill pointer.
5. Extend governance/scaffold fixtures so the mandatory route is executable and
   does not make Graphify an authority.
6. Run guidance checks and create one focused local commit.

### WP2 — Worktree artifact inheritance

1. Extend `scripts/setup_worktree_env.sh` with explicit seed ownership and an
   allowlisted seed manifest for `graph.json`, `manifest.json`,
   `.graphify_python`, manifest-backed `graphify-input/` Markdown, and required
   run/provenance metadata. Synthesize child `.graphify_root` plus a seed
   sentinel; treat the stat index as optional and never inherit a durable AST
   temporary file.
2. Preserve worktree-local mutable state, shared content-addressed semantic
   caches, collision safety, idempotence, and child-root metadata rebinding.
3. Extend `scripts/tests/test_setup_worktree_env.sh` with parent-seed, missing
   seed, collision, isolation, idempotence, and `--check` cases.
4. Run the setup test in a disposable fixture and create one focused local
   commit.

### WP3 — Upstream-first freshness

1. Import upstream `detect_incremental` through the Graphify interpreter used by
   the initialized worktree, pass one absolute manifest path, and isolate any
   temporary output or cache path from inherited state.
2. Call upstream incremental detection twice over the full bounded corpus
   against that absolute manifest path, isolating a worktree-local temporary
   cache/output. Filter only code results from `kind="ast"`; filter only
   document, paper, and image results from `kind="semantic"`.
3. Retain only ARIA provenance, required projection-node, ancestor, status
   mapping, and diagnostic logic.
4. Replace historical state names with `fresh`, `usable-stale`, and `unusable`;
   deletions, exclusions, unsupported files, and unscoped drift are unusable.
   Keep CLI exit behavior explicit for strict versus usable checks.
5. Rewrite freshness fixtures around upstream `save_manifest`/manifest semantics
   or minimally shaped upstream-compatible manifests without reproducing its
   hashes.
6. Run focused freshness, upstream-skill, and setup tests and create one focused
   local commit.

### WP4 — Context7 integration and routing

1. Add `/graphify-labs/graphify` to the Context7 registry with current-doc versus
   installed-version semantics.
2. Add compact Context7 triggers to `aria-nbv-context`; add only domain-specific
   provenance guidance to `agents-db` if backlog evidence can cite Context7.
3. Add routing/governance fixtures for exact supplied IDs, ID resolution, docs
   retrieval, and exact local verification.
4. Run G002, scaffold audit/self-test, agent-memory checks, and create one focused
   local commit.

### WP5 — Hosted validation

1. Run the live scaffold audit in `.github/workflows/ci.yml` alongside the
   existing self-test and focused Graphify/setup tests.
2. Extend `scripts/ci_impact.py` and `scripts/tests/test_ci_impact.py` so changes
   to audit code, fixtures, routing guidance, governance tests, and Graphify
   contracts select the scaffold job.
3. Run the hosted-equivalent command set locally, including `make scaffold-audit`,
   `make scaffold-audit-self-test`, `make check-agent-memory`, G002, all focused
   Graphify/setup/CI-impact tests, and `git diff --check`.
4. Create one focused local commit and retain the exact final SHA and validation
   transcript for independent review.

## Risks and Mitigations

- **Stale parent snapshot copied into a child.** Setup copies provenance and the
  child freshness check immediately classifies it; only bounded ancestor drift
  is queryable.
- **Inherited state is mistaken for current child state.** Copy only the
  allowlisted durable seed, synthesize child root/sentinel metadata, and isolate
  all temporary outputs and caches from the absolute inherited manifest path.
- **Child refresh mutates parent state.** Copy only an allowlist of mutable files
  and assert different inodes/content isolation; share only semantic cache
  directories.
- **Upstream API drift.** Use the pinned interpreter/source, verify the callable
  signature, and fail with a version/setup diagnostic rather than implementing a
  compatibility hash layer.
- **Overloaded root guidance.** Root gets only the mandatory route and points to
  `aria-nbv-context`; operational detail stays in the boundary reference.
- **Context7 becomes authority.** Guidance requires exact installed source/tests
  for pinned behavior and exact repository owners for ARIA behavior.
- **Hosted CI lacks generated Graphify artifacts.** Hosted validation proves
  repository-owned setup/freshness contracts hermetically; any strict live-graph
  gate must restore or build its declared artifact before checking it.

## Verification and Stop Conditions

The implementation is complete only when all five workpackages are committed,
the exact-base diff contains only request-owned scaffold surfaces, targeted and
hosted-equivalent validation pass after the final cleanup pass, and independent
`code-reviewer` plus `architect` reviews approve the architecture invariants.
No push or PR mutation is authorized by this plan.
