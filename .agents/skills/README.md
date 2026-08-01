# ARIA-NBV Skill Style Guide

Skills are hot-path agent instructions. Keep them compact, task-specific, and
activation-oriented. Long details belong in `references/` files.

## Required Frontmatter

```yaml
---
name: skill-name
description: One sentence describing when to use the skill.
metadata:
  mode: "implementation | router | diagnostic | review | maintenance"
  not_when:
    - "confusing adjacent task cue"
  handoff_to:
    - "skill-name for adjacent ownership"
  evidence_required:
    - "artifact, source, command, or trace needed before acting"
  applies_to:
    - "repo/glob/**"
  triggers:
    - "phrase or task cue"
  must_read:
    - "small required source list"
  canonical_sources:
    - "repo/path.md#heading-or-stable-anchor"
  context7_refs:
    - "/org/project"
  literature_refs:
    - "BibTeX-key-or-owner-path"
  tool_refs:
    - "mcp__server.tool_name"
  verification:
    - "command or review check"
---
```

Use meaningful routing metadata under `metadata:` so skills stay compatible with
`make scaffold-audit`. Broad skills may use broad globs, but triggers must
still be concrete enough for an agent or KG router to distinguish them. Do not
use ad hoc modes such as `scaffold`; universal preflight or routing skills are
`router` skills until another accepted mode is added deliberately.
Keep all routing fields nested under `metadata`; do not add new top-level
frontmatter keys. Broad/router skills should include `mode`, `not_when`,
`handoff_to`, and `evidence_required` so lane selection stays machine-readable.
Every directory under `.agents/skills/` must match the frontmatter `name`.
Machine-facing `handoff_to` entries should start with a repo-local skill name or
  declared capability wording, not unresolved plugin namespaces such as `omx:*`,
  `github:*`, or `oh-my-codex:*`.
Every skill must declare `metadata.canonical_sources` as relative repo paths.
Use anchors for Markdown or Quarto owners when a stable section exists. This
field names where the durable truth lives; the skill body should summarize only
the activation rule, read-first path, evidence contract, and verification loop.
Do not put planned but unimplemented research detail in skills. Put it in the
owning thesis roadmap, research-question page, Quarto theory page, Typst
section, package `AGENTS.md`, or source code contract instead.
Use optional `context7_refs`, `literature_refs`, and `tool_refs` only as thin
routing edges. Context7 refs must already exist in
their exact upstream identifier; literature refs must resolve to
BibTeX keys, Quarto/literature paths, local TeX mirror paths, or route labels
in `aria-nbv-context/references/context_map.md`; tool refs use canonical
`mcp__<server>.<tool_name>` names. Do not point skill metadata at generated
context indexes as source owners.

Byte-identical, separately pinned upstream skill bundles are exempt from ARIA
frontmatter and hot-path-style requirements. Do not patch upstream frontmatter
to satisfy this validator. Put repository activation, source-order, safety, and
verification instructions in the nearest ARIA companion skill, and enforce the
declared upstream bytes with a separate integrity test.

## OMX Sidecar Pattern

ARIA-NBV skills are sidecars for Codex/OMX orchestration. OMX owns workflow
state, goals, phase transitions, and review/QA gates; a repo skill owns local
domain knowledge, exact tool loops, required evidence, and verification choices.

- `not_when` should name adjacent work that belongs to another skill or OMX
  phase.
- `handoff_to` should name the next local skill or workflow when the current
  skill is only supporting context.
- `evidence_required` should state the artifact, command output, source, or
  trace needed before acting or handing off.
- Use a short `## OMX Integration` body section only when the role split is not
  obvious from metadata. Do not duplicate root routing or the full OMX operator
  manual inside individual skills.

## Body Template

- Use When
- Do Not Use When, if confusion is likely
- Read First, usually 3-5 sources
- Rules, usually 5-10 bullets
- Workflow, short and ordered
- Verification
- Stop or completion conditions

## Style Rules

- Default skill bodies should stay under about 150 lines unless the skill wraps
  an operator workflow with unavoidable commands.
- Avoid duplicating root source order, long command lists, or schema manuals.
- Prefer references over nested procedural walls.
- Prefer a canonical-source link over restating formulas, roadmap claims, API
  contracts, or operator commands already owned elsewhere.
- Do not add speculative abstractions or future-work instructions unless the
  task explicitly owns that future-work surface.
- Every skill should preserve the `agent-behavior` principles: explicit
  assumptions, simplest sufficient change, surgical edits, and verifiable
  completion.
- Do not repeat the full lane-selection policy in every skill. Put routing cues
  in metadata and keep detailed arbitration in `agent-behavior`.
- Before deleting a skill or merging router skills, update
  `scripts/scaffold/fixtures/routing.json` and keep `make scaffold-audit` green.

## Source-Order Review Gate

Run the source-order question before adding, deleting, or merging skill prose:

1. What source owns this truth?
2. Is this sentence routing/evidence, or durable project truth?
3. If this skill disappeared, which owner would still preserve activation,
   dirty-worktree safety, request traceability, and verification?

`make scaffold-audit` reports semantic-drift warnings when a skill body appears
to contain formulas, roadmap claims, future-work plans, or implementation
contracts. Treat those warnings as review prompts first: either move the detail
to the canonical owner and link it through `metadata.canonical_sources`, or keep
the sentence only when it is a compact routing cue.
