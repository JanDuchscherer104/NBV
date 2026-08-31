#import "../../../shared/macros.typ": *
#import "../../../shared/tables.typ": publication-table, index-cell

== Dataset and Ecosystem Choice <sec:thesis-dataset-ecosystem>

ARIA-NBV uses the Project Aria ecosystem because its components jointly define
the observation, supervision, and evaluation surfaces required by the thesis.
Project Aria provides the sensing and geometry contract: its streams are
tightly calibrated and time-aligned, and its Machine Perception Services (MPS)
provide trajectories, online calibration, and semi-dense point clouds with
observation lineage @projectaria-engel2023. This makes Project Aria a suitable
reference for what an Aria-native decision-time state may contain. It does not,
however, establish an online next-best-view controller, on-device compute
feasibility, or real-world reconstruction performance.

// evidence:
// - @projectaria-engel2023 -> docs/literature/tex-src/arXiv-project-aria/device.tex:15-17 (calibrated, time-aligned sensing and no on-device-compute claim)
// - @projectaria-engel2023 -> docs/literature/tex-src/arXiv-project-aria/tools.tex:9-13 (MPS products, VRS, and tools)
// - @projectaria-engel2023 -> docs/literature/tex-src/arXiv-project-aria/mps.tex:48-50 (partial semi-dense reconstruction and observation lineage)

Aria Synthetic Environments (ASE) supplies a controlled synthetic dataset
aligned with the Aria observation surface used here. It contains 100,000
procedurally generated indoor scenes with one outward-facing simulated RGB
stream, ground-truth trajectories, MPS-style semi-dense maps, depth, instance
annotations, and structured scene descriptions @ProjectAria-ASE-2025.
The release totals more than 58 million RGB images, 67 trajectory-days, 7,800
trajectory-kilometres, and about 23 TB; those figures establish useful scale,
not a claim that all data are in the local experimental snapshot.
EFM3D augments the ASE substrate with 3D oriented bounding-box metadata and
releases ground-truth meshes for its simulated validation set
@EFM3D-straub2024. These assets make repeatable target-task construction and
mesh-based offline evaluation possible, but they remain privileged supervision
or evaluation evidence. In particular, ground-truth depth, segmentation, boxes,
and meshes do not become actor-visible merely because an adapted data snippet
stores them beside logged streams.

// evidence:
// - @ProjectAria-ASE-2025 -> https://facebookresearch.github.io/projectaria_tools/docs/open_datasets/aria_synthetic_environments_dataset (overview and dataset-contents sections, checked 2026-08-31)
// - @ProjectAria-ASE-2025 -> https://facebookresearch.github.io/projectaria_tools/docs/open_datasets/aria_synthetic_environments_dataset/ase_data_format (field roles and GT-trajectory distinction, checked 2026-08-31)
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/dataset.tex:15-18 (ASE OBB metadata)
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/dataset.tex:30-30 (simulated-validation ground-truth meshes)

#figure(
  image(
    "../../figures/ase_aria_atek_roles.svg",
    width: 100%,
  ),
  caption: [Roles of Project Aria, ASE, EFM3D, and ATEK in the offline experiment. The upper layer assigns each product its observation, data-substrate, representation, or interface contribution; the lower band separates actor-visible evidence from privileged supervision and evaluation assets. This conceptual contract figure is grounded in the cited source interfaces. @projectaria-engel2023 @ProjectAria-ASE-2025 @EFM3D-straub2024 @ATEK-about-2025],
) <fig:thesis-aria-atek-roles>

=== Dataset Scale and Ground-Truth Mesh Scope

EFM3D releases ground-truth meshes for its simulated validation setting. The
local ATEK--EFM inventory used for this mesh-evaluation protocol contains 100
scene directories, and the local GT-mesh inventory has the same 100 scene IDs
(recorded in the immutable gallery manifest). This is $100 / 100,000 = 0.1$
percent of the full ASE scene count and a deliberately bounded local evaluation
scope. The logarithmic
comparison in @fig:thesis-ase-mesh-scope makes the three-order-of-magnitude
gap explicit, preventing the 100-scene result from being read as a property of
the entire 100,000-scene release.

// evidence:
// - @ProjectAria-ASE-2025 -> https://facebookresearch.github.io/projectaria_tools/docs/open_datasets/aria_synthetic_environments_dataset (100,000 scenes and aggregate scale, checked 2026-08-31)
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/dataset.tex:30-30 (simulated-validation ground-truth meshes)
// - docs/contents/ase_dataset.qmd:42-52 (100 local scene directories and 4,608 local snippet windows)
// - docs/typst/thesis/data/ase-figure-gallery/manifest.json (schema v1: matching 100-scene ATEK and GT-mesh inventories; exact IDs and mesh-statistics digest)

#figure(
  image(
    "../../figures/ase_gt_mesh_subset_scale.svg",
    width: 100%,
  ),
  caption: [Scale of the released ASE corpus and the local ATEK--EFM mesh-evaluation snapshot. A logarithmic scene-count axis locates 100 local scene directories against 100,000 ASE scenes; the snapshot is 0.1% of the corpus (a 1,000:1 ratio). This schematic quantitative comparison combines the cited ASE release size with the dated local inventory. @ProjectAria-ASE-2025],
) <fig:thesis-ase-mesh-scope>

