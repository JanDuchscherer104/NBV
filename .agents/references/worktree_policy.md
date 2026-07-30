# Worktree Policy

Use this reference when working in any parallel-session git worktree. Worktrees
fork the working tree and the agent scaffold (`.agents/memory/history/`,
`.agents/*.toml`, `.codex/`); without an explicit merge policy those forks
silently diverge.

## Memory Surfaces By Merge Risk

| Surface | Merge risk | Policy |
|---|---|---|
| `.agents/memory/history/YYYY/MM/*.md` | Low — additive, dated | Always commit on the worktree branch. Conflict-free across worktrees because filenames are date+slug. |
| `.agents/issues.toml`, `.agents/todos.toml`, `.agents/refactors.toml` | Medium — structured, ID-keyed | New records are conflict-free if IDs do not collide; check `grep -E '^id = ' <file>` in `main` before picking a new ID. Edits to existing records (description, context, references) need a merge pass. |
| `.agents/resolved.toml` | Low — additive | Resolved records move via `make agents-db AGENTS_ARGS='resolve ...'`; do not hand-edit. |
| `.agents/references/*.md` | Medium | Treat as docs. Conflict by line; rebase before merge. |
| `.agents/skills/<name>/SKILL.md` | Medium | Same as references. |
| Root and nested `AGENTS.md` | High | Same as state — reconcile by hand, never overwrite. |

## Per-Session Workflow

1. Pick a unique worktree branch name; do not reuse another session's branch.
2. When picking a new agents-DB ID, prefer `grep -E '^id = ' .agents/<file>.toml`
   on `main` (or `git ls-tree main:.agents/<file>.toml`) to see committed IDs.
   Active uncommitted IDs in another worktree may collide and need a rename
   on merge.
3. On non-trivial work, leave a debrief under
   `.agents/memory/history/YYYY/MM/`. Use `make new-debrief TITLE='...'` when
   the worktree has a populated `aria_nbv/.venv`; otherwise call
   `python3 scripts/new_debrief.py '...'` directly (stdlib only).
4. Run `python3 scripts/agents_db.py validate` and
   `python3 scripts/validate_agent_memory.py` before opening a PR or merging
   the worktree branch back.

## Worktree Limitations

- The `Makefile`'s `_check_python` target requires `aria_nbv/.venv/bin/python`.
  New worktrees do not provision this venv automatically. Either run
  `cd aria_nbv && uv sync --all-extras` from the worktree, or call the
  underlying scripts (`scripts/agents_db.py`, `scripts/validate_agent_memory.py`,
  `scripts/new_debrief.py`) directly with `python3` for stdlib-only tasks.
- `.codex/config.toml` and `aria_nbv/.venv/` are operator-local and gitignored;
  they do not propagate into worktrees.

## On Conflict

- Prefer the most-recent source-backed edit when two worktrees touched the same
  thesis, package, reference, or backlog owner with the same intent.
- Do not silently drop the other agent's record; if you cannot reconcile,
  promote the conflict to a debrief and ask the human owner.
- Never use `git restore` or `git reset --hard` to "resolve" a conflict
  (root `AGENTS.md` non-negotiable).
