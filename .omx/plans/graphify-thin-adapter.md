---
kind: plan
status: approved-ready-for-ultragoal
owner: scaffold-tooling
decision: upstream-plus-one-thin-adapter
context: .omx/context/graphify-thin-adapter-20260731T175054Z.md
test_spec: .omx/plans/test-spec-graphify-thin-adapter.md
---

# Upstream Graphify with one thin source-link projection

## Desired result

Replace ARIA-NBV's dormant 2,738-LOC Graphify lifecycle with one small,
tracked, deterministic Markdown projection builder. The builder preserves and
validates source-owned relationships among active thesis sources, explicit
thesis code links, both bibliographies, `docs/literature/sources.jsonl`, and
the corresponding local TeX/PDF assets. Unmodified, user-installed upstream
Graphify may ingest native code/docs plus the ignored projection.

Exact sources remain authoritative and fully usable without Graphify. No
Graphify install, graph refresh, freshness check, hook, semantic backend, or
generated output becomes a repository or CI prerequisite.

## Success criteria

1. A standard-library CLI builds the same projection bytes from the same
   source bytes and revision context.
2. Every emitted relationship carries repository-relative source locators and
   identifies whether it was explicitly extracted, deterministically joined,
   ambiguous, or unresolved.
3. Active citations resolve against both bibliography owners. Manifest joins
   use only deterministic identities; no fuzzy match or inferred scientific
   link is emitted.
4. Explicit `gh`/`gh-wip` path targets are validated when present. No code link
   is created merely because code and thesis discuss similar concepts. Each
   target identity includes repository, source-ref spelling, resolved OID, path,
   and line range; same-path links at different source refs never collapse even
   when those refs resolve to the same commit.
5. Declared TeX/PDF asset paths are represented by lexical repository-relative
   identity and explicit `present`/`missing-local` status through Markdown proxy
   pages. Their content is not parsed and PDF-page or TeX-file/section nodes are
   not created.
6. Generated pages are ignored, local, reproducible, and admitted to the
   optional Graphify corpus without admitting raw Typst/TeX/BibTeX/JSONL or the
   full PDF corpus.
7. The old vendored skill, refresh/freshness/integration scripts, post-commit
   hook, custom tests, version pin, Make targets, CI family/install, and special
   validation exceptions are gone.
8. Root guidance describes Graphify as optional derived navigation and gives
   exact-source fallback first. Current-main Aria-Grill and direct-skill
   governance is preserved after rebase.
9. Fresh local verification and exact pushed-head hosted CI are green. The PR
   contains no thesis scientific prose, package semantics, generated graph,
   local PDF/TeX churn, or user-scoped installation state.
10. A real upstream Graphify extraction consumes the generated Markdown and
    proves one expected proxy traversal before the legacy lifecycle is deleted
    or the replacement PR is published.

## Non-goals

- Parse or summarize scientific TeX/PDF content.
- Add thesis-to-code links to the currently link-free active thesis.
- Modify Python scientific/domain behavior or docstrings.
- Create a Graphify plugin, import API, graph fragment, schema mirror, graph
  writer, graph merger, global graph, watcher, hook, freshness daemon, or cache.
- Guarantee a native Graphify edge from a projection page to `.py`, `.typ`,
  `.bib`, `.tex`, or `.pdf`; upstream 0.9.31 does not provide that contract.
- Treat Graphify traversal as evidence for a thesis claim.
- Ingest all local PDFs or TeX files into the default graph.
- Model PDF pages, TeX files/sections, or extracted paper content.
- Add dependencies, a generic knowledge ontology, dashboard, scoring system, or
  second literature catalogue.
- Change the source-link macros or bibliography content except to correct a
  demonstrably broken existing identity in a separately reviewed owner change.

## RALPLAN-DR

### Principles

1. **One durable owner:** projection pages point to exact source owners and
   never restate scientific truth as authority.
2. **Upstream first:** ARIA owns only the missing source-to-Markdown projection;
   upstream owns extraction, graph structure, query, path, and explain.
3. **Optional by construction:** exact-source work, ordinary hooks, and hosted
   CI do not require Graphify or generated projection state.
4. **Explicit provenance over inference:** every link has a lexical source
   locator, deterministic identity rule, and ambiguity status.
5. **Reviewable deletion:** a real upstream consumption proof precedes removal
   of the dormant lifecycle, with one PR-level rollback boundary.

### Top decision drivers

1. Preserve thesis-code-citation-local-source traversal without making a graph
   a competing source of truth.
2. Minimize repository-owned code and eliminate the measured legacy lifecycle.
3. Stay inside upstream 0.9.31's documented public CLI/input contracts and
   retain green, credential-free hosted CI.

### Options considered

#### Option A — Unmodified upstream only

Pros:

- Zero repository Graphify implementation LOC.
- Smallest maintenance and strongest upstream ownership.

Cons:

- Typst, BibTeX, JSONL, and TeX identities are not natively represented.
- It cannot preserve the requested deterministic chain from thesis citation to
  bibliography, manifest, and local source assets.

Decision: rejected after the measured gap and the user's explicit selection of
option 3.

#### Option B — Deterministic ignored Markdown evidence projection

Pros:

- Uses a natively supported upstream input modality.
- Keeps source relationships usable without Graphify.
- Requires no Graphify internals, graph schema, backend, or new dependency.
- Can be unit-tested hermetically and inspected as plain text.
- Replaces the custom lifecycle with a bounded data transformation.
- Uses Markdown proxy pages for code/PDF/TeX-root identities while preserving
  raw-owner backlinks and reference-qualified identity.

Cons:

- Cross-modal Graphify traversal terminates at projection identity pages rather
  than native Python/PDF/TeX nodes.
- A small amount of ARIA code remains to validate and project unsupported
  owner formats.

Decision: selected.

#### Option C — Direct Graphify graph post-processing or fragment import

Pros:

- Could create direct edges to native graph nodes.

Cons:

- No documented stable extractor-plugin or graph-fragment import API exists.
- ARIA would own Graphify schema/lifecycle compatibility and stale-state rules.
- Repeats the main failure mode of the old custom integration.

Decision: rejected. If native cross-modal nodes become necessary, propose and
land an upstream extension first.

#### Option D — Parse all Typst, TeX, BibTeX, JSONL, and PDFs locally

Pros:

- Richest possible repository-specific graph.

Cons:

