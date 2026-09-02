"""Trusted, metadata-only Streamlit authoring for ``BaseConfig`` TOML files."""

from __future__ import annotations

import inspect
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Generic, TypeVar, cast

import streamlit as st
from pydantic import ValidationError

from ...configs import (
    ConfigAuthoringError,
    ConfigDocument,
    ConfigFieldDescriptor,
    ConfigValue,
    ConfigWriteReceipt,
    PathConfig,
    describe_config_model,
)
from ...utils import BaseConfig

ConfigT = TypeVar("ConfigT", bound=BaseConfig)


@dataclass(frozen=True, slots=True)
class ConfigEditorResult(Generic[ConfigT]):
    """Result of one metadata-only Streamlit config editing transaction.

    The adapter validates a draft through :class:`ConfigDocument`; it never
    constructs the runtime target. Callers decide whether and when to invoke
    ``ConfigT.setup_target()`` after an explicit submit.
    """

    config: ConfigT
    """Last validated config, or the opened config before submission."""

    submitted: bool
    """Whether the user submitted validation or save in this rerun."""

    receipt: ConfigWriteReceipt | None
    """Atomic save receipt when the user requested a save copy."""

    validation_succeeded: bool = False
    """Whether the current submitted draft passed complete Pydantic validation."""


@dataclass(frozen=True, slots=True)
class ConfigSelection(Generic[ConfigT]):
    """One validated TOML variant selected by a Streamlit page."""

    path: Path
    config: ConfigT


def trusted_config_catalog() -> dict[str, type[BaseConfig]]:
    """Return explicitly imported root config models available to the workspace.

    The catalog is code-owned and evaluated only when the user selects this
    page. TOML files cannot request arbitrary imports or discover subclasses.
    Importing these classes does not call ``setup_target``.
    """

    from ...lightning.cli import CLIAriaNBVExperimentConfig
    from ...oracle.pipelines.campaign import CudaRolloutCampaignConfig
    from ...oracle.pipelines.offline_vin import VinOfflineWriterConfig
    from ...oracle.pipelines.rollout_dataset import RolloutDatasetWriterConfig
    from ...reporting import ScientificReportConfig
    from ...rerun_inspector._config import RerunOfflineInspectorConfig
    from ..config import NbvStreamlitAppConfig

    return {
        "Training experiment": CLIAriaNBVExperimentConfig,
        "Rollout campaign": CudaRolloutCampaignConfig,
        "Rollout writer": RolloutDatasetWriterConfig,
        "Offline VIN writer": VinOfflineWriterConfig,
        "Rerun inspector": RerunOfflineInspectorConfig,
        "Streamlit app": NbvStreamlitAppConfig,
        "Scientific report": ScientificReportConfig,
    }


def trusted_config_patterns() -> dict[str, tuple[str, ...]]:
    """Return code-owned file patterns paired with the trusted root models."""

    return {
        "Training experiment": ("offline_only.toml", "offline_smoke_2epoch.toml"),
        "Rollout campaign": (
            "build_rollouts_v2_cuda_campaign.toml",
            "build_rollouts_v1_cuda_campaign.toml",
            "build_rollouts_v1_cuda_campaign_pilot_corrected_v*.toml",
        ),
        "Rollout writer": (
            "build_rollouts_v2_cuda_campaign_writer.toml",
            "build_rollouts_v2_realistic.toml",
            "build_rollouts_v3_target_shell_experiment.toml",
            "build_rollouts_qh_v0_baseline.toml",
            "build_rollouts_v1_diverse.toml",
            "build_rollouts_v1_lrz.template.toml",
            "build_rollouts_v1_microset.toml",
            "build_rollouts_v1_multihorizon_highgain.toml",
            "build_rollouts_v1_smoke.toml",
        ),
        "Offline VIN writer": ("build_vin_offline*.toml",),
        "Rerun inspector": ("rerun_offline.toml",),
        "Streamlit app": ("streamlit_app*.toml",),
        "Scientific report": ("reports/*.toml",),
    }


