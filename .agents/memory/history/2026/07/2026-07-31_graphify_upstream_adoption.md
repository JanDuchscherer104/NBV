---
id: 2026-07-31_graphify_upstream_adoption
date: 2026-07-31
title: "Graphify Upstream Adoption"
status: in-progress
topics: [graphify, scaffold, tooling, projection]
confidence: high
canonical_updates_needed: []
files_touched:
  - AGENTS.md
  - docs/AGENTS.md
  - docs/literature/README.md
  - .agents/references/human_owner_intent.md
  - .gitignore
  - .graphifyignore
  - .github/workflows/ci.yml
  - Makefile
  - scripts/build_graphify_projection.py
  - scripts/ci_impact.py
  - scripts/tests/test_build_graphify_projection.py
  - scripts/tests/test_ci_impact.py
  - scripts/validate_agent_memory.py
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
  - ".omx/plans/graphify-thin-adapter.md"
  - ".omx/plans/test-spec-graphify-thin-adapter.md"
---

## Task

Adopt the owner's selected option 3: retain user-installed upstream Graphify
and add one deterministic, ignored Markdown projection for source-owned links
that upstream Graphify does not natively extract. Exact code, Typst, BibTeX,
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

## Findings

- All 33 hermetic adapter unit tests passed. The broader focused pytest slice,
  including scaffold contracts, passed all 37 tests.
- Live `--check` validation and two builds produced byte-identical ignored
  projections containing 288 Markdown pages at the exact branch head.
- An independent Typst compile and the configured `cite`, `link`, and `heading`
  queries passed, so the projection was checked against compiled thesis
  evidence rather than lexical scanning alone.
- The independent pre-gate code review has no unresolved P0--P2 findings after
  the eight accepted repairs.
- Ruff formatting, default lint, and the strict complexity selection passed;
  mypy passed for the adapter and its tests. The focused scaffold checks and
  agent-memory validation also passed.
- The first upstream-consumption attempt did not prove the edge. Graphify
  0.9.31's public `extract` command detected 237 code files and 364 semantic
  files, while the attempted `claude-cli` backend returned an expired-OAuth
  `401`; all five semantic chunks failed, so no projection nodes or expected
  reference edge were produced.
- The approved continuation uses the unmodified user-installed upstream
  `$graphify` skill in a `codex login` authenticated session. Its authenticated
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

## Dispositions

- **Retained:** exact source owners, source verification, optional upstream
  Graphify, and ignored generated projection state.
- **Replaced:** the former unresolved three-option decision gate with the
  explicit option-3 target and its implemented deterministic Markdown
  projection boundary.
- **Removed:** mandatory Graphify routing and execution, the vendored skill,
  refresh/freshness/integration scripts, post-commit hook, version pin, custom
  tests, Graphify-specific Make/CI family, and their validation exceptions and
  guidance consumers. Commit `121dd235` owns the final lifecycle deletion and
  consumer repair.
- **Deferred:** none inside the repository implementation.
- **Open:** publish the committed branch, create the PR, monitor exact-head
  hosted CI, and change this debrief to `complete`. The upstream proof,
  lifecycle deletion, consumer repair, local verification, and final review
  repair are complete.

## Verification

The completed implementation evidence comprises 33 passing adapter unit tests,
37 passing focused pytest cases including scaffold coverage, Ruff format and
default lint, the clean `C901`/`PLR0911`/`PLR0912`/`PLR0913`/`PLR0915` strict
complexity selection, mypy over the adapter and its tests, live `--check` over
288 generated Markdown pages, two byte-identical live builds, an independent
Typst compile plus `cite`/`link`/`heading` queries, focused scaffold checks, and
`make check-agent-memory`. The pre-gate review has no unresolved P0--P2
findings. The failed Graphify probe is preserved in the Ultragoal ledger as
G006 evidence: the earlier installed Claude backend returned expired-OAuth
`401`.

The replacement proof then passed with Graphify 0.9.31 at source HEAD
`3016d6c629a732dac30769039f734ff5496ad3f2`, using the disposable root
`/tmp/aria-graphify-codex-proof.EjW8rf`. Authenticated Codex-host subagent
semantic JSON fed a fresh 60-node/117-edge graph containing 51 native Python
nodes from `aria_nbv/aria_nbv/lightning/qh_module.py`. Public `graphify path`
showed the exact one-hop `EXTRACTED` `references` relation between
`literature:arxiv:1509.06461` (literature L8) and
`pdf:docs/literature/pdf/Double-DQN.pdf`, backed by the expected repo-relative
projection source files
`graphify-input/literature/literature-arxiv-1509-06461-346065ae69ea.md` and
`graphify-input/assets/pdf-docs-literature-pdf-double-dqn-pdf-fd61d0aa14bb.md`.
No token was exported, no provider API key or repository secret participated,
and no Graphify fork, repository-owned Graphify package import, or graph patch
was used. This satisfies
the hard upstream-consumption gate but does not claim legacy deletion,
publication, PR creation, or hosted CI complete.

## Canonical-State Impact

No additional canonical-state file is required. The committed guidance and
human-owner-intent changes own the optional-tool and option-3 projection
boundary. This record remains `in-progress` until upstream document consumption
proof is followed by the authorized deletion, final review, publication, and
hosted-CI completion work.
