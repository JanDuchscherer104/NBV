"""Emit a hash-only CUDA candidate-generation receipt for one checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch
from efm3d.aria.obb import ObbTW

from aria_nbv.configs import PathConfig
from aria_nbv.data_handling import AseEfmDatasetConfig
from aria_nbv.oracle.pipelines.rollout_dataset import RolloutDatasetWriterConfig
from aria_nbv.pose_generation import CandidateGenerationRuntimeContext
from aria_nbv.targets import TargetDescriptor
from aria_nbv.utils import Verbosity


def _tensor_receipt(value: torch.Tensor) -> dict[str, object]:
    canonical = value.detach().cpu().contiguous()
    nan_mask = (
        torch.isnan(canonical)
        if canonical.is_floating_point()
        else torch.zeros_like(canonical, dtype=torch.bool)
    )
    finite = (
        canonical[~nan_mask] if canonical.is_floating_point() else canonical.reshape(-1)
    )
    return {
        "dtype": str(canonical.dtype),
        "shape": list(canonical.shape),
        "raw_sha256": hashlib.sha256(canonical.numpy().tobytes()).hexdigest(),
        "nan_mask_sha256": hashlib.sha256(nan_mask.numpy().tobytes()).hexdigest(),
        "finite_sha256": hashlib.sha256(
            finite.contiguous().numpy().tobytes()
        ).hexdigest(),
    }


def _load_sample():
    paths = PathConfig(root=Path("/home/jd/repos/ARIA-NBV"))
    config = AseEfmDatasetConfig(
        paths=paths,
        scene_ids=["81283"],
        batch_size=None,
        load_meshes=True,
        require_mesh=True,
        mesh_simplify_ratio=0.02,
        device="cpu",
        verbosity=Verbosity.QUIET,
        is_debug=False,
    )
    return next(iter(config.setup_target()))


def _nearest_target(sample) -> tuple[TargetDescriptor, float]:
    assert sample.obbs is not None
    obbs = sample.obbs.obbs
    valid = ~obbs.get_padding_mask()
    flat = ObbTW(obbs.tensor().reshape(-1, 34)[valid.reshape(-1)])
    reference = sample.trajectory.final_pose
    distances = torch.linalg.norm(
        flat.T_world_object.t - reference.t.reshape(1, 3), dim=1
    )
    target = flat[int(torch.argmin(distances).item())]
    relative = reference.inverse() @ target.T_world_object
    descriptor = TargetDescriptor(
        sem_id=int(target.sem_id.reshape(-1)[0].item()),
        class_name="real-scene-obb",
        pose_world_object=tuple(
            float(value)
            for value in target.T_world_object.tensor().reshape(-1).tolist()
        ),
        extents_m=tuple(
            float(value) for value in target.bb3_diagonal.reshape(-1).tolist()
        ),
        relative_pose_reference_object=tuple(
            float(value) for value in relative.tensor().reshape(-1).tolist()
        ),
    )
    return descriptor, float(distances.min().item())


def _rng_state_receipt() -> dict[str, object]:
    return {
        "cpu": _tensor_receipt(torch.random.get_rng_state()),
        "cuda": [_tensor_receipt(state) for state in torch.cuda.get_rng_state_all()],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    sample = _load_sample()
    descriptor, target_distance = _nearest_target(sample)
    mixture = RolloutDatasetWriterConfig.from_toml(args.config).candidate_mixture
    payload = mixture.model_dump()
    payload["base"]["device"] = "cuda"
    payload["base"]["seed"] = 73
    generator = type(mixture).model_validate(payload).setup_target()
    runtime = CandidateGenerationRuntimeContext(descriptor=descriptor)

    torch.manual_seed(991)
    torch.cuda.manual_seed_all(991)
    torch.cuda.synchronize()
    rng_before = _rng_state_receipt()
    result = generator.generate_from_typed_sample(sample, runtime_context=runtime)
    torch.cuda.synchronize()
    rng_after = _rng_state_receipt()

    receipt = {
        "torch_version": torch.__version__,
        "cuda_runtime_version": torch.version.cuda,
        "cudnn_version": torch.backends.cudnn.version(),
        "gpu": torch.cuda.get_device_name(0),
        "target_distance_m": target_distance,
        "attempted": int(result.mask_valid.numel()),
        "valid": int(result.mask_valid.sum().item()),
        "fields": {
            "shell_poses": _tensor_receipt(result.shell_poses.tensor()),
            "poses_world_cam": _tensor_receipt(result.views.tensor()),
            "mask_valid": _tensor_receipt(result.mask_valid),
            "strategy_id": _tensor_receipt(result.strategy_id),
            "position_id": _tensor_receipt(result.position_id),
            "mixture_id": _tensor_receipt(result.mixture_id),
            "sampler_probability": _tensor_receipt(result.sampler_probability),
            "position_pair_id": _tensor_receipt(result.position_pair_id),
            "gaze_variant_id": _tensor_receipt(result.gaze_variant_id),
        },
        "masks": {
            name: _tensor_receipt(value) for name, value in sorted(result.masks.items())
        },
        "extras": {
            name: _tensor_receipt(value)
            for name, value in sorted(result.extras.items())
            if torch.is_tensor(value)
        },
        "component_name": list(result.component_name or ()),
        "rng_before": rng_before,
        "rng_after": rng_after,
        "rng_state_unchanged": rng_before == rng_after,
    }
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
