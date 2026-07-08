---
id: 2026-06-22_scene_encoding_architecture_suggestions_docs
date: 2026-06-22
title: "Scene Encoding Architecture Suggestions Docs"
status: done
topics: [thesis, efm3d, scene-memory, qh, documentation]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/contents/literature/efm3d.qmd
  - docs/contents/literature/rl_planning.qmd
  - docs/contents/theory/candidate_view_dependence.qmd
  - docs/contents/theory/efm3d_scene_embeddings.qmd
  - docs/contents/theory/rl_planning.qmd
  - docs/contents/thesis/advisor_meeting_2026_05_22_questions.md
  - docs/contents/thesis/questions.qmd
  - docs/contents/thesis/roadmap.qmd
  - docs/contents/glossary.qmd
  - docs/glossary/terms.yml
  - docs/_generated/context/glossary.jsonl
  - docs/typst/shared/equations/features.typ
  - docs/typst/shared/equations/rl.typ
  - docs/typst/shared/glossary.typ
  - docs/typst/thesis/advisor_meeting_2026_05_22.typ
  - docs/typst/thesis/sections/01-introduction.typ
  - docs/typst/thesis/sections/02-foundations/02-01-related-work.typ
  - docs/typst/thesis/sections/02-foundations/02-02-geometric-learning.typ
  - docs/typst/thesis/sections/04-method/index.typ
---

## Task

Incorporated the valid parts of the scene-encoding architecture critique into
the thesis and peripheral documentation. The accepted corrections separate the
target proposer from scene memory, keep EFM3D/EVL as an Aria-native perception
substrate, and avoid promoting appearance features or set interaction patterns
beyond what the rollout problem can justify.

## Method

Reframed the first persistent scene-memory upgrade as sparse ray-aware
occupied/free/unknown evidence rather than DINO-on-point. DINO descriptors remain
as actor-visible appearance ablations, gated by visibility evidence rather than
projection validity alone. Candidate frustum pooling is described as a support
summary, while candidate observation reasoning uses a ray/render-style query over
the persistent scene memory.

Updated the finite-horizon value-function narrative to use candidate-to-state
query attention as the default implementation, with candidate-candidate
self-attention and pooled set models kept as controls or ablations. Replaced
exact mean-centred residual dueling language with an uncentred continuous-return
residual, and scoped CORAL-style ordinal objectives to the one-step scorer.

## Verification

- `git diff --check`
- `make qmd-frontmatter-check`
- focused `quarto render` checks for the edited Quarto/Markdown pages
- `cd docs && typst compile typst/thesis/main.typ /tmp/aria-nbv-thesis-after-suggestion-incorporation.pdf --root .`
- `pdfinfo /tmp/aria-nbv-thesis-after-suggestion-incorporation.pdf`

## Notes

No implementation behavior was changed in this pass. The edits are documentation
and notation alignment only, preserving actor-visible/oracle separation and
marking the revised scene-memory components as planned thesis architecture.
