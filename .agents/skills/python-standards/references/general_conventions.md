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
- Call config `.setup_target()` once per owning lifecycle at a composition root,
  such as a CLI entrypoint, Lightning setup/factory, pipeline orchestrator, or
  application controller. Inject the constructed dependency into domain,
  `forward`, and scoring hot paths; those calls do not construct it internally.
- Keep single-consumer private helpers local and inline trivial helpers. Promote
  behavior only after multiple demonstrated consumers establish the lowest
  shared domain owner; avoid hypothetical generic utility buckets.
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

## Config-as-Factory And Lifecycle

The composition root owns reuse and teardown for the object it constructs.
Reuse an object for the root's declared cache, request, stage, trainer, or
pipeline lifetime; close or release it at that same boundary when the object has
an explicit lifecycle. Framework-owned device, rank, checkpoint, and worker
hooks may construct or reconstruct objects when the framework defines that
lifecycle. Keep that exception in the framework adapter and document why normal
injection cannot own it.

## Validators
Use `field_validator` and `model_validator` when validation logic belongs in the config rather than in runtime classes.

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
