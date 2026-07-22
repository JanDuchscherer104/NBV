"""Dependency-direction regressions for the framework-neutral Q_H scorer."""

from __future__ import annotations

import ast
import inspect
import os
import subprocess
import sys

import aria_nbv.vin.models.target_finite_horizon as target_finite_horizon


def test_qh_scorer_source_has_no_lightning_dependency() -> None:
    """The plain scorer must depend on the data contract, never Lightning."""

    tree = ast.parse(inspect.getsource(target_finite_horizon))
    imported_modules = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_modules.update(
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    )

    assert not any(
        module == "aria_nbv.lightning" or module.startswith("aria_nbv.lightning.") for module in imported_modules
    )


def test_qh_scorer_cold_import_avoids_lightning_and_store_construction() -> None:
    """Importing the scorer must remain usable in a plain PyTorch process."""

    script = r"""
import importlib
import sys

import aria_nbv
from aria_nbv.data_handling.offline.store import VinOfflineStoreReader

forbidden = ("pytorch_lightning", "lightning", "aria_nbv.rollouts.qh_reader")
before = {
    name
    for name in sys.modules
    if any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden)
}

def reject_store_construction(*args, **kwargs):
    raise AssertionError("scorer import constructed VIN storage")

VinOfflineStoreReader.__init__ = reject_store_construction
sys.modules.pop("aria_nbv.vin.models.target_finite_horizon", None)
importlib.import_module("aria_nbv.vin.models.target_finite_horizon")

after = {
    name
    for name in sys.modules
    if any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden)
}
assert after == before, f"scorer import added forbidden modules: {sorted(after - before)}"
"""
    environment = os.environ.copy()
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0, result.stdout + result.stderr
