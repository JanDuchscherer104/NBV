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
- Keep the active Typst thesis as the sole scientific narrative and
  interpretation owner, while direct code/tests, immutable empirical artifacts,
  and exact papers remain authoritative for the claims it cites. Keep Quarto
  thesis pages as navigation only.
- Prefer upstream tool behavior and the smallest maintainable adapter that can
  preserve ARIA source identity; generated navigation is evidence, not truth.
- Preserve high-signal prior instructions by assigning each accepted rule or
  preference one current owner, not by treating transcripts as live guidance.
- Manage checkpoints and model artifacts through Git LFS when they are intended
  to be versioned.
- Prefer compact ARIA-native skills over vendoring generic upstream skill sets.

## Instruction Capture

| New durable information | Destination |
|---|---|
| Repo-wide invariant or safety rule | `AGENTS.md` or nearest nested `AGENTS.md` |
| Repeatable workflow | `.agents/skills/[skill-name]/SKILL.md` |
| Human-owner preference | `.agents/references/human_owner_intent.md` |
| Current scientific direction or open question | Active Typst thesis |
| Current implementation contract | Owning code, tests, docstrings, nearest package `AGENTS.md`, or concise subsystem README |
| Empirical measurement or validity | Immutable manifest or evidence bundle |
| Literature claim | Exact external paper |
| Actionable defect, todo, or refactor | `.agents/issues.toml`, `.agents/todos.toml`, or `.agents/refactors.toml` |
| Public thesis narrative | Active Typst thesis |
| Public thesis navigation/reference | Quarto thesis indexes |
| Supporting execution or retrieval record | Debriefs, transcripts, OMX artifacts, or Graphify output |
| Generated terminology or agent mirrors | tracked glossary output or `.agents/generated/` with explicit source provenance |

Prefer the smallest surface that can preserve the instruction without creating
a second source of truth.
