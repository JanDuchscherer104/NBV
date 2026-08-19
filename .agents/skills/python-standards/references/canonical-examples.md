# Canonical Python Docstring Examples

Load only the example matching the public contract being written. These examples
demonstrate composition, theory, field semantics, and sequencing; exact source,
tests, and package owners still decide the real API.

## Module Docstring

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

## Theory-Rich Function Docstring

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

## Config Or Datamodel Field Docs

```python
class OracleRRIConfig(TargetConfig["OracleRRI"]):
    """Config-as-factory wrapper for oracle RRI computation."""

    fusion_voxel_size_m: float = Field(default=0.0, ge=0.0)
    """Optional deterministic voxel-fusion size for ``P_t`` and ``P_t ∪ P_q``."""

    fusion_max_points: int | None = Field(default=None, ge=1)
    """Optional deterministic point cap applied after voxel fusion."""
```

## Sequencing Example

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
