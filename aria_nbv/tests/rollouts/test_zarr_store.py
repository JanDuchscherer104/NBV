"""Smoke tests for the standalone rollout Zarr replay store."""

# ruff: noqa: S101

from __future__ import annotations

import inspect
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import torch
import zarr

pytest.importorskip("efm3d")

from efm3d.aria.pose import PoseTW

from aria_nbv.oracle.target_rri import TARGET_CROP_POLICY_GT_OBB_ORIENTED_ANY_VERTEX_V1
from aria_nbv.oracle.target_selection import TARGET_INVALID_REASON_VERSION
from aria_nbv.pose_generation import candidate_set_to_legacy_result
from aria_nbv.pose_generation.candidate_mixture import CandidateMixtureViewGeneratorConfig
from aria_nbv.pose_generation.program_generator import ProgramCandidateGenerator
from aria_nbv.rollouts import RolloutZarrStoreConfig, RolloutZarrStoreReader
from aria_nbv.rollouts.candidate_evidence import (
    CandidateFactAvailability,
    candidate_evidence_snapshot_from_stored,
)
from aria_nbv.rollouts.info_cli import main as rollouts_info_main
from aria_nbv.rollouts.inspection import (
    candidate_audit_rows,
    candidate_flow_rows,
    rollout_statistics,
    root_relative_candidate_rows,
)
from aria_nbv.rollouts.manifest import ROLLOUT_MANIFEST_FILENAME, RolloutStoreManifestContext
from aria_nbv.rollouts.read_model import rollout_rows, rollout_steps, target_by_id
from aria_nbv.rollouts.trace import (
    CANDIDATE_TRACE_CODEC_VERSION,
    INVALID_REASON_CODES,
    INVALID_REASON_VERSION,
    CandidateTraceFacts,
    candidate_trace_facts,
)
from aria_nbv.rollouts.zarr_store import (
    ROLLOUT_ZARR_SCHEMA_VERSION,
    validate_rollout_zarr_store,
    write_rollout_zarr_store,
)
from tests.rollout_fixtures import build_rollout_records


def _json_list(reader: RolloutZarrStoreReader, path: str) -> list[str]:
    return json.loads(bytes(reader.array(path).tolist()).decode("utf-8"))


def _steps(record):
    return [record.evaluated.step(0, step.step_index) for step in record.evaluated.result.trajectories[0].steps]


def _mask_target_eval_candidate_rows(step) -> None:
    valid_count = int(step.transition.candidates.mask_valid.detach().cpu().to(dtype=torch.bool).sum().item())
    step.evaluation.evidence.target_eval_candidate_points_world = torch.zeros((valid_count, 2, 3), dtype=torch.float32)
    step.evaluation.evidence.target_eval_candidate_point_lengths = torch.full((valid_count,), 2, dtype=torch.long)


def _readonly_int64(values: list[int]) -> np.ndarray:
    array = np.asarray(values, dtype=np.int64)
    array.setflags(write=False)
    return array


def _attach_candidate_trace_facts(records) -> None:
    """Attach deterministic current-codec facts without migrating replay composition."""

    for record in records:
        config_hash = record.lineage.policy.candidate_config_hash
        for trajectory in record.evaluated.result.trajectories:
            for step in trajectory.steps:
                mask = step.candidates.mask_valid.detach().cpu().to(dtype=torch.bool).reshape(-1)
                n = int(mask.numel())
                valid = torch.nonzero(mask, as_tuple=False).reshape(-1).tolist()
                lineage = _readonly_int64(list(range(n)))
                inapplicable = _readonly_int64([-1] * n)
                step.candidate_trace_facts = CandidateTraceFacts(
                    codec_version=CANDIDATE_TRACE_CODEC_VERSION,
                    semantic_group_id=tuple("fixture-group" for _ in range(n)),
                    center_family_id=tuple("forward_local" for _ in range(n)),
                    gaze_family_id=tuple("directional" for _ in range(n)),
                    candidate_family_id=tuple("fixture-family" for _ in range(n)),
                    center_id=lineage,
                    position_pair_id=inapplicable,
                    gaze_variant_id=_readonly_int64([-1] * n),
                    attempt_round_id=_readonly_int64([0] * n),
                    draw_id=_readonly_int64(list(range(n))),
                    proposal_key=tuple(f"fixture:{index}" for index in range(n)),
                    target_frame_identity=tuple("" for _ in range(n)),
                    target_frame_availability=tuple("unavailable" for _ in range(n)),
                    criteria=(),
                    valid_indices=_readonly_int64(valid),
                    action_indices=_readonly_int64(valid),
                    candidate_program_hash="1" * 64,
                    request_binding_hash="2" * 64,
                    candidate_substream_revision="shipped_mixture_seed_paths_v1",
                    action_order_revision="ordered_hard_valid_v1",
                    completion_mode="fixed_attempts",
                    attempted_count=n,
                    valid_count=len(valid),
                    action_count=len(valid),
                    proposal_key_revision="rollout-proposal-v1",
                    proposal_replica=0,
                    legacy_candidate_config_hash=config_hash,
                )


def _array_paths(group: zarr.Group, prefix: str = "") -> tuple[str, ...]:
    paths = [f"{prefix}{name}" for name in group.array_keys()]
    for name in group.group_keys():
        paths.extend(_array_paths(group[name], f"{prefix}{name}/"))
    return tuple(sorted(paths))


def _array_storage_bytes(store_path: Path, array_path: str) -> dict[str, bytes]:
    directory = store_path / array_path
    return {
        str(path.relative_to(directory)): path.read_bytes() for path in sorted(directory.rglob("*")) if path.is_file()
    }


def test_candidate_codec_dual_write_preserves_legacy_tables_and_reads_semantics(tmp_path) -> None:
    from aria_nbv.rerun_inspector._rollout_zarr import _stored_candidate_family_names

    legacy_records = build_rollout_records(horizon=1, num_samples=4, seed=91)
    current_records = build_rollout_records(horizon=1, num_samples=4, seed=91)
    _attach_candidate_trace_facts(current_records)
    legacy_path = tmp_path / "legacy.zarr"
    current_path = tmp_path / "current.zarr"
    write_rollout_zarr_store(legacy_path, legacy_records, split_manifest_hash="fixture-split-manifest")
    write_rollout_zarr_store(current_path, current_records, split_manifest_hash="fixture-split-manifest")
    legacy = RolloutZarrStoreReader(legacy_path)
    current = RolloutZarrStoreReader(current_path)

    legacy_array_paths = _array_paths(legacy.root)
    additive_prefixes = (
        "step_candidate_facts/",
        "candidate_semantics/",
        "candidate_criteria/",
        "candidate_actions/",
        "candidate_valids/",
    )
    current_legacy_paths = tuple(
        path
        for path in _array_paths(current.root)
        if not path.startswith(additive_prefixes) and path != "dictionaries/candidate_fact"
    )
    assert current_legacy_paths == legacy_array_paths
    for path in legacy_array_paths:
        left = legacy.root[path]
        right = current.root[path]
        assert left.dtype == right.dtype
        assert left.shape == right.shape
        assert left.chunks == right.chunks
        assert np.array_equal(np.asarray(left), np.asarray(right), equal_nan=True)
        assert _array_storage_bytes(legacy_path, path) == _array_storage_bytes(current_path, path)
    assert "candidate_fact" not in legacy.root["dictionaries"]
    assert current.root.attrs["candidate_trace_codec_version"] == CANDIDATE_TRACE_CODEC_VERSION
    assert current.root.attrs["q_h_source_tables"] == "steps,candidates,rollouts,targets"
    assert validate_rollout_zarr_store(current_path).ok

    rollout = rollout_rows(current)[0]
    stored = rollout_steps(current, rollout)[0]
    assert stored.candidate_codec is not None
    assert stored.candidate_codec.candidate_family_ids.tolist() == ["fixture-family"] * stored.num_candidates
    assert stored.candidate_codec.valid_indices.tolist() == np.flatnonzero(stored.actor_action_mask).tolist()
    assert stored.candidate_codec.action_indices.tolist() == stored.candidate_codec.valid_indices.tolist()
    assert _stored_candidate_family_names(stored).tolist() == ["fixture-family"] * stored.num_candidates
    legacy_step = rollout_steps(legacy, rollout_rows(legacy)[0])[0]
    assert _stored_candidate_family_names(legacy_step).tolist() == legacy_step.mixture_names.tolist()
    assert not stored.candidate_codec.valid_indices.flags.writeable
    assert current.candidate_codec_tables() is current.candidate_codec_tables()
    audit = candidate_audit_rows(current, limit=stored.num_candidates)
    assert {str(row["mixture"]) for row in audit} == {"fixture-family"}
    flow = candidate_flow_rows(current)
    assert any(str(row["target_id"]).startswith("proposal:fixture:") for row in flow)
    geometry = root_relative_candidate_rows(current, rollout_row_id=rollout.rollout_row_id)
    assert {str(row["mixture"]) for row in geometry} == {"fixture-family"}
    statistics = rollout_statistics(current)
    assert set(statistics["valid_candidates"]["component_counts"]) == {"fixture-family"}
    assert set(statistics["selected"]["component_counts"]) == {"fixture-family"}


def test_candidate_codec_reader_rejects_partial_bundle(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=4, seed=92)
    _attach_candidate_trace_facts(records)
    store_path = tmp_path / "partial.zarr"
    write_rollout_zarr_store(store_path, records, split_manifest_hash="fixture-split-manifest")
    root = zarr.open_group(str(store_path), mode="a")
    del root["candidate_valids"]

    with pytest.raises(ValueError, match="complete supported table/dictionary/version bundle"):
        RolloutZarrStoreReader(store_path)
    validation = validate_rollout_zarr_store(store_path)
    assert not validation.ok
    assert any("complete supported table/dictionary/version bundle" in error for error in validation.errors)


def test_candidate_codec_writer_rejects_same_count_valid_order_drift(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=4, seed=93)[:1]
    _attach_candidate_trace_facts(records)
    step = _steps(records[0])[0].transition
    facts = step.candidate_trace_facts
    assert facts is not None and facts.valid_count >= 2
    permuted = facts.valid_indices.copy()
    permuted[:2] = permuted[1::-1]
    permuted.setflags(write=False)
    step.candidate_trace_facts = replace(facts, valid_indices=permuted)

    with pytest.raises(ValueError, match="valid_indices must equal the legacy compact-valid order"):
        write_rollout_zarr_store(tmp_path / "permuted.zarr", records)


