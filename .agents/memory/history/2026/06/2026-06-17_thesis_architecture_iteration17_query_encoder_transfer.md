---
id: 2026-06-17_thesis_architecture_iteration17_query_encoder_transfer
date: 2026-06-17
title: "Thesis Architecture Iteration 17 Query Encoder Transfer"
status: done
topics: [thesis, architecture, q-h, qcnet, literature]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/04-method/index.typ
  - docs/typst/thesis/sections/02-foundations/index.typ
  - docs/literature/sources.jsonl
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Summary

Iteration 17 integrates the completed subagent scan around QCNet/QCNeXt and
referenced trajectory-forecasting encoders. It keeps the useful transfer narrow:
query-centric local frames, typed relative encodings, and local/global support
hierarchies are relevant to candidate-query `Q_H`; trajectory decoders and
scene-level pooled confidence heads are not.

## Evidence

- `docs/literature/tex-src/arXiv-QCNet/main.tex` describes the QCNet encoder as
  query-centric, local-spacetime-frame based, and driven by relative
  spatial-temporal positional embeddings.
- `docs/typst/thesis/sections/04-method/index.typ` already requires independent MLP
  and pooled DeepSets controls before masked Set Transformer or QCNet-style
  relative positional encodings.
- `docs/contents/ideas.qmd` records query-centric attention, frustum/space
  tokens, and early-fusion questions as local design leads.
- `docs/literature/tex-src/arXiv-QCNet/egbib.bib` references Perceiver, HiVT,
  Scene Transformer, and Wayformer, which are useful enough to become explicit
  manifest entries or documented referenced-paper leads.

## Canonical Updates Needed

- Add the candidate-query encoder contract to the thesis method section:
  typed tokens, target/candidate local frames, edge-typed RPE, hard masks, and
  per-candidate residual-dueling outputs.
- Decide whether VectorNet, Perceiver, Wayformer, HiVT, and Scene Transformer
  become `docs/literature/sources.jsonl` entries with relevance metadata and
  litkg propagation.
- Add tests for row permutation, duplicate candidates, invalid-row firewall,
  target-frame transforms, history-step shuffles, fusion-source dropout, and
  absolute-head contamination.
