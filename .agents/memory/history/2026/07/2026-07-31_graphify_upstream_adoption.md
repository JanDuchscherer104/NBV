---
id: 2026-07-31_graphify_upstream_adoption
date: 2026-07-31
title: "Graphify Upstream Adoption"
status: complete
topics: [graphify, scaffold, tooling, projection]
confidence: high
canonical_updates_needed: []
files_touched:
  - AGENTS.md
  - docs/AGENTS.md
  - docs/literature/README.md
  - .agents/references/source_order.md
  - .agents/references/human_owner_intent.md
  - .omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md
  - .omx/plans/graphify-thin-adapter.md
  - .omx/plans/test-spec-graphify-thin-adapter.md
  - .gitignore
  - .graphifyignore
  - .github/workflows/ci.yml
  - Makefile
  - scripts/build_graphify_projection.py
  - scripts/ci_impact.py
  - scripts/tests/test_build_graphify_projection.py
  - scripts/tests/test_ci_impact.py
  - scripts/validate_agent_memory.py
  - .agents/skills/graphify/
  - .codex/skills/graphify/
  - scripts/graphify_refresh.py
  - scripts/check_graphify_freshness.py
  - scripts/check_graphify_integration.py
  - scripts/git_hooks/post-commit
artifacts:
  - "commit:9d085d99"
  - "commit:f1b31443"
  - "commit:3ea8b57d"
  - "commit:63323508"
  - "commit:aee82c30"
  - "commit:121dd235"
  - "commit:8f3202c8"
  - "pull-request:https://github.com/JanDuchscherer104/ARIA-NBV/pull/45"
  - ".omx/plans/graphify-thin-adapter.md"
  - ".omx/plans/test-spec-graphify-thin-adapter.md"
---

## Task

Adopt the owner's selected option 3: retain the user-installed upstream
Graphify tool, install its project skill under `.agents/skills/graphify/`, and
add one deterministic ignored Markdown projection for source-owned links that
upstream Graphify does not natively extract. Exact code, Typst, BibTeX,
`sources.jsonl`, PDF, and TeX sources remain authoritative. The approved stop
rule requires a real upstream projection-edge proof before the dormant legacy
lifecycle may be deleted or a replacement PR may be published.

## Method

The branch was rebased onto `origin/main` at `8d1043f6`; the rewritten
predecessor commits are `9d085d99` for the optional-tool boundary (formerly
`80eab1ee`) and `f1b31443` for the comparison record. Commit `3ea8b57d` records
the approved plan and test specification, `63323508` locks the projection
contract with fixture-first tests, and `aee82c30` implements the standard-library
projection builder plus its narrow corpus and owner guidance.

The subsequent pre-gate review repaired all eight accepted findings before the
external upstream-consumption gate: citation ownership is source-local while
compiled multiplicity remains global; `gh-symbol` reconciliation accepts only
the exact repository/language/symbol search URL; Typst verification uses a
unique external scratch directory; output installation rejects symlinked
ancestors and physical escapes; unresolved `main` no longer falls back to
`HEAD`; the stale `memory-mine` phony target was removed; the index records the
configured code ref's pin kind, resolved OID, entity count, and per-family
counts; and the fixture matrix plus mypy coverage was expanded. The renderer,
Typst-closure reader, and narrow BibTeX reader were also split into factual
helpers so the strict complexity selection passes without adding a framework.

The builder consumes the active Typst thesis closure, both bibliography
owners, `docs/literature/sources.jsonl`, explicit thesis code-link macros, and
declared local PDF/TeX identities. It emits ignored Markdown proxy pages only;
it does not parse scientific PDF/TeX content, write Graphify's graph schema, or
make Graphify a repository or CI prerequisite.

The retained capability is deliberately file-level. The compiled `heading`
query validates that the active thesis closure compiles, but heading results are
not projected into section/subsection nodes. Thesis citations and code targets
therefore remain attached to their owning source file. Code-target pages record
exact path, ref, and line provenance for human resolution; no native Graphify
edge to the corresponding Python file or symbol is promised.

