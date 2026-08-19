# ARIA-NBV Source Order

Use this reference when locating current project truth or resolving conflicting
sources. It is the global authority map; `aria-nbv-context` owns traversal.

## Compositional Owner Tree

- **Scientific language and thesis**
  - Ubiquitous language: `docs/typst/shared/glossary.typ` owns terms;
    `symbols.typ` and `equations.typ` own reusable notation and equations;
    `docs/notation.yml` owns cross-format lookup. Generated glossary and notation
    files are projections.
  - Active narrative and research questions: `docs/typst/thesis/main.typ` and
    its included sections, especially `sections/01-research-questions.typ`.
    RQ1--RQ4 are the evaluated core; RQ5 is the conditional online bridge and
    RQ6 the lower-priority continuous or simulator escalation.
  - Development gates and open work: guarded
    `docs/typst/thesis/development/{roadmap,m1-contract-report}.typ` and
    `sections/06-draft-open-work.typ`. These views do not enter submission
    output or promote a planned result.
  - Historical evidence: `docs/typst/seminar_paper/`, archived proposal sources,
    dated debriefs, and `docs/contents/ideas.qmd`. They provide provenance, not
    current thesis direction.
  - Literature identity and evidence: `docs/references*.bib`, exact primary
    sources, and the maintained literature catalog. Generated indexes are
    navigation only.
- **Executable system**
  - Behavior and public contracts: `aria_nbv/aria_nbv/`, nearest package
    `AGENTS.md`, public signatures, types, and docstrings.
  - Proof and selected behavior: `aria_nbv/tests/` and active configuration.
    Documentation, Graphify, Context7, memory, and generated context cannot
    override these owners.
- **Project work and accepted intent**
  - Actionable work: `.agents/{issues,todos,refactors}.toml`; completed records:
    `.agents/resolved.toml`; operate them through `agents-db`.
  - Reviewed human preferences: `.agents/references/human_owner_intent.md`.
  - Accepted scaffold target: the explicitly superseded decisions in
    `.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md`.
    Plans and later debriefs implement or evidence that target; they do not
    silently redefine it.
- **Agent execution**
  - Repository invariants and routing: root or nearest nested `AGENTS.md`.
  - Repeatable workflows: `.agents/skills/*/SKILL.md`. Skills own activation,
    procedure, evidence, handoff, and verification, then point back into this
    tree instead of copying scientific or executable truth.
  - Long operator detail: `.agents/references/`; keep this shelf small and
    cross-cutting.
- **Navigation and external evidence**
  - Graphify is the primary broad-context navigation map in Codex worktrees.
    `aria-nbv-context` owns query-first activation, upstream lifecycle use,
    freshness/repair, degradation, and exact-source verification. Graph output
    remains derived evidence and never becomes the owner it locates.
  - Context7 is current external API/version evidence after a local owner and
    installed call site are known. Domain-skill `metadata.context7_refs` and
    `aria-nbv-context/references/context7_library_ids.md` own exact IDs and query
    recipes. External docs never settle ARIA behavior or scientific claims.
  - `docs/_generated/context/{source_index,literature_index,data_contracts}.md`
    are optional generated navigation; refresh with `make context` only when
    that route is needed.
  - Screenshots, rendered pages, retrieval results, and automation output are
    evidence until their exact owner changes.

## Conflict Rule

Traverse the narrowest matching branch, open the exact owner, and verify the
claim there. Prefer active Typst over seminar/archive history for thesis
direction; prefer source, tests, and active configuration for behavior; prefer
explicit accepted supersessions over plans or chronology for scaffold intent.
Planned work never becomes an implemented result through retrieval, age, or
repetition.

## Capture Rule

- Repo invariant: root or nearest nested `AGENTS.md`.
- Repeatable workflow: `.agents/skills/*/SKILL.md`.
- Actionable work: `.agents/issues.toml`, `.agents/todos.toml`, or
  `.agents/refactors.toml` through `agents-db`.
- Public narrative: active Quarto or Typst owner.
- Scientific language: shared Typst glossary, symbols, equations, or notation
  registry selected through the owner tree.
- Human-owner preference: `.agents/references/human_owner_intent.md` only after
  explicit review and acceptance.
- Accepted scoped target: the relevant explicit supersession in `.omx/specs/`.
- Dated debriefs and optional tools capture evidence or proposals, never a
  second current-truth owner.
