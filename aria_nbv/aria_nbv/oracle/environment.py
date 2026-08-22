"""Identity-bound actor contexts for online oracle decisions."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import torch
from efm3d.aria.pose import PoseTW

from ..data_handling.qh_data import QhActorTensors
from ..pose_generation.types import CandidateSamplingResult
from ..rollouts.replay.state import CounterfactualTrajectory
from ..utils import BaseConfig


class StaleOracleDecisionContextError(ValueError):
    """Raised before scoring when a bound decision payload changed in place."""


@dataclass(frozen=True, slots=True)
class OracleDecisionContext:
    """Bind one actor projection to an exact replay state and candidate table.

    The frozen dataclass is intentionally only an envelope: replay DTOs contain
    mutable nested tensors and lists. :meth:`validate_integrity` therefore
    recomputes all hashes immediately before every consumer crosses the seam.
    """

    episode_id: str
    """Stable source/target/config identity supplied by the episode owner."""

    state_hash: str
    """Canonical hash of the episode identity and selected trajectory prefix."""

    table_hash: str
    """Canonical hash of the state identity and complete candidate table."""

    actor_hash: str
    """Canonical hash of the actor-safe Q_H projection and profile identity."""

    trajectory: CounterfactualTrajectory
    """Current replay prefix; nested mutation invalidates this context."""

    candidates: CandidateSamplingResult
    """Exact full-shell table aligned with the actor's final state row."""

    actor: QhActorTensors
    """Batched actor-only chain prefix consumed by the finite-horizon scorer."""

    actor_profile: str = "qh_cf0_v1"
    """Closed actor projection identity included in :attr:`actor_hash`."""

    @classmethod
    def bind(
        cls,
        *,
        episode_id: str,
        trajectory: CounterfactualTrajectory,
        candidates: CandidateSamplingResult,
        actor: QhActorTensors,
        actor_profile: str = "qh_cf0_v1",
    ) -> "OracleDecisionContext":
        """Validate candidate alignment and create canonical detached hashes."""

        if not episode_id:
            raise ValueError("Oracle decision contexts require a non-empty episode_id.")
        _validate_actor_candidate_alignment(actor, candidates)
        state_hash = _canonical_hash((episode_id, trajectory))
        table_hash = _canonical_hash((state_hash, candidates))
        actor_hash = _canonical_hash((actor_profile, actor))
        return cls(
            episode_id=episode_id,
            state_hash=state_hash,
            table_hash=table_hash,
            actor_hash=actor_hash,
            trajectory=trajectory,
            candidates=candidates,
            actor=actor,
            actor_profile=actor_profile,
        )

    def to_qh_actor(self) -> QhActorTensors:
        """Return the bound one-way actor projection after integrity validation."""

        self.validate_integrity()
        return self.actor

    def validate_integrity(self) -> None:
        """Reject nested state, table, or actor mutation before any scoring work."""

        _validate_actor_candidate_alignment(self.actor, self.candidates)
        actual_state = _canonical_hash((self.episode_id, self.trajectory))
        actual_table = _canonical_hash((actual_state, self.candidates))
        actual_actor = _canonical_hash((self.actor_profile, self.actor))
        mismatches = [
            name
            for name, expected, actual in (
                ("state", self.state_hash, actual_state),
                ("table", self.table_hash, actual_table),
                ("actor", self.actor_hash, actual_actor),
            )
            if expected != actual
        ]
        if mismatches:
            raise StaleOracleDecisionContextError(
                f"Oracle decision context changed after binding: {', '.join(mismatches)} hash mismatch."
            )


@dataclass(frozen=True, slots=True)
class OracleQuery:
    """Closed oracle-label query over one bound candidate table."""

    mode: Literal["dense_valid", "subset", "selected_only"]
    """Dense learning support, ordered evaluation subset, or one selected row."""

    shell_indices: tuple[int, ...] = ()
    """Ordered unique full-shell rows required by sparse query modes."""

    def __post_init__(self) -> None:
        if self.mode not in {"dense_valid", "subset", "selected_only"}:
            raise ValueError(f"Oracle query mode is unsupported: {self.mode!r}.")
        if self.mode == "dense_valid":
            if self.shell_indices:
                raise ValueError("dense_valid Oracle queries must not declare shell_indices.")
            return
        if self.mode == "subset" and not self.shell_indices:
            raise ValueError("subset Oracle queries require a non-empty ordered shell_indices tuple.")
        if self.mode == "selected_only" and len(self.shell_indices) != 1:
            raise ValueError("selected_only Oracle queries require exactly one shell index.")
        if len(set(self.shell_indices)) != len(self.shell_indices) or any(index < 0 for index in self.shell_indices):
            raise ValueError("Oracle query shell_indices must be unique non-negative rows.")


