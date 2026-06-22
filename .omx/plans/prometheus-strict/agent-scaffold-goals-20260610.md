# Prometheus Strict Plan: ARIA-NBV Agent Scaffold Goals

Date: 2026-06-10

## Target Result

Persist the complete ARIA-NBV agent-scaffold rework as a durable plan plus
compact agents-db work items, with a first execution wave that strengthens the
operator onboarding spine and specifies a replaceable autoresearch v0 adapter.

## Goals Inventory

- Keep `/home/jd/.codex/AGENTS.md` pointer-only for ARIA-NBV. The repo owns
  ARIA policy, routing, and validation.
- Keep OMX optional. OMX may orchestrate interviews, plans, teams, gates, and
  QA loops, but it must not become required for normal repository work.
- Preserve strict single ownership:
  - repo policy and routing: root or nearest `AGENTS.md`
  - current truth and conflict resolution: `.agents/references/source_order.md`
    and `.agents/memory/state/`
  - optional OMX, MCP, KG, memory, graph, and autoresearch boundaries:
    `.agents/references/alignment_tools_contract.md`
  - verification gates: `.agents/references/verification_matrix.md`
  - actionable work: `.agents/issues.toml`, `.agents/todos.toml`, and
    `.agents/refactors.toml` through `make agents-db`
- Add contract-only gates for code, docs, literature, CLI, Streamlit, Rerun, and
  visual interpretation loops before adding new automation code.
- Define autoresearch v0 as an adapter contract first, not a new dependency.
  External harnesses may propose configs, evidence, reports, and backlog
  changes, but they must not directly mutate policy, memory, roadmap, or active
  backlog.
- Keep litkg as an advisory source-backed router, claim checker, retrieval
  layer, and consolidation-proposal channel. Graphify, Neo4j, Graphiti,
  MemPalace, and similar tools remain derived or optional until a record
  explicitly promotes a role.
- Add deterministic validator coverage for source ownership, required alignment
  links, forbidden tracked runtime state, and pointer-only global onboarding.

## Autoresearch Adapter Contract

The first wave records the boundary and allowed artifacts only.

- Allowed inputs: task brief, source-order profile, bounded config patch,
  explicit experiment budget, allowed command list, and evidence-output root.
- Allowed tool classes: typed config patcher, controlled experiment launcher,
  checkpoint evaluator, oracle/cache smoke command, literature/context retriever,
  report writer, and proposal emitter.
- Disallowed behavior: raw shell by default, uncontrolled package installation,
  direct edits to `AGENTS.md`, `.agents/memory/state/`, agents-db TOML, public
  thesis narrative, or runtime credential files.
- Required outputs: proposed config diff, command transcript, metrics/artifact
  paths, visual evidence paths when applicable, report, and optional
  agents-db/memory proposals for a human or normal agent lane to apply.
- Safety limits: explicit budget caps, deterministic seeds where applicable,
  dry-run support for destructive or expensive actions, and stop conditions when
  evidence is missing or gates fail.

## External Shortlist

Freshness date: 2026-06-10. These are candidates behind the adapter boundary,
not repo-owned dependencies.

- `karpathy/autoresearch`: conceptual single-GPU autoresearch loop seed.
- `langchain-ai/langgraph`: orchestration candidate for typed stateful DAGs.
- `langchain-ai/open_deep_research`: literature/deep-research pattern
  candidate.
- `run-llama/llama_index`: indexing/RAG candidate.
- `sakanaai/ai-scientist` and `sakanaai/ai-scientist-v2`: research-loop
  references only unless licensing, dependency, and fit are cleared.

## Execution Plan

1. Keep this plan as the narrative scope artifact and link actionable work to
   existing agents-db records instead of creating duplicate queue sprawl.
2. Extend `refactor-016` as the scaffold ownership and DB-record-style umbrella.
3. Connect litkg/tool decisions through `issue-023`, `issue-025`, `todo-035`,
   `todo-039`, `todo-043`, `todo-068`, `todo-069`, and `todo-075`.
4. Tighten the onboarding spine in the repo-owned references and keep the
   user-global ARIA block pointer-only.
5. Add contract-only visual and autoresearch gate language to the verification
   matrix and alignment tools contract.
6. Extend deterministic scaffold validation to reject global ARIA policy drift
   and missing goal-plan references.

## Verification Matrix

| Claim | Required evidence | Owner |
| --- | --- | --- |
| Goal inventory is durable | Plan file exists under `.omx/plans/prometheus-strict/` | scaffold executor |
| Work is actionable without duplicate queue sprawl | Existing agents-db records reference this plan | scaffold executor |
| Global onboarding stays pointer-only | Exact marker-block check of `/home/jd/.codex/AGENTS.md` | scaffold executor |
| Optional tools remain replaceable | Alignment contract names adapter boundaries and owner surfaces | scaffold executor |
| Visual and Streamlit gates are contract-only | Verification matrix defines evidence contracts without new automation code | scaffold executor |
| Backlog remains valid | `make agents-db AGENTS_ARGS='validate'` and `make agents-db` | scaffold executor |
| Scaffold invariants hold | `make check-agent-memory` | scaffold executor |

## Handoff

Recommended next workflow after this persistence pass: direct execution for
small scaffold edits, `$ralph` for a single-owner implementation loop, or
`$team` only if independent lanes are split into docs/backlog/validator/tool
audit work.

## Clean-Room Credit

Inspired by OMO Prometheus (`code-yeongyu/oh-my-openagent`), reimplemented from
concept under MIT.
