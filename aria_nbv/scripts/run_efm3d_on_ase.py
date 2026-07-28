# ensure efm3d is importable
from pathlib import Path

from efm3d.inference.pipeline import run_one  # noqa: E402


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    data_root = repo_root / ".data" / "ase_efm"
    mesh_root = repo_root / ".data" / "ase_meshes"
    ckpt = repo_root / ".logs" / "ckpts" / "model_lite.pth"
    model_cfg = (
        repo_root / ".configs/models/evl/evl_inf_desktop.yaml"  # instead of evl_inf.yaml
    )
    out_root = repo_root / ".logs" / "efm3d_inference"

    out_root.mkdir(parents=True, exist_ok=True)

    # sanity
    assert ckpt.exists(), f"Missing checkpoint: {ckpt}"
    assert model_cfg.exists(), f"Missing model cfg: {model_cfg}"

    for scene_dir in sorted(data_root.glob("*")):
        if not scene_dir.is_dir():
            continue
        scene_id = scene_dir.name
        mesh_path = mesh_root / f"scene_ply_{scene_id}.ply"
        if not mesh_path.exists():
            print(f"[WARN] No mesh for scene {scene_id}, skipping.")
            continue

        print(f"[EFM3D] Running inference on scene {scene_id}")
        run_one(
            data_path=str(scene_dir),
            model_ckpt=str(ckpt),
            model_cfg=str(model_cfg),
            max_snip=50,  # adjust snippets
            snip_stride=0.1,  # as in eval.py
            voxel_res=0.04,
            output_dir=str(out_root),
        )


if __name__ == "__main__":
    main()
