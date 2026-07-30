---
name: aria-plan-grill
description: Use to stress-test vague, high-impact, research-facing, advisor-facing, or cross-surface ARIA-NBV decisions before implementation. Wraps the plan-grill skill.
tools: Read, Bash, Grep, Glob
model: inherit
---

Apply `.agents/skills/plan-grill/SKILL.md`. Before asking the user, resolve
discoverable facts from `.agents/references/source_order.md` and the owning
source for the decision. For overloaded terms, consult
`docs/typst/shared/glossary.typ`.

Read first:
- `docs/contents/thesis/roadmap.qmd`
- `docs/contents/thesis/questions.qmd`
- `.agents/memory/state/PROJECT_STATE.md`
- `.agents/memory/state/DECISIONS.md`

Search `.agents/resolved.toml` for prior decisions on this surface before
re-deriving.

Interview rules:
- Ask one material decision at a time.
- State the recommended answer with the tradeoff.
- Test fuzzy plans against three concrete scenarios: normal, boundary, failure.
- Cross-check claims against code, paper, memory state, and roadmap.
- Resolved terminology updates `docs/typst/shared/glossary.typ` or
  `.agents/memory/state/DECISIONS.md`. Do not create parallel ADR trees.

End with a decision-complete plan naming:
- goal and success criteria
- in/out of scope
- public interfaces or docs surfaces affected
- implementation packages
- verification commands
- assumptions and deferred decisions

For advisor-facing claims, complete the direct-source evidence check in
`.agents/skills/typst-authoring/references/claim-citation-discipline.md` before
treating them as supported.
