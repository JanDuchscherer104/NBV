# ARIA-NBV Agent Guidance

Use this dispatcher with the nearest applicable `AGENTS.md`. Exact sources,
tests, configuration, and Typst own behavior and scientific claims.

## Source Order

- Use `.agents/skills/aria-nbv-context/SKILL.md#owner-hierarchy` for current
  hierarchy and conflict resolution. Generated, retrieved, and historical
  material is evidence, not current authority.

## Diagnosis And Routing

- For non-trivial coding, docs, scaffold, research, or memory edits, apply
  `agent-behavior` first.
- Package work reads `aria_nbv/AGENTS.md`, then the one nested guide that owns
  the touched contract. Docs, bibliography, Typst, and Quarto work starts at
  `docs/AGENTS.md`.
- Mermaid and thesis-diagram work uses `aria-nbv-mermaid`; notation is owned by
  `docs/typst/shared`. Use `aria-nbv-context` for owner-tree traversal, broad
  project context, and current external-library evidence.
- Vague, high-impact, advisor-facing, architecture, interface-design, committed
  Mermaid, or interactive-visualization work routes through `aria-grill` unless
  the user explicitly chooses another route.
- Reviews report severity-ranked, line-referenced findings. Publish actionable
  P0-P2 PR findings as resolvable GitHub review threads and resolve them only
  after exact-head evidence; report local-only reviews locally. Architect and
  critic review outputs stay session-local; persist only accepted decisions in
  their canonical owner. Failure-first diagnosis uses `agent-behavior`; the
  nearest semantic guide owns behavior. Backlog or memory changes use
  `agents-db`; cleanup uses `simplification`; LRZ work uses `lrz-ai-systems`.
- Rerun SDK, entity, sink, blueprint, `.rrd`, camera/depth logging, and offline/
  rollout inspection work uses `rerun-nbv-inspector`. Package README files,
  code, configuration, and tests remain behavioral owners.

## Graphify And Context7 App

- For architecture, relationships, ownership, or broad project context, use
  `aria-nbv-context`. It treats upstream Graphify `query`, `path`, and `explain`
  as the primary navigation map, then opens exact owners before consequential
  claims or edits. It also routes the Context7 App only for current external API
  or version evidence. Worktree setup, freshness, fallback, exact library IDs,
  and focused query recipes stay behind that route.

## Universal Safety

- Do not use `git restore` or `git reset --hard` unless explicitly requested.
- Assume the worktree can be dirty; never revert unrelated user or agent work.
- Keep public docs aligned with their current thesis/code owners; historical
  evidence is cited as historical. Do not publish internal agent/runtime state.

## Optional Tools And Capture

- External skills, OMX, MCP, MemPalace, memory, and autoresearch provide
  optional evidence or orchestration, never ARIA truth ownership. Route durable
  changes through the hierarchy owner.
- Deliberate user-authored `<...>` prose, including a read-only capture request,
  activates `agent-behavior`'s durable-capture branch. It selects the smallest
  source-order owner and names that owner's verification.
- Unavailable optional retrieval falls back to exact sources; guidance, state,
  memory, and debrief owners use `make check-agent-memory`.

## Verification And Debriefs

- Follow the nearest guide and run the narrowest proof of the changed contract.
  Advisor-facing claims require the cited primary source and exact local evidence.
- Non-trivial work leaves a debrief under `.agents/memory/history/YYYY/MM/`.
  Native debriefs follow `.agents/memory/README.md`; do not recreate `.codex` as
  a notes bucket.
