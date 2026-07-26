# ARIA-NBV Agent Guidance

Use this file as the root dispatcher. Detailed rules live in the nearest
`AGENTS.md`, `.agents/skills/`, and `.agents/references/`.

## Source Order
- Use `.agents/references/source_order.md` for current truth and conflict
  resolution.
- The active Typst thesis is the sole owner of scientific narrative and
  interpretation: research questions, priorities, interpretation, and
  calibrated claim wording. It cites the direct evidence authorities named in
  `.agents/references/source_order.md`; Quarto thesis pages are navigation only.

## Routing
- For non-trivial work, state assumptions, inspect the nearest owner, keep the
  diff request-traceable, preserve unrelated changes, and verify the touched
  surface before completion.
- Package work under `aria_nbv/`: read `aria_nbv/AGENTS.md`, then one nested
  guide only when that module contract is touched.
- Docs, bibliography, Typst, or Quarto work: read `docs/AGENTS.md`.
- Quarto, Typst, Mermaid `.mmd`, thesis prose, citation, or diagram work: use
  `aria-docs`; math notation
  must come from `docs/typst/shared`; validate with
  `tools/mermaid/scripts/aria_mermaid_lint.py`; render locally with `mmdc`
  when available and do not use online renderers unless explicitly permitted.
- Need file localization or deterministic local discovery: use `aria-nbv-context`.
- For authority-sensitive claims, follow the direct-source checklist and open
  exact bibliography, literature, thesis, and package owners.
- Vague, high-impact, or advisor-facing plans: use `plan-grill`.
- Bugs, regressions, suspicious metrics, or failing checks: use the selected
  diagnostic workflow after localizing the owning source and reproducer.
- Backlog or memory changes: use the `agents-db` skill.
- Cleanup, pruning, or simplification: use the selected generic codebase-design
  workflow under this repository's ownership and verification rules.
- LRZ AI Systems, Slurm, DSS, Pyxis, or remote compute work: use `lrz-ai-systems`.

## Non-Negotiables
- Do not use `git restore` or `git reset --hard` unless explicitly requested.
- Assume the worktree can be dirty; never revert unrelated user or agent
  changes.
- Treat `omx uninstall --scope project --keep-config --purge` as destructive.
  Execute it only when explicitly authorized and only through the pinned native
  acceptance fixture in a disposable clone with isolated HOME/Codex/XDG/temp
  state, a verified external seed, and a sentinel outside the enclosing
  temporary parent. The fixture must prove complete `.omx` removal and restore
  every registered payload at its exact pre-purge SHA-256.
- Keep public docs aligned with current thesis direction, current code, and
  historical evidence only when cited.
- Debriefs, transcripts, OMX artifacts, Graphify output, internal agent memory,
  and generated context are supporting records, not primary evidence
  authorities or public documentation surfaces.
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
- Current scientific direction: update the active Typst thesis; Quarto thesis
  pages only index or reference it. Implementation truth stays with code, tests,
  and nearest package guidance.
- Actionable work: update `.agents/issues.toml`, `.agents/todos.toml`, or
  `.agents/refactors.toml` through `agents-db`.
- Public scientific narrative: update the active Typst thesis; keep Quarto as
  navigation/reference.

## Commands
- Python: `aria_nbv/.venv/bin/python`
- Package format/lint: `ruff format <file>` and `ruff check <file>`
- Package tests: `cd aria_nbv && uv run pytest <path>`
- Contract inspection: `make context-contracts`
- Source outlines: `make context-qmd-outline`, `make context-typst-outline`,
  and `make context-typst-includes`
- Agents DB: `make agents-db`; memory check: `make check-agent-memory`
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
  claims require `.agents/references/direct_source_claim_checklist.md`.

## Debriefs
- Non-trivial work leaves a debrief under `.agents/memory/history/YYYY/MM/`.
- Native debriefs must follow `.agents/references/agent_memory_templates.md` and
  include `canonical_updates_needed` even when the list is empty; non-empty
  entries name the exact package, docs, reference, or backlog owners updated.
- Debriefs and transcripts preserve supporting context; direct sources own the
  behavior, measurements, validity, and literature claims they summarize.
- Legacy `.codex/*.md` notes were migrated. Do not recreate `.codex` as a notes
  bucket; only checked-in `.codex/*.example.*` templates are allowed, except
  the intentionally vendored `.codex/skills/graphify/**` project skill.

## Graphify

Graphify is source-derived navigation; exact code, active Typst sources,
bibliography entries, and external papers remain authoritative. The adapter
admits three explicit source families from `.graphify.toml` and converts only
explicit Typst, TeX, and Bib structure into input for the pinned upstream AST.

Rules:
- For architecture, codebase, file-relationship, or project-content questions,
  run `make graphify-freshness`, then use native `graphify query`, `path`,
  `explain`, or `tree`. Fall back to exact sources when the graph is stale or
  insufficient.
- Refresh only through `make graphify-refresh` or
  `python scripts/graphify_adapter.py sync`; direct root `graphify update .` is
  not canonical because extraction uses the adapter's temporary corpus.
- Native Graphify owns graph schema, reports, traversal, clustering, merge, and
  on-demand ignored HTML. No wiki is maintained.
- A corpus-changing source commit `S` requires an immediate graph-only child
  `G`; `make graphify-ci` validates the final tree and authoring history.
