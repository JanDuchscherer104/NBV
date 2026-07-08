"""Gymnasium/SB3 reinforcement-learning surfaces for counterfactual pose selection.

The initial RL boundary is intentionally narrow:

- the environment reuses the existing one-step candidate generator,
- actions select one candidate from the fixed pre-pruning shell,
- rewards come from the structured counterfactual evaluator (oracle RRI by
  default), and
- observations expose the current shell, validity mask, and rollout history
  through a Gymnasium ``Dict`` space compatible with Stable-Baselines3's
  ``MultiInputPolicy``.

This follows the repo's current outlook and Hestia's formulation: greedy-like
immediate rewards, a short horizon, and PPO-ready interfaces without committing
to a large continuous-control stack prematurely.
"""

from __future__ import annotations

from math import ceil
from typing import TYPE_CHECKING, Any

import gymnasium as gym
import numpy as np
import torch
from efm3d.aria.camera import CameraTW
from efm3d.aria.pose import PoseTW
from gymnasium import spaces
from pydantic import Field, field_validator

from ..data_handling import EfmSnippetView
from ..pose_generation import CandidateViewGenerator, CandidateViewGeneratorConfig
from ..rollouts.counterfactuals import (
    CounterfactualCandidateEvaluation,
    CounterfactualEvaluatorFn,
    CounterfactualOracleRriScorerConfig,
    CounterfactualRolloutResult,
    CounterfactualStepResult,
    CounterfactualTrajectory,
)
from ..utils import BaseConfig, Console, TargetConfig, Verbosity
from ..utils.frames import rotate_yaw_cw90

if TYPE_CHECKING:
    import trimesh


def _shell_action_capacity(candidate_config: CandidateViewGeneratorConfig) -> int:
    """Return the maximum shell size exposed as the discrete RL action space."""

    return int(ceil(candidate_config.num_samples * candidate_config.oversample_factor))


def _float_box(shape: tuple[int, ...]) -> spaces.Box:
    """Return a wide float32 box space for SB3-ready numeric arrays."""

    max_f = np.finfo(np.float32).max
    return spaces.Box(low=-max_f, high=max_f, shape=shape, dtype=np.float32)


class CounterfactualRLEnvConfig(TargetConfig["CounterfactualRLEnv"]):
    """Config-as-factory surface for the basic counterfactual RL environment."""

    @property
    def target_type(self) -> type["CounterfactualRLEnv"]:
        return CounterfactualRLEnv

    candidate_config: CandidateViewGeneratorConfig = Field(default_factory=CandidateViewGeneratorConfig)
    """One-step candidate generator reused after each selected action."""

    reward: CounterfactualOracleRriScorerConfig = Field(default_factory=CounterfactualOracleRriScorerConfig)
    """Reward evaluator used when no explicit runtime evaluator is provided."""

    horizon: int = Field(default=3, ge=1)
    """Episode horizon in rollout steps."""

    invalid_action_penalty: float = -0.01
    """Immediate penalty applied when the chosen shell action is invalid."""

    terminate_on_invalid_action: bool = False
    """Whether invalid actions immediately terminate the episode."""

    verbosity: Verbosity = Field(default=Verbosity.NORMAL)
    """Logging verbosity for environment orchestration."""

    is_debug: bool = False
    """Enable debug logging for environment orchestration."""

    _coerce_verbosity = field_validator("verbosity", mode="before")(BaseConfig._coerce_verbosity)


