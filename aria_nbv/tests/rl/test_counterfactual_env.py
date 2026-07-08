"""Tests for the counterfactual RL environment."""

# ruff: noqa: S101

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("efm3d")
pytest.importorskip("gymnasium")
pytest.importorskip("stable_baselines3")

import torch
import trimesh
from efm3d.aria import CameraTW, PoseTW

from aria_nbv.pose_generation import CandidateViewGeneratorConfig, SamplingStrategy
from aria_nbv.rl import (
    CounterfactualPPOConfig,
    CounterfactualRLEnv,
    CounterfactualRLEnvConfig,
    validate_counterfactual_env,
)
from aria_nbv.rollouts import CounterfactualCandidateEvaluation


def _identity_pose(device: torch.device | str = "cpu") -> PoseTW:
    return PoseTW(
        torch.tensor(
            [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            device=device,
        )
    )


def _dummy_camera(device: torch.device | str = "cpu") -> CameraTW:
    return CameraTW.from_surreal(
        width=torch.tensor([64.0], device=device),
        height=torch.tensor([64.0], device=device),
        type_str="Pinhole",
        params=torch.tensor([[60.0, 60.0, 32.0, 32.0]], device=device),
        gain=torch.zeros(1, device=device),
        exposure_s=torch.zeros(1, device=device),
        valid_radius=torch.tensor([64.0], device=device),
        T_camera_rig=PoseTW.from_matrix3x4(torch.eye(3, 4, device=device).unsqueeze(0)),
    )


def _mesh_triplet(device: torch.device | str = "cpu") -> tuple[trimesh.Trimesh, torch.Tensor, torch.Tensor]:
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    verts = torch.from_numpy(mesh.vertices).to(dtype=torch.float32, device=device)
    faces = torch.from_numpy(mesh.faces).to(dtype=torch.int64, device=device)
    return mesh, verts, faces


def _default_extent(device: torch.device | str = "cpu") -> torch.Tensor:
    return torch.tensor([-10.0, 10.0, -10.0, 10.0, -10.0, 10.0], dtype=torch.float32, device=device)


def _fake_reward_evaluator(result, trajectory, step_index):
    del trajectory

    valid_poses = result.poses_world_cam()
    centers = valid_poses.t.reshape(-1, 3)
    scores = torch.linspace(0.1, 0.1 * centers.shape[0], centers.shape[0], device=centers.device)
    scores = scores + float(step_index)
    candidate_points = centers.unsqueeze(1).repeat(1, 2, 1)
    lengths = torch.full((centers.shape[0],), 2, dtype=torch.long, device=centers.device)
    return CounterfactualCandidateEvaluation(
        scores=scores,
        score_label="oracle_rri",
        metric_vectors={"rri": scores},
        candidate_point_clouds_world=candidate_points,
        candidate_point_cloud_lengths=lengths,
    )


def _make_env() -> CounterfactualRLEnv:
    candidate_cfg = CandidateViewGeneratorConfig(
        num_samples=8,
        oversample_factor=1.0,
        min_radius=0.5,
        max_radius=0.5,
        ensure_collision_free=False,
        ensure_free_space=False,
        min_distance_to_mesh=0.0,
        sampling_strategy=SamplingStrategy.UNIFORM_SPHERE,
        view_max_azimuth_deg=0.0,
        view_max_elevation_deg=0.0,
        verbosity=0,
        seed=0,
        is_debug=True,
    )
    cfg = CounterfactualRLEnvConfig(
        candidate_config=candidate_cfg,
        horizon=3,
        invalid_action_penalty=-0.01,
        verbosity=0,
        is_debug=True,
    )
    mesh, verts, faces = _mesh_triplet(candidate_cfg.device)
    return CounterfactualRLEnv(
        cfg,
        reward_evaluator=_fake_reward_evaluator,
        reference_pose=_identity_pose(device=candidate_cfg.device),
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        camera_calib_template=_dummy_camera(candidate_cfg.device),
        occupancy_extent=_default_extent(candidate_cfg.device),
    )


def test_counterfactual_rl_env_reset_and_step() -> None:
    env = _make_env()

    obs, info = env.reset(seed=0)
    valid_actions = np.flatnonzero(info["action_mask"])

    assert obs["candidate_positions"].shape == (env.action_space.n, 3)
    assert valid_actions.size > 0

    obs_next, reward, terminated, truncated, info_next = env.step(int(valid_actions[0]))

    assert reward > 0.0
    assert truncated is False
    assert terminated is False
    assert obs_next["history_mask"].sum() >= 2
    assert info_next["cumulative_rri"] == pytest.approx(reward)


def test_counterfactual_rl_env_passes_sb3_check_and_ppo_smoke() -> None:
    env = _make_env()
    validate_counterfactual_env(env)

    model = CounterfactualPPOConfig(
        n_steps=8,
        batch_size=4,
        n_epochs=1,
        verbose=0,
    ).setup_target(env=env)
    model.learn(total_timesteps=16)

    obs, _ = env.reset(seed=1)
    action, _ = model.predict(obs, deterministic=True)
    assert int(action) >= 0


def test_counterfactual_rl_env_aligns_default_oracle_depth_budget_to_shell() -> None:
    candidate_cfg = CandidateViewGeneratorConfig(
        num_samples=60,
        oversample_factor=1.9,
        min_radius=0.5,
        max_radius=0.5,
        ensure_collision_free=False,
        ensure_free_space=False,
        min_distance_to_mesh=0.0,
        sampling_strategy=SamplingStrategy.UNIFORM_SPHERE,
        view_max_azimuth_deg=0.0,
        view_max_elevation_deg=0.0,
        verbosity=0,
        seed=0,
        is_debug=False,
    )
    cfg = CounterfactualRLEnvConfig(candidate_config=candidate_cfg, verbosity=0, is_debug=False)
    mesh, verts, faces = _mesh_triplet(candidate_cfg.device)
    sample = SimpleNamespace(
        mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        semidense=SimpleNamespace(collapse_points=lambda: np.zeros((0, 3), dtype=np.float32)),
        trajectory=SimpleNamespace(final_pose=_identity_pose(device=candidate_cfg.device)),
        get_camera=lambda _label: SimpleNamespace(calib=_dummy_camera(candidate_cfg.device)),
        get_occupancy_extend=lambda: _default_extent(candidate_cfg.device),
    )

    env = CounterfactualRLEnv(cfg, sample=sample)

    assert env._reward_evaluator is not None
    assert env._reward_evaluator.config.depth.max_candidates_final >= 114
