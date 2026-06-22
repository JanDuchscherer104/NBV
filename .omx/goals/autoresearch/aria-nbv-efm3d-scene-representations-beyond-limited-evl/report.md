# ARIA-NBV Autoresearch: EFM3D Scene Representations Beyond EVL Voxel Extent

This compatibility report mirrors the active goal artifact at:

`.omx/goals/autoresearch/aria-nbv-efm3d-scene-representations-beyond-limi/report.md`

Recommendation: sparse actor-visible semidense/fused point bank plus compressed DINO descriptors from logged observations. EVL remains the local OBB/support anchor; it should not be treated as complete scene memory. Actor-visible descriptors must not use GT meshes, GT OBB crops, oracle RRI, or all-candidate rendered depth. Critic verdict: pass.
