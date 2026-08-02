# ARIA-NBV Agent Guidance

Use this dispatcher with the nearest applicable `AGENTS.md`. Exact sources,
tests, configuration, and Typst own behavior and scientific claims.

## Source Order

- Use `.agents/references/source_order.md` for current truth and conflict
  resolution. Generated, retrieved, and historical material is evidence, not
  current authority.

## Routing

- For non-trivial coding, docs, scaffold, research, or memory edits, apply
  `agent-behavior` first.
- Package work reads `aria_nbv/AGENTS.md`, then the one nested guide that owns
  the touched contract. Docs, bibliography, Typst, and Quarto work starts at
  `docs/AGENTS.md`.
- Mermaid and thesis-diagram work uses `aria-nbv-mermaid`; notation is owned by
  `docs/typst/shared`. Use `aria-nbv-context` for deterministic discovery.
- Vague, high-impact, advisor-facing, architecture, interface-design, committed
  Mermaid, or interactive-visualization work routes through `aria-grill` unless
  the user explicitly chooses another route.
- Review exact diffs with nearest owners; diagnose failures from a smallest
  reproducer before changing behavior. Backlog or memory changes use `agents-db`;
  cleanup uses `simplification`; LRZ work uses `lrz-ai-systems`.
- Rerun SDK, entity, sink, blueprint, `.rrd`, camera/depth logging, and offline/
  rollout inspection work uses `rerun-nbv-inspector`. It provides the current
  official-reference and Context7 route; package README files, code,
  configuration, and tests remain behavioral owners.

## Universal Safety

- Do not use `git restore` or `git reset --hard` unless explicitly requested.
- Assume the worktree can be dirty; never revert unrelated user or agent work.
- Keep public docs aligned with their current thesis/code owners; historical
  evidence is cited as historical. Do not publish internal agent/runtime state.

## Optional Tools And Capture

- External skills, OMX, MCP, Graphify, MemPalace, memory, and autoresearch are
  optional evidence or orchestration, never ARIA truth owners or prerequisites
  for normal work. Route durable changes through the source-order owner.
- Use `aria-nbv-context` only when useful for semantic recall; if a tool is
  absent or unverified, continue with direct repository search and exact sources.
- Graphify eligibility, freshness, projection, and fallback belong to
  `aria-nbv-context`; eligible queries use the byte-identical upstream Graphify
  skill. Graph outputs remain derived navigation, never authority.
- The source-order capture rule selects the smallest owner. `agent-behavior`
  owns angle-bracket eligibility and the capture procedure.

## Verification And Debriefs

- Follow the nearest guide and run the narrowest proof of the changed contract.
  Guidance, state, and debrief changes require `make check-agent-memory`;
  advisor-facing claims require the cited primary source and exact local evidence.
- Non-trivial work leaves a debrief under `.agents/memory/history/YYYY/MM/`.
  Native debriefs follow `.agents/memory/README.md`; do not recreate `.codex` as
  a notes bucket.
