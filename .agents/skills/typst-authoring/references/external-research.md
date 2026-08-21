# External Refresh Queries

Refresh external information only when local references are insufficient or
the task asks for current Typst behavior. Distill rules into this skill; do
not bulk-copy external skill content.

## Official Typst Docs

Use official Typst docs with narrow queries; for current library selection, use
[`aria-nbv-context`](../../aria-nbv-context/SKILL.md) and its
[Context7 registry](../../aria-nbv-context/references/context7_library_ids.md):

- `math attach subscript superscript limits scripts`
- `math op text operator spacing limits`
- `figure caption label reference`
- `bibliography cite reference label`
- `compile png ppi pages root`
- `import include module path root`
- `table header align stroke inset`
- `layout align block box columns grid stack place pad page pagebreak measure`
- `scripting let blocks content destructuring include import module set show context`
- `csv json toml data loading array dictionary map filter slice reduce to-dict`
- `symbols math shorthands cal bold op arrows relations greek`

## Skill Registry Inspiration

Use these only for concise workflow ideas:

- `https://context7.com/skills?q=typst`
- `https://context7.com/skills?q=academic+writing`
- `https://context7.com/skills?q=scientific+writing`
- `https://context7.com/skills?q=thesis+writing`
- `https://context7.com/skills?q=technical+writing`

Useful patterns are task modes, fixture-based regression tests,
compile/render/inspect loops, claim ledgers, and minimal on-demand references.