def render_configuration_workspace(
    catalog: Mapping[str, type[BaseConfig]],
    *,
    configs_dir: Path | None = None,
    path_patterns: Mapping[str, tuple[str, ...]] | None = None,
) -> None:
    """Inspect, validate, diff, and save a trusted config without runtime setup.

    Widgets are derived from Pydantic schema plus source-owned inline field
    docstrings. Scientific/theory IDs and write policy come from structured
    ``json_schema_extra['aria']`` metadata. Save-as-copy is the default and all
    writes carry the digest observed when the source file was opened.
    """

    st.header("Configuration Workspace")
    st.caption(
        "Inspect and safely author trusted TOML configuration. Validation never constructs a training, generation, "
        "Rerun, W&B, or reporting target."
    )
    root = (configs_dir or PathConfig().configs_dir).expanduser().resolve()
    model_name = st.selectbox("Root config model", options=tuple(catalog), key="config_workspace_model")
    patterns = (path_patterns or {}).get(model_name, ("**/*.toml",))
    paths = ordered_config_paths(root, patterns)
    if not paths:
        st.info(f"No trusted {model_name} TOML configs found below {root}.")
        return
    selected_path = st.selectbox(
        "TOML file",
        options=paths,
        format_func=lambda path: path.relative_to(root).as_posix(),
        key="config_workspace_path",
    )
    model = catalog[model_name]
    try:
        document = ConfigDocument.open(selected_path, model)
    except ConfigAuthoringError as exc:
        st.error(str(exc))
        return
    source_file = inspect.getsourcefile(model)
    source_link = None
    if source_file is not None:
        try:
            relative_source = Path(source_file).resolve().relative_to(PathConfig().root)
            source_link = "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/" + relative_source.as_posix()
        except ValueError:
            source_link = None
    module_reference = model.__module__.removeprefix("aria_nbv.")
    links = [f"[generated API](/reference/{module_reference}.html)"]
    if source_link is not None:
        links.append(f"[Python owner]({source_link})")
    st.caption(f"Root model `{model.__module__}.{model.__qualname__}` · " + " · ".join(links))
    model_docstring = inspect.getdoc(model)
    if model_docstring:
        with st.expander("Root model contract"):
            st.markdown(model_docstring)
    st.caption(f"Source SHA-256: `{document.source_sha256}`")
    render_config_document(
        document,
        save_root=root,
        save_name=f"{selected_path.stem}.edited.toml",
        key_prefix="config_workspace",
    )


def render_config_document(
    document: ConfigDocument[ConfigT],
    *,
    save_root: Path,
    save_name: str,
    key_prefix: str,
) -> ConfigEditorResult[ConfigT]:
    """Render one reusable schema-driven editor for an opened config document.

    The document is already validated before entering this adapter. The form
    only edits JSON/TOML-compatible values and delegates validation and atomic
    persistence back to :class:`ConfigDocument`; it never evaluates a target.
    """

    descriptors = document.describe()
    current = cast(dict[str, ConfigValue], document.config.model_dump(mode="json"))
    patch: dict[str, ConfigValue] = {}
    form_key = f"{key_prefix}:form"
    with st.form(form_key):
        st.subheader("Validated fields")
        for descriptor in descriptors:
            value = _value_at(current, descriptor.path)
            if isinstance(value, dict) and any(item.path.startswith(f"{descriptor.path}.") for item in descriptors):
                continue
            updated = _field_widget(descriptor, value, key_prefix=key_prefix)
            if updated != value:
                _set_patch(patch, descriptor.path, updated)
        requested_name = st.text_input(
            "Save copy as",
            value=save_name,
            help="Relative names are saved below the configured config directory.",
            key=f"{key_prefix}:save_name",
        )
        validate = st.form_submit_button("Validate draft", icon=":material/fact_check:")
        save = st.form_submit_button("Validate and save copy", type="primary", icon=":material/save:")
    if not validate and not save:
        return ConfigEditorResult(config=document.config, submitted=False, receipt=None)
    try:
        updated = document.validate_patch(patch)
    except ConfigAuthoringError as exc:
        st.error(str(exc))
        return ConfigEditorResult(config=document.config, submitted=True, receipt=None)
    diff = document.diff(updated)
    if diff.is_empty:
        st.success("Draft is valid and semantically unchanged.")
    else:
        st.dataframe(
            [
                {"field": entry.path, "before": entry.before, "after": entry.after}
                for entry in diff.entries
                if (descriptor := _descriptor_for(descriptors, entry.path)) is None or not descriptor.sensitive
            ],
            hide_index=True,
        )
    receipt: ConfigWriteReceipt | None = None
    if save:
        requested_destination = Path(requested_name).expanduser()
        destination = (
            requested_destination.resolve()
            if requested_destination.is_absolute()
            else (save_root / requested_destination).resolve()
        )
        if not destination.is_relative_to(save_root):
            st.error(f"Saved config copies must remain below `{save_root}`.")
            return ConfigEditorResult(config=updated, submitted=True, receipt=None, validation_succeeded=True)
        try:
            receipt = document.save_copy(destination, expected_sha256=document.source_sha256)
        except ConfigAuthoringError as exc:
            st.error(str(exc))
            return ConfigEditorResult(config=updated, submitted=True, receipt=None, validation_succeeded=True)
        st.success(f"Saved `{receipt.path}` with SHA-256 `{receipt.sha256}`.")
    return ConfigEditorResult(config=updated, submitted=True, receipt=receipt, validation_succeeded=True)


