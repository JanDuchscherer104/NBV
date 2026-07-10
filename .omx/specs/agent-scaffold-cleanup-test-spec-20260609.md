# Test Spec: ARIA-NBV Agent Scaffold Cleanup

## Static Checks

- `make check-agent-memory`
  - validates native debriefs;
  - rejects legacy `.codex/*.md` notes;
  - rejects committed `.omx` runtime files when not ignored;
  - checks root guidance links the alignment/tool contract.
- `make agents-db AGENTS_ARGS='validate'`
  - verifies active backlog schema remains valid.

## Targeted Content Checks

- `rg -n "alignment_tools_contract|OMX remains optional|source of truth|Graphiti|MemPalace|Graphity" AGENTS.md .agents/references scripts/validate_agent_memory.py`
- `! rg -n "Invalidity is a hard mask/reason|Do not treat V0 GT|Gymnasium/SB3/online simulator|make kg-claim-check KG_CLAIM" /home/jd/.codex/AGENTS.md`
- `git check-ignore -v .omx .codex/config.toml .codex/hooks.json`

## Review Checks

- Confirm no runtime state is made authoritative.
- Confirm no optional backend becomes required for normal repo work.
- Confirm `/home/jd/.codex/AGENTS.md` only routes to repo-owned ARIA guidance
  and does not duplicate detailed ARIA policy.

## QA Scenarios

- Dirty worktree: pre-existing thesis/advisor edits remain untouched.
- Missing optional runtime: scaffold validation does not require Neo4j,
  Graphiti, MemPalace, Ollama, Semantic Scholar, or OMX tmux.
- Misleading claim-check: litkg claim checks remain advisory rather than hard
  gates for scaffold truth.
