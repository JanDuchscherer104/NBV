r"""Validated rollout-to-VIN joins for finite-candidate Q_H chains.

The dataset joins private rollout source references to the exact immutable VIN
actor sample and verifies manifest and split identity before iteration. Typed
chain materialization lives in :mod:`aria_nbv.data_handling.qh_data.materialization`;
rollout decoding and VIN storage remain with their respective readers.
"""

from __future__ import annotations

from functools import cached_property
from pathlib import Path

from pydantic import Field, field_validator
from torch.utils.data import Dataset

from ...rollouts.qh_reader import QhDataContract, QhRolloutReader, _QhSourceRef
from ...rollouts.shard_manifest import build_rollout_split_manifest_hash
from ...utils import Stage, TargetConfig
from ...utils.fingerprints import stable_msgspec_hash
from ..identifiers import compact_ase_atek_sample_id
from ..vin_store.format import VinOfflineIndexRecord
from ..vin_store.store import VinOfflineStoreConfig, VinOfflineStoreReader
from .materialization import _audit_for, _evl_block_signature, _read_static_context, _tensor_chain
from .views import QhActorStateContract, QhChain


class QhDatasetConfig(TargetConfig["QhDataset"]):
    """Configure ordered rollout stores and their exact immutable VIN actor source."""

    rollout_store_dirs: tuple[Path, ...] = Field(min_length=1)
    """Non-empty rollout-store paths; tuple order defines ``QhChainKey.store_index``."""

    actor: VinOfflineStoreConfig = Field(default_factory=VinOfflineStoreConfig)
    """Immutable VIN store whose actor-visible root rows must match every rollout source reference."""

    split: Stage | None = None
    """Learning/campaign split admitted by the rollout reader; ``None`` reads all chains."""

    require_rich_modalities: bool = False
    """Require root EVL evidence and selected CF-GT depth instead of permitting an explicit diagnostic-only legacy read."""

    include_audit: bool = False
    """Attach CPU-only chain provenance for debugging; never adds payloads to scorer tensors or device transfer."""

    @field_validator("split", mode="before")
    @classmethod
    def _normalize_split(cls, value: Stage | str | None) -> Stage | None:
        """Normalize a serialized stage and map ``None`` or ``"all"`` to no split filter."""

        return None if value is None or value == "all" else Stage.from_str(value)

    @property
    def target_type(self) -> type[QhDataset]:
        """Return :class:`QhDataset` for config-as-factory construction."""

        return QhDataset

    def setup_target(self) -> QhDataset:
        """Construct both readers and preflight rollout-to-actor source identity.

        Returns:
            :class:`QhDataset` ready for indexed chain reads after validating
            the configured actor manifest, split, and source rows.
        """

        return QhDataset(
            rollout_reader=QhRolloutReader(
                self.rollout_store_dirs,
                campaign_split=self.split,
                include_selected_depth=self.require_rich_modalities,
            ),
            actor_reader=VinOfflineStoreReader(self.actor),
            split=self.split,
            require_rich_modalities=self.require_rich_modalities,
            include_audit=self.include_audit,
        )


