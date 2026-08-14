# Python Conventions

This file owns the generic non-docstring Python typing, runtime, config, and
upstream-reuse conventions for `aria_nbv/`. Python docstring rules, including
field docs, tensor-shape rendering, equations, examples, references, and
Quartodoc behavior, live in the `python-standards` skill entrypoint and its
focused references. Executable formatter/linter configuration lives in
`aria_nbv/pyproject.toml`; nearest source and tests own behavior and local API
detail.

## Core Rules
- Config classes should inherit from `BaseConfig` where appropriate.
- Instantiate runtime objects through config `.setup_target()` factories instead of constructing them ad hoc.
- Prefer vectorized implementations over functional helpers, comprehensions, or explicit loops when readability remains acceptable.
- All path-handling should be done through `PathConfig` objects that validate existence and absoluteness. Use `pathlib.Path` for filesystem paths.
- Prefer `Enum` for categorical values and `match-case` when it improves multi-branch clarity.
- Use existing utilities from `efm3d`, `atek`, and `projectaria_tools` before reimplementing infrastructure.
- Use `PoseTW` for poses and `CameraTW` for cameras unless a subsystem explicitly requires a different camera type.
- Route public API documentation, tensor-shape prose, and coordinate-frame
  prose to the `python-standards` skill.

## Typing
- Type all public signatures and prefer modern builtins such as `list[str]` and `dict[str, Any]`.
- Use `TYPE_CHECKING` guards for imports only needed in annotations.
- Use `Literal` for constrained string values when the set of values is small and stable.
- Keep helper dataclasses and typed containers explicit rather than passing around untyped dict payloads.

## Config-as-Factory and Validators
Runtime objects are created through config `.setup_target()` methods. Use `field_validator` and `model_validator` when validation logic belongs in the config rather than in runtime classes.

```python
from pydantic import Field, field_validator, model_validator

class MyComponentConfig(BaseConfig["MyComponent"]):
    target: type["MyComponent"] = Field(default_factory=lambda: MyComponent, exclude=True)

    learning_rate: float = Field(default=1e-3, gt=0)
    batch_size: int = Field(default=32, gt=0)
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
