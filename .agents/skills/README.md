# ARIA-NBV Skill Style Guide

Skills are compact agent procedures. Native frontmatter selects the skill;
the body keeps universal invariants and chooses conditional references.

## Frontmatter

Every ARIA-owned `SKILL.md` starts with exactly these two fields:

```yaml
---
name: skill-name
description: One model-facing sentence describing when to use the skill.
---
```

Use the directory name as `name`. Write `description` as one sentence that
states the skill's outcome and its distinct activation branches. Keep it
specific enough for autonomous selection and short enough to remain a useful
always-loaded pointer. Put procedure, evidence, handoffs, and verification in
the body or a conditional reference.

## Body

Keep the body below 150 lines. Include only material every invocation needs:

- the outcome and the smallest safe workflow;
- universal invariants and ownership boundaries;
- branch selectors that name the condition and its next reference or handoff;
- completion criteria that make the required evidence explicit.

Use imperative language. Prefer one owner, one purpose, and one proof. Treat
source files, tests, configuration, and active scientific documents as the
truth owners; skills route to them without copying their contracts.

## Conditional references

Link each branch directly to the smallest existing `references/*.md` file and
state when to read it. When a branch genuinely has many subtopics, a directly
linked branch index may route one additional hop to its leaf references; do not
chain through a second index. Convert weak plain reference-name inventories into
concise Markdown pointers where practical. Put branch-specific commands, lookup
tables, examples, version details, and longer procedures in those references.
Do not create a registry that mirrors the skill set or source ownership.
Make pointer preservation a completion condition: complete a progressive-
disclosure edit only when an existing or replacement pointer names the branch
and target strongly enough to load the moved detail.

Use the repository's current owner paths for implementation and scientific
claims. A pointer identifies where to look; it does not make the pointer's
target authoritative over the source owner. In scientific documentation,
`docs/typst/shared/glossary.typ` owns durable terms; `docs/typst/glossary/` is
rendered/modular output; `docs/references.bib` and `docs/references-qh.bib` own
citation identities; `docs/literature/sources.jsonl` owns acquisition and
relevance metadata; `docs/contents/literature/` owns review synthesis; and
`docs/typst/thesis/sections/` owns active claim placement.

## Ownership and handoffs

Keep local invariants in the skill that governs them. Hand off at the branch
endpoint to the nearest package guide, docs/Typst owner, failure owner, or
specialist skill. Record the evidence required for that handoff next to the
branch that consumes it.

For an already-known exact owner, open that owner and its nearest `AGENTS.md`
and stop retrieving. Use optional navigation, recall, or external-document
references only when their branch condition is active.

## Upstream skills

For every upstream-derived bundle, preserve its upstream frontmatter, exact
upstream body, and all upstream bytes. The pinned release/commit reference and
bounded refresh/check procedure belong, with ARIA-specific activation,
source-order, safety, and verification, in an ARIA-owned companion or
maintenance surface outside the bundle, while the upstream bundle remains
byte-identical.

## Review

Before editing a skill, identify the owner of each sentence, classify it as an
invariant, selector, pointer, or completion criterion, and remove duplicated
source truth. Check that every pointer exists, every body remains under the
line budget, and every example or command is verified before publication.
