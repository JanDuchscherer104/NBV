# User-Local Codex Guidance

## PRML VSLAM Worktrees

- In any `/home/jd/repos/prml-vslam*` checkout or worktree, use the local helper before Python, `uv`, `pytest`, or `make` commands:
  - interactive shell: `source ~/.local/bin/prml-vslam-worktree-env`
  - one command: `prml-vslam-worktree-env run <command>`
  - uv command: `prml-vslam-worktree-env uv <uv args...>`
- Plain `uv ...` is also user-locally wrapped at `/home/jd/.local/bin/uv` for PRML VSLAM paths. The original binary is `/home/jd/.local/bin/uv.real`; use `uv.real` only when intentionally bypassing PRML worktree defaults.
- The helper keeps tracked repo files untouched while standardizing local state:
  - current worktree source is first on `PYTHONPATH`
  - shared env is `/home/jd/repos/prml-vslam/.venv`
  - shared datasets are `/home/jd/repos/prml-vslam/.data`
  - missing worktree-local `external/vista-slam/DBoW3Py` is avoided with `UV_NO_SOURCES_PACKAGE=DBoW3Py`
  - `UV_FROZEN=1` prevents accidental `uv.lock` edits
- To bind the shared editable install to the current worktree without reinstalling dependencies, run `prml-vslam-worktree-env bind`.
- To sync dependency changes into the shared env without lockfile churn, run `prml-vslam-worktree-env sync --extra dev` from the intended worktree.
- Do not change `PROJECT_ROOT` in `src/prml_vslam/utils/path_config.py` to share local data or env state. Use the helper-managed ignored `.data` symlink and environment instead.

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
- Gymnasium/SB3/online simulator work is stretch or M6 bridge work unless the
  task explicitly targets that gate.

## Optional Operator Tools
- OMX remains optional operator orchestration. Use
  `.agents/references/omx_quick_reference.md` only when the task explicitly
  asks for OMX or operator orchestration; do not make OMX required for normal
  repo work.

## Instruction Capture
- Repo invariant: update this file or the nearest nested `AGENTS.md`.
- Repeatable workflow: update or add a compact `.agents/skills/*/SKILL.md`.
- Human-owner preference: update `.agents/references/human_owner_intent.md`.
- Current truth: update `.agents/memory/state/`.
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
  include `canonical_updates_needed` even when the list is empty.
- Legacy `.codex/*.md` notes were migrated. Do not recreate `.codex` as a notes
  bucket; only checked-in `.codex/*.example.*` templates are allowed.

<!-- OMX:RUNTIME:START -->
<session_context>
**Session:** omx-1780227758762-kfybap | 2026-05-31T11:42:43.748Z

**Explore Command Deprecated:** `omx explore` is deprecated and MUST NOT be recommended for new repository lookup work.
- `USE_OMX_EXPLORE_CMD` is compatibility-only; unset/default is disabled. Truthy values keep legacy callers working but do not make `omx explore` preferred.
- Replacement path: use normal Codex repository inspection tools/subagents; use `omx sparkshell -- <command>` only for explicit shell-native read-only evidence or `--tmux-pane` summaries.
- Compatibility routing is not enabled; do not route simple lookups to `omx explore`.

**Compaction Protocol:**
Before context compaction, preserve critical state:
1. Write progress checkpoint via `omx state write --input '<json>' --json`
2. Save key decisions via `omx notepad write-working --input '<json>' --json`
3. If context is >80% full, proactively checkpoint state
</session_context>
<!-- OMX:RUNTIME:END -->