def select_toml_config(
    model: type[ConfigT],
    paths: Sequence[Path],
    *,
    ui: Any = st,
    label: str,
    key_prefix: str,
    allow_none: bool = False,
    none_label: str = "(interactive defaults)",
    disabled: bool = False,
) -> ConfigSelection[ConfigT] | None:
    """Select and validate one trusted TOML variant without constructing a target.

    The selector is the shared GUI seam for campaign, rollout, and live-candidate
    pages. Pydantic performs the complete parse/validation; callers explicitly
    decide whether to call ``setup_target`` after selection.
    """

    # Preserve caller order: it is the source-owned reviewed default order.
    # Sorting here can silently select an older campaign/profile on first load.
    ordered_paths = tuple(dict.fromkeys(path.expanduser().resolve() for path in paths))
    if not ordered_paths:
        ui.info(f"No validated {model.__name__} TOML variants are available.")
        return None
    options: tuple[Path | None, ...] = ((None,) if allow_none else ()) + ordered_paths
    selected = ui.selectbox(
        label,
        options=options,
        format_func=lambda path: none_label if path is None else path.name,
        key=f"{key_prefix}:path",
        disabled=disabled,
    )
    if selected is None:
        return None
    try:
        return ConfigSelection(path=selected, config=ConfigDocument.open(selected, model).config)
    except (ConfigAuthoringError, OSError) as exc:
        ui.error(f"Invalid {selected.name}: {exc}")
        return None


def ordered_config_paths(root: Path, patterns: Sequence[str]) -> tuple[Path, ...]:
    """Expand trusted patterns deterministically without changing pattern order."""

    paths: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        for path in sorted(root.glob(pattern), key=lambda candidate: candidate.as_posix()):
            resolved = path.expanduser().resolve()
            if resolved not in seen:
                seen.add(resolved)
                paths.append(resolved)
    return tuple(paths)


