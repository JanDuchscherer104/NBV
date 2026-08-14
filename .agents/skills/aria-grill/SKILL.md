---
name: aria-grill
description: Stress-test vague, high-impact, research-facing, advisor-facing, or cross-surface ARIA-NBV decisions before implementation; use as the ARIA gateway for progressively disclosed architecture, interface, static-diagram, and interactive-visualization capabilities.
metadata:
  mode: router
  not_when:
    - "a concrete failing command, traceback, or metric owns the task"
    - "the edit is already localized and low impact"
    - "the user asks for code review of concrete diffs"
  handoff_to:
    - "nearest owning guide for concrete failures"
    - "aria-nbv-context when the affected surface is unknown"
    - "nearest owning guide for concrete diff review"
    - "nearest docs guide for public narrative edits after the decision"
  evidence_required:
    - "source-order owner for the decision"
    - "success criteria, in/out of scope, and deferred decisions"
    - "direct-source evidence for advisor-facing claims"
    - "source ladder and explicit claim strength for theory-rich mode"
  applies_to:
    - "**"
  triggers:
    - "advisor-facing decision"
    - "thesis scope"
    - "high-impact refactor"
    - "scaffold ownership"
    - "theory-rich plan"
    - "conceptual plan"
    - "--conceptual"
    - "elaborate plan"
    - "rich context"
    - "option tradeoffs"
    - "literature-grounded plan"
  must_read:
    - ".agents/references/source_order.md"
    - "docs/typst/thesis/main.typ"
    - "docs/typst/thesis/development/roadmap.typ"
    - "docs/typst/thesis/sections/01-research-questions.typ"
    - "references/plan-mode-theory-patterns.md when using theory-rich or elaborate modifiers"
  canonical_sources:
    - ".agents/references/source_order.md#role-split"
    - "docs/typst/thesis/main.typ"
    - "docs/typst/thesis/development/roadmap.typ"
    - "docs/typst/thesis/sections/01-research-questions.typ"
    - ".agents/skills/aria-grill/references/plan-mode-theory-patterns.md"
  context7_refs:
    - "/pytorch/pytorch"
    - "/facebookresearch/pytorch3d"
    - "/websites/typst_app"
    - "/websites/quarto"
  literature_refs:
    - "docs/contents/literature/index.qmd"
    - "finite-candidate-rl"
    - "quality-driven-rri"
    - "egocentric-aria-substrate"
  tool_refs:
    - "mcp__MCP_DOCKER.resolve_library_id"
    - "mcp__MCP_DOCKER.get_library_docs"
    - "mcp__code_index.search_code_advanced"
  verification:
    - "decision-complete plan with assumptions and deferred decisions"
---

# Aria Grill

## Grounding

Before asking the user, resolve discoverable facts from
`.agents/references/source_order.md` and the owning source for the decision.
Use `docs/typst/shared/glossary.typ` for overloaded terms and the nearest
`AGENTS.md` for touched code or docs.

For optional upstream questioning patterns, see
`references/upstream-mattpocock.md`; keep ARIA source-order owners canonical.

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

When selecting a capability, explicitly invoke its available installed skill.
If it is unavailable, state that limitation and continue with source-grounded
local analysis. Return accepted conclusions to the source-order owner; create
no wrappers or parallel truth surfaces.

## Plan-Mode Modifiers

Keep the default path concise unless one of these modifiers applies.

- `elaborate`: when the user asks for elaboration or option context, explain
  the practical meaning, pros, cons, and recommended default for each material
  answer option before asking the next question. Do not perform a literature
  sweep unless a claim is research-facing or high impact.
- `theory-rich`: when the user explicitly asks for theory, rich context,
  literature/API grounding, diagrams, equations, or advisor-facing rationale,
  read `references/plan-mode-theory-patterns.md`. Ground theory in the source
  ladder, state claim strength, and include option tradeoffs before questions.
- `conceptual`: when the user asks for `--conceptual`, conceptual planning,
  systems thinking, or architectural explanation, start with the system
  boundary and source-owner model before implementation detail. Name vertical
  truth owners and horizontal evidence sources, include a Mermaid diagram for
  non-trivial plans, link implementation-facing Python plans to
  `python-standards` and the nearest `aria_nbv/**/AGENTS.md`,
  use local literature owners before web search for thesis claims, and use
  Context7 only for external library/API behavior after local owner inspection.
  Keep `$plan`, `$ralplan`, and `$prometheus-strict` as workflow owners; this
  skill is the ARIA sidecar that teaches why the routing matters.
- Use Codex-app-safe Markdown/KaTeX equations when they clarify the decision:
  write inline equations as `\(...\)`, display equations as `$$...$$` with
  blank lines before and after, avoid `$...$` inline math because it may not
  render reliably in Codex chat, and never put equations intended to render in
  fenced code blocks. Use fenced `mermaid` blocks for diagrams, and keep math
  out of Mermaid labels unless it is plain text. For committed `.mmd` assets,
  hand off to `aria-nbv-mermaid` and validate locally.
- Treat Wikipedia as orientation only. Do not use it as advisor-facing,
  proposal-critical, or thesis-claim evidence.

## Interview Rules

- Until shared understanding is reached and the user accepts a decision-
  complete plan, perform only read-only grounding and questions. Do not
  implement or write durable glossary, decision, roadmap, or guidance changes.
- Ask one material decision at a time.
- State the recommended answer with the tradeoff.
- Under `elaborate` or `theory-rich`, explain answer-option tradeoffs before
  calling `request_user_input`.
- Challenge overloaded terms against `docs/typst/shared/glossary.typ`.
- For fuzzy thesis or planning terms, test the plan with three concrete
  scenarios: one normal case, one boundary case, and one failure case.
- Cross-check claims against code, paper, memory state, and roadmap before
  accepting them.
- Resolved terminology updates `docs/typst/shared/glossary.typ` or the
  smallest applicable source-order owner. Do not add a parallel root context
  file or ADR tree as a second source of truth.
- Distinguish `current`, `planned`, `scratch`, and `archive` docs.
- Capture durable outcomes through the root `AGENTS.md` Instruction Capture
  lanes.

## Output

End with a decision-complete plan naming the goal, success criteria, scope,
affected owners, verification, assumptions, and deferred decisions.
