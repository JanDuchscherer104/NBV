"""Launch the configured ARIA-NBV Streamlit application.

This module owns the `nbv-st`/direct-script dispatch, forwards user CLI
arguments to Streamlit, and installs a conservative file-watcher default. The
application layout and data workflows belong to :mod:`aria_nbv.app`. This
entrypoint stays import-light so Streamlit creates its runtime before cached
panel decorators are evaluated.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aria_nbv.app import NbvStreamlitApp, NbvStreamlitAppConfig

__all__ = ["NbvStreamlitApp", "NbvStreamlitAppConfig", "main", "streamlit_entry"]

_FILE_WATCHER_ENV = "STREAMLIT_SERVER_FILE_WATCHER_TYPE"
_FILE_WATCHER_FLAG = "--server.fileWatcherType"
_DEFAULT_FILE_WATCHER_TYPE = "auto"
_RUN_ON_SAVE_ENV = "STREAMLIT_SERVER_RUN_ON_SAVE"
_RUN_ON_SAVE_FLAG = "--server.runOnSave"
_DEFAULT_RUN_ON_SAVE = "true"


def main() -> None:  # pragma: no cover - Streamlit runner
    """Construct and run the configured ARIA-NBV Streamlit application."""

    from aria_nbv.app.config import NbvStreamlitAppConfig

    NbvStreamlitAppConfig().setup_target().run()


def __getattr__(name: str) -> Any:
    """Resolve compatibility exports without eagerly importing the app."""

    if name == "NbvStreamlitApp":
        from aria_nbv.app.app import NbvStreamlitApp

        return NbvStreamlitApp
    if name == "NbvStreamlitAppConfig":
        from aria_nbv.app.config import NbvStreamlitAppConfig

        return NbvStreamlitAppConfig
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _has_streamlit_override(args: Sequence[str], flag: str) -> bool:
    """Return whether forwarded CLI arguments explicitly set one Streamlit option."""

    return any(arg == flag or arg.startswith(f"{flag}=") for arg in args)


def _build_streamlit_argv(app_path: Path, forwarded_args: Sequence[str]) -> list[str]:
    streamlit_args = list(forwarded_args)
    script_args: list[str] = []
    if "--" in streamlit_args:
        delimiter_index = streamlit_args.index("--")
        script_args = streamlit_args[delimiter_index:]
        streamlit_args = streamlit_args[:delimiter_index]

    if not _has_streamlit_override(streamlit_args, _FILE_WATCHER_FLAG) and _FILE_WATCHER_ENV not in os.environ:
        streamlit_args = [
            _FILE_WATCHER_FLAG,
            _DEFAULT_FILE_WATCHER_TYPE,
            *streamlit_args,
        ]
    if not _has_streamlit_override(streamlit_args, _RUN_ON_SAVE_FLAG) and _RUN_ON_SAVE_ENV not in os.environ:
        streamlit_args = [
            _RUN_ON_SAVE_FLAG,
            _DEFAULT_RUN_ON_SAVE,
            *streamlit_args,
        ]

    return ["streamlit", "run", *streamlit_args, str(app_path), *script_args]


def streamlit_entry() -> None:  # pragma: no cover - console script
    """Launch via `nbv-st` console entry.

    The wrapper uses Streamlit's ``auto`` watcher and automatic rerun by default:
    watchdog when it is available, otherwise polling. Set
    ``STREAMLIT_SERVER_FILE_WATCHER_TYPE`` or ``STREAMLIT_SERVER_RUN_ON_SAVE``,
    or pass the corresponding Streamlit option before ``--``, to override either
    behavior for a constrained or intentionally stable session.
    """

    from streamlit.web.cli import main as st_main

    # streamlit CLI does not accept "-m"; pass absolute path to this file
    app_path = Path(__file__).resolve()
    sys.argv = _build_streamlit_argv(app_path, sys.argv[1:])
    st_main()


if __name__ == "__main__":  # pragma: no cover
    main()
