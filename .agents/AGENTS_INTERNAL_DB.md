# ARIA-NBV Internal Agent DB

This file tracks the active engineering and research backlog for ARIA-NBV.

## Core Backlog

- **Issues**: [issues.toml](./issues.toml) - High-priority bugs and scaffold leaks.
- **TODOs**: [todos.toml](./todos.toml) - Immediate and research milestones.
- **Refactors**: [refactors.toml](./refactors.toml) - Structural and hygiene improvements.
- **Resolved**: [resolved.toml](./resolved.toml) - Archive of completed work.

## Relation to Memory

The agents DB holds **active maintenance debt**; it does not own current truth
or replace a source document. Extracted proposal, transcript, or review
requirements become agents-DB work when actionable. Accepted durable content
goes to the exact Typst, Python/configuration/test, setup, or guidance owner;
otherwise keep it in a dated memory debrief.

Active issues and todos must carry compact prose context plus structured
`references` pointers. Use `repo:` for internal files, `bib:` for papers in
`docs/references.bib`, durable identifiers such as `arxiv:`/`doi:`/`s2:`,
external docs as `url:`, and Context7 library docs as `context7:`. This keeps
local backlog records auditable and machine-readable.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, the completion hook maintains the graph automatically;
  do not ask agents to run a separate Graphify repair command.

### ARIA-NBV mandatory reconciliation

Graphify is mandatory navigation in Codex worktrees, while exact repository
sources remain authoritative. Setup and completion hooks own eligibility,
projection maintenance, and admission. Query only an admitted `fresh` or
bounded `usable-stale` artifact; repair or reinitialize `unusable` artifacts
through the setup owner before eligible work. If automatic maintenance cannot
restore usability, report the degraded state and use exact sources rather than
treating Graphify as optional.

## Priority Pillars

1. **Scaffold Hygiene**: Fix stale skills and dense root guidance.
2. **Docs Discipline**: Triage `docs/` tree by role.
3. **Research Core**: Freeze M1 contracts, build entity-aware target RRI,
   observed-only target selection, bounded oracle rollouts, and the
   finite-candidate candidate-query Transformer Q_H. Gym-style online
   simulators are stretch or bridge work after the ASE rollout/Q_H path is
   stable.
4. **Agentic Lifecycle**: Port PR and issue lifecycle workflows.

## Current Rollout/Q_H Critical Path

For multi-step offline sample generation, override generic high-priority sorting
with this dependency order until the rollout/Q_H path is producing trusted
samples:

1. `issue-007` / `todo-007` plus `issue-031`: M1 data/cache/oracle contract gate and homogeneous RRI eval-stream lineage.
2. `issue-021` / `todo-031`: invalidity as hard masks and reason codes.
3. `issue-020` / `todo-005`, `todo-029`, `todo-053`, `todo-028`: target RRI,
   observed target selection, V1 OBS-SEL / PRED-Q / GT-EVAL, and target-aware
   candidate mixture provenance.
4. `issue-018` / `todo-058`, `todo-026`: rollout retention/schema and bounded
   oracle lookahead evidence.
5. `issue-022` / `todo-033`: LRZ deterministic sharding, resumable writes, and
   campaign status/indexing.
6. `issue-019` / `todo-027`: stochastic rollout support, with
   temperature-softmax before first Q_H data and Gumbel as later evidence.
7. `issue-028` / `todo-078`, `todo-052`: chunked Q_H training views and the
   candidate-query Transformer baseline.
8. `issue-013` / `todo-037`: evidence report once rollout and Q_H smoke outputs
   exist.

Advisor/docs, governance/scaffold, KG, GitHub mirroring, simulator, Gym, and
continuous-control work stays parallel or deferred unless it blocks this path.
