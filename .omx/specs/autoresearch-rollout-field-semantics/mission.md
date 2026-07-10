# Autoresearch Mission: Rollout Field Semantics and Counterfactual UI Alignment

Created: 2026-06-23T09:23:37Z

## Mission

Produce a validated, implementation-grounded plan for the next ARIA-NBV changes around rollout target fields, target-selection equations, projected-area semantics, and Streamlit defaults.

## Required Questions

- Where should the unified thesis explanation of rollout target fields and scores live?
- Which shared Typst equation/symbol modules should own the target-selection and target-RRI equations?
- Which target table fields are actor-visible selector inputs, oracle target-task inputs, GT/evaluation-only fields, or diagnostics?
- What is the current meaning of `projected_area_px`, why can it be zero for all rows, and what replacement or clarification is needed?
- How should `_page_counterfactual_rollouts` get defaults from `.configs/*.toml` instead of hard-coded widget values?

## Validation Mode

`prompt-architect-artifact`

The completion artifact must include an architect approval verdict and point to `result.md`.

