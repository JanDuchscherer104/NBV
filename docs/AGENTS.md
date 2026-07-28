# Docs Guidance

Apply this file when working under `docs/`.

## Priorities
- Use `.agents/references/source_order.md` for truth ownership.
- Current thesis direction and interpretation live in the active Typst thesis
  include closure. Quarto roadmap/questions and legacy memory journals are
  navigation and supporting evidence only.
- Current terminology lives in `docs/typst/shared/glossary.typ`; the Quarto
  glossary is generated output.
- `docs/contents/ideas.qmd` is read-only archive/scratch.
- `docs/typst/thesis/main.typ` and its included sections own the active
  master's-thesis seed. Archived proposal/advisor Typst sources under
  `.agents/archive/docs/typst/thesis/` are provenance only.
- `docs/typst/seminar_paper/main.typ` is historical implemented evidence.
- Keep Quarto docs aligned to the correct source role instead of introducing
  competing top-level narratives.
- Keep `docs/references.bib` as the single bibliography source of truth.
- Preserve established Quarto and Typst structure unless the task explicitly changes it.
- Resolve current claims through `.agents/references/source_order.md`; do not
  treat legacy state journals as current-truth owners.
- Keep internal agent guidance, generated context, and OMX runtime notes out of
  public Quarto navigation. If a generated agent mirror is needed, regenerate
  it under `.agents/generated/`; do not write agent mirrors under
  `docs/contents/**`.

## Default Workflow
- Use `scripts/nbv_qmd_outline.sh --compact` to localize the exact Quarto page before opening it.
- Use `scripts/nbv_typst_includes.py --paper --mode outline` to localize the exact Typst section before opening it.
- Open `docs/index.qmd`, `docs/contents/thesis/roadmap.qmd`, and
  `docs/contents/thesis/questions.qmd` only when the task is about project
  narrative, priorities, or roadmap. Historical scratch pages live under
  `.agents/archive/docs/`.
- If you need current project truth, open the owning source from
  `.agents/references/source_order.md` instead of scanning broad doc trees.
- Run `make kg-claim-check KG_CLAIM="..."` for advisor-facing proposal,
  roadmap, research-question, or literature-synthesis claims.

## Commands
- Context refresh: `make context`
- API reference refresh: `./scripts/quarto_generate_api_docs.sh`
- Internal agent scaffold refresh: `./scripts/quarto_generate_agent_docs.py`
- QMD frontmatter check: `make qmd-frontmatter-check`
- Quarto render: `cd docs && quarto render .`
- Quarto preview: `cd docs && quarto preview`
- Quarto check: `quarto check`
- Typst paper: `cd docs && typst compile typst/seminar_paper/main.typ --root .`
- Typst thesis: `cd docs && typst compile typst/thesis/main.typ --root .`
- Typst thesis final-link review:
  `cd docs && typst compile typst/thesis/main.typ /tmp/aria-thesis-final.pdf --root . --input aria-wip-links=false --input aria-code-ref=<sha-or-tag>`
- Typst slides: `cd docs && typst compile typst/seminar_slides/<file>.typ --root .`
- QMD tree: `make context-qmd-tree`
- Outline-first routing: `scripts/nbv_qmd_outline.sh`, `scripts/nbv_typst_includes.py`

## Diagram Rules
- Validate Mermaid before committing diagram edits.
- For Mermaid source files, use the `aria-nbv-mermaid` skill and run
  `python tools/mermaid/scripts/aria_mermaid_lint.py <file.mmd>`.
- Prefer local rendering with `tools/mermaid/scripts/render_mermaid.sh` when
  global `mmdc` is available; do not use online renderers for unpublished
  thesis figures unless explicitly permitted.
- Use `{mermaid}` fences in Quarto.
- Use `<br/>` for Mermaid line breaks and Mermaid-safe node ids.

## Writing Rules
- Keep cross-references and bibliography entries synchronized.
- Add new references to `docs/references.bib` when introducing important concepts or papers.
- Replace temporary citation placeholders such as `cite…` before finishing.
- Use links to relevant internal docs or authoritative external references when introducing non-obvious concepts.
- Use `.agents/references/thesis_code_links.md` for thesis-to-code links:
  `#gh` is for final-worthy pinned implementation anchors, while `#gh-wip`
  and `#gh-symbol` are removable draft/agent navigation aids.
- Keep Quarto source files (`*.qmd`) separate from rendered site output. Published HTML belongs under `docs/_site/`, not next to the sources.
- Treat `docs/_freeze/` as tracked execution state for code-backed pages when needed; treat `docs/_site/`, `site_libs/`, `index_files/`, and `*_files/` as generated publish artifacts.
- Do not store generated context or rendered artifacts in tracked docs paths unless the task explicitly requires it.
- Treat generated agent scaffold mirrors as internal operator artifacts under
  `.agents/generated/`; do not expose them in public Quarto content.
- Retained QMD pages should carry minimal ownership metadata: `title`, `phase`,
  `audience`, `status`, and `owner`. Use
  `phase: thesis | seminar | archive | generated`,
  `audience: public | advisor | developer | agent`,
  `status: current | planned | scratch | deprecated`, and
  `owner: paper | docs | code | agent | generated | jan`.
- Current thesis pages live under `docs/contents/thesis/`; past seminar
  material belongs under `docs/contents/seminar/`; raw scratch or stale history
  belongs under `.agents/archive/docs/`. Only curated public archive summaries
  may live under `docs/contents/archive/`.
- Active tasks belong in `.agents/*.toml`, not public TODO pages.
- For larger doc changes, run `make qmd-frontmatter-check`, `quarto render`,
  and `quarto check` before finishing.
