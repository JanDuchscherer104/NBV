---
id: 2026-06-23_thesis_descriptor_encoding_patch
date: 2026-06-23
title: "Thesis Descriptor Encoding and Notation Patch"
status: done
topics: [thesis, typst, descriptors, scene-encoding, notation]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/typst/shared/equations/entity.typ
  - docs/typst/shared/equations/model.typ
  - docs/typst/shared/equations/rl.typ
  - docs/typst/shared/equations/scene.typ
  - docs/typst/shared/equations/spatial.typ
  - docs/typst/shared/glossary.typ
  - docs/typst/shared/symbols/model.typ
  - docs/typst/shared/symbols/scene.typ
  - docs/typst/shared/symbols/spatial.typ
  - docs/notation.yml
  - tools/mermaid/references/aria_symbol_map.yaml
  - docs/contents/literature/efm3d.qmd
  - docs/contents/theory/efm3d_scene_embeddings.qmd
  - docs/typst/thesis/figures/oracle_target_task_sampler_contract.mmd
  - docs/typst/thesis/figures/oracle_target_task_sampler_contract.pdf
  - docs/typst/thesis/figures/oracle_target_task_sampler_contract.svg
  - docs/typst/thesis/figures/qh_teacher_student_render_path.mmd
  - docs/typst/thesis/figures/qh_teacher_student_render_path.pdf
  - docs/typst/thesis/figures/qh_teacher_student_render_path.svg
  - docs/typst/thesis/figures/qh_vin_gnn_architecture.mmd
  - docs/typst/thesis/figures/qh_vin_gnn_architecture.pdf
  - docs/typst/thesis/figures/qh_vin_gnn_architecture.svg
  - docs/typst/thesis/figures/qh_symmetry_contract.mmd
  - docs/typst/thesis/figures/qh_symmetry_contract.pdf
  - docs/typst/thesis/figures/qh_symmetry_contract.svg
  - docs/typst/thesis/figures/qh_symmetry_contract.png
  - docs/typst/thesis/figures/qh_directional_memory.mmd
  - docs/typst/thesis/figures/qh_directional_memory.pdf
  - docs/typst/thesis/figures/qh_directional_memory.svg
  - docs/typst/thesis/figures/qh_actor_oracle_contract.mmd
  - docs/typst/thesis/figures/qh_actor_oracle_contract.pdf
  - docs/typst/thesis/figures/qh_actor_oracle_contract.svg
  - docs/typst/thesis/figures/proposal_system_flow.mmd
  - docs/typst/thesis/figures/proposal_system_flow.pdf
  - docs/typst/thesis/figures/proposal_system_flow.svg
  - docs/typst/thesis/figures/proposal_system_flow.png
  - docs/typst/thesis/sections/04-method/04-01-scene-representation-requirements.typ
  - docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ
  - docs/typst/thesis/sections/04-method/04-02-descriptor-and-encoding-plan.typ
  - docs/typst/thesis/sections/04-method/04-03-candidate-and-replay-contract.typ
  - docs/typst/thesis/sections/04-method/04-04-architecture-contract.typ
  - docs/typst/thesis/sections/04-method/04-05-finite-candidate-value-model.typ
---

## Task

Patch the thesis method sections after peer review of the descriptor and encoding
plan. The section needed one clear owner for descriptor definitions, a cleaner
narrative for target, scene, candidate, relation, and directional-history
features, and less duplication across neighboring method sections. A follow-up
notation pass also had to standardize target descriptors, query pools, ray-query
features, candidate-relative geometry, and model-row tokens.

## Method

Rewrote `04-02-descriptor-and-encoding-plan.typ` as the descriptor catalogue and
model-input protocol. Moved the directional-history explanation and figure into
that section, kept candidate/replay storage details in `04-03`, and kept the
finite-candidate value model architecture in `04-05`. Cleaned the shared target
descriptor equation and updated the oracle/data-generation prose that invokes it.
Added `scene`, `spatial`, and `model` namespaces under shared Typst symbols and
equations so the thesis can distinguish actor-visible records, learned tokens,
support pools, ray queries, and provenance. Updated Quarto implementation notes
to use the same notation and to keep EVL internals, DINO point-bank extraction,
and cache provenance details outside the main thesis prose. Updated thesis
Mermaid sources, rendered figure artifacts, and the Mermaid symbol map so diagram
labels use the same `phi_e` target descriptor as the thesis text and symbol
index. After final review, normalized the live thesis Mermaid figures from stale
bold-calligraphic set notation to shared `cal(P)`, `cal(Q)`, and `cal(M)`
symbols, and split actor-visible evidence from oracle matching assets in the
target-task diagram.

## Verification

Validated shared notation with `make glossary`, compiled the thesis with
`typst compile typst/thesis/main.typ /tmp/aria-thesis-notation-patch.pdf
--root . --input aria-wip-links=false`, rendered the changed Quarto EFM3D pages,
checked whitespace with `git diff --check`, and scanned for stale ambiguous
symbols such as `bold(T)_e`, `hat(p)_e`, old feature-namespace invocations, and
old VIN pool names. Mermaid figure sources were linted with
`aria_nbv/.venv/bin/python tools/mermaid/scripts/aria_mermaid_lint.py ...` and
rendered with `npx @mermaid-js/mermaid-cli` plus `/usr/bin/google-chrome`.

## Canonical State Impact

No canonical state update is needed. The patch changes thesis exposition and
shared equation wording, not project behavior or repo guidance.
