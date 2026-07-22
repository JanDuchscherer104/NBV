# Human Owner Intent

Use this file for durable Jan-specific preferences that are not public project
narrative, not current technical truth, and not a repeatable workflow.

## Current Preferences

- Keep `.agents/` as the canonical agent scaffold.
- Keep OMX optional; it is orchestration, not repo state.
- Do not restore legacy cache migration or runtime training APIs.
- Keep retained public QMD docs renderable, but move retired implementation
  scratch/history to `.agents/archive/docs/` and expose current implementation
  contracts through generated quartodoc/API docs.
- Manage checkpoints and model artifacts through Git LFS when they are intended
  to be versioned.
- Prefer compact ARIA-native skills over vendoring generic upstream skill sets.

## Instruction Capture

| New durable information | Destination |
|---|---|
| Repo-wide invariant or safety rule | `AGENTS.md` or nearest nested `AGENTS.md` |
| Repeatable workflow | `.agents/skills/[skill-name]/SKILL.md` |
| Human-owner preference | `.agents/references/human_owner_intent.md` |
| Current scientific direction or open question | `docs/contents/thesis/roadmap.qmd`, `docs/contents/thesis/questions.qmd`, or the active Typst thesis |
| Current implementation contract | Owning code, tests, docstrings, nearest package `AGENTS.md`, or concise subsystem README |
| Actionable defect, todo, or refactor | `.agents/issues.toml`, `.agents/todos.toml`, or `.agents/refactors.toml` |
| Public thesis narrative | `docs/` Quarto or `docs/typst/thesis/main.typ` |
| Generated terminology or agent mirrors | tracked glossary output or `.agents/generated/` with explicit source provenance |

Prefer the smallest surface that can preserve the instruction without creating
a second source of truth.
