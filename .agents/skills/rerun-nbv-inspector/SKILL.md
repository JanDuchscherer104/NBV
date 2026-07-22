---
name: rerun-nbv-inspector
description: Use for ARIA-NBV Rerun offline-store inspection, candidate/frustum visualization, RRI validity diagnostics, camera/depth layers, geometry logging, and `.rrd` smoke artifacts.
metadata:
  mode: implementation
  not_when:
    - "generic Streamlit behavior has no Rerun logging path"
    - "the input store is invalid before Rerun receives it"
    - "geometry semantics outside the inspector are changing"
  handoff_to:
    - "dataset-cache-ops for incompatible or invalid offline stores"
    - "nearest package owner for pose, camera, projection, or label semantics"
    - "specialized diagnostic capability for launch failures or suspicious output"
  evidence_required:
    - "focused inspector test, saved .rrd, or exact store blocker"
    - "entity path, frame direction, candidate order, and display-only transform evidence"
    - "official Rerun evidence for SDK behavior changes"
  applies_to:
    - "aria_nbv/aria_nbv/rerun_inspector/**"
    - "aria_nbv/aria_nbv/app/**"
    - ".configs/rerun_offline.toml"
  triggers:
    - "Rerun inspector"
    - ".rrd artifact"
    - "candidate frustum visualization"
    - "Rerun camera or depth logging"
  must_read:
    - "aria_nbv/AGENTS.md"
    - ".agents/skills/rerun-nbv-inspector/references/nbv-inspector-contract.md"
    - ".agents/skills/rerun-nbv-inspector/references/rerun-python-patterns.md"
  canonical_sources:
    - "aria_nbv/AGENTS.md#geometry-contracts"
    - ".agents/skills/rerun-nbv-inspector/references/nbv-inspector-contract.md"
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
    - "cd aria_nbv && uv run pytest tests/rerun_inspector tests/data_handling/test_offline_visual_inventory.py -q"
---

# Rerun NBV Inspector

1. Read the inspector contract and localize the full logging path.
2. Keep the inspector read-only: never change stored poses, labels, ordering,
   masks, or geometry for display.
3. Declare one scene basis; keep world geometry in world entities and
   camera-local data under posed camera entities.
4. Preserve candidate prefix/order across count, validity, RRI, labels, and
   frusta. Empty/all-invalid cases produce no selected candidate layer.
5. Treat CW90, thinning, color, and blueprints as deterministic display policy.
6. Pair metric depth with matching pose/intrinsics for 3D interpretation.

Prefer a one-sample saved `.rrd` after focused tests. If the store is blocked,
report the exact version/error and use fixtures rather than weakening readers.
