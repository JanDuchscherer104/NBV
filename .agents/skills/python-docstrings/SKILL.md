---
name: python-docstrings
description: Write and refactor concise, contract-focused Python docstrings for modules, public classes, functions, methods, protocols, config models, DTOs, wrappers, and streaming or session APIs. Use when Python docstrings are missing, sparse, misleading, or need better cross-references, examples, units, shapes, lifecycle notes, or boundary semantics.
metadata:
  mode: implementation
  not_when:
    - "public docs, Quarto, or Typst prose not generated from Python APIs"
    - "implementation behavior changes where docstrings are incidental"
    - "large API redesign before the target interface is stable"
  handoff_to:
    - "docs-curator for public narrative, Quarto, or Typst documentation"
    - "nbv-geometry-contracts for frame, unit, or tensor-shape semantics"
    - "simplification for behavior-preserving API cleanup before documentation"
  evidence_required:
    - "public API or cross-module contract being documented"
    - "local package owner and any needed generated-doc cross-reference"
    - "targeted ruff check for touched Python docstring files"
  applies_to:
    - "aria_nbv/aria_nbv/**/*.py"
  triggers:
    - "docstring"
    - "API docs"
    - "shape docs"
    - "contract docs"
  must_read:
    - "aria_nbv/AGENTS.md"
    - ".agents/skills/python-docstrings/references/type-shape-jaxtyping.md"
    - ".agents/skills/python-docstrings/references/theory-rich-docstrings.md"
    - ".agents/skills/python-docstrings/references/config-datamodel-fields.md"
    - ".agents/skills/python-docstrings/references/quartodoc-contract.md"
    - ".agents/skills/python-docstrings/references/cross-references.md"
  canonical_sources:
    - "aria_nbv/AGENTS.md#completion-criteria"
    - ".agents/skills/python-docstrings/references/type-shape-jaxtyping.md"
    - ".agents/skills/python-docstrings/references/theory-rich-docstrings.md"
    - ".agents/skills/python-docstrings/references/config-datamodel-fields.md"
    - ".agents/skills/python-docstrings/references/quartodoc-contract.md"
    - ".agents/skills/python-docstrings/references/cross-references.md"
  context7_refs:
    - "/pytorch/pytorch"
    - "/pydantic/pydantic"
  tool_refs:
    - "mcp__code_index.search_code_advanced"
    - "mcp__code_index.get_symbol_body"
  verification:
    - "ruff format <file>"
    - "ruff check <file>"
    - "./scripts/quarto_generate_api_docs.sh when generated API docs are affected"
---

# Python Docstrings

## OMX Integration

OMX can schedule docstring work as part of implementation cleanup, but this
skill supplies only Python API-contract guidance. Return the documented public
surface, convention evidence, and targeted lint/doc verification.

## Overview

Write or refactor Python docstrings as API contracts. Prefer concise,
high-information docstrings that explain behavior, invariants, units, shapes,
ownership, sequencing, theory, and boundary semantics instead of paraphrasing
type hints. This skill owns all ARIA-NBV docstring preferences, including
field docs, shape display, Jaxtyping-facing docstring style, examples,
cross-references, equations, and Quartodoc rendering constraints.

## Workflow

1. Read the package owner and this skill before editing Python docstrings.
2. Identify the public API surface. Cover public modules, public classes,
   public functions, public methods, and meaningful typed fields or properties
   that form an external or cross-module contract.
3. Choose sections deliberately. Default to a summary line plus only the
   sections that add information: `Args:`, `Returns:`, `Yields:`,
   `Attributes:`, `Examples:`, `Notes:` or `Theory:`.
4. Write behavioral contracts. Document semantics, invariants, side effects,
   units, shapes, coordinate frames, ownership, lifecycle, theory, and boundary
   expectations. Do not restate obvious type hints.
5. Cross-reference internal symbols and external sources with the local
   Quartodoc role contract or Quarto-compatible Markdown. See
   [references/cross-references.md](./references/cross-references.md).
6. For tensor values, use Jaxtyping annotations whenever possible and still
   include the shape-style docstring token when shape or dtype matters:
   `points ``Tensor["N 3", float32]``: ...`. See
   [references/type-shape-jaxtyping.md](./references/type-shape-jaxtyping.md).
7. Trim boilerplate. Remove empty sections and filler prose. Avoid `Raises:`
   unless callers genuinely need to rely on or handle the failure contract.
8. Optionally audit. Run [scripts/audit_docstrings.py](./scripts/audit_docstrings.py)
   to find missing or suspiciously short docstrings before or after a refactor.

## Writing Rules

- Start with a concise summary line that describes behavior, not the symbol
  name.
- Use Google-style sections, but omit sections that do not add information.
- Make module docstrings explain purpose, main contents, conceptual model, and
  responsibility boundaries.
- Make important class docstrings explain role, theoretical meaning, and when
  to use the abstraction.
- Make function and method docstrings explain behavior and semantics, not just
  parameters.
- Prefer dense explanation over long prose. Prioritize invariants,
  preconditions, coordinate frames, units, shapes, mathematical definitions,
  normalization terms, ownership, mutation semantics, persistence boundaries,
  and sequencing expectations.
