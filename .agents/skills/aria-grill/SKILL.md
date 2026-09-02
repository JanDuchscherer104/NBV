---
name: aria-grill
description: Stress-test vague, high-impact, research-facing, advisor-facing, or cross-surface ARIA-NBV decisions, including thesis scope, theory-rich plans, option tradeoffs, and architecture, interface, or visualization choices, before implementation.
---

# Aria Grill

## Grounding

Before asking, resolve discoverable facts from the
[`aria-nbv-context` owner hierarchy](../aria-nbv-context/SKILL.md#owner-hierarchy)
and the exact decision owner. Use `docs/typst/shared/glossary.typ` for overloaded
terms and the nearest `AGENTS.md` for touched code or docs.

For thesis-scope decisions, read the active thesis, roadmap, research-question
owners, and the applicable record in
`docs/typst/thesis/development/reader-state.toml`; non-thesis branches skip
them. Theory-rich, deep-theory, or elaborate modifiers additionally load
[`references/plan-mode-theory-patterns.md`](references/plan-mode-theory-patterns.md).
For a conceptual, elaborate, theory-rich, or deep-theory thesis decision,
also load
[`references/thesis-teaching-packet.md`](references/thesis-teaching-packet.md).

For optional upstream questioning patterns, see
[`references/upstream-mattpocock.md`](references/upstream-mattpocock.md); keep
ARIA source-order owners canonical. For external API or version uncertainty,
hand off through [`aria-nbv-context`](../aria-nbv-context/SKILL.md) and read its
[Context7 registry](../aria-nbv-context/references/context7_library_ids.md).

## Progressive Capability Routing

Repository policy routes implicit ARIA use through Aria Grill; explicit user
invocation overrides it. Select only the smallest material capability:

- `codebase-design`: boundary vocabulary and comparison; use its
  `DESIGN-IT-TWICE` workflow to compare materially different public interfaces.
- `improve-codebase-architecture`: evidence-backed broader architecture scan.
- `domain-modeling`: vocabulary, entities, value objects, or domain boundaries.
- `aria-nbv-mermaid`: accepted static diagrams maintained in the repository.
- `visualize`: interactive, dynamic, or spatial explanation needing more than
  static prose or Mermaid.

Explicitly invoke the selected available skill. If unavailable, continue with
source-grounded local analysis. Return accepted conclusions to the hierarchy
owner; create no wrappers or parallel truth surfaces.

## Plan-Mode Modifiers

Keep the default path concise unless one of these modifiers applies.

- `elaborate`: when the user asks for elaboration or option context, explain
  the practical meaning, pros, cons, and recommended default for each material
  answer option before asking the next question. Do not perform a literature
  sweep unless a claim is research-facing or high impact.
- `theory-rich` / `deep-theory`: when the user explicitly asks for theory,
  rich context, external-evidence grounding, diagrams, equations, or research rationale,
  read [`references/plan-mode-theory-patterns.md`](references/plan-mode-theory-patterns.md).
  Ground theory in the source ladder, state claim strength, and include option
  tradeoffs before questions.
- `conceptual`: when the user asks for `--conceptual`, conceptual planning,
  systems thinking, or architectural explanation, start with the system
  boundary and source-owner model before implementation detail. Name vertical
  truth owners and horizontal evidence sources, include a Mermaid diagram for
  non-trivial plans, link implementation-facing Python plans to
  `python-standards` and the nearest `aria_nbv/**/AGENTS.md`,
  use local literature owners before web search for thesis claims, and use the
  `aria-nbv-context` external-evidence branch only for library/API behavior
  after local owner inspection.
  Keep `$plan`, `$ralplan`, and `$prometheus-strict` as workflow owners; this
  skill is the ARIA sidecar that teaches why the routing matters.
- Use Codex-app-safe Markdown/KaTeX equations when they clarify the decision:
  write inline equations as `\(...\)`, display equations as `$$...$$` with
  blank lines before and after, avoid `$...$` inline math because it may not
  render reliably in Codex chat, and never put equations intended to render in
  fenced code blocks. Use fenced `mermaid` blocks for diagrams, and keep math
  out of Mermaid labels unless it is plain text. For committed `.mmd` assets,
  hand off to `aria-nbv-mermaid` and validate locally.
- Treat Wikipedia as orientation only; ground proposal and thesis evidence in
  cited primary sources.

## Thesis teaching handoff

For a conceptual, elaborate, theory-rich, or deep-theory thesis branch,
produce the task-local teaching
packet before the implementation plan. Its purpose is to preserve the
explanatory value of the discussion when work moves into `academic-writing`.

The packet must:

- begin from the ledger's incoming reader state and active question;
- teach one motivating geometric or empirical case before architecture names;
- separate definitions, implementation facts, literature claims, project
  decisions, hypotheses, and inferences;
- explain relevant geometry, temporal causality, hierarchy, representation, and
  data assumptions at the level the reader needs;
- introduce equations only after their objects and desired behavior are clear;
- compare options through preserved information, symmetries, failure modes, and
  evidence rather than novelty;
- end with a recommended explanation order, durable takeaways, open decisions,
  exact owner pointers, and whether the ledger would change.

The packet is not committed as a parallel thesis or architecture owner.
`academic-writing` consumes accepted conclusions, rechecks them against exact
sources, and realizes only the evidence-calibrated reader-facing argument.

## Interview Rules

- Until shared understanding is reached and the user accepts a decision-
  complete plan, perform only read-only grounding and questions. Do not
  implement or write durable glossary, decision, roadmap, or guidance changes.
- Ask one material decision at a time.
- State the recommended answer with the tradeoff.
- Under `elaborate`, `theory-rich`, or `deep-theory`, explain answer-option
  tradeoffs before
  calling `request_user_input`.
- Challenge overloaded terms against `docs/typst/shared/glossary.typ`.
- For fuzzy thesis or planning terms, test the plan with three concrete
  scenarios: one normal case, one boundary case, and one failure case.
- Cross-check claims against the exact source-order owners (Typst, Python,
  configuration, tests, and guidance), historical evidence, and roadmap before
  accepting them.
- Resolved terminology updates `docs/typst/shared/glossary.typ` or the
  smallest applicable source-order owner. Do not add a parallel root context
  file or ADR tree as a second source of truth.
- Distinguish `current`, `planned`, `scratch`, and `archive` docs.
- Capture durable outcomes through the root `AGENTS.md` Instruction Capture
  lanes.

## Output

For a thesis theory branch, return the teaching packet and then a
decision-complete plan. Other branches return the plan directly. Name the goal,
success criteria, scope, affected owners, verification, assumptions, and
deferred decisions.
