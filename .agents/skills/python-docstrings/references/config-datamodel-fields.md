# Config And Datamodel Fields

Public dataclasses, Pydantic models, config objects, DTOs, typed samples, and
prediction containers need field-level documentation.

## Rules

- Add an inline field docstring after each meaningful public field.
- Include tensor shape and dtype with the ARIA-NBV shape-style token whenever
  the field stores tensor data.
- Include units, coordinate frames, valid ranges, lifecycle, persistence, and
  default semantics when they matter.
- Use class-level `Attributes:` to summarize grouped state, but keep the inline
  field docstring as the per-field source.
- Do not use `Field(..., description=...)` as the primary repo-owned field
  documentation. `Field` descriptions are schema metadata, not a replacement
  for source-level docs.

## Example

```python
@dataclass(slots=True)
class EfmCameraView:
    """Camera stream normalized into the EFM schema.

    Attributes:
        images: RGB frames normalized to `[0, 1]`.
        calib: Per-frame camera intrinsics and extrinsics.
    """

    images: Float[Tensor, "F C H W"]
    """``Tensor["F C H W", float32]`` normalized RGB images in Aria RDF frame."""

    calib: CameraTW
    """Per-frame `CameraTW` calibration; `CameraTW.tensor` has shape ``(F, 34)``."""
```

For Pydantic configs, keep validation constraints in `Field(...)` and explain
human-facing semantics in the field docstring:

```python
class TrainingConfig(BaseConfig):
    batch_size: int = Field(default=32, gt=0)
    """Mini-batch size used by training and validation dataloaders."""
```
