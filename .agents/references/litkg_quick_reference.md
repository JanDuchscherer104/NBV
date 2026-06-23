# litkg Agent Quick Reference

Use this reference for ARIA-NBV KG-backed retrieval and claim checks. LitKG is
a probationary source-backed router, claim checker, and research-memory layer,
not the default brain for every agent task. Use `semantic-scholar-litkg` only
when changing litkg-rs, KG source coverage, or KG operation itself.

## Probation Lane

Use LitKG when work crosses source families or needs source-backed arbitration:

- thesis writing and advisor-facing claims;
- literature synthesis and research framing;
- active backlog lookup and consolidation proposals;
- scaffold cleanup that needs stale-reference or duplicate-owner discovery;
- Rerun, plotting, or coding tasks that need current visual/data contracts
  across skills, docs, code, and memory.

Do not require LitKG for localized one-file coding edits, narrow test fixes, or
obvious file discovery. Start those with the nearest `AGENTS.md`, owning skill,
`aria-nbv-context`, and targeted `rg`/file reads. If LitKG returns broad or
generic context, treat it as advisory and inspect the concrete owner directly.

## Default Commands

- Route a broad task:
  `make kg-route KG_TASK="<task>"`
- Search indexed context quickly:
  `make kg-search KG_QUERY="<terms>"`
- Limit search to exact graph modalities:
  `make kg-search KG_QUERY="<terms>" KG_MODALITY="literature,docs"`
- Claim-check advisor-facing or thesis claims:
  `make kg-claim-check KG_CLAIM="<claim>"`
- Propose memory/backlog consolidation:
  `make kg-consolidate`
- Inspect source/backend readiness:
  `make kg-capabilities KG_FORMAT=json`

When connecting thesis prose to implementation code, use `kg-search` or
`kg-route` to locate likely source/code relationships, inspect the cited owners,
then encode the selected Typst link with
`.agents/references/thesis_code_links.md`: `#gh` for final-worthy pinned
anchors, `#gh-wip` and `#gh-symbol` for removable draft/agent navigation.

## Output Modes

`kg-route`, `kg-search`, and `kg-claim-check` print a **compact ~12-line
summary by default** (top sources, active backlog ids, risk flags, suggested
next action, first required read). The compact output is the agent-readable
fast path; reach for it first.

Escape hatches when more detail is needed:

- `KG_VERBOSE=1` -> legacy full payload (passes `--full` to context-pack;
  re-emits `evidence_spans`, `backend_status`, `action_plan`, `assumptions`,
  `profile`, `budget_tokens`, `truncated`, `relevant_papers`, and the legacy
  aliases `missing_leaves` / `missing_context_leaves`). Use only when
  triaging or back-filling a tool that depends on the legacy shape.
- `KG_FORMAT=json` -> lean JSON (the default agent-facing shape; suitable
  for `jq` pipelines and hooks). Bulk and legacy fields are omitted.

Examples:

```bash
# Compact default (fastest to read):
make kg-route KG_TASK="harden bounded oracle-RRI lookahead"

# Full text payload when triaging:
make kg-route KG_TASK="..." KG_VERBOSE=1

# Raw JSON for piping:
make kg-route KG_TASK="..." KG_FORMAT=json | jq '.top_sources[].path'
```

The compact filters live under `scripts/kg/compact_*.jq`; edit those if the
summary shape needs to change.

## Expected Context-Pack Fields

Agent-facing context packs expose both the legacy fields and the newer compact
routing fields. Treat the compact fields as the first read, then open cited
spans before changing code or docs.

- `verb`
- `task_summary`
- `assumptions`
- `top_sources` with path, title, role, authority, freshness, source span,
  source type, scores, and why relevant
- `required_reads` derived from the highest-ranked deduped source paths
- `active_backlog`, `active_issues`, and `active_todos` with issue/todo id,
  priority, context, references, acceptance, and verification when present