## Findings

- All 33 hermetic adapter unit tests passed. The broader focused pytest slice,
  including scaffold contracts, passed all 37 tests.
- Live `--check` validation and two builds produced byte-identical ignored
  projections containing 288 Markdown pages at the exact branch head.
- An independent Typst compile and the configured `cite`, `link`, and `heading`
  queries passed, so the projection was checked against compiled thesis
  evidence rather than lexical scanning alone. This is compilation/closure
  evidence, not section-granular retrieval evidence.
- The independent pre-gate code review had no unresolved P0--P2 findings after
  the eight accepted repairs. The later PR review found additional governance,
  routing-corpus, live-CI, and stale-graph read-side gaps; the 2026-08-01
  remediation updated the accepted decision owner, bounded corpus, live owner
  check, and read-side fallback contract.
- Ruff formatting, default lint, and the strict complexity selection passed;
  mypy passed for the adapter and its tests. The focused scaffold checks and
  agent-memory validation also passed.
- The first upstream-consumption attempt did not prove the edge. Graphify
  0.9.31's public `extract` command detected 237 code files and 364 semantic
  files, while the attempted `claude-cli` backend returned an expired-OAuth
  `401`; all five semantic chunks failed, so no projection nodes or expected
  reference edge were produced.
- The approved continuation initially used the user-installed upstream
  `$graphify` skill in a `codex login` authenticated session. The final
  remediation installs the upstream 0.9.31 skill under
  `.agents/skills/graphify/`, adds only the ARIA-NBV preflight and routing
  metadata, and reduces root `AGENTS.md` to a pointer. Its authenticated
  Codex subagents may produce semantic JSON before the normal upstream build.
  No ChatGPT/Codex token export, `OPENAI_API_KEY` reuse, repository secret,
  Graphify fork, repository-owned Graphify package import, or repository-owned
  lifecycle is permitted.
- The hard upstream-consumption gate passed at source HEAD
  `3016d6c629a732dac30769039f734ff5496ad3f2` with Graphify 0.9.31 and
  disposable output `/tmp/aria-graphify-codex-proof.EjW8rf`. An authenticated
  Codex host subagent produced the semantic JSON; no provider API-key
  environment variable participated.
- The fresh graph contains 60 nodes and 117 edges, including 51 native Python
  nodes from `aria_nbv/aria_nbv/lightning/qh_module.py`. Public `graphify path`
  reported a one-hop `EXTRACTED` `references` edge from
  `literature:arxiv:1509.06461` to
  `pdf:docs/literature/pdf/Double-DQN.pdf`, with literature locator L8 and the
  expected source files
  `graphify-input/literature/literature-arxiv-1509-06461-346065ae69ea.md` and
  `graphify-input/assets/pdf-docs-literature-pdf-double-dqn-pdf-fd61d0aa14bb.md`.
  The proof used no token export, API key, repository secret, Graphify fork,
  repository-owned Graphify package import, or graph patch.

## 2026-08-01 Review Remediation

The exact-head PR review identified deterministic-projection defects,
provenance and identity gaps, retrieval limitations, and governance or
verification gaps. The remediation preserves the thin-adapter boundary:

- successful builds remove stale swap debris without serializing it; read-only
  checks still report and preserve debris;
- both argparse spellings of `--aria-code-ref` record CLI provenance;
- metadata-only literature identities use an explicit constrained stable ID or
  a canonical-content SHA-256, while JSONL line numbers remain locators only;
- literature pages project only the reviewed source-owned catalogue allowlist;
- local asset status is explicitly environment-scoped and summarized by a
  deterministic inventory digest;
- compiled headings are catalogued without inventing section nodes or source
  attribution, and code proxies gain exact human owner links without claiming
  native Python graph edges;
- the accepted target-state specification owns the option-3 supersession, while
  the root corpus admits bounded dispatcher and skill entrypoints and keeps
  package tests on exact-source search;
