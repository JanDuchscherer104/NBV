---
id: 2026-06-18_thesis_mermaid_visual_iteration1
date: 2026-06-18
title: "Thesis Mermaid Visual Iteration 1"
status: done
topics: [thesis, mermaid, typst, figures]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/typst/thesis/sections/02-foundations/index.typ
  - docs/typst/thesis/sections/03-oracle-and-data-generation/03-01-state-and-visibility.typ
  - docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ
  - docs/typst/thesis/sections/04-method/index.typ
  - docs/typst/thesis/sections/05-experimental-design/index.typ
---

## Task

Begin the interruptible thesis-diagram Ralph loop by adding high-value existing Mermaid/SVG figures to the active Typst thesis seed.

## Method

Used `aria-nbv-mermaid`, `typst-authoring`, and Prometheus-style critique to select protocol and boundary figures instead of decorative architecture charts. Reused existing lint-clean Mermaid sources where available, rendered the missing target-sampler export locally through Chrome-backed Mermaid CLI, and switched active Typst inclusion to Mermaid-rendered PDFs after visual QA showed Typst drops Mermaid SVG foreign-object labels.

## Outputs

- Swapped the background system-flow inclusion from PNG to Mermaid-rendered PDF after SVG label rendering failed in Typst.
- Added the actor-visible versus oracle-only contract figure to `03-01-formal-state.typ`.
- Added the oracle target-task sampler contract figure to `03-02-data-generation.typ`.
- Swapped active Mermaid image inclusions from SVG/PNG to PDF for print-correct labels.
- Added the actor-visible directional-memory figure and caption to the method replay-contract section.
- Added the finite-candidate architecture sketch to the value-model method section and removed the extra alignment wrapper so the caption and prose stay adjacent to the wide diagram.
- Added the teacher/student render-path boundary figure to the evaluation section to keep privileged dense renders outside V1 actor inputs.
- Added the rollout replay / masked Double-Q contract figure to `04-evaluation.typ` and cross-referenced it from the replay evidence text.
- Removed the extra alignment wrapper from the wide rollout replay figure so the page no longer leaves a large blank region between diagram and caption.

## Verification

Ran `python3 tools/mermaid/scripts/aria_mermaid_lint.py docs/typst/thesis/figures/*.mmd`, which passed with zero errors and zero warnings. The target sampler source was normalized until lint reported no issues. Rendered Mermaid PDF companions using `PUPPETEER_EXECUTABLE_PATH=/usr/bin/google-chrome-stable npx --yes @mermaid-js/mermaid-cli ... --pdfFit`; `mmdc` was not installed globally, so the local `npx` path was used. The thesis compiled with `cd docs && typst compile typst/thesis/main.typ /tmp/aria-nbv-thesis-mermaid-iteration.pdf --root .` using Typst 0.14.2. Rendered representative pages with `pdftoppm` and visually inspected the current Figure 4, Figure 6, Figure 7, and Figure 8 pages; labels are visible, captions do not collide with page numbers, and the wide-diagram captions remain adjacent after removing the unnecessary alignment wrappers. Mermaid SVGs remain source/preferred export artifacts, but Typst active inclusion currently uses PDF because Typst drops Mermaid SVG `foreignObject` labels.

## Canonical State Impact

No canonical thesis-direction or memory state update is needed. The change is a thesis-presentation improvement using already-owned thesis sources.
