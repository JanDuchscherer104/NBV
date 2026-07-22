"""Grouped Streamlit inspection application with lazy page imports.

The package exposes typed application and configuration factories while
keeping panel modules unloaded until their navigation callbacks run.
"""

from __future__ import annotations

from typing import Any

__all__ = ["NbvStreamlitApp", "NbvStreamlitAppConfig"]


def __getattr__(name: str) -> Any:
    """Lazily import Streamlit-heavy modules.

    This keeps configuration and non-UI helpers importable without loading the
    Streamlit application frame or any panel modules.
    """

    if name == "NbvStreamlitApp":
        from .app import NbvStreamlitApp

        return NbvStreamlitApp
    if name == "NbvStreamlitAppConfig":
        from .config import NbvStreamlitAppConfig

        return NbvStreamlitAppConfig
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + __all__)