def test_candidate_codec_writer_requires_independent_legacy_config_hash(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=4, seed=930)[:1]
    _attach_candidate_trace_facts(records)
    record = records[0]
    record.lineage.policy.candidate_config_hash = None
    step = _steps(record)[0].transition
    facts = step.candidate_trace_facts
    assert facts is not None
    step.candidate_trace_facts = replace(facts, legacy_candidate_config_hash=None)

    with pytest.raises(ValueError, match="requires an independently persisted legacy candidate config hash"):
        write_rollout_zarr_store(tmp_path / "missing-legacy-hash.zarr", records)


def test_candidate_codec_validator_rejects_per_owner_config_hash_swap(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=4, seed=94)[:2]
    records[1].lineage.policy.candidate_config_hash = "fixture-config-second"
    _attach_candidate_trace_facts(records)
    store_path = tmp_path / "swapped-hash.zarr"
    write_rollout_zarr_store(store_path, records, split_manifest_hash="fixture-split-manifest")
    root = zarr.open_group(str(store_path), mode="a")
    hashes = root["step_candidate_facts/legacy_candidate_config_hash_id"]
    values = np.asarray(hashes).copy()
    assert values.shape == (2,) and values[0] != values[1]
    hashes[:] = values[::-1]

    validation = validate_rollout_zarr_store(store_path)
    assert not validation.ok
    assert any("owning rollout lineage" in error for error in validation.errors)


def test_candidate_codec_reader_rejects_wrong_additive_dtype(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=4, seed=95)[:1]
    _attach_candidate_trace_facts(records)
    store_path = tmp_path / "wrong-dtype.zarr"
    write_rollout_zarr_store(store_path, records, split_manifest_hash="fixture-split-manifest")
    root = zarr.open_group(str(store_path), mode="a")
    group = root["candidate_valids"]
    array = group["valid_position"]
    values = np.asarray(array, dtype=np.int64)
    chunks = array.chunks
    del group["valid_position"]
    group.create_array("valid_position", data=values, chunks=chunks)

    with pytest.raises(ValueError, match="must be 1-D int32"):
        RolloutZarrStoreReader(store_path)
    validation = validate_rollout_zarr_store(store_path)
    assert not validation.ok
    assert any("must be 1-D int32" in error for error in validation.errors)


@pytest.mark.parametrize(
    ("updates", "match"),
    [
        (("candidate_semantics/center_id", -1), "non-negative"),
        (
            (("candidate_semantics/position_pair_id", -2), ("candidate_semantics/gaze_variant_id", -2)),
            "exactly -1",
        ),
        (
            (
                ("step_candidate_facts/proposal_key_revision_id", -2),
                ("step_candidate_facts/proposal_replica", -2),
            ),
            "sentinel must be exactly -1",
        ),
        (("step_candidate_facts/legacy_candidate_config_hash_id", -2), "sentinel must be exactly -1"),
    ],
)
def test_candidate_codec_reader_rejects_invalid_lineage_sentinels(tmp_path, updates, match: str) -> None:
    records = build_rollout_records(horizon=1, num_samples=4, seed=97)[:1]
    _attach_candidate_trace_facts(records)
    store_path = tmp_path / "invalid-sentinel.zarr"
    write_rollout_zarr_store(store_path, records, split_manifest_hash="fixture-split-manifest")
    root = zarr.open_group(str(store_path), mode="a")
    normalized = (updates,) if isinstance(updates[0], str) else updates
    for path, value in normalized:
        root[path][0] = value

    validation = validate_rollout_zarr_store(store_path)
    assert not validation.ok
    reader = RolloutZarrStoreReader(store_path)
    with pytest.raises(ValueError, match=match):
        rollout_steps(reader, rollout_rows(reader)[0])


def test_candidate_codec_validator_and_reader_reject_invalid_dictionary_references(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=4, seed=98)[:1]
    _attach_candidate_trace_facts(records)
    store_path = tmp_path / "invalid-dictionary-reference.zarr"
    write_rollout_zarr_store(store_path, records, split_manifest_hash="fixture-split-manifest")
    zarr.open_group(str(store_path), mode="a")["candidate_semantics/candidate_family_id"][0] = 999_999

    validation = validate_rollout_zarr_store(store_path)
    assert not validation.ok
    assert any("contains an invalid reference" in error for error in validation.errors)
    reader = RolloutZarrStoreReader(store_path)
    with pytest.raises(ValueError, match="dictionary id is outside"):
        rollout_steps(reader, rollout_rows(reader)[0])


def test_current_codec_reducers_reject_empty_semantic_identity(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=4, seed=980)[:1]
    _attach_candidate_trace_facts(records)
    store_path = tmp_path / "empty-semantic-identity.zarr"
    write_rollout_zarr_store(store_path, records, split_manifest_hash="fixture-split-manifest")
    root = zarr.open_group(str(store_path), mode="a")
    dictionary = _json_list(RolloutZarrStoreReader(store_path), "dictionaries/candidate_fact")
    empty_identity_id = dictionary.index("")
    root["candidate_semantics/proposal_key_id"][0] = empty_identity_id

    validation = validate_rollout_zarr_store(store_path)
    assert not validation.ok
    reader = RolloutZarrStoreReader(store_path)
    with pytest.raises(ValueError, match="semantic identities must be nonempty strings"):
        candidate_flow_rows(reader)


def test_candidate_codec_validator_and_reader_reject_attempted_count_drift(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=4, seed=101)[:1]
    _attach_candidate_trace_facts(records)
    store_path = tmp_path / "attempted-count-drift.zarr"
    write_rollout_zarr_store(store_path, records, split_manifest_hash="fixture-split-manifest")
    root = zarr.open_group(str(store_path), mode="a")
    root["step_candidate_facts/attempted_count"][0] += 1

    validation = validate_rollout_zarr_store(store_path)
    assert not validation.ok
    assert any("attempted count disagrees" in error for error in validation.errors)
    reader = RolloutZarrStoreReader(store_path)
    with pytest.raises(ValueError, match="attempted count does not match"):
        rollout_steps(reader, rollout_rows(reader)[0])


@pytest.mark.parametrize("group_name", ["candidate_valids", "candidate_actions"])
def test_candidate_codec_validator_and_reader_reject_orphan_projection_rows(tmp_path, group_name: str) -> None:
    records = build_rollout_records(horizon=1, num_samples=4, seed=102)[:1]
    _attach_candidate_trace_facts(records)
    store_path = tmp_path / f"orphan-{group_name}.zarr"
    write_rollout_zarr_store(store_path, records, split_manifest_hash="fixture-split-manifest")
    root = zarr.open_group(str(store_path), mode="a")
    group = root[group_name]
    for name in group.array_keys():
        array = group[name]
        old_size = int(array.shape[0])
        array.resize((old_size + 1,))
        array[old_size] = 999 if name == "step_row_id" else 0
    count_attr = "candidate_trace_valid_rows" if group_name == "candidate_valids" else "candidate_trace_action_rows"
    root.attrs[count_attr] = int(root.attrs[count_attr]) + 1

    validation = validate_rollout_zarr_store(store_path)
    assert not validation.ok
    assert any("reference unknown stored steps" in error for error in validation.errors)
    reader = RolloutZarrStoreReader(store_path)
    with pytest.raises(ValueError, match="reference unknown stored steps"):
        reader.candidate_codec_tables()


def test_candidate_codec_validator_rejects_supported_reference_to_unknown_revision(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=4, seed=99)[:1]
    _attach_candidate_trace_facts(records)
    store_path = tmp_path / "unknown-revision.zarr"
    write_rollout_zarr_store(store_path, records, split_manifest_hash="fixture-split-manifest")
    root = zarr.open_group(str(store_path), mode="a")
    values = _json_list(RolloutZarrStoreReader(store_path), "dictionaries/candidate_fact")
    revision_id = int(root["step_candidate_facts/candidate_substream_revision_id"][0])
    values[revision_id] = "future_v9"
    payload = np.frombuffer(json.dumps(values, separators=(",", ":")).encode("utf-8"), dtype=np.uint8)
    dictionaries = root["dictionaries"]
    del dictionaries["candidate_fact"]
    dictionaries.create_array("candidate_fact", data=payload, chunks=(max(1, payload.size),))

    validation = validate_rollout_zarr_store(store_path)
    assert not validation.ok
    assert any("substream revision is unsupported" in error for error in validation.errors)
    reader = RolloutZarrStoreReader(store_path)
    with pytest.raises(ValueError, match="substream revision is unsupported"):
        rollout_steps(reader, rollout_rows(reader)[0])


def test_candidate_codec_lazy_grouping_stays_sort_linearithmic(monkeypatch: pytest.MonkeyPatch) -> None:
    from aria_nbv.rollouts.zarr_store import _grouped_positions

    source = inspect.getsource(_grouped_positions)
    assert 'np.argsort(values, kind="stable")' in source
    assert "np.flatnonzero(values ==" not in source
    calls = 0
    original = np.flatnonzero

    def counted(values: np.ndarray) -> np.ndarray:
        nonlocal calls
        calls += 1
        return original(values)

    monkeypatch.setattr(np, "flatnonzero", counted)
    grouped = _grouped_positions(np.arange(10_000, dtype=np.int64))
    assert len(grouped) == 10_000
    assert calls == 1


def test_candidate_codec_writer_uses_constant_time_dictionary_lookup() -> None:
    from aria_nbv.rollouts.zarr_store import _candidate_fact_id

    identities = {f"proposal:{index}": index for index in range(10_000)}
    assert [_candidate_fact_id(identities, key) for key in identities] == list(range(10_000))
    assert ".index(" not in inspect.getsource(_candidate_fact_id)


def test_candidate_codec_reader_decodes_large_dictionary_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aria_nbv.rollouts.zarr_store as store_module

    records = build_rollout_records(horizon=1, num_samples=4, seed=96)[:1]
    _attach_candidate_trace_facts(records)
    store_path = tmp_path / "dictionary-once.zarr"
    write_rollout_zarr_store(store_path, records, split_manifest_hash="fixture-split-manifest")
    calls = 0
    original = store_module._candidate_fact_dictionary

    def counted(root: object) -> tuple[str, ...]:
        nonlocal calls
        calls += 1
        return original(root)

    monkeypatch.setattr(store_module, "_candidate_fact_dictionary", counted)
    reader = RolloutZarrStoreReader(store_path)
    assert reader.candidate_codec_tables() is reader.candidate_codec_tables()
    assert calls == 1


