# ARIA-Specific Context7 Routes

Use these handles only when deterministic local inspection cannot answer an
external-stack question. They are discovery aids, not contract owners.

- `/facebookresearch/atek`: ASE/ATEK snippet and adaptor semantics.
- `/websites/facebookresearch_github_io_projectaria_tools`: calibration,
  trajectories, VRS, and pose-tool behavior.
- `/facebookresearch/efm3d`: EFM3D tensor wrappers and backbone interfaces.

Start with vendored source and the owning ARIA package. Generic dependency IDs
belong in the `context7_refs` of the skill that needs them and are verified
against Context7 at use time.
