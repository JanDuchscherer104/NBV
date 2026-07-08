# Type, Shape, And Jaxtyping

## Defaults

- Always use Jaxtyping for tensor-heavy public signatures when it can be
  applied without breaking runtime annotation resolution.
- Also always include the ARIA-NBV shape-style token in `Args:`, `Returns:`,
  `Yields:`, `Attributes:`, and per-field docstrings when shape or dtype is
  part of the contract:
  `images ``Tensor["F C H W", float32]``: normalized RGB images.`
- Use `TYPE_CHECKING` imports for type-only dependencies when annotations are
  not needed at runtime. Do not hide imports needed by Pydantic validation,
  `model_rebuild()`, runtime dispatch, or Quartodoc static/runtime discovery.

## Jaxtyping Signatures

Prefer real annotations like:

```python
from jaxtyping import Float, Int
from torch import Tensor

def compute_rri(
    points_t: Float[Tensor, "N_t 3"],
    points_q: Float[Tensor, "N_q 3"],
    gt_mesh_vertices: Float[Tensor, "V 3"],
    gt_mesh_faces: Int[Tensor, "F 3"],
) -> tuple[Float[Tensor, "N_q"], Float[Tensor, "D"]]:
    ...
```

Use `Float`, `Int`, and `Bool` when the dtype family matters. Use exact aliases
such as `Float32` or `Int64` only when exact dtype is enforced or central to
the contract. Use one space-separated shape string: `"B C H W"`, `"N_t 3"`,
`"..."`, or `""` for scalars.

## Docstring Shape Style

The docstring must still expose shape and dtype where they matter:

```python
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
            - rri ``Tensor["N_q", float32]``: Relative improvement per
              candidate point.
            - diagnostics ``Tensor["D", float32]``: Diagnostic terms used to
              audit distance, masking, and normalization.
    """
```

Use the docstring token to communicate reader-facing contracts; use the
Jaxtyping annotation to communicate checker/runtime-facing contracts. They are
intentionally redundant for tensor shape contracts because generated docs,
reviews, and agents read docstrings even when annotations are abbreviated by
renderers.

## Avoid

- `points (Tensor["N 3", float32]): ...`
- mixed shape formats such as `Tensor["B", "C", "H", "W"]`
- unquoted fixed axes such as `Tensor[N, 3]`
- omitting frame, units, or normalization when those are needed for correct
  interpretation
