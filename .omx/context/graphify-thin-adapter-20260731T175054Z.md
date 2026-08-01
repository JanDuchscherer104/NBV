# Graphify thin-adapter context snapshot

Captured: 2026-07-31T17:50:54Z

## Planning identity

- Repository: `/home/jd/repos/ARIA-NBV-graphify-upstream-adoption`
- Branch: `codex/graphify-upstream-adoption`
- Planning HEAD: `f764d37dbfb095ac7a9ee767574ae89071019982`
- Current `origin/main`: `8d1043f6ee615a1cadbc2c41cce4b0b424648c5d`
- Divergence: branch is two commits ahead and four commits behind `origin/main`.
- Human decision: option 3, retain upstream Graphify plus one proven thin
  adapter.
- Lane: Ralplan consensus planning complete; the recommended execution handoff
  is `$ultragoal` using the plan and test specification. This context artifact
  itself does not implement product or scaffold changes.

## Authoritative constraints

The accepted target state in
`.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md` requires:

- one owner for each durable meaning;
- exact-source fallback without Graphify;
- upstream-first use and a local adapter only for a measured gap;
- untracked, qualified, non-authoritative generated views;
- no mandatory Graphify hook, freshness gate, CI dependency, or ordinary-task
  dependency;
- no custom Graphify replacement, graph-schema owner, scientific TeX/PDF
  parser, or hidden thesis/package semantic change;
- one reviewable concern, evidence bundle, and rollback boundary per PR.

The source owners relevant to this plan are:

| Meaning | Owner |
| --- | --- |
| Active thesis prose and active citations | `docs/typst/thesis/main.typ` and included sections |
| Thesis code-link convention | `docs/typst/shared/style.typ` (`gh`, `gh-wip`, `gh-symbol`) |
| Implementation contracts | Python code and docstrings under `aria_nbv/aria_nbv/` |
| Citation records | `docs/references.bib` and `docs/references-qh.bib` |
| Local literature catalogue | `docs/literature/sources.jsonl` |
| Local paper sources | `docs/literature/tex-src/` and `docs/literature/pdf/` |
| Tool authority and conflict resolution | `.agents/references/source_order.md` |
| Human selection of Graphify role | `.agents/references/human_owner_intent.md` |

## Current evidence

- Commit `80eab1ee` removed mandatory Graphify routing, hosted-CI execution,
  and normal hook installation while retaining the old integration as a dormant
  comparison candidate.
- Commit `f764d37d` added
  `.agents/memory/history/2026/07/2026-07-31_graphify_upstream_adoption.md`.
- The comparison measured about 2,738 tracked LOC in the ARIA-owned Graphify
  lifecycle. Exact-source navigation and unmodified upstream Graphify own zero
  Graphify implementation LOC in this repository.
- Upstream Graphify 0.9.31 natively supports code plus Markdown-family,
  HTML/text/RST/YAML, and PDF inputs. It does not natively support Typst, TeX,
  BibTeX, or JSONL as semantic source types.
- Upstream documents no stable extractor-plugin or graph-fragment import API.
  The repository must not write `graph.json`, import `graphify.*`, use
  `merge-graphs`/global graph state, or own Graphify's schema/lifecycle.
- Upstream Markdown reference extraction creates deterministic graph edges only
  between Markdown-like documents. Links to `.py`, `.typ`, `.bib`, `.tex`, or
  `.pdf` remain human navigation, not promised native Graphify edges.
- Upstream PDF extraction preserves file identity but not scientific page/range
  provenance. A PDF node cannot verify a claim.
- The active thesis currently contains many citation keys but no active
  `gh`/`gh-wip`/`gh-symbol` callsites. The adapter must preserve future real
  callsites and must not fabricate thesis-to-code links.
- `typst query` can return compiled citation, link, and heading elements, but
  does not expose a reliable source-line locator. Compiler validation therefore
  needs a conservative active include closure and narrow lexical candidate
  reconciliation. Only literal repository-local includes are supported;
  dynamic includes are a hard unsupported-input error. When compiled
  multiplicity cannot be reconciled unambiguously with lexical candidates, the
  projection must stop or coarsen the thesis locator to the smallest proven
  active source file rather than invent a line.
- Compiled-link reconciliation is namespace-scoped. Only URLs under the exact
  configured repository GitHub `/blob/` namespace and the exact configured
  repository `gh-symbol` search namespace are adapter candidates. Internal
  Typst links, bibliography links, and unrelated external URLs remain outside
  the adapter and do not participate in multiplicity checks.
- `docs/literature/sources.jsonl` contains 45 records; 35 declare `tex_dir` and
  35 declare `pdf_file`. This worktree contains 399 local TeX-tree files, 370
  of them `.tex`; the repository-relative PDF path currently resolves through a
  worktree symlink to 37 files. Generated evidence must never record the
  machine-resolved symlink target.
- `docs/references.bib` has 96 keys and `docs/references-qh.bib` has three; there
  are currently no duplicate keys.
- `scripts/scaffold_audit.py` has a reusable key-only BibTeX loader, but it
  defaults to `docs/references.bib` and cannot supply fields needed for exact
  manifest joins.
- `.graphifyignore` currently admits unsupported Typst/JSONL/BibTeX paths and
  excludes local PDF/TeX assets. The target corpus should admit native code,
  native Markdown-family docs, and the generated Markdown projection. Raw TeX,
  BibTeX, JSONL, and the full PDF corpus stay outside the default root graph.
