"""Rich console with shared verbosity, debug state, and structured summaries.

This module provides :class:`Verbosity` and the package-wide :class:`Console`
adapter for gated Rich output, progress reporting, and optional Lightning-log
forwarding. It owns presentation state and routing only; callers retain
responsibility for metric meaning, exception policy, and training control flow.

All instances share logging gates and the optional Lightning logger bridge;
prefixes remain instance-local so concurrent components retain readable source
context.
"""

import inspect
import traceback
from collections.abc import Callable
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from devtools import pformat
from rich.console import Console as RichConsole
from rich.theme import Theme

from .rich_summary import summarize

if TYPE_CHECKING:
    from lightning.pytorch.loggers.logger import Logger


class Verbosity(IntEnum):
    """Ordered output gates shared by every :class:`Console` instance."""

    QUIET = 0
    NORMAL = 1
    VERBOSE = 2

    @classmethod
    def from_any(cls, value: Any) -> "Verbosity":
        """Coerce booleans/ints/strings into a Verbosity level."""
        if isinstance(value, cls):
            return value
        if isinstance(value, bool):
            return cls.NORMAL if value else cls.QUIET
        if isinstance(value, (int, float)):
            try:
                return cls(max(min(int(value), int(cls.VERBOSE)), int(cls.QUIET)))
            except ValueError:
                return cls.NORMAL
        if isinstance(value, str):
            normalised = value.strip().lower()
            mapping = {
                "quiet": cls.QUIET,
                "silent": cls.QUIET,
                "normal": cls.NORMAL,
                "info": cls.NORMAL,
                "verbose": cls.VERBOSE,
                "debug": cls.VERBOSE,
                "max": cls.VERBOSE,
            }
            if normalised in mapping:
                return mapping[normalised]
        return cls.NORMAL


