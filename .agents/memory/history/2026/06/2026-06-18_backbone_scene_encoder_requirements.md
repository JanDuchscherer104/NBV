---
id: 2026-06-18_backbone_scene_encoder_requirements
date: 2026-06-18
title: "Backbone Scene Encoder Requirements"
status: done
topics: [thesis, scene-encoding, backbone, target-rri]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/typst/thesis/sections/03-method.typ
---

## Task

Added a thesis-method subsection that makes backbone and scene-encoder
requirements explicit before the candidate/replay and value-model contracts.

## Output

- Made OBB-capable actor-visible target evidence a hard gate for any thesis-core
  backbone replacement.
- Kept EFM3D/EVL as the Aria/ASE-native anchor for OBB and local target/support
  evidence.
- Scoped semidense/fused point banks, compressed DINO-on-point features, EVL
  internal/crop reads, point/sparse encoders, 3DGS-style state, and Deja
  View-style recurrence as conditioning ablations or bridges rather than
  immediate backbone replacements.
- Preserved the historic-versus-counterfactual modality boundary: rich logged
  snippets can expose image/EVL/OBB evidence, while counterfactual states cannot
  assume fresh RGB/DINO/semantic/detector outputs unless a separate validated
  renderable or learned modality generator exists.

## Verification

- `cd docs && typst compile typst/thesis/main.typ --root . /tmp/thesis-main.pdf`
- `git diff --check -- docs/typst/thesis/sections/03-method.typ`

## Canonical State Impact

No separate canonical state update is required. The active thesis seed owns this
method wording.