def test_candidate_codec_validator_decodes_large_dictionary_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aria_nbv.rollouts.zarr_store as store_module

    records = build_rollout_records(horizon=1, num_samples=4, seed=100)[:1]
    _attach_candidate_trace_facts(records)
    store_path = tmp_path / "validation-dictionary-once.zarr"
    write_rollout_zarr_store(store_path, records, split_manifest_hash="fixture-split-manifest")
    calls = 0
    original = store_module._candidate_fact_dictionary

    def counted(root: object) -> tuple[str, ...]:
        nonlocal calls
        calls += 1
        return original(root)

    monkeypatch.setattr(store_module, "_candidate_fact_dictionary", counted)
    validation = validate_rollout_zarr_store(store_path)
    assert validation.ok, validation.errors
    assert calls == 1


def test_real_paired_candidate_set_survives_zarr_and_inspection_codecs(tmp_path) -> None:
    from tests.pose_generation.test_candidate_interface import _query_free, _request

    config = _query_free(CandidateMixtureViewGeneratorConfig.paired_center_gaze_family())
    candidate_set = ProgramCandidateGenerator().generate(_request(config, seed=43))
    projected = candidate_set_to_legacy_result(candidate_set)
    assert candidate_set.completion.attempted_count == 60
    assert 0 < candidate_set.completion.valid_count < 60
    # The legacy rollout fixture emits two gaze variants per configured centre,
    # so 30 configured centres produce the same 60-row attempted shell.
    records = build_rollout_records(horizon=1, num_samples=30, seed=43)[:1]
    lineage = records[0].lineage
    lineage.source.scene_id = "scene-content-sha256"
    lineage.source.mesh_version = "mesh-content-sha256"
    lineage.target.target_protocol_version = "v1_observed"
    lineage.target.target_source = "detected_obbs"
    lineage.target.target_sem_id = 1
    lineage.target.target_class_name = "chair"
    lineage.target.target_center_world = (0.0, 0.0, 2.0)
    lineage.target.target_pose_world_object = (
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        2.0,
    )
    lineage.target.target_relative_pose_reference_object = lineage.target.target_pose_world_object
    for record in records:
        for trajectory in record.evaluated.result.trajectories:
            for step in trajectory.steps:
                step.candidates = projected
                step.candidate_trace_facts = candidate_trace_facts(
                    candidate_set,
                    proposal_key_revision="rollout-proposal-v1",
                    proposal_replica=3,
                    legacy_candidate_config_hash=record.lineage.policy.candidate_config_hash,
                )
    store_path = tmp_path / "paired.zarr"
    write_rollout_zarr_store(store_path, records, split_manifest_hash="fixture-split-manifest")
    reader = RolloutZarrStoreReader(store_path)
    rollout = rollout_rows(reader)[0]
    step = rollout_steps(reader, rollout)[0]
    codec = step.candidate_codec
    assert codec is not None
    assert codec.semantic_group_ids.tolist() == list(candidate_set.attempts.semantic_group_id)
    assert codec.center_family_ids.tolist() == list(candidate_set.attempts.center_family_id)
    assert codec.gaze_family_ids.tolist() == list(candidate_set.attempts.gaze_family_id)
    assert codec.candidate_family_ids.tolist() == list(candidate_set.attempts.candidate_family_id)
    assert codec.position_pair_ids.tolist() == candidate_set.attempts.position_pair_id.tolist()
    assert codec.gaze_variant_ids.tolist() == candidate_set.attempts.gaze_variant_id.tolist()
    assert [criterion.criterion_id for criterion in codec.criteria] == [
        criterion.criterion_id for criterion in candidate_set.admission.criteria
    ]
    assert codec.candidate_program_hash == candidate_set.candidate_program_hash
    assert codec.request_binding_hash == candidate_set.request_binding_hash
    target = target_by_id(reader, rollout.target_row_id)
    assert target is not None
    snapshot = candidate_evidence_snapshot_from_stored(rollout, step, target)
    assert all(row.admission_availability is CandidateFactAvailability.AVAILABLE for row in snapshot.rows)
    criterion_group = zarr.open_group(store_path, mode="a")["candidate_criteria"]
    criterion_group["local_available"][:] = False
    for name in ("applicable", "evaluated", "passed"):
        criterion_group[name][:] = False
    for name in ("reason_code", "source_role"):
        criterion_group[name][:] = -1
    criterion_group["margin"][:] = np.nan
    unavailable_reader = RolloutZarrStoreReader(store_path)
    unavailable_rollout = rollout_rows(unavailable_reader)[0]
    unavailable_step = rollout_steps(unavailable_reader, unavailable_rollout)[0]
    unavailable_target = target_by_id(unavailable_reader, unavailable_rollout.target_row_id)
    assert unavailable_target is not None
    unavailable_snapshot = candidate_evidence_snapshot_from_stored(
        unavailable_rollout,
        unavailable_step,
        unavailable_target,
    )
    assert all(row.admission_availability is CandidateFactAvailability.PARTIAL for row in unavailable_snapshot.rows)
    audit = candidate_audit_rows(reader, limit=60)
    assert {row["mixture"] for row in audit} == set(candidate_set.attempts.candidate_family_id)
    flow = candidate_flow_rows(reader)
    proposal_nodes = {str(row["target_id"]) for row in flow if row["target_stage"] == "proposal"}
    assert proposal_nodes == {f"proposal:{key}" for key in candidate_set.attempts.proposal_key}

    criterion_indices = np.asarray(criterion_group["criterion_index"], dtype=np.int64)
    criterion_ids = criterion_group["criterion_id"]
    original_ids = np.asarray(criterion_ids, dtype=np.int64)
    first_rows = np.flatnonzero(criterion_indices == 0)
    second_rows = np.flatnonzero(criterion_indices == 1)
    criterion_ids[second_rows[0]] = original_ids[first_rows[0]]
    drift_validation = validate_rollout_zarr_store(store_path)
    assert not drift_validation.ok
    assert any("constant over N" in error for error in drift_validation.errors)
    criterion_ids[:] = original_ids
    criterion_ids[second_rows] = original_ids[first_rows[0]]
    duplicate_validation = validate_rollout_zarr_store(store_path)
    assert not duplicate_validation.ok
    assert any("identities must be unique per step" in error for error in duplicate_validation.errors)
    duplicate_reader = RolloutZarrStoreReader(store_path)
    with pytest.raises(ValueError, match="criterion identities must be unique"):
        rollout_steps(duplicate_reader, rollout_rows(duplicate_reader)[0])


def test_mixed_admission_availability_round_trips_with_explicit_sentinels(tmp_path) -> None:
    from aria_nbv.data_handling.vin_store.candidate_codec import vin_candidate_facts
    from tests.pose_generation.test_candidate_interface import _typed_admission_fixture

    _config, _scene, _request, candidate_set = _typed_admission_fixture()
    path = next(
        criterion for criterion in candidate_set.admission.criteria if criterion.criterion_id == "path_clearance"
    )
    assert path.local is not None
    availability = path.local_availability.tolist()
    assert any(availability) and not all(availability)

    vin_facts = vin_candidate_facts(candidate_set, legacy_candidate_config_hash="fixture-config")
    vin_path = next(criterion for criterion in vin_facts.criteria if criterion.criterion_id == "path_clearance")
    assert vin_path.applicable is not None
    assert vin_path.evaluated is not None
    assert vin_path.passed is not None
    assert vin_path.reason_code is not None
    assert vin_path.margin is not None
    assert vin_path.source_role is not None
    for index, available in enumerate(availability):
        if available:
            assert vin_path.applicable[index] == bool(path.local.applicable[index])
            assert vin_path.evaluated[index] == bool(path.local.evaluated[index])
            assert vin_path.reason_code[index] == int(path.local.reason_code[index])
            assert vin_path.source_role[index] == int(path.local.source_role[index])
        else:
            assert vin_path.applicable[index] is False
            assert vin_path.evaluated[index] is False
            assert vin_path.passed[index] is False
            assert vin_path.reason_code[index] == -1
            assert vin_path.source_role[index] == -1
            assert np.isnan(vin_path.margin[index])

    records = build_rollout_records(horizon=1, num_samples=4, seed=31)[:1]
    lineage = records[0].lineage
    lineage.source.scene_id = "scene-content-sha256"
    lineage.source.mesh_version = "mesh-content-sha256"
    lineage.target.target_protocol_version = "v1_observed"
    lineage.target.target_source = "detected_obbs"
    lineage.target.target_center_world = (0.0, 0.0, 2.0)
    projected = candidate_set_to_legacy_result(candidate_set)
    step = records[0].evaluated.result.trajectories[0].steps[0]
    step.candidates = projected
    selected_shell_index = int(candidate_set.action_indices[0])
    step.selected_shell_index = selected_shell_index
    step.selected_valid_index = candidate_set.valid_indices.tolist().index(selected_shell_index)
    step.candidate_trace_facts = candidate_trace_facts(
        candidate_set,
        legacy_candidate_config_hash=lineage.policy.candidate_config_hash,
    )
    store_path = tmp_path / "mixed-admission.zarr"
    write_rollout_zarr_store(store_path, records, split_manifest_hash="fixture-split-manifest")
    reader = RolloutZarrStoreReader(store_path)
    stored = rollout_steps(reader, rollout_rows(reader)[0])[0]
    assert stored.candidate_codec is not None
    stored_path = next(
        criterion for criterion in stored.candidate_codec.criteria if criterion.criterion_id == "path_clearance"
    )
    assert stored_path.local_available.tolist() == availability
    unavailable = ~stored_path.local_available
    assert not stored_path.applicable[unavailable].any()
    assert not stored_path.evaluated[unavailable].any()
    assert not stored_path.passed[unavailable].any()
    assert np.all(stored_path.reason_code[unavailable] == -1)
    assert np.all(stored_path.source_role[unavailable] == -1)
    assert np.isnan(stored_path.margin[unavailable]).all()
    target = target_by_id(reader, rollout_rows(reader)[0].target_row_id)
    assert target is not None
    snapshot = candidate_evidence_snapshot_from_stored(
        rollout_rows(reader)[0],
        stored,
        target,
    )
    assert any(row.admission_availability is CandidateFactAvailability.PARTIAL for row in snapshot.rows)
    assert any(row.admission_availability is CandidateFactAvailability.AVAILABLE for row in snapshot.rows)

    root = zarr.open_group(str(store_path), mode="a")
    local_available = np.asarray(root["candidate_criteria/local_available"], dtype=np.bool_)
    passed = np.asarray(root["candidate_criteria/passed"], dtype=np.bool_)
    passed_row = int(np.flatnonzero(local_available & passed)[0])
    root["candidate_criteria/passed"][passed_row] = False
    root["candidate_criteria/reason_code"][passed_row] = 1
    validation = validate_rollout_zarr_store(store_path)
    assert not validation.ok
    assert any("contradicts local criterion evidence" in error for error in validation.errors)
    corrupted_reader = RolloutZarrStoreReader(store_path)
    with pytest.raises(ValueError, match="contradicts local criterion evidence"):
        rollout_steps(corrupted_reader, rollout_rows(corrupted_reader)[0])


