// This file defines slides for the ASE, EFM3D & EVL talk.
// It is based on the definitely-not-isec-theme provided in the skeleton.

#import "@preview/definitely-not-isec-slides:1.0.1": *
#import "@preview/muchpdf:0.1.1": muchpdf

#let fig_path = "/figures/"

#show: definitely-not-isec-theme.with(
  aspect-ratio: "16-9",
  slide-alignment: top,
  progress-bar: true,
  institute: [HM],
  logo: [#image(fig_path + "hm-logo.svg", width: 2cm)],
  config-info(
    title: [ASE, EFM3D & EVL: Datasets, Models & Tools for NBV],
    subtitle: [Towards Relative Reconstruction Metrics for Next-Best-View],
    authors: ([*Jan Duchscherer*]),
    extra: [VCML Seminar WS24/25],
    footer: [
      #grid(
        columns: (1fr, auto, 1fr),
        align: bottom,
        align(left)[Jan Duchscherer],
        align(center)[VCML Seminar WS24/25],
        align(right)[#datetime.today().display("[day padding:none]. [month repr:short] [year]")],
      )
    ],
    download-qr: "",
  ),
  config-common(
    handout: false,
  ),
  config-colors(
      primary: rgb("fc5555"),
  ),
)

// Set global text size
#set text(size: 17pt)

// Style links to be blue and underlined
#show link: set text(fill: blue)
#show link: it => underline(it)

// The title slide summarises the talk.
#title-slide()

// ASE Section
#section-slide(title: [Aria Synthetic Environments], subtitle: [Dataset for Egocentric 3D Scene Understanding])[
  #figure(image(fig_path + "scene-script/ase_modalities.jpg", width: 80%), caption: [@SceneScript-avetisyan2024])
]

// ASE overview slide
#slide(title: [ASE Dataset Overview])[
 #grid(columns: (1fr, 1fr), gutter: 1.5cm,
   [#text(size: 16pt)[
  *Dataset Content*
  - 100,000 unique multi-room interior scenes
  - \~2-min egocentric trajectories per scene
  - Populated with ~8,000 3D objects
  - Aria camera & lens characteristics

  *Ground Truth Annotations*
  - 6DoF trajectories
  - RGB-D frames
  - 2D panoptic segmentation
  - Semi-dense SLAM PC w/ visibility info
  - 3D floor plan (SceneScript SSL format)
  - _GT meshes_ as `.ply` files

  *Key Resources*
  - Project Aria Tools for data access
  - #link("https://facebookresearch.github.io/projectaria_tools/docs/open_datasets/aria_synthetic_environments_dataset")[ASE documentation] @ProjectAria-ASE-2025 @SceneScript-avetisyan2024
  ]],
    [
    #v(1em)
    #figure([#image(fig_path + "scene-script/ase_primitives.jpg", width: 90%)
    #v(0.5em)
    #image(fig_path + "efm3d/gt_mesh.jpg", width: 90%)], caption: [@SceneScript-avetisyan2024])
    ]
  )
]

// ASE Dataset Structure
#slide(title: [ASE Dataset Structure])[
  #text(size: 10pt)[
  ```
  scene_id/
  ├── ase_scene_language.txt          # Ground truth scene layout in SSL format
  ├── object_instances_to_classes.json # Mapping from instance IDs to semantic classes
  ├── trajectory.csv                   # 6DoF camera poses along the egocentric path
  ├── semidense_points.csv.gz          # Semi-dense 3D point cloud from MPS SLAM
  ├── semidense_observations.csv.gz    # Point observations (which images see which points)
  ├── rgb/                             # RGB image frames
  │   ├── 000000.png
  │   └── ...
  ├── depth/                           # Ground truth depth maps
  │   ├── 000000.png
  │   └── ...
  └── instances/                       # Instance segmentation masks
      ├── 000000.png
      └── ...
  ```
  ]
]

// EFM3D Section
#section-slide(title: [EFM3D Benchmark], subtitle: [3D Egocentric Foundation Model: \ Egocentric Voxel Lifting (EVL)
    #figure(muchpdf(read(fig_path + "efm3d/EFM3D_teaser_v1.pdf", encoding: none), width: 27cm), caption: [@EFM3D-straub2024])
  ])

#slide(title: [EFM3D & EVL])[
  *EFM3D Tasks*
  - 3D object detection
  - 3D surface regression (occupancy volumes)
    - on ASE, ADT#footnote[#text(size: 12pt)[Aria Digital Twin]], AEO#footnote[#text(size: 12pt)[Aria Everyday Objects: small-scale, real-world w/ 3D OBBs]] datasets

  *EVL Architecture*
  - Utilizes _all_ available egocentric modalities:
    + multiple (rectified) RGB, grayscale, and semi-dense points inputs
    + camera intrinsics and extrinsics
  - _16.7M trainable_ + _86.6M frozen_ params
  - Inherits foundational capabilities from frozen 2D model (DinoV2.5) by lifting 2D features to 3D @EFM3D-straub2024

  #figure(muchpdf(read(fig_path + "efm3d/efm3d_arch_v1.pdf", encoding: none)), caption: [@EFM3D-straub2024])
]

