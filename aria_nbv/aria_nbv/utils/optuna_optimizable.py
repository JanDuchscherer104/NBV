"""Optuna-friendly search space helpers.

This mirrors the utility layer from ``external/doc_classifier`` so aria_nbv
configs can declare Optuna search spaces declaratively via ``optimizable_field``.

The core idea is:

- attach an `Optimizable` instance to a Pydantic ``Field`` via
  ``json_schema_extra={"optimizable": ...}``,
- have an Optuna-aware orchestration layer traverse the config tree and apply
  trial suggestions before constructing runtime objects.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from enum import Enum
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

if TYPE_CHECKING:
    import optuna


class Optimizable(BaseModel, Generic[T]):
    """Declarative description of an optimisable parameter.

    The class intentionally avoids importing Optuna at runtime so the rest of the
    package can be used without the optional dependency. The ``trial`` argument
    is treated duck-typed (expects ``suggest_float/int/categorical`` methods).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    target: type[Any] | None = None
    """Type of the parameter (int, float, bool, str, Enum)."""
    low: float | int | None = None
    """Lower bound for numeric spaces."""
    high: float | int | None = None
    """Upper bound for numeric spaces."""
    step: int | None = 1
    """Step used for discrete integer suggestions."""
    categories: Sequence[Any] | None = None
    """Explicit set of categorical choices (or Enum members)."""
    log: bool = False
    """Use logarithmic sampling for numeric spaces."""
    name: str | None = None
    """Optional override for the Optuna parameter name."""
    default: T | None = None
    """Default value used outside Optuna trials."""
    description: str | None = None
    """Human readable description of the parameter."""
    relies_on: dict[str, tuple[Any, ...]] | None = None
    """Optional dependency map: {param_path: (accepted_values,...)}."""

    @classmethod
    def continuous(
        cls,
        *,
        low: float,
        high: float,
        log: bool = False,
        name: str | None = None,
        default: float | None = None,
        description: str | None = None,
        relies_on: dict[str, tuple[Any, ...]] | None = None,
    ) -> "Optimizable[float]":
        """Describe a bounded floating-point search space."""
        return cls(
            target=float,
            low=low,
            high=high,
            log=log,
            name=name,
            default=default,
            description=description,
            relies_on=relies_on,
        )

    @classmethod
    def discrete(
        cls,
        *,
        low: int,
        high: int,
        step: int = 1,
        log: bool = False,
        name: str | None = None,
        default: int | None = None,
        description: str | None = None,
        relies_on: dict[str, tuple[Any, ...]] | None = None,
    ) -> "Optimizable[int]":
        """Describe a bounded integer search space with a fixed step."""
        return cls(
            target=int,
            low=low,
            high=high,
            step=step or 1,
            log=log,
            name=name,
            default=default,
            description=description,
            relies_on=relies_on,
        )

    @classmethod
    def categorical(
        cls,
        *,
        choices: Sequence[Any],
        name: str | None = None,
        default: Any | None = None,
        description: str | None = None,
        relies_on: dict[str, tuple[Any, ...]] | None = None,
    ) -> "Optimizable[Any]":
        """Describe a search space over an explicit finite choice set."""
        return cls(
            categories=tuple(choices),
            name=name,
            default=default,
            description=description,
            relies_on=relies_on,
        )

    def suggest(
        self,
        trial: "optuna.Trial",  # type: ignore[name-defined]
        path: str,
        *,
        current_value: Any | None = None,
        value_lookup: Callable[[str], Any] | None = None,
    ) -> T:
        """Sample a value from Optuna.

        Args:
            trial: Optuna trial (duck-typed; must implement suggest_* APIs).
            path: Default parameter name derived from the config path.

        Returns:
            Suggested value coerced into the requested target type.
        """
        if self.relies_on and value_lookup is not None:
            if not self._dependencies_satisfied(value_lookup):
                if current_value is not None:
                    return self._coerce(current_value)
                if self.default is not None:
                    return self._coerce(self.default)
                return self._coerce(current_value)
        name = self.name or path
        if self._is_categorical():
            choices = list(self._categorical_choices())
            opt_choices: list[Any] = []
            reverse_map: dict[Any, Any] = {}
            for choice in choices:
                opt_choice, mapped = self._to_optuna_choice(choice)
                opt_choices.append(opt_choice)
                if mapped is not None:
                    reverse_map[opt_choice] = mapped
            if not opt_choices:
                raise ValueError(f"Categorical optimizable '{name}' requires at least one choice.")
            if len(opt_choices) == 1:
                # Treat single-choice categoricals as fixed parameters. This avoids
                # Optuna's "CategoricalDistribution does not support dynamic value
                # space" error when continuing an existing study where the same
                # parameter name previously had a larger choice set.
                value = opt_choices[0]
            else:
                value = trial.suggest_categorical(name, opt_choices)
            if value in reverse_map:
                value = reverse_map[value]
            return self._coerce(value)
        if self._is_bool():
            value = trial.suggest_categorical(name, [True, False])
            return self._coerce(value)
        if self._is_int():
            return self._coerce(
                trial.suggest_int(
                    name,
                    int(self._require_low()),
                    int(self._require_high()),
                    step=self.step or 1,
                    log=self.log,
                )
            )
        if self._is_float():
            return self._coerce(
                trial.suggest_float(
                    name,
                    float(self._require_low()),
                    float(self._require_high()),
                    log=self.log,
                )
            )
        raise ValueError(f"Unsupported optimizable configuration for '{path}'.")

    def serialize(self, value: Any) -> Any:
        """Convert a suggested value to a JSON/W&B friendly representation."""
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, (list, tuple)):
            return self._stringify_choice(value)
        return value

    # ------------------------------------------------------------------ helpers
    def _is_bool(self) -> bool:
        return self.target is bool

    def _is_int(self) -> bool:
        return self.target is int

    def _is_float(self) -> bool:
        return self.target is float or (isinstance(self.low, float) or isinstance(self.high, float))

    def _is_categorical(self) -> bool:
        return self.categories is not None or (isinstance(self.target, type) and issubclass(self.target, Enum))

    def _categorical_choices(self) -> Sequence[Any]:
        if self.categories is not None:
            return self.categories
        target = self.target
        if isinstance(target, type) and issubclass(target, Enum):
            return list(target)
        raise ValueError("Categorical optimizables require either categories or an Enum target.")

    def _require_low(self) -> float | int:
        if self.low is None:
            raise ValueError("Optimizable requires 'low'.")
        return self.low

    def _require_high(self) -> float | int:
        if self.high is None:
            raise ValueError("Optimizable requires 'high'.")
        return self.high

    def _coerce(self, value: Any) -> Any:
        target = self.target
        if target is None:
            return value
        if isinstance(target, type) and issubclass(target, Enum):
            if isinstance(value, target):
                return value
            return target(value)
        if target in {int, float, bool, str}:
            return target(value)
        return value

    def _to_optuna_choice(self, choice: Any) -> tuple[Any, Any | None]:
        """Convert a categorical choice into an Optuna-friendly primitive.

        Returns:
            Tuple of (optuna_choice, mapped_value). If mapped_value is not None,
            it is the original choice to restore after sampling.
        """
        if isinstance(choice, Enum):
            return choice.value, choice
        if isinstance(choice, (list, tuple)):
            return self._stringify_choice(choice), choice
        if choice is None or isinstance(choice, (bool, int, float, str)):
            return choice, None
        return str(choice), choice

    def _stringify_choice(self, choice: Sequence[Any]) -> str:
        """Stable string representation for categorical sequences."""
        if all(isinstance(item, str) for item in choice):
            return "+".join(choice)
        if all(isinstance(item, (int, float, bool)) for item in choice):
            return ",".join(str(item) for item in choice)
        return "+".join(str(item) for item in choice)

    def _dependencies_satisfied(self, value_lookup: Callable[[str], Any]) -> bool:
        for key, accepted in (self.relies_on or {}).items():
            value = value_lookup(key)
            if isinstance(value, Enum):
                value = value.value
            accepted_values = tuple(v.value if isinstance(v, Enum) else v for v in accepted)
            if value not in accepted_values:
                return False
        return True


def optimizable_field(
    *,
    default: T | None = None,
    default_factory: Callable[[], T] | None = None,
    optimizable: Optimizable[T],
    **field_kwargs: Any,
) -> Any:
    """Attach an optimizable definition to a Pydantic Field.

    Exactly one of ``default`` or ``default_factory`` must be provided.
    """
    if (default is None) == (default_factory is None):
        raise ValueError("Provide exactly one of default or default_factory.")
    extras = dict(field_kwargs.pop("json_schema_extra", {}) or {})
    extras["optimizable"] = optimizable
    if default_factory is not None:
        return Field(
            default_factory=default_factory,
            json_schema_extra=extras,
            **field_kwargs,
        )
    return Field(default=default, json_schema_extra=extras, **field_kwargs)


__all__ = [
    "Optimizable",
    "optimizable_field",
]
