# ARIA-NBV Agent Guidance

Use this file as the root dispatcher. Detailed rules live in the nearest
`AGENTS.md`, `.agents/skills/`, and `.agents/references/`.

## Source Order
- Use `.agents/references/source_order.md` for current truth and conflict
  resolution.
- Current thesis direction is owned by the thesis roadmap/questions and active
  Typst thesis. The seminar paper is historical implemented evidence, not
  current thesis priority.

## Routing
- Non-trivial coding, docs, scaffold, research, or memory edits: apply
  `agent-behavior` first.
- Package work under `aria_nbv/`: read `aria_nbv/AGENTS.md`, then one nested
  guide only when that module contract is touched.
- Docs, bibliography, Typst, or Quarto work: read `docs/AGENTS.md`.
- Mermaid `.mmd` or thesis diagram work: use `aria-nbv-mermaid`; math notation
  must come from `docs/typst/shared`; validate with
  `tools/mermaid/scripts/aria_mermaid_lint.py`; render locally with `mmdc`
  when available and do not use online renderers unless explicitly permitted.
- Need file localization or deterministic local discovery: use `aria-nbv-context`.
- Need KG-backed retrieval, source-backed routing, claim checks, or
  consolidation: use `aria-litkg-memory`.
- Need to modify litkg-rs, KG source coverage, KG config, or KG operation:
  use `semantic-scholar-litkg`; keep repo-independent implementation in
  `.agents/external/litkg-rs`.
- Vague, high-impact, or advisor-facing plans: use `plan-grill`.
- Bugs, regressions, suspicious metrics, or failing docs/data/KG checks: use
  `diagnose-aria`.
- Backlog or memory changes: use the `agents-db` skill.
- Cleanup, pruning, or simplification: use the `simplification` skill.
- LRZ AI Systems, Slurm, DSS, Pyxis, or remote compute work: use `lrz-ai-systems`.

## Non-Negotiables
- Do not use `git restore` or `git reset --hard` unless explicitly requested.
- Assume the worktree can be dirty; never revert unrelated user or agent
  changes.
- Keep public docs aligned with current thesis direction, current code, and
  historical evidence only when cited.
- Internal agent memory, generated context, and OMX runtime state are not public
  documentation surfaces.
- Do not treat V0 GT actor-visible target runs as main V1 performance.
- Invalidity is a hard mask/reason contract, not low RRI.
- Generic Gymnasium/SB3 or external online-simulator work is stretch or M6
  bridge work unless the task explicitly targets that gate. Online discrete
  `Q_H` over the existing finite-candidate ASE mesh/oracle loop is the
  advisor-facing RQ5 bridge after offline `Q_H` evidence is stable.

## Optional Operator Tools
- OMX remains optional operator orchestration. Use
  `.agents/references/omx_quick_reference.md` only when the task explicitly
  asks for OMX or operator orchestration; do not make OMX required for normal
  repo work.
- Use `.agents/references/alignment_tools_contract.md` when work crosses OMX,
  MCP, KG, memory, graph, or autoresearch adapter boundaries; optional tools
  produce evidence and proposals, not repo-owned truth.

## Instruction Capture
- Repo invariant: update this file or the nearest nested `AGENTS.md`.
- Repeatable workflow: update or add a compact `.agents/skills/*/SKILL.md`.
- Human-owner preference: update `.agents/references/human_owner_intent.md`.
- Current scientific direction: update the thesis roadmap/questions or active
  Typst thesis; implementation truth stays with code, tests, and nearest package
  guidance.
- Actionable work: update `.agents/issues.toml`, `.agents/todos.toml`, or
  `.agents/refactors.toml` through `agents-db`.
- Public narrative: update Quarto or Typst docs.

## Commands
- Python: `aria_nbv/.venv/bin/python`
- Package format/lint: `ruff format <file>` and `ruff check <file>`
- Package tests: `cd aria_nbv && uv run pytest <path>`
- Context refresh: `make context`; contract index: `make context-contracts`
- Agents DB: `make agents-db`; memory check: `make check-agent-memory`
- litkg commands: see `.agents/references/litkg_quick_reference.md`.
- Surface checks: see `.agents/references/verification_matrix.md`.

## Verification
- Repo guidance, canonical state, debriefs, or skills: `make check-agent-memory`
  and validate changed skills with the local skill validator when available.
- Agents DB edits: `make agents-db AGENTS_ARGS='validate'` and `make agents-db`.
- Python/package edits: format, lint, and targeted pytest for the touched
  surface.
- Data-handling, RRI, or VIN contract edits: follow the nearest nested guide and
  update docs/memory when behavior changes.
- Docs edits: render the touched Quarto or Typst surface when non-trivial.
- Advisor-facing proposal, roadmap, research-question, or literature-synthesis
  claims require `make kg-claim-check KG_CLAIM="..."`.

## Debriefs
- Non-trivial work leaves a debrief under `.agents/memory/history/YYYY/MM/`.
- Native debriefs must follow `.agents/references/agent_memory_templates.md` and
  include `canonical_updates_needed` even when the list is empty; non-empty
  entries name the exact package, docs, reference, or backlog owners updated.
- Legacy `.codex/*.md` notes were migrated. Do not recreate `.codex` as a notes
  bucket; only checked-in `.codex/*.example.*` templates are allowed, except
  the intentionally vendored `.codex/skills/graphify/**` project skill.

## Graphify

Graphify is the default ARIA-NBV navigation graph when
`graphify-out/graph.json` exists. The graph is generated local state and should
remain untracked unless a later artifact or LFS policy changes that.

The repo-owned `.graphifyignore` defines the root corpus for `graphify .`:
package code, docs, and important `.agents/` references/memory/backlog. It
excludes runtime state, external repos, generated docs/sites, caches, large
media, `graphify-out/`, `.codex/`, `.configs/`, root `scripts/`, `AGENTS.md`,
`.agents/skills/`, `aria_nbv/scripts/`, and `aria_nbv/tests/`.

Rules:
- For architecture, codebase, file-relationship, or project-content questions,
  first run `python3 scripts/check_graphify_freshness.py --quiet`. When it
  succeeds, use `graphify query "<question>"`; otherwise fall back to the
  owning source files until the graph is refreshed. Use
  `graphify path "<A>" "<B>"` for relationships and
  `graphify explain "<concept>"` for focused concepts.
- Dirty `graphify-out/` files are expected after hooks or incremental updates;
  dirty graph files are not a reason to skip Graphify. Only skip Graphify if
  the task is about stale or incorrect graph output, or the user explicitly says
  not to use it.
- If `graphify-out/wiki/index.md` exists, use it for broad navigation before
  raw source browsing. Read `graphify-out/GRAPH_REPORT.md` for broad
  architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `python3 scripts/graphify_refresh.py` with the
  changed paths in `GRAPHIFY_CHANGED`, or run `graphify update .` followed by
  the freshness check. Documentation, paper, and diagram changes set
  `graphify-out/needs_update`; refresh them with the Graphify extraction
  workflow, whose completion records the current policy digest, before treating
  semantic links as current.
- `litkg-rs` remains the source-authority layer for `kg-search`,
  `kg-route`, `kg-claim-check`, Semantic Scholar/literature enrichment, and
  thesis/advisor evidence. Use Graphify for navigation first; use litkg for
  authority-sensitive claims.
