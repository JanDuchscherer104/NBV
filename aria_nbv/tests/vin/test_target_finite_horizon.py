"""Contracts for the production finite-horizon Q_H scorer."""

# ruff: noqa: S101

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest
import torch
from efm3d.aria.camera import CameraTW
from efm3d.aria.pose import PoseTW

from aria_nbv.data_handling.qh_data import QhActorTensors, collate_qh_chains
from aria_nbv.data_handling.qh_data.views import QhSelectedObservationPrefix, QhStaticContext
from aria_nbv.utils.fingerprints import stable_config_hash
from aria_nbv.vin.encoders import LearnableFourierFeaturesConfig, R6dLffPoseEncoderConfig
from aria_nbv.vin.models.target_finite_horizon import (
    TargetFiniteHorizonScorer,
    TargetFiniteHorizonScorerConfig,
)
from aria_nbv.vin.modules.qh_history_encoders import (
    QhCausalTransformerHistoryEncoderConfig,
    QhMeanPoolHistoryEncoderConfig,
)
from aria_nbv.vin.modules.qh_scene_encoders import (
    QhLegacySelectedSurfacePointSceneEncoderConfig,
    QhSelectedSurfacePointSceneEncoderConfig,
)
from aria_nbv.vin.modules.qh_state_fusion import (
    QhCrossAttentionStateFusionConfig,
    QhIndependentMlpStateFusionConfig,
)
from aria_nbv.vin.modules.qh_value_decoders import (
    QhCoralValueDecoderConfig,
    QhPredeclaredPhysicalCoralSupport,
)
from tests.data_handling.test_qh import _chain, _snippet

_FLOAT32_GOLDEN_ATOL = 1e-4
"""Cross-backend tolerance for frozen scalar-output smoke values only."""


def _actor(*, steps: int = 3, width: int = 4) -> QhActorTensors:
    chain = _chain(steps=steps, width=width)
    context = QhStaticContext(
        vin_snippet=_snippet(steps),
        t_world_voxel=PoseTW(),
        voxel_extent=torch.tensor([-1.0, 1.0, -1.0, 1.0, -1.0, 1.0]),
        occ_pr=torch.linspace(0.1, 0.8, 8).reshape(1, 2, 2, 2),
        occ_input=torch.linspace(0.2, 0.9, 8).reshape(1, 2, 2, 2),
        free_input=torch.linspace(0.9, 0.2, 8).reshape(1, 2, 2, 2),
        counts=torch.arange(8, dtype=torch.int64).reshape(2, 2, 2),
        cent_pr=torch.linspace(0.3, 1.0, 8).reshape(1, 2, 2, 2),
        pts_world=torch.arange(24, dtype=torch.float32).reshape(8, 3) / 10.0,
        evl_presence=torch.ones(8, dtype=torch.bool),
    )
    chain = replace(chain, actor=replace(chain.actor, static_context=context))
    return collate_qh_chains([chain]).actor


def _scorer() -> TargetFiniteHorizonScorer:
    torch.manual_seed(11)
    scorer = TargetFiniteHorizonScorerConfig(
        hidden_dim=32,
        dropout=0.0,
        max_horizon=4,
    ).setup_target()
    scorer.eval()
    return scorer


def _cfplus_actor(*, steps: int = 3, width: int = 4) -> QhActorTensors:
    """Return the CF+ H0 control actor with one exact causal carrier."""

    actor = _actor(steps=steps, width=width)
    batch_size = actor.step_mask.shape[0]
    history_pose = PoseTW().tensor().reshape(1, 1, 1, 12).expand(batch_size, steps, steps, -1).clone()
    actor = replace(actor, history_pose_relative_root=PoseTW(history_pose))
    depth = (
        1.0
        + torch.arange(
            batch_size * steps * steps * 6,
            dtype=torch.float32,
        ).reshape(batch_size, steps, steps, 2, 3)
        / 20.0
    )
    camera_row = CameraTW.from_parameters(
        width=torch.tensor([3.0]),
        height=torch.tensor([2.0]),
        fx=torch.tensor([4.0]),
        fy=torch.tensor([4.0]),
        cx=torch.tensor([1.5]),
        cy=torch.tensor([1.0]),
        gain=torch.tensor([0.0]),
        exposure_s=torch.tensor([0.0]),
        valid_radiusx=torch.tensor([3.0]),
        valid_radiusy=torch.tensor([2.0]),
        T_camera_rig=PoseTW().tensor().reshape(1, 12),
        dist_params=torch.empty((1, 0)),
    ).tensor()
    prefix = QhSelectedObservationPrefix(
        depth_m=depth.to(torch.float16),
        valid_mask=torch.ones_like(depth, dtype=torch.bool),
        camera=CameraTW(camera_row.reshape(1, 1, 1, 22).expand(batch_size, steps, steps, -1).clone()),
        camera_pose_relative_root=PoseTW(history_pose.clone()),
        prefix_mask=actor.history_mask.clone(),
    )
    return replace(actor, selected_observation_prefix=prefix)


def _cfplus_scorer() -> TargetFiniteHorizonScorer:
    """Return a deterministic privileged H0 scorer that ignores CF-GT values."""

    torch.manual_seed(11)
    scorer = TargetFiniteHorizonScorerConfig(
        hidden_dim=32,
        dropout=0.0,
        max_horizon=4,
        experiment_profile="qh_cfplus_gt_depth_v1",
    ).setup_target()
    scorer.eval()
    return scorer


def _s1_scorer(*, view_chunk_size: int = 16) -> TargetFiniteHorizonScorer:
    """Return the fixed-width selected-surface S1 scorer."""

    torch.manual_seed(11)
    scorer = TargetFiniteHorizonScorerConfig(
        hidden_dim=32,
        dropout=0.0,
        max_horizon=4,
        experiment_profile="qh_cfplus_gt_depth_v1",
        representation_semantics="root_moments_plus_selected_surface_points_identity_start_v1",
        scene_encoder=QhSelectedSurfacePointSceneEncoderConfig(
            pixel_stride=1,
            view_chunk_size=view_chunk_size,
            point_hidden_dim=16,
            coordinate_scale_m=2.0,
        ),
    ).setup_target()
    scorer.eval()
    return scorer