- High parser and scientific-provenance complexity.
- Duplicates compiler/bibliography/PDF behavior and invites false claim links.
- Violates the accepted target state and minimal-implementation requirement.

Decision: rejected.

## ADR

### Decision

Track one Python CLI, provisionally
`scripts/build_graphify_projection.py`, plus focused tests. It reads canonical
owners and emits ignored Markdown under `graphify-input/` through a validated
sibling-temp and in-process backup swap. Upstream Graphify consumes the projection
together with native code and Markdown documents. Delete the old ARIA Graphify
lifecycle only after the replacement tests and a real upstream extraction pass.

### Drivers

- Upstream lacks native Typst/BibTeX/JSONL/TeX support and a public plugin API.
- The requested relationships already have exact source owners and identifiers.
- The old integration's cost is disproportionate to its proven navigation
  utility.

### Alternatives

- Upstream only: insufficient for the explicitly selected cross-modal seam.
- Direct graph post-processing: unstable, schema-coupled, rejected.
- Full local multimodal parser: excessive and scientifically unsafe, rejected.

### Why this choice

Markdown is upstream-supported, human-inspectable, and sufficient to express a
derived identity network without claiming unsupported direct native-node
edges. A source projection is also usable when Graphify is absent, so the
adapter cannot become the only representation of a relationship.

### Consequences

- The repo maintains one small metadata projection transform.
- Graphify explains projection-to-proxy edges; humans follow exact backlinks to
  authoritative non-Markdown sources.
- The root graph omits raw TeX and bulk PDFs by default.
- Native direct cross-modal edges remain an upstream feature request, not local
  debt.
- Generated output can be discarded and rebuilt from owners. Caught swap
  failures restore the backup; a later normal build discards stale temp/backup
  debris and rebuilds. No persistent recovery or crash/power-loss guarantee is
  claimed.

### Follow-ups

- Re-evaluate only if a real task demonstrates that proxy identity pages are
  insufficient.
- Any request for direct native edges begins with an upstream issue/PR and a
  bounded comparison; it does not expand this adapter.

## Deterministic projection contract

### CLI

Target command:

```bash
python3 scripts/build_graphify_projection.py \
  --output graphify-input \
  --aria-code-ref FULL_SHA_OR_RELEASE_TAG
```

Optional read-only validation:

```bash
python3 scripts/build_graphify_projection.py --check \
  --aria-code-ref FULL_SHA_OR_RELEASE_TAG
```

CLI rules:

- Repository root and owner paths have explicit defaults; tests may override
  every input and output path with fixture roots.
- `--aria-code-ref REF` is the single configuration source for Typst's
  `aria-code-ref` input. It defaults deterministically to `main` to match the
  development build, but any inherited final `gh` then fails pin validation.
  Pass the same exact value as `--input aria-code-ref=<REF>` to every `cite`,
  `link`, and `heading` query and to the independent thesis compile used for
  verification. Record the value, whether it came from CLI or the default, pin
  kind, and resolved OID in projection provenance. Do not add a config file or
  environment-variable fallback.
- `--check` parses, compiles/queries, validates, joins, and renders in memory or
  a temporary directory; it does not require or mutate `graphify-input/`.
- A normal build discards stale sibling temp/backup debris, writes and validates
  a new sibling temp tree, renames the previous output to a backup, then renames
  the validated temp tree into place. Any caught failure during that in-process
  swap restores the backup before returning nonzero; success removes it.
- `--check` is read-only: it reports stale temp/backup debris without deleting,
  restoring, or swapping anything.
- There is no completion marker, persistent recovery state, or kill/power-loss
  atomicity guarantee. A later normal build simply discards debris and rebuilds
  from owners.
- The CLI never invokes Graphify, writes `graphify-out/`, installs hooks/skills,
  contacts the network, or resolves symlinks into emitted machine paths.
- Exactly `git` and `typst` may run through one injectable command runner. No
  shell invocation or other subprocess is permitted.
- Exit 0 means the projection was validated (and built unless `--check`). Exit
  nonzero prints a concise owner path, locator/identity, and remediation.

### Inputs

- Active thesis root: `docs/typst/thesis/main.typ` plus the transitive closure of
  literal repository-local Typst include/import paths. Inactive sibling `.typ`
  files are not scanned. Dynamic/computed include paths are unsupported and
  fail with their source locator.
- Link macro contract: `docs/typst/shared/style.typ`.
- Bibliographies: `docs/references.bib`, then `docs/references-qh.bib` as equal
  identity owners; file order never resolves duplicate keys.
- Literature catalogue: `docs/literature/sources.jsonl`, preserving one-based
  JSONL line numbers.
- Assets: lexical paths beneath `docs/literature/tex-src/` and
  `docs/literature/pdf/`.
- Code targets: explicit repository-relative paths named by actual `gh` or
  `gh-wip` callsites, qualified by the compiled destination ref. Upstream
  Graphify continues to parse package code natively; the adapter does not
  inventory all code.

### Compiled truth and exact locators

- Invoke `typst query` for compiled `cite`, `link`, and `heading` elements using
  the active thesis root and the same exact
  `--input aria-code-ref=<CLI_VALUE>` on every call. A missing Typst executable
  or failed query is a build error for this optional command, not a
  repository-wide blocker.
- Build the active source closure conservatively. The narrow lexer must exclude
  comments and raw/code blocks and must fail on dynamic includes rather than
  scanning the whole thesis directory.
- Scan only that closure for citation tokens and explicit
  `gh`/`gh-wip`/`gh-symbol` candidates. Reconcile per-identity compiled-query
  multiplicity with lexical multiplicity for citations and compiled link
  destinations. A mismatch is an error; duplicate destinations do not permit
  arbitrary pairing.
- Filter compiled links before reconciliation. Admit only:
  - exact URLs in the configured repository GitHub
    `<base>/blob/<ref>/<path>#L...` namespace used by `gh`/`gh-wip`;
  - the exact configured repository GitHub search namespace produced by
    `gh-symbol`, including repository and language/symbol query fields.
  Internal Typst links, bibliography URLs, and unrelated external links are
  outside adapter scope and do not affect candidate multiplicity.
- Do not create a standalone `thesis-link` identity. Attach relations to the
  owning `thesis-source` page. When each lexical occurrence is uniquely proven,
  emit one relation with semantic target, deterministic source-order ordinal,
  total multiplicity, and exact line/column. When compiled/lexical multiplicity
  agrees but only file precision is provable, emit one aggregated relation with
  source file, semantic target, and `occurrence_count`; omit ordinal and
  line/column. If more than one active file remains possible, fail as ambiguous.
  Never attach a guessed line.