def test_rollout_zarr_store_writes_reads_and_validates_records(tmp_path) -> None:
    records = build_rollout_records(horizon=2, num_samples=8, seed=7)
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        records,
        discount_gamma=0.95,
        target_protocol_version="v0_gt_input",
        source_offline_store_version="7",
        split_manifest_hash="fixture-split-manifest",
    )

    assert result.num_rollouts == 3
    assert result.num_steps == 6
    assert result.num_candidates > 0

    validation = validate_rollout_zarr_store(result.store_dir)
    assert validation.ok, validation.errors

    reader = RolloutZarrStoreReader(result.store_dir)
    assert reader.root.attrs["schema_id"] == "aria_nbv.rollout_zarr_q_invalidity"
    assert reader.root.attrs["schema_version"] == ROLLOUT_ZARR_SCHEMA_VERSION
    assert reader.root.attrs["return_semantics"] == "cumulative_target_root_gain"
    assert reader.root.attrs["manifest_path"] == ROLLOUT_MANIFEST_FILENAME
    assert result.manifest_path.exists()
    assert result.manifest_sha256 == reader.root.attrs["manifest_sha256"]
    assert "writer_config" not in reader.root.attrs
    assert "generation_manifest_json" not in reader.root["metadata"]
    manifest_bundle = reader.manifest()
    manifest = manifest_bundle["manifest"]
    assert manifest["schema_version"] == ROLLOUT_ZARR_SCHEMA_VERSION
    assert manifest["counts"]["rollouts"] == result.num_rollouts
    assert manifest["counts"]["steps"] == result.num_steps
    assert manifest["counts"]["candidates"] == result.num_candidates
    assert manifest["counts"]["candidate_diagnostics"] == result.num_candidates
    assert manifest["counts"]["target_eval_crops"] == 0
    assert manifest["counts"]["q_h_states"] == result.num_steps
    assert manifest["generation"]["invocation"]["mode"] == "programmatic"
    assert manifest["source_coverage"]["scene_counts"] == {"fixture_box": 3}
    assert manifest["source_coverage"]["source_shard_counts"] == {"vin-shard-000000": 3}
    assert "splits" not in reader.root
    assert "sources" in reader.root
    assert "q_h" in reader.root
    assert "selected_depth" in reader.root
    assert "candidate_diagnostics" in reader.root
    assert reader.root.attrs["q_h_view_persisted"] is True
    assert reader.root.attrs["q_h_view_role"] == "training_core_derived_cache"
    assert reader.root.attrs["q_h_chunk_states"] == 64
    assert reader.root.attrs["q_h_state_count"] == result.num_steps
    assert set(reader.array("sources/source_row_id").tolist()) == {0, 1, 2}
    assert set(reader.array("rollouts/source_row_id").tolist()) == {0, 1, 2}
    root_pose = reader.array("rollouts/root_pose_world")
    assert root_pose.shape == (result.num_rollouts, 12)
    assert np.isfinite(root_pose).all()
    assert reader.array("rollouts/root_time_ns").shape == (result.num_rollouts,)
    assert reader.array("rollouts/root_trajectory_index").shape == (result.num_rollouts,)
    assert reader.array("rollouts/root_frame_index").shape == (result.num_rollouts,)
    assert reader.array("targets/target_projected_area_pixels").tolist() == [512.0, 512.0, 512.0]
    assert np.allclose(reader.array("targets/target_effective_support_count"), np.asarray([12.0, 12.0, 12.0]))
    assert reader.array("targets/target_semidense_support_count").tolist() == [7, 7, 7]
    assert reader.array("targets/target_evl_support_count").tolist() == [5, 5, 5]
    assert np.allclose(reader.array("targets/target_visibility_score"), np.asarray([0.8, 0.8, 0.8]))
    assert np.allclose(reader.array("targets/target_support_score"), np.asarray([1.0, 1.0, 1.0]))
    assert np.allclose(reader.array("targets/target_deficit_score"), np.asarray([0.9, 0.9, 0.9]))

    deleted_candidate_arrays = {
        "candidate_valid_mask",
        "padded_mask",
        "heavy_diag_available_mask",
        "selection_entropy",
    }
    assert deleted_candidate_arrays.isdisjoint(set(reader.root["candidates"].array_keys()))
    assert "transition_id" not in set(reader.root["steps"].array_keys())
    assert "transition" not in set(reader.root["dictionaries"].array_keys())

    candidate_valid = reader.array("candidates/actor_action_mask")
    selection_probabilities = reader.array("candidates/selection_probabilities")
    assert np.all(selection_probabilities[~candidate_valid] == 0.0)
    assert np.all(reader.array("candidates/selected_mask") <= candidate_valid)
    assert np.array_equal(
        reader.array("candidate_diagnostics/candidate_row_id"),
        reader.array("candidates/candidate_row_id"),
    )
    assert reader.array("candidates/position_id").shape == (result.num_candidates,)
    assert reader.array("candidates/position_pair_id").shape == (result.num_candidates,)
    assert reader.array("candidates/gaze_variant_id").shape == (result.num_candidates,)
    assert np.all(reader.array("candidates/position_pair_id") == -1)
    assert np.all(reader.array("candidates/gaze_variant_id") == -1)
    assert np.array_equal(
        reader.array("candidate_diagnostics/position_id"),
        reader.array("candidates/position_id"),
    )
    assert reader.array("candidate_diagnostics/path_collision_mask").dtype == np.dtype(np.bool_)
    for diagnostic_name in (
        "mesh_distance_m",
        "path_min_clearance_m",
        "free_space_margin_m",
        "motion_step_length_m",
        "motion_height_delta_m",
        "motion_backward_step_m",
        "motion_yaw_delta_deg",
        "target_distance_m",
        "target_bearing_yaw_deg",
    ):
        values = reader.array(f"candidate_diagnostics/{diagnostic_name}")
        assert values.dtype == np.dtype(np.float32)
        assert values.shape == (result.num_candidates,)
    for diagnostic_name in (
        "view_jitter_yaw_deg",
        "view_jitter_pitch_deg",
        "view_jitter_azimuth_limit_deg",
        "view_jitter_elevation_limit_deg",
        "target_view_angle_deg",
        "target_pixel_margin_px",
    ):
        values = reader.array(f"candidate_diagnostics/{diagnostic_name}")
        assert values.dtype == np.dtype(np.float32)
        assert values.shape == (result.num_candidates,)
    assert reader.array("candidate_diagnostics/view_jitter_is_bounded").dtype == np.dtype(np.bool_)
    assert reader.array("candidate_diagnostics/view_jitter_is_bounded").all()
    assert np.all(reader.array("candidate_diagnostics/view_jitter_yaw_deg") == 0.0)
    assert np.all(reader.array("candidate_diagnostics/view_jitter_pitch_deg") == 0.0)
    assert not reader.array("candidate_diagnostics/target_view_evaluated_mask").any()
    assert not reader.array("candidate_diagnostics/target_in_fov_mask").any()
    assert np.isnan(reader.array("candidate_diagnostics/target_view_angle_deg")).all()
    assert np.isnan(reader.array("candidate_diagnostics/target_pixel_margin_px")).all()
    selected_depth = reader.root["selected_depth"]
    assert selected_depth.attrs["enabled"] is True
    assert selected_depth.attrs["codec"] == "blosc:zstd:clevel=5:bitshuffle"
    assert selected_depth.attrs["renderer"] == "Pytorch3DDepthRenderer"
    assert selected_depth.attrs["source_resolution"] == "exact_output_size"
    assert reader.root.attrs["selected_depth_role"] == "selected_successor_state_history"
    assert reader.root.attrs["selected_depth_znear_m"] == pytest.approx(0.001)
    assert reader.root.attrs["selected_depth_zfar_m"] == pytest.approx(20.0)
    assert selected_depth["depth_m"].dtype == np.dtype(np.float16)
    assert selected_depth["valid_mask"].dtype == np.dtype(np.bool_)
    assert selected_depth["depth_m"].shape == (result.num_steps, 240, 240)
    assert selected_depth["valid_mask"].shape == (result.num_steps, 240, 240)
    assert selected_depth["depth_m"].chunks == (min(16, result.num_steps), 240, 240)
    assert np.array_equal(reader.array("selected_depth/step_row_id"), reader.array("steps/step_row_id"))
    assert np.array_equal(
        reader.array("selected_depth/candidate_row_id"),
        reader.array("steps/selected_candidate_row_id"),
    )
    target_eval_crops = reader.root["target_eval_crops"]
    assert target_eval_crops.attrs["enabled"] is False
    assert target_eval_crops.attrs["retention"] == "disabled_training_core"
    assert target_eval_crops.attrs["role"] == "oracle_eval_only"
    assert target_eval_crops.attrs["coordinate_frame"] == "world"
    assert target_eval_crops.attrs["max_points"] == 50_000
    crop_rows = int(target_eval_crops["crop_row_id"].shape[0])
    assert crop_rows == manifest["counts"]["target_eval_crops"]
    assert target_eval_crops["points_world"].shape == (crop_rows, 50_000, 3)
    assert target_eval_crops["mask"].shape == (crop_rows, 50_000)
    assert crop_rows == 0

    q_h = reader.q_h_view()
    q_h_group = reader.root["q_h"]
    assert q_h_group.attrs["view_role"] == "training_core_derived_cache"
    assert q_h_group.attrs["td_semantics"] == "selected_transition_only"
    assert q_h_group.attrs["reward_metric"] == "target_root_gain"
    assert q_h_group.attrs["return_semantics"] == "cumulative_target_root_gain"
    assert q_h_group.attrs["chunk_states"] == 64
    assert q_h_group.attrs["state_count"] == result.num_steps
    assert {
        "one_step_scene_rri",
        "bootstrap_next_step_row_id",
        "terminal_mask",
        "discount",
    }.isdisjoint(set(q_h_group.array_keys()))
    q_candidate_row_id = q_h["candidate_row_id"]
    valid_action_mask = q_h["valid_action_mask"]
    q_train_mask = q_h["q_train_mask"]

    assert np.array_equal(reader.array("q_h/state_step_row_id"), q_h["state_step_row_id"])
    assert set(q_h["source_row_id"].tolist()) == {0, 1, 2}
    assert q_candidate_row_id.shape == valid_action_mask.shape
    assert np.all(q_train_mask <= valid_action_mask)
    assert "q_target_target_rri" not in q_h
    assert "one_step_target_root_gain" in q_h
    assert "position_id" in q_h
    assert "td_reward" in q_h
    assert np.isfinite(q_h["one_step_target_root_gain"][q_train_mask]).all()
    assert np.isfinite(q_h["td_reward"]).all()
    assert np.all(~valid_action_mask[q_candidate_row_id < 0])
    derived_q_h = reader.q_h_view(discount_gamma=0.5)
    assert np.any(derived_q_h["td_discount"] != q_h["td_discount"])
    for name, actual in q_h.items():
        expected = derived_q_h[name]
        if name == "td_discount":
            continue
        if np.issubdtype(actual.dtype, np.floating):
            assert np.allclose(actual, expected, equal_nan=True)
        else:
            assert np.array_equal(actual, expected)


