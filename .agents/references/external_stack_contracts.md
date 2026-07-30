# External Stack Contracts

This is the maintained internal developer distillation for the upstream stack
used by ARIA-NBV. It replaces the deprecated raw public pages archived under
`.agents/archive/docs/ext-impl/`.

Keep public thesis docs focused on ARIA-NBV evidence. Use this reference when
editing package docstrings, debugging dataset/geometry contracts, or checking
which upstream ATEK, EFM3D, and Project Aria concepts are actually relevant.

## ATEK

ATEK is the tensorized ASE data pipeline ARIA-NBV consumes through
`AseEfmDataset` and the EFM adaptor path.

Retain these contracts:

- WebDataset shards provide snippet-level camera streams, trajectory poses,
  semi-dense points, online calibration, depth/GT fields where available, and
  scene/snippet identity needed for mesh pairing and lineage.
- Flattened ATEK keys are remapped into EFM-style keys through
  `EfmModelAdaptor`; ARIA-NBV should not invent parallel schema names when the
  adaptor already owns the conversion.
- Surface metrics from ATEK remain useful as a source reference for
  accuracy/completeness and point-to-mesh distance semantics, but current
  oracle code should expose ARIA-NBV's own metric contract through
  `aria_nbv.rri_metrics`.
- OBB GT and evaluation helpers are relevant to V0 target-RRI sanity checks and
  V1 observed-target / GT-label matching. GT OBBs are label/evaluation assets,
  not actor-visible target inputs in the main protocol.

Do not carry forward:

- CubeRCNN/SAM2 adaptor details unless a task explicitly touches those models.
- Full file-by-file vendor catalogs.
- Wikipedia primers, tutorial snippets, local host paths, terminal tree dumps,
  or speculative "underused" feature lists.

## EFM3D And EVL

EFM3D is the egocentric 3D state substrate. ARIA-NBV uses EVL outputs and EFM
geometry wrappers as actor-visible evidence for candidate scoring and rollout
state summaries.

Retain these contracts:

- Use `PoseTW` and `CameraTW` for pose/camera data. Avoid raw matrices in
  package contracts unless they are explicitly boundary payloads.
- Preserve frame direction in names and docstrings. The most important current
  conventions are world-from-camera candidate poses, world-from-rig reference
  poses, `CameraTW` intrinsics/extrinsics, and display-only CW90 corrections.
- `ObbTW` predictions or tracked boxes are actor-visible target hypotheses for
  V1. Matched GT OBB crops define target-RRI labels and evaluation only.
- Current ARIA-NBV package code consumes these EFM key families:
  `ARIA_IMG`, `ARIA_CALIB`, `ARIA_IMG_TIME_NS`, `ARIA_FRAME_ID`,
  `ARIA_DISTANCE_M`, `ARIA_DEPTH_TIME_NS`, `ARIA_POSE_T_WORLD_RIG`,
  `ARIA_POSE_TIME_NS`, `ARIA_SNIPPET_T_WORLD_SNIPPET`,
  `ARIA_POINTS_WORLD`, `ARIA_POINTS_DIST_STD`,
  `ARIA_POINTS_INV_DIST_STD`, `ARIA_POINTS_TIME_NS`,
  `ARIA_POINTS_VOL_MIN`, `ARIA_POINTS_VOL_MAX`, `ARIA_OBB_PADDED`,
  `ARIA_OBB_FREQUENCY_HZ`, `ARIA_OBB_SEM_ID_TO_NAME`, and EVL prediction
  outputs such as `ARIA_OBB_PRED`, `ARIA_OBB_PRED_VIZ`,
  `ARIA_OBB_PRED_SEM_ID_TO_NAME`, and `ARIA_OBB_PRED_PROBS_FULL`.
  Treat this as a compact contract snapshot, not a replacement for source
  imports in `aria_nbv.data_handling.ase_efm.views`, `aria_nbv.vin.backbone_evl`,
  and `aria_nbv.rerun_inspector`.
- EVL voxel evidence is local and checkpoint/config dependent. Any rollout,
  offline store, or Q_H payload using EVL fields needs source/config/checkpoint
  hashes to avoid mixing incomparable state.
- The relevant utility families are ray/depth/point-cloud conversion, voxel
  support/free-space evidence, mesh distance/evaluation references, OBB
  matching/tracking support, and EVL inference outputs.

Do not carry forward:

- Exhaustive `ARIA_*` constant tables in public docs. Document only consumed
  keys at owning package surfaces such as `EfmSnippetView`, `VinSnippetView`,
  `EvlBackboneOutput`, rollout traces, and target records.
- Claims that EVL predictions are ground truth. They are actor-visible evidence.
- Differentiable pose-refinement or occupancy-supervision ideas as current
  thesis requirements unless they become explicit agents-db work.

## Project Aria Tools

Project Aria Tools define the upstream device, VRS, calibration, MPS, and ASE
reader ecosystem.

Retain these contracts:

- VRS and MPS are provenance for calibrated egocentric streams, trajectories,
  online calibration, semi-dense points, and related perception products.
- ARIA-NBV's current thesis path primarily consumes ASE/ATEK/EFM tensorized
  snippets rather than raw VRS recordings.
- MPS/semi-dense points are observed reconstruction evidence. ASE meshes and GT
  annotations are oracle supervision and evaluation assets.

Do not carry forward:

- General Project Aria tutorial code, downloader walkthroughs, or full tool
  tree listings in public thesis docs.
- Raw Project Aria examples that bypass ARIA-NBV's typed dataset and geometry
  contracts.

## Package Docstring Follow-Up Targets

When the docstring enrichment todo is implemented, prioritize:

- `aria_nbv.data_handling.ase_efm.views`: consumed EFM keys, units, frames, and OBB
  actor-visible versus GT-label boundaries.
- `aria_nbv.data_handling.efm_dataset`: ATEK shard, EFM adaptor, mesh pairing,
  and scene/snippet filtering contracts.
- `aria_nbv.pose_generation`: candidate pose frame semantics, validity masks,
  and target-aware candidate mode boundaries.
- `aria_nbv.rendering`: PyTorch3D depth convention, backprojection frame, and
  camera context requirements.
- `aria_nbv.rri_metrics`: scene and target RRI metric semantics, crop failure,
  and invalidity-not-low-quality boundaries.
- `aria_nbv.vin`: EVL evidence provenance, target-conditioned scorer inputs,
  and calibration/ranking output semantics.
