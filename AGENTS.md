# ARIA-NBV Agent Guidance

Use this dispatcher with the nearest applicable `AGENTS.md`. Exact sources,
tests, configuration, and Typst own behavior and scientific claims.

## Source Order

- Use `.agents/references/source_order.md` for current truth and conflict
  resolution. Generated, retrieved, and historical material is evidence, not
  current authority.

## Diagnosis And Routing

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
- Reviews report severity-ranked, line-referenced findings. Publish actionable
  P0-P2 PR findings as resolvable GitHub review threads and resolve them only
  after exact-head evidence; report local-only reviews locally. Failure-first
  diagnosis is the
  repository-wide invariant for bugs, regressions, suspicious metrics, and
  failing checks; `agent-behavior` owns the repeatable procedure, while the
  nearest semantic guide owns behavior. Reproduce the smallest failure, inspect
  exact source and focused tests, and verify the cause before changing behavior.
  Backlog or memory changes use `agents-db`; cleanup uses `simplification`; LRZ
  work uses `lrz-ai-systems`.
- Rerun SDK, entity, sink, blueprint, `.rrd`, camera/depth logging, and offline/
  rollout inspection work uses `rerun-nbv-inspector`. It provides the current
  official-reference and Context7 route; package README files, code,
  configuration, and tests remain behavioral owners.

## Graphify

- Every Codex worktree initializes Graphify through
  `scripts/setup_worktree_env.sh`. For eligible codebase architecture,
  relationship, ownership, or project-content questions, run
  `scripts/check_graphify_freshness.py --json`, query the byte-identical
  upstream Graphify skill first for `fresh` or `usable-stale`, then verify
  exact sources. Repair an `unusable` bootstrap before eligible work; if it
  remains unusable, report the degradation and use exact sources only.
  Graph output is derived navigation, never authority.

## Universal Safety

- Do not use `git restore` or `git reset --hard` unless explicitly requested.
- Assume the worktree can be dirty; never revert unrelated user or agent work.
- Keep public docs aligned with their current thesis/code owners; historical
  evidence is cited as historical. Do not publish internal agent/runtime state.

## Optional Tools And Capture

- External skills, OMX, MCP, MemPalace, memory, and autoresearch provide
  optional evidence or orchestration, never ARIA truth ownership. Route durable
  changes through the source-order owner.
- Use `aria-nbv-context` for semantic recall only when it materially improves
  the task; unavailable optional retrieval falls back to exact sources.
- The source-order capture rule selects the smallest owner. `agent-behavior`
  owns angle-bracket eligibility and the capture procedure. A read-only capture
  route still names each selected owner's verification; guidance, state, memory,
  and debrief owners use `make check-agent-memory`.

## Verification And Debriefs

- Follow the nearest guide and run the narrowest proof of the changed contract.
  Advisor-facing claims require the cited primary source and exact local evidence.
- Non-trivial work leaves a debrief under `.agents/memory/history/YYYY/MM/`.
  Native debriefs follow `.agents/memory/README.md`; do not recreate `.codex` as
  a notes bucket.