class CounterfactualRLEnv(gym.Env[dict[str, np.ndarray], int]):
    """Gymnasium environment for sequential counterfactual pose selection."""

    metadata = {"render_modes": ["rgb_array"], "render_fps": 1}

    def __init__(
        self,
        config: CounterfactualRLEnvConfig,
        *,
        sample: EfmSnippetView | None = None,
        reward_evaluator: CounterfactualEvaluatorFn | None = None,
        reference_pose: PoseTW | None = None,
        gt_mesh: "trimesh.Trimesh" | None = None,
        mesh_verts: torch.Tensor | None = None,
        mesh_faces: torch.Tensor | None = None,
        camera_calib_template: CameraTW | None = None,
        occupancy_extent: torch.Tensor | None = None,
    ) -> None:
        super().__init__()

        self.config = config
        self.console = (
            Console.with_prefix(self.__class__.__name__)
            .set_verbosity(self.config.verbosity)
            .set_debug(self.config.is_debug)
        )
        self._candidate_generator: CandidateViewGenerator = self.config.candidate_config.setup_target()
        self._reward_evaluator = reward_evaluator
        self._sample = sample

        (
            self._reference_pose,
            self._gt_mesh,
            self._mesh_verts,
            self._mesh_faces,
            self._camera_calib_template,
            self._occupancy_extent,
        ) = self._resolve_runtime_state(
            sample=sample,
            reference_pose=reference_pose,
            gt_mesh=gt_mesh,
            mesh_verts=mesh_verts,
            mesh_faces=mesh_faces,
            camera_calib_template=camera_calib_template,
            occupancy_extent=occupancy_extent,
        )

        if self._reward_evaluator is None:
            if sample is None:
                raise ValueError(
                    "CounterfactualRLEnv requires either `sample` for the default oracle-RRI reward "
                    "or an explicit `reward_evaluator`.",
                )
            reward_cfg = self._aligned_reward_config()
            self._reward_evaluator = reward_cfg.setup_target(sample=sample)

        self._max_shell_candidates = _shell_action_capacity(self.config.candidate_config)

        self.action_space = spaces.Discrete(self._max_shell_candidates)
        self.observation_space = spaces.Dict(
            {
                "step_fraction": spaces.Box(low=0.0, high=1.0, shape=(1,), dtype=np.float32),
                "current_position": _float_box((3,)),
                "history_positions": _float_box((self.config.horizon + 1, 3)),
                "history_mask": spaces.Box(low=0.0, high=1.0, shape=(self.config.horizon + 1,), dtype=np.float32),
                "candidate_positions": _float_box((self._max_shell_candidates, 3)),
                "candidate_valid_mask": spaces.Box(
                    low=0.0,
                    high=1.0,
                    shape=(self._max_shell_candidates,),
                    dtype=np.float32,
                ),
            }
        )

        self._trajectory: CounterfactualTrajectory | None = None
        self._step_count = 0
        self._current_candidates: Any = None
        self._current_evaluation: CounterfactualCandidateEvaluation | None = None
        self._shell_to_valid = torch.full((self._max_shell_candidates,), -1, dtype=torch.long)

    @staticmethod
    def _canonicalize_pose(reference_pose: PoseTW) -> PoseTW:
        """Apply the same display-basis correction used by candidate generation."""

        return rotate_yaw_cw90(reference_pose)

    def _aligned_reward_config(self) -> CounterfactualOracleRriScorerConfig:
        """Ensure the default oracle scorer can evaluate the full RL action shell."""

        shell_capacity = _shell_action_capacity(self.config.candidate_config)
        reward_cfg = self.config.reward
        if int(reward_cfg.depth.max_candidates_final) >= shell_capacity:
            return reward_cfg

        self.console.log(
            "Raising reward.depth.max_candidates_final from "
            f"{int(reward_cfg.depth.max_candidates_final)} to {shell_capacity} "
            "so the oracle scorer covers the full shell action space.",
        )
        return reward_cfg.model_copy(
            update={
                "depth": reward_cfg.depth.model_copy(
                    update={"max_candidates_final": shell_capacity},
                )
            }
        )

    @staticmethod
    def _generator_input_pose(reference_pose_world: PoseTW) -> PoseTW:
        """Undo the display correction before calling the one-step generator."""

        return rotate_yaw_cw90(reference_pose_world, undo=True)

    def _resolve_runtime_state(
        self,
        *,
        sample: EfmSnippetView | None,
        reference_pose: PoseTW | None,
        gt_mesh: "trimesh.Trimesh" | None,
        mesh_verts: torch.Tensor | None,
        mesh_faces: torch.Tensor | None,
        camera_calib_template: CameraTW | None,
        occupancy_extent: torch.Tensor | None,
    ) -> tuple[PoseTW, "trimesh.Trimesh", torch.Tensor, torch.Tensor, CameraTW, torch.Tensor]:
        """Resolve runtime geometry either from a sample or direct arguments."""

        device = torch.device(self.config.candidate_config.device)
        if sample is not None:
            if sample.mesh is None or sample.mesh_verts is None or sample.mesh_faces is None:
                raise ValueError("CounterfactualRLEnv sample must carry mesh, mesh_verts, and mesh_faces.")
            cam_view = sample.get_camera(self.config.candidate_config.camera_label)
            resolved_pose = (
                reference_pose if reference_pose is not None else sample.trajectory.final_pose.to(device=device)
            )
            return (
                resolved_pose.to(device=device),
                sample.mesh,
                sample.mesh_verts.to(device=device),
                sample.mesh_faces.to(device=device),
                cam_view.calib.to(device=device),
                sample.get_occupancy_extend().to(device=device, dtype=torch.float32),
            )

        missing = [
            name
            for name, value in {
                "reference_pose": reference_pose,
                "gt_mesh": gt_mesh,
                "mesh_verts": mesh_verts,
                "mesh_faces": mesh_faces,
                "camera_calib_template": camera_calib_template,
                "occupancy_extent": occupancy_extent,
            }.items()
            if value is None
        ]
        if missing:
            raise ValueError(f"CounterfactualRLEnv missing runtime inputs: {', '.join(missing)}.")

        assert gt_mesh is not None
        assert mesh_verts is not None
        assert mesh_faces is not None
        assert reference_pose is not None
        assert camera_calib_template is not None
        assert occupancy_extent is not None
        return (
            reference_pose.to(device=device),
            gt_mesh,
            mesh_verts.to(device=device),
            mesh_faces.to(device=device),
            camera_calib_template.to(device=device),
            occupancy_extent.to(device=device, dtype=torch.float32),
        )

    def _evaluate_candidates(self) -> CounterfactualCandidateEvaluation | None:
        """Evaluate the current valid-candidate batch with the configured reward."""

        assert self._trajectory is not None
        assert self._current_candidates is not None
        valid_poses = self._current_candidates.poses_world_cam()
        num_valid = valid_poses.tensor().shape[0]
        if num_valid == 0:
            return None

        raw_eval = self._reward_evaluator(self._current_candidates, self._trajectory, self._step_count)
        if isinstance(raw_eval, CounterfactualCandidateEvaluation):
            return raw_eval.validate(
                num_valid=num_valid,
                device=valid_poses.t.device,
                dtype=valid_poses.t.dtype,
            )
        return CounterfactualCandidateEvaluation(
            scores=torch.as_tensor(raw_eval, device=valid_poses.t.device, dtype=valid_poses.t.dtype),
            score_label="reward",
        ).validate(num_valid=num_valid, device=valid_poses.t.device, dtype=valid_poses.t.dtype)

    def _refresh_candidates(self, reference_pose_world: PoseTW) -> None:
        """Generate the next candidate shell and reward evaluation."""

        self._current_candidates = self._candidate_generator.generate(
            reference_pose=self._generator_input_pose(reference_pose_world),
            gt_mesh=self._gt_mesh,
            mesh_verts=self._mesh_verts,
            mesh_faces=self._mesh_faces,
            camera_calib_template=self._camera_calib_template,
            occupancy_extent=self._occupancy_extent,
        )

        self._shell_to_valid = torch.full((self._max_shell_candidates,), -1, dtype=torch.long)
        valid_to_shell = torch.nonzero(self._current_candidates.mask_valid, as_tuple=False).reshape(-1)
        if valid_to_shell.numel() > 0:
            valid_count = min(int(valid_to_shell.shape[0]), self._max_shell_candidates)
            self._shell_to_valid[valid_to_shell[:valid_count]] = torch.arange(valid_count)
        self._current_evaluation = self._evaluate_candidates()

    def _build_observation(self) -> dict[str, np.ndarray]:
        """Pack the current shell and rollout history into a Dict observation."""

        assert self._trajectory is not None
        assert self._current_candidates is not None

        history = self._trajectory.pose_chain_world().t.detach().cpu().numpy().astype(np.float32)
        history_positions = np.zeros((self.config.horizon + 1, 3), dtype=np.float32)
        history_mask = np.zeros((self.config.horizon + 1,), dtype=np.float32)
        hist_len = min(history.shape[0], self.config.horizon + 1)
        history_positions[:hist_len] = history[:hist_len]
        history_mask[:hist_len] = 1.0

        shell = self._current_candidates.shell_poses.t.detach().cpu().numpy().astype(np.float32)
        candidate_positions = np.zeros((self._max_shell_candidates, 3), dtype=np.float32)
        shell_len = min(shell.shape[0], self._max_shell_candidates)
        candidate_positions[:shell_len] = shell[:shell_len]

        valid_mask = np.zeros((self._max_shell_candidates,), dtype=np.float32)
        raw_valid = self._current_candidates.mask_valid.detach().cpu().numpy().astype(np.float32)
        valid_mask[: min(raw_valid.shape[0], self._max_shell_candidates)] = raw_valid[: self._max_shell_candidates]

        current_position = self._trajectory.final_pose_world().t.detach().cpu().numpy().reshape(3).astype(np.float32)
        step_fraction = np.array([self._step_count / float(self.config.horizon)], dtype=np.float32)
        return {
            "step_fraction": step_fraction,
            "current_position": current_position,
            "history_positions": history_positions,
            "history_mask": history_mask,
            "candidate_positions": candidate_positions,
            "candidate_valid_mask": valid_mask,
        }

    def _build_info(self) -> dict[str, Any]:
        """Return diagnostic info for the current state."""

        action_mask = self.current_action_mask()
        return {
            "action_mask": action_mask,
            "step_count": self._step_count,
            "cumulative_score": None if self._trajectory is None else float(self._trajectory.cumulative_score),
            "cumulative_rri": None if self._trajectory is None else self._trajectory.cumulative_rri,
            "score_label": None if self._current_evaluation is None else self._current_evaluation.score_label,
        }

    def current_action_mask(self) -> np.ndarray:
        """Return the current shell-validity mask."""

        return (self._shell_to_valid >= 0).detach().cpu().numpy()

    def current_valid_shell_indices(self) -> np.ndarray:
        """Return the shell indices that are currently valid actions."""

        return np.flatnonzero(self.current_action_mask())

    def current_reward_scores(self) -> np.ndarray | None:
        """Return per-valid-candidate reward scores for the current shell."""

        if self._current_evaluation is None:
            return None
        return self._current_evaluation.scores.detach().cpu().numpy().astype(np.float32)

    def current_score_label(self) -> str | None:
        """Return the label attached to the current reward scores."""

        if self._current_evaluation is None:
            return None
        return self._current_evaluation.score_label

    def current_candidates_result(self) -> Any | None:
        """Return the current candidate batch for plotting/debugging."""

        return self._current_candidates

    def greedy_action(self) -> int | None:
        """Return the shell action with the highest immediate reward."""

        if self._current_evaluation is None or self._current_candidates is None:
            return None
        valid_to_shell = torch.nonzero(self._current_candidates.mask_valid, as_tuple=False).reshape(-1)
        if valid_to_shell.numel() == 0:
            return None
        best_valid = int(torch.argmax(self._current_evaluation.scores).item())
        return int(valid_to_shell[best_valid].item())

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        """Reset the episode to the configured root pose."""

        del options
        super().reset(seed=seed)
        root_pose_world = self._canonicalize_pose(self._reference_pose)
        self._trajectory = CounterfactualTrajectory(root_pose_world=root_pose_world)
        self._step_count = 0
        self._refresh_candidates(root_pose_world)
        return self._build_observation(), self._build_info()

    def step(self, action: int) -> tuple[dict[str, np.ndarray], float, bool, bool, dict[str, Any]]:
        """Advance the environment by selecting one candidate shell action."""

        assert self._trajectory is not None
        terminated = False
        truncated = False
        reward = float(self.config.invalid_action_penalty)
        selected_metrics: dict[str, float] | None = None

        action_idx = int(action)
        valid_index = -1
        if 0 <= action_idx < self._max_shell_candidates:
            valid_index = int(self._shell_to_valid[action_idx].item())

        if valid_index < 0 or self._current_evaluation is None or self._current_candidates is None:
            self._step_count += 1
            terminated = bool(self.config.terminate_on_invalid_action or self._step_count >= self.config.horizon)
            if terminated:
                self._trajectory = self._trajectory.mark_terminated()
        else:
            selected_points = self._current_evaluation.selected_point_cloud(valid_index)
            step = CounterfactualStepResult(
                step_index=self._step_count,
                candidates=self._current_candidates,
                selected_valid_index=valid_index,
                selected_shell_index=action_idx,
                selection_score=float(self._current_evaluation.scores[valid_index].item()),
                selection_score_label=self._current_evaluation.score_label,
                selection_scores=self._current_evaluation.scores.detach().clone(),
                selected_metrics=self._current_evaluation.selected_metrics(valid_index),
                metric_vectors={
                    name: values.detach().clone() for name, values in self._current_evaluation.metric_vectors.items()
                },
                selected_point_cloud_world=None if selected_points is None else selected_points.detach().clone(),
            )
            selected_metrics = dict(step.selected_metrics)
            self._trajectory = self._trajectory.with_appended_step(step)
            reward = float(step.selection_score)
            self._step_count += 1
            terminated = self._step_count >= self.config.horizon
            if not terminated:
                self._refresh_candidates(self._trajectory.final_pose_world())
                if self._current_evaluation is None:
                    terminated = True
                    self._trajectory = self._trajectory.mark_terminated()

        info = self._build_info()
        info["selected_shell_index"] = action_idx
        info["selected_valid_index"] = None if valid_index < 0 else valid_index
        if selected_metrics is not None:
            info["selected_metrics"] = selected_metrics
        return self._build_observation(), reward, terminated, truncated, info

    def render(self) -> np.ndarray:
        """Return the visited trajectory centers as a tiny RGB-array-style payload."""

        assert self._trajectory is not None
        history = self._trajectory.pose_chain_world().t.detach().cpu().numpy()
        return history.astype(np.float32)

    def close(self) -> None:
        """Close environment resources."""

    def as_rollout_result(self) -> CounterfactualRolloutResult:
        """Expose the current episode trajectory through the plotting API."""

        assert self._trajectory is not None
        score_label = "reward" if self._current_evaluation is None else self._current_evaluation.score_label
        return CounterfactualRolloutResult(
            root_pose_world=self._trajectory.root_pose_world,
            trajectories=[self._trajectory],
            horizon=self.config.horizon,
            branch_factor=1,
            beam_width=1,
            selection_policy="rl_env",
            score_label=score_label,
        )


