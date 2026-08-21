---
id: 2026-08-21_candidate_choice_comparison_plots
date: 2026-08-21
title: "Candidate choice comparison plots"
status: done
topics: [rollouts, inspection, streamlit, candidate-selection]
confidence: high
canonical_updates_needed: []
codex_thread: codex://threads/019fffa4-b85c-7db1-8404-d69c73e6485e
---

## Task
Add reversible candidate-family plots that preserve factual time, conditional choice context, and observed sequence returns.

## Method
Deepened the single-pass candidate population projection before adding plot-first Streamlit views. Kept the complete store audit behind the existing explicit load control and keyed its cache by store identity plus a projection revision.

## Findings
- `aria_nbv/aria_nbv/rollouts/inspection.py` owns state-level family availability, policy mass, realized choice, conditional transitions, factual sequences, and sequence-level terminal-return summaries.
- `aria_nbv/aria_nbv/app/panels/_stored_rollouts/candidate_generation.py` compares one exact cohort at a time over acquisition depth and through expected-versus-realized transition heatmaps; raw rows remain collapsed.
- `aria_nbv/aria_nbv/app/panels/_stored_rollouts/reconstruction_return.py` keeps the post-selection sequence/return comparison in Reward & reconstruction and labels it exploratory rather than causal.
- Position, direction, generator component, and position-direction vocabularies are independently selectable. Incompatible generation controls are never pooled.

## Verification
- Focused inspection and Streamlit suites: 173 passed.
- Ruff format/check, compileall, and `git diff --check`: passed.
- A validated promoted smoke artifact produced all four vocabularies, temporal summaries, conditional transitions, selected sequences, and all three Plotly figure types without error.

## Canonical Owner Impact
Current truth changed only in presentation-free rollout inspection, stored-rollout Streamlit panels, their cache seam, and focused tests. No schema, generation, training, dependency, or Typst contract changed.