def test_rollout_zarr_persists_pair_provenance_columns(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=4, seed=17)[:1]
    candidates = _steps(records[0])[0].transition.candidates
    count = int(candidates.mask_valid.numel())
    candidates.position_pair_id = torch.arange(count, dtype=torch.int64)
    candidates.gaze_variant_id = torch.zeros(count, dtype=torch.int64)

    result = write_rollout_zarr_store(
        tmp_path / "paired.zarr",
        records,
        discount_gamma=0.95,
        target_protocol_version="v0_gt_input",
        source_offline_store_version="7",
        split_manifest_hash="fixture-split-manifest",
    )
    reader = RolloutZarrStoreReader(result.store_dir)

    assert reader.array("candidates/position_pair_id")[:count].tolist() == list(range(count))
    assert reader.array("candidates/gaze_variant_id")[:count].tolist() == [0] * count


def test_rollout_zarr_legacy_missing_pair_columns_read_as_sentinels(tmp_path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "legacy.zarr", build_rollout_records(horizon=1, num_samples=4, seed=23)
    )
    root = zarr.open_group(store=zarr.storage.LocalStore(str(result.store_dir)), mode="a")
    del root["candidates/position_pair_id"]
    del root["candidates/gaze_variant_id"]

    reader = RolloutZarrStoreReader(result.store_dir)
    assert reader.array("candidates/position_pair_id").shape == (result.num_candidates,)
    assert reader.array("candidates/gaze_variant_id").shape == (result.num_candidates,)
    assert np.all(reader.array("candidates/position_pair_id") == -1)
    assert np.all(reader.array("candidates/gaze_variant_id") == -1)
    validation = validate_rollout_zarr_store(result.store_dir)
    assert validation.ok, validation.errors


@pytest.mark.parametrize(
    ("field", "values", "match"),
    [
        ("gaze_variant_id", [2, -1, -1, -1], "unsupported values"),
        ("position_pair_id", [0, -1, -1, -1], "share the -1 sentinel"),
    ],
)
def test_rollout_zarr_rejects_malformed_pair_provenance(tmp_path, field, values, match) -> None:
    records = build_rollout_records(horizon=1, num_samples=4, seed=29)
    result = write_rollout_zarr_store(tmp_path / f"invalid-{field}.zarr", records)
    root = zarr.open_group(store=zarr.storage.LocalStore(str(result.store_dir)), mode="a")
    array = root[f"candidates/{field}"]
    malformed = np.full(array.shape, -1, dtype=array.dtype)
    malformed[: len(values)] = np.asarray(values, dtype=array.dtype)
    array[:] = malformed

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any(match in error for error in validation.errors)


def test_rollout_zarr_dense_valid_contract_is_proven_by_persisted_support(tmp_path) -> None:
    records = build_rollout_records(horizon=2, num_samples=8, seed=7)
    result = write_rollout_zarr_store(
        tmp_path / "dense-valid.zarr",
        records,
        oracle_query_mode="dense_valid",
        label_support_semantics="equals_action_on_realized_steps_v1",
    )

    reader = RolloutZarrStoreReader(result.store_dir)
    q_h = reader.q_h_view()
    assert reader.root.attrs["oracle_query_mode"] == "dense_valid"
    assert reader.root.attrs["label_support_semantics"] == "equals_action_on_realized_steps_v1"
    assert np.array_equal(q_h["q_train_mask"], q_h["valid_action_mask"])
    validation = reader.validate()
    assert validation.ok, validation.errors


def test_rollout_zarr_dense_valid_contract_rejects_subset_support(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=25)[:1]
    records[0].lineage.target.target_protocol_version = "v1-observed"
    records[0].lineage.target.target_row_id = 11
    records[0].lineage.target.target_id = "target-invalid"
    records[0].lineage.target.target_invalid_reason_bitset = 1 << 10
    records[0].lineage.target.target_primary_invalid_reason = 10
    records[0].lineage.target.gt_match_status = "unmatched_gt"

    with pytest.raises(ValueError, match="dense-valid.*q_train_mask"):
        write_rollout_zarr_store(
            tmp_path / "invalid-dense-valid.zarr",
            records,
            target_protocol_version="v1-observed",
            oracle_query_mode="dense_valid",
            label_support_semantics="equals_action_on_realized_steps_v1",
        )


def test_rollout_zarr_validation_rejects_dense_support_tampering(tmp_path) -> None:
    records = build_rollout_records(horizon=2, num_samples=8, seed=19)
    result = write_rollout_zarr_store(
        tmp_path / "tampered-dense-valid.zarr",
        records,
        oracle_query_mode="dense_valid",
        label_support_semantics="equals_action_on_realized_steps_v1",
    )

    root = zarr.open_group(result.store_dir, mode="a")
    q_train_mask = np.asarray(root["q_h/q_train_mask"][:], dtype=np.bool_)
    tampered_row = tuple(int(index) for index in np.argwhere(q_train_mask)[0])
    root["q_h/q_train_mask"][tampered_row] = False

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("dense-valid q_train_mask" in error for error in validation.errors)


def test_rollout_zarr_rejects_mixed_query_and_support_profiles(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=31)[:1]

    with pytest.raises(ValueError, match="must be declared together"):
        write_rollout_zarr_store(
            tmp_path / "mixed-profile.zarr",
            records,
            oracle_query_mode="dense_valid",
            label_support_semantics="subset_of_action_v1",
        )


def test_rollout_zarr_rejects_stale_schema_version(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=11)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)

    root = zarr.open_group(result.store_dir, mode="a")
    root.attrs["schema_version"] = "0.8-global-target-rows"

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any(
        "0.8-global-target-rows" in error and ROLLOUT_ZARR_SCHEMA_VERSION in error for error in validation.errors
    )


def test_rollout_zarr_can_persist_target_eval_crops_for_audit_profile(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=33)[:1]

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records, target_eval_crops_enabled=True)
    reader = RolloutZarrStoreReader(result.store_dir)

    target_eval_crops = reader.root["target_eval_crops"]
    assert reader.root.attrs["target_eval_crops_enabled"] is True
    assert target_eval_crops.attrs["enabled"] is True
    assert target_eval_crops.attrs["retention"] == "sampled_audit"
    crop_rows = int(target_eval_crops["crop_row_id"].shape[0])
    assert crop_rows >= result.num_steps
    assert target_eval_crops["points_world"].shape == (crop_rows, 50_000, 3)
    assert target_eval_crops["mask"].shape == (crop_rows, 50_000)
    assert np.array_equal(
        np.asarray(target_eval_crops["mask"]).sum(axis=1).astype(np.int32),
        np.asarray(target_eval_crops["lengths"]),
    )
    assert set(np.asarray(target_eval_crops["source_role_id"]).tolist()) == {0, 1}
    assert np.any(np.asarray(target_eval_crops["candidate_row_id"]) == -1)
    validation = validate_rollout_zarr_store(result.store_dir)
    assert validation.ok, validation.errors


def test_rollout_zarr_validation_rejects_missing_hot_position_id(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=31)[:1]
    for step in _steps(records[0]):
        step.transition.candidates.position_id = None
        step.transition.candidates.extras.clear()
        n = int(step.transition.candidates.mask_valid.numel())
        step.transition.candidates.extras.update(
            {
                "path_collision_mask": torch.zeros(n, dtype=torch.bool),
                "path_collision_applicable_mask": torch.zeros(n, dtype=torch.bool),
                "path_collision_evaluated_mask": torch.zeros(n, dtype=torch.bool),
            }
        )

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)

    assert np.array_equal(
        reader.array("candidate_diagnostics/candidate_row_id"),
        reader.array("candidates/candidate_row_id"),
    )
    assert np.all(reader.array("candidate_diagnostics/position_id") == -1)
    assert np.all(reader.array("candidates/position_id") == -1)
    assert not reader.array("candidate_diagnostics/path_collision_mask").any()
    for name in (
        "mesh_distance_m",
        "path_min_clearance_m",
        "free_space_margin_m",
        "motion_step_length_m",
        "motion_height_delta_m",
        "motion_backward_step_m",
        "motion_yaw_delta_deg",
        "target_distance_m",
        "target_bearing_yaw_deg",
    ):
        assert np.isnan(reader.array(f"candidate_diagnostics/{name}")).all()

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("position_id" in error for error in validation.errors)


