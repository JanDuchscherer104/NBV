r"""Actor-safe chain data for finite-candidate ``Q_H`` training.

The package joins private rollout-source identity to immutable VIN actor
evidence, exposes factual chain views, and pads heterogeneous chains for fitted
value learning. Storage interpretation remains owned by
:mod:`aria_nbv.rollouts.qh_reader`; scorer- and objective-specific admission
remains owned by the Lightning training module.

This package provides only the six public data-seam symbols listed in
``__all__``; supervision and source-key DTOs remain leaf-internal contracts.

The package interface intentionally omits supervision and identity detail that
only sibling implementations need. Import :class:`QhSupervision` and
:class:`QhChainKey` from :mod:`aria_nbv.data_handling.qh_data.views` when
implementing another Q_H data adapter.
"""

from .batching import QhBatch, collate_qh_chains
from .dataset import QhDataset, QhDatasetConfig
from .views import QhActorTensors, QhChain

__all__ = [
    "QhActorTensors",
    "QhBatch",
    "QhChain",
    "QhDataset",
    "QhDatasetConfig",
    "collate_qh_chains",
]
