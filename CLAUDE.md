---
note: This file makes the agent scaffold visible to Claude Code. The canonical
guidance lives in AGENTS.md (cross-vendor) and the nearest nested AGENTS.md.
---

# Claude Code Entry Point

Claude Code does not auto-load `AGENTS.md`. This file routes Claude sessions
into the same scaffold that Codex and Gemini already use.

## Read First
1. `AGENTS.md` — root dispatcher, source order, routing, non-negotiables.
2. `.agents/references/source_order.md` — current truth and conflict resolution.
3. The nearest nested `AGENTS.md` for the touched surface (`aria_nbv/AGENTS.md`,
   `docs/AGENTS.md`, or a module-specific guide).
4. The owning skill under `.agents/skills/<name>/SKILL.md` once the lane is known.

## Behavior
- Apply the `agent-behavior` skill before any non-trivial change. Its principles
  are: state assumptions, inspect the owner, narrowest sufficient edit,
  preserve unrelated work, verify before claiming done.
- Capture durable instruction in the smallest correct surface (`AGENTS.md`,
  `.agents/skills/*/SKILL.md`, `.agents/references/human_owner_intent.md`,
  the active Typst thesis, owning code/tests, or the agents DB via
  `make agents-db`). Legacy `.agents/memory/state/` journals are read-only
  migration evidence.
- Non-trivial work leaves a debrief under `.agents/memory/history/YYYY/MM/`
  following `.agents/references/agent_memory_templates.md`.

## Commands
- Format/lint: `ruff format <file>` and `ruff check <file>`.
- Tests: `cd aria_nbv && uv run pytest <path>`.
- Memory + DB checks: `make check-agent-memory`, `make agents-db`.
- KG (probationary): see `.agents/references/litkg_quick_reference.md`.

## Claude-Specific Surfaces
- Slash commands: `.claude/commands/` mirrors the most-used scaffold verbs.
- Subagents: `.claude/agents/` wraps reviewer / diagnoser / plan-grill /
  debrief-writer lanes for cold-context isolation.
- Skills: `.claude/skills/` symlinks every skill under `.agents/skills/` so
  Claude Code can match the skill `description` field without forking the
  source-of-truth SKILL.md. Refresh after adding or renaming a skill:
  `make claude-skills`.
- Hooks: `.claude/settings.json` runs `make check-agent-memory` on session
  start, validates the agents DB on pre-compact, and runs the debrief nudge
  on stop.

## Verification
- Pick the narrowest check from `.agents/references/verification_matrix.md`.
- After agent-memory or skill edits: `make check-agent-memory`.
- After agents-DB edits: `make agents-db AGENTS_ARGS='validate'`.