- `gh-symbol` remains a dynamic, draft-only search identity. Emit it as
  `unresolved-dynamic` with its source locator; do not guess a local Python
  definition or create a direct edge.

### Stable generated identities

Generated IDs are navigation identities, never canonical IDs:

- `thesis-source:<repo-relative-path>`
- `code-target:<repository>@<source-ref>[<resolved-oid>]:<repo-relative-path>:<line-range>`
- `citation:<bib-key>`
- `literature:arxiv:<normalized-id>`, else `literature:doi:<normalized-doi>`,
  else `literature:url:<normalized-url>`, else
  `literature:manifest-line:<line>`
- `tex-root:<repo-relative-path>`
- `pdf:<repo-relative-path>`

Filenames use a collision-resistant digest of the full generated ID plus a
short readable prefix. No Graphify node ID, search position, absolute path, or
runtime ID is persisted. Source-ref spelling and resolved OID are both identity
components; a tag and literal SHA pointing to the same commit intentionally
produce different identities/pages. A code-target page owns only target facts:
repository, source-ref spelling, resolved OID, path, line range, and separate
target validation status against the resolved Git object and current worktree.
The thesis-source relation exclusively owns `macro_kind`, compiled URL,
`pin_kind` (`full-sha`, `release-tag`, or `mutable`), occurrence or multiplicity,
and thesis source locator. A target page may render backlinks derived from
those relations, but must not persist an independent copy of relation metadata.
A release tag must exist under `refs/tags/` and resolve to a commit; record both
tag spelling and resolved OID as target facts. Final `gh` accepts only
`full-sha` or verified `release-tag`. Mutable refs are valid only for `gh-wip`;
`gh(ref: "main")` is a hard error. `git` resolves the ref and reads non-HEAD
target content.

A macro call with no explicit `ref` inherits the single CLI
`--aria-code-ref`. Inherited full SHA and verified release tag are valid for
final `gh`; inherited default `main` is rejected whenever a final `gh` exists.
Explicit macro refs still determine their own source-ref identity, but all
compiled queries receive the same CLI input so compiled URLs remain
reproducible.

The repository component comes from the compiled GitHub URL and must agree with
the repository configured by the source-link owner in
`docs/typst/shared/style.typ`. Validate path/line against the resolved Git
object. Record current-worktree status independently as `same-ref-clean`,
`same-ref-owner-dirty`, `different-ref-path-present`, or
`different-ref-path-absent`; absence at a different historical ref is factual,
not an error.

### Bibliography-to-manifest joins

Join in this strict precedence:

1. normalized arXiv ID;
2. normalized DOI;
3. normalized canonical URL.

Normalization is deliberately narrow:

- arXiv: case-fold; strip `arXiv:` or an arXiv URL prefix and a terminal version
  suffix such as `v2`;
- DOI: case-fold; strip `doi:` or `https://doi.org/`; preserve the remaining
  identifier bytes except surrounding whitespace;
- URL: parse structurally; case-fold scheme/host, normalize an empty path to
  `/`, and remove only a terminal `/`; do not drop query/fragment data;

At the first available matching precedence, exactly one record may match.
Multiple candidates or conflicting higher/lower identity signals are errors.
Records with no deterministic match are emitted as explicit `unmatched`
identities. They are not silently dropped or joined by short title.
The BibTeX reader extracts only entry key plus eprint/arXiv, DOI, and URL fields
needed by these rules. It does not parse BibTeX titles; the manifest's own title
is display text only and never a join key.

### Projection pages

Emit sorted UTF-8 Markdown with LF endings:

```text
graphify-input/
  index.md
  thesis/*.md
  code/*.md
  citations/*.md
  literature/*.md
  assets/*.md
```

- `index.md` states non-authority, source revision, owner-input dirty/clean
  state, generator schema version, owner paths/digests, counts, errors/warnings,
  and links to each projection family.
- Every generated page uses its complete generated identity as the H1; the
  exact H1 label is the read-side traversal identity used by the upstream smoke.
- Thesis-source pages link to citation/code identity pages only for explicit
  source tokens. Each code relation owns macro kind, compiled URL, pin kind,
  thesis source locator, and either exact occurrence metadata
  (`ordinal`/`multiplicity`/line/column) or one file-precision aggregated
  relation (`occurrence_count`, no ordinal or line). Code-target pages contain
  only target facts; any displayed backlinks are derived from these relations.
- Citation pages link to the exact BibTeX owner/entry locator and, when joined,
  one literature page.
- Literature pages link to the JSONL line, matched citations, and generated
  TeX-root/PDF proxy pages. Each proxy records the lexical raw-owner path with
  `present` or `missing-local` status, so Graphify observes
  `literature -> proxy` while humans follow `proxy -> raw owner`.
- PDF proxies state `page_locator: unavailable`; TeX-root proxies state
  `content_parsed: false`. TeX file/section nodes, PDF-page nodes, and content
  parsing are explicitly deferred.
- Backlinks to non-Markdown owners are ordinary relative Markdown links for
  humans. Only links among projection `.md` pages are promised Graphify edges.
- Revision provenance is `git rev-parse HEAD`, exact owner path/locator, and
  SHA-256 of every owner input byte stream. Dirty/clean state is computed only
  for the enumerated owner inputs, not unrelated worktree paths. No timestamp
  enters deterministic page content.

### Generated-output and corpus policy

- Add `/graphify-input/` to `.gitignore` and keep `graphify-out/` ignored.
- Update `.graphifyignore` so root extraction admits:
  - package code supported by upstream;
  - maintained Markdown/QMD/RST/text/YAML/HTML docs already in scope;
  - `graphify-input/**/*.md`.
- Remove ineffective admissions for raw `.typ`, `.bib`, `.jsonl`, and `.tex`.
- Keep `docs/literature/pdf/` and `docs/literature/tex-src/` excluded from the
  default root graph. Their identities are represented in the projection.
- A bounded direct upstream PDF extraction is an explicit operator experiment
  in a separate output directory; it is never merged into or required by the
  root graph.

### Failure semantics

Hard errors, with no output replacement:

