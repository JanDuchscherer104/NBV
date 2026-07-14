---
id: 2026-07-14_graphify_docstrings_and_slop_prune
date: 2026-07-14
title: "Graphify, Python API Contracts, and Slop Pruning"
status: done
topics: [graphify, docstrings, aria_nbv, simplification, architecture]
confidence: high
canonical_updates_needed: []
files_touched:
  - .codex/skills/graphify/SKILL.md
  - aria_nbv/aria_nbv
  - aria_nbv/tests/utils/test_rich_summary.py
assumptions:
  - "Docstrings specify the current implementation contract; they do not promise future equivariances or provenance that the code does not enforce."
---

Graphify now resolves the Python environment behind the installed `graphify`
entry point, persists semantic extraction artifacts in a unique run directory,
and merges only the chunks named by that run's manifest. This prevents late
writers from an interrupted pass contaminating a retry and treats the artifact
rather than conversational output as the success boundary. The workflow uses
write-capable executor agents outside OMX team mode and no longer depends on
obsolete worker or close-agent behavior.

The `aria_nbv` package documentation now makes important tensor axes, dtypes,
units, coordinate frames, temporal conventions, storage lineage, and
actor-versus-oracle boundaries explicit. In particular, rollout and RRI APIs
distinguish invalid candidates from low-scoring candidates, VIN documentation
states only the permutation symmetries actually implemented, and EFM/VIN data
contracts link local voxel fields and trajectory-relative quantities to their
source poses and scene frames.

The low-risk simplification pass folded the duplicate `utils.summary`
implementation into `utils.rich_summary`, retained a compact direct-import
compatibility re-export, added behavior regression coverage, and removed dead
commented Streamlit controls. Remaining higher-risk slop is concentrated in
the twin counterfactual oracle scorers, the large Zarr schema/store module,
parallel rollout diagnostic surfaces, duplicated frustum and CW90 transforms,
broad exception swallowing, and private `_records` coupling. Those seams need
behavior-locking tests before consolidation.

Verification reached zero standard and module-overview docstring audit findings
across the package. Ruff formatting/linting, Python compilation, executable-AST
comparison for docstring-only files, the focused summary regression test, and
the package test suite passed. The final Graphify corpus statistics and health
warnings are recorded in the generated `graphify-out` report rather than in
canonical memory because those metrics change with the repository corpus.
