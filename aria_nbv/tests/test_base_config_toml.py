"""Regression tests for :class:`aria_nbv.utils.base_config.BaseConfig`."""

import tomllib

import pytest
import torch

from aria_nbv.utils import BaseConfig, TargetConfig


class _DeviceConfig(BaseConfig):
    """Minimal config holding a torch device."""

    device: torch.device = torch.device("cpu")
    """Torch device used by the component."""


class _ConstructedTarget:
    """Runtime target constructed directly from a config."""

    def __init__(self, config: "_ConstructedTargetConfig", *, label: str) -> None:
        self.config = config
        self.label = label


class _ConstructedTargetConfig(TargetConfig[_ConstructedTarget]):
    """Config whose target is constructed directly."""

    @property
    def target_type(self) -> type[_ConstructedTarget]:
        return _ConstructedTarget


class _FactoryProduct:
    """Runtime product returned by a target factory method."""

    def __init__(self, label: str) -> None:
        self.label = label


class _FactoryTarget:
    """Factory target exposing its own setup_target method."""

    @staticmethod
    def setup_target(config: "_FactoryTargetConfig", *, suffix: str) -> _FactoryProduct:
        return _FactoryProduct(f"{config.prefix}-{suffix}")


class _FactoryTargetConfig(TargetConfig[_FactoryProduct]):
    """Config whose target delegates construction to a target factory."""

    prefix: str = "factory"

    @property
    def target_type(self) -> type[_FactoryTarget]:
        return _FactoryTarget


class _TargetlessConfig(BaseConfig):
    """Legacy config without a target."""


def test_to_toml_converts_torch_device_to_str() -> None:
    cfg = _DeviceConfig(device=torch.device("cpu"))
    rendered = cfg.to_toml(include_comments=False, include_type_hints=False)

    parsed = tomllib.loads(rendered)
    assert parsed["device"] == "cpu"


@pytest.mark.parametrize(("backend", "expected"), (("cpu", "cpu"), ("mojo", "cpu")))
def test_global_pytorch3d_backend_resolves_device(monkeypatch, backend: str, expected: str) -> None:
    monkeypatch.setenv("PYTORCH3D_BACKEND", backend)

    assert BaseConfig._resolve_geometry_device("cuda") == torch.device(expected)


def test_global_pytorch3d_backend_rejects_unknown_value(monkeypatch) -> None:
    monkeypatch.setenv("PYTORCH3D_BACKEND", "metal")

    with pytest.raises(ValueError, match="auto, cpu, cuda, mojo"):
        BaseConfig._resolve_geometry_device("auto")


def test_global_cuda_backend_requires_cuda(monkeypatch) -> None:
    monkeypatch.setenv("PYTORCH3D_BACKEND", "cuda")
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)

    with pytest.raises(ValueError, match="requires available CUDA"):
        BaseConfig._resolve_geometry_device("auto")


def test_target_config_setup_target_constructs_target() -> None:
    target = _ConstructedTargetConfig().setup_target(label="direct")

    assert isinstance(target, _ConstructedTarget)
    assert target.label == "direct"


def test_target_config_setup_target_delegates_to_target_factory() -> None:
    target = _FactoryTargetConfig(prefix="typed").setup_target(suffix="factory")

    assert isinstance(target, _FactoryProduct)
    assert target.label == "typed-factory"


def test_base_config_without_target_stays_legacy_targetless() -> None:
    assert _TargetlessConfig().setup_target() is None
