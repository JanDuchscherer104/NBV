---
id: 2026-08-22_scientific_readme_and_package_data_lineage
date: 2026-08-22
title: "Scientific README and package data lineage"
status: done
topics: [documentation, readme, architecture, data-lineage]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - README.md
  - aria_nbv/README.md
  - docs/figures/diagrams/data_handling/mermaid/package_data_lineage.mmd
  - docs/figures/diagrams/data_handling/mermaid/package_data_lineage.svg
codex_thread: codex://threads/01a02a4f-a49b-70a0-a68b-eb8fc77dfed1
repo_object_format: sha1
repo_head: d0df09abf02f15f24bb5984362914e90067c3f43
repo_branch: "codex/readme-scientific-diagram"
worktree_kind: linked
---

## Task
Replace promotional project framing with a neutral scientific entry point and
add a package-level data-lineage diagram that identifies the modalities crossing
the immutable VIN and rollout-store boundaries.

## Method
Checked the active thesis research questions and roadmap, package storage
contracts, and exact Python owners. Reframed the root README around scope,
evidence status, protocol, and reproducible entry points. Adapted the selected
two-store Mermaid candidate with modality-labelled edges, then rendered its SVG
with the official Mermaid CLI 11.16.0 container.

## Findings
`README.md` now distinguishes implemented substrate, open evidence gates, and
deferred scope without claiming a completed target-conditioned policy result.
`aria_nbv/README.md` now explains the physical-store split and links to the
detailed data-handling and rollout owners. The source and rendered overview live
at `docs/figures/diagrams/data_handling/mermaid/package_data_lineage.{mmd,svg}`.

## Verification
Passed Mermaid lint with zero warnings, 21 ownership-consolidation tests,
relative-link checks, GitHub GFM rendering, `make docs-render-core`, and
`uv build` for both sdist and wheel. The documentation render retained existing
generated API-link warnings but exited successfully.

## Canonical Owner Impact
The two README owners and their diagram were updated. No Typst, Python,
configuration, test, setup, or agent-guidance owner required a change.