def _coral_scorer() -> TargetFiniteHorizonScorer:
    """Return a deterministic scorer with a three-class ordinal value head."""

    torch.manual_seed(11)
    scorer = TargetFiniteHorizonScorerConfig(
        hidden_dim=32,
        dropout=0.0,
        max_horizon=4,
        value_decoder=QhCoralValueDecoderConfig(
            support=QhPredeclaredPhysicalCoralSupport.create(
                source_population_digest="population-v1",
                ordered_input_digest="physical-rule-inputs-v1",
                physical_rule="symmetric-root-gain-support-v1",
                bin_edges=(-0.5, 0.5),
                bin_values=(-1.0, 0.0, 1.0),
            ),
            preinit_bias=False,
        ),
    ).setup_target()
    scorer.eval()
    return scorer


def _ordered_history_scorer() -> TargetFiniteHorizonScorer:
    """Return a deterministic A1 scorer whose only new factor is H1 history."""

    torch.manual_seed(11)
    scorer = TargetFiniteHorizonScorerConfig(
        hidden_dim=32,
        dropout=0.0,
        max_horizon=4,
        history_encoder=QhCausalTransformerHistoryEncoderConfig(attention_heads=4),
    ).setup_target()
    scorer.eval()
    return scorer


def test_qh_scorer_output_matches_actor_candidate_axes_and_is_deterministic() -> None:
    actor = _actor()
    scorer = _scorer()

    first = scorer(actor)
    second = scorer(actor)

    assert first.conditional_q.shape == actor.action_mask.shape == (1, 3, 4)
    assert first.conditional_q.dtype == torch.float32
    assert torch.equal(first.conditional_q, second.conditional_q)
    assert torch.isfinite(first.conditional_q[actor.action_mask]).all()


def test_qh_scene_encoder_extraction_preserves_outputs_and_current_identity() -> None:
    """Lock extraction within float32 backend rounding and current identity."""

    config = TargetFiniteHorizonScorerConfig(hidden_dim=32, dropout=0.0, max_horizon=4)
    scorer = _scorer()
    output = scorer(_actor())

    assert stable_config_hash(config) == "f1940a233c7ea5b7"
    assert len(scorer.state_dict()) == 44
    assert not scorer.scene_encoder.state_dict()
    assert not any(key.startswith("scene_encoder.") for key in scorer.state_dict())
    torch.testing.assert_close(
        output.conditional_q,
        torch.tensor(
            [
                [
                    [-0.0111854225, -0.0080969334, -0.0088586658, -0.0080592483],
                    [-0.0085932389, -0.0064415932, -0.0055623800, -0.0082657412],
                    [-0.0083224773, -0.0050708354, -0.0052963421, -0.0028626025],
                ]
            ]
        ),
        rtol=0.0,
        atol=_FLOAT32_GOLDEN_ATOL,
    )
    torch.testing.assert_close(
        output.feasibility_logits,
        torch.tensor(
            [
                [
                    [-1.2504171133, -1.2618308067, -1.2461163998, -1.2615814209],
                    [-1.2496248484, -1.2496305704, -1.2499766350, -1.2494469881],
                    [-1.2460227013, -1.2493461370, -1.2373200655, -1.2411725521],
                ]
            ]
        ),
        rtol=0.0,
        atol=_FLOAT32_GOLDEN_ATOL,
    )


def test_qh_cfplus_h0_is_exactly_invariant_to_selected_observation_values() -> None:
    """The matched control admits CF+ identity without consuming its payload."""

    actor = _cfplus_actor()
    prefix = actor.selected_observation_prefix
    assert prefix is not None
    scorer = _cfplus_scorer()
    baseline = scorer(actor)
    changed_prefix = replace(
        prefix,
        depth_m=prefix.depth_m.add(37),
        valid_mask=~prefix.valid_mask,
        camera=CameraTW(prefix.camera.tensor().add(11)),
        camera_pose_relative_root=PoseTW(prefix.camera_pose_relative_root.tensor().add(5)),
    )

    changed = scorer(replace(actor, selected_observation_prefix=changed_prefix))

    assert torch.equal(changed.conditional_q, baseline.conditional_q)
    assert torch.equal(changed.feasibility_logits, baseline.feasibility_logits)


def test_qh_cfplus_h0_preserves_action_mask_independence_and_invalid_row_isolation() -> None:
    actor = _cfplus_actor()
    scorer = _cfplus_scorer()
    baseline = scorer(actor)
    action_mask = actor.action_mask.clone()
    action_mask[..., 0] = ~action_mask[..., 0]
    mask_changed = scorer(replace(actor, action_mask=action_mask))

    candidate_mask = actor.candidate_mask.clone()
    candidate_mask[..., -1] = False
    action_mask = actor.action_mask & candidate_mask
    masked = replace(actor, candidate_mask=candidate_mask, action_mask=action_mask)
    candidate_pose = actor.candidate_pose_relative_root.tensor().clone()
    candidate_pose[..., -1, :] = 1.0e6
    invalid_changed = scorer(replace(masked, candidate_pose_relative_root=PoseTW(candidate_pose)))
    invalid_baseline = scorer(masked)

    assert torch.equal(mask_changed.conditional_q, baseline.conditional_q)
    assert torch.equal(mask_changed.feasibility_logits, baseline.feasibility_logits)
    assert torch.equal(invalid_changed.conditional_q[candidate_mask], invalid_baseline.conditional_q[candidate_mask])
    assert torch.equal(
        invalid_changed.feasibility_logits[candidate_mask],
        invalid_baseline.feasibility_logits[candidate_mask],
    )


def test_qh_s1_keeps_every_common_downstream_weight_equal_to_h0() -> None:
    """Fixed scene width and late S1 construction isolate downstream initialization."""

    h0 = _cfplus_scorer()
    s1 = _s1_scorer()
    h0_state = h0.state_dict()
    s1_state = s1.state_dict()
    common_keys = [key for key in h0_state if not key.startswith("scene_encoder.")]

    assert common_keys
    assert all(key in s1_state for key in common_keys)
    for key in common_keys:
        assert torch.equal(s1_state[key], h0_state[key]), key
    assert s1.scene_encoder.output_dim == h0.scene_encoder.output_dim == 28


def test_qh_s1_identity_start_matches_h0_and_can_open_on_first_backward() -> None:
    """A fresh S1 is the exact H0 function, but its output projection can learn."""

    actor = _cfplus_actor()
    h0 = _cfplus_scorer()
    s1 = _s1_scorer()

    h0_output = h0(actor)
    s1_output = s1(actor)

    assert torch.count_nonzero(s1.scene_encoder.point_update.weight) == 0
    assert torch.equal(s1_output.conditional_q, h0_output.conditional_q)
    assert torch.equal(s1_output.feasibility_logits, h0_output.feasibility_logits)

    loss = s1_output.conditional_q[actor.candidate_mask].square().sum()
    loss.backward()
    projection_gradient = s1.scene_encoder.point_update.weight.grad

    assert projection_gradient is not None
    assert torch.isfinite(projection_gradient).all()
    assert torch.count_nonzero(projection_gradient) > 0