class CounterfactualPPOConfig(TargetConfig[Any]):
    """Low-gamma PPO defaults for the basic counterfactual RL environment."""

    @property
    def target_type(self) -> type["CounterfactualPPOFactory"]:
        return CounterfactualPPOFactory

    learning_rate: float = 3e-4
    """Optimizer learning rate."""

    n_steps: int = 128
    """Rollout length per environment update."""

    batch_size: int = 64
    """Minibatch size for PPO updates."""

    n_epochs: int = 10
    """Number of PPO epochs per update."""

    gamma: float = 0.1
    """Discount factor kept small to mimic Hestia's greedy-leaning objective."""

    gae_lambda: float = 0.95
    """GAE lambda used by PPO."""

    ent_coef: float = 0.0
    """Entropy regularization coefficient."""

    vf_coef: float = 0.5
    """Value-function loss coefficient."""

    clip_range: float = 0.2
    """PPO clipping range."""

    device: str = "auto"
    """Stable-Baselines3 device selection string."""

    verbose: int = 0
    """SB3 verbosity level."""


class CounterfactualPPOFactory:
    """Factory wrapper around Stable-Baselines3 PPO."""

    @staticmethod
    def setup_target(config: CounterfactualPPOConfig, *, env: gym.Env) -> Any:
        """Instantiate a PPO agent for a counterfactual RL environment."""

        from stable_baselines3 import PPO

        return PPO(
            "MultiInputPolicy",
            env,
            learning_rate=config.learning_rate,
            n_steps=config.n_steps,
            batch_size=config.batch_size,
            n_epochs=config.n_epochs,
            gamma=config.gamma,
            gae_lambda=config.gae_lambda,
            ent_coef=config.ent_coef,
            vf_coef=config.vf_coef,
            clip_range=config.clip_range,
            device=config.device,
            verbose=config.verbose,
        )


def validate_counterfactual_env(env: gym.Env) -> None:
    """Run Stable-Baselines3 compatibility checks on a custom environment."""

    from stable_baselines3.common.env_checker import check_env

    check_env(env)


__all__ = [
    "CounterfactualPPOConfig",
    "CounterfactualPPOFactory",
    "CounterfactualRLEnv",
    "CounterfactualRLEnvConfig",
    "validate_counterfactual_env",
]
