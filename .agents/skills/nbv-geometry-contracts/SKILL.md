---
name: nbv-geometry-contracts
description: Use when ARIA-NBV work touches pose, camera, coordinate-frame, CW90, PyTorch3D projection, depth backprojection, candidate frusta, or geometry diagnostics contracts.
metadata:
  mode: implementation
  not_when:
    - "model-head, docs-only, or app-only changes with no pose, camera, depth, or frame contract"
    - "target/entity RRI semantics where geometry contracts are unchanged"
    - "Rerun viewer layout work that is display-only and already frame-verified"
  handoff_to:
    - "diagnose-aria for concrete geometry failures or suspicious rendered output"
    - "rerun-nbv-inspector for Rerun frame-coordinate or entity-tree diagnostics"
    - "entity-aware-rri for target crop semantics and target-specific labels"
    - "counterfactual-rollout-planner for rollout candidate geometry in non-myopic evaluation"
  evidence_required:
    - "frame convention, transform direction, tensor shape, and units for touched data"
    - "focused rendering, pose-generation, or RRI test output"
    - "visual diagnostic only when static tests cannot prove the frame contract"
  applies_to:
    - "aria_nbv/aria_nbv/pose_generation/**"
    - "aria_nbv/aria_nbv/rendering/**"
    - "aria_nbv/aria_nbv/rri_metrics/**"
    - "aria_nbv/aria_nbv/utils/data_plotting.py"
  triggers:
    - "PoseTW"
    - "CameraTW"
    - "CW90"
    - "backprojection"
  must_read:
    - "AGENTS.md"
    - "aria_nbv/AGENTS.md"
    - ".agents/memory/state/GOTCHAS.md"
  canonical_sources:
    - "aria_nbv/AGENTS.md#core-rules"
    - "aria_nbv/AGENTS.md#core-rules"
    - ".agents/references/external_stack_contracts.md#efm3d-and-evl"
    - "docs/typst/thesis/sections/03-oracle-and-data-generation/03-01-state-and-visibility.typ"
    - ".agents/memory/state/GOTCHAS.md"
  context7_refs:
    - "/facebookresearch/pytorch3d"
    - "/pytorch/pytorch"
  literature_refs:
    - "egocentric-aria-substrate"
  tool_refs:
    - "mcp__code_index.search_code_advanced"
    - "mcp__code_index.get_symbol_body"
    - "mcp__MCP_DOCKER.get_library_docs"
  verification:
    - "cd aria_nbv && uv run pytest tests/pose_generation tests/rendering"
    - "cd aria_nbv && uv run pytest tests/rri_metrics when labels change"
    - "make context-contracts when generated contract context is needed"
---

# NBV Geometry Contracts

## OMX Integration

OMX owns orchestration; this skill owns ARIA geometry invariants used by an OMX
phase. Return frame/shape/unit evidence, the smallest failing or passing test,
and any required handoff to Rerun, RRI, or rollout sidecars.

## When To Use

Use this skill for changes or reviews involving:

- `PoseTW`, `CameraTW`, rig/camera/world transforms, or `T_target_source` naming
- candidate poses, candidate frusta, PyTorch3D cameras, NDC, or depth maps
- CW90 corrections, gravity alignment, or display-only rotations
- depth backprojection, point-cloud construction, or visibility diagnostics

Do not use it for pure model-head, docs-only, or non-geometry app changes.

## Read First

1. `AGENTS.md`
2. `aria_nbv/AGENTS.md`
3. `aria_nbv/AGENTS.md` and `python-standards` when generic Python guidance is needed
4. `.agents/references/external_stack_contracts.md`
5. `.agents/memory/state/GOTCHAS.md`
6. `aria_nbv/aria_nbv/vin/AGENTS.md` when VIN batch/candidate fields are touched
7. The focused rendering or pose-generation tests for the changed path
8. `docs/_generated/context/data_contracts.md` only after `make
   context-contracts` when you need the generated contract index

## Contract Rules

- Treat `aria_nbv/AGENTS.md`, the `python-standards` skill, and
  `.agents/references/external_stack_contracts.md` as the canonical owners for
  frame, transform, camera, and external-stack conventions.
- Return the frame convention, transform direction, tensor shape, units, and
  smallest relevant test evidence for the touched surface.
- Keep display-only visualization corrections out of training, rendering, and
  store semantics unless the canonical owner and tests change together.
- Hand off target crop semantics to `entity-aware-rri` and Rerun entity-tree or
  visual artifact issues to `rerun-nbv-inspector`.

## Verification

- `cd aria_nbv && uv run pytest tests/rendering/test_depth_backprojection_conventions.py`
- `cd aria_nbv && uv run pytest tests/rendering/test_candidate_renderer_integration.py tests/rendering/test_pytorch3d_renderer.py`
- `cd aria_nbv && uv run pytest tests/vin/test_vin_utils.py` when VIN diagnostics or batch fields are affected
- `make check-agent-memory` for guidance or memory edits

## Diagnostics Matrix

- Pose/frame edits: assert transform direction, units, and `PoseTW` batch shape.
- Camera/projection edits: assert `CameraTW` intrinsics/extrinsics and
  PyTorch3D/NDC conventions.
- Depth/backprojection edits: assert metric-depth interpretation, valid masks,
  and world-frame point bounds.
- Candidate-frustum edits: assert display-only CW90 corrections do not mutate
  training, rendering, or store semantics.
- Streamlit diagnostics: verify figures are display transforms only and do not
  feed back into model or oracle data.
