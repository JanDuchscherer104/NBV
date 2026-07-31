---
kind: test-spec
status: approved-ready-for-ultragoal
plan: .omx/plans/graphify-thin-adapter.md
architect_round_1: ITERATE
architect_round_2: ITERATE
architect_round_3: ITERATE
architect_final: APPROVE
critic_round_1: ITERATE
architect_post_critic_1: ITERATE
architect_post_critic_final: APPROVE
critic_round_2: ITERATE
architect_final_confirmation: APPROVE
critic_final: APPROVE
consensus_complete: true
selected_option: deterministic-ignored-markdown-evidence-projection
next_handoff: $ultragoal
context: .omx/context/graphify-thin-adapter-20260731T175054Z.md
---

# Test specification: Graphify source-link projection

## Purpose

Prove that the one retained ARIA adapter is deterministic, source-owned,
recoverable, and optional to ordinary repository work. Tests validate the
projection transform and its corpus/CI boundary; they do not test Graphify
internals or scientific claims.

- Production target: `scripts/build_graphify_projection.py`
- Test target: `scripts/tests/test_build_graphify_projection.py`
- Framework: standard-library `unittest`; no new dependency.
- Fixtures: temporary roots with minimal Typst, BibTeX, JSONL, Git refs, Python,
  TeX-root, and placeholder PDF paths.
- Subprocess boundary: one injected runner permits exactly `git` and `typst`.
- Hosted CI: runs the credential-free projection self-test, never Graphify.
- LOC: report production, tests, generated output, deletion, and upstream LOC
  separately as evidence. LOC is not a pass/fail threshold.

## Shared fixture

Use one small Git fixture containing:

- an active thesis root, two literal local includes, and one inactive sibling;
- comments/raw blocks that contain citation/link-looking text;
- one compiled citation with two lexical occurrences;
- one valid `gh`, one `gh-wip`, and one `gh-symbol` callsite;
- mixed compiled links: configured-repository `/blob/`, exact configured
  `gh-symbol` search, internal Typst, bibliography, another repository's GitHub
  `/blob/`, and unrelated external URL;
- positive final `gh` fixtures for a literal full SHA and an existing release
  tag, a tag and SHA resolving to the same commit, plus a negative
  `gh(ref: "main")` fixture;
- two distinct thesis-source relations resolving to one identical code target;
- the same code path at two refs resolving to different commits;
- two disjoint BibTeX owners containing only the identity fields needed by the
  fixture;
- manifest rows joined separately by arXiv, DOI, and URL, plus unmatched rows;
- present/missing TeX-root/PDF paths and a PDF-root symlink whose target is
  outside the repository;
- fake compiled `cite`, `link`, and `heading` query results.
- CLI `--aria-code-ref` fixtures for inherited full SHA, inherited verified
  release tag, and omitted/default `main`.

## Hermetic adapter tests

### 1. Determinism, digests, and scoped dirt

- Two builds from identical owner bytes and refs have identical relative files
  and bytes; output contains no timestamp or absolute path.
- Every enumerated owner input has a SHA-256 digest.
- Dirt in an unrelated path does not change `owner_worktree_state`; dirt in an
  owner path does and changes its digest.
- `--check` validates/renders in temporary memory without mutating output.

### 2. Bounded output swap

- The builder validates a sibling temp tree before swap.
- Ordinary failure before/after backup creation restores or preserves the prior
  output.
- `--check` reports stale temp/backup debris without mutation.
- A later normal build discards stale temp/backup debris and rebuilds from
  owners; no completion marker or persistent startup recovery state exists.
- Tests/docs explicitly assert no crash/power-loss atomicity guarantee.
- Output outside the repository or overlapping an owner is rejected.

### 3. Conservative active Typst closure

- Traverse only transitive literal repository-local include/import paths from
  `main.typ`; inactive sibling files produce no candidate.
- Reject dynamic/computed include paths, absolute includes, and repository
  escapes with the active source locator.
