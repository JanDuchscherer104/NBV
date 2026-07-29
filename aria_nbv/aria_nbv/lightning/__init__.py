"""Lightning orchestration for VIN candidate-scorer training.

This package provides the config-as-factory experiment, data-module, training
module, trainer, callback, and optimizer surfaces used by the runnable
one-step CORAL scorer. It owns Lightning lifecycle and optimization wiring;
actor-visible feature construction belongs to :mod:`aria_nbv.vin`, oracle
labels belong to :mod:`aria_nbv.rri_metrics`, and the separate finite-horizon
``Q_H`` stack remains leaf-owned by :mod:`aria_nbv.lightning.qh_datamodule`,
:mod:`aria_nbv.lightning.qh_module`, and
:mod:`aria_nbv.lightning.qh_experiment` rather than widening the one-step
package-root interface.
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