- missing/unexecutable Typst or failed compiled query;
- malformed JSONL/BibTeX needed for the selected fields;
- dynamic/computed Typst include/import path or include escaping the repository;
- compiled/lexical identity multiplicity mismatch or multi-file locator
  ambiguity;
- duplicate BibTeX key across owners;
- active compiled citation absent from both bibliographies;
- unresolved Git ref, missing target at resolved ref, missing current-worktree
  target when applicable, invalid line range, or compiled/lexical destination
  mismatch for `gh`/`gh-wip`;
- mutable final `gh` ref, including inherited default `aria-code-ref=main`, or
  unresolvable/non-tag release-tag claim;
- duplicate generated ID/filename;
- ambiguous or conflicting deterministic join;
- output path outside the repository or overlapping an owner/input path.

Explicit non-fatal records:

- valid bibliography or manifest entry with no deterministic counterpart;
- `gh-symbol` dynamic identity;
- bibliography entries not cited by the active thesis;
- declared local TeX/PDF asset absent from this checkout (`missing-local`, with
  the existing acquisition command);
- owner-input dirty state (record per-input SHA-256 and scoped status).

The builder never claims the previous output is fresh. A caught validation/swap
failure restores/leaves the prior output and exits nonzero. Stale temp/backup
debris from an interrupted process is reported by `--check`; a later normal
build discards it and rebuilds. There is no completion marker, persistent
recovery machine, or crash/power-loss guarantee.

## Work packages

### WP0 — Rebase and preserve current governance

1. Fetch and rebase `codex/graphify-upstream-adoption` onto exact
   `origin/main` (`8d1043f6` at planning time; re-resolve immediately before
   execution).
   Record the fetched SHA. If it changed, repeat the current-main diff/deletion
   inventory and update the debrief before resolving conflicts.
2. Resolve `AGENTS.md`, `Makefile`, `.github/workflows/ci.yml`,
   `scripts/tests/test_ci_impact.py`, and
   `scripts/tests/test_graphify_integration.py` conflicts in favor of:
   - current-main Aria-Grill/direct-skill and MemPalace governance;
   - the already accepted optional-Graphify boundary from `80eab1ee`;
   - no reintroduction of mandatory Graphify CI, hooks, or routing.
3. Re-run the comparison record checks before adapter edits. Do not count
   rebase-only drift as adapter work.
4. Prove `git merge-base --is-ancestor origin/main HEAD` after rebase and list
   every remaining live Graphify consumer from the rebased tree. The WP4
   inventory is evidence from the planning head, not permission to delete a
   newly changed current-main owner blindly.

Stop if current main contains a new accepted Graphify decision that supersedes
the target-state spec or the user's option-3 selection.

### WP1 — Lock the projection behavior in fixtures

Add `scripts/tests/test_build_graphify_projection.py` first. Use temporary
repositories, tiny Typst/BibTeX/JSONL/code/asset fixtures, and a fake compiled
query runner. Cover every case in the accompanying test spec before deletion.

No test imports Graphify or requires network, PDF content, Git LFS, the full
literature corpus, or a semantic backend.

### WP2 — Implement the single adapter

Add `scripts/build_graphify_projection.py` as one module with small factual
records and pure functions for:

- owner loading and source locators;
- narrow BibTeX metadata extraction;
- deterministic identity normalization/join;
- compiled Typst query orchestration plus source-token location;
- link/asset validation;
- deterministic Markdown rendering;
- validated sibling-temp plus in-process backup/swap/restore and CLI reporting;
  normal-build debris cleanup, with read-only debris reporting in `--check`.

Keep the implementation in one file unless the test file proves a second
production module reduces, rather than increases, the total interface. Do not
generalize it into a graph library. Report production, test, generated, deleted,
and upstream LOC separately as review evidence; no LOC value is an acceptance
gate.

### WP3 — Set the optional corpus and operator contract

Modify:

- `.gitignore`: ignore `graphify-input/`; remove vendored-skill exceptions after
  WP6 deletion.
- `.graphifyignore`: admit native upstream formats and generated Markdown only;
  keep raw source/bulk assets excluded.
- `docs/literature/README.md`: document exact owners, projection command,
  non-authority, and raw-asset exclusion.
- `docs/AGENTS.md`: correct the bibliography owner statement to include both
  `docs/references.bib` and `docs/references-qh.bib`; do not change citation
  content.
- `AGENTS.md`: replace mandatory Graphify routing with a short optional-tool
  pointer: exact sources first; when a local graph/projection exists, qualify
  revision and verify consequential links in source.
- `.agents/references/human_owner_intent.md`: record the explicit option-3
  selection and thin-adapter boundary.
- `.agents/references/source_order.md`: change only if the rebase reintroduces a
  contradictory Graphify owner statement; otherwise leave it unchanged.

Do not add a project-local Graphify skill. The upstream skill remains
user-scoped and optional.

### WP4 — Freeze the legacy deletion inventory

Confirm the exact paths to delete after the upstream gate:

- `.codex/skills/graphify/**`
- `scripts/graphify_refresh.py`
- `scripts/check_graphify_freshness.py`
- `scripts/check_graphify_integration.py`
- `scripts/git_hooks/post-commit`
- `scripts/tests/test_graphify_freshness.py`
- `scripts/tests/test_graphify_integration.py`
- `scripts/tests/test_post_commit_graph_dispatch.sh`

Confirm the exact live consumers to update after the upstream gate:

- `Makefile`: remove `graphify-skill-self-test`,
  `graphify-integration-self-test`, `graphify-ci`, and
  `install-graphify-git-hook`; add the lightweight
  `graphify-projection-self-test` target for unconditional execution inside the
  credential-free docs CI job.
- `.github/workflows/ci.yml`: remove Graphify install/validation and legacy
  paths. The docs job always runs `graphify-projection-self-test`; hosted CI
  never installs Graphify or builds a graph.
- `scripts/ci_impact.py` and `scripts/tests/test_ci_impact.py`: remove the
  `graphify` family; route the builder, its test, `.graphifyignore`,
  `docs/literature/sources.jsonl`, and literature projection documentation to
  `docs` (and governance/debrief paths to `scaffold`) using existing fail-closed
  rules.
- `scripts/validate_agent_memory.py`: remove the special
  `.codex/skills/graphify/` allowance.
- `.gitignore`: remove project-vendored Graphify skill reincludes.

Do not delete or update these paths yet. Re-check them against the rebased
current main immediately before the upstream gate; historical
debrief/transcript references remain provenance and are not rewritten.