@dataclass(frozen=True, slots=True)
class OracleEndpointEvaluation:
    """Detached JSON-safe endpoint facts for one oracle episode."""

    episode_id: str
    """Episode identity shared with every decision context."""

    state_hash: str
    """Terminal replay-state identity."""

    acquisitions: int
    """Number of committed selected actions."""

    terminal: bool
    """Whether the episode reached a terminal state."""

    terminal_reason: str
    """Stable reason for horizon completion or early termination."""

    target_rri: float
    """Independent final target RRI value."""

    root_gain: float
    """Independent final root-normalized target gain."""

    oracle_query_count: int
    """Total hard-oracle candidate rows queried by the episode."""

    def __post_init__(self) -> None:
        if self.acquisitions < 0 or self.oracle_query_count < 0:
            raise ValueError("Oracle endpoint counts must be non-negative.")
        if not math.isfinite(self.target_rri) or not math.isfinite(self.root_gain):
            raise ValueError("Oracle endpoint metrics must be finite scalars.")


def _validate_actor_candidate_alignment(actor: QhActorTensors, candidates: CandidateSamplingResult) -> None:
    if actor.action_mask.ndim != 3 or actor.action_mask.shape[0] != 1:
        raise ValueError("Oracle decision actor projections require action_mask shape (1,S,N).")
    realized = torch.nonzero(actor.step_mask[0], as_tuple=False).reshape(-1)
    if realized.numel() == 0:
        raise ValueError("Oracle decision actor projection requires one realized state.")
    final_state = int(realized[-1].item())
    expected = torch.as_tensor(candidates.mask_valid, device=actor.action_mask.device, dtype=torch.bool).reshape(-1)
    actual = actor.action_mask[0, final_state].reshape(-1)
    if not torch.equal(actual, expected):
        raise ValueError("Oracle decision actor action mask must equal the bound candidate table hard-valid mask.")
    pose_rows = actor.candidate_pose_relative_root.tensor()  # type: ignore[no-untyped-call]
    if pose_rows.ndim != 4 or pose_rows.shape[0] != 1:
        raise ValueError("Oracle decision actor candidate poses require shape (1,S,N,12).")
    actual_poses = pose_rows[0, final_state]
    root = PoseTW(
        actor.root_pose_world.tensor()[0].to(device=actual_poses.device, dtype=actual_poses.dtype)  # type: ignore[no-untyped-call]
    )
    shell = PoseTW(
        candidates.shell_poses.tensor().to(device=actual_poses.device, dtype=actual_poses.dtype)  # type: ignore[no-untyped-call]
    )
    expected_poses = root.inverse().compose(shell).tensor()
    if actual_poses.shape != expected_poses.shape or not torch.allclose(
        actual_poses,
        expected_poses,
        rtol=1e-6,
        atol=1e-7,
    ):
        raise ValueError(
            "Oracle decision actor candidate poses must equal the bound full-shell table relative to root."
        )


def _canonical_hash(value: Any) -> str:
    """Hash nested typed payloads with detached CPU tensor bytes and stable order."""

    digest = hashlib.sha256()
    _update_hash(digest, value)
    return digest.hexdigest()


def _update_hash(digest: Any, value: Any) -> None:
    if isinstance(value, torch.Tensor):
        tensor = value.detach().cpu().contiguous()
        digest.update(b"tensor\0")
        digest.update(str(tensor.dtype).encode())
        digest.update(repr(tuple(tensor.shape)).encode())
        digest.update(tensor.numpy().tobytes())
        return
    tensor_method = getattr(value, "tensor", None)
    if callable(tensor_method):
        digest.update(f"typed-tensor:{type(value).__module__}.{type(value).__qualname__}\0".encode())
        _update_hash(digest, tensor_method())
        return
    if isinstance(value, BaseConfig):
        _update_hash(digest, value.model_dump_jsonable())
        return
    if isinstance(value, CandidateSamplingResult):
        digest.update(b"candidate-sampling-result\0")
        _update_hash(digest, value.to_serializable())
        return
    if is_dataclass(value) and not isinstance(value, type):
        digest.update(f"dataclass:{type(value).__module__}.{type(value).__qualname__}\0".encode())
        for field in fields(value):
            digest.update(field.name.encode() + b"\0")
            _update_hash(digest, getattr(value, field.name))
        return
    if isinstance(value, dict):
        digest.update(b"dict\0")
        for key in sorted(value, key=lambda item: repr(item)):
            _update_hash(digest, key)
            _update_hash(digest, value[key])
        return
    if isinstance(value, (list, tuple)):
        digest.update(f"{type(value).__name__}\0".encode())
        for item in value:
            _update_hash(digest, item)
        return
    if isinstance(value, (set, frozenset)):
        digest.update(f"{type(value).__name__}\0".encode())
        for item in sorted(value, key=repr):
            _update_hash(digest, item)
        return
    if isinstance(value, Path):
        _update_hash(digest, str(value))
        return
    if isinstance(value, Enum):
        _update_hash(digest, value.value)
        return
    if value is None or isinstance(value, (str, int, float, bool)):
        digest.update(f"scalar:{type(value).__name__}:{value!r}\0".encode())
        return
    serializable = getattr(value, "to_serializable", None)
    if callable(serializable):
        _update_hash(digest, serializable())
        return
    raise TypeError(f"Unsupported canonical oracle hash payload {type(value).__name__}.")


__all__ = [
    "OracleDecisionContext",
    "OracleEndpointEvaluation",
    "OracleQuery",
    "StaleOracleDecisionContextError",
]
