r"""Fit and persist global quantile bins for CORAL RRI supervision.

VIN trains an ordinal regressor (CORAL) rather than directly regressing oracle
RRI values. We therefore map continuous RRIs to ordinal labels via *empirical
quantile edges* (equal-mass bins):

- fit $K-1$ quantiles on finite, hard-valid oracle RRIs,
- assign $y=\operatorname{bucketize}(r; e_0,\ldots,e_{K-2})$,
- expand $y$ into the cumulative CORAL levels $\mathbb{1}[y>k]$.

Design goals:
    - Accumulate fit data on CPU.
    - Persist fit data to resume after Ctrl-C / crashes.
    - Avoid overwriting JSON outputs by default.

File formats:
    - Fit data: ``.pt`` (torch.save state with ``rri_chunks``)
    - Fitted binner: ``.json`` (num_classes + edges)

The binner owns label discretization and dataset priors, not candidate
validity. Invalid actions must be removed with their hard mask before fitting
or transformation; mapping them to class ``0`` would conflate invalidity with
valid but low utility. CORAL predictions decoded through these bins are
actor-side proxies, while the input RRI values are oracle supervision.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import torch
from torch import Tensor

from ..configs import PathConfig


def _unique_path(path: Path, *, overwrite: bool) -> Path:
    """Return a non-overwriting path by appending ``-<n>`` before the suffix."""
    path = Path(path)
    if overwrite or not path.exists():
        return path

    idx = 1
    while True:  # pragma: no cover - should terminate quickly
        candidate = path.with_name(f"{path.stem}-{idx}{path.suffix}")
        if not candidate.exists():
            return candidate
        idx += 1


def _atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding=encoding)
    os.replace(tmp, path)


def _atomic_torch_save(path: Path, state: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    torch.save(state, tmp)
    os.replace(tmp, path)


def ordinal_labels_to_levels(labels: Tensor, *, num_classes: int) -> Tensor:
    r"""Expand ordinal labels into cumulative CORAL threshold targets.

    CORAL represents a K-class ordinal label ``y ∈ {0, ..., K-1}`` as ``K-1``
    binary targets:

        levels[k] = 1  if y > k
                  = 0  otherwise

    Args:
        labels ``Tensor["...", int64]``: Ordinal class ids in
            ``[0, num_classes-1]``.
        num_classes: Number of ordinal classes ``K``.

    Returns:
        ``Tensor["... K-1", float32]`` binary levels
        $\mathbb{1}[y>k]$.
    """
    if num_classes < 2:
        raise ValueError("num_classes must be >= 2.")
    if labels.dtype not in (torch.int32, torch.int64):
        raise TypeError(f"labels must be integer dtype, got {labels.dtype}.")

    thresholds = torch.arange(num_classes - 1, device=labels.device, dtype=labels.dtype)
    levels = labels.unsqueeze(-1) > thresholds  # ... x (K-1)
    return levels.to(dtype=torch.float32)


@dataclass(slots=True)
class RriOrdinalBinner:
    """Map finite oracle RRI values to globally fitted ordinal classes.

    ``K`` classes are separated by ``K-1`` nondecreasing empirical quantile
    edges. The fitted statistics are dimensionless because RRI is normalized.
    Fitting accumulates transient CPU chunks; JSON persistence stores the
    compact fitted artifact used by training and evaluation.
    """

    num_classes: int = 0
    """Number of ordinal classes ``K``; fitted binners require ``K >= 2``."""

    edges: Tensor = field(
        default_factory=lambda: torch.empty((0,), dtype=torch.float32),
    )
    """``Tensor["K-1", float32]`` dimensionless quantile edges in ascending order."""

    midpoints: Tensor | None = None
    """Optional ``Tensor["K", float32]`` dimensionless extrapolated class midpoints."""

    bin_means: Tensor | None = None
    """Optional ``Tensor["K", float32]`` empirical oracle-RRI mean per class."""

    bin_stds: Tensor | None = None
    """Optional ``Tensor["K", float32]`` empirical oracle-RRI standard deviation per class."""

    bin_counts: Tensor | None = None
    """Optional ``Tensor["K", float32]`` finite sample counts used to derive priors."""

    _rri_chunks: list[Tensor] = field(default_factory=list, repr=False)
    """Transient CPU ``Tensor["N_i", float32]`` chunks retained only while fitting or resuming."""

    @property
    def is_fitted(self) -> bool:
        """Report whether ``K`` and the required ``K-1`` edges are present."""
        return int(self.num_classes) >= 2 and int(self.edges.numel()) == int(self.num_classes) - 1

    def transform(self, rri: Tensor) -> Tensor:
        """Bucketize oracle RRI values into a flat candidate/sample axis.

        Args:
            rri ``Tensor["...", float32]``: Finite, hard-valid,
                dimensionless oracle RRI values.

        Returns:
            ``Tensor["N", int64]`` flattened labels in ``[0, K-1]``. A value
            equal to an edge is assigned to the lower adjacent class because
            ``torch.bucketize(..., right=False)`` is used.
        """
        if not self.is_fitted:
            raise RuntimeError(
                "Binner not fitted. Call fit_from_iterable(...) or load a fitted JSON binner.",
            )

        rri_f = rri.reshape(-1).to(dtype=torch.float32)
        labels = torch.bucketize(rri_f, self.edges.to(device=rri_f.device), right=False)
        return labels.to(dtype=torch.int64)

    def labels_to_levels(self, labels: Tensor) -> Tensor:
        """Expand ``Tensor["...", int64]`` labels to ``Tensor["... K-1", float32]`` levels."""
        if not self.is_fitted:
            raise RuntimeError("Binner not fitted; cannot convert labels to levels.")
        return ordinal_labels_to_levels(labels, num_classes=int(self.num_classes))

    def rri_to_levels(self, rri: Tensor) -> Tensor:
        """Flatten RRI values and return ``Tensor["N K-1", float32]`` CORAL levels."""
        labels = self.transform(rri)
        return self.labels_to_levels(labels)

    def class_midpoints(self) -> Tensor:
        """Return dimensionless class representatives derived from quantile edges.

        Returns:
            ``Tensor["K", float32]`` class midpoints. Interior values average
            adjacent edges; endpoint values extrapolate half an edge spacing.

        Notes:
            If `midpoints` is not already stored, extrapolation requires at
            least two edges, corresponding to ``K >= 3``.
        """
        if self.midpoints is not None:
            return self.midpoints

        if not self.is_fitted:
            raise RuntimeError("Binner not fitted; midpoints are undefined.")

        edges = self.edges.reshape(-1).to(dtype=torch.float32)
        if edges.numel() < 2:
            raise ValueError("Expected at least two edges to compute midpoints.")

        step_lo = edges[1] - edges[0]
        step_hi = edges[-1] - edges[-2]
        lo = edges[0] - 0.5 * step_lo
        hi = edges[-1] + 0.5 * step_hi
        mids = 0.5 * (edges[:-1] + edges[1:])

        self.midpoints = torch.cat([lo.unsqueeze(0), mids, hi.unsqueeze(0)], dim=0)

        return self.midpoints

    def class_priors(self) -> Tensor:
        """Return ``Tensor["K", float32]`` empirical class priors or a uniform fallback."""
        if not self.is_fitted:
            raise RuntimeError("Binner not fitted; class priors undefined.")
        if self.bin_counts is not None and self.bin_counts.numel() == int(self.num_classes):
            counts = self.bin_counts.to(dtype=torch.float32)
            total = counts.sum()
            if total > 0:
                return counts / total
        num_classes = int(self.num_classes)
        return torch.full((num_classes,), 1.0 / float(num_classes), dtype=torch.float32)

    def threshold_priors(self) -> Tensor:
        """Return ``Tensor["K-1", float32]`` cumulative priors ``P(y > k)``."""
        priors = self.class_priors()
        return torch.flip(torch.cumsum(torch.flip(priors, dims=[0]), dim=0), dims=[0])[1:]

    def expected_from_probs(self, probs: Tensor) -> Tensor:
        """Compute expected RRI proxy from class probabilities.

        Args:
            probs ``Tensor["... K", float32]``: Actor-predicted class
                probabilities aligned with this binner's class order.

        Returns:
            ``Tensor["...", float32]`` dimensionless continuous RRI proxies
            using empirical bin means when present, otherwise midpoints.
        """
        if not self.is_fitted:
            raise RuntimeError("Binner not fitted; expected values undefined.")
        centers = self.bin_means if self.bin_means is not None else self.class_midpoints()
        centers = centers.to(device=probs.device, dtype=probs.dtype)
        return (probs * centers.view(*([1] * (probs.ndim - 1)), -1)).sum(dim=-1)

    # --------------------------------------------------------------------- JSON (checkpoint + artifact)
    def to_dict(self) -> dict[str, Any]:
        """Return the fitted JSON payload with CPU-native edges and optional statistics."""
        if not self.is_fitted:
            raise RuntimeError(
                "Binner not fitted; only fitted binners can be serialized.",
            )
        data = {
            "num_classes": int(self.num_classes),
            "edges": self.edges.detach().cpu().tolist(),
        }
        if self.bin_means is not None:
            data["bin_means"] = self.bin_means.detach().cpu().tolist()
        if self.bin_stds is not None:
            data["bin_stds"] = self.bin_stds.detach().cpu().tolist()
        if self.bin_counts is not None:
            data["bin_counts"] = self.bin_counts.detach().cpu().tolist()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RriOrdinalBinner:
        """Construct a CPU binner from a payload produced by :meth:`to_dict`."""
        bin_means = data.get("bin_means")
        bin_stds = data.get("bin_stds")
        bin_counts = data.get("bin_counts")
        return cls(
            num_classes=int(data["num_classes"]),
            edges=torch.tensor(data["edges"], dtype=torch.float32),
            bin_means=(torch.tensor(bin_means, dtype=torch.float32) if bin_means is not None else None),
            bin_stds=(torch.tensor(bin_stds, dtype=torch.float32) if bin_stds is not None else None),
            bin_counts=(torch.tensor(bin_counts, dtype=torch.float32) if bin_counts is not None else None),
        )

    def save(self, path: str | Path, *, overwrite: bool = False) -> Path:
        """Atomically save a fitted JSON artifact and return its resolved path.

        Relative paths are resolved through :class:`aria_nbv.configs.PathConfig`.
        Unless `overwrite` is true, an existing target receives a numeric
        suffix instead of being replaced.
        """
        if not self.is_fitted:
            raise RuntimeError(
                "Binner not fitted; call fit_from_iterable(...) before save().",
            )

        out_path = PathConfig().resolve_artifact_path(path, expected_suffix=".json")
        out_path = _unique_path(out_path, overwrite=overwrite)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(
            out_path,
            json.dumps(self.to_dict(), indent=2, sort_keys=True),
        )
        return out_path

    @classmethod
    def load(cls, path: str | Path) -> RriOrdinalBinner:
        """Load a fitted CPU binner from a resolved JSON artifact path."""
        in_path = PathConfig().resolve_artifact_path(
            path,
            expected_suffix=".json",
            create_parent=False,
        )
        data = json.loads(in_path.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    @staticmethod
    def load_fit_data(path: str | Path) -> Tensor:
        """Load flattened RRI samples from a saved binner fit-data file.

        Args:
            path: Path to a ``.pt`` file that stores ``rri_chunks``.

        Returns:
            ``Tensor["N", float32]`` of finite RRI samples.
        """
        fit_path = Path(path).expanduser()
        state = torch.load(fit_path, map_location="cpu", weights_only=True)
        chunks = state.get("rri_chunks", [])
        if not chunks:
            return torch.empty((0,), dtype=torch.float32)
        flat = torch.cat(
            [torch.as_tensor(chunk, dtype=torch.float32).reshape(-1) for chunk in chunks],
            dim=0,
        )
        flat = flat[torch.isfinite(flat)]
        return flat

    # --------------------------------------------------------------------- fitting (single entry point)
    @classmethod
    def fit_from_iterable(
        cls,
        iterable: Iterable[Tensor | tuple[Tensor, Any]],
        *,
        num_classes: int = 15,
        target_items: int | None = None,
        max_skips: int = 0,
        fit_data_path: str | Path | None = None,
        resume: bool = False,
        save_every: int = 1,
        on_progress: Callable[[int, int, Tensor | None, Any | None], None] | None = None,
    ) -> RriOrdinalBinner:
        """Fit global quantile edges from a stream of finite oracle RRI chunks.

        Args:
            iterable: Stream of RRI tensors or ``(rri, metadata)`` pairs. Each
                yielded tensor counts as one successful item after finite
                filtering, regardless of its number of scalar samples.
            num_classes: Requested class count ``K >= 2``.
            target_items: Optional number of successful yielded items to
                collect before fitting; this is not a scalar-sample count.
            max_skips: Maximum all-nonfinite items before failure; ``0`` allows
                unlimited skips until the iterable is exhausted.
            fit_data_path: Optional ``.pt`` checkpoint for CPU RRI chunks.
            resume: Load existing fit chunks from `fit_data_path` before
                consuming `iterable`.
            save_every: Successful-item interval for atomic fit-data writes;
                non-positive values disable periodic writes but not the final
                or exception write.
            on_progress: Optional callback receiving successful-item count,
                skip count, the latest finite tensor on its input device, and
                yielded metadata.

        Returns:
            Fitted :class:`RriOrdinalBinner` with CPU edges, means, standard
            deviations, and counts.

        Notes:
            - All fit data is stored on CPU.
            - Fit data is saved on Ctrl-C / exceptions when ``fit_data_path`` is provided.
            - The iterable may yield either ``rri`` tensors or ``(rri, meta)`` tuples.
            - Callers must apply hard candidate validity before yielding; this
              function removes non-finite values but has no validity mask.
        """
        path = None
        if fit_data_path is not None:
            path = PathConfig().resolve_artifact_path(
                fit_data_path,
                expected_suffix=".pt",
            )

        binner = cls()
        if path is not None and path.exists():
            if not resume:
                raise FileExistsError(
                    f"Fit data already exists at {path}. Delete it or pass resume=True.",
                )
            state = torch.load(path, map_location="cpu", weights_only=True)
            binner._rri_chunks = [t.reshape(-1).to(dtype=torch.float32) for t in state["rri_chunks"]]

        successes = len(binner._rri_chunks)
        skipped = 0

        def _save_fit_data() -> None:
            if path is None:
                return
            path.parent.mkdir(parents=True, exist_ok=True)
            state = {
                "rri_chunks": [t.detach().to(device="cpu", dtype=torch.float32) for t in binner._rri_chunks],
            }
            _atomic_torch_save(path, state)

        try:
            for item in iterable:
                if target_items is not None and successes >= int(target_items):
                    break

                if isinstance(item, tuple):
                    rri_raw, meta = item
                else:
                    rri_raw, meta = item, None

                rri_f = rri_raw.reshape(-1).to(dtype=torch.float32)
                rri_f = rri_f[torch.isfinite(rri_f)]
                if rri_f.numel() == 0:
                    skipped += 1
                    if on_progress is not None:
                        on_progress(successes, skipped, None, meta)
                    if int(max_skips) > 0 and skipped >= int(max_skips):
                        raise RuntimeError(
                            f"Unable to fit binner: only {successes}/{target_items or '∞'} items after {skipped} skips.",
                        )
                    continue

                binner._rri_chunks.append(rri_f.detach().cpu())
                successes = len(binner._rri_chunks)

                if on_progress is not None:
                    on_progress(successes, skipped, rri_f.detach(), meta)

                if path is not None and int(save_every) > 0 and (successes % int(save_every) == 0):
                    _save_fit_data()
        except (KeyboardInterrupt, Exception):
            _save_fit_data()
            raise

        if target_items is not None and successes < int(target_items):
            raise RuntimeError(
                f"Dataset exhausted while fitting binner ({successes}/{int(target_items)} successful items collected).",
            )

        _save_fit_data()
        return binner._finalize(num_classes=int(num_classes))

    # --------------------------------------------------------------------- internals
    def _finalize(self, *, num_classes: int) -> RriOrdinalBinner:
        if int(num_classes) < 2:
            raise ValueError("num_classes must be >= 2.")
        if not self._rri_chunks:
            raise ValueError("No fit data available.")

        rri = torch.cat(self._rri_chunks, dim=0).to(dtype=torch.float32)
        rri = rri[torch.isfinite(rri)]
        if rri.numel() == 0:
            raise RuntimeError("No finite RRI samples available to fit binner.")
        qs = torch.linspace(
            1.0 / float(num_classes),
            float(num_classes - 1) / float(num_classes),
            steps=int(num_classes) - 1,
            device=rri.device,
        )
        self.num_classes = int(num_classes)
        edges = torch.quantile(rri, qs).to(dtype=torch.float32)
        edges = torch.unique_consecutive(edges)
        if edges.numel() < int(num_classes) - 1:
            lo = float(rri.min().item())
            hi = float(rri.max().item())
            if not torch.isfinite(torch.tensor([lo, hi])).all() or abs(hi - lo) < 1e-6:
                lo, hi = -1.0, 1.0
            edges = torch.linspace(
                lo,
                hi,
                steps=int(num_classes) + 1,
                device=rri.device,
                dtype=torch.float32,
            )[1:-1]
        self.edges = edges.detach().cpu()
        midpoints = self.class_midpoints().to(device=rri.device, dtype=rri.dtype)
        labels = torch.bucketize(rri, edges, right=False)
        counts = torch.bincount(labels, minlength=int(num_classes)).to(dtype=torch.float32)
        means = torch.empty(int(num_classes), device=rri.device, dtype=rri.dtype)
        stds = torch.empty_like(means)
        for idx in range(int(num_classes)):
            vals = rri[labels == idx]
            if vals.numel() == 0:
                means[idx] = midpoints[idx]
                stds[idx] = 0.0
            else:
                means[idx] = vals.mean()
                stds[idx] = vals.std(unbiased=False)
        self.bin_means = means.detach().cpu()
        self.bin_stds = stds.detach().cpu()
        self.bin_counts = counts.detach().cpu()
        return self


__all__ = ["RriOrdinalBinner", "ordinal_labels_to_levels"]
