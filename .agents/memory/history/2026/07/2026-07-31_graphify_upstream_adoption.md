---
id: 2026-07-31_graphify_upstream_adoption
date: 2026-07-31
title: "Graphify Upstream Adoption"
status: blocked
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
  - scripts/build_graphify_projection.py
  - scripts/tests/test_build_graphify_projection.py
artifacts:
  - "commit:9d085d99"
  - "commit:f1b31443"
  - "commit:3ea8b57d"
  - "commit:63323508"
  - "commit:aee82c30"
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

The builder consumes the active Typst thesis closure, both bibliography
owners, `docs/literature/sources.jsonl`, explicit thesis code-link macros, and
declared local PDF/TeX identities. It emits ignored Markdown proxy pages only;
it does not parse scientific PDF/TeX content, write Graphify's graph schema, or
make Graphify a repository or CI prerequisite.

## Findings

- All 21 hermetic projection tests passed.
- Live `--check` validation and two builds produced byte-identical ignored
  projections containing 288 Markdown pages at the exact branch head.
- An independent Typst compile and the configured `cite`, `link`, and `heading`
  queries passed, so the projection was checked against compiled thesis
  evidence rather than lexical scanning alone.
- The required upstream-consumption proof is blocked. Graphify 0.9.31's public
  `extract` command detected 237 code files and 364 semantic files, but rejects
  document extraction without a working semantic backend. The installed
  `claude-cli` backend returned an expired-OAuth `401`; all five semantic chunks
  failed, so no projection nodes or expected reference edge were produced.
- `graphify update` is code-only and therefore cannot provide the missing
  Markdown-consumption proof.

## Dispositions

- **Retained:** exact source owners, source verification, optional upstream
  Graphify, ignored generated projection state, and the dormant legacy
  lifecycle until the upstream proof succeeds.
- **Replaced:** the former unresolved three-option decision gate with the
  explicit option-3 target and its implemented deterministic Markdown
  projection boundary.
- **Removed:** mandatory Graphify routing, normal hook installation, and
  required root/hosted-CI Graphify execution from the earlier decoupling
  change at `9d085d99`. No legacy Graphify implementation was deleted in this
  blocked phase.
- **Deferred:** deletion of the vendored skill and custom lifecycle, repair of
  their remaining Make/CI/hook/guidance consumers, independent final review,
  publication, PR creation, and hosted-CI monitoring.
- **Open:** obtain an authorized working semantic backend or a genuine
  backend-free upstream path, rerun the real 0.9.31 projection-edge proof, and
  resume G006 only if that hard gate passes. G005 remains pending behind G006.

## Verification

The completed implementation evidence comprises 21 passing tests, Ruff-clean
changed Python, two byte-identical 288-page live builds, live `--check`, and an
independent Typst compile plus `cite`/`link`/`heading` queries. The failed
Graphify probe is preserved in the Ultragoal ledger as G006 evidence. Per the
approved stop rule, the failure caused no legacy deletion, push, PR, or hosted
CI attempt.

## Canonical-State Impact

No additional canonical-state file is required. The committed guidance and
human-owner-intent changes own the optional-tool and option-3 projection
boundary. This record remains `blocked` until upstream document consumption is
proved and the retained/deferred work is either completed or explicitly
replanned.
