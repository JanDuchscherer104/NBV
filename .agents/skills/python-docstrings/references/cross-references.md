# Cross-References

Use Sphinx/Python-domain roles for local ARIA-NBV API symbols. These roles are
readable in VS Code/Pylance hovers and are resolved in Quarto API pages by the
local `docs/_extensions/aria-python-roles/aria-python-roles.lua` filter against
Quartodoc's generated `docs/objects.json` inventory.

Preferred local roles:

- `:mod:`aria_nbv.data_handling`` or `:py:mod:`aria_nbv.data_handling`` for
  modules and packages.
- `:class:`EfmSnippetView`` or `:py:class:`aria_nbv.data_handling.EfmSnippetView``
  for classes.
- `:func:`infer_semidense_bounds`` or
  `:py:func:`aria_nbv.data_handling.infer_semidense_bounds`` for functions.
- `:meth:`EfmSnippetView.to`` or
  `:py:meth:`aria_nbv.data_handling.EfmSnippetView.to`` for methods.
- `:attr:`EfmSnippetView.scene_id`` or
  `:py:attr:`aria_nbv.data_handling.EfmSnippetView.scene_id`` for attributes,
  fields, properties, and documented constants emitted by Quartodoc as
  `attribute`.
- `:data:` / `:py:data:` may be used for documented constants; ARIA-NBV maps
  them to the local `attribute` inventory role because Quartodoc currently emits
  package constants as attributes.

Use fully qualified names whenever a short symbol may be ambiguous across the
package. Short names are acceptable on generated API pages when the target is
under the current module/class context or is unique in `docs/objects.json`.

External API symbols are not resolved by the local ARIA inventory filter unless
they also appear in `docs/objects.json`. Use Markdown links for external docs,
or add and verify external inventory support before using external intersphinx
roles such as `:external+torchmetrics:py:class:`.

## Preferred Internal References

- Use Sphinx roles for local link-worthy API symbols: `:class:`VinOfflineDataset``,
  `:meth:`OracleRRI.score``, `:mod:`aria_nbv.rri_metrics``, and
  `:data:`OFFLINE_DATASET_VERSION``.
- Use plain backticks for symbol mentions that should not be links.
- Use Markdown links only when the target is stable and helpful:
  `[RRI theory](../../contents/theory/rri_theory.qmd)`.
- Use Quarto cross-reference syntax such as `@eq-rri` only in `.qmd` pages
  that own the label. Do not introduce API-docstring-local labels unless the
  generated page has been rendered and checked.
- Prefer module/class docstrings for dense cross-surface contracts; avoid
  repeating the same link on every method.

Examples:

- ``Return a :class:`RriResult` with per-candidate RRI and distance diagnostics.``
- ``Call :meth:`OracleRRI.score` after candidate depth backprojection.``
- ``Keep immutable offline-store semantics in :mod:`aria_nbv.data_handling`.``
- ``Use :class:`VinOfflineDataset` for VIN training samples, not raw EFM dicts.``
- ``Respect :class:`CandidateViewGeneratorConfig` when changing sampling bounds.``

## Math

Use Markdown math:

- Inline: `$P_t \cup P_q$`
- Display:

```text
$$
\mathrm{RRI}(q)=\frac{D(P_t,M)-D(P_t\cup P_q,M)}{D(P_t,M)+\epsilon}.
$$
```

Use raw docstrings when LaTeX backslashes appear:

```python
r"""Compute improvement $D(\mathcal{P}_t,M)-D(\mathcal{P}_{t\cup q},M)$."""
```

## External References

Use Markdown links for external material that is not a resolvable API symbol:

- API docs
- research papers
- tutorials
- conceptual references

Examples:

- `Point-mesh distances use [PyTorch3D point-mesh distance primitives](https://pytorch3d.org/docs/).`
- `Tensor shapes and dtypes are stated in the field docstring.`

Do not leave unresolved roles for external targets in rendered Quarto pages.
Keep external links selective and relevant.
