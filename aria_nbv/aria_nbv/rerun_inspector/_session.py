"""Define the injected Rerun surface and initialize exactly one output sink.

This module owns recording startup order: initialize the application and
recording id, open the configured save, spawn, or gRPC sink, then declare the
static ARIA world coordinate convention before geometry logs. Logger objects
own subsequent entities and timelines; this module does not close viewers or
mutate source datasets.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias

from ._entities import ENTITY_WORLD

if TYPE_CHECKING:
    from ._config import RerunInspectorOutputConfig

RerunEntityFactory: TypeAlias = Callable[..., object]


class RerunModule(Protocol):
    """Injectable subset of the Rerun SDK used by inspector loggers.

    Production uses the imported SDK module; tests may supply a recorder fake.
    Entity factories construct payloads, while lifecycle methods initialize one
    recording/sink and ``log``/time methods append entities to that session.
    """

    Points3D: RerunEntityFactory
    """Factory for 3D point batches in the parent entity coordinate frame."""

    LineStrips3D: RerunEntityFactory
    """Factory for ordered 3D line-strip batches."""

    Boxes3D: RerunEntityFactory
    """Factory for posed 3D boxes and optional labels."""

    AnyValues: RerunEntityFactory
    """Factory for structured scalar/list metadata components."""

    TextDocument: RerunEntityFactory
    """Factory for JSON or plain-text metadata documents."""

    Scalar: RerunEntityFactory
    """Factory for one legacy scalar time-series sample."""

    Scalars: RerunEntityFactory
    """Factory for scalar time-series samples."""

    SeriesLines: RerunEntityFactory
    """Factory for time-series line styling descriptors."""

    SeriesPoints: RerunEntityFactory
    """Factory for time-series point styling descriptors."""

    Transform3D: RerunEntityFactory
    """Factory for explicit parent-from-child rigid transforms."""

    Mesh3D: RerunEntityFactory
    """Factory for triangle meshes in the parent entity frame."""

    Image: RerunEntityFactory
    """Factory for display-oriented image rasters."""

    DepthImage: RerunEntityFactory
    """Factory for metric depth rasters."""

    Pinhole: RerunEntityFactory
    """Factory for calibrated camera intrinsics and image-plane display geometry."""

    ViewCoordinates: Any
    """SDK coordinate-system constants, including ARIA-compatible LUF and Z-up."""

    TransformRelation: Any
    """SDK transform-direction constants used to declare parent-from-child poses."""

    def init(self, *args: object, **kwargs: object) -> None:
        """Initialize application and recording identity before opening a sink."""

    def save(self, *args: object, **kwargs: object) -> None:
        """Open an owned ``.rrd`` file sink for subsequent entity logs."""

    def spawn(self, *args: object, **kwargs: object) -> None:
        """Spawn and connect a local viewer sink with configured resource limits."""

    def connect_grpc(self, *args: object, **kwargs: object) -> None:
        """Connect the initialized recording to an existing gRPC sink."""

    def log(self, entity_path: str, entity: object, *args: object, **kwargs: object) -> None:
        """Append components at a stable entity path in the active recording."""

    def set_time(self, timeline: str, *, sequence: int | None = None, **kwargs: object) -> None:
        """Set the integer sequence position used by subsequent dynamic logs."""

    def set_time_sequence(self, timeline: str, sequence: int, **kwargs: object) -> None:
        """Set an integer timeline for subsequent logs."""


def start_rerun_recording(rr_module: RerunModule, output: RerunInspectorOutputConfig) -> None:
    """Initialize one recording and open its configured sink before entity logs.

    The call order is invariant: ``init`` first, then exactly one of ``save``,
    ``spawn``, or ``connect_grpc``. Save mode creates only the destination
    parent directory; source VIN and rollout stores are never touched.
    """

    rr_module.init(output.application_id, recording_id=output.recording_id)
    if output.mode == "save":
        output.save_path.parent.mkdir(parents=True, exist_ok=True)
        rr_module.save(output.save_path)
    elif output.mode == "spawn":
        rr_module.spawn(
            port=output.spawn_port,
            connect=True,
            memory_limit=output.spawn_memory_limit,
            hide_welcome_screen=output.hide_welcome_screen,
        )
    elif output.mode == "connect":
        rr_module.connect_grpc(output.connect_addr)
    else:  # pragma: no cover - pydantic constrains this.
        raise ValueError(f"Unsupported Rerun output mode: {output.mode}")


def log_world_coordinates(rr_module: RerunModule) -> None:
    """Declare the Rerun scene root as ARIA's right-handed Z-up world."""

    rr_module.log(ENTITY_WORLD, rr_module.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)


__all__ = ["RerunModule", "log_world_coordinates", "start_rerun_recording"]