### WP5 — Validate the live owner corpus and upstream consumption

1. Run the builder against the live repository into a temporary output and
   then `graphify-input/`.
2. Review all errors, warnings, unmatched joins, counts, and lexical asset
   paths. Do not weaken matching rules to improve coverage.
3. Compile/query the active thesis independently, including separate `cite`,
   `link`, and `heading` queries.
4. With user-installed upstream Graphify 0.9.31, first inspect exact CLI help
   and determine whether Markdown structural extraction can run without a
   semantic backend. Run the smallest public command that actually consumes
   the projection; if full document extraction requires a backend, use only an
   already-authorized backend. Record the exact command and evidence. Then
   prove:
   - native Python nodes remain present;
   - projection Markdown pages are present;
   - one exact literature full-identity H1 and its linked asset-proxy
     full-identity H1 are connected by a file-to-file `references` edge;
   - direct `.py`/`.pdf`/`.tex` backlinks are reported as human provenance,
     not asserted Graphify edges;
   - stale/wrong-root output is not treated as current evidence.
5. Prefer public `graphify path "<literature H1>" "<asset H1>" --graph ...`
   when it proves the exact edge. If read-side CLI is insufficient, inspect the
   fresh public `graph.json` read-only and assert a `references` edge whose two
   `source_file` values equal the expected fresh projection Markdown files.
   Reading public output is test evidence; never modify it.
6. Record the exact upstream version, command, H1 labels, projection
   `source_file` values, output root, source revision, and observation in the
   final debrief. Do not track the graph.

This is a hard deletion/publication gate. A manifest or read-side query over an
old graph is insufficient: the fresh extraction must name projection Markdown
inputs and demonstrate the expected proxy traversal. If upstream cannot
consume the projection, or requires a backend that is not authorized/available,
keep the dormant legacy lifecycle and do not publish the replacement PR. Do not
add a CI secret or backend to bypass the gate.

### WP6 — Delete the legacy lifecycle after the gate

Only after WP5 passes, perform the WP4 deletion/update inventory exactly. Run
the live-consumer search again, preserve historical provenance, and verify that
the credential-free projection self-test remains unconditional in the docs CI
job. If the inventory changed on current main, update the plan/debrief before
deleting newly discovered live behavior.

After every legacy deletion and guidance/CI edit is present, rerun on the exact
final tree:

```bash
make scaffold-audit scaffold-audit-self-test
make check-agent-memory
make graphify-projection-self-test
```

Pre-deletion passes do not satisfy this post-deletion gate.

### WP7 — Review, publication, and exact-head closure

1. Update the comparison debrief to `complete` and record the option-3
   selection, retained/replaced/removed/deferred/open dispositions, exact test
   evidence, and `canonical_updates_needed`.
2. Add one implementation debrief only if the existing comparison debrief
   cannot accurately own the final replacement evidence without conflating
   comparison and implementation. Prefer one final record.
3. Run independent code review. Publish and resolve actionable P0-P2 GitHub
   review threads under `code-review-aria-nbv` policy.
4. Obtain Architect `CLEAR` on exact HEAD.
5. Commit task-owned paths only, push, create/update one PR with the replacement
   concern, and monitor every required hosted check to terminal green.
6. Re-check exact remote head SHA, mergeability, PR diff, and unresolved review
   threads before declaring completion.

## Recommended PR boundary and commit shape

Use one replacement PR from the rebased branch because the comparison commits,
thin adapter, and deletion form one independently reversible Graphify-role
decision. Do not open/publish that replacement PR until WP5 proves real upstream
consumption; before then all adapter work remains local and the dormant legacy
lifecycle remains intact. Keep review separation in commits:

1. `docs(agents): record optional Graphify selection` — rebased comparison and
   human decision, no adapter behavior.
2. `test(graphify): lock source projection contract` — fixtures and failing
   behavior tests.
3. `feat(graphify): build optional source-link projection` — one adapter,
   corpus policy, minimal docs.
4. `refactor(graphify): remove legacy lifecycle` — deletions and CI/Make/live
   consumer cleanup.
5. `docs(agents): record Graphify replacement evidence` — final debrief only.

PR title:

> Replace custom Graphify lifecycle with an optional source-link projection

If the rebased comparison diff remains too large or reviewers cannot assess the
evidence separately, split commit 1 into a preparatory evidence-only PR, then
base commits 2-5 on its merged head. Do not split adapter addition from legacy
deletion into independently mergeable long-lived states unless the first PR
keeps the legacy dormant; the replacement proof must exist before deletion.

## Exact file disposition

### Add

- `scripts/build_graphify_projection.py`
- `scripts/tests/test_build_graphify_projection.py`
- `.omx/context/graphify-thin-adapter-20260731T175054Z.md` (planning only)
- `.omx/plans/graphify-thin-adapter.md` (planning only)
- `.omx/plans/test-spec-graphify-thin-adapter.md` (planning only)

### Modify if required by the final rebased diff

- `.gitignore`
- `.graphifyignore`
- `AGENTS.md`
- `docs/AGENTS.md`
- `docs/literature/README.md`
- `.agents/references/human_owner_intent.md`
- `.agents/references/source_order.md` only for a real contradiction
- `.agents/memory/history/2026/07/2026-07-31_graphify_upstream_adoption.md`
- `Makefile`
- `.github/workflows/ci.yml`
- `scripts/ci_impact.py`
- `scripts/tests/test_ci_impact.py`
- `scripts/validate_agent_memory.py`

### Delete

- `.codex/skills/graphify/.graphify_version`
- `.codex/skills/graphify/SKILL.md`
- `.codex/skills/graphify/references/*.md`
- `.codex/skills/graphify/scripts/check_run_isolation.py`
- `scripts/graphify_refresh.py`
- `scripts/check_graphify_freshness.py`
- `scripts/check_graphify_integration.py`
- `scripts/git_hooks/post-commit`
- `scripts/tests/test_graphify_freshness.py`
- `scripts/tests/test_graphify_integration.py`
- `scripts/tests/test_post_commit_graph_dispatch.sh`

### Never stage

- `graphify-input/**`
- `graphify-out/**`
- local PDFs, TeX downloads, worktree symlinks, caches, backend credentials, or
  user-scoped `~/.codex/skills/graphify/**`

## Verification commands

Resolve exact flags against the rebased tree, then run in this order:

```bash
git status --short --branch
git diff --check

ruff format scripts/build_graphify_projection.py \
  scripts/tests/test_build_graphify_projection.py
ruff check scripts/build_graphify_projection.py \
  scripts/tests/test_build_graphify_projection.py

python3 scripts/tests/test_build_graphify_projection.py
python3 scripts/build_graphify_projection.py --check \
  --aria-code-ref FULL_SHA_OR_RELEASE_TAG
python3 scripts/build_graphify_projection.py --output graphify-input \
  --aria-code-ref FULL_SHA_OR_RELEASE_TAG
python3 scripts/build_graphify_projection.py --output graphify-input \
  --aria-code-ref FULL_SHA_OR_RELEASE_TAG

cd docs
typst compile typst/thesis/main.typ /tmp/aria-thesis-graphify-plan.pdf --root . \
  --input aria-code-ref=FULL_SHA_OR_RELEASE_TAG
typst query typst/thesis/main.typ cite --root . --pretty \
  --input aria-code-ref=FULL_SHA_OR_RELEASE_TAG
typst query typst/thesis/main.typ link --root . --pretty \
  --input aria-code-ref=FULL_SHA_OR_RELEASE_TAG
typst query typst/thesis/main.typ heading --root . --pretty \
  --input aria-code-ref=FULL_SHA_OR_RELEASE_TAG
cd ..

make ci-impact-self-test
# Pre-deletion baseline only; repeat after WP6 on the exact final tree.
make scaffold-audit scaffold-audit-self-test
make graphify-projection-self-test
make agents-db-validate check-agent-memory
make qmd-frontmatter-check api-docs-self-test docs-render-core
make package-smoke PYTEST_ARGS=

git grep -n -E \
  'check_graphify_freshness|graphify_refresh|check_graphify_integration|install-graphify-git-hook|graphify-ci|\.codex/skills/graphify' \
  -- ':!*.md' ':!.agents/memory/**' ':!.omx/**'
git status --ignored --short graphify-input graphify-out

# Required after WP6 deletion plus all guidance/CI edits.
make scaffold-audit scaffold-audit-self-test
make check-agent-memory
make graphify-projection-self-test

git diff --check
```

Required upstream 0.9.31 consumption gate, into a disposable directory and
never tracked:

```bash
graphify --version
graphify extract . --no-cluster --out /tmp/aria-graphify-option3
graphify path "<exact literature full-identity H1>" \
  "<exact asset full-identity H1>" \
  --graph /tmp/aria-graphify-option3/graphify-out/graph.json
```

The executor first checks exact 0.9.31 CLI help and uses a backend-free Markdown
extraction path if upstream supports one. Otherwise an already authorized
backend is required. The evidence must show that this fresh command consumed
`graphify-input/**/*.md` and that `path` traverses between the exact generated
literature and asset full-identity H1 labels. If public CLI output is
insufficient, read the fresh public graph JSON without modifying it and assert
the file-to-file `references` edge with both expected projection `source_file`
values. Code-only extraction, an old graph, or manifest presence without the
edge is insufficient. Do not import Graphify's package or add
credentials/installation to hosted CI.

Hosted CI must run `graphify-projection-self-test` unconditionally whenever the
docs job runs. Impact routing must select docs for the builder, its test,
`.graphifyignore`, `docs/literature/sources.jsonl`, and the literature README.
Hosted CI must not install/run Graphify. After push:

```bash
gh pr checks <pr-number> --watch
gh pr view <pr-number> --json headRefOid,mergeable,reviewDecision,statusCheckRollup
```

## Acceptance checklist

- [ ] Branch is rebased onto current `origin/main`; Aria-Grill/direct-skill
      governance is preserved.
- [ ] Exact-source navigation succeeds with `graphify` absent from `PATH`.
- [ ] Adapter is one tracked standard-library script; no new dependency.
- [ ] Same inputs/revision produce byte-identical generated Markdown.
- [ ] Owner-input SHA-256 values and owner-scoped Git dirty status are recorded;
      unrelated dirt does not change provenance status.
- [ ] Active citations compile and resolve across both BibTeX owners.
- [ ] Join precedence and ambiguity behavior match the deterministic contract.
- [ ] Active Typst closure contains only literal repository-local includes;
      dynamic includes and compiled/lexical multiplicity ambiguity fail.
- [ ] Compiled-link reconciliation admits only the configured repository GitHub
      `/blob/` namespace and exact `gh-symbol` search namespace; mixed internal
      and unrelated external links remain outside adapter scope.
- [ ] One explicit `--aria-code-ref` value is passed as the exact
      `--input aria-code-ref=<VALUE>` to every Typst query and the independent
      Typst compile, and recorded with source/pin/OID provenance. Inherited SHA
      and verified tag pass; inherited default `main` fails when a final `gh`
      exists.
- [ ] All declared local TeX/PDF paths are reported lexically with explicit
      presence status through Markdown proxy pages; absolute symlink targets
      never appear.
- [ ] Existing explicit thesis code links validate as
      `repository@source-ref[resolved-oid]:path:line-range`. Code-target pages
      contain only repository/ref/OID/path/range and target validation facts;
      thesis-source relations exclusively preserve macro kind, compiled URL,
      pin kind, occurrence/multiplicity, and thesis source locator. A shared
      target remains one page with distinct source relations, and a tag remains
      distinct from a SHA even when both resolve to the same commit.
      Final `gh` uses a full SHA or verified release tag with recorded resolved
      OID; mutable refs occur only in `gh-wip`; no new callsite is added.
- [ ] Thesis-source pages carry deterministic multiplicity-qualified relations;
      exact occurrences have ordinal/line/column, file-precision aggregation
      has only semantic target plus occurrence count, and no standalone
      line-dependent thesis-link identity exists.
- [ ] Projection pages state authority/provenance and do not claim direct native
      edges or PDF page evidence.
- [ ] `graphify-input/` and `graphify-out/` are ignored and absent from the PR.
- [ ] Raw Typst/BibTeX/JSONL/TeX and bulk PDFs are outside the default graph
      corpus; projection Markdown is admitted.
- [ ] Legacy Graphify lifecycle and every live consumer are deleted.
- [ ] A fresh real upstream extraction consumed the projection and proved one
      exact literature-H1 to asset-H1 `references` edge, with both expected
      fresh projection `source_file` values, before that deletion; otherwise
      the dormant lifecycle is retained and no replacement PR is published.