def test_qh_s1_consumes_selected_surface_values_without_reading_action_mask() -> None:
    actor = _cfplus_actor()
    prefix = actor.selected_observation_prefix
    assert prefix is not None
    scorer = _s1_scorer()
    with torch.no_grad():
        scorer.scene_encoder.point_update.weight.fill_(0.1)
    baseline = scorer(actor)
    changed_depth = prefix.depth_m.clone()
    changed_depth[prefix.prefix_mask[..., None, None].expand_as(changed_depth)] += 0.75
    changed = scorer(replace(actor, selected_observation_prefix=replace(prefix, depth_m=changed_depth)))
    action_mask = actor.action_mask.clone()
    action_mask[..., 0] = ~action_mask[..., 0]
    mask_changed = scorer(replace(actor, action_mask=action_mask))

    assert not torch.equal(changed.conditional_q, baseline.conditional_q)
    assert not torch.equal(changed.feasibility_logits, baseline.feasibility_logits)
    assert torch.equal(mask_changed.conditional_q, baseline.conditional_q)
    assert torch.equal(mask_changed.feasibility_logits, baseline.feasibility_logits)


def test_qh_s1_view_chunking_is_numerically_equivalent() -> None:
    actor = _cfplus_actor()
    one_view = _s1_scorer(view_chunk_size=1)
    all_views = _s1_scorer(view_chunk_size=32)
    all_views.load_state_dict(one_view.state_dict())

    first = one_view(actor)
    second = all_views(actor)

    torch.testing.assert_close(second.conditional_q, first.conditional_q, rtol=0.0, atol=1e-7)
    torch.testing.assert_close(second.feasibility_logits, first.feasibility_logits, rtol=0.0, atol=1e-7)


def test_qh_s1_selected_observation_has_exact_one_step_causal_shift() -> None:
    """Observation ``j`` may affect states ``t>j`` and no earlier state."""

    actor = _cfplus_actor()
    prefix = actor.selected_observation_prefix
    assert prefix is not None
    scorer = _s1_scorer()
    with torch.no_grad():
        scorer.scene_encoder.point_update.weight.fill_(0.1)
    baseline = scorer(actor)
    depth = prefix.depth_m.clone()
    depth[:, :, 1] += 0.75
    changed = scorer(replace(actor, selected_observation_prefix=replace(prefix, depth_m=depth)))

    assert torch.equal(changed.conditional_q[:, :2], baseline.conditional_q[:, :2])
    assert torch.equal(changed.feasibility_logits[:, :2], baseline.feasibility_logits[:, :2])
    assert not torch.equal(changed.conditional_q[:, 2], baseline.conditional_q[:, 2])
    assert not torch.equal(changed.feasibility_logits[:, 2], baseline.feasibility_logits[:, 2])


def test_qh_s1_candidate_rows_remain_isolated() -> None:
    """S1 is shared state context and never creates candidate-candidate edges."""

    actor = _cfplus_actor()
    scorer = _s1_scorer()
    with torch.no_grad():
        scorer.scene_encoder.point_update.weight.fill_(0.1)
    baseline = scorer(actor)
    changed_pose = actor.candidate_pose_relative_root.tensor().clone()
    changed_pose[..., 1, -3:] += torch.tensor([0.4, -0.2, 0.1])
    changed = scorer(replace(actor, candidate_pose_relative_root=PoseTW(changed_pose)))
    unchanged_rows = torch.ones_like(actor.candidate_mask)
    unchanged_rows[..., 1] = False

    assert torch.equal(changed.conditional_q[unchanged_rows], baseline.conditional_q[unchanged_rows])
    assert torch.equal(
        changed.feasibility_logits[unchanged_rows],
        baseline.feasibility_logits[unchanged_rows],
    )


def test_qh_s1_ignores_future_payload_values_and_preserves_candidate_equivariance() -> None:
    actor = _cfplus_actor()
    prefix = actor.selected_observation_prefix
    assert prefix is not None
    scorer = _s1_scorer()
    baseline = scorer(actor)
    inactive = ~prefix.prefix_mask
    future_depth = prefix.depth_m.clone()
    future_depth[inactive[..., None, None].expand_as(future_depth)] = 60000.0
    future_camera = prefix.camera.tensor().clone()
    future_camera[inactive] = 1.0e6
    future_pose = prefix.camera_pose_relative_root.tensor().clone()
    future_pose[inactive] = -1.0e6
    changed = scorer(
        replace(
            actor,
            selected_observation_prefix=replace(
                prefix,
                depth_m=future_depth,
                camera=CameraTW(future_camera),
                camera_pose_relative_root=PoseTW(future_pose),
            ),
        )
    )
    permutation = torch.tensor([2, 0, 3, 1])
    permuted = replace(
        actor,
        candidate_pose_relative_root=PoseTW(actor.candidate_pose_relative_root.tensor()[:, :, permutation]),
        candidate_mask=actor.candidate_mask[:, :, permutation],
        action_mask=actor.action_mask[:, :, permutation],
    )
    permuted_output = scorer(permuted)

    assert torch.equal(changed.conditional_q, baseline.conditional_q)
    assert torch.equal(changed.feasibility_logits, baseline.feasibility_logits)
    torch.testing.assert_close(
        permuted_output.conditional_q,
        baseline.conditional_q[:, :, permutation],
        rtol=0.0,
        atol=1e-6,
    )
    torch.testing.assert_close(
        permuted_output.feasibility_logits,
        baseline.feasibility_logits[:, :, permutation],
        rtol=0.0,
        atol=1e-6,
    )


def test_qh_s1_configuration_is_profile_and_semantics_bound() -> None:
    scene_encoder = QhSelectedSurfacePointSceneEncoderConfig()

    with pytest.raises(ValueError, match="representation_semantics"):
        TargetFiniteHorizonScorerConfig(
            experiment_profile="qh_cfplus_gt_depth_v1",
            scene_encoder=scene_encoder,
        )
    with pytest.raises(ValueError, match="requires qh_cfplus_gt_depth_v1"):
        TargetFiniteHorizonScorerConfig(
            representation_semantics="root_moments_plus_selected_surface_points_identity_start_v1",
            scene_encoder=scene_encoder,
        )


