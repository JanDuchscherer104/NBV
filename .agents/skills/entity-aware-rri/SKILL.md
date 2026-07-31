---
name: entity-aware-rri
description: Use when ARIA-NBV work touches target/entity selection, GT OBB crops, target-specific RRI labels, target-conditioned VIN fields, or entity-aware diagnostics.
metadata:
  mode: implementation
  not_when:
    - "scene-level RRI or geometry work with no target/entity contract"
    - "rollout planning where target-RRI semantics are already fixed"
    - "docs-only glossary wording without RRI, target, or actor-visibility impact"
  handoff_to:
    - "diagnose-aria for concrete target-RRI failures or suspicious metrics"
    - "nbv-geometry-contracts for pose, camera, crop-frame, or unit issues"
    - "counterfactual-rollout-planner for multi-step target-gain evaluation"
    - "aria-grill for advisor-facing target-protocol decisions"
  evidence_required:
    - "V0 versus V1 actor-visibility path and OBS-SEL / PRED-Q / GT-EVAL status"
    - "target crop support, invalid-target reasons, and target/scene RRI comparison"
    - "focused RRI/data-handling test or explicit missing seam"
  applies_to:
    - "aria_nbv/aria_nbv/rri_metrics/**"
    - "aria_nbv/aria_nbv/data_handling/**"
    - "aria_nbv/aria_nbv/vin/**"
    - "docs/contents/thesis/**"
  triggers:
    - "target RRI"
    - "entity-aware"
    - "GT OBB"
    - "OBS-SEL"
  must_read:
    - "docs/contents/thesis/roadmap.qmd#roadmap-m3"
    - "docs/contents/thesis/questions.qmd#rq3-representation"
    - "aria_nbv/aria_nbv/rri_metrics/AGENTS.md"
    - "aria_nbv/aria_nbv/data_handling/AGENTS.md"
  canonical_sources:
    - "docs/contents/theory/rri_theory.qmd#target-specific-error-gain"
    - "docs/contents/theory/rri_theory.qmd#scene-rri-role"
    - "docs/contents/theory/rri_theory.qmd#nbv-objective"
    - "docs/contents/theory/candidate_sampling_target_selection.qmd#actor-visible-target-selection"
    - "docs/contents/theory/candidate_sampling_target_selection.qmd#target-rri-qh-connection"
    - "docs/contents/thesis/roadmap.qmd#roadmap-m3"
    - "docs/contents/thesis/questions.qmd#rq3-representation"
    - "aria_nbv/aria_nbv/rri_metrics/AGENTS.md"
    - "aria_nbv/aria_nbv/data_handling/AGENTS.md"
  literature_refs:
    - "quality-driven-rri"
    - "egocentric-aria-substrate"
    - "VIN-NBV-frahm2025"
  tool_refs:
    - "mcp__code_index.search_code_advanced"
    - "mcp__code_index.get_symbol_body"
  verification:
    - "cd aria_nbv && uv run pytest tests/rri_metrics"
    - "cd aria_nbv && uv run pytest tests/data_handling/test_vin_offline_store.py"
---

# Entity-Aware RRI

## OMX Integration

OMX owns the surrounding plan or execution loop; this skill supplies the
target/entity evidence contract. Return actor-visible versus oracle-only
boundaries, target validity evidence, and the focused RRI verification loop.

## When To Use

Use this skill for:

- target/entity eligibility and selection policies
- GT OBB cropped RRI, target mesh/point support, and invalid target reasons
- target-conditioned VIN batch fields, labels, and diagnostics
- scene-level versus target-level RRI comparisons

Do not use it for generic scene-level RRI unless an entity/target contract is
involved.

## Read First

1. `docs/contents/theory/rri_theory.qmd` for target-specific RRI definitions.
2. `docs/contents/theory/candidate_sampling_target_selection.qmd` for
   actor-visible target selection and GT-label boundaries.
3. `docs/contents/thesis/roadmap.qmd` section M3 and
   `docs/contents/thesis/questions.qmd` section RQ3 for current thesis scope.
4. `aria_nbv/aria_nbv/rri_metrics/AGENTS.md`
5. `aria_nbv/aria_nbv/data_handling/AGENTS.md`

## Rules

- Treat the Quarto theory pages and package `AGENTS.md` files listed in
  `metadata.canonical_sources` as the source of truth for formulas, V0/V1
  semantics, and target-visibility policy.
- Keep actor-visible inputs, oracle-only labels, and GT evaluation crops
  separate in evidence and claims.
- Keep unsupported targets explicit with invalid reasons; do not turn them into
  low-RRI valid samples or scene-level fallback labels.
- Log or inspect target and scene RRI separately when comparing behavior.
- Hand off pose, camera, crop-frame, or unit uncertainty to
  `nbv-geometry-contracts` before changing labels.

## Verification

- `cd aria_nbv && uv run pytest tests/rri_metrics`
- `cd aria_nbv && uv run pytest tests/data_handling/test_vin_offline_store.py`
- `cd docs && quarto render contents/thesis/roadmap.qmd contents/thesis/questions.qmd` when target-aware claims change
- `make check-agent-memory` for memory or skill edits
