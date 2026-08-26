"""Lightning orchestration for VIN candidate-scorer training.

This package provides the config-as-factory experiment, data-module, training
module, trainer, callback, and optimizer surfaces used by the runnable
one-step CORAL scorer. Its finite-horizon leaf modules additionally own QH
stage admission, masked Double-Q optimization, exact-``Q_2`` certification,
and immutable experiment/bundle publication. Actor-visible feature
construction belongs to :mod:`aria_nbv.vin`; oracle labels belong to
:mod:`aria_nbv.rri_metrics` and :mod:`aria_nbv.oracle`.

The package root intentionally retains the one-step stable import surface.
Import finite-horizon contracts from :mod:`aria_nbv.lightning.qh_datamodule`,
:mod:`aria_nbv.lightning.qh_module`,
:mod:`aria_nbv.lightning.qh_experiment`, and
:mod:`aria_nbv.lightning.qh_q2_certification`.
"""

from .aria_nbv_experiment import AriaNBVExperimentConfig
from .lit_datamodule import VinDataModule, VinDataModuleConfig
from .lit_module import AdamWConfig, VinLightningModule, VinLightningModuleConfig
from .lit_trainer_callbacks import TrainerCallbacksConfig
from .lit_trainer_factory import TrainerFactoryConfig

__all__ = [
    "AdamWConfig",
    "AriaNBVExperimentConfig",
    "TrainerCallbacksConfig",
    "TrainerFactoryConfig",
    "VinDataModule",
    "VinDataModuleConfig",
    "VinLightningModule",
    "VinLightningModuleConfig",
]