def test_qh_legacy_s1_identity_is_readable_but_not_reusable() -> None:
    """The ambiguous historical discriminator remains inspection-only."""

    config = TargetFiniteHorizonScorerConfig(
        hidden_dim=32,
        dropout=0.0,
        max_horizon=4,
        experiment_profile="qh_cfplus_gt_depth_v1",
        representation_semantics="root_moments_plus_selected_surface_points_v1",
        scene_encoder=QhLegacySelectedSurfacePointSceneEncoderConfig(
            pixel_stride=1,
            point_hidden_dim=16,
        ),
    )
    scorer = config.setup_target()

    scorer.validate_artifact_state(require_publishable=False)
    with pytest.raises(ValueError, match="inspection-only"):
        scorer.validate_artifact_state(require_publishable=True)


def test_qh_cf0_rejects_any_selected_observation_carrier() -> None:
    actor = _cfplus_actor()

    with pytest.raises(ValueError, match="qh_cf0_v1 rejects privileged selected observations"):
        _scorer()(actor)


def test_qh_cfplus_rejects_missing_or_wrong_source_carrier() -> None:
    actor = _cfplus_actor()
    prefix = actor.selected_observation_prefix
    assert prefix is not None
    scorer = _cfplus_scorer()

    with pytest.raises(ValueError, match="requires a causal CF-GT prefix"):
        scorer(replace(actor, selected_observation_prefix=None))
    with pytest.raises(ValueError, match="source_protocol='cf_gt'"):
        scorer(replace(actor, selected_observation_prefix=replace(prefix, source_protocol="other")))


@pytest.mark.parametrize("field", ["depth", "valid", "camera", "pose", "mask"])
def test_qh_cfplus_rejects_malformed_selected_observation_axes(field: str) -> None:
    actor = _cfplus_actor()
    prefix = actor.selected_observation_prefix
    assert prefix is not None
    if field == "depth":
        changed = replace(prefix, depth_m=prefix.depth_m[..., :-1])
    elif field == "valid":
        changed = replace(prefix, valid_mask=prefix.valid_mask[..., :-1])
    elif field == "camera":
        changed = replace(prefix, camera=CameraTW(prefix.camera.tensor()[:, :-1]))
    elif field == "pose":
        changed = replace(
            prefix,
            camera_pose_relative_root=PoseTW(prefix.camera_pose_relative_root.tensor()[:, :-1]),
        )
    else:
        changed = replace(prefix, prefix_mask=prefix.prefix_mask[..., :-1])

    with pytest.raises(ValueError, match="shape|match"):
        _cfplus_scorer()(replace(actor, selected_observation_prefix=changed))


def test_qh_cfplus_rejects_future_selected_observation_support() -> None:
    actor = _cfplus_actor()
    prefix = actor.selected_observation_prefix
    assert prefix is not None
    future = prefix.prefix_mask.clone()
    future[:, 0, 0] = True

    with pytest.raises(ValueError, match="strictly causal"):
        _cfplus_scorer()(replace(actor, selected_observation_prefix=replace(prefix, prefix_mask=future)))


def test_qh_scorer_returns_conditional_q_and_feasibility_logits() -> None:
    actor = _actor()
    output = _scorer()(actor)

    assert hasattr(output, "conditional_q")
    assert hasattr(output, "feasibility_logits")
    assert output.conditional_q.shape == actor.action_mask.shape
    assert output.feasibility_logits.shape == actor.action_mask.shape
    assert output.conditional_q.dtype is torch.float32
    assert output.feasibility_logits.dtype is torch.float32
    assert output.value_auxiliary is None


def test_qh_coral_scorer_preserves_scalar_contract_and_attaches_thresholds() -> None:
    actor = _actor()
    output = _coral_scorer()(actor)
    materialized = actor.candidate_mask & actor.step_mask.unsqueeze(-1)

    assert output.value_auxiliary is not None
    assert output.conditional_q.shape == actor.action_mask.shape
    assert output.value_auxiliary.logits.shape == (*actor.action_mask.shape, 2)
    assert output.value_auxiliary.logits.dtype is torch.float32
    assert output.value_auxiliary.bin_edges.tolist() == [-0.5, 0.5]
    assert output.value_auxiliary.bin_values.tolist() == [-1.0, 0.0, 1.0]
    assert torch.isfinite(output.value_auxiliary.logits[materialized]).all()
    assert torch.equal(
        output.value_auxiliary.logits[~materialized],
        torch.zeros_like(output.value_auxiliary.logits[~materialized]),
    )
    assert bool((output.conditional_q[materialized] >= -1.0).all())
    assert bool((output.conditional_q[materialized] <= 1.0).all())
    torch.testing.assert_close(
        output.conditional_q,
        torch.tensor(
            [
                [
                    [-0.0339741707, -0.0324316025, -0.0328121185, -0.0324127674],
                    [-0.0326795280, -0.0316047966, -0.0311655998, -0.0325159729],
                    [-0.0325441658, -0.0309200287, -0.0310328007, -0.0298169851],
                ]
            ]
        ),
        rtol=0.0,
        atol=_FLOAT32_GOLDEN_ATOL,
    )
    torch.testing.assert_close(
        output.value_auxiliary.logits,
        torch.tensor(
            [
                [
                    [
                        [-0.0679745078, -0.0679745078],
                        [-0.0648860186, -0.0648860186],
                        [-0.0656477511, -0.0656477511],
                        [-0.0648483336, -0.0648483336],
                    ],
                    [
                        [-0.0653823242, -0.0653823242],
                        [-0.0632306784, -0.0632306784],
                        [-0.0623514652, -0.0623514652],
                        [-0.0650548264, -0.0650548264],
                    ],
                    [
                        [-0.0651115626, -0.0651115626],
                        [-0.0618599206, -0.0618599206],
                        [-0.0620854273, -0.0620854273],
                        [-0.0596516877, -0.0596516877],
                    ],
                ]
            ]
        ),
        rtol=0.0,
        atol=_FLOAT32_GOLDEN_ATOL,
    )


def test_qh_scorer_explicit_remaining_horizon_matches_default_query() -> None:
    actor = _actor()
    scorer = _scorer()
    explicit = actor.horizon_remaining

    default = scorer(actor)
    queried = scorer(actor, requested_horizon=explicit)

    assert torch.equal(default.conditional_q, queried.conditional_q)
    assert torch.equal(default.feasibility_logits, queried.feasibility_logits)