class Console(RichConsole):
    """Console wrapper that centralises formatting and convenience helpers."""

    _shared_pl_logger: ClassVar["Logger | None"] = None
    _shared_global_step: ClassVar[int] = 0
    _global_verbosity: ClassVar[Verbosity] = Verbosity.NORMAL
    _global_debug: ClassVar[bool] = False
    _external_sink: ClassVar[Callable[[str], None] | None] = None
    prefix: str | None = None
    """Instance-local `::`-separated source context prepended to messages."""

    default_settings = {
        "theme": Theme(
            {
                "config.name": "bold blue",  # Config class names
                "config.field": "green",  # Regular fields
                "config.propagated": "yellow",  # Propagated fields
                "config.value": "white",  # Field values
                "config.type": "dim",  # Type annotations
                "config.doc": "italic dim",  # Documentation
            },
        ),
        "width": 120,
        "force_terminal": True,
        "color_system": "auto",
        "markup": True,
        "highlight": True,
    }

    def __init__(self, **kwargs):
        """Initialise the console with project defaults and user overrides."""
        settings = self.default_settings.copy()
        settings.update(kwargs)
        super().__init__(**settings)
        self.show_timestamps = False
        self.prefix = None

    @property
    def _pl_logger(self) -> "Logger | None":
        """Shared logger instance across all consoles."""
        return type(self)._shared_pl_logger

    @_pl_logger.setter
    def _pl_logger(self, logger: "Logger | None") -> None:
        type(self)._shared_pl_logger = logger

    @property
    def _global_step(self) -> int:
        """Shared global step across all consoles."""
        return type(self)._shared_global_step

    @_global_step.setter
    def _global_step(self, value: int) -> None:
        type(self)._shared_global_step = value

    @property
    def verbosity(self) -> Verbosity:
        """Return the process-wide minimum level for informational output."""
        return type(self)._global_verbosity

    @verbosity.setter
    def verbosity(self, value: Verbosity | int | bool) -> None:
        """Set the process-wide verbosity after coercing supported aliases."""
        type(self)._global_verbosity = Verbosity.from_any(value)

    @property
    def verbose(self) -> bool:
        """Report whether normal informational logging is currently enabled."""
        return self.verbosity >= Verbosity.NORMAL

    @verbose.setter
    def verbose(self, value: bool) -> None:
        """Enable normal output when true, otherwise silence informational logs."""
        self.verbosity = value

    @property
    def is_debug(self) -> bool:
        """Return the process-wide debug gate used by :meth:`dbg`."""
        return type(self)._global_debug

    @is_debug.setter
    def is_debug(self, value: bool) -> None:
        """Set the process-wide debug gate for every console instance."""
        type(self)._global_debug = value

    @classmethod
    def with_prefix(cls, *parts: str) -> "Console":
        """Create a console instance with a prefixed context.

        Enables builder-style chaining.

        Usage:
        ```python
        console = Console.with_prefix(
            self.__class__.__name__,
            <name_of_the_current_method>
            <further_parts>, # eg. stage, worker_idx...
        )
        ```

        """
        instance = cls()
        instance.set_prefix(*parts)
        return instance

    @classmethod
    def with_caller_prefix(cls, *extra_parts: str, stack_depth: int = 1) -> "Console":
        """Create a console with prefix inferred from the caller's module and function."""
        frame_info = inspect.stack()[stack_depth + 1]
        module_name = Path(frame_info.filename).stem
        parts = (module_name, frame_info.function, *extra_parts)
        return cls().set_prefix(*parts)

    @classmethod
    def from_callsite(cls, *parts: str, stack_offset: int = 0) -> "Console":
        """Compatibility constructor mirroring the PRML VSLAM console API."""
        return cls.with_caller_prefix(*parts, stack_depth=stack_offset + 1)

    def set_prefix(self, *parts: str) -> "Console":
        """Set a custom prefix for all log messages.

        Enables builder-style chaining.
        """
        if not parts:
            self.prefix = None
        else:
            self.prefix = "::".join(filter(None, parts))

        return self

    def unset_prefix(self) -> "Console":
        """Remove this instance's contextual prefix and return the console."""
        self.prefix = None
        return self

    def log(self, message: str) -> None:
        """Emit an informational message when verbosity is enabled."""
        if self.verbosity < Verbosity.NORMAL:
            return
        formatted = self._format_message(message)
        self.print(formatted)
        self._emit_sink(formatted)
        if self._pl_logger is not None:
            self._log_to_lightning("info", message)

    def log_summary(self, label: str, value: Any, *, include_stats: bool = False) -> None:
        """Log a structured summary built from `summarize`."""
        summary = summarize(value, include_stats=include_stats)
        self.log(f"{label}: {summary}")

    def warn(self, message: str) -> None:
        """Emit a warning message and include a short caller stack."""
        if self.verbosity >= Verbosity.NORMAL:
            formatted = (
                f"[bright_yellow]Warning:[/bright_yellow] {self._format_message(message)}\n"
                f"[dim]{self._get_caller_stack()}[/dim]"
            )
            self.print(formatted)
            self._emit_sink(formatted)
        if self._pl_logger is not None:
            self._log_to_lightning("warning", message)

    def error(self, message: str) -> None:
        """Emit an error message and show the relevant caller stack."""
        formatted = (
            f"[bright_red]Error:[/bright_red] {self._format_message(message)}\n[dim]{self._get_caller_stack()}[/dim]"
        )
        self.print(formatted)
        self._emit_sink(formatted)
        if self._pl_logger is not None:
            self._log_to_lightning("error", message)

    def plog(self, obj: Any, **kwargs) -> None:
        """Pretty-print an object using the best available formatter."""
        if self.verbosity >= Verbosity.NORMAL:
            formatted = pformat(obj, **kwargs)
            self.print(formatted)
            self._emit_sink(formatted)
        if self._pl_logger is not None:
            self._log_to_lightning("info", pformat(obj, **kwargs))

    def dbg(self, message: str) -> None:
        """Emit a debug message when debug mode is enabled."""
        if self.is_debug or self.verbosity >= Verbosity.VERBOSE:
            formatted = f"[bold magenta]Debug:[/bold magenta] {self._format_message(message)}"
            self.print(formatted)
            self._emit_sink(formatted)
            if self._pl_logger is not None:
                self._log_to_lightning("debug", message)

    def dbg_summary(self, label: str, value: Any, *, include_stats: bool = False) -> None:
        """Emit a compact tensor-aware summary when debug logging is enabled."""
        if self.is_debug or self.verbosity >= Verbosity.VERBOSE:
            summary = summarize(value, include_stats=include_stats)
            self.dbg(f"{label}: {summary}")

    def set_verbosity(self, level: Verbosity | int | bool) -> "Console":
        """Set verbosity level (0=quiet, 1=normal, 2=verbose)."""
        self.verbosity = level
        return self

    def set_verbose(self, verbose: Verbosity | int | bool) -> "Console":
        """Backward-compatible alias for `set_verbosity`."""
        self.set_verbosity(verbose)
        return self

    def set_debug(self, is_debug: bool) -> "Console":
        """Enable or disable debug logging while keeping verbose mode sensible."""
        self.is_debug = is_debug
        if is_debug:
            self.verbosity = Verbosity.VERBOSE
        return self

    def set_timestamp_display(self, show_timestamps: bool) -> "Console":
        """Toggle timestamps for subsequent log messages."""
        self.show_timestamps = show_timestamps
        return self

    def _format_message(self, message: str) -> str:
        """Format message with optional timestamp and prefix."""
        if self.prefix:
            # Use rich markup for terminal display
            rich_prefix = self.prefix.replace(
                "::",
                "[/bold cyan][grey]::[/grey][bold cyan]",
            )
            prefix = rf"\[[bold cyan]{rich_prefix}[/bold cyan]]: "
        else:
            prefix = ""
        if self.show_timestamps:
            return f"[{self._get_timestamp()}] {prefix}{message}"
        return f"{prefix}{message}"

    def _get_caller_stack(self) -> str:
        """Get formatted stack trace excluding console internals."""
        stack = traceback.extract_stack()
        # Filter out frames from this file
        current_file = Path(__file__).resolve()
        relevant_frames = [
            frame
            for frame in stack[:-1]  # Exclude current frame
            if Path(frame.filename).resolve() != current_file
        ]
        # Format remaining frames
        return "".join(
            traceback.format_list(relevant_frames[-2:]),
        )  # Show last 2 relevant frames

    @classmethod
    def integrate_with_logger(
        cls,
        logger: "Logger",
        global_step: int = 0,
    ) -> type["Console"]:
        """Integrate all Console instances with PyTorch Lightning logger for WandB/TensorBoard logging.

        This is a class method that sets the shared logger state for all Console instances.

        Args:
            logger: PyTorch Lightning logger instance (e.g., WandbLogger, TensorBoardLogger).
            global_step: Current training step for metric logging.

        Returns:
            Console class for method chaining.

        Example:
            ```python
            # In your LightningModule.__init__
            Console.integrate_with_logger(self.logger)

            # In training_step
            def training_step(self, batch, batch_idx):
                Console.update_global_step(self.global_step)
                console = Console.with_prefix("training")
                console.log("Processing batch")  # → Terminal + WandB!
            ```
        """
        cls._shared_pl_logger = logger
        cls.update_global_step(global_step)
        return cls

    @classmethod
    def update_global_step(cls, global_step: int) -> type["Console"]:
        """Update the shared global step for all console instances."""
        cls._shared_global_step = global_step
        return cls

    def _log_to_lightning(self, level: str, message: str) -> None:
        """Log message to PyTorch Lightning logger.

        Args:
            level: Log level (info, warning, error, debug).
            message: Message content without formatting.
        """
        if self._pl_logger is None:
            return

        # Skip logging if message appears to be from Rich progress bar or internal Rich output
        # Progress bars and other Rich widgets should not be logged to W&B
        if not message or message.isspace():
            return

        # Construct metric name with prefix and level
        # Convert :: separators to / for hierarchical metric names
        prefix_clean = self.prefix.replace("::", "/") if self.prefix else "Console"
        metric_name = f"{prefix_clean}/{level}"

        # Log as text to WandB/logger using log_text if available, otherwise skip
        try:
            # WandbLogger has log_text method for logging strings
            if hasattr(self._pl_logger, "log_text"):
                self._pl_logger.log_text(
                    key=metric_name,
                    columns=["message"],
                    data=[[message]],
                    step=self._global_step,
                )
            # For TensorBoard and others, log to experiment directly
            elif hasattr(self._pl_logger, "experiment"):
                exp = self._pl_logger.experiment
                # WandB experiment object
                if hasattr(exp, "log"):
                    exp.log({metric_name: message}, step=self._global_step)
                # TensorBoard experiment
                elif hasattr(exp, "add_text"):
                    exp.add_text(metric_name, message, self._global_step)
        except Exception:
            # Fallback: silent failure to avoid breaking training
            pass

    @classmethod
    def set_sink(cls, sink: Callable[[str], None] | None) -> None:
        """Register an external sink to receive plain-text log lines."""

        cls._external_sink = sink

    def _emit_sink(self, message: str) -> None:
        """Emit formatted message to external sink if registered."""

        if self._external_sink is not None:
            try:
                self._external_sink(message)
            except Exception:
                # Sink failures should not disrupt logging
                pass
