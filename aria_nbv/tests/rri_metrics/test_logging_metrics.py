import sys
import types

import pytest
import torch

if "power_spherical" not in sys.modules:
    power_spherical = types.ModuleType("power_spherical")

    class DummyPowerSpherical:  # pragma: no cover - import shim only
        pass

    power_spherical.HypersphericalUniform = DummyPowerSpherical
    power_spherical.PowerSpherical = DummyPowerSpherical
    sys.modules["power_spherical"] = power_spherical

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

if "e3nn" not in sys.modules:
    e3nn = types.ModuleType("e3nn")
    o3 = types.ModuleType("e3nn.o3")
    e3nn.o3 = o3
    sys.modules["e3nn"] = e3nn
    sys.modules["e3nn.o3"] = o3

from aria_nbv.rri_metrics.logging import (
    LabelHistogram,
    Loss,
    Metric,
    RriErrorStats,
    VinMetrics,
    loss_key,
    metric_key,
    topk_accuracy_from_probs,
)
from aria_nbv.utils import Stage


def test_label_histogram_counts() -> None:
    hist = LabelHistogram(num_classes=4)
    labels = torch.tensor([0, 1, 1, 3, 3, 3])
    hist.update(labels)
    counts = hist.compute()
    assert counts.tolist() == [1, 2, 0, 3]


def test_label_histogram_rejects_invalid_class_count() -> None:
    with pytest.raises(ValueError, match="num_classes"):
        LabelHistogram(num_classes=0)


def test_label_histogram_rejects_out_of_range_labels() -> None:
    hist = LabelHistogram(num_classes=3)

    with pytest.raises(ValueError, match=r"\[0, 3\)"):
        hist.update(torch.tensor([0, 3]))

    with pytest.raises(ValueError, match=r"\[0, 3\)"):
        hist.update(torch.tensor([-1]))


def test_vin_metrics_empty_compute() -> None:
    metrics = VinMetrics(num_classes=3)
    assert metrics.compute() == {}


def test_vin_metrics_compute() -> None:
    metrics = VinMetrics(num_classes=3)
    pred_scores = torch.tensor([0.1, 0.2, 0.3, 0.4])
    rri = torch.tensor([0.0, 0.5, 0.2, 0.9])
    pred_class = torch.tensor([0, 1, 2, 1])
    labels = torch.tensor([0, 1, 2, 2])
    metrics.update(pred_scores=pred_scores, rri=rri, pred_class=pred_class, labels=labels)
    result = metrics.compute()
    assert set(result.keys()) == {"spearman", "confusion", "label_hist"}
    assert result["confusion"].shape == (3, 3)
    assert result["label_hist"].shape == (3,)


def test_vin_metrics_can_disable_spearman_buffering() -> None:
    metrics = VinMetrics(num_classes=3, enable_spearman=False)
    pred_scores = torch.tensor([0.1, 0.2, 0.3, 0.4])
    rri = torch.tensor([0.0, 0.5, 0.2, 0.9])
    pred_class = torch.tensor([0, 1, 2, 1])
    labels = torch.tensor([0, 1, 2, 2])

    metrics.update(pred_scores=pred_scores, rri=rri, pred_class=pred_class, labels=labels)
    result = metrics.compute()

    assert set(result.keys()) == {"confusion", "label_hist"}
    assert metrics.spearman is None


def test_metric_key() -> None:
    assert metric_key(Stage.TRAIN, Metric.LOSS) == "train/loss"
    assert metric_key(Stage.TRAIN, Metric.SPEARMAN_STEP) == "train/spearman_step"
    assert metric_key(Stage.TRAIN, Metric.SPEARMAN_STEP, namespace="aux") == "train-aux/spearman_step"
    assert metric_key(Stage.VAL, Metric.SPEARMAN) == "val/spearman"
    assert metric_key(Stage.TEST, Metric.LABEL_HISTOGRAM) == "test/label_histogram"


def test_loss_key() -> None:
    assert loss_key(Stage.TRAIN, Loss.LOSS) == "train/loss"
    assert loss_key(Stage.VAL, Loss.AUX_REGRESSION) == "val/aux_regression_loss"
    assert loss_key(Stage.TRAIN, Loss.ORD_FOCAL, namespace="aux") == "train-aux/coral_loss_focal"


def test_topk_accuracy_from_probs() -> None:
    probs = torch.tensor(
        [
            [0.1, 0.7, 0.2],
            [0.5, 0.1, 0.4],
        ],
        dtype=torch.float32,
    )
    labels = torch.tensor([1, 2], dtype=torch.int64)
    acc_top1 = topk_accuracy_from_probs(probs, labels, top_k=1)
    acc_top2 = topk_accuracy_from_probs(probs, labels, top_k=2)
    assert torch.isclose(acc_top1, torch.tensor(0.5))
    assert torch.isclose(acc_top2, torch.tensor(1.0))


def test_topk_accuracy_validates_top_k_before_empty_inputs() -> None:
    probs = torch.empty((0, 3), dtype=torch.float32)
    labels = torch.empty((0,), dtype=torch.int64)

    with pytest.raises(ValueError, match="top_k"):
        topk_accuracy_from_probs(probs, labels, top_k=0)


def test_rri_error_stats_bias_variance() -> None:
    stats = RriErrorStats()
    pred = torch.tensor([2.0, 4.0])
    rri = torch.tensor([1.0, 3.0])
    stats.update(pred, rri)
    result = stats.compute()
    assert torch.isclose(result["bias2"], torch.tensor(1.0))
    assert torch.isclose(result["variance"], torch.tensor(0.0))


def test_rri_error_stats_ignores_nonfinite_pairs() -> None:
    stats = RriErrorStats()
    pred = torch.tensor([2.0, float("nan"), 4.0, float("inf")])
    rri = torch.tensor([1.0, 1.0, 3.0, 2.0])

    stats.update(pred, rri)
    result = stats.compute()

    assert torch.isclose(result["bias2"], torch.tensor(1.0))
    assert torch.isclose(result["variance"], torch.tensor(0.0))


def test_rri_error_stats_returns_empty_for_all_nonfinite_pairs() -> None:
    stats = RriErrorStats()

    stats.update(torch.tensor([float("nan"), 1.0]), torch.tensor([1.0, float("nan")]))

    assert stats.compute() == {}
