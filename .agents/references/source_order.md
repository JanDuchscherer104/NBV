# ARIA-NBV Source Order

Use this reference when a task needs current project truth or sources disagree.

## Role Split

- Thesis narrative and research questions: `docs/typst/thesis/main.typ` and
  `docs/typst/thesis/sections/01-research-questions.typ` own current prose,
  objectives, boundaries, and the six-tier RQ scope. RQ1--RQ4 are the
  evaluated core; RQ5 is a conditional online bridge and RQ6 is a lower-
  priority continuous/simulator escalation.
  Development-only planning and gate views are owned by
  `docs/typst/thesis/development/roadmap.typ` and
  `docs/typst/thesis/development/m1-contract-report.typ`, guarded by
  `development_only`. Quarto thesis pages are historical/migration inputs, not
  current-truth owners.
- Current terminology: `docs/typst/shared/glossary.typ` owns terms and symbols;
  `docs/contents/glossary.qmd` is generated public output.
- Idea archive: `docs/contents/ideas.qmd` is read-only scratch/history, not
  current direction.
- Active thesis seed: `docs/typst/thesis/main.typ` and its included sections
  own thesis-facing Typst prose once thesis work is in scope. Archived
  proposal/advisor Typst sources under `.agents/archive/docs/typst/thesis/`
  are provenance only.
- Seminar evidence: `docs/typst/seminar_paper/main.typ` and included sections
  describe the older implemented substrate and past seminar writeup. Use them
  for historical evidence, not for current thesis priority.
- Implementation behavior: `aria_nbv/aria_nbv/`, `aria_nbv/tests/`, and the
  active configuration files own executable package behavior. Mandatory
  Graphify navigation and optional retrieval never substitute for
  opening these exact sources.
- Development-only thesis owners: `docs/typst/thesis/development/roadmap.typ`,
  `docs/typst/thesis/development/m1-contract-report.typ`, and
  `docs/typst/thesis/sections/06-draft-open-work.typ` provide guarded planning,
  gate status, and open-work notes; they are included only through
  `development_only` and are absent from submission output.
- Agents-DB action records (`.agents/issues.toml`, `.agents/todos.toml`, and
  `.agents/refactors.toml`) own actionable follow-up metadata only. They do not
  replace thesis narrative, implementation, tests, or current state owners.
- Active maintenance work: `.agents/issues.toml`, `.agents/todos.toml`,
  `.agents/refactors.toml`, and `.agents/resolved.toml` via `make agents-db`.
- Accepted scaffold-rework target state:
  `.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md` owns the
  scoped scaffold requirements and planning bounds, including the explicit
  2026-08-01 upstream-only boundary and 2026-08-14 mandatory Graphify
  supersession. It does not replace the exact code, test, configuration,
  thesis, or human-preference owners above.
- Generated routing artifacts: `docs/_generated/context/source_index.md`,
  `literature_index.md`, and `data_contracts.md`; refresh with `make context`
  when stale.
- Operator aids and long conventions: `.agents/references/`.
- Agent skills: `.agents/skills/*/SKILL.md` own activation, routing,
  read-first, evidence, and verification loops only. They point to canonical
  sources instead of restating thesis claims, formulas, package contracts, or
  planned implementation detail. Semantic-drift warnings from
  `make scaffold-audit` are source-order review prompts.
- Exception: the byte-identical pinned upstream `.agents/skills/graphify/SKILL.md`
  bundle is exempt from local thin-skill metadata/prose rules;
  `.agents/skills/aria-nbv-context/SKILL.md` owns ARIA-specific Graphify
  activation, freshness, degradation, and safety boundaries.
- Graphify is mandatory navigation in Codex worktrees but remains derived
  evidence, not truth; `aria-nbv-context` owns its route and degradation
  behavior. Other optional tools and adapters provide evidence, not truth; the
  owning source remains authoritative.
- Prefer bounded typed interfaces over unrestricted adapter shell access.
- External research and automation propose source-linked changes; repository
  lanes apply durable mutations.
- Screenshots, rendered pages, and UI diagnostics are advisory until the
  owning source, test, or accepted record changes.
- Thesis-to-code links: `docs/typst/shared/style.typ` defines the
  horizontal link convention for Typst implementation anchors and removable
  agent/draft navigation links. These links help humans and agents traverse
  thesis/code relationships, but they do not override the thesis, code,
  bibliography, guidance, or agents-DB owners above.

## Conflict Rule

When active Typst thesis docs conflict with the seminar paper or dated history,
prefer the active Typst source for direction and keep the other material as
historical evidence. Resolve executable behavior through Python, tests, and
active configuration; resolve routing through `AGENTS.md` and this source-order
map. Do not promote planned work to implemented results.

## Capture Rule

- Repo invariant: root or nearest nested `AGENTS.md`.
- Repeatable workflow: `.agents/skills/*/SKILL.md`.
- Dated migration receipts and debrief history are evidence only; current truth
  resolves to the active Typst, Python, configuration, test, and guidance
  owners above.
- Actionable work: `.agents/issues.toml`, `.agents/todos.toml`, or
  `.agents/refactors.toml` through `agents-db`.
- Public narrative: Quarto or Typst docs.
- Human-owner preference: `.agents/references/human_owner_intent.md`.
- Accepted scoped target state: the relevant `.omx/specs/` artifact named in
  the role split above; later plans implement it but do not redefine it. A
  later human decision that changes an open choice must be recorded as an
  explicit supersession in that accepted artifact before implementation claims
  closure.
- Optional tools provide evidence or proposals; their owning source remains
  authoritative.
