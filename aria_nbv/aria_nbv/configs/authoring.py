"""Comment-preserving, optimistic-concurrency authoring for trusted configs.

``ConfigDocument`` is the filesystem seam used by CLI and Streamlit authoring.
It parses TOML with :mod:`tomlkit`, validates the complete tree with a caller-
supplied :class:`aria_nbv.utils.BaseConfig` subtype, and promotes writes only
when the originally observed file digest still matches.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Generic, TypeAlias, TypeVar, cast, get_args, get_origin

import tomlkit
from pydantic import ValidationError
from pydantic.errors import PydanticInvalidForJsonSchema
from pydantic_core import PydanticSerializationError, PydanticUndefined
from tomlkit.toml_document import TOMLDocument

from ..utils.base_config import BaseConfig
from .field_docs import inherited_field_docstring

ConfigT = TypeVar("ConfigT", bound=BaseConfig)

ConfigScalar: TypeAlias = None | bool | int | float | str
"""JSON/TOML scalar retained by the metadata-only authoring seam."""

ConfigValue: TypeAlias = ConfigScalar | list["ConfigValue"] | dict[str, "ConfigValue"]
"""JSON/TOML-compatible value used by config descriptors and patches."""


class ConfigAuthoringError(ValueError):
    """Base error for parse, validation, policy, and write failures."""


class ConfigConflictError(ConfigAuthoringError):
    """Raised when a source file changed after it was inspected."""


@dataclass(frozen=True, slots=True)
class ConfigFieldDescriptor:
    """Schema and source documentation for one editable field.

    Attributes:
        path: Dotted path within the validated configuration tree.
        title: Human-readable schema title.
        annotation: Stable textual form of the Python annotation.
        documentation: Inline field docstring from the nearest source owner.
        required: Whether the validated model requires the field.
        default: JSON-compatible default, or ``None`` when absent.
        choices: Closed enum or ``Literal`` choices, if any.
        allows_none: Whether omission represents an explicit optional value.
        minimum: Inclusive or exclusive lower numeric bound when declared.
        maximum: Inclusive or exclusive upper numeric bound when declared.
        editable: Whether trusted authoring surfaces may change this field.
        sensitive: Whether presentation surfaces must conceal the value.
        theory_ids: Canonical Typst-derived theory identifiers relevant to the field.
    """

    path: str
    """Dotted path within the validated configuration tree."""

    title: str
    """Human-readable schema title."""

    annotation: str
    """Stable textual form of the Python annotation."""

    documentation: str | None
    """Inline field docstring from the nearest source owner."""

    required: bool
    """Whether the validated model requires the field."""

    default: ConfigValue
    """JSON-compatible default value, or ``None`` when no default exists."""

    choices: tuple[ConfigValue, ...]
    """Closed enum or ``Literal`` choices, if any."""

    allows_none: bool
    """Whether the Python annotation admits ``None``."""

    minimum: float | int | None
    """Declared lower numeric bound, irrespective of inclusive/exclusive form."""

    maximum: float | int | None
    """Declared upper numeric bound, irrespective of inclusive/exclusive form."""

    editable: bool
    """Whether trusted authoring surfaces may change this field."""

    sensitive: bool
    """Whether presentation surfaces must conceal the field value."""

    theory_ids: tuple[str, ...]
    """Canonical theory identifiers attached through ``json_schema_extra['aria']``."""


@dataclass(frozen=True, slots=True)
class ConfigDiffEntry:
    """One semantic value change between the opened and validated draft."""

    path: str
    """Dotted field path."""

    before: ConfigValue
    """Original JSON-compatible value."""

    after: ConfigValue
    """Validated draft value."""


@dataclass(frozen=True, slots=True)
class ConfigDiff:
    """Canonical semantic changes for one authoring transaction."""

    entries: tuple[ConfigDiffEntry, ...]
    """Changes sorted by dotted field path."""

    @property
    def is_empty(self) -> bool:
        """Return whether the validated draft is semantically unchanged."""

        return not self.entries


@dataclass(frozen=True, slots=True)
class ConfigWriteReceipt:
    """Identity of one atomically promoted configuration file."""

    path: Path
    """Absolute destination path."""

    sha256: str
    """SHA-256 digest of the exact written TOML bytes."""

    previous_sha256: str | None
    """Digest of a replaced destination, when one existed."""

    changed: bool
    """Whether destination bytes differed from the promoted bytes."""


class ConfigDocument(Generic[ConfigT]):
    """Inspect, patch, diff, and atomically save one trusted TOML config.

    ``open`` and ``describe`` are metadata-only: they validate values and read
    Python source/schema metadata but never call ``setup_target``. A patch is
    applied to a tomlkit tree so unrelated comments, ordering, and whitespace
    survive. ``save_copy`` uses the digest observed at ``open`` as a compare-
    and-swap token and writes through a same-directory temporary file.
    """

    def __init__(
        self,
        *,
        path: Path,
        model: type[ConfigT],
        source_text: str,
        document: TOMLDocument,
        config: ConfigT,
    ) -> None:
        self.path = path
        self.model = model
        self.source_text = source_text
        self.source_sha256 = _sha256(source_text.encode("utf-8"))
        self.config = config
        self._document = document
        self._draft_document = document.copy()
        self._draft_config = config

    @classmethod
    def open(cls, path: Path, model: type[ConfigT]) -> "ConfigDocument[ConfigT]":
        """Open and validate a TOML file without constructing its runtime target."""

        resolved = path.expanduser().resolve(strict=True)
        source_text = resolved.read_text(encoding="utf-8")
        try:
            document = tomlkit.parse(source_text)
            config = model.model_validate(document.unwrap())
        except (tomlkit.exceptions.ParseError, ValidationError) as exc:
            raise ConfigAuthoringError(f"Invalid config {resolved}: {exc}") from exc
        return cls(path=resolved, model=model, source_text=source_text, document=document, config=config)

    def describe(self) -> tuple[ConfigFieldDescriptor, ...]:
        """Return schema-derived field descriptors without evaluating runtime targets."""

        return tuple(_describe_model(self.model))

    def validate_patch(self, patch: Mapping[str, ConfigValue]) -> ConfigT:
        """Apply a partial mapping to the TOML tree and validate the complete config.

        The validated draft becomes the value subsequently reported by
        :meth:`diff` and written by :meth:`save_copy`. Locked fields reject
        changes before validation; sensitive fields may still be changed by
        trusted callers but presentation surfaces must conceal them.
        """

        _reject_locked_patch(self.model, patch)
        draft = self._document.copy()
        _merge_mapping(draft, patch)
        try:
            config = cast(ConfigT, self.model.model_validate(draft.unwrap()))
        except ValidationError as exc:
            raise ConfigAuthoringError(str(exc)) from exc
        self._draft_document = draft
        self._draft_config = config
        return config

    def diff(self, updated: ConfigT | None = None) -> ConfigDiff:
        """Return semantic changes against the originally opened config."""

        candidate = updated or self._draft_config
        before = _flatten(self.config.model_dump(mode="json"))
        after = _flatten(candidate.model_dump(mode="json"))
        entries = tuple(
            ConfigDiffEntry(path=path, before=before.get(path), after=after.get(path))
            for path in sorted(before.keys() | after.keys())
            if before.get(path) != after.get(path)
        )
        return ConfigDiff(entries=entries)

    def save_copy(
        self,
        destination: Path,
        *,
        expected_sha256: str,
    ) -> ConfigWriteReceipt:
        """Atomically promote the validated draft after source-digest verification.

        Args:
            destination: New file or explicitly selected overwrite target.
            expected_sha256: Digest returned when this document was opened.

        Raises:
            ConfigConflictError: If the opened source changed or the supplied
                digest is not the one observed by this document.
        """

        if expected_sha256 != self.source_sha256:
            raise ConfigConflictError("Expected digest does not match the opened config.")
        current = self.path.read_bytes()
        current_sha256 = _sha256(current)
        if current_sha256 != expected_sha256:
            raise ConfigConflictError(
                f"Config changed since inspection: expected {expected_sha256}, observed {current_sha256}."
            )
        target = destination.expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        rendered = tomlkit.dumps(self._draft_document).encode("utf-8")
        previous = target.read_bytes() if target.exists() else None
        previous_sha256 = _sha256(previous) if previous is not None else None
        if previous == rendered:
            return ConfigWriteReceipt(
                path=target,
                sha256=_sha256(rendered),
                previous_sha256=previous_sha256,
                changed=False,
            )
        fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(rendered)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return ConfigWriteReceipt(
            path=target,
            sha256=_sha256(rendered),
            previous_sha256=previous_sha256,
            changed=True,
        )


def _describe_model(model: type[BaseConfig], prefix: str = "") -> list[ConfigFieldDescriptor]:
    try:
        schema = model.model_json_schema()
    except (PydanticInvalidForJsonSchema, PydanticSerializationError):
        schema = {}
    properties = schema.get("properties", {})
    required = set(schema.get("required", ()))
    output: list[ConfigFieldDescriptor] = []
    for name, field in model.model_fields.items():
        path = f"{prefix}.{name}" if prefix else name
        field_schema = properties.get(name, {})
        policy = _aria_policy(field.json_schema_extra)
        annotation = field.annotation
        choices = _schema_choices(field_schema) or _annotation_choices(annotation)
        default = field_schema.get("default", _field_default(field))
        output.append(
            ConfigFieldDescriptor(
                path=path,
                title=str(field_schema.get("title", field.title or name.replace("_", " ").title())),
                annotation=_annotation_name(annotation),
                documentation=inherited_field_docstring(model, name),
                required=name in required or field.is_required(),
                default=default,
                choices=choices,
                allows_none=_allows_none(annotation),
                minimum=_coalesce_bound(
                    _schema_bound(field_schema, "minimum", "exclusiveMinimum"),
                    _metadata_bound(field.metadata, "ge", "gt"),
                ),
                maximum=_coalesce_bound(
                    _schema_bound(field_schema, "maximum", "exclusiveMaximum"),
                    _metadata_bound(field.metadata, "le", "lt"),
                ),
                editable=bool(policy.get("editable", True)) and not bool(policy.get("locked", False)),
                sensitive=bool(policy.get("sensitive", False)),
                theory_ids=_theory_ids(policy),
            )
        )
        nested = _nested_model(annotation)
        if nested is not None:
            output.extend(_describe_model(nested, path))
    return output


def describe_config_model(model: type[BaseConfig]) -> tuple[ConfigFieldDescriptor, ...]:
    """Return schema/documentation descriptors for an in-memory config model."""

    return tuple(_describe_model(model))


def _theory_ids(policy: Mapping[str, Any]) -> tuple[str, ...]:
    value = policy.get("theory_ids", ())
    if not isinstance(value, list | tuple | set):
        return ()
    return tuple(str(identifier) for identifier in value)


def _reject_locked_patch(model: type[BaseConfig], patch: Mapping[str, ConfigValue], prefix: str = "") -> None:
    for name, value in patch.items():
        field = model.model_fields.get(name)
        path = f"{prefix}.{name}" if prefix else name
        if field is None:
            continue
        policy = _aria_policy(field.json_schema_extra)
        if bool(policy.get("locked", False)) or policy.get("editable") is False:
            raise ConfigAuthoringError(f"Field {path!r} is locked for authoring.")
        nested = _nested_model(field.annotation)
        if nested is not None and isinstance(value, Mapping):
            _reject_locked_patch(nested, value, path)


def _merge_mapping(container: MutableMapping[str, Any], patch: Mapping[str, ConfigValue]) -> None:
    for key, value in patch.items():
        if value is None:
            container.pop(key, None)
            continue
        current = container.get(key)
        if isinstance(value, Mapping) and isinstance(current, MutableMapping):
            _merge_mapping(current, value)
        else:
            container[key] = tomlkit.item(_jsonable(value))


def _jsonable(value: Any) -> ConfigValue:
    if isinstance(value, BaseConfig):
        return _jsonable(value.model_dump(mode="json", exclude_none=True))
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Enum):
        return _jsonable(value.value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple | list | set):
        return [_jsonable(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported config value type: {type(value).__name__}")


def _flatten(value: Any, prefix: str = "") -> dict[str, ConfigValue]:
    if isinstance(value, Mapping):
        output: dict[str, ConfigValue] = {}
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            output.update(_flatten(item, child))
        return output
    return {prefix: _jsonable(value)}


def _aria_policy(extra: Any) -> Mapping[str, Any]:
    if not isinstance(extra, Mapping):
        return {}
    aria = extra.get("aria", {})
    return aria if isinstance(aria, Mapping) else {}


def _nested_model(annotation: Any) -> type[BaseConfig] | None:
    if isinstance(annotation, type) and issubclass(annotation, BaseConfig):
        return annotation
    for argument in get_args(annotation):
        if isinstance(argument, type) and issubclass(argument, BaseConfig):
            return argument
    return None


def _annotation_choices(annotation: Any) -> tuple[ConfigValue, ...]:
    origin = get_origin(annotation)
    if str(origin).endswith("Literal"):
        return tuple(_jsonable(value) for value in get_args(annotation))
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return tuple(member.value for member in annotation)
    for argument in get_args(annotation):
        choices = _annotation_choices(argument)
        if choices:
            return choices
    return ()


def _schema_choices(schema: Mapping[str, Any]) -> tuple[ConfigValue, ...]:
    direct = schema.get("enum")
    if isinstance(direct, list):
        return tuple(value for value in direct if value is not None)
    choices: list[ConfigValue] = []
    branches = schema.get("anyOf", ())
    for branch in branches if isinstance(branches, list) else ():
        if isinstance(branch, Mapping):
            choices.extend(_schema_choices(branch))
    return tuple(dict.fromkeys(choices))


def _schema_bound(schema: Mapping[str, Any], inclusive: str, exclusive: str) -> float | int | None:
    value = schema.get(inclusive, schema.get(exclusive))
    if isinstance(value, int | float) and not isinstance(value, bool):
        return value
    branches = schema.get("anyOf", ())
    if isinstance(branches, list):
        for branch in branches:
            if isinstance(branch, Mapping) and (value := _schema_bound(branch, inclusive, exclusive)) is not None:
                return value
    return None


def _allows_none(annotation: Any) -> bool:
    if annotation is type(None):
        return True
    return any(_allows_none(argument) for argument in get_args(annotation))


def _field_default(field: Any) -> ConfigValue:
    value = getattr(field, "default", PydanticUndefined)
    if value is PydanticUndefined:
        return None
    return _jsonable(value) if not isinstance(value, type) else f"{value.__module__}.{value.__qualname__}"


def _metadata_bound(metadata: list[Any], inclusive: str, exclusive: str) -> float | int | None:
    for constraint in metadata:
        value = getattr(constraint, inclusive, getattr(constraint, exclusive, None))
        if isinstance(value, int | float) and not isinstance(value, bool):
            return value
    return None


def _coalesce_bound(first: float | int | None, second: float | int | None) -> float | int | None:
    return second if first is None else first


def _annotation_name(annotation: Any) -> str:
    return getattr(annotation, "__name__", str(annotation).replace("typing.", ""))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


__all__ = [
    "ConfigAuthoringError",
    "ConfigConflictError",
    "ConfigDiff",
    "ConfigDiffEntry",
    "ConfigDocument",
    "ConfigFieldDescriptor",
    "ConfigScalar",
    "ConfigValue",
    "ConfigWriteReceipt",
    "describe_config_model",
]
