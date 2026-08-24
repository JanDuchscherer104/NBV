"""Weights & Biases logger configuration for Lightning experiments.

This module owns :class:`WandbConfig` and its config-as-factory translation to
Lightning's `WandbLogger`, including local storage, run identity, grouping,
resume, and checkpoint-artifact options. It does not define metric schemas,
start training, or create a W&B run until :meth:`WandbConfig.setup_target` is
called.

The config keeps W&B identity, resume, grouping, and artifact settings in the
same config-as-factory tree as the rest of an ARIA-NBV experiment.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field
from pytorch_lightning.loggers import WandbLogger

from ..utils import TargetConfig
from .path_config import PathConfig


class WandbConfig(TargetConfig[WandbLogger]):
    """Wrapper around Lightning's `WandbLogger`.

    References:
        https://lightning.ai/docs/pytorch/stable/api/lightning.pytorch.loggers.wandb.html
    """

    @property
    def target_type(self) -> type[WandbLogger]:
        """Return Lightning's W&B logger class for config-factory inspection."""
        return WandbLogger

    name: str | None = Field(default=None, description="Display name for the run.")
    """Optional display name for the run."""

    project: str = Field(default="aria-nbv", description="W&B project name.")
    """Destination W&B project name."""

    entity: str | None = None
    """Optional W&B user or team entity."""

    run_id: str | None = Field(default=None, description="Resume or create a run with this ID.")
    """Stable run id used for creation or resumption."""

    resume: Literal["allow", "must", "never"] | None = Field(
        default=None,
        description="Resume behavior for existing runs (passed to wandb.init).",
    )
    """Policy for an already existing `run_id`."""

    anonymous: bool | None = Field(default=None, description="Enable anonymous mode.")
    """Optional W&B anonymous-mode override."""

    offline: bool = Field(False, description="Enable offline logging.")
    """Write events locally without contacting the W&B service."""

    log_model: bool | str = Field(
        default=False,
        description="Forward Lightning checkpoints to W&B artefacts.",
    )
    """Lightning checkpoint-to-W&B artifact logging policy."""

    checkpoint_name: str | None = Field(default=None, description="Checkpoint artefact name.")
    """Optional name for uploaded checkpoint artifacts."""

    tags: list[str] | None = Field(default=None, description="Optional list of tags.")
    """Optional run tags used for filtering and comparison."""

    group: str | None = Field(default=None, description="Group multiple related runs.")
    """Optional group shared by related runs or trials."""

    job_type: str | None = Field(default=None, description="Attach a W&B job_type label.")
    """Optional role label such as training, evaluation, or sweep."""

    prefix: str | None = Field(default=None, description="Namespace prefix for metric keys.")
    """Optional namespace prepended to logged metric keys."""

    def init_kwargs(self) -> dict[str, Any]:
        """Return the shared W&B run-identity arguments for non-Lightning reporters.

        Lightning-only checkpoint and metric-prefix options deliberately remain
        exclusive to :meth:`setup_target`.  This keeps small reporting tools on
        the same project, identity, grouping, and offline-mode contract without
        pretending that they are Lightning loggers.
        """
        kwargs: dict[str, Any] = {
            "name": self.name,
            "project": self.project,
            "entity": self.entity,
            "dir": PathConfig().wandb.as_posix(),
            "id": self.run_id,
            "mode": "offline" if self.offline else "online",
            "tags": self.tags,
            "group": self.group,
            "job_type": self.job_type,
        }
        if self.resume is not None:
            kwargs["resume"] = self.resume
        if self.anonymous is not None:
            kwargs["anonymous"] = self.anonymous
        return kwargs

    def setup_target(self, **kwargs: Any) -> WandbLogger:
        """Instantiate a logger rooted in :class:`PathConfig`'s W&B directory."""
        wandb_dir = PathConfig().wandb.as_posix()
        init_kwargs: dict[str, Any] = {}
        if self.resume is not None:
            init_kwargs["resume"] = self.resume
        if self.anonymous is not None:
            init_kwargs["anonymous"] = self.anonymous

        return WandbLogger(
            name=self.name,
            project=self.project,
            entity=self.entity,
            save_dir=wandb_dir,
            id=self.run_id,
            offline=self.offline,
            log_model=self.log_model,
            prefix=self.prefix,
            checkpoint_name=self.checkpoint_name,
            tags=self.tags,
            group=self.group,
            job_type=self.job_type,
            **init_kwargs,
            **(kwargs or {}),
        )


__all__ = ["WandbConfig"]
