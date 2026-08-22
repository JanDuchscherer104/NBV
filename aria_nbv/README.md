# `aria-nbv` Python Package

`aria-nbv` provides the executable data, oracle-RRI, finite-candidate rollout,
inspection, VIN, and training infrastructure for the ARIA-NBV research project.
It requires Python 3.11; full
[ASE](https://facebookresearch.github.io/projectaria_tools/docs/open_datasets/aria_synthetic_environments_dataset)
generation, [PyTorch3D](https://github.com/facebookresearch/pytorch3d) rendering,
and training are designed for the repository's Linux environment with CUDA
12.1.

- [Project overview](https://github.com/JanDuchscherer104/ARIA-NBV)
- [Setup and data requirements](https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/SETUP.md)
- [Published documentation and API reference](https://janduchscherer104.github.io/ARIA-NBV/)

Package behavior is owned by source, tests, and active configuration in the
repository. The active Typst thesis owns current scientific claims and research
status.

## Evidence and Data Lineage

ARIA-NBV keeps source evidence, one-step supervision, and multi-step replay in
separate physical stores. Raw or upstream-managed assets from
[ASE](https://facebookresearch.github.io/projectaria_tools/docs/open_datasets/aria_synthetic_environments_dataset),
[ATEK](https://github.com/facebookresearch/ATEK), and
[EFM3D](https://github.com/facebookresearch/efm3d) remain external;
`vin_offline` stores immutable one-step evidence; `rollouts.zarr` stores compact
factual replay plus stable references to its source rows. Joined readers expose
the modalities needed for one-step VIN, finite-horizon `Q_H`, and inspection
without copying raw streams, full meshes, or backbone tensors into every
rollout.

![ARIA-NBV evidence and two-store lineage](https://raw.githubusercontent.com/JanDuchscherer104/ARIA-NBV/main/docs/figures/diagrams/data_handling/mermaid/package_data_lineage.svg)

The arrow labels identify the principal data products crossing each boundary;
they are not complete schema definitions. The
[data-handling runbook](aria_nbv/data_handling/README.md) and
[rollout contract](aria_nbv/rollouts/README.md) own the detailed formats and
validation rules.
