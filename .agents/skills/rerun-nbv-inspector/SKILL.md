---
name: rerun-nbv-inspector
description: Use when creating, reviewing, or fixing ARIA-NBV Rerun integrations for immutable VIN offline-store inspection, NBV candidate/frustum visualization, RRI/validity diagnostics, depth/RGB/keyframe layers, OBB/mesh/trajectory logging, `.rrd` smoke artifacts, or Rerun frame-coordinate issues involving PoseTW, CameraTW, PyTorch3D cameras, and display-only CW90 handling.
metadata:
  mode: implementation
  not_when:
    - "generic Streamlit UI behavior with no Rerun artifact or visual logging path"
    - "offline-store data validity before Rerun receives a compatible sample"
    - "geometry-frame changes outside the Rerun logging or inspection surface"
  handoff_to:
    - "diagnose-aria for concrete Rerun launch failures or suspicious visual output"
    - "dataset-cache-ops for incompatible or invalid offline stores"
    - "nbv-geometry-contracts for PoseTW, CameraTW, projection, or CW90 frame issues"
    - "aria-litkg-memory for official-doc/API lookup when Rerun behavior is uncertain"
  evidence_required:
    - "focused inspector test, saved .rrd smoke artifact, or exact store incompatibility"
    - "entity-path, frame-coordinate, and display-only downsampling evidence"
    - "official Rerun/API evidence when changing SDK usage patterns"
  applies_to:
    - "aria_nbv/aria_nbv/app/**"
    - "aria_nbv/aria_nbv/rerun_inspector/**"
    - "aria_nbv/aria_nbv/**/rerun*.py"
    - "docs/reference/**"
    - ".agents/skills/rerun-nbv-inspector/**"
  triggers:
    - "Rerun"
    - "offline inspector"
    - ".rrd"
    - "candidate frustum"
  must_read:
    - "AGENTS.md"
    - "aria_nbv/AGENTS.md"
    - ".agents/skills/rerun-nbv-inspector/references/nbv-inspector-contract.md"
    - ".agents/skills/rerun-nbv-inspector/references/context7-queries.md"
  canonical_sources:
    - "aria_nbv/AGENTS.md#core-rules"
    - ".agents/skills/rerun-nbv-inspector/references/nbv-inspector-contract.md"
    - ".agents/skills/rerun-nbv-inspector/references/context7-queries.md"
    - ".agents/skills/rerun-nbv-inspector/references/rerun-python-patterns.md"
    - ".agents/references/external_stack_contracts.md"
  context7_refs:
    - "/rerun-io/rerun"
    - "/websites/streamlit_io"
    - "/facebookresearch/pytorch3d"
  literature_refs:
    - "quality-driven-rri"
    - "egocentric-aria-substrate"
  tool_refs:
    - "mcp__MCP_DOCKER.get_library_docs"
    - "mcp__MCP_DOCKER.browser_run_code"
    - "mcp__code_index.search_code_advanced"
  verification:
    - "focused Rerun inspector tests or smoke command for changed surface"
---

# Rerun NBV Inspector

## OMX Integration

OMX owns task orchestration; this skill owns ARIA Rerun evidence production.
Return the exact inspector command, artifact path, frame/entity evidence, and
handoffs for data or geometry blockers.

## Overview

Use this skill for ARIA-NBV Rerun work where visual diagnostics must protect
data, geometry, and RRI contracts. Treat Rerun as an observer sink for offline
samples and rollout diagnostics, not as the owner of scientific semantics.

Start from current official Rerun docs and examples before changing API usage.
Use the PRML `rerun-slam-integration` skill as a pattern source, but keep
ARIA-NBV-specific decisions grounded in immutable VIN stores and NBV geometry.

## Workflow

1. Load current repo guidance first: `AGENTS.md`, `aria_nbv/AGENTS.md`, and
   `aria_nbv/aria_nbv/data_handling/AGENTS.md` when the offline store is
   touched.
