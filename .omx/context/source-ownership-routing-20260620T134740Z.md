# Autopilot Context: Source Ownership And Routing

- activation prompt / task seed: implement the source-of-truth and skill-routing streamlining plan under `$autopilot`.
- original task status: activation-prompt.
- desired outcome: reduce duplicated authority in ARIA-NBV skills, make canonical owners machine-readable, preserve distinct routing responsibilities, and verify scaffold gates.
- known facts/evidence: `make scaffold-audit` currently exists and validates skill metadata, handoffs, line budgets, and routing fixtures; root `AGENTS.md` directs scaffold work through `agent-behavior`; `.agents/references/source_order.md` owns conflict resolution and capture lanes.
- constraints: preserve dirty worktree drift, keep changes scoped to repo-owned scaffold surfaces, do not merge or delete skills in this first pass, and keep planned or unimplemented thesis detail out of skills.
- unknowns/open questions: exact canonical source list per skill must be derived from current metadata and existing docs/source owners.
- likely codebase touchpoints: `scripts/scaffold_audit.py`, `.agents/references/skill_style_guide.md`, `.agents/references/source_order.md`, `.agents/references/scaffold_routing_fixtures.json`, and `.agents/skills/*/SKILL.md`.
- scope note: this seed is the Autopilot activation prompt and the immediately preceding accepted plan, not a guaranteed complete prior conversation transcript.
