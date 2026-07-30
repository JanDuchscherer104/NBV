# Tensor And NumPy Shapes

## Defaults

- Use ordinary ``torch.Tensor`` and ``numpy.ndarray`` annotations. Shape and
  dtype belong in docstrings because standard Python annotations do not encode
  those runtime facts.
- Include the ARIA-NBV shape-style token in `Args:`, `Returns:`, `Yields:`,
  `Attributes:`, and per-field docstrings whenever shape or dtype matters:
  `images ``Tensor["F C H W", float32]``: normalized RGB images.`
- Use `TYPE_CHECKING` imports for type-only dependencies when annotations are
  not needed at runtime. Do not hide imports needed by Pydantic validation,
  `model_rebuild()`, runtime dispatch, or Quartodoc discovery.

## Ordinary Signatures

Prefer direct framework annotations:

```python
import numpy as np
from torch import Tensor


def compute_rri(
    points_t: Tensor,
    points_q: Tensor,
    gt_mesh_vertices: Tensor,
    gt_mesh_faces: Tensor,
    sample_ids: np.ndarray,
) -> tuple[Tensor, Tensor]:
    ...
```

Use `Tensor` for PyTorch values and `np.ndarray` for NumPy values. Keep exact
shape, dtype, frame, unit, and support semantics in the docstring rather than
introducing a second annotation system.

## Docstring Shape Style

```python
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
            - rri ``Tensor["N_q", float32]``: Relative improvement per
              candidate point.
            - diagnostics ``Tensor["D", float32]``: Terms used to audit
              distance, masking, and normalization.
    """
```

Use one space-separated shape string such as `"B C H W"`, `"N_t 3"`,
`"..."`, or `""` for scalars. For NumPy arrays, use the analogous token
``ndarray["N 3", float32]``.

## Avoid

- encoding shape in a non-standard runtime annotation;
- `points (Tensor["N 3", float32]): ...`;
- mixed shape formats such as `Tensor["B", "C", "H", "W"]`;
- unquoted fixed axes such as `Tensor[N, 3]`;
- omitting frame, units, support, or normalization when needed for correct use.