- Exclude tokens in comments and raw/code blocks.
- Invoke and verify compiled `cite`, `link`, and `heading` queries plus an
  independent thesis compile.
- Pass the same exact `--input aria-code-ref=<CLI_VALUE>` to all three queries
  and the independent compile, and record value, source (`cli`/`default`), pin
  kind, and resolved OID.
- Filter compiled links before multiplicity reconciliation: admit only exact
  configured-repository `/blob/` destinations and exact configured-repository
  `gh-symbol` search destinations. Internal, bibliography, and unrelated
  external links remain outside scope and do not alter multiplicity.
- Reconcile compiled and lexical multiplicities per identity. Missing,
  duplicate, or multiplicity-mismatched candidates fail.
- No standalone thesis-link identity exists. Exact, uniquely paired occurrences
  become relations on the thesis-source page with deterministic source-order
  ordinal, total multiplicity, and line/column. If only file precision is
  proven, emit one aggregated source-page relation with semantic target and
  occurrence count, without ordinal or line. Candidates spanning files fail.
- Duplicate occurrence coverage proves stable exact ordinals when possible and
  stable aggregated multiplicity when only file precision is provable.

### 4. Citation ownership and identity-only joins

- A citation from each BibTeX owner resolves to its exact owner/entry locator.
- Duplicate keys across owners and active compiled keys absent from both fail.
- Parse only BibTeX entry key, eprint/arXiv, DOI, and URL fields. A test with a
  complex title proves title parsing is unnecessary.
- Exercise strict join precedence arXiv, DOI, then URL.
- Normalize only documented prefixes/case/version/path rules; preserve URL
  query/fragment identity.
- No title or fuzzy join exists. Title-only near/exact matches remain
  explicitly unmatched.
- Same-precedence multiples or conflicting identity signals fail; unmatched
  BibTeX/manifest records remain visible and unlinked.

### 5. Reference-qualified code targets

- Generated identity is
  `repository@source-ref[resolved-oid]:path:line-range`; source-ref spelling and
  resolved commit OID both participate.
- A code-target page contains only repository, source-ref spelling, resolved
  OID, path, line range, resolved-object validation, and current-worktree target
  validation status (`same-ref-clean`,
  `same-ref-owner-dirty`, `different-ref-path-present`, or
  `different-ref-path-absent`).
- Each thesis-source relation exclusively contains `macro_kind`, compiled URL,
  `pin_kind` (`full-sha`, `release-tag`, or `mutable`), occurrence or
  multiplicity, and thesis source locator. A target page may show derived
  backlinks but contains no independently persisted relation metadata.
- Compiled URL repository must agree with the source-link owner's configured
  repository. Path/range validation uses the resolved Git object; a path absent
  only from a different current worktree is recorded, not failed.
- The same path/line at two refs generates two identities/pages.
- A release tag and literal SHA resolving to the same commit still generate two
  identities/pages; their respective thesis-source relations preserve macro
  kind, compiled URL, pin kind, occurrence metadata, and source locator.
- Two distinct thesis-source relations that resolve to the same complete target
  identity generate exactly one code-target page and two distinct relations.
  Assert that the target page contains only target facts; any rendered backlink
  list is derived from those relations and does not persist macro kind, compiled
  URL, pin kind, occurrence/multiplicity, or thesis source locator as target
  fields.
- A final `gh` with full SHA passes. A final `gh` with an existing release tag
  passes and records both tag name and resolved commit OID. A final
  `gh(ref: "main")` fails. Mutable refs pass only for `gh-wip`.
- A `gh` without explicit ref inherits CLI `--aria-code-ref`: full SHA and
  verified release tag pass; omitted/default `main` fails. Every Typst query
  receives the same inherited value.
- Missing/unresolvable refs, missing Git-object paths, invalid ranges, and
  compiled/lexical destination multiplicity mismatch fail.
- `gh-symbol` remains `unresolved-dynamic`; even an obvious local definition is
  not guessed.
- Similar thesis/code words without a macro produce no relation.

### 6. Literature and asset proxies

