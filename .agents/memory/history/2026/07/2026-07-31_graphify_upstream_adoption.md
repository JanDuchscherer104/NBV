---
id: 2026-07-31_graphify_upstream_adoption
date: 2026-07-31
title: "Graphify Upstream Adoption Comparison"
status: in-progress
topics: [graphify, scaffold, tooling, comparison]
confidence: high
canonical_updates_needed: []
files_touched:
  - AGENTS.md
  - Makefile
  - .github/workflows/ci.yml
  - scripts/tests/test_ci_impact.py
  - scripts/tests/test_graphify_integration.py
artifacts:
  - "commit:80eab1ee"
---

## Task

Evaluate whether ARIA-NBV should delete Graphify, retain unmodified upstream
Graphify as an optional user tool, or justify one thin adapter. First remove
Graphify from mandatory agent, hook, and CI paths without destroying the
existing comparison candidate; then compare exact-source navigation, the
dormant pinned integration, and current upstream behavior.

## Method

Commit `80eab1ee` made Graphify optional and preserved the existing custom
lifecycle solely as a dormant comparison candidate. The fixed comparison used
the same target commit, source-grounded expected answers, isolated generated
outputs, and separate measurements for correctness, owner/path utility,
provenance handling, runtime, output/context size, generated size, and
ARIA-owned LOC. It did not compute a composite score.

The user tool was upgraded from Graphify 0.9.26 to unmodified upstream 0.9.31,
and the upstream Codex skill was installed at user scope under
`~/.codex/skills/graphify/`. No project installer, hook, semantic-backend
credential, repository dependency, vendor, adapter, or repair was introduced.
The dormant 0.9.20 candidate ran through an isolated `uvx` shim.

## Measured Findings

- Exact-source search found and verified every required owner, including when
  Graphify was absent from `PATH`. Its targeted searches completed below the
  timer's 0.01-second resolution and generated no persistent output.
- Both code-only graphs located `QhBatch`, its hierarchy, and useful import
  paths. Neither natural-language owner nor broad architecture query found the
  relevant Q_H owners without exact-symbol narrowing. The returned import path
  also did not express the real dataset-to-chain-to-collator-to-training flow.
- Dormant 0.9.20 extracted 5,645 nodes and 15,646 edges in 7.16 seconds; its
  graph was 7,838,484 bytes and total generated output 19,580,733 bytes.
  Upstream 0.9.31 extracted 5,682 nodes and 15,697 edges in 7.09 seconds; its
  graph was 7,864,512 bytes and total generated output 18,183,670 bytes.
- Typical path/explain calls took 0.44--0.54 seconds. Broad-query stdout was
  3,062 bytes for the dormant candidate and 4,111 bytes upstream, yet both were
  dead ends. Upstream added useful repository-relative line evidence to edges.
- The dormant refresh completed in 9.93 seconds and its freshness check passed.
  Its integration checker then misread a user-skill/package mismatch warning
  as version 0.9.31 instead of the isolated package's 0.9.20. This was retained
  as evidence and not repaired.
- Graph JSON does not embed a source commit. A graph built from `origin/main`
  answered current-looking queries normally and required an external HEAD
  comparison to reject it. Wrong-root output likewise required checking
  `.graphify_root` or resolving returned sources. Inferred type-use edges still
  required source qualification.
- Keyless full-corpus detection found 248 code files, 53 documents, 8 papers,
  and 8 images, then stopped because semantic extraction requires a supported
  backend. Typst, TeX, and general BibTeX were not natively represented.
- The upstream PDF-enabled probe detected three readable literature PDFs and
  preserved repository-relative file identity plus word counts, but produced
  no claim-local page/range nodes without the semantic backend. PDF identity is
  therefore partial rather than sufficient scientific provenance.
- The frozen ARIA-owned custom lifecycle is 2,738 tracked LOC. Exact-source
  navigation and unmodified upstream Graphify own zero Graphify implementation
  LOC in this repository.

## Source Corrections

The comparison corrected its initial expectations before judging candidates:

- fitted-Q admission is owned by
  `aria_nbv/aria_nbv/lightning/qh_module.py:389-399`;
- the data path is `QhDataset.__getitem__ -> QhChain -> collate_qh_chains ->
  QhBatch -> training_step`, not a direct data-module-to-Lightning call;
- the current thesis owner is
  `docs/typst/thesis/sections/04-method/04-05-finite-candidate-value-model.typ`;
- exact Double-DQN literature evidence is in
  `docs/literature/tex-src/arXiv-Double-DQN/DoubleDQN_aaai2016_total.tex`;
- `DoubleDQN-vanHasselt2015` is owned by `docs/references.bib:643`, not
  `docs/references-qh.bib`.

## Dispositions

- **Retained:** exact source owners and source verification; optional upstream
  installation; the dormant vendored/custom candidate until selection.
- **Removed:** mandatory Graphify routing, normal hook installation, and
  required root/hosted-CI Graphify execution in commit `80eab1ee`.
- **Deferred:** deleting the custom lifecycle, final corpus policy, PDF
  admission, and any upstream TeX/BibTeX capability until the owner selects an
  option. No ARIA-specific semantic parser or adapter is authorized.
- **Open:** the explicit human selection below. Implementation remains in
  progress and no postselection ownership/corpus work may start before it.

## Verification

The comparison verified Graphify 0.9.31 and the user-scoped skill installation,
ran the absent-tool, exact-source, dormant, upstream, stale-HEAD, wrong-root,
false-inference, broad-query, and three-PDF probes, removed the temporary stale
worktree, and left generated graphs untracked. `make check-agent-memory` and
`git diff --check` passed for this record.

## Decision Gate

No composite score or automatic recommendation resolves the measured
trade-offs. The human owner must choose exactly one:

1. delete Graphify completely;
2. retain optional, user-installed, unmodified upstream Graphify; or
3. retain upstream Graphify plus one specifically proven thin adapter, which
   requires a new scoped plan.

## Canonical-State Impact

No canonical state update is required while selection is pending. Commit
`80eab1ee` and current guidance own the already-applied optional-tool boundary;
the selected postcomparison outcome will determine any later canonical update.
