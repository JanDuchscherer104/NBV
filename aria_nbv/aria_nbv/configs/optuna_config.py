"""Optuna integration helpers for experiment orchestration."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field
from pytorch_lightning import Callback

from ..utils import BaseConfig, Console, TargetConfig
from ..utils.optuna_optimizable import Optimizable
from .path_config import PathConfig

if TYPE_CHECKING:
    import optuna

Setter = Callable[[Any], None]


def _require_optuna() -> Any:
    try:
        import optuna  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise ModuleNotFoundError(
            "Optuna is required for sweeps. Install with `pip install optuna optuna-integration`.",
        ) from exc
    return optuna


class OptunaConfig(TargetConfig["optuna.Study"]):
    """Configure an Optuna study used by :class:`aria_nbv.lightning.AriaNBVExperimentConfig`."""

    study_name: str = "aria-nbv"
    """Study name (used for Optuna storage and W&B grouping)."""

    direction: Literal["minimize", "maximize"] = "minimize"
    """Optuna optimization direction."""

    n_trials: int = 20
    """Number of Optuna trials to run."""

    monitor: str = "train/loss"
    """Metric key to optimize (must be present in the Lightning trainer metrics)."""

    load_if_exists: bool = True
    """Re-use an existing study with the same name when True."""

    sampler: Literal["tpe", "random"] = "tpe"
    """Optuna sampler choice."""

    pruner: Literal["median", "successive_halving"] = "median"
    """Optuna pruner choice."""

    suggested_params: dict[str, Any] = Field(default_factory=dict, exclude=True)
    """Latest trial suggestions applied to the config tree (W&B friendly)."""

    def setup_target(self) -> "optuna.Study":  # type: ignore[name-defined]
        """Create or load an Optuna study."""
        optuna = _require_optuna()
        sampler = optuna.samplers.TPESampler() if self.sampler == "tpe" else optuna.samplers.RandomSampler()
        pruner = optuna.pruners.MedianPruner() if self.pruner == "median" else optuna.pruners.SuccessiveHalvingPruner()
        paths = PathConfig()
        return optuna.create_study(
            study_name=self.study_name,
            storage=paths.resolve_optuna_study_uri(self.study_name),
            load_if_exists=bool(self.load_if_exists),
            direction=str(self.direction),
            sampler=sampler,
            pruner=pruner,
        )

    def setup_optimizables(
        self,
        experiment_config: BaseConfig,
        trial: "optuna.Trial",  # type: ignore[name-defined]
        *,
        console: Console | None = None,
    ) -> None:
        """Apply Optimizable hints embedded in the config tree."""
        if not isinstance(experiment_config, BaseConfig):
            return
        self.suggested_params.clear()

        opt_console = console or Console.with_prefix(
            self.__class__.__name__,
            "setup_optimizables",
        )
        opt_console.set_verbose(getattr(experiment_config, "verbose", False)).set_debug(
            getattr(experiment_config, "is_debug", False),
        )

        def join(prefix: str | None, suffix: str) -> str:
            """Compose dotted paths for nested fields."""
            return f"{prefix}.{suffix}" if prefix else suffix

        def _extract_optimizable(field: Any, current_value: Any) -> Optimizable | None:
            """Retrieve an Optimizable definition from field metadata or value."""
            if isinstance(current_value, Optimizable):
                return current_value
            if field is not None:
                extras = getattr(field, "json_schema_extra", None) or {}
                opt = extras.get("optimizable")
                if isinstance(opt, Optimizable):
                    return opt
            return None

        def resolve_path(path: str) -> Any:
            obj: Any = experiment_config
            for part in path.split("."):
                if obj is None:
                    return None
                if isinstance(obj, BaseConfig):
                    obj = getattr(obj, part, None)
                elif isinstance(obj, dict):
                    obj = obj.get(part)
                else:
                    return None
            return obj

        def visit(
            value: Any,
            *,
            path: str | None,
            setter: Setter,
            field_info: Any = None,
        ) -> None:
            """Walk config values and apply Optuna suggestions when encountered."""
            optimizable = _extract_optimizable(field_info, value)
            if optimizable is not None:
                param_name = path or optimizable.name or "param"
                suggestion = optimizable.suggest(
                    trial,
                    param_name,
                    current_value=value,
                    value_lookup=resolve_path,
                )
                setter(suggestion)
                serialized = optimizable.serialize(suggestion)
                self.suggested_params[param_name] = serialized
                opt_console.log(
                    f"Optuna suggest {param_name}={serialized} (trial {trial.number})",
                )
                if optimizable.description:
                    opt_console.log(
                        f"Optuna param note: {param_name} - {optimizable.description}",
                    )
                return

            if isinstance(value, BaseConfig):
                for child_name, child_field in value.__class__.model_fields.items():
                    child_value = getattr(value, child_name)
                    visit(
                        child_value,
                        path=join(path, child_name),
                        setter=lambda new_value, obj=value, attr=child_name: setattr(
                            obj,
                            attr,
                            new_value,
                        ),
                        field_info=child_field,
                    )
            elif isinstance(value, list):
                for idx, item in enumerate(value):
                    visit(
                        item,
                        path=f"{path}[{idx}]" if path else f"[{idx}]",
                        setter=lambda new_value, seq=value, index=idx: seq.__setitem__(
                            index,
                            new_value,
                        ),
                        field_info=None,
                    )
            elif isinstance(value, dict):
                for key, item in value.items():
                    visit(
                        item,
                        path=join(path, str(key)),
                        setter=lambda new_value, mapping=value, mapping_key=key: mapping.__setitem__(
                            mapping_key,
                            new_value,
                        ),
                        field_info=None,
                    )

        for name, field in experiment_config.__class__.model_fields.items():
            value = getattr(experiment_config, name)
            visit(
                value,
                path=name,
                setter=lambda new_value, obj=experiment_config, attr=name: setattr(
                    obj,
                    attr,
                    new_value,
                ),
                field_info=field,
            )

    def log_to_wandb(self) -> None:
        """Send the most recent suggestions to W&B."""
        try:
            import wandb  # type: ignore[import-not-found]
        except ModuleNotFoundError:  # pragma: no cover - optional dependency
            return
        if wandb.run is not None and self.suggested_params:
            wandb.config.update(self.suggested_params, allow_val_change=True)

    def get_pruning_callback(self, trial: "optuna.Trial") -> Callback:  # type: ignore[name-defined]
        """Return a PyTorch Lightning pruning callback for the configured monitor."""
        try:
            from optuna_integration import PyTorchLightningPruningCallback  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dep
            raise ModuleNotFoundError(
                "Optuna pruning requires `optuna-integration`. Install with `pip install optuna optuna-integration`.",
            ) from exc
        return PyTorchLightningPruningCallback(trial=trial, monitor=str(self.monitor))


__all__ = ["OptunaConfig"]
