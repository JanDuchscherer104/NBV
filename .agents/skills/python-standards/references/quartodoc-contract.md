# Quartodoc Contract

ARIA-NBV generates Python API documentation with Quartodoc through
`docs/_quarto.yml`.

## Local Contract

- `quartodoc.package: aria_nbv`
- `quartodoc.source_dir: ../aria_nbv`
- `quartodoc.parser: google`
- `filters` includes `_extensions/aria-python-roles/aria-python-roles.lua`
  so Sphinx/Python-domain roles in generated API pages link against
  the generated `objects.json` inventory
- public private/import filtering is controlled by the `quartodoc.options`
  block and section-level overrides
- `include_attributes: true` means attribute and field docs matter for rendered
  API pages

Run API doc generation with:

```bash
./scripts/quarto_generate_api_docs.sh
```

For larger docstring changes, render the touched generated page or run the docs
checks named in `docs/AGENTS.md`.

## Rendering Rules

- Use Google-style sections because Quartodoc is configured with the Google
  parser.
- Use Markdown math (`$...$` and `$$...$$`) for equations.
- Use raw Python docstrings when LaTeX backslashes appear.
- Use ordinary fenced Python or doctest examples inside docstrings. Do not use
  executable Quarto fences such as `````{python}````` unless execution is
  deliberate and locally rendered.
- Prefer Sphinx/Python-domain roles for local ARIA-NBV API links:
  `:mod:`, `:class:`, `:func:`, `:meth:`, `:attr:`, `:data:`, and their
  explicit `:py:*:` forms. The Quarto role filter maps those forms to
  Quartodoc's `module`, `class`, `function`, and `attribute` inventory roles.

## Local Role Support

- `:mod:` / `:py:mod:` for modules such as `aria_nbv.rri_metrics.oracle_rri`
- `:class:` / `:py:class:` for classes such as `aria_nbv.rri_metrics.RriResult`
- `:func:` / `:py:func:` for functions such as
  `aria_nbv.rri_metrics.chamfer_point_mesh`
- `:meth:` / `:py:meth:` for methods such as
  `aria_nbv.rri_metrics.oracle_rri.OracleRRI.score`
- `:attr:` / `:py:attr:` for documented fields, properties, and attributes
- `:data:` / `:py:data:` for constants that Quartodoc emits as attributes

External inventory roles require a separately configured and verified external
inventory. Until then, use Markdown links for external API docs.
