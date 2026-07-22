# EFM3D And ARIA Workloads On LRZ

Use this when a task mentions EFM3D, ASE, ATEK, EVL, upstream EFM3D training, or
using facebookresearch/efm3d examples as LRZ input.

## Upstream Facts

- EFM3D is a PyTorch benchmark for Project Aria 3D object detection and surface
  regression, with EVL baseline code and distributed training support.
- EFM3D uses ASE training/eval data, ADT/AEO evaluation data, and ATEK/WebDataset
  sequence formats.
- Full ASE training data is about 7 TB. Small training subsets and one-sequence
  eval downloads exist for smoke tests.
- Upstream EFM3D recommends conda for its own environment and also documents pip
  paths. Training builds an mmdetection3d CUDA extension.
- Upstream `sbatch_run.sh` trains with 2 nodes, 1 task per node, `--gres=gpu:8`,
  and `torchrun --nproc_per_node 8`.

## LRZ Translation Rules

- Put EFM3D/ASE/ATEK data under `$ARIA_DSS/data/raw/` or
  `$ARIA_DSS/data/processed/`; do not stage full ASE under `$HOME`.
- Put TensorBoard, W&B, Slurm logs, checkpoints, local `.sqsh` images, and Python
  package/model caches under `$ARIA_DSS`.
- Do not copy EFM3D `--gres=gpu:8` blindly. Current LRZ H100 and HGX A100
  partitions expose 4 GPUs per node; DGX A100 exposes 8 GPUs per node. Verify
  with `sinfo` before writing the final request.
- For LRZ jobs, use Pyxis/containerized workloads. Inside the container, using
  conda or pip is acceptable when the workload requires it, but caches and build
  artifacts should live on DSS.
- Build CUDA extensions inside the same container/runtime family used for the
  job that will run them.
- Start with one ASE eval sequence or a small ASE training subset before
  requesting multi-node training resources.

## Good Progression

1. Confirm DSS quota is compatible with the planned data subset.
2. Download one eval sequence or a small ASE subset to `$ARIA_DSS`.
3. Run single-GPU container smoke with `nvidia-smi` and an import check.
4. Run the smallest EFM3D inference/training command that exercises the data
   path and CUDA extension.
5. Scale to single-node multi-GPU.
6. Scale to multi-node only after logs prove single-node execution works.

## Handoffs

- Use `dataset-cache-ops` for ARIA-owned dataset/cache contracts.
- Use the nearest rollout package and thesis owners for rollout or `Q_H`
  workload semantics.
- Use the selected diagnostic capability for concrete failed EFM3D/ARIA job
  logs.