// ATEK Section
#section-slide(
  title: [ATEK Toolkit],
  subtitle: [
    Streamlined ML Workflows for Aria Datasets
    #figure(image(fig_path + "atek/overview.png", width: 20cm), caption: [@ATEK-Repo])
])//[
  // #align(center)[
  //   #text(size: 14pt)[


  //     #v(2em)

  //     #grid(columns: (1fr, 1fr, 1fr), gutter: 2em,
  //       [*Data Store*\ PyTorch\ WebDataset],
  //       [*Evaluation*\ Mesh Metrics\ Benchmarks],
  //       [*Training*\ Pre-processed\ Splits]
  //     )
  //   ]
  // ]
// ]

#slide(title: [ATEK Toolkit])[
  *ATEK Data Store*
  - Pre-processed for various tasks $->$ ready for PyTorch training
  - Local download or cloud streaming
  - Eval metrics (accuracy, completeness, F-score) $->$ adaptation for RRI
  - Integration w\/ Meta's MPS and
  - Various example notebooks

  *Provided Models*
  - _Cube R-CNN_ @omni3d-cubercnn-brazil2023 for OBBs, _EFM_ @EFM3D-straub2024 for OBBs & surface reconstruction

  *Resources*
  - #link("https://github.com/facebookresearch/ATEK")[ATEK GitHub] @ATEK-about-2025
  - #link("https://www.youtube.com/watch?v=m6oFLfYUpoM&t=7242s")[ECCV 2024 Tutorial: Egocentric Research with Project Aria]
]

// VIN-NBV Overview
#slide(title: [VIN-NBV: Learning-Based Next-Best-View])[
  *Key Innovation* @VIN-NBV-frahm2025
  - First NBV method to directly optimize *reconstruction quality* (not coverage)
  - Predicts *Relative Reconstruction Improvement (RRI)* without capturing new images
  - 30% improvement over coverage-based baselines
  - Trained 24h on 4 A6000 GPUs (no pre-trained backbone)

  *Relative Reconstruction Improvement (RRI)*

  For a candidate view $q$, RRI quantifies expected improvement:

  $ "RRI"(q) = ("CD"(cal(P)_"base", cal(P)_"GT") - "CD"(cal(P)_("base" union q), cal(P)_"GT")) / ("CD"(cal(P)_"base", cal(P)_"GT")) $

  - Range: $[0, 1]$ where higher = better view
  - Normalized by current error → scale-independent
  - Chamfer Distance (CD) measures reconstruction quality

  *VIN Architecture*

  Predicts RRI from current reconstruction state:

  $ hat("RRI")(q) = "VIN"_theta (cal(P)_"base", C_"base", C_q) $

  - Input: Partial point cloud + camera poses
  - Features: Surface normals, visibility counts, depth, coverage
  - Output: RRI ranking via ordinal classification
]

// Putting it together: RRI & NBV with ASE, EFM3D & ATEK
#slide(title: [RRI-based NBV with ASE, EFM3D & ATEK])[
  - Use ASE visibility data + GT meshes for oracle RRI and visibility count
  - Maybe compute RRI separately for each entity (walls, doors, objects) to allow semantic weighting
  - Use EVL as scene encoder

  *Pipeline*
  1. *Scene Encoding*:
    - Sample random point $t$ in ASE trajectory as starting pose
    - Get partial PC, camera poses and RGB-D frames $(C, cal(P)_("base"), I_("RGB"-D))^(1:t)$ up to $t$ from historical trajectory
    - Use EVL to encode current scene observation
  3. *Sample*: Generate candidate viewpoint pool around last pose
  4. *Predict*: Use _scene encodings_ + _candidate view encoding_ to predict RRI per candidate
    - _freeze_ EVL weights, only train _VIN head_

  #pagebreak()
  *ATEK Integration*
  - GT meshes enable oracle RRI computation (training labels)
  - Mesh-based metrics (accuracy, completeness, F-score) for evaluation
  - Pre-processed data splits for model training

  *Key Challenges*
  - Ray-casting from candidate views to compute visibility and $cal(P)_("base" union q)$ from GT meshes
  - Multi-entity scenes vs. VIN-NBV's single-object focus $=>$ compute?
  - Projection of features to candidate views? Is this explicit $"SE"(3)$ tf actually necesary?
]

// TODO slide
#slide(title: [Next Steps & TODOs])[
  *Literature Review*
  - Read Project Aria paper @ProjectAria-ASE-2025
  - Study EFM3D & EVL in depth @EFM3D-straub2024
  - Reread VIN-NBV and GenNBV approach to get in-depth understanding of potential  metrics and loss functions
  - Mesh to distance field conversion / Distance to mesh surface as as metric?
  - Is CD dependent on the density of the point cloud?

  *Technical Exploration*
  - Explore GT meshes (`.ply` files) in ASE dataset
  - Get familiar with #link("https://github.com/facebookresearch/ATEK")[ATEK] and #link("https://github.com/facebookresearch/ATEK/blob/main/docs/ATEK_Data_Store.md")[ATEK Data Store]
  - Test mesh-based evaluation metrics

  *Implementation Goals*
  - Implement ray-casting/rendering for candidate views
  - Develop RRI computation pipeline using GT meshes

]


// Bibliography slide
#slide(title: [Bibliography])[
  #bibliography("/references.bib", style: "ieee")
]
