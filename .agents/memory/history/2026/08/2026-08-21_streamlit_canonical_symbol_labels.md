---
id: 2026-08-21_streamlit_canonical_symbol_labels
date: 2026-08-21
title: "Implement Streamlit Canonical Symbol Labels"
status: done
topics: [streamlit, notation, typst, scientific-visualization]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/notation.yml
  - aria_nbv/aria_nbv/app/scientific_labels.py
  - aria_nbv/aria_nbv/app/state.py
  - aria_nbv/aria_nbv/app/app.py
  - aria_nbv/aria_nbv/app/panels/
codex_thread: codex://threads/019fffa4-b85c-7db1-8404-d69c73e6485e
---

## Task

Add one global Symbols/Text/Both preference and reuse exact canonical Typst
notation keys across suitable Streamlit scientific labels without changing
factual data, schemas, exports, or computation.

## Method and findings

The notation registry now enforces exact key-to-Typst-path equality and exposes
the previously unaddressable cumulative root-gain, target-reward, and
directional-error symbols. A Streamlit-free app-level resolver and scientific
label inventory own the field-to-symbol mapping; session state owns the global
display preference. Three owner-disjoint migrations applied the shared helper
to rollout/training, generation/foundation, and model/experiment pages.

A real headless Chrome smoke proved that this Streamlit runtime renders inline
math in Markdown and metric labels, while Plotly titles and axes expose TeX
delimiters literally. Plotly therefore keeps readable text, with canonical
notation rendered once beside relevant figures through one shared helper.

The worktree already contained concurrent root/target-pose inspection changes.
Those source and test hunks were preserved unstaged; only request-owned hunks
were committed.

## Verification

- Canonical glossary validation: 56 terms, 85 symbols, 93 equations.
- Focused combined Pytest suite: 130 passed.
- Ruff format/check across the app and app tests passed.
- Targeted mypy over the shared label, state, and panel helper owners passed.
- `compileall` and `git diff --check` passed.
- Generated notation projections were reproducible with no post-generation diff.

## Canonical-state impact

Scientific notation and presentation behavior changed in their canonical docs
and app owners. Persisted rollout schemas, reducers, training, campaign
generation, Rerun behavior, raw dataframe keys, selector values, and export
columns are unchanged.
