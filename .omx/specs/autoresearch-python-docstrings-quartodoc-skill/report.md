# Python Docstrings Skill Autoresearch Report

## Direct Recommendation

Make `.agents/skills/python-docstrings/SKILL.md` and its local
`references/` files the only maintained docstring instruction surface.
Move docstring-specific guidance out of
`.agents/references/python_conventions.md`, then leave that file with
non-docstring Python conventions plus a pointer to `$python-docstrings`.

## Repo-Local Evidence

- `.agents/skills/python-docstrings/SKILL.md` currently lists
  `.agents/references/python_conventions.md` in both `must_read` and
  `canonical_sources`, so the skill does not yet satisfy single-owner
  docstring maintenance.
- `.agents/references/python_conventions.md` currently owns docstring-specific
  sections: attribute docstrings, Google-style docstrings, Quartodoc rendering
  advice, and examples.
- `docs/_quarto.yml` configures Quartodoc for the package with
  `package: aria_nbv`, `source_dir: ../aria_nbv`, `parser: google`,
  `include_attributes: true`, `include_private: false`,
  `include_imports: false`, `include_empty: false`, `children: separate`,
  embedded member options, and `member_order: source`.
- `scripts/quarto_generate_api_docs.sh` is the local generation path for
  `docs/reference`, chooses `QUARTO_PYTHON`, active `VIRTUAL_ENV`, the package
  `.venv`, or `uvx`, and retries stale alias failures.
- `docs/AGENTS.md` names `./scripts/quarto_generate_api_docs.sh` as the API
  reference refresh command.
- `.agents/references/skill_style_guide.md` says skills should be compact,
  activation-oriented, and point to canonical sources instead of duplicating
  durable owner truth.

## Upstream Evidence

- Quartodoc supports Google, Sphinx, and NumPy parsers via `_quarto.yml`, with
  NumPy as its default and `parser: google` as the configured override.
- Quartodoc content configuration supports documenting functions, modules,
  classes, attributes, methods, and child members; the local config uses that
  machinery for generated API pages.
- Quartodoc generally uses static analysis by default, so generated API pages
  can miss dynamically assigned docstrings unless dynamic lookup is configured.
- Quartodoc examples distinguish doctest and Markdown fenced examples, which
  render without execution, from Quarto executable fences such as
  ````{python}` that execute during `quarto render`.
- Quartodoc links can be normal `.qmd` Markdown links; function-name interlinks
  require the interlinks filter setup, which is not present in the current
  local `_quarto.yml`.
- Griffe parses Google-style sections including `Args`, `Attributes`,
  `Yields`, `Raises`, and `Examples`; its documentation notes that
  `Examples:` is the parsed examples section, while singular `Example` is
  treated differently.
- Google Python style requires docstrings for public APIs, nontrivial or
  non-obvious functions, modules, classes, public attributes, and relevant side
  effects.
- Quarto uses Pandoc Markdown and supports equations and cross-references,
  which supports the repo's rule to use Markdown math in generated API pages.

## Current Issues

1. Single-source ownership is violated because `python_conventions.md` still
   contains docstring-specific rules and examples.
2. `python-docstrings` points to `python_conventions.md` as a canonical
   docstring source, so agents can preserve or extend the wrong owner.
3. `must_read` omits `references/cross-references.md` and
   `references/examples.md` even though those files contain required
   Quarto/Quartodoc guidance.
4. The skill does not state the active local Quartodoc contract:
   `parser: google`, static package collection, attributes included, private
   members excluded, imports excluded by default, empty docs excluded, and
   source-order member presentation.
5. Verification only mentions `ruff format` and `ruff check`, but generated
   API-doc correctness also needs `./scripts/quarto_generate_api_docs.sh` for
   public API docstring changes and a targeted Quarto render when the rendered
   page is risky.
6. The skill allows singular `Example:`, but upstream Griffe/Quartodoc parsing
   treats `Examples:` as the examples section. The skill should prefer
   `Examples:` for parsed API examples.
7. The skill does not warn that Quarto executable code fences in docstrings can
   execute during docs render. Prefer doctest prompts or ordinary Markdown
   fenced code in docstrings unless execution is intentional and validated.
8. Cross-reference guidance should explicitly state that local `_quarto.yml`
   does not enable Quartodoc interlinks/autolink, so backticks and stable
   Markdown links are the default.
9. Pydantic/config guidance should include the local rule: do not use
   `Field(..., description=...)` as the primary config-field documentation
   surface; prefer attribute docstrings on meaningful fields.
10. The audit script is useful but limited: it finds missing and suspiciously
    short docstrings, not incorrect Google sections, Quartodoc parse failures,
    rendered Markdown/math issues, stale generated pages, or broken links.
11. Existing examples are generic and should be replaced or supplemented with
    ARIA-NBV examples covering `PoseTW`, `CameraTW`, tensor shape/dtype/frame
    contracts, config factories, rollout/Zarr persistence boundaries, and
    invalidity reason contracts.

## Should Be Included

- A "single owner" rule: all docstring-relevant guidance lives under
  `.agents/skills/python-docstrings/`; other references only link to it.
- A "Quarto/Quartodoc Contract" section capturing the local `_quarto.yml`
  settings that affect docstring writing.
- A "Generated API Verification" section:
  `ruff format <file>`, `ruff check <file>`,
  `./scripts/quarto_generate_api_docs.sh` for public API docstrings, and
  targeted `quarto render` for nontrivial generated pages.
- A "Examples" rule preferring `Examples:` and non-executing doctest or
  Markdown code blocks in docstrings.
- A "Cross References" rule saying Markdown links/backticks are default
  because interlinks/autolink are not configured locally.
- Config/datamodel rules for attribute docstrings, meaningful defaults,
  units, ranges, persistence semantics, and `setup_target()` behavior.
- ARIA-NBV-specific examples for geometry, data views, rollouts, invalidity,
  config-as-factory, and tensor contracts.
- A note that `scripts/audit_docstrings.py` is a triage aid rather than a docs
  renderer or parser validator.

## Boundaries

This report is evidence for a follow-up implementation pass. It does not edit
tracked guidance files because the originating workflow was
`best-practice-research`, which is read-only by contract.
