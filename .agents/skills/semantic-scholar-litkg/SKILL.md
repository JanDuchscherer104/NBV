---
name: semantic-scholar-litkg
description: Use for temporary WP6-bound litkg-rs ingestion, ARIA KG config, source adapters, backend exports, and generated KG artifacts.
metadata:
  mode: implementation
  not_when:
    - "ordinary KG retrieval, routing, claim checking, or consolidation"
    - "local source discovery needs no KG tooling change"
  handoff_to:
    - "aria-litkg-memory for retrieval, routing, claims, or consolidation"
    - "aria-nbv-context for deterministic local discovery"
    - "agents-db for backlog-only records"
  evidence_required:
    - "existing litkg-rs adapter or subsystem boundary"
    - "official API evidence for Semantic Scholar behavior changes"
    - "KG capability or smoke output for config changes"
  applies_to:
    - ".agents/external/litkg-rs/**"
    - ".configs/litkg.toml"
    - ".agents/kg/**"
  triggers:
    - "litkg-rs implementation"
    - "Semantic Scholar adapter"
    - "KG config or backend export"
  must_read:
    - ".agents/references/litkg_quick_reference.md"
    - ".agents/skills/semantic-scholar-litkg/references/integration-spec.md"
  canonical_sources:
    - ".gitmodules"
    - ".agents/skills/semantic-scholar-litkg/references/integration-spec.md"
    - ".agents/references/litkg_quick_reference.md#default-commands"
    - ".configs/litkg.toml"
  context7_refs:
    - "/pytorch/pytorch"
    - "/pydantic/pydantic"
    - "/isl-org/open3d"
    - "/lightning-ai/pytorch-lightning"
  literature_refs:
    - "docs/literature/sources.jsonl"
    - "docs/references.bib"
  tool_refs:
    - "mcp__MCP_DOCKER.get_library_docs"
    - "mcp__MCP_DOCKER.list_papers"
  verification:
    - "make kg-capabilities KG_FORMAT=json"
    - "cd .agents/external/litkg-rs && cargo fmt --all --check && cargo test when the submodule is hydrated"
---

# Semantic Scholar LitKG

This implementation sidecar remains active only through WP5; WP6 owns removal.

1. Localize the change to ingestion, source adaptation, config, export, or
   generated artifacts and inspect the existing adapter boundary.
2. Keep repo-independent behavior in `litkg-rs`; keep ARIA paths, authority,
   and source selection in `.configs/litkg.toml` or ARIA owners.
3. Verify current official API behavior before changing Semantic Scholar
   fields, pagination, headers, or rate limits.
4. Preserve agents-DB context/references in KG outputs and avoid a second
   retrieval workflow beside the existing `kg-*` commands.
5. Run the narrow toolkit/config smoke and capability check; report an
   unhydrated submodule as an environment blocker rather than changing policy.
