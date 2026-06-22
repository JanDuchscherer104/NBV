"""Target-conditioned rollout generation and replay Zarr stores.

`aria_nbv.rollouts` owns the multi-step thesis replay surface. It composes
VIN offline samples, actor-visible target selection, finite candidate
generation, and target-RRI oracle scoring into standalone rollout artifacts.
Raw snippet access and immutable VIN offline stores remain in
`aria_nbv.data_handling`.
"""

from .dataset_writer import (
    RolloutDatasetWriter,
    RolloutDatasetWriterConfig,
    RolloutDatasetWriterStats,
    RolloutRecipeConfig,
    RolloutTargetSource,
    SelectedDepthRetentionConfig,
)
from .inspection import (
    RolloutSuspiciousQueryConfig,
    candidate_audit_rows,
    candidate_group_summary_rows,
    candidate_result_diagnostic_counts,
    decode_invalid_reason,
    decode_position_id,
    decode_strategy_id,
    decode_target_invalid_reason,
    discover_rollout_store_paths,
    rollout_step_objective_rows,
    rollout_store_inventory_rows,
    rollout_tree_summary_rows,
    selected_depth_preview,
    selected_depth_summary_rows,
    suspicious_rollout_rows,
    target_audit_rows,
    validity_waterfall_rows,
)
from .manifest import (
    ROLLOUT_MANIFEST_FILENAME,
    ROLLOUT_MANIFEST_VERSION,
    RolloutStoreInvocation,
    RolloutStoreManifestContext,
)
from .shard_manifest import (
    ROLLOUT_SHARD_MANIFEST_VERSION,
    ROLLOUT_SHARD_OWNER_FILENAME,
    ROLLOUT_SHARD_SUCCESS_FILENAME,
    RolloutShardEntry,
    RolloutShardRow,
)
from .shards import (
    RolloutShardCampaignStatus,
    RolloutShardRunResult,
    RolloutShardStatus,
    plan_rollout_shards,
    run_rollout_shard,
    summarize_rollout_shard_campaign,
    write_rollout_shard_manifest_from_config,
)
from .trace import (
    INVALID_REASON_CODES,
    INVALID_REASON_VERSION,
    RolloutLineage,
    RolloutZarrRecord,
)
from .zarr_store import (
    DEFAULT_RETURN_SEMANTICS,
    ROLLOUT_ZARR_SCHEMA_ID,
    ROLLOUT_ZARR_SCHEMA_VERSION,
    RolloutZarrStoreConfig,
    RolloutZarrStoreReader,
    RolloutZarrValidationResult,
    RolloutZarrWriteResult,
    validate_rollout_zarr_store,
    write_rollout_zarr_store,
)

__all__ = [
    "DEFAULT_RETURN_SEMANTICS",
    "INVALID_REASON_CODES",
    "INVALID_REASON_VERSION",
    "ROLLOUT_ZARR_SCHEMA_ID",
    "ROLLOUT_ZARR_SCHEMA_VERSION",
    "ROLLOUT_MANIFEST_FILENAME",
    "ROLLOUT_MANIFEST_VERSION",
    "ROLLOUT_SHARD_MANIFEST_VERSION",
    "ROLLOUT_SHARD_OWNER_FILENAME",
    "ROLLOUT_SHARD_SUCCESS_FILENAME",
    "RolloutDatasetWriter",
    "RolloutDatasetWriterConfig",
    "RolloutDatasetWriterStats",
    "RolloutLineage",
    "RolloutRecipeConfig",
    "RolloutTargetSource",
    "RolloutSuspiciousQueryConfig",
    "SelectedDepthRetentionConfig",
    "RolloutShardCampaignStatus",
    "RolloutShardEntry",
    "RolloutShardRow",
    "RolloutShardRunResult",
    "RolloutShardStatus",
    "RolloutStoreInvocation",
    "RolloutStoreManifestContext",
    "RolloutZarrStoreConfig",
    "RolloutZarrStoreReader",
    "RolloutZarrRecord",
    "RolloutZarrValidationResult",
    "RolloutZarrWriteResult",
    "candidate_audit_rows",
    "candidate_group_summary_rows",
    "candidate_result_diagnostic_counts",
    "decode_invalid_reason",
    "decode_position_id",
    "decode_strategy_id",
    "decode_target_invalid_reason",
    "discover_rollout_store_paths",
    "plan_rollout_shards",
    "rollout_store_inventory_rows",
    "rollout_step_objective_rows",
    "rollout_tree_summary_rows",
    "run_rollout_shard",
    "selected_depth_preview",
    "selected_depth_summary_rows",
    "summarize_rollout_shard_campaign",
    "suspicious_rollout_rows",
    "target_audit_rows",
    "validity_waterfall_rows",
    "validate_rollout_zarr_store",
    "write_rollout_shard_manifest_from_config",
    "write_rollout_zarr_store",
]