def test_rollout_zarr_accepts_legacy_store_without_optional_view_diagnostics(tmp_path) -> None:
    """The optional view bundle does not invalidate already generated stores."""

    records = build_rollout_records(horizon=1, num_samples=6, seed=33)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    writable = zarr.open_group(str(result.store_dir), mode="a")
    group = writable["candidate_diagnostics"]
    for name in (
        "view_jitter_yaw_deg",
        "view_jitter_pitch_deg",
        "view_jitter_azimuth_limit_deg",
        "view_jitter_elevation_limit_deg",
        "view_jitter_is_bounded",
        "target_view_angle_deg",
        "target_pixel_margin_px",
        "target_in_fov_mask",
        "target_view_evaluated_mask",
    ):
        del group[name]

    validation = validate_rollout_zarr_store(result.store_dir)

    assert validation.ok, validation.errors


def test_rollout_zarr_preserves_uncapped_nonzero_view_jitter_residuals(tmp_path) -> None:
    """Zero limits never erase measured residuals or invent a bounded box."""

    records = build_rollout_records(horizon=1, num_samples=6, seed=34)[:1]
    for step in _steps(records[0]):
        count = int(step.transition.candidates.mask_valid.numel())
        step.transition.candidates.extras.update(
            {
                "view_jitter_yaw_deg": torch.linspace(-120.0, 100.0, count),
                "view_jitter_pitch_deg": torch.linspace(-70.0, 60.0, count),
                "view_jitter_azimuth_limit_deg": torch.zeros(count),
                "view_jitter_elevation_limit_deg": torch.zeros(count),
                "view_jitter_is_bounded": torch.zeros(count, dtype=torch.bool),
            }
        )

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)

    assert np.any(np.abs(reader.array("candidate_diagnostics/view_jitter_yaw_deg")) > 1e-3)
    assert np.any(np.abs(reader.array("candidate_diagnostics/view_jitter_pitch_deg")) > 1e-3)
    assert np.all(reader.array("candidate_diagnostics/view_jitter_azimuth_limit_deg") == 0.0)
    assert np.all(reader.array("candidate_diagnostics/view_jitter_elevation_limit_deg") == 0.0)
    assert not reader.array("candidate_diagnostics/view_jitter_is_bounded").any()


def test_rollout_zarr_validates_path_collision_diagnostics_against_invalidity(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=32)[:1]
    step = _steps(records[0])[0]
    collision_shell_index = 0 if int(step.transition.selected_shell_index) != 0 else 1
    candidate_valid = step.transition.candidates.mask_valid.clone()
    candidate_valid[collision_shell_index] = False
    step.transition.candidates.mask_valid = candidate_valid
    path_mask = torch.zeros_like(candidate_valid, dtype=torch.bool)
    path_mask[collision_shell_index] = True
    step.transition.candidates.masks["PathCollisionRule"] = ~path_mask
    step.transition.candidates.extras["path_collision_mask"] = path_mask
    step.transition.candidates.extras["path_collision_applicable_mask"] = torch.ones_like(path_mask)
    step.transition.candidates.extras["path_collision_evaluated_mask"] = torch.ones_like(path_mask)
    _mask_target_eval_candidate_rows(step)

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    validation = validate_rollout_zarr_store(result.store_dir)
    assert validation.ok, validation.errors
    reader = RolloutZarrStoreReader(result.store_dir)
    path_bit = 1 << INVALID_REASON_CODES["PATH_SEGMENT_COLLISION"]
    assert int(reader.array("candidates/invalid_reason_bitset")[collision_shell_index]) & path_bit
    assert (
        int(reader.array("candidates/primary_invalid_reason")[collision_shell_index])
        == INVALID_REASON_CODES["PATH_SEGMENT_COLLISION"]
    )

    root = zarr.open_group(result.store_dir, mode="a")
    root["candidates/invalid_reason_bitset"][collision_shell_index] = np.asarray(1, dtype=np.uint32)
    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("PATH_SEGMENT_COLLISION" in error for error in validation.errors)


def test_rollout_zarr_writer_rejects_missing_collision_diagnostics(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=33)[:1]
    step = _steps(records[0])[0]
    for name in (
        "path_collision_mask",
        "path_collision_applicable_mask",
        "path_collision_evaluated_mask",
    ):
        step.transition.candidates.extras.pop(name, None)
    _mask_target_eval_candidate_rows(step)

    with pytest.raises(ValueError, match="required candidate diagnostics"):
        write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)


def test_rollout_zarr_validation_requires_selected_depth_when_enabled(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=9)[:1]
    for step in _steps(records[0]):
        step.evaluation.evidence.selected_depth_m = None
        step.evaluation.evidence.selected_depth_valid_mask = None

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("selected_depth/step_row_id" in error or "selected-depth" in error for error in validation.errors)


