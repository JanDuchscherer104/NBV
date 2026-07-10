# Autopilot Context: Agent Scaffold Cleanup

## Activation Prompt / Task Seed

User requested `$oh-my-codex:autopilot` to clean up and improve the ARIA-NBV
agent scaffold from the accumulated context.

## Original Task Status

activation-prompt

## Desired Outcome

- Reduce scaffold redundancy and clarify single sources of definition and
  responsibility.
- Keep OMX, litkg, graphify/Graphiti/MemPalace, and external autoresearch
  harnesses optional and replaceable.
- Add automated checks where possible so alignment rules are enforced rather
  than only described.

## Known Facts / Evidence

- Root `AGENTS.md` is the repo dispatcher.
- `.agents/references/source_order.md` owns current truth and capture rules.
- `.agents/references/skill_style_guide.md` owns skill shape and metadata.
- `.agents/references/verification_matrix.md` owns verification routing.
- `.configs/litkg.toml` already states litkg/graphify/Neo4j/Graphiti/MemPalace
  runtime roles.
- `make kg-status` returned `kg-status: ok`.
- `make kg-capabilities KG_FORMAT=json` showed core ARIA sources ready and
  optional runtime leaves mixed/configured.
- `kg-claim-check` produced a false positive on the bad claim that LitKG should
  be the default source of truth for every ARIA task; claim checks must remain
  advisory until the verdict layer is hardened.
- Working tree has unrelated thesis/advisor changes that must not be reverted.

## Constraints

- Keep public docs distinct from internal agent/operator scaffolding.
- `.omx/`, `.codex/config.toml`, and `.codex/hooks.json` remain ignored runtime
  state.
- Prefer minimal edits over broad skill rewrites.
- Do not make external harnesses hard dependencies for normal repo work.

## Unknowns / Open Questions

- None blocking for a first cleanup pass. The selected first deliverable is an
  adapter/contract cleanup rather than a runnable autonomous AutoML loop.

## Likely Codebase Touchpoints

- `AGENTS.md`
- `.agents/references/source_order.md`
- `.agents/references/verification_matrix.md`
- `scripts/validate_agent_memory.py`
- a compact new `.agents/references/` contract if needed

## Scope Note

This snapshot records the Autopilot activation context and prior same-thread
decisions. It is not public documentation and does not supersede repo source
order or canonical memory.
