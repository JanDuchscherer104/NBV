"""Trusted, metadata-only Streamlit authoring for ``BaseConfig`` TOML files."""

from __future__ import annotations

import inspect
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import streamlit as st

from ...configs import ConfigAuthoringError, ConfigDocument, ConfigFieldDescriptor, PathConfig
from ...utils import BaseConfig


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
            "build_rollouts_qh_v0_baseline.toml",
            "build_rollouts_v1_diverse.toml",
            "build_rollouts_v1_lrz.template.toml",
            "build_rollouts_v1_microset.toml",
            "build_rollouts_v1_multihorizon_highgain.toml",
            "build_rollouts_v2_cuda_campaign_writer.toml",
            "build_rollouts_v2_realistic.toml",
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
    paths = tuple(
        sorted(
            {path for pattern in patterns for path in root.glob(pattern)},
            key=lambda path: path.as_posix(),
        )
    )
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
    descriptors = document.describe()
    current = document.config.model_dump(mode="json")
    patch: dict[str, object] = {}
    with st.form("config_workspace_form"):
        st.subheader("Validated fields")
        for descriptor in descriptors:
            value = _value_at(current, descriptor.path)
            if isinstance(value, dict) and any(item.path.startswith(f"{descriptor.path}.") for item in descriptors):
                continue
            updated = _field_widget(descriptor, value)
            if updated != value:
                _set_patch(patch, descriptor.path, updated)
        save_name = st.text_input(
            "Save copy as",
            value=f"{selected_path.stem}.edited.toml",
            help="Relative names are saved below the configured .configs directory.",
        )
        validate = st.form_submit_button("Validate draft", icon=":material/fact_check:")
        save = st.form_submit_button("Validate and save copy", type="primary", icon=":material/save:")
    if not validate and not save:
        return
    try:
        updated = document.validate_patch(patch)
    except ConfigAuthoringError as exc:
        st.error(str(exc))
        return
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
    if save:
        requested_destination = Path(save_name).expanduser()
        destination = (
            requested_destination.resolve()
            if requested_destination.is_absolute()
            else (root / requested_destination).resolve()
        )
        if not destination.is_relative_to(root):
            st.error(f"Saved config copies must remain below `{root}`.")
            return
        try:
            receipt = document.save_copy(destination, expected_sha256=document.source_sha256)
        except ConfigAuthoringError as exc:
            st.error(str(exc))
            return
        st.success(f"Saved `{receipt.path}` with SHA-256 `{receipt.sha256}`.")


def _field_widget(descriptor: ConfigFieldDescriptor, value: object) -> object:
    label = descriptor.path
    help_text = descriptor.documentation
    disabled = not descriptor.editable
    key = f"config_workspace_field:{descriptor.path}"
    if descriptor.theory_ids:
        help_text = f"{help_text or ''}\n\n{_theory_help(descriptor.theory_ids)}".strip()
    if descriptor.allows_none:
        enabled = st.checkbox(
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
    if descriptor.choices:
        options = tuple(descriptor.choices)
        index = options.index(value) if value in options else 0
        return st.selectbox(label, options=options, index=index, disabled=disabled, help=help_text, key=key)
    if isinstance(value, bool):
        return st.checkbox(label, value=value, disabled=disabled, help=help_text, key=key)
    if isinstance(value, int) and not isinstance(value, bool):
        kwargs: dict[str, Any] = {"value": value, "step": 1, "disabled": disabled, "help": help_text, "key": key}
        if descriptor.minimum is not None:
            kwargs["min_value"] = int(descriptor.minimum)
        if descriptor.maximum is not None:
            kwargs["max_value"] = int(descriptor.maximum)
        return int(st.number_input(label, **kwargs))
    if isinstance(value, float):
        kwargs = {"value": value, "disabled": disabled, "help": help_text, "key": key}
        if descriptor.minimum is not None:
            kwargs["min_value"] = float(descriptor.minimum)
        if descriptor.maximum is not None:
            kwargs["max_value"] = float(descriptor.maximum)
        return float(st.number_input(label, **kwargs))
    if isinstance(value, list | dict):
        raw = st.text_area(
            label,
            value=json.dumps(value, indent=2, sort_keys=True),
            disabled=disabled,
            help=help_text,
            key=key,
        )
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    rendered = "" if value is None else str(value)
    updated = st.text_input(
        label,
        value=rendered,
        type="password" if descriptor.sensitive else "default",
        disabled=disabled,
        help=help_text,
        key=key,
    )
    return None if value is None and not updated else updated


def _value_at(values: Mapping[str, object], path: str) -> object:
    current: object = values
    for segment in path.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(segment)
    return current


def _set_patch(patch: dict[str, object], path: str, value: object) -> None:
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


def _optional_seed(descriptor: ConfigFieldDescriptor) -> object:
    annotation = descriptor.annotation.lower()
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


__all__ = ["render_configuration_workspace", "trusted_config_catalog", "trusted_config_patterns"]