- [ ] Root/hosted CI contains no Graphify install, hook, refresh, or freshness
      requirement.
- [ ] Credential-free docs CI runs `graphify-projection-self-test`
      unconditionally and impact routing covers every adapter owner path.
- [ ] Hermetic unit, live projection, Typst, scaffold, docs, package, diff, and
      required upstream-consumption checks pass.
- [ ] `make scaffold-audit scaffold-audit-self-test` and
      `make graphify-projection-self-test` pass.
- [ ] After legacy deletion and guidance/CI changes, rerun
      `make scaffold-audit scaffold-audit-self-test`,
      `make check-agent-memory`, and `make graphify-projection-self-test` on the
      exact final tree; pre-deletion results are not reused.
- [ ] Comparison/final debrief records retained, replaced, removed, deferred,
      and open capabilities with exact evidence.
- [ ] Independent review has no unresolved valid P0-P2 findings; Architect is
      `CLEAR`; hosted CI is green at the exact pushed head.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Projection becomes a second truth store | Pages contain identities, locators, status, and backlinks only; no copied claims or inferred semantics. |
| BibTeX parser grows | Extract only key, arXiv/eprint, DOI, and URL; never parse or join by title. |
| Source scanning sees inactive files, comments, or raw blocks | Traverse literal active includes only, exclude non-code lexical regions, and reconcile compiled/lexical multiplicities; fail ambiguity or coarsen only to a proven single active file. |
| Unrelated compiled links pollute multiplicity | Reconcile only the configured repository `/blob/` and exact `gh-symbol` search namespaces; ignore internal and unrelated external URLs. |
| Typst invocations compile different code refs | One CLI `--aria-code-ref` value is passed as the exact `--input aria-code-ref=<VALUE>` to every query and the independent verification compile, and recorded in provenance; no environment/config fallback. |
| File-precision links acquire unstable pseudo-lines | Store multiplicity-qualified relations on the thesis-source page; use exact ordinal/line only when proven, otherwise one aggregate count. |
| Target and relation facts drift or duplicate | Code-target pages own only repository/ref/OID/path/range and target validation; thesis-source relations exclusively own macro kind, compiled URL, pin kind, occurrence/multiplicity, and source locator. Shared-target tests prove one target with multiple relations; backlinks are derived only. |
| Mutable final link masquerades as archival | Reject mutable refs for `gh`; accept only a full SHA or an existing release tag resolved and recorded by Git. Keep mutable refs in `gh-wip`. |
| Proxy page is mistaken for native code/PDF edge | Label edge class and limitations on every page and in docs/tests. |
| PDF symlink leaks machine path | Never emit `resolve()`/realpath; validate existence but serialize the lexical repo path. |
| Optional local assets are absent in a clean checkout | Emit `missing-local` plus the existing acquisition command; do not fail or invent content. |
| Generated output stales | Embed revision/dirty state and source hashes; never claim freshness; rebuild explicitly. |
| Output swap is interrupted | Caught failures restore the in-process backup; `--check` reports debris; a later normal build discards stale temp/backup and rebuilds. No completion marker or persistent recovery state. |
| Rebase resurrects mandatory Graphify | Resolve against target-state/user selection and run forbidden-live-consumer searches. |
| CI becomes dependent on Graphify/backend | CI tests only the standard-library adapter and mocked Typst runner; no Graphify install or semantic credential. |
| Adapter expands toward graph schema | No `graphify.*` imports, graph JSON writes, merge/global calls, watcher, or hook; enforce by tests/search. |
| Deletion loses unique behavior | A real upstream extraction precedes deletion; if it cannot run or prove traversal, keep the dormant lifecycle and publish nothing. |

## Rollback

- Before merge: revert the adapter/deletion commits or close the PR; generated
  directories are disposable.
- After merge: revert the single replacement PR. The prior custom lifecycle is
  recoverable from Git history, but do not reinstall its hook automatically.
- The canonical sources are never migrated, so rollback cannot lose thesis,
  code, bibliography, manifest, TeX, or PDF identities.
- Ordinary builder failure restores/leaves the previous ignored output.
  `--check` only reports stale temp/backup debris; a later normal build discards
  that debris and rebuilds. There is no completion marker, persistent recovery
  state, or kill/power-loss guarantee. Deleting `graphify-input/` remains safe
  because it is derived.

## Staffing and execution handoff

Available agent types and recommended lanes:

| Lane | Agent type | Reasoning | Ownership |
| --- | --- | --- | --- |
| Rebase/conflict map | `git-master` | high | Preserve current-main governance and task-owned history. |
| Fixture-first contract | `test-engineer` | medium | Own projection fixtures/tests only. |
| Adapter implementation | `executor` | medium | Own builder, corpus, and minimal operator docs. |
| Legacy deletion | `code-simplifier` | high | Own exact removal only after the upstream consumption gate passes. |
| Independent review | `code-reviewer` | high | Exact-head correctness, scope, safety, maintainability. |
| Architecture gate | `architect` | xhigh | Verify source ownership and no second graph lifecycle. |
| Completion evidence | `verifier` | high | Commands, generated-state exclusion, PR/CI exact head. |

For `$ultragoal`, decompose durable goals as:

- G001 rebase and recover optional-tool governance;
- G002 lock deterministic projection contract;
- G003 implement and validate the thin adapter;
- G004 prove real upstream projection consumption;
- G005 delete legacy lifecycle and repair live consumers;
- G006 independent review, debrief, publication, and hosted-CI closure.

Run G001 before all others. G002 must complete before G003; G003's live corpus
checks precede G004; G004 must pass before G005 deletion. G006 begins only after
integration.
Parallel work is safe only for fixture design and deletion inventory; shared
Make/CI/guidance files require a single integrator.

For `$team`, use at most three implementation lanes (test contract, adapter,
deletion inventory), then one leader integrates sequentially. Do not let agents
edit the same Make/CI/guidance files concurrently.

If durable goal mode is unavailable, use `$ralph` as the single-owner fallback
with this plan and test spec, stopping only after exact-head review and hosted
CI. `$autoresearch-goal` is not appropriate because the user already made the
architecture decision; `$performance-goal` is unnecessary unless a later
measured build-time budget becomes a requirement.

## Stop rules

Stop and escalate rather than broaden the adapter if:

- upstream 0.9.31 cannot consume ordinary projection Markdown without a local
  graph-schema patch;
