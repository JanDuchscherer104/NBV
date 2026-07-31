# ARIA-NBV Agent Guidance

Use this file as the root dispatcher. Detailed rules live in the nearest
`AGENTS.md`, `.agents/skills/`, and `.agents/references/`.

## Source Order
- Use `.agents/references/source_order.md` for current truth and conflict
  resolution.
- Current thesis direction is owned by thesis roadmap/questions plus canonical
  memory. The seminar paper is historical implemented evidence, not current
  thesis priority.

## Routing
- Non-trivial coding, docs, scaffold, research, or memory edits: apply
  `agent-behavior` first.
- Package work under `aria_nbv/`: read `aria_nbv/AGENTS.md`, then one nested
  guide only when that module contract is touched.
- Docs, bibliography, Typst, or Quarto work: read `docs/AGENTS.md`.
- Mermaid `.mmd` or thesis diagram work: use `aria-nbv-mermaid`; math notation
	must come from `docs/typst/shared`; validate with
	`tools/mermaid/scripts/aria_mermaid_lint.py`; render locally with `mmdc`
	through `tools/mermaid/scripts/render_mermaid.sh` and do not use online
	renderers unless explicitly permitted.
- Need file localization or deterministic local discovery: use `aria-nbv-context`.
- Vague, high-impact, or advisor-facing plans: use `aria-grill`. Repository
  policy routes implicit ARIA use of optional architecture, interface-design,
  committed Mermaid, and interactive-visualization capabilities through Aria
  Grill; explicit user invocation overrides that route.
- PR or working-tree review: use `code-review-aria-nbv`; actionable P0--P2
  findings on a PR are published and resolved as GitHub review threads, while
  local-only reviews report the same line-referenced findings locally.
- Bugs, regressions, suspicious metrics, or failing docs/data checks: use
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
- Externally installed skills are optional capabilities, not ARIA-NBV truth
  owners. Translate any proposed output path through the repository source order
  before creating a new tracked surface.
- OMX remains optional operator orchestration; use its upstream help only when
  a task explicitly asks for operator orchestration. Do not make it required
  for normal repo work.
- Optional OMX, MCP, graph, memory, and autoresearch tools produce evidence or
  proposals, not repo-owned truth. Apply durable changes only through the
  owning source, package guidance, docs, or Agents DB surface.
- Optional MemPalace use comes from the official upstream Codex plugin, uses
  the `aria-nbv` wing, and follows the reviewed corpus boundary in
  `.agents/references/human_owner_intent.md`; the repository owns no wrapper.

## Instruction Capture
- Repo invariant: update this file or the nearest nested `AGENTS.md`.
- Repeatable workflow: update or add a compact `.agents/skills/*/SKILL.md`.
- Human-owner preference: update `.agents/references/human_owner_intent.md`.
- Current truth: update `.agents/memory/state/`.
- Actionable work: update `.agents/issues.toml`, `.agents/todos.toml`, or
  `.agents/refactors.toml` through `agents-db`.
- Public narrative: update Quarto or Typst docs.
- Angle-bracket instruction capture is owned by `agent-behavior`; apply its
  current-user-message eligibility rule and route valid captures here.

## Commands
- Python: `aria_nbv/.venv/bin/python`
- Package format/lint: `ruff format <file>` and `ruff check <file>`
- Package tests: `cd aria_nbv && uv run pytest <path>`
- Context refresh: `make context`; contract index: `make context-contracts`
- Agents DB: `make agents-db`; memory check: `make check-agent-memory`
- Surface checks: use the nearest package guide or skill, then the narrowest
  test, render, or command that proves the changed contract.

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
  claims require direct inspection of the cited primary source and exact local
  implementation or measurement evidence where applicable.

## Debriefs
- Non-trivial work leaves a debrief under `.agents/memory/history/YYYY/MM/`.
- Native debriefs must follow `.agents/memory/README.md` and
  include `canonical_updates_needed` even when the list is empty.
- Legacy `.codex/*.md` notes were migrated. Do not recreate `.codex` as a notes
  bucket; only checked-in `.codex/*.example.*` templates are allowed.

## Graphify

Graphify is an optional derived navigation aid, never a knowledge owner or a
prerequisite for repository work. Start from exact code, Typst, bibliography,
and literature sources. When `graphify-input/` and a local graph exist, qualify
navigation results with the projection's `source_revision`, and verify every
consequential link or claim in its owning source. If Graphify is absent or its
revision does not match the task, continue with exact-source discovery.

Build the ignored evidence projection with
`python3 scripts/build_graphify_projection.py`, setting
`--output graphify-input` and `--aria-code-ref <full-sha-or-release-tag>`.
The repository supplies all project-side setup. After merge, an operator needs
only a normal user-installed upstream Graphify tool/skill (install it if
absent) and an authenticated Codex session via `codex login`, then invokes
`$graphify` on the corpus selected by `.graphifyignore`. The unmodified upstream
skill may dispatch authenticated Codex subagents for semantic extraction. Never
export a ChatGPT/Codex token, reuse it as `OPENAI_API_KEY`, add repository
secrets, or introduce a Graphify fork, repository-owned package import, or
local lifecycle.