def test_qh_admitted_forward_matches_public_forward_and_skips_revalidation(monkeypatch: pytest.MonkeyPatch) -> None:
    actor = _actor()
    scorer = _scorer()
    admitted = scorer.admit_actor(actor)
    expected = scorer(actor)

    def fail_validation(_: QhActorTensors) -> None:
        raise AssertionError("admitted forward must not repeat actor admission")

    monkeypatch.setattr(scorer, "_validate_actor", fail_validation)
    actual = scorer.forward_admitted(admitted)

    torch.testing.assert_close(actual.conditional_q, expected.conditional_q, rtol=0.0, atol=0.0)
    torch.testing.assert_close(actual.feasibility_logits, expected.feasibility_logits, rtol=0.0, atol=0.0)


def test_qh_admitted_forward_rejects_in_place_actor_mutation() -> None:
    actor = _actor()
    scorer = _scorer()
    admitted = scorer.admit_actor(actor)
    actor.action_mask[..., 0] = ~actor.action_mask[..., 0]

    with pytest.raises(ValueError, match="mutated after admission"):
        scorer.forward_admitted(admitted)


def test_qh_admitted_forward_rejects_another_scorers_admission() -> None:
    actor = _actor()
    admitting_scorer = _scorer()
    consuming_scorer = _scorer()
    admitted = admitting_scorer.admit_actor(actor)

    with pytest.raises(ValueError, match="different scorer"):
        consuming_scorer.forward_admitted(admitted)


def test_qh_inference_tensors_use_fully_validated_forward() -> None:
    scorer = _scorer().eval()

    with torch.inference_mode():
        actor = _actor()
        output = scorer(actor)
        with pytest.raises(ValueError, match="cannot be reused"):
            scorer.admit_actor(actor)

    assert torch.isfinite(output.conditional_q).all()


def test_qh_admitted_forward_retains_requested_horizon_validation() -> None:
    actor = _actor()
    scorer = _scorer()
    admitted = scorer.admit_actor(actor)
    invalid = torch.zeros_like(actor.horizon_remaining)

    with pytest.raises(ValueError, match="at least one"):
        scorer.forward_admitted(admitted, requested_horizon=invalid)


def test_qh_admitted_forward_reuses_admitted_default_horizon(monkeypatch: pytest.MonkeyPatch) -> None:
    actor = _actor()
    scorer = _scorer()
    admitted = scorer.admit_actor(actor)
    validated_horizons: list[torch.Tensor | None] = []
    original = scorer._validated_requested_horizon

    def record_validation(current_actor: QhActorTensors, requested_horizon: torch.Tensor | None) -> torch.Tensor:
        validated_horizons.append(requested_horizon)
        return original(current_actor, requested_horizon)

    monkeypatch.setattr(scorer, "_validated_requested_horizon", record_validation)

    scorer.forward_admitted(admitted)
    assert validated_horizons == []

    scorer.forward_admitted(admitted, requested_horizon=actor.horizon_remaining)
    assert validated_horizons == [actor.horizon_remaining]


def test_qh_scorer_accepts_bounded_off_diagonal_horizon_query() -> None:
    actor = _actor()
    scorer = _scorer()
    shorter = actor.horizon_remaining.clone()
    shorter[:, 0] = 1

    output = scorer(actor, requested_horizon=shorter)

    assert output.conditional_q.shape == actor.action_mask.shape
    assert torch.isfinite(output.conditional_q[actor.candidate_mask]).all()
    assert torch.equal(output.feasibility_logits, scorer(actor).feasibility_logits)


@pytest.mark.parametrize("invalid_horizon", [-1, 0, 5])
def test_qh_scorer_rejects_requested_horizon_outside_supported_range(invalid_horizon: int) -> None:
    actor = _actor()
    with pytest.raises(ValueError, match="horizon"):
        _scorer()(actor, requested_horizon=torch.full(actor.action_mask.shape[:2], invalid_horizon))


def test_qh_scorer_rejects_requested_horizon_above_factual_budget_without_clamping() -> None:
    actor = _actor()
    horizon = actor.horizon_remaining.clone()
    horizon[:, -1] = 2

    with pytest.raises(ValueError, match="factual horizon_remaining"):
        _scorer()(actor, requested_horizon=horizon)


def test_qh_scorer_rejects_requested_horizon_shape_and_dtype_drift() -> None:
    actor = _actor()
    scorer = _scorer()

    with pytest.raises(ValueError, match="shape"):
        scorer(actor, requested_horizon=actor.horizon_remaining.unsqueeze(-1))
    with pytest.raises(ValueError, match="int64"):
        scorer(actor, requested_horizon=actor.horizon_remaining.float())


def test_qh_scorer_raw_outputs_are_independent_of_action_mask() -> None:
    actor = _actor()
    scorer = _scorer()
    changed_mask = actor.action_mask.clone()
    changed_mask[..., 0] = ~changed_mask[..., 0]

    baseline = scorer(actor)
    changed = scorer(replace(actor, action_mask=changed_mask))

    assert torch.equal(changed.conditional_q, baseline.conditional_q)
    assert torch.equal(changed.feasibility_logits, baseline.feasibility_logits)


def test_qh_coral_thresholds_are_independent_of_action_mask() -> None:
    actor = _actor()
    scorer = _coral_scorer()
    changed_mask = actor.action_mask.clone()
    changed_mask[..., 0] = ~changed_mask[..., 0]

    baseline = scorer(actor)
    changed = scorer(replace(actor, action_mask=changed_mask))

    assert baseline.value_auxiliary is not None
    assert changed.value_auxiliary is not None
    assert torch.equal(changed.conditional_q, baseline.conditional_q)
    assert torch.equal(changed.value_auxiliary.logits, baseline.value_auxiliary.logits)


def test_qh_scorer_materialized_candidate_rows_are_finite_when_not_action_selectable() -> None:
    actor = _actor()
    action_mask = actor.action_mask.clone()
    action_mask[..., 0] = False
    output = _scorer()(replace(actor, action_mask=action_mask))

    materialized = actor.candidate_mask & actor.step_mask.unsqueeze(-1)
    assert torch.isfinite(output.conditional_q[materialized]).all()
    assert torch.isfinite(output.feasibility_logits[materialized]).all()


def test_qh_scorer_materialized_invalid_candidate_is_isolated_from_other_rows() -> None:
    actor = _actor()
    scorer = _scorer()
    action_mask = actor.action_mask.clone()
    action_mask[..., -1] = False
    invalid = replace(actor, action_mask=action_mask)
    baseline = scorer(invalid)
    poses = actor.candidate_pose_relative_root.tensor().clone()
    poses[..., -1, 9:12] += 1000.0
    changed = scorer(replace(invalid, candidate_pose_relative_root=PoseTW(poses)))

    assert torch.allclose(changed.conditional_q[..., :-1], baseline.conditional_q[..., :-1], atol=1e-6, rtol=1e-6)
    assert torch.allclose(
        changed.feasibility_logits[..., :-1],
        baseline.feasibility_logits[..., :-1],
        atol=1e-6,
        rtol=1e-6,
    )