def render_typed_config_fields(
    config: ConfigT,
    *,
    ui: Any = st,
    key_prefix: str,
    excluded_paths: frozenset[str] = frozenset(),
    choices: Mapping[str, Sequence[ConfigValue]] | None = None,
    bounds: Mapping[str, tuple[float | int | None, float | int | None]] | None = None,
) -> ConfigT:
    """Render schema-driven controls and return a revalidated config copy.

    Pydantic field metadata determines the Streamlit widget: closed choices use
    select boxes, booleans use checkboxes, numeric bounds use number inputs, and
    structured values use JSON text areas. The returned model is validated before
    leaving the adapter and no runtime target is created. ``choices`` supplies
    explicit finite alternatives for fields whose domain type is runtime-only
    (for example ``torch.device``) and therefore has no JSON-schema enum.
    ``bounds`` supplies presentation bounds for operationally constrained fields
    whose Pydantic model intentionally remains broad for programmatic callers.
    """

    current = _config_widget_values(config.model_dump(mode="python"))
    patch: dict[str, ConfigValue] = {}
    descriptors = describe_config_model(type(config))
    for descriptor in descriptors:
        if descriptor.path in excluded_paths:
            continue
        value = _value_at(current, descriptor.path)
        if isinstance(value, dict) and any(item.path.startswith(f"{descriptor.path}.") for item in descriptors):
            continue
        choice_override = tuple((choices or {}).get(descriptor.path, ()))
        minimum_override, maximum_override = (bounds or {}).get(descriptor.path, (None, None))
        updated = _field_widget(
            descriptor,
            value,
            key_prefix=key_prefix,
            ui=ui,
            choice_override=choice_override,
            minimum_override=minimum_override,
            maximum_override=maximum_override,
        )
        if updated != value:
            _set_patch(patch, descriptor.path, updated)
    if not patch:
        return config
    merged = dict(current)
    _merge_value_patch(merged, patch)
    try:
        validated = type(config).model_validate(merged)
    except (ValidationError, TypeError, ValueError) as exc:
        ui.error(f"Invalid configuration draft: {exc}")
        return config
    return cast(ConfigT, validated)


def _config_widget_values(value: Any) -> dict[str, ConfigValue]:
    """Convert a Pydantic model dump into values accepted by Streamlit widgets."""

    if isinstance(value, BaseConfig):
        value = value.model_dump(mode="python")
    if not isinstance(value, Mapping):
        raise TypeError("Config field rendering requires a mapping model dump.")

    def convert(item: Any) -> ConfigValue:
        if isinstance(item, BaseConfig):
            return convert(item.model_dump(mode="python"))
        if isinstance(item, Path):
            return item.as_posix()
        if isinstance(item, Enum):
            return convert(item.value)
        if isinstance(item, Mapping):
            return {str(key): convert(child) for key, child in item.items()}
        if isinstance(item, tuple | list | set):
            return [convert(child) for child in item]
        tolist = getattr(item, "tolist", None)
        if callable(tolist):
            return convert(tolist())
        if item is None or isinstance(item, (str, int, float, bool)):
            return item
        return str(item)

    return {str(key): convert(item) for key, item in value.items()}


def _merge_value_patch(container: dict[str, ConfigValue], patch: Mapping[str, ConfigValue]) -> None:
    """Merge one dotted-field patch into a widget-value mapping."""

    for key, value in patch.items():
        current = container.get(key)
        if isinstance(value, Mapping) and isinstance(current, dict):
            _merge_value_patch(current, value)
        else:
            container[key] = value


