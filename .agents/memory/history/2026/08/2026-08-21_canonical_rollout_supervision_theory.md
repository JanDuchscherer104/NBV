---
id: 2026-08-21_canonical_rollout_supervision_theory
date: 2026-08-21
title: "Canonical rollout supervision theory"
status: done
topics: [rollout-supervision, streamlit, typst, scientific-notation]
confidence: high
canonical_updates_needed: []
codex_thread: codex://threads/019fffa4-b85c-7db1-8404-d69c73e6485e
---

## Task
Ground Rollout Supervision plot explanations in canonical shared equations, symbols, and glossary terms without parsing Typst at runtime.

## Method
Corrected and extended the shared notation registry, regenerated its tracked Typst projections, added a typed YAML theory resolver, and migrated every `_stored_rollouts` explanation to a concise narrative interface with explicit theory references.

## Findings
`docs/notation.yml` now distinguishes immediate rollout-root reward, observed cumulative prefix, endpoint gain, and finite-horizon return. `aria_nbv/aria_nbv/app/panels/_stored_rollouts/theory.py` owns runtime resolution and source links. `shared.py` renders resolved equations with `st.latex`, relevant symbols and terms, and a visible warning when canonical theory cannot be resolved. All Rollout Supervision explanations use the new section-based interface; `counterfactual_rollouts.py` remains unchanged.

## Verification
Glossary validation and focused Typst compilation passed. The combined theory, Rollout Supervision panel, laziness, validation-gate, and progressive-disclosure suite passed with 104 tests. Ruff format/check, compileall, URL checks, and `git diff --check` passed. Targeted mypy remained blocked by missing third-party PyYAML, pandas, and Plotly stubs plus one pre-existing `shared.py` dataclass-narrowing error.

## Canonical Owner Impact
Updated canonical scientific truth in `docs/notation.yml` and generated shared Typst equation/symbol projections; updated runtime lookup and presentation owners under `aria_nbv/aria_nbv/app/panels/_stored_rollouts`; updated their focused tests. No schema, campaign, training, Rerun, dependency, or `counterfactual_rollouts.py` change.
