"""Typed config-as-factory foundation for ARIA-NBV runtime objects.

This module provides :class:`BaseConfig`, generic :class:`TargetConfig`, and
singleton :class:`SingletonConfig`. It owns Pydantic validation, nested config
serialization, TOML/cache representations, and the standard runtime-construction
hook; concrete configs own domain defaults and target classes own runtime
behavior.

Configs validate nested experiment state, serialize stable TOML/cache payloads,
and construct runtime targets through :meth:`BaseConfig.setup_target`. Runtime
objects stay outside the persisted config graph; late-bound dependencies are
passed explicitly to `setup_target`.
"""

import tomllib
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any, ClassVar, ForwardRef, Generic, Self, TypeVar, cast

import tomli_w
import torch
from pydantic import PrivateAttr, model_validator
from pydantic_settings import (
    BaseSettings,
    CliSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)
from rich.text import Text
from rich.tree import Tree

from .console import Console, Verbosity

TargetT = TypeVar("TargetT")


class BaseConfig(BaseSettings):
    """Validate, serialize, inspect, and instantiate one configuration tree.

    Subclasses that construct runtime objects should inherit
    :class:`TargetConfig` and expose `target_type`. Plain subclasses may use
    `setup_target` as a no-op and still share TOML, cache, and CLI behavior.
    """

    cache_exclude_fields: ClassVar[set[str]] = set()
    """Field names to exclude from cache snapshots."""

    cache_exclude_extra_key: ClassVar[str] = "cache_exclude"
    """json_schema_extra key for marking fields excluded from cache snapshots."""

    propagation_exclude_fields: ClassVar[set[str]] = set()
    """Field names that must not propagate into nested config identities."""

    @property
    def target_type(self) -> type[Any] | None:
        """Callable target used by `setup_target`.

        Defaults to ``None``; target-producing subclasses should use
        `TargetConfig` and override this property.
        """
        return None

    @property
    def target(self) -> type[Any] | None:
        """Compatibility alias for `target_type`.

        New config factories should override `target_type`; this property keeps
        existing subclasses and external callers working during migration.
        """
        return self.target_type

    def setup_target(self, *args: Any, **kwargs: Any) -> Any | None:
        """Instantiate or return the target object for this config, if applicable.

        Prioritizes a 'setup_target' method on the target itself and falls back to calling the init method.
        """
        return self._setup_target_from_factory(*args, _allow_missing_target=True, **kwargs)

    def _config_target_type(self) -> type[Any] | None:
        """Resolve the preferred target declaration, including legacy `target` overrides."""
        if (target_type := self.target_type) is not None:
            return target_type
        return self.target

    def _setup_target_from_factory(
        self,
        *args: Any,
        _allow_missing_target: bool,
        **kwargs: Any,
    ) -> Any | None:
        """Instantiate the configured target with shared error handling."""
        if (target_type := self._config_target_type()) is None:
            if _allow_missing_target:
                return None
            msg = (
                f"{self.__class__.__name__} must define a 'target_type' or legacy 'target' property, "
                "or override 'setup_target'."
            )
            Console.from_callsite(stack_offset=1).error(msg)
            raise ValueError(msg)
        factory = getattr(target_type, "setup_target", target_type)

        if not callable(factory):
            msg = (
                f"Target '{target_type}' of type {factory.__class__.__name__} is not callable / does not have a "
                "'setup_target' or '__init__' method."
            )
            Console.from_callsite(stack_offset=1).error(msg)
            raise ValueError(msg)

        return factory(self, *args, **kwargs)

    model_config = SettingsConfigDict(
        arbitrary_types_allowed=True,
        validate_default=True,
        validate_assignment=True,
        protected_namespaces=(),
        cli_parse_args=False,
        cli_avoid_json=True,
        cli_kebab_case=True,
    )

    _propagated_fields: dict[str, Any] = PrivateAttr(default_factory=dict)

    def __class_getitem__(cls, _item: Any) -> type["BaseConfig"]:
        """Keep legacy ``BaseConfig[T]`` subclass declarations working."""
        return cls

    @property
    def propagated_fields(self) -> dict[str, Any]:
        """Track which fields were propagated from a parent config."""
        return self._propagated_fields

    @staticmethod
    def _resolve_device(value: str | torch.device) -> torch.device:
        if isinstance(value, torch.device):
            return value
        if value is None or str(value).lower() == "auto":
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")
        return torch.device(value)

    @staticmethod
    def _coerce_verbosity(value: Any) -> Verbosity:
        """Normalize verbosity values accepted across config models."""
        return Verbosity.from_any(value)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Restrict default settings sources to init + optional TOML/CLI.

        By default, environment/dotenv/file-secret sources are disabled for safety.
        Classes can opt into CLI by setting `cli_parse_args=True` in model_config or
        override this method for custom behavior.
        """
        sources: list[PydanticBaseSettingsSource] = [init_settings]

        model_cfg = getattr(settings_cls, "model_config", {}) or {}
        toml_file = model_cfg.get("toml_file")
        if toml_file:
            sources.append(TomlConfigSettingsSource(settings_cls, toml_file=toml_file))

        if model_cfg.get("cli_parse_args"):
            sources.append(CliSettingsSource(settings_cls, cli_parse_args=True))

        return tuple(sources)

    # ------------------------------------------------------------------ JSON-friendly dumps
    def model_dump_jsonable(self, **kwargs: Any) -> dict[str, Any]:
        """Return a JSON-serializable dump suitable for logging/checkpoint metadata."""
        return cast(dict[str, Any], self.to_jsonable(self.model_dump(**kwargs)))

    def model_dump_cache(
        self,
        *,
        exclude: set[str] | None = None,
        exclude_none: bool = True,
    ) -> dict[str, Any]:
        """Return a cache-friendly dump with per-field cache exclusions.

        Args:
            exclude: Additional field names to exclude from the snapshot.
            exclude_none: Skip fields with value ``None`` when True.
        """
        resolved_exclude = set(exclude or set())
        resolved_exclude.update(self._cache_exclude_fields())
        payload: dict[str, Any] = {}
        for field_name, field in self.__class__.model_fields.items():
            if field_name in resolved_exclude or field.exclude:
                continue
            value = getattr(self, field_name)
            if exclude_none and value is None:
                continue
            payload[field_name] = self._cache_jsonable(value, exclude_none=exclude_none)
        return payload

    @classmethod
    def _cache_jsonable(cls, value: Any, *, exclude_none: bool) -> Any:
        if isinstance(value, BaseConfig):
            return value.model_dump_cache(exclude_none=exclude_none)
        if isinstance(value, dict):
            payload: dict[str, Any] = {}
            for key, item in value.items():
                if exclude_none and item is None:
                    continue
                payload[str(key)] = cls._cache_jsonable(item, exclude_none=exclude_none)
            return payload
        if isinstance(value, (list, tuple, set)):
            items = [cls._cache_jsonable(item, exclude_none=exclude_none) for item in value]
            return [item for item in items if not (exclude_none and item is None)]
        return cls.to_jsonable(value)

    @classmethod
    def _cache_exclude_fields(cls) -> set[str]:
        excludes = set(getattr(cls, "cache_exclude_fields", set()))
        for field_name, field in cls.model_fields.items():
            extra = field.json_schema_extra
            if isinstance(extra, dict) and extra.get(cls.cache_exclude_extra_key, False):
                excludes.add(field_name)
        return excludes

    @classmethod
    def to_jsonable(cls, value: Any) -> Any:
        """Convert nested configs and common types into JSON-friendly primitives."""
        if isinstance(value, BaseConfig):
            return value.model_dump_jsonable()
        if isinstance(value, dict):
            return {k: cls.to_jsonable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [cls.to_jsonable(v) for v in value]
        if isinstance(value, Path):
            return value.as_posix()
        if isinstance(value, torch.device):
            return str(value)
        if isinstance(value, torch.dtype):
            return str(value)
        if isinstance(value, torch.Tensor):
            return value.detach().cpu().tolist()
        if isinstance(value, Enum):
            return value.value if hasattr(value, "value") else str(value)
        if isinstance(value, type):
            return value.__name__
        return value

    # --------------------------------------------------------------------- TOML IO
    def to_toml(
        self,
        path: Path | None = None,
        *,
        include_comments: bool = True,
        include_type_hints: bool = True,
    ) -> str:
        """Serialise the config (and nested configs) to TOML.

        Args:
            path: Optional path to write the TOML to.
            include_comments: Ignored (kept for API compatibility).
            include_type_hints: Ignored (kept for API compatibility).

        Returns:
            The rendered TOML string.
        """
        del include_comments, include_type_hints
        data = self._toml_normalize(self.model_dump(exclude_none=True))
        rendered = tomli_w.dumps(data)
        if path is not None:
            Path(path).write_text(rendered, encoding="utf-8")
        return rendered

    def save_toml(
        self,
        path: Path | str,
        *,
        include_comments: bool = True,
        include_type_hints: bool = True,
    ) -> Path:
        """Persist the configuration to a TOML file and return the resolved path."""
        target_path = Path(path)
        self.to_toml(
            path=target_path,
            include_comments=include_comments,
            include_type_hints=include_type_hints,
        )
        return target_path

    @classmethod
    def from_toml(cls: type[Self], source: str | Path | bytes) -> Self:
        """Load a config from a TOML string or file path."""
        if isinstance(source, Path):
            data = cls._load_toml_path(source)
        elif isinstance(source, bytes):
            data = tomllib.loads(source.decode("utf-8"))
        else:
            if "\n" in source or "\r" in source:
                data = tomllib.loads(source)
            else:
                potential_path = Path(source)
                if potential_path.exists():
                    data = cls._load_toml_path(potential_path)
                else:
                    data = tomllib.loads(source)

        return cls.model_validate(data)

    # ------------------------------------------------------------------ Visualization
    def inspect(self, show_docs: bool = False) -> None:
        """Render the nested configuration as a Rich tree on the project console.

        Args:
            show_docs: Include class and field documentation alongside values.
        """
        tree = self._build_tree(show_docs=show_docs, _seen_singletons=set())
        Console.from_callsite(stack_offset=1).print(tree, soft_wrap=False, highlight=True, markup=True, emoji=False)

    def _build_tree(  # pragma: no cover - visualization helper
        self,
        show_docs: bool = False,
        _seen_singletons: set[int] | None = None,
        _is_top_level: bool = True,
        _seen_path_configs: set[int] | None = None,
    ) -> Tree:
        if _seen_singletons is None:
            _seen_singletons = set()
        if _seen_path_configs is None:
            _seen_path_configs = set()

        tree = Tree(Text(self.__class__.__name__, style="config.name"))

        if show_docs and self.__class__.__doc__:
            tree.add(Text(self.__class__.__doc__, style="config.doc"))

        for field_name, field in self.__class__.model_fields.items():
            value = getattr(self, field_name)
            field_style = "config.propagated" if field_name in self.propagated_fields else "config.field"

            # Handle singleton configs (only once)
            if isinstance(value, SingletonConfig):
                # Check if it's a PathConfig
                is_path_config = value.__class__.__name__ == "PathConfig"

                # If it's a PathConfig and we're not at the top level, just show a reference
                if is_path_config and not _is_top_level:
                    tree.add(
                        Text(
                            f"{field_name}: {value.__class__.__name__}(Singleton)",
                            style="config.value",
                        )
                    )
                    continue

                # Regular singleton handling
                if id(value) in _seen_singletons:
                    tree.add(
                        Text(
                            f"{field_name}: {value.__class__.__name__}(Singleton)",
                            style="config.value",
                        )
                    )
                    continue

                _seen_singletons.add(id(value))
                subtree = tree.add(Text(f"{field_name}:", style=field_style))
                subtree.add(
                    value._build_tree(
                        show_docs=show_docs,
                        _seen_singletons=_seen_singletons,
                        _is_top_level=False,
                        _seen_path_configs=_seen_path_configs,
                    )
                )
                continue

            # Create field node text
            field_text = Text()
            field_text.append(f"{field_name}: ", style=field_style)

            # Handle nested configs
            if isinstance(value, BaseConfig):
                # Special handling for PathConfig
                is_path_config = value.__class__.__name__ == "PathConfig"

                # If it's a PathConfig and we're not at the top level, just show a reference
                if is_path_config and not _is_top_level:
                    tree.add(
                        Text(
                            f"{field_name}: {value.__class__.__name__}(Singleton)",
                            style="config.value",
                        )
                    )
                    continue

                subtree = tree.add(field_text)
                nested_tree = value._build_tree(
                    show_docs=show_docs,
                    _seen_singletons=_seen_singletons,
                    _is_top_level=False,
                    _seen_path_configs=_seen_path_configs,
                )
                subtree.add(nested_tree)
                continue

            # Handle lists/tuples of configs
            if isinstance(value, (list, tuple)) and value and isinstance(value[0], BaseConfig):
                subtree = tree.add(field_text)
                for i, item in enumerate(value):
                    # SingletonConfig handling in lists
                    if isinstance(item, SingletonConfig):
                        # Check if it's a PathConfig
                        is_path_config = item.__class__.__name__ == "PathConfig"

                        # If it's a PathConfig and we're not at the top level, just show a reference
                        if is_path_config and not _is_top_level:
                            subtree.add(
                                Text(
                                    f"[{i}]: {item.__class__.__name__}(Singleton)",
                                    style="config.value",
                                )
                            )
                            continue

                        if id(item) in _seen_singletons:
                            subtree.add(
                                Text(
                                    f"[{i}]: {item.__class__.__name__}(Singleton)",
                                    style="config.value",
                                )
                            )
                            continue
                        _seen_singletons.add(id(item))
                        item_subtree = subtree.add(Text(f"[{i}]:", style="config.field"))
                        item_subtree.add(
                            item._build_tree(
                                show_docs=show_docs,
                                _seen_singletons=_seen_singletons,
                                _is_top_level=False,
                                _seen_path_configs=_seen_path_configs,
                            )
                        )
                        continue

                    # Check if regular item is a PathConfig
                    is_path_config = item.__class__.__name__ == "PathConfig"
                    if is_path_config and not _is_top_level:
                        subtree.add(
                            Text(
                                f"[{i}]: {item.__class__.__name__}(Reference)",
                                style="config.value",
                            )
                        )
                        continue

                    item_tree = item._build_tree(
                        show_docs=show_docs,
                        _seen_singletons=_seen_singletons,
                        _is_top_level=False,
                        _seen_path_configs=_seen_path_configs,
                    )
                    subtree.add(Text(f"[{i}]", style="config.field")).add(item_tree)
                continue

            # Format value
            value_str = self._format_value(value)
            field_text.append(value_str, style="config.value")

            # Add type info
            type_name = self._get_type_name(field.annotation)
            field_text.append(f" ({type_name})", style="config.type")

            # Add field and documentation
            field_node = tree.add(field_text)
            if show_docs and field.description:
                field_node.add(Text(field.description, style="config.doc"))

        return tree

    def _format_value(self, value: Any) -> str:  # pragma: no cover - visualization helper
        """Format a value for display."""
        try:
            if isinstance(value, str):
                return f'"{value}"'
            if isinstance(value, (int, float, bool)):
                return str(value)
            if isinstance(value, Enum):
                return str(value.value if hasattr(value, "value") else value)
            if isinstance(value, Path):
                return str(value)
            if isinstance(value, dict):
                if not value:
                    return "{}"
                items = [f"{k}: {repr(v)}" for k, v in value.items()]
                return "{" + ", ".join(items) + "}"
            if value is None:
                return "None"
            if isinstance(value, type):
                return value.__name__
            return repr(value)
        except Exception:
            return "<unprintable>"

    def _get_type_name(self, annotation: Any) -> str:  # pragma: no cover - visualization helper
        """Get type name from annotation."""
        try:
            if hasattr(annotation, "__origin__"):
                origin = annotation.__origin__.__name__
                args = []
                for arg in annotation.__args__:
                    if isinstance(arg, ForwardRef):
                        args.append(arg.__forward_arg__)
                    elif hasattr(arg, "__name__"):
                        args.append(arg.__name__)
                    else:
                        args.append(str(arg))
                return f"{origin}[{', '.join(args)}]"
            return str(annotation).replace("typing.", "")
        except Exception:
            return "Any"

    @model_validator(mode="after")
    def _propagate_shared_fields(self) -> "BaseConfig":
        """Propagate shared field values to nested BaseConfig instances."""
        for field_name, field_value in self:
            if field_name in {"propagated_fields", "target", "target_type"}:
                continue

            if isinstance(field_value, BaseConfig):
                self._propagate_to_child(field_name, field_value)

            elif isinstance(field_value, (list, tuple)):
                for item in field_value:
                    if isinstance(item, BaseConfig):
                        self._propagate_to_child(field_name, item)

        return self

    def _propagate_to_child(self, parent_field: str, child_config: "BaseConfig") -> None:
        """Propagate matching fields from parent to child config.

        Uses setattr() to ensure child validators run after propagation,
        allowing debug-mode logic and other validators to execute properly.
        """
        shared_fields = {
            name: value
            for name, value in self
            if name in child_config.__class__.model_fields
            and name != parent_field
            and name not in self.propagation_exclude_fields
            and name not in child_config.propagation_exclude_fields
            and name not in ("propagated_fields", "target", "target_type")
        }

        for name, value in shared_fields.items():
            current_value = getattr(child_config, name, None)
            if current_value != value:
                # Use regular setattr to trigger validators
                setattr(child_config, name, value)
                child_config.propagated_fields[name] = value

                Console.from_callsite(stack_offset=1).log(
                    f"Propagated {name}={value} from {self.__class__.__name__} to {child_config.__class__.__name__}"
                )

    # ------------------------------------------------------------------ TOML utils
    @classmethod
    def _load_toml_path(cls, path: Path) -> dict[str, Any]:
        class _TomlReader(BaseSettings):
            model_config = SettingsConfigDict(toml_file=path)

        source = TomlConfigSettingsSource(_TomlReader, toml_file=path)
        return source()

    @classmethod
    def _toml_normalize(cls, value: Any) -> Any:
        if isinstance(value, BaseConfig):
            return cls._toml_normalize(value.model_dump(exclude_none=True))
        if isinstance(value, dict):
            return {key: cls._toml_normalize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [cls._toml_normalize(item) for item in value]
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, torch.device):
            return str(value)
        if isinstance(value, torch.dtype):
            return str(value)
        if isinstance(value, torch.Tensor):
            return value.detach().cpu().tolist()
        if isinstance(value, Enum):
            enum_value = value.value if hasattr(value, "value") else str(value)
            return enum_value
        return value


class TargetConfig(BaseConfig, Generic[TargetT]):
    """Typed config-as-factory base whose `setup_target` returns `TargetT`.

    `TargetT` describes the runtime object returned by `setup_target`; it does
    not have to be the same type as `target_type` when the target delegates to a
    custom factory method.
    """

    def setup_target(self, *args: Any, **kwargs: Any) -> TargetT:
        """Instantiate or return the typed target object for this config."""
        return cast(
            TargetT,
            self._setup_target_from_factory(
                *args,
                _allow_missing_target=False,
                **kwargs,
            ),
        )


class SingletonConfig(BaseConfig):
    """Base class for singleton configurations."""

    _instances: ClassVar[dict[type, Any]] = {}
    _lock: ClassVar[Lock] = Lock()

    model_config = SettingsConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
        validate_default=True,
    )

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        with cls._lock:
            if cls not in cls._instances:
                instance = super(BaseConfig, cls).__new__(cls)
                instance.__dict__["_initialized"] = False
                cls._instances[cls] = instance
            return cast(Self, cls._instances[cls])

    def __init__(self, **kwargs: Any) -> None:
        if not getattr(self, "_initialized", False):
            super().__init__(**kwargs)
            self.__dict__["_initialized"] = True
        else:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    current = getattr(self, key)
                    if current != value:
                        Console.from_callsite(stack_offset=1).log(
                            f"Updating singleton {self.__class__.__name__} field '{key}' from {current} to {value}"
                        )
                    setattr(self, key, value)

    def __copy__(self) -> "SingletonConfig":
        """Return self since this is a singleton."""
        return self

    def __deepcopy__(self, memo: dict[int, Any] | None = None) -> "SingletonConfig":
        """Return self since this is a singleton. Implements proper deepcopy protocol."""
        if memo is not None:
            memo[id(self)] = self
        return self