- hosted docs CI runs both the hermetic suite and the live owner projection
  check; read-side freshness requires commit agreement plus the upstream
  stat-index SHA-256 of the current projection index, so same-commit stale graphs
  fail closed.

The original plan and test specification are marked implemented and carry a
post-implementation amendment rather than remaining active instructions that
contradict the remediated contracts. The final focused suite contains 41
projection tests and 11 CI-impact tests. Independent exact-diff re-review
returned `CLEAR` with no remaining P0--P2 findings.

## Dispositions

- **Retained:** exact source owners, source verification, optional upstream
  Graphify, the project-installed `.agents/skills/graphify/` usage surface, and
  ignored generated projection state.
- **Replaced:** the former unresolved three-option decision gate with the
  explicit option-3 target and its implemented deterministic Markdown
  projection boundary.
- **Removed:** mandatory Graphify execution, the retired `.codex` skill and
  hook, refresh/freshness/integration scripts, custom lifecycle tests,
  Graphify-specific Make/CI family, and their validation exceptions and
  guidance consumers. Commit `121dd235` owns the legacy lifecycle deletion and
  consumer repair; the replacement `.agents` skill is an upstream workflow
  surface, not a lifecycle.
- **Deferred:** section/subsection projection, native proxy-to-Python graph
  edges, and package-test indexing. Each requires measured value or an upstream
  capability rather than expansion of this thin adapter.
- **Open:** publication remains pending at record authoring. The exact pushed
  head and hosted CI outcome must be evidenced on PR #45. The file-level proxy
  boundary is an accepted limitation, not evidence of section-level or
  native-code traversal.

## Verification

The completed implementation evidence comprises 33 passing adapter unit tests,
37 passing focused pytest cases including scaffold coverage, Ruff format and
default lint, the clean `C901`/`PLR0911`/`PLR0912`/`PLR0913`/`PLR0915` strict
complexity selection, mypy over the adapter and its tests, live `--check` over
288 generated Markdown pages, two byte-identical live builds, an independent
Typst compile plus `cite`/`link`/`heading` queries, focused scaffold checks, and
`make check-agent-memory`. The pre-gate review was clear at that earlier head;
the later PR review and its follow-up verification supersede that closure claim.
The failed Graphify probe is preserved in the Ultragoal ledger as
G006 evidence: the earlier installed Claude backend returned expired-OAuth
`401`.

The replacement proof then passed with Graphify 0.9.31 at source HEAD
`3016d6c629a732dac30769039f734ff5496ad3f2`, using the disposable root
`/tmp/aria-graphify-codex-proof.EjW8rf`. Authenticated Codex-host subagent
semantic JSON fed the upstream skill's normal Graphify build, alongside native
AST extraction of `aria_nbv/aria_nbv/lightning/qh_module.py`. The resulting
fresh graph contained 60 nodes and 117 edges, including 51 native Python nodes.
The user-scoped upstream skill digest was
`9024289348cceb6140af33e9875742dc55f55e5d574e44e5a21bb36239b1bcf4`;
its extraction-spec digest was
`32d7decad42d58129c6694ea4e4ce1f72a531bc5161827d2095787e9448735e9`.
The exact public read-side proof command was:

```bash
graphify path 'literature:arxiv:1509.06461' \
  'pdf:docs/literature/pdf/Double-DQN.pdf' \
  --graph /tmp/aria-graphify-codex-proof.EjW8rf/graphify-out/graph.json
```

It showed the exact one-hop `EXTRACTED` `references` relation between
`literature:arxiv:1509.06461` (literature L8) and
`pdf:docs/literature/pdf/Double-DQN.pdf`, backed by the expected repo-relative
projection source files
`graphify-input/literature/literature-arxiv-1509-06461-346065ae69ea.md` and
`graphify-input/assets/pdf-docs-literature-pdf-double-dqn-pdf-fd61d0aa14bb.md`.
No token was exported, no provider API key or repository secret participated,
and no Graphify fork, repository-owned Graphify package import, or graph patch
was used. This satisfies the hard upstream-consumption gate. Commit `121dd235`
then completed the authorized lifecycle deletion and consumer repair. Local
verification is complete; publication, PR creation, and hosted CI remain open.

