"""Contract tests for comment-preserving config authoring."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest
from pydantic import Field

from aria_nbv.configs import ConfigConflictError, ConfigDocument
from aria_nbv.utils import BaseConfig


class _NestedConfig(BaseConfig):
    count: int = Field(default=2, ge=1, le=8)
    """Bounded nested count."""


class _AuthoringConfig(BaseConfig):
    name: str = "baseline"
    """Human-readable experiment name."""

    nested: _NestedConfig = Field(default_factory=_NestedConfig)
    """Nested configuration tree."""

    secret: str = Field(default="token", json_schema_extra={"aria": {"sensitive": True}})
    """Sensitive test value."""

    locked: int = Field(default=3, json_schema_extra={"aria": {"locked": True}})
    """Reviewed value that cannot be changed in the authoring workspace."""

    optional_count: int | None = None
    """Optional count removed from TOML when disabled."""

    mode: Literal["baseline", "study"] | None = None
    """Optional closed authoring mode."""


class _SchemaFallbackConfig(BaseConfig):
    value: int = Field(default=2, ge=0, json_schema_extra={"code_owner": int})
    """Field whose non-serializable code metadata blocks full JSON Schema."""


def _write_config(path: Path) -> None:
    path.write_text(
        '# preserved heading\nname = "baseline"  # keep me\nsecret = "token"\nlocked = 3\noptional_count = 4\nmode = "baseline"\n\n[nested]\n# nested note\ncount = 2\n',
        encoding="utf-8",
    )


def test_config_document_preserves_comments_and_reports_semantic_diff(tmp_path: Path) -> None:
    source = tmp_path / "source.toml"
    destination = tmp_path / "copy.toml"
    _write_config(source)

    document = ConfigDocument.open(source, _AuthoringConfig)
    updated = document.validate_patch({"nested": {"count": 5}})
    diff = document.diff(updated)
    receipt = document.save_copy(destination, expected_sha256=document.source_sha256)

    rendered = destination.read_text(encoding="utf-8")
    assert "# preserved heading" in rendered
    assert "# keep me" in rendered
    assert "# nested note" in rendered
    assert "count = 5" in rendered
    assert tuple(entry.path for entry in diff.entries) == ("nested.count",)
    assert receipt.changed


def test_noop_save_is_byte_exact(tmp_path: Path) -> None:
    source = tmp_path / "source.toml"
    destination = tmp_path / "copy.toml"
    _write_config(source)
    document = ConfigDocument.open(source, _AuthoringConfig)

    document.save_copy(destination, expected_sha256=document.source_sha256)

    assert destination.read_bytes() == source.read_bytes()


def test_stale_source_digest_rejects_write(tmp_path: Path) -> None:
    source = tmp_path / "source.toml"
    destination = tmp_path / "copy.toml"
    _write_config(source)
    document = ConfigDocument.open(source, _AuthoringConfig)
    source.write_text(source.read_text(encoding="utf-8") + "# external edit\n", encoding="utf-8")

    with pytest.raises(ConfigConflictError, match="changed since inspection"):
        document.save_copy(destination, expected_sha256=document.source_sha256)

    assert not destination.exists()


def test_describe_uses_source_docs_schema_and_policy(tmp_path: Path) -> None:
    source = tmp_path / "source.toml"
    _write_config(source)
    document = ConfigDocument.open(source, _AuthoringConfig)

    descriptors = {descriptor.path: descriptor for descriptor in document.describe()}

    assert descriptors["name"].documentation == "Human-readable experiment name."
    assert descriptors["nested.count"].minimum == 1
    assert descriptors["nested.count"].maximum == 8
    assert descriptors["secret"].sensitive
    assert not descriptors["locked"].editable
    assert descriptors["optional_count"].allows_none
    assert descriptors["mode"].choices == ("baseline", "study")


def test_locked_field_patch_fails_before_write(tmp_path: Path) -> None:
    source = tmp_path / "source.toml"
    _write_config(source)
    document = ConfigDocument.open(source, _AuthoringConfig)

    with pytest.raises(ValueError, match="locked"):
        document.validate_patch({"locked": 4})


def test_optional_none_removes_toml_key_and_validates_default(tmp_path: Path) -> None:
    source = tmp_path / "source.toml"
    destination = tmp_path / "copy.toml"
    _write_config(source)
    document = ConfigDocument.open(source, _AuthoringConfig)

    updated = document.validate_patch({"optional_count": None})
    document.save_copy(destination, expected_sha256=document.source_sha256)

    assert updated.optional_count is None
    assert "optional_count" not in destination.read_text(encoding="utf-8")


def test_describe_falls_back_when_full_json_schema_is_unavailable(tmp_path: Path) -> None:
    source = tmp_path / "fallback.toml"
    source.write_text("value = 2\n", encoding="utf-8")

    descriptor = ConfigDocument.open(source, _SchemaFallbackConfig).describe()[0]

    assert descriptor.path == "value"
    assert descriptor.minimum == 0
    assert descriptor.documentation == "Field whose non-serializable code metadata blocks full JSON Schema."