- `risk_flags`
- `suggested_next_action` as an object with `summary`, optional `skill`,
  optional `command`, and `why`
- `verification_commands`
- `missing_context` (canonical name; the legacy aliases `missing_leaves`
  and `missing_context_leaves` are now emitted only under `KG_VERBOSE=1`)

The following legacy fields are emitted only under `KG_VERBOSE=1`
(equivalent to passing `--full` to `context-pack`): `profile`,
`budget_tokens`, `truncated`, `assumptions`, `action_plan`,
`evidence_spans`, `relevant_papers`, `missing_leaves`,
`missing_context_leaves`, and `backend_status`. The default lean JSON
payload for a trivial smoke task is ~42 KB (vs ~230 KB legacy).

Authority is configured in `.configs/litkg.toml`. Current canonical memory,
current thesis QMDs, thesis proposal Typst, and implementation code should rank
above historical seminar paper evidence and episodic history for comparable
matches.

Transcript-derived context follows a trust ladder: raw agent messages are
private low-trust search material, raw user messages are higher-signal but not
canonical, and distilled user intent plus later agent-grounded agreement is a
high-trust candidate memory. Only checked-in canonical memory, backlog, docs,
and code become current truth.

## Advanced Commands

- Emit a full JSON context pack:
  `make kg-route KG_TASK="<task>" KG_FORMAT=json`
- Use a specific context-pack profile directly:
  `.agents/external/litkg-rs/target/debug/litkg-cli context-pack --config .configs/litkg.toml --repo-root . --task "<task>" --profile thesis-coding --format json`
- Inspect a broad source/backlog query:
  `make kg-search KG_QUERY="<terms>" KG_FORMAT=json KG_LIMIT=10`
- Search only literature/paper nodes:
  `make kg-search KG_QUERY="<terms>" KG_MODALITY="literature"`

Question-answer synthesis is deferred until there is a real synthesis layer.
Use `kg-search` for fast retrieval and `kg-route` when an agent needs a context
pack with source ranking, backlog, risks, and verification.

## Typed-Query Escape Hatch (neo4j-cypher MCP)

