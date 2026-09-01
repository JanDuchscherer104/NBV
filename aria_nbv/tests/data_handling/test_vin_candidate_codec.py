"""Contract tests for the optional VIN candidate-facts audit codec."""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from aria_nbv.data_handling.vin_store.candidate_codec import (
    VIN_CANDIDATE_FACTS_CODEC_VERSION,
    VinCandidateCriterionFacts,
    VinCandidateFacts,
)


def _facts() -> VinCandidateFacts:
    return VinCandidateFacts(
        codec_version=VIN_CANDIDATE_FACTS_CODEC_VERSION,
        attempted_count=3,
        valid_count=2,
        action_count=1,
        labeled_prefix_count=2,
        valid_indices=(0, 2),
        action_indices=(2,),
        semantic_group_id=("group",) * 3,
        center_family_id=("forward_local",) * 3,
        gaze_family_id=("directional",) * 3,
        candidate_family_id=("family",) * 3,
        center_id=(0, 1, 2),
        position_pair_id=(-1, -1, -1),
        gaze_variant_id=(-1, -1, -1),
        attempt_round_id=(0, 0, 0),
        draw_id=(0, 1, 2),
        proposal_key=("key:0", "key:1", "key:2"),
        target_frame_identity=("", "", ""),
        target_frame_availability=("unavailable",) * 3,
        criteria=(),
        candidate_program_hash="1" * 64,
        request_binding_hash="2" * 64,
        candidate_substream_revision="shipped_mixture_seed_paths_v1",
        action_order_revision="ordered_hard_valid_v1",
        completion_mode="fixed_attempts",
        proposal_key_revision=None,
        proposal_replica=None,
        legacy_candidate_config_hash="legacy-config",
    )


def _criterion(cumulative_valid: tuple[bool, ...]) -> VinCandidateCriterionFacts:
    n = len(cumulative_valid)
    return VinCandidateCriterionFacts(
        criterion_id="criterion",
        cumulative_valid=cumulative_valid,
        local_available=(True,) * n,
        applicable=(True,) * n,
        evaluated=(True,) * n,
        passed=cumulative_valid,
        reason_code=tuple(0 if value else 1 for value in cumulative_valid),
        margin=(0.0,) * n,
        source_role=(1,) * n,
        reason_revision="candidate_admission_v1",
        source_role_revision="candidate_admission_v1",
    )


def test_vin_candidate_codec_roundtrips_exact_declared_record() -> None:
    facts = _facts()
    decoded = VinCandidateFacts.from_record(facts.to_record())

    assert decoded == facts
    assert decoded.labeled_prefix_count == 2
    assert decoded.action_indices == (2,)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("valid_count", True, "non-negative integer"),
        ("valid_indices", (0.0, 2), "exact integers"),
        ("action_indices", (1,), "subset"),
        ("candidate_substream_revision", "future", "unsupported"),
        ("action_order_revision", "future", "unsupported"),
        ("semantic_group_id", (7, "group", "group"), "nonempty"),
        ("target_frame_identity", ("frame", "", ""), "agree with row availability"),
        ("proposal_key_revision", "", "present together"),
    ],
)
def test_vin_candidate_codec_rejects_runtime_type_and_revision_drift(field: str, value: object, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        replace(_facts(), **{field: value})


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("center_id", (0, -1, 2), "non-negative"),
        ("attempt_round_id", (0, -1, 0), "non-negative"),
        ("draw_id", (0, 1, -1), "non-negative"),
        ("position_pair_id", (-2, -1, -1), "exactly -1"),
        ("gaze_variant_id", (-2, -1, -1), "exactly -1"),
        ("proposal_replica", -2, "present together"),
    ],
)
def test_vin_candidate_codec_rejects_invalid_lineage_sentinels(field: str, value: object, match: str) -> None:
    updates: dict[str, object] = {field: value}
    if field == "proposal_replica":
        updates["proposal_key_revision"] = None
    with pytest.raises(ValueError, match=match):
        replace(_facts(), **updates)


def test_vin_candidate_codec_rejects_nonmonotone_and_terminal_admission_masks() -> None:
    first = replace(_criterion((False, False, False)), criterion_id="first")
    second = replace(_criterion((True, False, True)), criterion_id="second")
    with pytest.raises(ValueError, match="monotone"):
        replace(_facts(), criteria=(first, second))

    terminal = _criterion((True, True, True))
    with pytest.raises(ValueError, match="terminal cumulative admission mask"):
        replace(_facts(), criteria=(terminal,))

    cumulative = _criterion((True, False, True))
    contradicted = replace(
        cumulative,
        passed=(False, False, True),
        reason_code=(1, 1, 0),
    )
    with pytest.raises(ValueError, match="contradicts local criterion evidence"):
        replace(_facts(), criteria=(contradicted,))


def test_vin_candidate_codec_has_no_rollout_dependency() -> None:
    source = Path(__file__).parents[2] / "aria_nbv/data_handling/vin_store/candidate_codec.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imports = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} | {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    }
    assert not any("rollouts" in name for name in imports)


def test_public_candidate_persistence_dto_fields_have_inline_contract_docs() -> None:
    package = Path(__file__).resolve().parents[2] / "aria_nbv"
    expected_classes = {
        package / "data_handling/vin_store/candidate_codec.py": {
            "VinCandidateCriterionFacts",
            "VinCandidateFacts",
        },
        package / "rollouts/trace.py": {"CandidateCriterionTrace", "CandidateTraceFacts"},
        package / "rollouts/read_model.py": {
            "StoredCandidateCriterion",
            "StoredCandidateCodecFacts",
            "StoredCandidateIdentity",
        },
    }
    missing: list[str] = []
    for source_path, class_names in expected_classes.items():
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
        for class_name in class_names:
            body = classes[class_name].body
            for index, statement in enumerate(body):
                if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                    continue
                following = body[index + 1] if index + 1 < len(body) else None
                documented = (
                    isinstance(following, ast.Expr)
                    and isinstance(following.value, ast.Constant)
                    and isinstance(following.value.value, str)
                    and bool(following.value.value.strip())
                )
                if not documented:
                    missing.append(f"{source_path.name}:{class_name}.{statement.target.id}")
    assert not missing


@pytest.mark.parametrize(("reason", "source"), [(999, 1), (0, 999)])
def test_vin_candidate_criterion_rejects_undeclared_codes(reason: int, source: int) -> None:
    with pytest.raises(ValueError, match="undeclared codes"):
        VinCandidateCriterionFacts(
            criterion_id="criterion",
            cumulative_valid=(True,),
            local_available=(True,),
            applicable=(True,),
            evaluated=(True,),
            passed=(reason == 0,),
            reason_code=(reason,),
            margin=(0.0,),
            source_role=(source,),
            reason_revision="candidate_admission_v1",
            source_role_revision="candidate_admission_v1",
        )


def test_vin_candidate_criterion_rejects_passed_reason_mismatch() -> None:
    with pytest.raises(ValueError, match="PASSED reason code exactly"):
        replace(_criterion((True,)), reason_code=(1,))
    with pytest.raises(ValueError, match="unevaluated rows must use the UNAVAILABLE reason"):
        replace(_criterion((False,)), evaluated=(False,), passed=(False,), reason_code=(1,))