def test_qh_scorer_candidate_permutation_preserves_both_output_heads() -> None:
    actor = _actor()
    scorer = _scorer()
    permutation = torch.tensor([2, 0, 3, 1])
    permuted = replace(
        actor,
        candidate_pose_relative_root=PoseTW(actor.candidate_pose_relative_root.tensor()[:, :, permutation]),
        candidate_mask=actor.candidate_mask[:, :, permutation],
        action_mask=actor.action_mask[:, :, permutation],
    )

    expected = scorer(actor)
    actual = scorer(permuted)

    assert torch.allclose(actual.conditional_q, expected.conditional_q[:, :, permutation], atol=1e-6, rtol=1e-6)
    assert torch.allclose(
        actual.feasibility_logits,
        expected.feasibility_logits[:, :, permutation],
        atol=1e-6,
        rtol=1e-6,
    )


def test_qh_ordered_history_preserves_candidate_permutation_equivariance() -> None:
    actor = _actor(steps=4)
    scorer = _ordered_history_scorer()
    permutation = torch.tensor([2, 0, 3, 1])
    permuted = replace(
        actor,
        candidate_pose_relative_root=PoseTW(actor.candidate_pose_relative_root.tensor()[:, :, permutation]),
        candidate_mask=actor.candidate_mask[:, :, permutation],
        action_mask=actor.action_mask[:, :, permutation],
    )

    expected = scorer(actor)
    actual = scorer(permuted)

    assert torch.allclose(actual.conditional_q, expected.conditional_q[:, :, permutation], atol=1e-6, rtol=1e-6)
    assert torch.allclose(
        actual.feasibility_logits,
        expected.feasibility_logits[:, :, permutation],
        atol=1e-6,
        rtol=1e-6,
    )


def test_qh_coral_scorer_candidate_permutation_preserves_thresholds() -> None:
    actor = _actor()
    scorer = _coral_scorer()
    permutation = torch.tensor([2, 0, 3, 1])
    permuted = replace(
        actor,
        candidate_pose_relative_root=PoseTW(actor.candidate_pose_relative_root.tensor()[:, :, permutation]),
        candidate_mask=actor.candidate_mask[:, :, permutation],
        action_mask=actor.action_mask[:, :, permutation],
    )

    expected = scorer(actor)
    actual = scorer(permuted)

    assert expected.value_auxiliary is not None
    assert actual.value_auxiliary is not None
    assert torch.allclose(
        actual.value_auxiliary.logits,
        expected.value_auxiliary.logits[:, :, permutation],
        atol=1e-6,
        rtol=1e-6,
    )


def test_qh_scorer_duplicate_candidate_has_identical_independent_outputs() -> None:
    actor = _actor()
    scorer = _scorer()
    poses = actor.candidate_pose_relative_root.tensor().clone()
    poses[..., 1, :] = poses[..., 0, :]

    output = scorer(replace(actor, candidate_pose_relative_root=PoseTW(poses)))

    assert torch.equal(output.conditional_q[..., 0], output.conditional_q[..., 1])
    assert torch.equal(output.feasibility_logits[..., 0], output.feasibility_logits[..., 1])


def test_qh_scorer_is_candidate_permutation_equivariant() -> None:
    actor = _actor()
    scorer = _scorer()
    permutation = torch.tensor([2, 0, 3, 1])
    permuted = replace(
        actor,
        candidate_pose_relative_root=PoseTW(actor.candidate_pose_relative_root.tensor()[:, :, permutation]),
        candidate_mask=actor.candidate_mask[:, :, permutation],
        action_mask=actor.action_mask[:, :, permutation],
    )

    expected = scorer(actor).conditional_q[:, :, permutation]
    actual = scorer(permuted).conditional_q

    assert torch.allclose(actual, expected, atol=1e-6, rtol=1e-6)


def test_qh_a0_identical_feature_control_preserves_public_candidate_invariants() -> None:
    actor = _actor()
    torch.manual_seed(11)
    scorer = TargetFiniteHorizonScorerConfig(
        hidden_dim=32,
        dropout=0.0,
        max_horizon=4,
        state_fusion=QhIndependentMlpStateFusionConfig(),
    ).setup_target()
    scorer.eval()
    permutation = torch.tensor([2, 0, 3, 1])
    permuted = replace(
        actor,
        candidate_pose_relative_root=PoseTW(actor.candidate_pose_relative_root.tensor()[:, :, permutation]),
        candidate_mask=actor.candidate_mask[:, :, permutation],
        action_mask=actor.action_mask[:, :, permutation],
    )
    changed_action_mask = actor.action_mask.clone()
    changed_action_mask[..., 0] = ~changed_action_mask[..., 0]

    expected = scorer(actor)
    actual = scorer(permuted)
    mask_changed = scorer(replace(actor, action_mask=changed_action_mask))
    candidate_mask = actor.candidate_mask.clone()
    candidate_mask[..., -1] = False
    valid_mask = actor.action_mask.clone()
    valid_mask[..., -1] = False
    masked = replace(actor, candidate_mask=candidate_mask, action_mask=valid_mask)
    mutated_pose = actor.candidate_pose_relative_root.tensor().clone()
    mutated_pose[..., -1, :] = 1.0e6
    invalid_changed = scorer(replace(masked, candidate_pose_relative_root=PoseTW(mutated_pose)))
    invalid_baseline = scorer(masked)

    assert torch.allclose(actual.conditional_q, expected.conditional_q[:, :, permutation], atol=1e-6, rtol=1e-6)
    assert torch.allclose(
        actual.feasibility_logits,
        expected.feasibility_logits[:, :, permutation],
        atol=1e-6,
        rtol=1e-6,
    )
    assert torch.equal(mask_changed.conditional_q, expected.conditional_q)
    assert torch.equal(mask_changed.feasibility_logits, expected.feasibility_logits)
    assert torch.allclose(
        invalid_changed.conditional_q[candidate_mask],
        invalid_baseline.conditional_q[candidate_mask],
        atol=1e-6,
        rtol=1e-6,
    )
    assert torch.allclose(
        invalid_changed.feasibility_logits[candidate_mask],
        invalid_baseline.feasibility_logits[candidate_mask],
        atol=1e-6,
        rtol=1e-6,
    )
    assert torch.equal(
        invalid_changed.conditional_q[~candidate_mask],
        torch.zeros_like(invalid_changed.conditional_q[~candidate_mask]),
    )
    assert torch.equal(
        invalid_changed.feasibility_logits[~candidate_mask],
        torch.zeros_like(invalid_changed.feasibility_logits[~candidate_mask]),
    )