`kg-search` and `kg-route` cover routine retrieval but cannot express
multi-hop joins or filtered vector lookups (e.g. *"papers that cite Hestia
AND have a section discussing hierarchical planning"*). For those, activate
the `litkg-cypher` MCP profile and call raw Cypher.

**One-time install** (gateway-side):

```bash
make kg-mcp-install
```

The target prints the exact `mcp-add` / `mcp-config-set` /
`mcp-create-profile` commands to run from any agent session that has the
`MCP_DOCKER` gateway tools loaded. The default config locks the server to
read-only (`read_only=true`); flip with
`mcp-config-set neo4j-cypher read_only=false` only when curating.

**Per-session activation:**

```text
mcp-activate-profile litkg-cypher
```

After activation the session exposes:

- `read_neo4j_cypher(query, params)` — arbitrary read-only Cypher (30 s
  timeout, response token cap).
- `get_neo4j_schema(sample_param=1000)` — live schema. Requires APOC
  (already loaded in the repo's Neo4j docker via `NEO4J_PLUGINS='["apoc"]'`).
- `write_neo4j_cypher(query, params)` — only if `read_only=false`.

**Live schema highlights** (call `get_neo4j_schema` for the full thing):

- Nodes: `Paper`, `PaperSection`, `Document`, `DocSection`, `ProjectMemory`,
  `MemorySurface`, `GeneratedContext`, `DataContract`, `AgentBacklogIssue`,
  `AgentBacklogTodo`, `Function`, `Module`, `Class`, `File`,
  `KGEmbeddingNode` (marker label on anything embedded).
- Vector index: `kg_embedding_index_2560` over `KGEmbeddingNode.kg_embedding`
  (HNSW, cosine, dim 2560 from `qwen3-embedding:4b`).
- Common edges: `(:Paper)-[:HAS_SECTION]->(:PaperSection)`,
  `(:Paper)-[:CITES]->(:Citation)`,
  `(:Function)-[:CALLS]->(:Function)`,
  `(:File)-[:CONTAINS]->(:Class|:Function|:Module)`.

**Example queries:**

```cypher
// 1. Sections of Hestia matching a topic.
MATCH (p:Paper {paper_id: "hestia-lu2026"})-[:HAS_SECTION]->(s:PaperSection)
WHERE toLower(s.title) CONTAINS "hierarchical"
RETURN p.paper_id, s.title, s.line_start, s.line_end;

// 2. Vector search with kind filter (hybrid retrieval beyond kg-search).
//    The caller supplies the $qvec parameter from an Ollama embedding call.
CALL db.index.vector.queryNodes('kg_embedding_index_2560', 10, $qvec)
  YIELD node, score
MATCH (node:Paper)
RETURN node.paper_id, node.title, score ORDER BY score DESC LIMIT 5;

// 3. Count code symbols per module under aria_nbv.pose_generation.
MATCH (m:Module)
WHERE m.qualified_name STARTS WITH "aria_nbv.pose_generation"
RETURN m.qualified_name, m.function_count, m.class_count
ORDER BY m.qualified_name;
```

**When NOT to use:** routine retrieval (use `kg-search`), claim verification
(use `kg-claim-check`), routing a high-level task (use `kg-route`). The MCP
escape hatch is for typed queries the wrappers don't cover.

## Health Check

`make kg-doctor` runs nine probes and prints a green/yellow/red table:

| Check | Red when |
|---|---|
| `ollama_reachable` | tunnel down at `127.0.0.1:11434` |
| `ollama_embedding_smoke` | round-trip embedding fails or dim != expected |
| `neo4j_http` | Neo4j HTTP API unreachable at `7474` |
| `neo4j_apoc` | APOC procedure count < 100 (missing plugin) |
| `neo4j_vector_index` | `kg_embedding_index_2560` missing or non-ONLINE |
| `embedding_coverage` | embedded-node count < 30% of bundle rows |
| `refresh_stamp_age` | last refresh > 24h ago (yellow, not red) |
| `refresh_lock_stale` | lock file points at a non-running PID |
| `kg_search_smoke` | lexical `kg-search RRI` returns 0 hits |

Default: text table, exits non-zero on red. JSON via
`KG_DOCTOR_ARGS='--format json'` for downstream tools.

Hook integration: `scripts/kg/auto_refresh.sh` runs `--soft --format json`
at the end of each refresh dispatch and appends the JSON snapshot to
`.agents/kg/.refresh.log`. `--soft` prevents red from breaking the
session.

Common red recoveries:
- Ollama down → bring up the SSH reverse tunnel (`ssh -N -R 11434:127.0.0.1:11434 ubuntu`).
- Neo4j down → `make kg-up`.
- Stale lock → `rm .agents/kg/.refresh.lock`.
- Coverage low → `make kg-load-bundle && make kg-enrich`.

## Fallback

If litkg is stale, unavailable, or returns broad/noisy context:

1. Use `aria-nbv-context` and targeted `rg`/file reads for local discovery.
2. Continue localized one-file or one-surface work when enough evidence exists.
3. Record or amend KG/backlog debt only when the litkg failure blocks the task or
   exposes durable scaffold drift.

Optional backend gaps such as Context7, Graphiti, Semantic Scholar enrichment,
OpenAI docs leaves, CodeGraphContext, or stale generated exports are warnings by
default. They become blockers only when the task explicitly requires that leaf
or no concrete local/canonical source can answer the request.

## Mandatory Claim Checks

Run `kg-claim-check` for advisor-facing proposal claims, thesis roadmap or
research-question claims, and literature-synthesis conclusions. Do not require
it for small internal wording, navigation, or localized implementation edits.