- Generate one Markdown proxy per declared TeX root and PDF identity.
- Every generated page H1 is its complete generated identity.
- Assert `literature.md -> proxy.md -> raw owner path` and that every generated
  `.md` link resolves.
- Present/missing local assets produce `present`/`missing-local`; metadata-only
  rows require no asset.
- Proxy output contains no TeX/PDF content and no resolved symlink/machine path.
- PDF proxy states `page_locator: unavailable`; TeX proxy states
  `content_parsed: false`.
- No TeX file/section node or PDF-page node is emitted.
- Absolute/escaping manifest asset paths fail.

### 7. No second Graphify lifecycle

- Builder source contains no `graphify.*` import, graph JSON write,
  `merge-graphs`, global graph, watcher, hook, refresh/freshness marker, network
  call, shell invocation, or home-directory mutation.
- Injected runner rejects every executable except exact `git` and `typst`.
- Non-Markdown raw-owner backlinks are labelled human provenance; only
  projection-to-projection Markdown links are promised Graphify edges.

## Repository contract tests

### 8. Corpus and ignore policy

- `graphify-input/**/*.md` is admitted by `.graphifyignore` and ignored by Git.
- Raw Typst/BibTeX/JSONL/TeX, bulk PDFs, scripts/tests, and `graphify-out/`
  remain outside the default graph corpus.

### 9. Unconditional credential-free CI

- `Makefile` exposes `graphify-projection-self-test` and the docs CI job always
  runs it when that job is selected.
- Impact routing selects docs for:
  `scripts/build_graphify_projection.py`, its test, `.graphifyignore`,
  `docs/literature/sources.jsonl`, and `docs/literature/README.md`.
- Hosted workflow contains no Graphify install/invocation/backend secret.

### 10. Deletion and guidance guard

Run only after the hard upstream gate passes:

- Every WP4/WP6 legacy path is absent.
- No live non-history consumer names retired scripts/targets/version pin.
- `.codex/skills/graphify/**` and its validator exception are absent.
- Normal hooks contain no Graphify/post-commit graph dispatcher.
- Root guidance says optional derived navigation and exact-source fallback,
  never default/required/fresh.
- Cross-modal guidance names both BibTeX owners.

Before the upstream gate passes, invert only the deletion assertions: the
dormant lifecycle must remain present and uninstalled so failure cannot destroy
the comparison/recovery path.

## Live repository checks

After hermetic tests on the rebased tree:

1. Run `python3 scripts/build_graphify_projection.py --check
   --aria-code-ref FULL_SHA_OR_RELEASE_TAG`.
2. Build twice and compare complete tree hashes.
3. Inspect recomputed counts for active include closure, compiled/lexical
   citation/link multiplicities, code targets by resolved ref, both
   bibliographies, manifest joins/unmatched records, proxies, and asset status.
4. Independently run every Typst invocation with the same
   `--input aria-code-ref=FULL_SHA_OR_RELEASE_TAG`:
   - active-thesis `typst compile ... --input
     aria-code-ref=FULL_SHA_OR_RELEASE_TAG`;
   - `typst query ... cite`;
   - `typst query ... link`;
   - `typst query ... heading`.
5. Confirm `git status --ignored` shows projection/graph output only as ignored.

Counts are drift evidence, not hard-coded acceptance thresholds.

## Hard upstream consumption gate

This must pass before legacy deletion or PR publication:

1. Confirm upstream Graphify 0.9.31 or re-review a newer version and capture
   exact `graphify extract --help` output relevant to document extraction.
2. Confirm the normal user-installed upstream Graphify skill/tool is available
   and the host Codex session is authenticated with `codex login`. The
   repository supplies every project-side setup surface.
3. Build the live projection, then invoke the unmodified upstream `$graphify`
   skill. It may dispatch authenticated Codex subagents to produce semantic
   JSON before running the ordinary upstream Graphify build into a disposable
   directory. Never export a ChatGPT/Codex token, reuse it as
   `OPENAI_API_KEY`, add repository secrets, or use a Graphify fork,
   repository-owned package import, or repository-owned lifecycle. The
   unmodified user-scoped skill may use its upstream package implementation.