The local ATEK--EFM snapshot used to inspect the mesh subset contains 100
scenes and 4,608 snippet windows. A scan dated 2025-12-31 found 8--152 windows
per scene (median 40; mean 46.1; tenth and ninetieth percentiles 8 and 88.8).
The percentile summary in @fig:thesis-ase-local-snippets is an operational
statistic of that local snapshot, rather than an estimate of the
complete ASE release or of a future ATEK export.

// evidence:
// - docs/contents/ase_dataset.qmd:42-52 (local snapshot method, date, and per-scene statistics)

#figure(
  image(
    "../../figures/ase_local_snapshot_summary.svg",
    width: 100%,
  ),
  caption: [Summary of per-scene availability in the locally scanned ATEK--EFM snapshot (scan date: 2025-12-31). The range, percentile interval, median, and mean characterize 4,608 windows across 100 scenes. This data-derived figure scopes local experimental availability, not the global ASE distribution.],
) <fig:thesis-ase-local-snippets>

ATEK supplies a standardized data and evaluation interface rather than another
source of scientific truth. It preprocesses Aria recordings into
PyTorch-compatible data, offers WebDataset-backed stores, and provides
standardized object-detection and surface-reconstruction evaluation
@ATEK-about-2025 @ATEK-DataStore-2025.
Its ASE `efm` and `efm_eval` configurations connect the selected data substrate
to the EFM3D representation and evaluation path. ATEK's surface-reconstruction
task evaluates predicted meshes against ground-truth meshes; it neither defines
the target-specific relative reconstruction improvement used here nor supplies
an NBV policy benchmark @ATEK-SurfaceRecon-2025.

// evidence:
// - @ATEK-about-2025 -> https://facebookresearch.github.io/projectaria_tools/docs/ATEK/about_ATEK (four workflow features, checked 2026-08-31)
// - @ATEK-DataStore-2025 -> https://github.com/facebookresearch/ATEK/blob/main/docs/ATEK_Data_Store.md (ASE efm/efm_eval WebDataset configurations and access conditions, checked 2026-08-31)
// - @ATEK-SurfaceRecon-2025 -> https://github.com/facebookresearch/ATEK/blob/main/docs/ML_task_surface_recon.md (input/evaluation contract and mesh metrics, checked 2026-08-31)

#figure(
  publication-table(
    columns: (0.74fr, 1.26fr, 1.36fr),
    header: ([*Requirement*], [*Aria ecosystem contribution*], [*Boundary for this thesis*]),
    rows: (
      (index-cell([Egocentric observation]), [Project Aria calibration, time alignment, poses, and MPS semi-dense evidence.], [Defines admissible evidence; it does not demonstrate an online NBV agent.]),
      (index-cell([Controlled supervision]), [ASE simulated Aria sequences and EFM3D 3D-task annotations.], [GT geometry and annotations remain label or evaluation assets.]),
      (index-cell([Representation path]), [EFM3D/EVL lifts posed, calibrated Aria streams and semi-dense priors into local 3D evidence.], [EVL is an observation/target-support provider, not the planner or a complete scene memory.]),
      (index-cell([Standardized interface]), [ATEK preprocessing, WebDataset stores, and task evaluators.], [ATEK does not define candidate generation, counterfactual transitions, target-RRI, or NBV evaluation.]),
    ),
  ),
  caption: [Requirements-based rationale for the Project Aria, ASE, EFM3D, and ATEK substrate. The layers are complementary rather than interchangeable.],
) <tab:thesis-dataset-ecosystem>

// evidence:
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/method.tex:4-4,37-39 (EVL input and geometric-prior roles)
// - @ATEK-about-2025 -> https://facebookresearch.github.io/projectaria_tools/docs/ATEK/about_ATEK (preprocessing, datastore, and standardized-evaluation roles, checked 2026-08-31)

This is a requirements-based choice, not a claim that the selected ecosystem is
universally superior. A real-recording-only study could improve sensor and
domain realism but would need a separately controlled target and reconstruction
reference; an unrelated indoor simulator would need a separately justified
Aria calibration, tooling, and representation path. ASE instead creates
synthetic-domain and trajectory distribution-shift risks, MPS-style geometry is
partial, data access and scale constrain feasible experiments, and the released
meshes cover only the stated validation scope. The ecosystem is therefore a
substrate on which a leakage-controlled offline protocol can be constructed,
not itself a leakage guarantee. The current ground-truth-derived target route is
an oracle-assisted control; the core actor-visible comparison remains gated on
an observation-derived target protocol as specified in @ssec:rq3. ARIA-NBV
itself remains responsible for target identity, hard-valid finite candidates,
selected-observation transitions, counterfactual labels, and target-specific
policy evaluation. The next section turns this division into the decision-time
actor/oracle boundary.

// evidence:
// - @projectaria-engel2023 -> docs/literature/tex-src/arXiv-project-aria/mps.tex:48-50 (partial MPS reconstruction)
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/dataset.tex:30-30 (validation-scope mesh release)
// - @ATEK-DataStore-2025 -> https://github.com/facebookresearch/ATEK/blob/main/docs/ATEK_Data_Store.md (access workflow and expiring URLs, checked 2026-08-31)