2. Query Rerun docs with Context7 library id `/rerun-io/rerun`; start from
   `references/context7-queries.md` and use the smallest relevant query.
3. Read `references/rerun-python-patterns.md` for recording, entity-tree,
   camera/depth, transform, and timeline guardrails.
4. Read `references/nbv-inspector-contract.md` before editing or reviewing
   ARIA-NBV inspector code, tests, docs, or `.configs/inspection/rerun/rerun_offline.toml`.
5. Read `references/official-examples-map.md` when choosing a Rerun example to
   compare against.
6. Inspect every touched `rr.` call site along the logging path, not just the
   failing sink.
7. For real smoke, prefer a saved `.rrd` artifact from one sample:

```bash
cd aria_nbv
uv run nbv-rerun-inspect --config-path ../.configs/inspection/rerun/rerun_offline.toml \
  --split val --index 0 --save ../.artifacts/rerun/sample.rrd
```

If the local store is version-blocked or partial, report the exact store error
and run fixture/fake-Rerun tests instead of weakening validation.

## Guardrails

- Keep Rerun read-only: never mutate offline-store poses, RRI labels, candidate
  ordering, validity masks, cached geometry, or training payloads for display.
- Declare one scene basis at the root, normally `rr.ViewCoordinates.RIGHT_HAND_Z_UP`
  for ARIA-NBV world-space diagnostics unless the code documents another choice.
- Treat `PoseTW` candidate poses as `T_world_cam` and reference rig poses as
  `T_world_rig`; do not pass raw matrices across public Rerun helper boundaries.
- Prefer native `rr.Transform3D` + `rr.Pinhole` camera entities for candidate
  cameras when transform direction and camera convention are covered by tests.
  Keep `rr.LineStrips3D` for trajectories and selected-view paths.
- Put `Pinhole`, RGB, and metric `DepthImage(..., meter=1.0)` on matching
  camera/image entities when depth is meant for 3D interpretation.
- Keep camera-local points under posed camera entities; keep world-space
  semidense, fused, mesh, OBB, and trajectory geometry under world-space paths.
- Preserve zero-candidate and all-invalid candidate cases as empty/no-top
  visual layers; never let padded rows become real candidates.
- Use stable, low-cardinality entity paths for candidate sets; batch frusta,
  centers, OBBs, and point clouds rather than logging one entity per candidate
  unless a specific selected candidate needs isolation.
- Treat blueprints as viewer layout only. They must not encode candidate
  validity, RRI, frame, or dataset semantics.
- Keep downsampling deterministic and display-only.

## Review Checklist

- Confirm config-as-factory usage and `.configs/inspection/rerun/rerun_offline.toml` stay aligned
  with `RerunOfflineInspectorConfig`.
- Confirm required visual inventory failures happen before `rr.init`, `rr.save`,
  `rr.spawn`, or `rr.connect_grpc`.
- Confirm candidate count, validity mask, oracle RRI, accuracy/completeness
  deltas, and frustum labels use the same prefix/order.
- Confirm `candidate_count=0` logs no candidates and an all-invalid mask logs no
  top-oracle frustum.
- Confirm `Pinhole.resolution` is `[width, height]`, while PyTorch3D
  `image_size` remains `(height, width)`.
- Confirm `DepthImage` layers are either explicit 2D diagnostics or paired with
  camera pose/intrinsics for 3D interpretation.
- Confirm generated `.rrd` outputs are smoke artifacts under `.artifacts/` or
  another non-training path.

## Verification

Use the narrowest checks that cover the touched surface:

```bash
cd aria_nbv
uv run ruff check aria_nbv/rerun_inspector tests/rerun_inspector \
  aria_nbv/data_handling/_offline_visual_inventory.py
uv run pytest tests/rerun_inspector tests/data_handling/test_offline_visual_inventory.py -q
```

When the store is compatible:

```bash
cd aria_nbv
uv run nbv-rerun-inspect --config-path ../.configs/inspection/rerun/rerun_offline.toml \
  --split val --index 0 --save ../.artifacts/rerun/sample.rrd
```
