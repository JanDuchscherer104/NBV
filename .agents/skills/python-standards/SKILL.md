---
name: python-standards
description: Apply ARIA-NBV Python conventions and write concise, contract-focused docstrings for modules, public classes, functions, methods, protocols, config models, DTOs, wrappers, and streaming or session APIs. Use for typing, configuration, DTO, docstring, shape, lifecycle, cross-reference, and Python API-contract work.
metadata:
  mode: implementation
  not_when:
    - "public docs, Quarto, or Typst prose not generated from Python APIs"
    - "implementation behavior changes where Python standards are incidental"
    - "large API redesign before the target interface is stable"
  handoff_to:
    - "aria-grill for unsettled module, interface, or domain-model decisions before implementation"
    - "nearest docs guide for public narrative, Quarto, or Typst documentation"
    - "nearest package guide for frame, unit, or tensor-shape semantics"
    - "simplification for behavior-preserving API cleanup before documentation"
  evidence_required:
    - "public API or cross-module contract being changed or documented"
    - "local package owner and any needed generated-doc cross-reference"
    - "targeted format, lint, test, or generated-doc evidence"
  applies_to:
    - "aria_nbv/aria_nbv/**/*.py"
  triggers:
    - "Python standards"
    - "typing"
    - "config model"
    - "DTO"
    - "docstring"
    - "API docs"
    - "shape docs"
    - "contract docs"
  must_read:
    - "aria_nbv/AGENTS.md"
    - ".agents/skills/python-standards/references/general_conventions.md"
    - ".agents/skills/python-standards/references/tensor-shapes.md"
    - ".agents/skills/python-standards/references/theory-rich-docstrings.md"
    - ".agents/skills/python-standards/references/config-datamodel-fields.md"
    - ".agents/skills/python-standards/references/quartodoc-contract.md"
    - ".agents/skills/python-standards/references/cross-references.md"
  canonical_sources:
    - "aria_nbv/AGENTS.md#completion-criteria"
    - "aria_nbv/pyproject.toml"
    - ".agents/skills/python-standards/references/general_conventions.md"
    - ".agents/skills/python-standards/references/tensor-shapes.md"
    - ".agents/skills/python-standards/references/theory-rich-docstrings.md"
    - ".agents/skills/python-standards/references/config-datamodel-fields.md"
    - ".agents/skills/python-standards/references/quartodoc-contract.md"
    - ".agents/skills/python-standards/references/cross-references.md"
  context7_refs:
    - "/pytorch/pytorch"
    - "/pydantic/pydantic"
  tool_refs:
    - "mcp__MCP_DOCKER.resolve_library_id"
    - "mcp__MCP_DOCKER.get_library_docs"
    - "mcp__code_index.search_code_advanced"
    - "mcp__code_index.get_symbol_body"
  verification:
    - "ruff format <file>"
    - "ruff check <file>"
    - "cd aria_nbv && uv run pytest <path>"
    - "./scripts/quarto_generate_api_docs.sh when generated API docs are affected"
---

# Python Standards

## OMX Integration

OMX can schedule Python-standard or docstring work as part of implementation
cleanup, but this skill supplies only Python API-contract guidance. Return the
changed public surface, convention evidence, and targeted lint, test, or docs
verification.

## General Python Conventions

Read [references/general_conventions.md](./references/general_conventions.md)
for typing, paths, config-as-factory behavior, runtime setup, logging, and
project wrapper conventions. Executable requirements remain owned by source,
tests, formatter, linter, and type configuration. ARIA-NBV domain semantics
remain with the nearest package owner.

## Docstring Overview

Write or refactor Python docstrings as API contracts. Prefer concise,
high-information docstrings that explain behavior, invariants, units, shapes,
ownership, sequencing, theory, and boundary semantics instead of paraphrasing
type hints. This skill owns all ARIA-NBV docstring preferences, including
field docs, tensor-shape display, examples,
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
6. For tensor values, use ordinary framework annotations and include the
   shape-style docstring token when shape or dtype matters:
   `points ``Tensor["N 3", float32]``: ...`. See
   [references/tensor-shapes.md](./references/tensor-shapes.md).
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
  per-field docstrings. Explain conceptual or theoretical meaning for fields
  whose role cannot be inferred from the type and name alone.
- Document a non-straightforward private function or method when its invariant,
  transformation, state transition, or failure mode is needed to safely change
  its caller. Keep trivial private helpers concise.
- Use standard Python annotations plus framework types (`Tensor`, `ndarray`,
  and project types). Do not introduce Jaxtyping or another runtime shape-type
  system; record shapes, frames, units, and support semantics in docstrings.
- Use `aria-grill` before documenting a genuinely unsettled boundary. Aria
  Grill may progressively invoke external architecture, interface, or domain-
  modeling capabilities; this skill records the resulting source-level
  contract and does not duplicate those design methods.
- Use `Yields:` for generators, iterators, and streaming-style APIs.
- Use `Examples:` for public APIs that are easy to misuse.
- Use `Notes:` or `Theory:` when they materially help correct usage. A complex
  geometry, RRI, rollout, reconstruction, or learning API may state one
  contract-defining equation, then link to the thesis owner for its definition
  and full derivation. Do not copy thesis prose or mathematical definitions.
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
from torch import Tensor


def compute_rri(
    points_t: Tensor,
    points_q: Tensor,
    gt_mesh_vertices: Tensor,
    gt_mesh_faces: Tensor,
) -> tuple[Tensor, Tensor]:
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

- [General Python conventions](./references/general_conventions.md)
- [Tensor and NumPy shapes](./references/tensor-shapes.md)
- [Theory-rich docstrings](./references/theory-rich-docstrings.md)
- [Config and datamodel fields](./references/config-datamodel-fields.md)
- [Quartodoc contract](./references/quartodoc-contract.md)
- [Cross-references](./references/cross-references.md)