def test_qh_scorer_invalid_rows_are_isolated() -> None:
    actor = _actor()
    scorer = _scorer()
    action_mask = actor.action_mask.clone()
    action_mask[..., -1] = False
    candidate_mask = actor.candidate_mask.clone()
    candidate_mask[..., -1] = False
    masked = replace(actor, action_mask=action_mask, candidate_mask=candidate_mask)
    mutated_pose = actor.candidate_pose_relative_root.tensor().clone()
    mutated_pose[..., -1, :] = 1.0e6
    mutated = replace(masked, candidate_pose_relative_root=PoseTW(mutated_pose))

    baseline = scorer(masked)
    changed = scorer(mutated)

    assert torch.allclose(
        changed.conditional_q[candidate_mask],
        baseline.conditional_q[candidate_mask],
        atol=1e-6,
        rtol=1e-6,
    )
    assert torch.equal(
        changed.conditional_q[~candidate_mask],
        torch.zeros_like(changed.conditional_q[~candidate_mask]),
    )


def test_qh_scorer_sanitizes_inactive_nonfinite_pose_rows() -> None:
    actor = _actor()
    scorer = _scorer()
    baseline = scorer(actor)
    candidate = actor.candidate_pose_relative_root.tensor().clone()
    candidate[~actor.candidate_mask] = float("nan")
    history = actor.history_pose_relative_root.tensor().clone()
    history[~actor.history_mask] = float("inf")

    actual = scorer(
        replace(
            actor,
            candidate_pose_relative_root=PoseTW(candidate),
            history_pose_relative_root=PoseTW(history),
        )
    )
    assert torch.allclose(actual.conditional_q, baseline.conditional_q, atol=1e-6, rtol=1e-6)
    assert torch.allclose(actual.feasibility_logits, baseline.feasibility_logits, atol=1e-6, rtol=1e-6)
    assert torch.isfinite(actual.conditional_q).all()
    assert torch.isfinite(actual.feasibility_logits).all()


def test_qh_scorer_rejects_nonfinite_active_pose_rows() -> None:
    actor = _actor()
    scorer = _scorer()
    candidate = actor.candidate_pose_relative_root.tensor().clone()
    first = tuple(int(value) for value in torch.nonzero(actor.action_mask, as_tuple=False)[0])
    candidate[first] = float("nan")
    with pytest.raises(ValueError, match="active candidate poses"):
        scorer(replace(actor, candidate_pose_relative_root=PoseTW(candidate)))

    target = actor.target_pose_relative_root.tensor().clone()
    target[..., 0] = float("inf")
    with pytest.raises(ValueError, match="active target poses"):
        scorer(replace(actor, target_pose_relative_root=PoseTW(target)))

    root = actor.root_pose_world.tensor().clone()
    root[..., 0] = float("nan")
    with pytest.raises(ValueError, match="active root poses"):
        scorer(replace(actor, root_pose_world=PoseTW(root)))

    extents = actor.target_extents.clone()
    extents[..., 0] = float("inf")
    with pytest.raises(ValueError, match="active target extents"):
        scorer(replace(actor, target_extents=extents))


def test_qh_candidate_relative_transforms_compose_in_the_declared_direction() -> None:
    actor = _actor()
    scorer = _scorer()
    batch_size, steps, width = actor.action_mask.shape
    rotation = torch.eye(3).expand(batch_size, steps, width, 3, 3).clone()
    candidate_translation = torch.zeros(batch_size, steps, width, 3)
    candidate_translation[:, 1, 0, 0] = 5.0
    candidates = PoseTW.from_Rt(rotation, candidate_translation)
    history_rotation = torch.eye(3).expand(batch_size, steps, steps, 3, 3).clone()
    history_translation = torch.zeros(batch_size, steps, steps, 3)
    history_translation[:, 1, 0, 0] = 2.0
    history = PoseTW.from_Rt(history_rotation, history_translation)
    target = PoseTW.from_Rt(torch.eye(3).expand(batch_size, 3, 3).clone(), torch.tensor([[9.0, 0.0, 0.0]]))
    actor = replace(
        actor,
        candidate_pose_relative_root=candidates,
        history_pose_relative_root=history,
        target_pose_relative_root=target,
    )

    current = scorer._current_pose_relative_root(actor, history)
    current_from_candidate = scorer._expand_pose(current.inverse(), width) @ candidates
    candidate_from_target = candidates.inverse() @ scorer._expand_pose(target, steps, width)

    assert torch.equal(current_from_candidate.t[0, 1, 0], torch.tensor([3.0, 0.0, 0.0]))
    assert torch.equal(candidate_from_target.t[0, 1, 0], torch.tensor([4.0, 0.0, 0.0]))


def test_qh_scorer_uses_target_history_and_budget_without_future_history() -> None:
    actor = _actor()
    scorer = _scorer()
    baseline = scorer(actor).conditional_q

    target = actor.target_extents.clone()
    target[:, 0] += 0.75
    assert not torch.allclose(scorer(replace(actor, target_extents=target)).conditional_q, baseline)

    history = actor.history_pose_relative_root.tensor().clone()
    history[:, 2, 0, :] += 0.25
    assert not torch.allclose(
        scorer(replace(actor, history_pose_relative_root=PoseTW(history))).conditional_q,
        baseline,
    )

    future_history = actor.history_pose_relative_root.tensor().clone()
    future_history[:, 0, 2, :] += 10_000.0
    assert torch.allclose(
        scorer(replace(actor, history_pose_relative_root=PoseTW(future_history))).conditional_q,
        baseline,
        atol=1e-6,
        rtol=1e-6,
    )

    budget = actor.horizon_remaining.clone()
    budget[:, 0] -= 1
    assert not torch.allclose(scorer(replace(actor, horizon_remaining=budget)).conditional_q, baseline)


