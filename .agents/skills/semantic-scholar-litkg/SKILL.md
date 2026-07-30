---
name: semantic-scholar-litkg
description: Use when changing or operating ARIA-NBV litkg-rs ingestion, KG config, backend/export contracts, source adapters, or generated KG artifacts.
metadata:
  mode: implementation
  not_when:
    - "ordinary KG retrieval, task routing, claim checks, or consolidation"
    - "local source discovery without KG tooling changes"
    - "agent backlog edits without litkg integration impact"
  handoff_to:
    - "aria-litkg-memory for retrieval, routing, claim checks, or consolidation"
    - "aria-nbv-context for deterministic local discovery"
    - "agents-db for backlog-only records"
  evidence_required:
    - "litkg-rs owner boundary or existing adapter inspection"
    - "official API documentation for Semantic Scholar behavior changes"
    - "KG capability or smoke output for ARIA config changes"
  applies_to:
    - ".agents/external/litkg-rs/**"
    - ".configs/litkg.toml"
    - ".agents/kg/**"
    - ".agents/skills/semantic-scholar-litkg/**"
  triggers:
    - "litkg-rs implementation"
    - "Semantic Scholar"
    - "KG config"
    - "Neo4j export"
  must_read:
    - "AGENTS.md"
    - ".agents/references/litkg_quick_reference.md"
    - ".agents/external/litkg-rs/AGENTS.md"
    - ".agents/skills/semantic-scholar-litkg/references/integration-spec.md"
  canonical_sources:
    - ".agents/external/litkg-rs/AGENTS.md"
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
    - "cd .agents/external/litkg-rs && cargo fmt --all --check"
    - "cd .agents/external/litkg-rs && cargo test"
    - "make check-agent-memory when ARIA guidance changes"
---

# Semantic Scholar litkg

Use this skill when changing or operating the KG tooling itself.

## Read First

1. `AGENTS.md` and `.agents/references/litkg_quick_reference.md`
2. `.agents/external/litkg-rs/AGENTS.md`
3. `.agents/external/litkg-rs/README.md`, `docs/architecture.md`, and
   `docs/kg-stack.md` when toolkit code changes
4. `references/integration-spec.md` for source coverage, TOML shape, backend
   selection, Semantic Scholar behavior, or adapter contracts

## Rules

- Keep repo-independent implementation in `.agents/external/litkg-rs`.
- Keep ARIA-NBV paths, authority tiers, and source-selection assumptions in
  `.configs/litkg.toml`, ARIA docs, or skills.
- Prefer existing litkg-rs adapters and external libraries before adding new
  parsers or schemas.
- Treat graphify/JSONL as durable generated artifacts, Neo4j export as optional
  traversal/runtime data, Graphiti as optional temporal ingestion,
  CodeGraphContext/code-index as code-symbol enrichment, and MemPalace as a
  separate episodic memory-mining path.
- Do not create a second agent retrieval workflow when `kg-*` or
  `context-pack` can express the need.
- Do not reintroduce a `kg-query` alias until a real synthesis layer exists;
  use `kg-search` for retrieval and `kg-route` for context packs.
- Generated KG artifacts remain internal unless explicitly curated into public
  docs.

## Workflow

1. Localize the capability to literature metadata, local code symbols, repo
   docs, agent memory, external docs, optional HTTPS pages, or backend export.
2. Inspect litkg-rs for an existing module or adapter boundary before adding a
   new crate, command, or schema field.
3. Update litkg-rs first for repo-independent behavior; add ARIA config/docs
   only after the toolkit surface exists.
4. For Semantic Scholar request fields, pagination, headers, or rate limits,
   verify current official API docs before changing behavior.
5. Preserve `.agents/issues.toml` and `.agents/todos.toml` `context` and
   `references` in context-pack/KG output.

## Validation

- ARIA guidance/config changes: `make kg-capabilities KG_FORMAT=json` and
  `make check-agent-memory`.
- litkg-rs toolkit edits: `cd .agents/external/litkg-rs && cargo fmt --all
  --check`, `cd .agents/external/litkg-rs && cargo test`, and the narrow
  litkg-rs smoke command for the changed capability.
- Agents DB integration: `make agents-db AGENTS_ARGS='validate'`.