- Use `Attributes:` when instance state is part of the contract. Public
  dataclasses, Pydantic models, DTOs, configs, and typed payloads also need
  per-field docstrings.
- Use `Yields:` for generators, iterators, and streaming-style APIs.
- Use `Examples:` for public APIs that are easy to misuse.
- Use `Notes:` or `Theory:` when they materially help correct usage. Complex
  geometry, RRI, rollout, reconstruction, and learning APIs should include the
  most important equations when those equations define the contract.
- Use Markdown math (`$...$`, `$$...$$`) for equations that should render in
  generated Quarto API pages; use raw Python docstrings (`r"""..."""`) when
  LaTeX backslashes appear.
- Use Sphinx/Python-domain roles for local API symbols so docstrings remain
  readable in VS Code and link in Quarto API pages: `:mod:`, `:class:`,
  `:func:`, `:meth:`, `:attr:`, and their explicit `:py:*:` forms. ARIA-NBV's
  Quarto role filter resolves these roles against `docs/objects.json`; see
  [references/cross-references.md](./references/cross-references.md).
- Avoid repeating the symbol name in prose, converting every type hint into a
  sentence, adding every section mechanically, or inserting long theory blocks
  for simple helpers.

## Canonical Examples

Module docstring:

```python
r"""High-level oracle RRI computation orchestrator.

This module wires candidate point clouds, point-mesh distance primitives, and
:class:`OracleRRIConfig` into one target-aware RRI scorer. It owns score
orchestration only; candidate sampling belongs to :mod:`aria_nbv.pose_generation`
and depth rendering belongs to :mod:`aria_nbv.rendering`.

The implemented scalar score is

$$
\mathrm{RRI}(q)=
\frac{\Delta(P_t, M)-\Delta(P_t \cup P_q, M)}
     {\max(\Delta(P_t, M), \epsilon)}.
$$
"""
```

Theory-rich function docstring:

```python
from jaxtyping import Float, Int
from torch import Tensor


def compute_rri(
    points_t: Float[Tensor, "N_t 3"],
    points_q: Float[Tensor, "N_q 3"],
    gt_mesh_vertices: Float[Tensor, "V 3"],
    gt_mesh_faces: Int[Tensor, "F 3"],
) -> tuple[Float[Tensor, "N_q"], Float[Tensor, "D"]]:
    r"""Compute candidate-view Relative Reconstruction Improvement.

    Args:
        points_t ``Tensor["N_t 3", float32]``: Current target reconstruction
            points in world frame, metres.
        points_q ``Tensor["N_q 3", float32]``: Candidate-view points in world
            frame, metres.
        gt_mesh_vertices ``Tensor["V 3", float32]``: Ground-truth mesh
            vertices in world frame, metres.
        gt_mesh_faces ``Tensor["F 3", int64]``: Triangle vertex indices into
            `gt_mesh_vertices`.

    Returns:
        Tuple[Tensor, Tensor]: RRI scores and diagnostics.
            - rri ``Tensor["N_q", float32]``: Candidate-point improvement
              values after normalization and validity masking.
            - diagnostics ``Tensor["D", float32]``: Diagnostic terms for
              current distance, candidate distance, and normalization.

    Theory:
        RRI scores how much candidate evidence reduces target reconstruction
        error relative to the current reconstruction:

        $$
        \mathrm{RRI}(q)=
        \frac{D(P_t, M)-D(P_t \cup P_q, M)}
             {\max(D(P_t, M), \epsilon)}.
        $$

        `P_t` is the current target point set, `P_q` is the candidate-view point
        set, and `M` is the ground-truth target mesh. Invalid candidates are
        masked before this value is used as a training target.
    """
```

Config or datamodel field docs:

```python
class OracleRRIConfig(TargetConfig["OracleRRI"]):
    """Config-as-factory wrapper for oracle RRI computation."""

    fusion_voxel_size_m: float = Field(default=0.0, ge=0.0)
    """Optional deterministic voxel-fusion size for ``P_t`` and ``P_t ∪ P_q``."""

    fusion_max_points: int | None = Field(default=None, ge=1)
    """Optional deterministic point cap applied after voxel fusion."""
```

Sequencing example:

```python
def run(self, sample: EfmSnippetView) -> OracleRriSample:
    """Run candidate generation, depth rendering, backprojection, and RRI scoring.

    Args:
        sample: EFM snippet with semi-dense points, camera calibration, target
            metadata, and loaded GT mesh tensors.

    Returns:
        :class:`OracleRriSample` containing candidates, rendered depths,
        backprojected candidate point clouds, and `RriResult` labels.

    Examples:
        >>> labeler = OracleRriLabeler(OracleRriLabelerConfig())
        >>> labeled = labeler.run(sample)
        >>> labeled.rri.rri.shape
        torch.Size([num_candidates])
    """
```

## References

- [Type, shape, and Jaxtyping](./references/type-shape-jaxtyping.md)
- [Theory-rich docstrings](./references/theory-rich-docstrings.md)
- [Config and datamodel fields](./references/config-datamodel-fields.md)
- [Quartodoc contract](./references/quartodoc-contract.md)
- [Cross-references](./references/cross-references.md)