def _field_widget(
    descriptor: ConfigFieldDescriptor,
    value: ConfigValue | None,
    *,
    key_prefix: str,
    ui: Any = st,
    choice_override: Sequence[ConfigValue] = (),
    minimum_override: float | int | None = None,
    maximum_override: float | int | None = None,
) -> ConfigValue:
    label = descriptor.path
    help_text = descriptor.documentation
    disabled = not descriptor.editable
    key = f"{key_prefix}:field:{descriptor.path}"
    if descriptor.theory_ids:
        help_text = f"{help_text or ''}\n\n{_theory_help(descriptor.theory_ids)}".strip()
    if descriptor.allows_none:
        enabled = ui.checkbox(
            f"{label} enabled",
            value=value is not None,
            disabled=disabled,
            help=f"Disable to omit this optional field.\n\n{help_text or ''}".strip(),
            key=f"{key}:enabled",
        )
        if not enabled:
            return None
        if value is None:
            value = _optional_seed(descriptor)
    options = tuple(choice_override) or tuple(descriptor.choices)
    if options:
        index = options.index(value) if value in options else 0
        return cast(
            ConfigValue, ui.selectbox(label, options=options, index=index, disabled=disabled, help=help_text, key=key)
        )
    if isinstance(value, bool):
        return cast(
            ConfigValue,
            ui.checkbox(label, value=bool(value), disabled=disabled, help=help_text, key=key),
        )
    if isinstance(value, int) and not isinstance(value, bool):
        kwargs: dict[str, Any] = {"value": value, "step": 1, "disabled": disabled, "help": help_text, "key": key}
        minimum = minimum_override if minimum_override is not None else descriptor.minimum
        maximum = maximum_override if maximum_override is not None else descriptor.maximum
        if minimum is not None:
            kwargs["min_value"] = int(minimum)
        if maximum is not None:
            kwargs["max_value"] = int(maximum)
        return int(ui.number_input(label, **kwargs))
    if isinstance(value, float):
        kwargs = {"value": value, "disabled": disabled, "help": help_text, "key": key}
        minimum = minimum_override if minimum_override is not None else descriptor.minimum
        maximum = maximum_override if maximum_override is not None else descriptor.maximum
        if minimum is not None:
            kwargs["min_value"] = float(minimum)
        if maximum is not None:
            kwargs["max_value"] = float(maximum)
        return float(ui.number_input(label, **kwargs))
    if isinstance(value, list | dict):
        raw = ui.text_area(
            label,
            value=json.dumps(value, indent=2, sort_keys=True),
            disabled=disabled,
            help=help_text,
            key=key,
        )
        try:
            return cast(ConfigValue, json.loads(raw))
        except json.JSONDecodeError:
            return cast(ConfigValue, raw)
    rendered = "" if value is None else str(value)
    updated = ui.text_input(
        label,
        value=rendered,
        type="password" if descriptor.sensitive else "default",
        disabled=disabled,
        help=help_text,
        key=key,
    )
    return cast(ConfigValue, None if value is None and not updated else updated)


def _value_at(values: Mapping[str, ConfigValue], path: str) -> ConfigValue | None:
    current: ConfigValue | Mapping[str, ConfigValue] | None = values
    for segment in path.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(segment)
    return cast(ConfigValue | None, current)


def _set_patch(patch: dict[str, ConfigValue], path: str, value: ConfigValue) -> None:
    current = patch
    segments = path.split(".")
    for segment in segments[:-1]:
        child = current.setdefault(segment, {})
        if not isinstance(child, dict):
            raise ValueError(f"Conflicting config patch path: {path}")
        current = child
    current[segments[-1]] = value


def _descriptor_for(
    descriptors: tuple[ConfigFieldDescriptor, ...],
    path: str,
) -> ConfigFieldDescriptor | None:
    return next((descriptor for descriptor in descriptors if descriptor.path == path), None)


def _optional_seed(descriptor: ConfigFieldDescriptor) -> ConfigValue:
    annotation = descriptor.annotation.lower()
    if "tensor" in annotation:
        return [0.0, 0.0, 0.0]
    if "bool" in annotation:
        return False
    if "int" in annotation:
        return int(descriptor.minimum or 0)
    if "float" in annotation:
        return float(descriptor.minimum or 0.0)
    return ""


def _theory_help(identifiers: tuple[str, ...]) -> str:
    from ...reporting.notation import TheoryReferences, TheoryResolutionError, resolve_theory

    rendered: list[str] = []
    for identifier in identifiers:
        for references in (
            TheoryReferences(symbol_ids=(identifier,)),
            TheoryReferences(equation_ids=(identifier,)),
            TheoryReferences(term_ids=(identifier,)),
        ):
            try:
                theory = resolve_theory(references)
            except TheoryResolutionError:
                continue
            if theory.symbols:
                description = theory.symbols[0].description
                source_url = theory.symbols[0].source_url
            elif theory.equations:
                description = theory.equations[0].description
                source_url = theory.equations[0].source_url
            else:
                description = theory.terms[0].definition
                source_url = theory.terms[0].source_url
            rendered.append(f"{identifier}: {description or 'canonical definition'} ({source_url})")
            break
        else:
            rendered.append(f"{identifier}: unresolved canonical theory ID")
    return "Canonical theory: " + "; ".join(rendered)


__all__ = [
    "ConfigEditorResult",
    "ConfigSelection",
    "render_config_document",
    "render_configuration_workspace",
    "render_typed_config_fields",
    "ordered_config_paths",
    "select_toml_config",
    "trusted_config_catalog",
    "trusted_config_patterns",
]
