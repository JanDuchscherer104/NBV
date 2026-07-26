# LRZ And Upstream Source Pointers

Use these links when refreshing LRZ/Slurm/Pyxis guidance. Local notes are
operator aids; these sources decide current cluster behavior when they conflict.

## LRZ AI Systems

- AI Systems overview: <https://doku.lrz.de/lrz-ai-systems-11484278.html>
- Compute and partitions: <https://doku.lrz.de/2-compute-10746641.html>
- Storage and DSS policy: <https://doku.lrz.de/3-storage-10746646.html>
- Enroot: <https://doku.lrz.de/4-enroot-1897007352.html>
- Slurm overview: <https://doku.lrz.de/5-slurm-1897076524.html>
- Interactive Slurm jobs:
  <https://doku.lrz.de/5-1-slurm-interactive-jobs-1898974515.html>
- Batch Slurm jobs:
  <https://doku.lrz.de/5-2-slurm-batch-jobs-introduction-1898974516.html>
- Multi-GPU Slurm jobs:
  <https://doku.lrz.de/5-3-slurm-batch-jobs-multi-gpu-1898974517.html>
- Multi-node Slurm jobs:
  <https://doku.lrz.de/5-4-slurm-batch-jobs-multi-node-1898714389.html>

Check live Slurm output before relying on partition names, limits, GPU counts,
QOS rules, or examples.

## Upstream Slurm And Containers

- Slurm documentation: <https://slurm.schedmd.com/documentation.html>
- Slurm GRES guide: <https://slurm.schedmd.com/gres.html>
- Pyxis upstream: <https://github.com/NVIDIA/pyxis>
- Enroot upstream: <https://github.com/NVIDIA/enroot>

Use LRZ pages first for LRZ-specific policy. Use upstream Slurm/Pyxis pages for
syntax and behavior that LRZ delegates to those tools.
