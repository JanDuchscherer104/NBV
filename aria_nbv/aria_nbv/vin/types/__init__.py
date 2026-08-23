"""Aggregate import surface for VIN typed containers.

Leaf modules own the concrete dataclasses: `backbone` owns EVL exchange
payloads, `prediction` owns scorer outputs, `model_inputs` owns forward-pass
intermediates, and `diagnostics` owns debug payloads. This package initializer
keeps `aria_nbv.vin.types` imports stable without owning duplicate definitions.
"""

from __future__ import annotations

from .backbone import EfmDict, EvlBackboneOutput, FreeInputMode, FreeInputProvenance, validate_free_input_provenance
from .diagnostics import VinV3ForwardDiagnostics
from .model_inputs import FieldBundle, GlobalContext, PoseFeatures, PreparedInputs
from .prediction import VinPrediction

__all__ = [
    "EfmDict",
    "EvlBackboneOutput",
    "FreeInputProvenance",
    "FreeInputMode",
    "FieldBundle",
    "GlobalContext",
    "PoseFeatures",
    "PreparedInputs",
    "VinPrediction",
    "VinV3ForwardDiagnostics",
    "validate_free_input_provenance",
]
