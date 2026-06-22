# Autoresearch Sandbox: Thesis Structure

## Local Evidence Read

- `docs/typst/thesis/main.typ`
- `docs/typst/thesis/template/layout/thesis_template.typ`
- `docs/typst/thesis/appendix/index.typ`
- `docs/typst/thesis/sections/*.typ`
- `docs/contents/thesis/questions.qmd`
- `docs/contents/thesis/roadmap.qmd`
- `.agents/references/source_order.md`
- `.agents/skills/typst-authoring/references/thesis-writing.md`
- `.agents/skills/typst-authoring/references/thesis-section-contracts.md`
- `.agents/skills/typst-authoring/references/claim-citation-discipline.md`
- `.omx/specs/autoresearch-thesis-lit-review/report.md`
- `.omx/specs/autoresearch-thesis-lit-review/result.json`

## External Evidence Used

- Hochschule München thesis assessment / workflow guidance:
  `https://seclab.cs.hm.edu/workflow/`
- TUM Informatics thesis page:
  `https://www.cit.tum.de/en/cit/studies/students/thesis-completing-your-studies/informatics/`
- General thesis-structure and research-process references:
  `https://paperpile.com/g/thesis-structure/`,
  `https://www.scribbr.com/category/research-process/`

## Constraints

- Planning-only pass under `$prometheus-strict` and `$autoresearch`.
- Do not mutate `docs/typst/thesis` until a follow-up execution handoff.
- Do not use historical sources as current truth unless their content is
  explicitly re-owned by `main.typ` or current roadmap/questions/memory.
