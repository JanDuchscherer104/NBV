# ARIA-NBV Source Order

Use this reference when sources disagree or an agent must decide where a durable
change belongs.

## Role Split

| Information | Current owner | Supporting evidence only |
| --- | --- | --- |
| Executable behavior | Code, typed APIs, tests, and nearest package guidance | PRs, debriefs, navigation tools |
| Scientific narrative and interpretation | Active Typst thesis include closure | Quarto navigation, plans, reviews |
| Measurements and validity | Immutable manifests and accepted evidence bundles | Thesis interpretation and reports |
| Literature claims | Exact cited paper | Bibliography entries and local notes |
| Terminology and reusable notation | `docs/typst/shared/` | Generated glossary pages |
| Current human preferences | `.agents/references/human_owner_intent.md` | Reviewed transcript evidence |
| Actionable work | Agents DB TOMLs | Debriefs and PR summaries |
| Accepted planning evidence | `.agents/omx_artifacts.toml` and its registered bundle | PR descriptions and handoffs |

Quarto thesis pages, the seminar paper, archived proposals, debriefs,
transcripts, OMX runtime state, Graphify, MemPalace, and agent output are not
current-truth owners. They can locate or explain an owner, but the exact owner
must be checked before acting.

## Conflict And Time Rule

Resolve each disputed statement through the owner for its information class.
Recency and provenance do not establish truth by themselves. A later human
preference supersedes an earlier preference only after a reviewed record names
both statements, their scopes, the active owner update, and any unresolved
conflict. Conversation cannot supersede code, tests, measurements, or papers
without a corresponding owner change.

Historical ledgers preserve the owner wording that was valid when recorded.
Readers must resolve every historical destination through this current source
order; transcripts and debriefs remain supporting records.

## Capture Rule

- Repository invariant: root or nearest nested `AGENTS.md`.
- Repeatable workflow: compact `.agents/skills/*/SKILL.md`.
- Scientific direction or interpretation: active Typst thesis.
- Implementation contract: owning code, tests, docstrings, or package guidance.
- Measurement or validity: immutable manifest or evidence bundle.
- Actionable work: `.agents/issues.toml`, `.agents/todos.toml`, or
  `.agents/refactors.toml` through `agents-db`.
- Human-owner preference: `.agents/references/human_owner_intent.md`.
- Optional tool boundary: `.agents/references/alignment_tools_contract.md`.

Prefer the smallest owner that can hold the information without creating a
second source of truth.
