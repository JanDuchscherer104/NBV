# ARIA-NBV Source Order

Use this reference when a task needs current project truth or sources disagree.

## Role Split

- Current thesis direction: `docs/contents/thesis/roadmap.qmd`,
  `docs/contents/thesis/questions.qmd`, and `.agents/memory/state/` describe
  the active thesis plan, locked decisions, open questions, gotchas, and current
  state.
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
- Active maintenance work: `.agents/issues.toml`, `.agents/todos.toml`,
  `.agents/refactors.toml`, and `.agents/resolved.toml` via `make agents-db`.
- Accepted scaffold-rework target state:
  `.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md` owns the
  scoped scaffold requirements and planning bounds, including the explicit
  2026-08-01 Graphify option-3 supersession. It does not replace the exact code,
  test, configuration, thesis, or human-preference owners above.
- Generated routing artifacts: `docs/_generated/context/source_index.md`,
  `literature_index.md`, and `data_contracts.md`; refresh with `make context`
  when stale.
- Operator aids and long conventions: `.agents/references/`.
- Agent skills: `.agents/skills/*/SKILL.md` own activation, routing,
  read-first, evidence, and verification loops only. They must point to
  canonical sources through `metadata.canonical_sources` instead of restating
  thesis claims, formulas, package contracts, or planned implementation detail.
  A byte-identical, separately pinned upstream skill is exempt from ARIA
  metadata; its ARIA activation and safety boundary belongs in a companion
  repository skill instead of an upstream-file overlay.
  Optional `metadata.context7_refs`, `metadata.literature_refs`, and
  `metadata.tool_refs` are horizontal evidence-routing hints; they do not
  override the owner ladder in this file.
  Semantic-drift warnings from `make scaffold-audit` are source-order review
  prompts: move durable truth to the owner above, or justify the text as a
  compact routing/evidence cue.
- Optional tools and adapters provide evidence, not truth. Tool-specific
  operating details remain with the retained tool owner.
  - External research and automation propose source-linked changes; ordinary
    repository lanes review and apply durable mutations.
  - Prefer bounded typed interfaces over exposing unrestricted shell access to
    an adapter.
  - Screenshots, rendered pages, and UI diagnostics are advisory evidence until
    the owning source, test, or accepted record is updated.
- Thesis-to-code links: `docs/typst/shared/style.typ` defines the
  horizontal link convention for Typst implementation anchors and removable
  agent/draft navigation links. These links help humans and agents traverse
  thesis/code relationships, but they do not override the thesis, code,
  bibliography, memory, or backlog owners above.

## Conflict Rule

When current thesis docs or canonical memory conflict with the seminar paper,
prefer the current source for direction and keep the seminar paper as historical
implemented evidence. Do not promote planned work to implemented results.

## Capture Rule

- Repo invariant: root or nearest nested `AGENTS.md`.
- Repeatable workflow: `.agents/skills/*/SKILL.md`.
- Current truth: `.agents/memory/state/`.
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
