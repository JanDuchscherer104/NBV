# Context Snapshot: Local Agent Skill Recommendations

## Task Statement
Run `$ralplan` on the extracted recommendation file for improving ARIA-NBV's local agent skills.

## Desired Outcome
Produce a consensus execution plan for integrating the extracted K-Dense scientific-agent-skills recommendations into ARIA-NBV without installing the complete upstream collection directly into `.agents/skills/`.

## Known Facts And Evidence
- The extracted recommendation says not to install the full K-Dense collection directly under `.agents/skills/`.
- The recommended architecture is a pinned external upstream source under `.agents/external/scientific-agent-skills` plus ARIA-owned adapter skills.
- The six proposed adapters are `scientific-writing`, `literature-review`, `scientific-review`, `scientific-visualization`, `experiment-design`, and `citation-management`.
- Root guidance says non-trivial scaffold work must apply `agent-behavior` first.
- `.agents/references/source_order.md` says skills own activation, routing, read-first evidence, and verification loops only; durable thesis truth lives elsewhere.
- `.agents/references/skill_style_guide.md` requires compact, metadata-rich, local canonical-source-oriented skills and warns against unresolved external tool namespaces.
- `.agents/external/litkg-rs` is the existing precedent for a pinned external dependency boundary.
- Current scaffold checks include `make scaffold-audit`, `make scaffold-audit-self-test`, `make check-agent-memory`, and `make claude-skills`.

## Constraints
- Ralplan is planning-only; no implementation edits outside `.omx` planning artifacts in this session.
- Preserve dirty worktree state, including existing `.omx` runtime changes and the modified `.agents/external/litkg-rs` submodule state.
- Do not make optional K-Dense, OMX, KG, MCP, Zotero, or other external tooling a source of truth.
- Keep adapter skill bodies compact and route durable claims to canonical docs, references, memory state, or package owners.
- Avoid generic package/domain skill sprawl; only repeatable ARIA-NBV workflows should become hot-path skills.

## Unknowns
- Exact upstream K-Dense commit and license must be verified during execution.
- Submodule is favored by precedent, but execution should verify it fits current repo policy.
- Zotero/Better BibTeX remains unresolved and must stay optional through `citation-management`.
- Exact routing fixtures should be finalized while writing adapter frontmatter.

## Likely Touchpoints
`AGENTS.md`, `docs/AGENTS.md`, `.agents/references/source_order.md`, `.agents/references/skill_style_guide.md`, `.agents/references/scaffold_routing_fixtures.json`, `.agents/references/alignment_tools_contract.md`, `.agents/skills/*/SKILL.md`, `.agents/skills/*/references/upstream-adaptation.md`, `.agents/external/scientific-agent-skills`, `.configs/external_skills.toml`, `scripts/external_skills.py`, `scripts/scaffold_audit.py`, `scripts/sync_claude_skills.sh`.