4. Prove from the fresh manifest/report/read-side CLI that:
   - projection Markdown inputs were consumed;
   - native Python nodes remain present;
   - the exact generated literature full-identity H1 and linked PDF/TeX-proxy
     full-identity H1 are known;
   - public `graphify path "<literature H1>" "<asset H1>" --graph <fresh>`
     proves their reference when sufficient;
   - raw `.tex`/`.pdf` backlinks are not misreported as native direct edges.
5. If public CLI is insufficient, inspect the fresh public graph JSON read-only
   and assert a file-to-file `references` edge whose two `source_file` values
   equal the expected literature and asset projection Markdown files. Public
   output is test evidence only and is never modified.
6. Record Graphify version, exact upstream command, Codex-subagent semantic
   extraction route (never credential material), source revision, both H1
   labels, both `source_file` values, output root, and observed edge; then
   remove temp output.

An old graph, read-only query without fresh extraction, manifest filename alone,
or a code-only run that omitted Markdown fails this gate. If the authenticated
upstream skill route cannot produce the proof without forbidden credential or
local-lifecycle work, retain the dormant legacy lifecycle and do not publish
the replacement PR. Do not add CI credentials or patch graph JSON.

## Verification sequence

1. Ruff format/check adapter and tests.
2. Run hermetic sections 1-7 and repository sections 8-9.
3. Run live `--check`, double-build, digest/dirt, and ignore checks.
4. Compile/query Typst including headings.
5. Run `make ci-impact-self-test`.
6. Run `make scaffold-audit scaffold-audit-self-test` and
   `make graphify-projection-self-test`.
7. Run `make agents-db-validate check-agent-memory` plus existing docs/package
   checks selected by the final diff.
8. Pass and record the hard upstream consumption gate.
9. Only then delete the dormant lifecycle and run repository section 10 plus
   forbidden-live-consumer searches.
10. On that exact post-deletion/guidance final tree, rerun
    `make scaffold-audit scaffold-audit-self-test`,
    `make check-agent-memory`, and `make graphify-projection-self-test`.
    Pre-deletion results do not satisfy this gate.
11. Run `git diff --check`, independent code review, and Architect `CLEAR` on
   exact HEAD.
12. Push the one replacement PR and wait for terminal green hosted CI; verify
    mergeability and zero unresolved valid P0-P2 threads at exact head.

## Interpretation

- Unit/live-owner failure: adapter or canonical relationship is not ready; do
  not weaken matching silently.
- Valid projection plus failed/unavailable upstream gate: retain dormant
  lifecycle and publish nothing.
- Unmatched record or missing optional asset: explicit status, not failure.
- Ambiguous/multiplicity-mismatched identity: failure.
- Green hosted CI: repository-contract evidence only, not Graphify freshness,
  scientific claim correctness, or PDF-page provenance.

## Required evidence bundle

- source/pushed head SHAs and exact changed/deleted paths;
- production/test/generated/deleted/upstream LOC, reported separately and never
  used as a gate;
- hermetic, live, Typst, CI-routing, root-check, and hard upstream-gate outcomes;
- include-closure, multiplicity, ref-qualified code, join/unmatched, proxy, and
  asset-presence counts;
- exact Graphify command, both full-identity H1 labels, both fresh projection
  `source_file` values, and evidence proving the `references` edge;
- confirmation generated output, local assets, credentials, and user skill were
  not staged;
- retained/replaced/removed/deferred/open dispositions;
- independent review, Architect, hosted-CI, mergeability, and unresolved-thread
  status at exact head.

## Acceptance

All repository checks and the hard upstream consumption gate pass before
deletion; no forbidden lifecycle remains afterward; exact pushed-head CI is
green; and no valid P0-P2 finding remains unresolved. If the upstream gate
cannot pass, acceptance is not met and the dormant lifecycle remains.