def test_rollout_zarr_validation_reports_mismatched_selected_depth_shapes(tmp_path) -> None:
    """Malformed depth/mask shapes must return structured validation errors, not broadcast exceptions."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=9)[:1],
    )
    root = zarr.open_group(result.store_dir, mode="a")
    valid_mask = root["selected_depth/valid_mask"]
    valid_mask.resize((valid_mask.shape[0], valid_mask.shape[1] - 1, valid_mask.shape[2]))

    validation = validate_rollout_zarr_store(result.store_dir)

    assert not validation.ok
    assert any("selected_depth/valid_mask shape" in error for error in validation.errors)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("zero_focal", "finite positive pinhole focal"),
        ("nonfinite_principal", "finite pixel coordinates"),
        ("wrong_raster_size", "equal the persisted depth raster size"),
        ("valid_below_clip", "within the declared clip range"),
        ("invalid_nonfill", "declared invalid fill value"),
    ),
)
def test_rollout_zarr_validation_rejects_invalid_selected_camera_depth_contract(
    tmp_path, mutation: str, message: str
) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=9)[:1],
    )
    root = zarr.open_group(result.store_dir, mode="a")
    if mutation == "zero_focal":
        root["selected_depth/focal_px"][0, 0] = 0.0
    elif mutation == "nonfinite_principal":
        root["selected_depth/principal_point_px"][0, 0] = np.inf
    elif mutation == "wrong_raster_size":
        root["selected_depth/image_size_hw"][0] = np.array([120, 240], dtype=np.int32)
    elif mutation == "valid_below_clip":
        root["selected_depth/valid_mask"][0, 0, 0] = True
        root["selected_depth/depth_m"][0, 0, 0] = 0.0
    else:
        root["selected_depth/valid_mask"][0, 0, 0] = False
        root["selected_depth/depth_m"][0, 0, 0] = 1.0

    validation = validate_rollout_zarr_store(result.store_dir)

    assert not validation.ok
    assert any(message in error for error in validation.errors)


def test_rollout_zarr_selected_action_td_fields_align_with_step_rows(tmp_path) -> None:
    records = build_rollout_records(horizon=2, num_samples=6, seed=3)
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)
    q_h = reader.q_h_view()

    step_selected = reader.array("steps/selected_candidate_row_id")
    td_selected = q_h["td_selected_candidate_row_id"]
    td_next = q_h["td_next_step_row_id"]
    td_terminal = q_h["td_terminal_mask"]
    td_discount = q_h["td_discount"]

    assert np.array_equal(td_selected, step_selected)
    assert td_next.shape == td_terminal.shape == td_selected.shape
    assert np.any(~td_terminal)
    assert np.any(td_terminal)
    assert np.all(td_discount[td_terminal] == 0.0)
    assert np.all(td_discount[~td_terminal] > 0.0)


def test_rollout_zarr_requires_explicit_target_root_gain_for_q_training(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=11)[:1]
    for step in _steps(records[0]):
        step.evaluation.labels.metrics.clear()

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)
    q_h = reader.q_h_view()

    assert np.isfinite(reader.array("candidates/selection_logits")).any()
    assert np.isnan(reader.array("candidates/target_rri")).all()
    assert np.isnan(reader.array("candidates/target_root_gain")).all()
    assert not reader.array("candidates/q_train_mask").any()
    assert np.isnan(q_h["one_step_target_rri"]).all()
    assert np.isnan(q_h["one_step_target_root_gain"]).all()
    assert not q_h["q_train_mask"].any()


def test_rollout_zarr_never_backfills_scene_rri_from_generic_rri(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=10)[:1]
    for step in _steps(records[0]):
        generic = torch.arange(step.transition.candidates.mask_valid.shape[0], dtype=torch.float32)
        step.evaluation.labels.metrics.clear()
        step.evaluation.labels.metrics.update(rri=generic, target_rri=generic, target_root_gain=generic + 10.0)

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)
    q_h = reader.q_h_view()

    assert np.isfinite(reader.array("candidates/target_rri")).any()
    assert np.isfinite(reader.array("candidates/target_root_gain")).any()
    assert np.isnan(reader.array("candidates/scene_rri")).all()
    assert "one_step_scene_rri" not in q_h


def test_rollout_zarr_qh_reward_uses_target_root_gain_not_target_rri(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=14)[:1]
    for step in _steps(records[0]):
        full = torch.arange(step.transition.candidates.mask_valid.shape[0], dtype=torch.float32)
        step.evaluation.labels.metrics["target_rri"] = full + 1.0
        step.evaluation.labels.metrics["target_root_gain"] = full + 101.0

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)
    q_h = reader.q_h_view()
    selected_index = int(q_h["selected_candidate_index"][0])

    assert q_h["td_reward"][0] == pytest.approx(q_h["one_step_target_root_gain"][0, selected_index])
    assert q_h["td_reward_target_rri"][0] == pytest.approx(q_h["one_step_target_rri"][0, selected_index])
    assert q_h["td_reward"][0] != pytest.approx(q_h["td_reward_target_rri"][0])


def test_rollout_zarr_masks_invalid_candidate_oracle_labels(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=12)[:1]
    step = _steps(records[0])[0]
    invalid_shell_index = 0 if int(step.transition.selected_shell_index) != 0 else 1
    step.transition.candidates.mask_valid[invalid_shell_index] = False
    step.evaluation.labels.metrics["target_rri"] = torch.arange(
        step.transition.candidates.mask_valid.shape[0], dtype=torch.float32
    )
    step.evaluation.labels.metrics["target_root_gain"] = (
        torch.arange(step.transition.candidates.mask_valid.shape[0], dtype=torch.float32) + 10.0
    )
    valid_count = int(step.transition.candidates.mask_valid.sum().item())
    step.evaluation.evidence.target_eval_candidate_points_world = (
        step.evaluation.evidence.target_eval_candidate_points_world[:valid_count]
    )
    step.evaluation.evidence.target_eval_candidate_point_lengths = (
        step.evaluation.evidence.target_eval_candidate_point_lengths[:valid_count]
    )

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)
    q_h = reader.q_h_view()

    candidate_valid = reader.array("candidates/actor_action_mask")
    assert not candidate_valid[invalid_shell_index]
    assert np.isnan(reader.array("candidates/target_rri")[invalid_shell_index])
    assert np.isnan(reader.array("candidates/target_root_gain")[invalid_shell_index])
    assert not reader.array("candidates/q_train_mask")[invalid_shell_index]
    assert np.isnan(q_h["one_step_target_rri"][0, invalid_shell_index])
    assert np.isnan(q_h["one_step_target_root_gain"][0, invalid_shell_index])
    assert not q_h["q_train_mask"][0, invalid_shell_index]


def test_rollout_zarr_preserves_multi_target_identity_in_qh_view(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=13)[:2]
    records[0].lineage.target.target_row_id = 7
    records[0].lineage.target.target_source_index = None
    records[0].lineage.target.target_id = "target-a"
    records[0].lineage.target.target_selection_policy = "greedy_top_k"
    records[0].lineage.target.target_selection_rank = 0
    records[0].lineage.target.target_selection_score = 0.75
    records[0].lineage.target.target_invalid_reason_bitset = 1
    records[0].lineage.target.target_primary_invalid_reason = 0
    records[0].lineage.target.target_reason_code_version = TARGET_INVALID_REASON_VERSION
    records[0].lineage.target.matched_gt_target_row_id = 70
    records[0].lineage.target.matched_gt_target_id = "gt-target-a"
    records[0].lineage.target.gt_match_iou = 0.8
    records[0].lineage.target.gt_match_score = 0.8
    records[0].lineage.target.gt_match_status = "matched"
    records[1].lineage.target.target_row_id = 9
    records[1].lineage.target.target_source_index = None
    records[1].lineage.target.target_id = "target-b"
    records[1].lineage.target.target_selection_policy = "greedy_top_k"
    records[1].lineage.target.target_selection_rank = 1
    records[1].lineage.target.target_selection_score = 0.5
    records[1].lineage.target.target_invalid_reason_bitset = 1
    records[1].lineage.target.target_primary_invalid_reason = 0
    records[1].lineage.target.target_reason_code_version = TARGET_INVALID_REASON_VERSION
    records[1].lineage.target.matched_gt_target_row_id = None
    records[1].lineage.target.matched_gt_target_id = None
    records[1].lineage.target.gt_match_status = "unmatched_gt"

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)
    q_h = reader.q_h_view()

    target_rows = reader.array("targets/target_row_id")
    target_names = _json_list(reader, "dictionaries/target")
    target_name_ids = reader.array("targets/target_id")

    assert set(target_rows.tolist()) == {0, 1}
    assert {target_names[int(index)] for index in target_name_ids.tolist()} == {"target-a", "target-b"}
    assert set(reader.array("rollouts/target_row_id").tolist()) == {0, 1}
    assert set(q_h["target_row_id"].tolist()) == {0, 1}
    assert reader.array("targets/target_source_index").tolist() == [7, 9]
    assert reader.array("targets/target_selection_rank").tolist() == [0, 1]
    assert np.allclose(reader.array("targets/target_selection_score"), np.asarray([0.75, 0.5], dtype=np.float32))
    assert reader.array("targets/matched_gt_target_row_id").tolist() == [70, -1]
    assert reader.array("targets/gt_label_valid_mask").tolist() == [True, False]
    config_names = _json_list(reader, "dictionaries/config")
    reason_version_ids = reader.array("targets/target_reason_code_version_id")
    assert {config_names[int(index)] for index in reason_version_ids.tolist()} == {TARGET_INVALID_REASON_VERSION}
    match_status = _json_list(reader, "dictionaries/target_match_status")
    status_ids = reader.array("targets/gt_match_status_id")
    assert [match_status[int(index)] for index in status_ids.tolist()] == ["matched", "unmatched_gt"]


def test_rollout_zarr_globalizes_selector_local_target_rows(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=14)[:2]
    for source_row_id, record in enumerate(records):
        record.lineage.source.source_row_id = source_row_id
        record.lineage.source.source_sample_index = source_row_id
        record.lineage.source.snippet_id = f"snippet-{source_row_id}"
        record.lineage.target.target_row_id = 0
        record.lineage.target.target_source_index = 0
        record.lineage.target.target_id = f"scene:snippet-{source_row_id}:target-local-0"
        record.lineage.target.matched_gt_target_id = f"scene:snippet-{source_row_id}:gt-local-0"
        record.lineage.target.matched_gt_target_row_id = 0

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)

    assert reader.array("targets/target_row_id").tolist() == [0, 1]
    assert reader.array("targets/target_source_index").tolist() == [0, 0]
    assert reader.array("rollouts/target_row_id").tolist() == [0, 1]
    target_names = _json_list(reader, "dictionaries/target")
    target_name_ids = reader.array("targets/target_id")
    assert [target_names[int(index)] for index in target_name_ids.tolist()] == [
        "scene:snippet-0:target-local-0",
        "scene:snippet-1:target-local-0",
    ]

    validation = validate_rollout_zarr_store(result.store_dir)
    assert validation.ok, validation.errors


def test_rollout_zarr_validation_rejects_target_rows_shared_across_sources(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=15)[:2]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)

    root = zarr.open_group(result.store_dir, mode="a")
    root["rollouts/target_row_id"][...] = np.asarray([0, 0], dtype=np.int64)

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("multiple source_row_id" in error for error in validation.errors)


def test_rollout_zarr_relative_pose_root_is_pose_transform(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=17)[:1]
    records[0].evaluated.result.root_pose_world = PoseTW(
        torch.tensor(
            [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 2.0, 3.0],
            dtype=torch.float32,
        )
    )

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    reader = RolloutZarrStoreReader(result.store_dir)

    pose = reader.array("candidates/pose_world_cam")[0]
    relative = reader.array("candidates/pose_relative_root")[0]
    stored_root = reader.array("rollouts/root_pose_world")[0]
    root_pose = records[0].evaluated.result.root_pose_world.tensor().numpy()
    expected = (
        records[0].evaluated.result.root_pose_world.inverse().compose(PoseTW(torch.as_tensor(pose))).tensor().numpy()
    )

    assert np.allclose(stored_root, root_pose, atol=1e-5)
    assert np.allclose(relative, expected, atol=1e-5)
    assert not np.allclose(relative, pose - root_pose, atol=1e-5)


def test_rollout_zarr_records_per_rollout_lineage_and_split(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=19)[:1]
    lineage = records[0].lineage
    lineage.source.split = "train"
    lineage.source.source_cache_version = "source-cache-v2"
    lineage.source.source_offline_store_manifest_hash = "source-manifest"
    lineage.source.split_manifest_hash = "split-manifest"
    lineage.policy.candidate_config_hash = "candidate-cfg"
    lineage.policy.oracle_config_hash = "oracle-cfg"
    lineage.policy.rollout_config_hash = "rollout-cfg"
    lineage.policy.model_checkpoint_hash = "model-ckpt"
    lineage.policy.branch_schedule_id = "branch-schedule"
    lineage.policy.reason_code_version = INVALID_REASON_VERSION
    lineage.policy.selection_rng_state_hash = "rng-state"
    lineage.target.target_protocol_version = "v1-observed"
    lineage.target.target_source = "detected_obbs"
    lineage.target.target_crop_policy = TARGET_CROP_POLICY_GT_OBB_ORIENTED_ANY_VERTEX_V1
    lineage.target.target_row_id = 5
    lineage.target.target_id = "target"
    lineage.target.target_selection_policy = "greedy_top_k"
    lineage.target.target_invalid_reason_bitset = 1
    lineage.target.target_primary_invalid_reason = 0
    lineage.target.target_reason_code_version = TARGET_INVALID_REASON_VERSION
    lineage.target.matched_gt_target_row_id = 50
    lineage.target.matched_gt_target_id = "gt-target"
    lineage.target.gt_match_status = "matched"
    for step in _steps(records[0]):
        n = int(step.transition.candidates.mask_valid.shape[0])
        step.transition.candidates.strategy_id = torch.arange(n, dtype=torch.int64) % 4
        step.transition.candidates.position_id = torch.arange(n, dtype=torch.int64) % 3
        step.transition.candidates.mixture_id = torch.arange(n, dtype=torch.int64) % 2
        step.transition.candidates.sampler_probability = torch.full((n,), 1.0 / float(n), dtype=torch.float32)

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        records,
        target_protocol_version="v1-observed",
        source_offline_store_version="vin-offline-v1",
        split_manifest_hash="split-manifest",
    )
    reader = RolloutZarrStoreReader(result.store_dir)

    split_names = _json_list(reader, "dictionaries/split")
    assert "splits" not in reader.root
    assert split_names[int(reader.array("rollouts/split_id")[0])] == "train"
    assert np.array_equal(reader.array("rollouts/source_row_id"), reader.array("sources/source_row_id"))
    assert np.array_equal(reader.array("lineage/rollout_row_id"), reader.array("rollouts/rollout_row_id"))
    for name in (
        "candidate_config_id",
        "oracle_config_id",
        "rollout_config_id",
        "model_checkpoint_id",
        "branch_schedule_id",
        "target_protocol_version_id",
        "target_crop_policy_id",
        "reason_code_version_id",
        "selection_rng_state_hash_id",
    ):
        assert int(reader.array(f"lineage/{name}")[0]) >= 0
    for name in ("source_cache_version_id", "source_offline_store_manifest_hash_id", "split_manifest_hash_id"):
        assert int(reader.array(f"sources/{name}")[0]) >= 0
    source_shards = _json_list(reader, "dictionaries/source_shard")
    assert source_shards[int(reader.array("sources/source_shard_id")[0])] == "vin-shard-000000"
    assert int(reader.array("sources/source_shard_row")[0]) >= 0
    for rollout_owned_name in ("root_pose_world", "policy_id", "target_row_id"):
        assert rollout_owned_name not in reader.root["lineage"]
    for target_owned_name in ("target_selection_policy_id", "matched_gt_target_row_id", "gt_match_status_id"):
        assert target_owned_name not in reader.root["lineage"]
        assert target_owned_name in reader.root["targets"]
    validation = validate_rollout_zarr_store(result.store_dir)
    assert validation.ok, validation.errors


def test_rollout_zarr_rejects_in_range_v1_target_source_even_when_masks_are_false(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=38)[:1]
    records[0].lineage.target.target_protocol_version = "v1-observed"
    records[0].lineage.target.target_source = "detected_obbs"
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records, target_protocol_version="v1-observed")

    root = zarr.open_group(result.store_dir, mode="a")
    encoded = np.frombuffer(json.dumps(["fabricated_actor"]).encode("utf-8"), dtype=np.uint8)
    root["dictionaries/target_source"].resize((encoded.size,))
    root["dictionaries/target_source"][...] = encoded
    root["targets/target_valid_mask"][...] = False
    root["targets/target_invalid_reason_bitset"][...] = 0

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("incompatible with v1_observed" in error for error in validation.errors)


def test_rollout_zarr_rejects_in_range_empty_v0_target_source_even_when_masks_are_false(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=41)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records, target_protocol_version="v0_gt_input")

    root = zarr.open_group(result.store_dir, mode="a")
    encoded = np.frombuffer(json.dumps([""]).encode("utf-8"), dtype=np.uint8)
    root["dictionaries/target_source"].resize((encoded.size,))
    root["dictionaries/target_source"][...] = encoded
    root["targets/target_valid_mask"][...] = False
    root["targets/target_invalid_reason_bitset"][...] = 0
    root["candidates/q_train_mask"][...] = False

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("incompatible with v0_gt_input" in error for error in validation.errors)


def test_rollout_zarr_accepts_admitted_v1_target_source(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=39)[:1]
    records[0].lineage.target.target_protocol_version = "v1-observed"
    records[0].lineage.target.target_source = "detected_obbs"
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records, target_protocol_version="v1-observed")

    validation = validate_rollout_zarr_store(result.store_dir)
    assert validation.ok, validation.errors


def test_rollout_zarr_preserves_v0_oracle_compatible_target_source(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=40)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records, target_protocol_version="v0_gt_input")

    validation = validate_rollout_zarr_store(result.store_dir)
    assert validation.ok, validation.errors


def test_rollout_zarr_rejects_mixed_split_shards(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=20)[:2]
    records[0].lineage.source.split = "train"
    records[1].lineage.source.split = "val"

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("exactly one split" in error for error in validation.errors)


def test_rollout_zarr_validation_requires_vin_source_shard_lineage(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=23)[:1]
    records[0].lineage.source.source_shard_id = None
    records[0].lineage.source.source_shard_row = -1

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("source_shard_id" in error for error in validation.errors)
    assert any("source_shard_row" in error for error in validation.errors)


def test_rollout_zarr_rejects_conflicting_source_row_lineage(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=24)[:2]
    records[0].lineage.source.source_row_id = 0
    records[1].lineage.source.source_row_id = 0
    records[1].lineage.source.source_sample_key = "different-source-row"
    records[1].lineage.source.source_shard_id = "vin-shard-999999"
    records[1].lineage.source.source_shard_row = 99

    with pytest.raises(ValueError, match="Conflicting source lineage"):
        write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)


def test_rollout_zarr_preserves_candidate_mixture_provenance_for_real_stores(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=21)[:1]
    lineage = records[0].lineage
    lineage.source.split = "train"
    lineage.source.source_cache_version = "source-cache-v7"
    lineage.source.source_offline_store_manifest_hash = "source-manifest"
    lineage.source.split_manifest_hash = "split-manifest"
    lineage.policy.candidate_config_hash = "candidate-cfg"
    lineage.policy.oracle_config_hash = "oracle-cfg"
    lineage.policy.rollout_config_hash = "rollout-cfg"
    lineage.policy.reason_code_version = INVALID_REASON_VERSION
    lineage.policy.selection_rng_state_hash = "rng-state"
    lineage.target.target_protocol_version = "v1-observed"
    lineage.target.target_source = "detected_obbs"
    lineage.target.target_crop_policy = TARGET_CROP_POLICY_GT_OBB_ORIENTED_ANY_VERTEX_V1
    lineage.target.target_row_id = 3
    lineage.target.target_id = "target"
    lineage.target.target_selection_policy = "greedy_top_k"
    lineage.target.target_invalid_reason_bitset = 1
    lineage.target.target_primary_invalid_reason = 0
    lineage.target.target_reason_code_version = TARGET_INVALID_REASON_VERSION
    lineage.target.matched_gt_target_row_id = 30
    lineage.target.matched_gt_target_id = "gt-target"
    lineage.target.gt_match_status = "matched"
    for step in _steps(records[0]):
        n = int(step.transition.candidates.mask_valid.shape[0])
        step.transition.candidates.strategy_id = torch.arange(n, dtype=torch.int64) % 4
        step.transition.candidates.mixture_id = torch.arange(n, dtype=torch.int64) % 2
        step.transition.candidates.sampler_probability = torch.full((n,), 1.0 / float(n), dtype=torch.float32)

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        records,
        target_protocol_version="v1-observed",
        source_offline_store_version="7",
        split_manifest_hash="split-manifest",
    )
    reader = RolloutZarrStoreReader(result.store_dir)

    actor_rows = reader.array("candidates/actor_action_mask")
    assert np.all(reader.array("candidates/strategy_id")[actor_rows] >= 0)
    assert np.all(reader.array("candidates/position_id")[actor_rows] >= 0)
    assert np.all(reader.array("candidates/mixture_id")[actor_rows] >= 0)
    assert np.isfinite(reader.array("candidates/sampler_probability")[actor_rows]).all()

    validation = validate_rollout_zarr_store(result.store_dir)
    assert validation.ok, validation.errors


def test_rollout_zarr_blocks_q_training_for_target_invalid_records(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=25)[:1]
    records[0].lineage.target.target_protocol_version = "v1-observed"
    records[0].lineage.target.target_row_id = 11
    records[0].lineage.target.target_id = "target-invalid"
    records[0].lineage.target.target_invalid_reason_bitset = 1 << 10
    records[0].lineage.target.target_primary_invalid_reason = 10
    records[0].lineage.target.gt_match_status = "unmatched_gt"

    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records, target_protocol_version="v1-observed")
    reader = RolloutZarrStoreReader(result.store_dir)
    q_h = reader.q_h_view()

    assert reader.array("candidates/oracle_label_mask").any()
    assert not reader.array("candidates/q_train_mask").any()
    assert not q_h["q_train_mask"].any()


def test_rollout_zarr_blocks_q_training_when_v1_target_reason_is_missing(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=26)[:1]
    target = records[0].lineage.target
    target.target_protocol_version = "v1_observed"
    target.target_source = "detected_obbs"
    target.target_invalid_reason_bitset = None
    target.gt_match_status = "admitted"
    target.gt_match_iou = 0.7

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        records,
        target_protocol_version="v1_observed",
    )
    reader = RolloutZarrStoreReader(result.store_dir)

    assert reader.array("targets/target_invalid_reason_bitset").tolist() == [0]
    assert reader.array("targets/target_valid_mask").tolist() == [False]
    assert reader.array("targets/gt_label_valid_mask").tolist() == [False]
    assert not reader.array("candidates/q_train_mask").any()
    validation = validate_rollout_zarr_store(result.store_dir)
    assert validation.ok, validation.errors


def test_rollout_zarr_preserves_v0_missing_target_reason_admission(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=27)[:1]
    records[0].lineage.target.target_invalid_reason_bitset = None

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        records,
        target_protocol_version="v0_gt_input",
    )
    reader = RolloutZarrStoreReader(result.store_dir)

    assert reader.array("targets/target_invalid_reason_bitset").tolist() == [1]
    assert reader.array("targets/target_valid_mask").tolist() == [True]
    assert reader.array("targets/gt_label_valid_mask").tolist() == [True]
    assert reader.array("candidates/q_train_mask").any()
    validation = validate_rollout_zarr_store(result.store_dir)
    assert validation.ok, validation.errors


def test_rollout_zarr_rejects_missing_root_lineage(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=23)[:1]

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        records,
        target_protocol_version="v1-observed",
        source_offline_store_version="",
    )

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("source_offline_store_version" in error for error in validation.errors)


def test_rollout_zarr_validation_requires_top_level_manifest(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=29)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    result.manifest_path.unlink()

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("manifest" in error for error in validation.errors)


def test_rollout_zarr_validation_rejects_manifest_hash_mismatch(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=31)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    payload["counts"]["rollouts"] = 999
    result.manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    validation = validate_rollout_zarr_store(result.store_dir)
    assert not validation.ok
    assert any("manifest hash" in error for error in validation.errors)


def test_rollouts_info_cli_prints_manifest_without_validation(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=37)[:1]
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    capsys.readouterr()

    rollouts_info_main(["--store", str(result.store_dir), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert payload["manifest"]["schema_version"] == ROLLOUT_ZARR_SCHEMA_VERSION
    assert payload["manifest"]["source_coverage"]["num_source_rows"] == 1
    assert "validation" not in payload


def test_rollout_manifest_preserves_cli_toml_and_resolved_config(tmp_path) -> None:
    records = build_rollout_records(horizon=1, num_samples=6, seed=41)[:1]
    config_path = tmp_path / "build_rollouts.toml"
    raw_toml = "max_samples = 1\n"
    config_path.write_text(raw_toml, encoding="utf-8")
    writer_config = RolloutZarrStoreConfig(store_dir=tmp_path / "rollouts.zarr")

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        records,
        manifest_context=RolloutStoreManifestContext.from_cli(
            writer_config=writer_config,
            argv=["nbv-build-rollouts", "--config-path", str(config_path)],
            config_path=config_path,
        ),
    )
    manifest = RolloutZarrStoreReader(result.store_dir).manifest()["manifest"]

    invocation = manifest["generation"]["invocation"]
    assert invocation["mode"] == "cli"
    assert invocation["raw_toml_text"] == raw_toml
    assert invocation["raw_toml_sha256"]
    assert manifest["generation"]["writer_config"]["store_dir"].endswith("rollouts.zarr")
    assert manifest["generation"]["runtime"]["git"]["available"] in {True, False}