def test_qh_feasibility_is_independent_of_target_budget_and_requested_horizon() -> None:
    actor = _actor()
    scorer = _scorer()
    baseline = scorer(actor).feasibility_logits
    target = actor.target_extents + 0.75
    budget = actor.horizon_remaining.clone()
    budget[:, 0] -= 1
    requested_horizon = budget.clone()
    requested_horizon[:, 0] = 1

    changed = scorer(
        replace(actor, target_extents=target, horizon_remaining=budget),
        requested_horizon=requested_horizon,
    ).feasibility_logits

    assert torch.equal(changed, baseline)


def test_qh_ordered_history_is_sensitive_only_to_noncurrent_prefix_order() -> None:
    actor = _actor(steps=4)
    history = actor.history_pose_relative_root.tensor().clone()
    history[:, 3, [0, 1]] = history[:, 3, [1, 0]]
    permuted = replace(actor, history_pose_relative_root=PoseTW(history))

    torch.manual_seed(11)
    mean_scorer = TargetFiniteHorizonScorerConfig(
        hidden_dim=32,
        dropout=0.0,
        max_horizon=4,
        history_encoder=QhMeanPoolHistoryEncoderConfig(),
    ).setup_target()
    mean_scorer.eval()
    ordered_scorer = _ordered_history_scorer()

    assert torch.allclose(
        mean_scorer(actor).conditional_q,
        mean_scorer(permuted).conditional_q,
        atol=1e-6,
        rtol=1e-6,
    )
    assert not torch.allclose(
        ordered_scorer(actor).conditional_q[:, 3],
        ordered_scorer(permuted).conditional_q[:, 3],
    )


def test_qh_scorer_rejects_incomplete_realized_history_prefix() -> None:
    actor = _actor(steps=4)
    history_mask = actor.history_mask.clone()
    history_mask[:, 3, 1] = False

    with pytest.raises(ValueError, match="complete strictly causal prefix"):
        _ordered_history_scorer()(replace(actor, history_mask=history_mask))


def test_qh_scorer_backward_updates_parameters_only() -> None:
    actor = _actor()
    scorer = _scorer()

    scorer(actor).conditional_q[actor.action_mask].sum().backward()

    assert any(parameter.grad is not None and bool(parameter.grad.abs().sum() > 0) for parameter in scorer.parameters())
    assert actor.candidate_pose_relative_root.tensor().grad is None
    assert actor.static_context is not None
    assert actor.static_context.occ_pr is not None
    assert actor.static_context.occ_pr.grad is None


def test_qh_scorer_config_is_factory_and_rejects_profile_mismatch() -> None:
    config = TargetFiniteHorizonScorerConfig(hidden_dim=32, max_horizon=4)

    assert config.model_dump()["horizon_query_semantics"] == "bounded_scalar_v1"
    assert config.target_type is TargetFiniteHorizonScorer
    assert isinstance(config.setup_target(), TargetFiniteHorizonScorer)

    actor = replace(_actor(), static_context=None)
    try:
        config.setup_target()(actor)
    except ValueError as error:
        assert "EVL" in str(error)
    else:  # pragma: no cover - assertion branch
        raise AssertionError("scorer accepted an actor without required EVL context")


@pytest.mark.parametrize(
    ("state_fusion", "history_encoder"),
    [
        (QhIndependentMlpStateFusionConfig(), None),
        (QhCrossAttentionStateFusionConfig(attention_heads=2), QhMeanPoolHistoryEncoderConfig()),
        (
            QhCrossAttentionStateFusionConfig(attention_heads=2),
            QhCausalTransformerHistoryEncoderConfig(attention_heads=2),
        ),
    ],
)
def test_qh_scorer_config_round_trips_discriminated_modules(state_fusion, history_encoder) -> None:
    config = TargetFiniteHorizonScorerConfig(
        hidden_dim=32,
        max_horizon=4,
        state_fusion=state_fusion,
        history_encoder=history_encoder,
    )

    restored = TargetFiniteHorizonScorerConfig.model_validate(config.model_dump_jsonable())

    assert restored == config
    assert type(restored.state_fusion) is type(state_fusion)
    assert type(restored.history_encoder) is type(history_encoder)


def test_qh_default_history_preserves_legacy_state_and_explicit_identity() -> None:
    default_config = TargetFiniteHorizonScorerConfig(hidden_dim=32, dropout=0.0, max_horizon=4)
    explicit_config = TargetFiniteHorizonScorerConfig(
        hidden_dim=32,
        dropout=0.0,
        max_horizon=4,
        history_encoder=QhMeanPoolHistoryEncoderConfig(),
    )
    assert "history_encoder" not in default_config.model_dump_jsonable()
    assert explicit_config.model_dump_jsonable()["history_encoder"]["kind"] == "mean_pool_v1"
    assert stable_config_hash(default_config) != stable_config_hash(explicit_config)

    torch.manual_seed(17)
    default = default_config.setup_target()
    torch.manual_seed(17)
    explicit = explicit_config.setup_target()
    assert default.state_dict().keys() == explicit.state_dict().keys()
    assert not any(key.startswith("history_encoder.") for key in default.state_dict())
    assert all(torch.equal(default.state_dict()[key], explicit.state_dict()[key]) for key in default.state_dict())
    actor = _actor(steps=4)
    default.eval()
    explicit.eval()
    assert torch.equal(default(actor).conditional_q, explicit(actor).conditional_q)


def test_qh_scorer_config_rejects_incompatible_attention_width() -> None:
    with pytest.raises(ValueError, match="divisible"):
        TargetFiniteHorizonScorerConfig(
            hidden_dim=31,
            state_fusion=QhCrossAttentionStateFusionConfig(attention_heads=4),
        )


def test_qh_scorer_config_validates_complete_history_pose_width() -> None:
    """H1 divisibility includes a concatenated raw pose residual."""

    pose_encoder = R6dLffPoseEncoderConfig(
        pose_encoder_lff=LearnableFourierFeaturesConfig(
            input_dim=9,
            fourier_dim=64,
            hidden_dim=128,
            output_dim=32,
            include_input=True,
        ),
    )
    assert pose_encoder.out_dim == 41

    with pytest.raises(ValueError, match="pose-encoder output width must be divisible"):
        TargetFiniteHorizonScorerConfig(
            hidden_dim=32,
            pose_encoder=pose_encoder,
            history_encoder=QhCausalTransformerHistoryEncoderConfig(attention_heads=4),
        )


def test_qh_scorer_module_has_no_oracle_or_supervision_dependency() -> None:
    path = Path(__file__).resolve().parents[2] / "aria_nbv" / "vin" / "models" / "target_finite_horizon.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module is not None}
    assert not any("oracle" in module for module in imports)
    assert "QhSupervision" not in path.read_text(encoding="utf-8")