- A code target is not just a path. Its derived identity is
  `repository@source-ref[resolved-oid]:path:line-range`. A code-target page owns
  only target facts: repository, source-ref spelling, resolved OID, path, line
  range, and target validation status where applicable. Source-ref spelling and
  resolved OID both participate, so a release tag and literal SHA resolving to
  the same commit remain distinct identities. Macro kind, compiled URL, pin
  kind, occurrence or multiplicity, and thesis source locator belong only to
  the thesis-source relation. A target page may render backlinks derived from
  those relations, but must not persist an independent copy of relation
  metadata. Final `gh` links accept only a literal full commit SHA or an
  existing repository release tag that resolves to a recorded commit OID;
  mutable refs such as `main` are allowed only for `gh-wip`.
- The builder has one explicit `--aria-code-ref REF` input, defaulting to
  `main` only to match Typst's development default. It passes that exact input
  to every `typst query` invocation; the independent thesis compile used for
  verification must receive the same explicit input. Provenance records value,
  source (`cli` or `default`), pin kind, and resolved OID. A final `gh` without
  an explicit per-call ref inherits this input; inherited full SHA and verified
  release tag pass, while inherited default `main` fails.
- PDF and TeX roots require generated Markdown proxy pages so upstream
  Markdown edges can traverse `literature -> asset proxy`; each proxy then
  links to the raw owner path for humans. PDF-page, TeX-file/section, and
  content nodes remain explicitly deferred.

## Current-main rebase hazard

`origin/main` includes merged PR #41 and reintroduces mandatory Graphify
guidance/CI relative to this branch while also carrying the accepted direct
skill/Aria-Grill governance. Execution must start with a rebase. Conflict
resolution must retain current-main governance and Aria-Grill changes while
reapplying the already accepted optional-Graphify boundary and the selected
thin-adapter path. Do not resurrect the old vendored skill, mandatory hosted
Graphify install, post-commit refresh, freshness checker, or default Graphify
routing.

## Target adapter boundary

The repository owns one small, standard-library projection builder. It reads
the canonical sources above, validates their explicit relationships, and emits
ordinary Markdown pages under ignored `graphify-input/`. Upstream Graphify may
then consume those pages without an ARIA graph-schema integration.

The projection represents identities and source-owned links; it does not copy
scientific claims or infer new relationships. Direct backlinks to code, Typst,
BibTeX, TeX, JSONL, and PDF remain human-resolvable provenance. Markdown links
among projection pages are the only cross-modal edges the adapter promises
upstream Graphify can observe.

There is no standalone line-dependent thesis-link node. A thesis-source page
owns multiplicity-qualified relations to semantic targets. When lexical
occurrences are uniquely proven, each relation records deterministic ordinal,
total multiplicity, and exact line/column. When only file precision is proven,
one aggregated relation records source file, semantic target, and occurrence
count without ordinal or guessed line. This avoids unstable identities while
preserving duplicate occurrences.

The builder may invoke exactly `git` and `typst` through one injectable command
runner. It records SHA-256 for every owner input used and computes dirty status
only for those inputs, not the whole worktree. Output publication uses a
validated sibling temporary tree and an in-process backup swap; caught failures
restore the backup. A later normal build discards stale temp/backup debris and
rebuilds, while `--check` only reports debris. There is no persistent recovery
state or crash/power-loss guarantee.

## Planning assumptions

- The tracked adapter and its tests are justified by the measured unsupported
  Typst/BibTeX/JSONL seam; generated projection pages remain ignored.
- No new Python dependency is required. The live builder may invoke the
  repository's existing Typst CLI for compiled-query validation.
- Malformed owners, dynamic Typst includes, compiled/lexical multiplicity
  ambiguity, unresolved active citation keys, escaping asset paths, or
  ambiguous deterministic joins are errors. Missing optional local assets,
  unmatched but valid bibliography/manifest records, and dynamic symbol-search
  links are explicit status records, never guesses.
- BibTeX-to-manifest joins use only key metadata needed for arXiv/eprint, DOI,
  or URL identities. Normalized-title joining is intentionally absent.
- Native ingestion of all 37 PDFs or 399 TeX-tree files is not part of the root
  corpus. A bounded direct upstream PDF extraction remains an operator action.
- The adapter is not proven until a real upstream Graphify extraction consumes
  its Markdown pages and demonstrates the expected proxy traversal. This is a
  hard pre-deletion/publication gate. If no authorized backend or backend-free
  Markdown extraction mode is available, the dormant legacy lifecycle remains
  and no replacement PR is published.
- Every generated page exposes its full projection identity as its H1. The hard
  smoke proves a fresh literature-H1 to asset-H1 reference using public
  `graphify path` when sufficient, otherwise read-only inspection of the public
  graph JSON for a `references` edge whose two `source_file` values are both
  inside the fresh projection. Public output may be read as test evidence but
  is never modified.

## Open planning questions

None. The human selected the only material architecture branch. The first
Architect gave final `APPROVE` after three `ITERATE` rounds. Critic round one
completed with `ITERATE`, and the post-Critic Architect P2 check also returned
`ITERATE`, temporarily suspending the prior approval. The post-Critic Architect
re-review then returned `APPROVE`. Critic round two subsequently returned
`ITERATE`, requiring the independent Typst compile to receive the same explicit
`aria-code-ref` input and requiring chronological consensus metadata. Final
Architect confirmation then returned `APPROVE`, followed chronologically by
final Critic `APPROVE`. The selected option remains deterministic ignored
Markdown evidence projection (upstream plus one thin adapter). Ralplan
consensus is complete; the recommended next handoff is `$ultragoal` with:

- `.omx/plans/graphify-thin-adapter.md`;
- `.omx/plans/test-spec-graphify-thin-adapter.md`;
- `.omx/context/graphify-thin-adapter-20260731T175054Z.md`.
