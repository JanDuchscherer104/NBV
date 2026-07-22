# Alignment Tools Contract

Use this contract when work crosses repo guidance, optional operator tooling,
KG/retrieval, graph backends, memory, MCP servers, or external autoresearch
harnesses.

## Ownership Rule

Optional tools produce evidence, proposals, diagnostics, or generated artifacts.
They do not own ARIA-NBV truth. Durable decisions must land in the owner
surface for the kind of information being changed.

## Owner Surfaces

- Repo policy and routing: root or nearest nested `AGENTS.md`.
- Current truth and conflict resolution: `.agents/references/source_order.md`
  plus the exact thesis, package, test, docstring, reference, or backlog owner.
- Repeatable workflows: compact `.agents/skills/*/SKILL.md` files.
- Actionable work: `.agents/issues.toml`, `.agents/todos.toml`, or
  `.agents/refactors.toml` through `agents-db`.
- Public narrative: Quarto or Typst docs.
- Verification gates: `.agents/references/verification_matrix.md`.
- KG/backend operating details: `.agents/external/litkg-rs/docs/` and
  `.configs/litkg.toml`.
- OMX operator usage: `.agents/references/omx_quick_reference.md`.

## Tool Boundaries

- OMX orchestrates optional workflows and gates. It must remain replaceable and
  must not become the repo source of truth.
- litkg retrieval, routing, and claim checks are advisory evidence channels.
  Claim checks need human or task-specific verification before they become
  thesis, roadmap, or implementation truth.
- Graph artifacts, Neo4j exports, Graphiti, MemPalace, and similar systems are
  derived or optional memory/query surfaces unless a task explicitly promotes a
  specific artifact through the owner surface above.
- External autoresearch or MCP harnesses must integrate through an adapter
  boundary that writes proposed artifacts and evidence, not direct policy,
  roadmap, source-owner, or backlog mutations.

## OMX Consumption Map

OMX workflows consume ARIA-NBV guidance as sidecar context and evidence:

- `$analyze`: use root or nearest `AGENTS.md`, `.agents/references/source_order.md`,
  and the narrowest domain skill to separate evidence, inference, and unknowns.
- `$prometheus-strict` / `$ralplan`: use `plan-grill`, thesis roadmap/questions,
  the nearest implementation owner, and this contract to set
  scope, owner surfaces, non-goals, and verification before execution.
- `$ultragoal`: use the active ARIA skill metadata for tool loops, must-read
  surfaces, evidence requirements, and the command index in
  `.agents/references/verification_matrix.md`.
- `$code-review`: use the ARIA code-review skill plus nearest owner guidance;
  findings that need reproduction hand off to `diagnose-aria` or the relevant
  domain sidecar.
- `$ultraqa`: use `diagnose-aria`, domain sidecars, Streamlit/Rerun/offline
  checks, and KG/docs commands as evidence producers. Results become durable
  only through the owning code, docs, reference, or backlog surface.
- Optional browser, MCP, KG, graph, memory, and autoresearch tools provide
  runtime evidence or proposals. They are never mandatory repo dependencies
  unless a later owner-surface change explicitly promotes them.

## Autoresearch Adapter

Autoresearch is a replaceable harness boundary, not a package commitment.
Maintained external projects such as `karpathy/autoresearch`, LangGraph,
Open Deep Research, LlamaIndex, or AI-Scientist variants may inform the adapter,
but ARIA-NBV owns only the typed interface and evidence contract.

Adapter outputs are proposals: config diffs, controlled command transcripts,
metrics, checkpoint evaluations, visual evidence, reports, and optional
agents-DB or source-owner update suggestions. A normal repo lane must apply any
durable change through the owner surfaces above.

Adapter implementations must be able to run with a bounded allowlist of typed
tools instead of raw shell by default. Typical tools are config patching,
experiment launch, checkpoint evaluation, oracle/cache smoke checks,
literature/context retrieval, and report writing.

## Visual And UI Gates

Visual interpretation gates are evidence producers. They may inspect Streamlit,
Rerun, screenshots, exported `.rrd` files, metrics tables, or generated reports,
but the gate result is advisory until the owning code, docs, reference, or backlog
surface is updated.

Wave-one visual work is contract-only: define expected artifacts, ownership, and
handoff points before adding new screenshot automation or Rerun inspection code.

## Update Rule

When a tool reveals a needed change, update the owner surface directly and keep
the tool output as evidence. Do not duplicate the same definition in multiple
surfaces to make an integration convenient.