class QhDataset(Dataset[QhChain]):
    """Join validated rollout chains to one immutable actor snippet per chain.

    Construction preflights every private source reference against the actor
    manifest and complete immutable actor index. ``split`` has already selected
    campaign chains at the rollout-reader boundary. ``__getitem__`` then reads
    one stored chain and its chain-constant root snippet exactly once. The
    result separates actor state from label support and other oracle transition
    facts; it does not decide fitted-Q admission.
    """

    _REBUILD_GUIDANCE = "Rebuild the VIN offline store and rollout corpus from the same immutable source manifest."

    def __init__(
        self,
        *,
        rollout_reader: QhRolloutReader,
        actor_reader: VinOfflineStoreReader,
        split: Stage | None = None,
        require_rich_modalities: bool = False,
        include_audit: bool = False,
    ) -> None:
        """Validate rollout provenance against the configured immutable actor store.

        Args:
            rollout_reader: Complete stored chains plus private immutable-source
                references and the fixed Q_H data contract.
            actor_reader: Reader for the immutable VIN actor rows referenced by
                the rollout corpus.
            split: Optional campaign/learning split selected by the rollout
                reader; physical source splits remain validated independently.
        """

        self.rollout_reader = rollout_reader
        self.actor_reader = actor_reader
        reader_split = rollout_reader.campaign_split
        if split is not None and reader_split != split:
            raise ValueError(
                "Q_H dataset split must match rollout_reader.campaign_split; "
                f"received split={split!r}, reader campaign_split={reader_split!r}."
            )
        self.split = reader_split
        self.require_rich_modalities = require_rich_modalities
        self.include_audit = include_audit
        self._manifest_hash = stable_msgspec_hash(actor_reader.manifest)
        self._actor_state_contract = QhActorStateContract(
            modality_mode="rich" if require_rich_modalities else "lean",
            actor_manifest_hash=self._manifest_hash,
            evl_block_signature=_evl_block_signature(actor_reader) if require_rich_modalities else (),
        )
        self._records = {record.sample_index: record for record in actor_reader.get_split_records(None)}
        self._validate_source_refs()

    def __len__(self) -> int:
        """Return the number of complete stored rollout chains."""

        return len(self.rollout_reader)

    def __getitem__(self, index: int) -> QhChain:
        """Read and tensorize one chain with its chain-constant root observation.

        Args:
            index: Zero-based rollout-reader position.

        Returns:
            :class:`QhChain` containing actor-visible tensors, separately owned
            supervision facts, and a CPU-only audit key. Candidate rows retain
            stored widths until collation.
        """

        stored = self.rollout_reader[index]
        record = self._record(stored.source_ref)
        snippet = self.actor_reader.read_actor_snippet(record, device="cpu")
        static_context = (
            _read_static_context(self.actor_reader, record, snippet) if self.require_rich_modalities else None
        )
        if self.require_rich_modalities and (static_context is None or not bool(static_context.evl_presence.all())):
            raise ValueError(
                "Q_H rich training requires every root EVL evidence field; rebuild the VIN offline store with backbone materialization."
            )
        return _tensor_chain(
            stored,
            snippet,
            static_context=static_context,
            require_rich_modalities=self.require_rich_modalities,
            audit=_audit_for(stored, self.rollout_reader.store_dirs[stored.store_index])
            if self.include_audit
            else None,
        )

    @cached_property
    def scenes(self) -> frozenset[str]:
        """Return immutable ASE scene identifiers represented by the validated corpus."""

        return self.rollout_reader.scenes

    @property
    def max_horizon(self) -> int:
        """Return the largest realized horizon among the validated chains."""

        return self.rollout_reader.max_horizon

    @property
    def contract(self) -> QhDataContract:
        """Return compatibility facts shared across the corpus's realized horizons.

        Horizon length is a per-chain fact represented by state count and
        ``horizon_remaining``; it is intentionally absent from this common
        reward, return, discount, schema, and provenance contract.
        """

        return self.rollout_reader.contract

    @property
    def actor_state_contract(self) -> QhActorStateContract:
        """Return metadata-only scorer-input compatibility facts for this stage."""

        return self._actor_state_contract

    @property
    def provenance(self) -> dict[str, object]:
        """Return rollout/actor store identity for audit displays, never scorer input."""

        return {
            "rollout": self.rollout_reader.provenance,
            "actor": {
                "store_path": str(self.actor_reader.config.store_dir),
                "store_version": str(self.actor_reader.manifest.version),
                "manifest_hash": self._manifest_hash,
                "split": self.split,
                "row_count": len(self._records),
            },
        }

    def _validate_source_refs(self) -> None:
        """Preflight exact actor rows and ordered per-source split membership."""

        for source_ref in self.rollout_reader.source_refs:
            self._record(source_ref)
        groups: dict[tuple[str, Stage, str], list[_QhSourceRef]] = {}
        for source_ref in self.rollout_reader.source_refs:
            groups.setdefault(
                (source_ref.source_manifest_hash, source_ref.split, source_ref.split_manifest_hash), []
            ).append(source_ref)
        for (manifest_hash, split, expected), source_refs in groups.items():
            records = [self._record(source_ref) for source_ref in source_refs]
            actual = build_rollout_split_manifest_hash(
                source_manifest_hash=manifest_hash,
                split=split.value,
                records=[
                    {
                        "order": order,
                        "sample_index": record.sample_index,
                        "sample_key": record.sample_key,
                        "scene_id": record.scene_id,
                        "snippet_id": record.snippet_id,
                        "split": record.split,
                        "source_shard_id": record.shard_id,
                        "source_shard_row": record.row,
                        **(
                            {
                                "campaign_split": source_ref.campaign_split.value
                                if source_ref.campaign_split is not Stage.VAL
                                else "validation"
                            }
                            if source_ref.campaign_split is not None
                            else {}
                        ),
                    }
                    for order, (record, source_ref) in enumerate(zip(records, source_refs, strict=True))
                ],
            )
            if actual != expected:
                raise ValueError(f"VIN split manifest does not match rollout source identity. {self._REBUILD_GUIDANCE}")

    def _record(self, source_ref: _QhSourceRef) -> VinOfflineIndexRecord:
        """Resolve one actor row and verify every persisted source-identity field."""

        try:
            record = self._records[source_ref.source_sample_index]
        except KeyError as error:
            raise KeyError(
                f"VIN sample_index={source_ref.source_sample_index} is absent from split {self.split!r}. "
                f"{self._REBUILD_GUIDANCE}"
            ) from error
        actual = (
            record.sample_index,
            compact_ase_atek_sample_id(record.sample_key),
            record.shard_id,
            record.row,
            record.scene_id,
            compact_ase_atek_sample_id(record.snippet_id),
            Stage.from_str(record.split),
            str(self.actor_reader.manifest.version),
            self._manifest_hash,
        )
        expected = (
            source_ref.source_sample_index,
            compact_ase_atek_sample_id(source_ref.source_sample_key),
            source_ref.source_shard_id,
            source_ref.source_shard_row,
            source_ref.scene_id,
            compact_ase_atek_sample_id(source_ref.snippet_id),
            source_ref.split,
            source_ref.actor_store_version,
            source_ref.source_manifest_hash,
        )
        if actual != expected:
            raise ValueError(f"VIN source identity does not match rollout chain. {self._REBUILD_GUIDANCE}")
        return record
