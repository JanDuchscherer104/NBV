# General Python Conventions

Use this disclosed reference for generic typing, runtime, and configuration
practice. `aria_nbv/AGENTS.md` owns ARIA-specific types, geometry, logging, and
package boundaries; formatter, linter, type configuration, source, and tests
remain the executable owners.

## Core Rules
- Config classes should inherit from `BaseConfig` where appropriate.
- Instantiate runtime objects through config `.setup_target()` factories instead of constructing them ad hoc.
- Prefer vectorized implementations over functional helpers, comprehensions, or explicit loops when readability remains acceptable.
- All path-handling should be done through `PathConfig` objects that validate existence and absoluteness. Use `pathlib.Path` for filesystem paths.
- Prefer `Enum` for categorical values and `match-case` when it improves multi-branch clarity.
- Prefer existing project and dependency seams before reimplementing
  infrastructure.
- Route public API documentation and tensor-shape prose through this skill's
  focused references; route coordinate-frame semantics to the owning package.

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

## Do Not
- Do not use `Field(default=<callable>)` when you mean `default_factory`.
- Do not leave public signatures untyped.
