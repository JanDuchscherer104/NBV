# Docstring Sections

Choose a concise summary line plus only the sections that add information:
`Args:`, `Returns:`, `Yields:`, `Attributes:`, `Examples:`, `Notes:`, or
`Theory:`. Document semantics, invariants, side effects, units, shapes,
coordinate frames, ownership, lifecycle, theory, and boundary expectations;
do not restate obvious type hints.

## Section Selection

- Start with a concise summary that describes behavior, not the symbol name.
- Use Google-style sections only when they add information. Explain purpose,
  role, behavior, invariants, units, shapes, frames, ownership, mutation,
  lifecycle, and sequencing rather than restating names or type hints.
- Use `Attributes:` for contract-bearing state. Public dataclasses, Pydantic
  models, DTOs, configs, and typed payloads need meaningful field docs.
- Use `Yields:` for streaming APIs and `Examples:` for easy-to-misuse APIs.
  Use `Notes:` or `Theory:` only when they materially improve correct usage;
  link complex definitions to the thesis owner instead of copying them.
- Avoid `Raises:` unless callers genuinely need to rely on or handle the failure
  contract. Remove empty sections and filler prose.

## Contract Notation

- Use standard Python and framework annotations (`Tensor`, `ndarray`, and
  project types); record shapes, frames, units, and support semantics in prose.
  When shape or dtype matters, add the shape-style token, for example:
  `points ``Tensor["N 3", float32]``: ...`. See
  [tensor shapes](./tensor-shapes.md).
- Use Markdown math (`$...$`, `$$...$$`) for Quarto equations and raw Python
  docstrings (`r"""..."""`) when LaTeX backslashes appear.
- Use Sphinx/Python-domain roles (`:mod:`, `:class:`, `:func:`, `:meth:`,
  `:attr:`, and `:py:*:` forms) for local API symbols. The Quarto role filter
  resolves them against the generated `objects.json` inventory; see
  [cross-references](./cross-references.md).

## Boundary Cases

Use `aria-grill` before documenting a genuinely unsettled boundary; this skill
records the resulting source-level contract without duplicating design. Keep
private-helper docs concise unless their invariant or failure mode is needed by
callers; avoid boilerplate and long theory blocks for simple APIs.
