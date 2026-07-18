"""Compose optional Rerun viewer layouts for offline and rollout inspection.

This module owns entity-query normalization and the default world, time-series,
and metadata panes. Blueprint submission is best-effort across Rerun SDK
versions; recording initialization and sink ownership stay in
:mod:`aria_nbv.rerun_inspector._session`.
"""

from __future__ import annotations

from collections.abc import Sequence

from ._entities import ENTITY_CANDIDATE_ROOT, ENTITY_DETECTED_OBBS, ENTITY_EFM_VOXELS, ENTITY_GT_OBBS
from ._session import RerunModule


def world_view_contents() -> list[str]:
    """Return the default world-view query rules for Rerun blueprints."""

    return ["+ /world/**"]


def hidden_world_view_paths(*, hidden_world_paths: Sequence[str] = ()) -> tuple[str, ...]:
    """Return rooted world-view entity paths hidden by default but still included."""

    return (
        normalize_blueprint_entity_path(ENTITY_CANDIDATE_ROOT),
        normalize_blueprint_entity_path(ENTITY_DETECTED_OBBS),
        normalize_blueprint_entity_path(ENTITY_EFM_VOXELS),
        normalize_blueprint_entity_path(ENTITY_GT_OBBS),
        *(normalize_blueprint_entity_path(path) for path in hidden_world_paths),
    )


def explicit_hidden_world_view_paths(*, hidden_world_paths: Sequence[str] = ()) -> tuple[str, ...]:
    """Return only caller-selected rooted entity paths hidden by a layer policy."""

    return tuple(normalize_blueprint_entity_path(path) for path in hidden_world_paths)


def normalize_blueprint_entity_path(path: str) -> str:
    """Return a rooted entity path suitable for Rerun blueprint query rules."""

    return f"/{path.lstrip('/')}"


def log_default_inspector_blueprint(
    rr_module: RerunModule,
    *,
    hidden_world_paths: Sequence[str] = (),
    use_default_hidden_paths: bool = True,
    scalar_plots_visible: bool = True,
    metadata_visible: bool = True,
) -> None:
    """Send the inspector layout with explicit entity and pane visibility.

    Args:
        rr_module: Active Rerun module or test double.
        hidden_world_paths: Included world subtrees hidden by blueprint default.
        use_default_hidden_paths: Add legacy offline-inspector hidden subtrees.
        scalar_plots_visible: Initially show rollout scalar panes.
        metadata_visible: Initially show the metadata pane.
    """

    send_blueprint = getattr(rr_module, "send_blueprint", None)
    if send_blueprint is None:
        return
    try:
        import rerun.blueprint as rrb

        hidden_paths = (
            hidden_world_view_paths(hidden_world_paths=hidden_world_paths)
            if use_default_hidden_paths
            else explicit_hidden_world_view_paths(hidden_world_paths=hidden_world_paths)
        )
        blueprint = rrb.Blueprint(
            rrb.Horizontal(
                rrb.Spatial3DView(
                    name="World",
                    origin="/world",
                    contents=world_view_contents(),
                    overrides={path: rrb.EntityBehavior(visible=False) for path in hidden_paths},
                ),
                rrb.Vertical(
                    rrb.TimeSeriesView(
                        name="Rollout RRI",
                        origin="/plots/rollout/rri",
                        visible=scalar_plots_visible,
                    ),
                    rrb.TimeSeriesView(
                        name="Rollout Diagnostics",
                        origin="/plots/rollout/diagnostics",
                        visible=scalar_plots_visible,
                    ),
                    rrb.TextDocumentView(
                        name="Metadata",
                        origin="/metadata",
                        contents=["/metadata/**"],
                        visible=metadata_visible,
                    ),
                    row_shares=[2, 1, 1],
                ),
                column_shares=[3, 1],
            ),
            collapse_panels=False,
        )
        send_blueprint(blueprint, make_active=True, make_default=True)
    except Exception:
        return


__all__ = [
    "hidden_world_view_paths",
    "explicit_hidden_world_view_paths",
    "log_default_inspector_blueprint",
    "normalize_blueprint_entity_path",
    "world_view_contents",
]
