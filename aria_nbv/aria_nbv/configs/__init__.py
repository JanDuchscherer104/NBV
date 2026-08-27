"""Lazy stable imports for ARIA-NBV configuration factories.

Loading :class:`PathConfig` must not import optional Optuna, W&B, TorchMetrics,
or Lightning runtime stacks. The public names remain available through module
attribute lookup and are imported only when requested.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .authoring import (
        ConfigAuthoringError,
        ConfigConflictError,
        ConfigDiff,
        ConfigDiffEntry,
        ConfigDocument,
        ConfigFieldDescriptor,
        ConfigWriteReceipt,
    )
    from .optuna_config import OptunaConfig
    from .path_config import PathConfig
    from .wandb_config import WandbConfig

_OWNERS = {
    "ConfigAuthoringError": ".authoring",
    "ConfigConflictError": ".authoring",
    "ConfigDiff": ".authoring",
    "ConfigDiffEntry": ".authoring",
    "ConfigDocument": ".authoring",
    "ConfigFieldDescriptor": ".authoring",
    "ConfigWriteReceipt": ".authoring",
    "OptunaConfig": ".optuna_config",
    "PathConfig": ".path_config",
    "WandbConfig": ".wandb_config",
}


def __getattr__(name: str) -> Any:
    """Load one public configuration class from its owning leaf module."""

    try:
        module_name = _OWNERS[name]
    except KeyError as error:
        raise AttributeError(name) from error
    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value


__all__ = [
    "ConfigAuthoringError",
    "ConfigConflictError",
    "ConfigDiff",
    "ConfigDiffEntry",
    "ConfigDocument",
    "ConfigFieldDescriptor",
    "ConfigWriteReceipt",
    "OptunaConfig",
    "PathConfig",
    "WandbConfig",
]