The project-skill follow-up ran
`graphify install --project --platform agents` with upstream Graphify 0.9.31.
The installed `.agents/skills/graphify/` bundle contains the progressive
references shipped by upstream plus the compact ARIA-NBV preflight and required
repository routing metadata. The follow-up passed 41 projection tests, 11
CI-impact tests, the 288-page live-owner check, scaffold audit with 21 skills
and zero errors, scaffold self-tests, agent-memory validation, `git diff
--check`, and `docs-render-core`. The first docs attempt hit the shared `/tmp`
quota; the identical gate passed with a task-specific `TMPDIR` on the main
filesystem.

## Canonical-State Impact

The accepted target-state specification now explicitly owns the option-3
supersession and bounded corpus; `source_order.md` points to that decision, while
human-owner intent remains the cross-task preference summary. The project skill
now owns agent-facing Graphify usage and the ARIA preflight; root `AGENTS.md`
contains only its dispatcher pointer. Upstream consumption proof, authorized
legacy deletion, and consumer repair remain complete.
The earlier independent review returned `APPROVE`, Architect verification
returned `CLEAR`, and PR #45 Root Verification passed at publication head
`6c0eafa99242398404effe85bac639798ad12834` in 10m24s. Those results do not close
the later review: the remediation requires fresh exact-head local verification,
hosted CI, and reviewer thread resolution before merge.

## 2026-08-01 Final PR #45 Remediation Record

At local head `8f6123e2f8ca62fca3e1e42bbd33d57752abf641`, commits `9597c8ee`
and `8f6123e2` complete the final local remediation. The Graphify skill now
uses the native Codex `executor` through `spawn_agent`/`wait_agent`, with a
UUID-scoped run directory and an exact expected-chunk manifest. Interrupted,
zero-input, and all-cache runs are isolated; missing or invalid expected chunks
fail closed and cannot make a graph current.

The repository-owned freshness CLI records the `invalid`, `missing`,
`semantic-stale`, `structural-stale`, and `fresh` states. It checks the
repository root, exact head, projection/index membership, and upstream's salted
stat-index hash semantics. The upstream Git hook remains optional local
invalidation/acceleration only; `hook status` reported no `post-commit` hook,
an installed `post-checkout` hook, and no merge driver, none of which authorizes
freshness.

The one-time shared-cache migration found 350 live entries: 126 unique payload
groups, 112 byte-identical duplicate groups, 224 redundant entries, and zero
conflicts. Replaced local directories were retained under the suffix
`semantic.pre-shared-20260801T124302Z`. Two-worktree validation recorded 386
cross-worktree cache hits and zero misses; graph, projection, manifest,
stat-index, and run state remain worktree-local.

The authenticated local Graphify `0.9.31` run at `8f6123e2` used semantic run
`c2c0daeb-3c79-4824-8d82-61e82bee1366`, produced fresh JSON, and yielded 6,222
nodes, 14,268 edges, and 519 communities. The live query traversal reached 85
BFS nodes before output truncation; the verified path was
`aria_nbv/__init__.py --imports [EXTRACTED]--> AseEfmDataset`. The read-only
multigraph diagnostic reported 1,288 dangling endpoint edges, one self-loop,
and 1,574 undirected same-endpoint collapses. These are non-blocking upstream
health diagnostics, not freshness or publication gates.

Local `make ci` passed: the QH/package contract suite had 266 passing tests
(159 warnings, 50.42s), package smoke had 112 passing tests (142 warnings,
16.31s), the projection suite had 41 passing tests, CI-impact and freshness
suites had 11 passing tests each, and the setup shell plus docs/Quarto and Typst
core render gates passed. The warnings and upstream diagnostics were
non-blocking. `make check-agent-memory` and `git diff --check` are the final
record checks. No commit or push is implied by this record: publication remains
pending and must be evidenced on PR #45.