- deterministic identity fields cannot join the needed source record;
- fulfilling a requested link requires parsing scientific TeX/PDF content;
- a new thesis-to-code semantic link is needed but absent from an owning thesis
  source;
- current main supersedes the accepted source-order/Graphify decision;
- hosted CI would require a Graphify install, network backend, or credential.

In each case, preserve exact-source navigation, leave the legacy lifecycle
dormant until the replacement question is resolved, and report the precise
gap. Do not reintroduce the old custom machinery.

## Consensus handoff

### Architect review round 1

- Status: completed.
- Verdict: `ITERATE`.
- Disposition: this revision incorporates reference-qualified code identity,
  PDF/TeX proxy pages, conservative Typst closure and multiplicity rules, hard
  upstream proof before deletion/publication, recoverable swap semantics,
  git/Typst-only subprocesses, owner digests/scoped dirt, identity-only BibTeX
  joins, and unconditional credential-free CI.
- Approval: pending Architect re-review. Critic review has not started.

### Architect review round 2

- Status: completed.
- Verdict: `ITERATE`.
- Disposition: this revision restricts final `gh` pins to full SHAs or verified
  release tags, moves mutable refs to `gh-wip`, removes persistent output
  recovery machinery, anchors the upstream gate to exact full-identity H1
  labels and fresh file-to-file `references` evidence, and adds scaffold plus
  projection self-tests to verification.
- Approval: pending Architect re-review. Critic review has not started.

### Architect review round 3

- Status: completed.
- Verdict: `ITERATE`.
- Disposition: code identity now includes both source-ref spelling and resolved
  OID, including a tag-versus-SHA same-commit fixture. The later post-Critic P2
  check supersedes that round's ownership wording: validation is a target fact,
  while macro/URL/pin and occurrence/source-locator facts are relation-owned.
  Scaffold audit, scaffold self-test, agent-memory validation, and projection
  self-test must rerun after deletion and guidance/CI changes on the exact final
  tree.
- Approval: pending Architect re-review. Critic review has not started.

### Architect final review

- Status: completed after three `ITERATE` rounds.
- Verdict: `APPROVE`.
- Approval: complete for the architecture/test-plan boundary preceding Critic
  review.

### Critic review round 1

- Status: completed.
- Verdict: `ITERATE`.
- Disposition: this revision scopes compiled-link reconciliation to ARIA's exact
  GitHub namespaces, adds the single `--aria-code-ref` contract, and replaces
  unstable thesis-link identities with multiplicity-qualified relations on
  thesis-source pages.
- Approval: pending Critic re-review; the consensus gate remains incomplete.

### Post-Critic Architect P2 check

- Status: completed after the prior final approval.
- Verdict: `ITERATE`.
- Disposition: code-target pages must own only target facts. Macro kind,
  compiled URL, pin kind, occurrence or multiplicity, and thesis source locator
  live exclusively on thesis-source relations. Target-page backlinks may be
  derived for display but may not persist independent relation metadata. A
  shared-target/multiple-relations regression is required.
- Approval: the prior `APPROVE` is suspended pending Architect re-review; the
  consensus gate remains incomplete.

### Post-Critic Architect re-review

- Status: completed after the P2 `ITERATE` check.
- Verdict: `APPROVE`.
- Disposition: target facts and thesis-source relation facts now have exclusive
  owners, derived backlinks do not duplicate relation state, and the
  shared-target/multiple-relations regression covers the boundary.
- Approval: complete for the post-Critic P2 architecture boundary.

### Critic review round 2

- Status: completed after the post-Critic Architect approval.
- Verdict: `ITERATE`.
- Disposition: the independent `typst compile` command must receive the same
  explicit `--input aria-code-ref=FULL_SHA_OR_RELEASE_TAG` as every query and
  builder verification. Consensus chronology and metadata must preserve the
  post-Critic Architect approval before this second Critic verdict.
- Approval: pending final Critic re-review and final Architect confirmation;
  the consensus gate remains incomplete.

### Final Architect confirmation

- Status: completed after the Critic round-two revisions.
- Verdict: `APPROVE`.
- Disposition: the exact code-ref input now reaches builder verification, every
  Typst query, and the independent compile; the prior source-ownership and
  shared-target contracts remain intact.
- Approval: complete for the final architecture and verification boundary.

### Final Critic review

- Status: completed after final Architect confirmation.
- Verdict: `APPROVE`.
- Disposition: all round-one and round-two findings are represented in the
  plan and test specification with executable acceptance checks and explicit
  stop rules.
- Approval: complete; Ralplan consensus is closed.

```yaml
ralplan_consensus_gate:
  plan: .omx/plans/graphify-thin-adapter.md
  test_spec: .omx/plans/test-spec-graphify-thin-adapter.md
  context: .omx/context/graphify-thin-adapter-20260731T175054Z.md
  planner:
    status: complete
    verdict: recommended
  selected_option:
    id: B
    name: deterministic-ignored-markdown-evidence-projection
    decision: upstream-plus-one-thin-adapter
  architect:
    status: completed
    verdict: APPROVE
    iterate_rounds_completed: 3
    post_critic_checks_completed: 3
    total_reviews_completed: 7
    prior_approval: APPROVE
    final_confirmation: APPROVE
    approval: complete
    review_artifact: .omx/plans/graphify-thin-adapter.md#final-architect-confirmation
  critic:
    status: completed
    verdict: APPROVE
    rounds_completed: 3
    approval: complete
    review_artifact: .omx/plans/graphify-thin-adapter.md#final-critic-review
  history:
    - architect-1: ITERATE
    - architect-2: ITERATE
    - architect-3: ITERATE
    - architect-initial-final: APPROVE
    - critic-1: ITERATE
    - architect-post-critic-p2: ITERATE
    - architect-post-critic-re-review: APPROVE
    - critic-2: ITERATE
    - architect-final-confirmation: APPROVE
    - critic-final: APPROVE
  next_handoff:
    workflow: $ultragoal
    plan: .omx/plans/graphify-thin-adapter.md
    test_spec: .omx/plans/test-spec-graphify-thin-adapter.md
    context: .omx/context/graphify-thin-adapter-20260731T175054Z.md
  complete: true
```

Ralplan consensus is complete. The recommended next handoff is `$ultragoal`
using this plan, its test specification, and the captured context; source-code
implementation remains outside this planning artifact.
