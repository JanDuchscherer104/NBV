import sys
import types

import matplotlib.pyplot as plt
import pytorch_lightning as pl

# Stub optional deps so lit_module imports without external packages.
if "coral_pytorch" not in sys.modules:
    coral_pytorch = types.ModuleType("coral_pytorch")
    layers = types.ModuleType("coral_pytorch.layers")
    losses = types.ModuleType("coral_pytorch.losses")

    class DummyCoralLayer:  # pragma: no cover - import shim only
        pass

    def dummy_coral_loss(*args, **kwargs):  # pragma: no cover - import shim only
        raise RuntimeError("coral_pytorch is not installed")

    layers.CoralLayer = DummyCoralLayer
    losses.coral_loss = dummy_coral_loss
    coral_pytorch.layers = layers
    coral_pytorch.losses = losses
    sys.modules["coral_pytorch"] = coral_pytorch
    sys.modules["coral_pytorch.layers"] = layers
    sys.modules["coral_pytorch.losses"] = losses

if "power_spherical" not in sys.modules:
    power_spherical = types.ModuleType("power_spherical")

    class DummyPowerSpherical:  # pragma: no cover - import shim only
        pass

    power_spherical.HypersphericalUniform = DummyPowerSpherical
    power_spherical.PowerSpherical = DummyPowerSpherical
    sys.modules["power_spherical"] = power_spherical

if "e3nn" not in sys.modules:
    e3nn = types.ModuleType("e3nn")
    o3 = types.ModuleType("e3nn.o3")
    e3nn.o3 = o3
    sys.modules["e3nn"] = e3nn
    sys.modules["e3nn.o3"] = o3

import aria_nbv.lightning.lit_module as lit_module
from aria_nbv.lightning.lit_module import VinLightningModule


class DummyExperiment:
    def __init__(self) -> None:
        self.logged: list[dict[str, object]] = []

    def log(self, data: dict[str, object]) -> None:
        self.logged.append(data)


class DummyWandbLogger:
    def __init__(self) -> None:
        self.experiment = DummyExperiment()


class DummyExperimentFigure:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def add_figure(self, tag: str, fig, global_step: int) -> None:  # type: ignore[no-untyped-def]
        self.calls.append((tag, global_step))


class DummyLogger:
    def __init__(self) -> None:
        self.experiment = DummyExperimentFigure()


class DummyWandbModule(types.ModuleType):
    def __init__(self) -> None:
        super().__init__("wandb")

    @staticmethod
    def Image(fig):  # type: ignore[no-untyped-def]
        return ("image", fig)


def _make_module(logger) -> VinLightningModule:
    module = VinLightningModule.__new__(VinLightningModule)
    pl.LightningModule.__init__(module)
    module._trainer = types.SimpleNamespace(logger=logger, current_epoch=2, global_step=5)
    return module


def test_log_figure_wandb(monkeypatch) -> None:
    monkeypatch.setattr(pl.loggers, "WandbLogger", DummyWandbLogger, raising=True)
    monkeypatch.setattr(lit_module, "WandbLogger", DummyWandbLogger, raising=True)
    monkeypatch.setitem(sys.modules, "wandb", DummyWandbModule())
    module = _make_module(DummyWandbLogger())
    fig = plt.figure()
    module._log_figure("tag", fig)
    logged = module.logger.experiment.logged
    assert logged
    assert "tag" in logged[-1]
    assert logged[-1]["epoch"] == 2


def test_log_figure_tensorboard_fallback(monkeypatch) -> None:
    monkeypatch.setattr(pl.loggers, "WandbLogger", DummyWandbLogger, raising=True)
    monkeypatch.setattr(lit_module, "WandbLogger", DummyWandbLogger, raising=True)
    module = _make_module(DummyLogger())
    fig = plt.figure()
    module._log_figure("tag", fig)
    assert module.logger.experiment.calls == [("tag", 5)]
