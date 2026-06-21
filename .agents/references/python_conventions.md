# Python Conventions

This file is the long-form reference for Python typing, docstring, and config
conventions in `aria_nbv/`. Binding short-form rules live in
`aria_nbv/AGENTS.md`.

## Core Rules
- Config classes should inherit from `BaseConfig` where appropriate.
- Instantiate runtime objects through config `.setup_target()` factories instead of constructing them ad hoc.
- Prefer vectorized implementations over functional helpers, comprehensions, or explicit loops when readability remains acceptable.
- All path-handling should be done through `PathConfig` objects that validate existence and absoluteness. Use `pathlib.Path` for filesystem paths.
- Prefer `Enum` for categorical values and `match-case` when it improves multi-branch clarity.
- Use existing utilities from `efm3d`, `atek`, and `projectaria_tools` before reimplementing infrastructure.
- Use `PoseTW` for poses and `CameraTW` for cameras unless a subsystem explicitly requires a different camera type.
- Document tensor shapes and coordinate frames when they are not obvious from the surrounding code.

## Typing
- Type all public signatures and prefer modern builtins such as `list[str]` and `dict[str, Any]`.
- Use `TYPE_CHECKING` guards for imports only needed in annotations.
- Use `Literal` for constrained string values when the set of values is small and stable.
- Keep helper dataclasses and typed containers explicit rather than passing around untyped dict payloads.

Example:
```python
from torch import Tensor

def compute_rri(
    P_t: Tensor,
    P_q: Tensor,
    gt_mesh_vertices: Tensor,
    gt_mesh_faces: Tensor,
) -> tuple[Tensor, Tensor]:
    """Compute Relative Reconstruction Improvement for a candidate view.

    Args:
        P_t (Tensor["N 3", float32]): Current reconstruction point cloud.
        P_q (Tensor["M 3", float32]): Candidate-view point cloud.
        gt_mesh_vertices (Tensor["V 3", float32]): Ground-truth mesh vertices.
        gt_mesh_faces (Tensor["F 3", int64]): Ground-truth mesh face indices.

    Returns:
        Tuple[Tensor, Tensor]: Main output and auxiliary diagnostics.
    """
    ...
```

## Attribute Docstrings
Prefer attribute docstrings on config and dataclass fields instead of `Field(..., description=...)` for ordinary primitive fields.

```python
class MyConfig(BaseConfig):
    my_bool: bool = True
    """Whether to enable the awesome feature."""
```

```python
class ExperimentConfig(BaseConfig):
    trainer_config: TrainerFactoryConfig
    """Configuration for the trainer factory (optimizer, scheduler, devices)."""
    module_config: VinLightningModuleConfig
    """Configuration for the model module (architecture, heads, loss weights)."""
    datamodule_config: VinDataModuleConfig
    """Configuration for data ingestion (datasets, transforms, batch sizing)."""

    def setup_target(self) -> tuple[Trainer, LightningModule, LightningDataModule]:
        trainer = self.trainer_config.setup_target()
        module = self.module_config.setup_target()
        datamodule = self.datamodule_config.setup_target()
        return trainer, module, datamodule
```

## Google-Style Docstrings
All public methods and functions should use Google-style docstrings. Prefer concise descriptions plus explicit `Args:` / `Returns:` sections over prose-heavy blocks.

Quartodoc renders these docstrings through Quarto. Use Markdown math (`$...$`
and `$$...$$`) and backtick code references; avoid Sphinx/RST math, class, and
function roles unless the generated page has been checked.
Use raw docstrings (`r"""..."""`) when LaTeX backslashes are present.

## Data Views and Typed Containers
Typed view objects and prediction containers should make their contracts explicit in field docstrings.

```python
@dataclass(slots=True)
class EfmCameraView:
    """Camera stream in EFM schema.

    Attributes:
        images: ``Tensor["F C H W", float32]`` normalized to ``[0, 1]``.
        calib: `CameraTW` storing per-frame intrinsics/extrinsics.
    """

    images: Tensor
    """``Tensor["F C H W", float32]`` normalized camera images in Aria RDF frame."""
    calib: CameraTW
    """Per-frame camera intrinsics/extrinsics (`CameraTW.tensor` shape ``(F, 34)``)."""
```

## Config-as-Factory and Validators
Runtime objects are created through config `.setup_target()` methods. Use `field_validator` and `model_validator` when validation logic belongs in the config rather than in runtime classes.

```python
from pydantic import Field, field_validator, model_validator

class MyComponentConfig(BaseConfig["MyComponent"]):
    target: type["MyComponent"] = Field(default_factory=lambda: MyComponent, exclude=True)
    """Factory target that `setup_target()` instantiates."""

    learning_rate: float = Field(default=1e-3, gt=0)
    """Learning rate for the optimizer."""
    batch_size: int = Field(default=32, gt=0)
    """Mini-batch size used by training and evaluation loops."""
```

## Console Logging
Use `Console` from `aria_nbv.utils` for structured logging.

```python
from aria_nbv.utils import Console

console = Console.with_prefix(self.__class__.__name__, 'setup_target')
console.set_verbose(self.verbose).set_debug(self.is_debug)

console.log('Starting setup...')
console.warn('Deprecated parameter')
console.error('Invalid configuration')
console.dbg('Internal state: ...')
console.plog(complex_obj)
```

## Do Not
- Do not use `Field(default=<callable>)` when you mean `default_factory`.
- Do not pass raw matrices where `PoseTW` or `CameraTW` are expected.
- Do not leave public signatures untyped.
- Do not hide shape or frame assumptions in implicit conventions when a short field docstring can state them directly.
