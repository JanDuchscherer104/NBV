// This file defines slides for the ASE, EFM3D & EVL talk.
// It is based on the definitely-not-isec-theme provided in the skeleton.

#import "@preview/definitely-not-isec-slides:1.0.1": *
#import "@preview/muchpdf:0.1.1": muchpdf

// Import shared macros and symbols
#import "../shared/macros.typ": *

// Import custom template extensions
#import "custom-template.typ": slide, color-block

#let fig_path = "../../figures/"

#show: definitely-not-isec-theme.with(
  aspect-ratio: "16-9",
  slide-alignment: top,
  progress-bar: false,  // Disable to avoid conflicts with page numbers
  institute: [Munich University of Applied Sciences],
  logo: [#image(fig_path + "hm-logo.svg", width: 1.8cm)],
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
        align(center)[
          VCML Seminar WS24/25 \
          #text(size: 0.85em)[#datetime.today().display("[day padding:none]. [month repr:short] [year]")]
        ],
        align(right)[
          #context [
            #let page-num = counter(page).get().first()
            #let total-pages = counter(page).final().first()
            #if page-num > 1 [#(page-num - 1) / #(total-pages - 1)]
          ]
        ],
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

// Table of Contents
#slide(title: [Outline])[
  #outline(
    title: none,
    indent: auto,
    depth: 2,
  )
]

// ASE Section
#section-slide(title: [Aria Synthetic Environments], subtitle: [Dataset for Egocentric 3D Scene Understanding])[
  #figure(image(fig_path + "scene-script/ase_modalities.jpg", width: 80%), caption: [@SceneScript-avetisyan2024])
]

= Aria Synthetic Environments (ASE)
// ASE overview slide
// #slide(title: [ASE Dataset Overview])[
 #grid(columns: (1fr, 1fr), gutter: 1.5cm,
   [#text(size: 16pt)[
  #color-block(title: [Dataset Content])[
  - 100,000 unique multi-room interior scenes
  - \~2-min egocentric trajectories per scene
  - Populated with ~8,000 3D objects
  - Aria camera & lens characteristics
  ]

  #color-block(title: [Ground Truth Annotations])[
  - #emph-color[#SixDoF] trajectories
  - RGB-D frames
  - 2D panoptic segmentation
  - Semi-dense #SLAM #PC w/ visibility info
  - 3D floor plan (#SSL format)
  - #emph-it[GT meshes] as #code-inline[.ply] files
  ]

  #v(0.3em)
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
// ]

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
  #grid(columns: (1fr, 1fr), gutter: 1cm, [
  #color-block(title: [EFM3D Tasks])[
  - 3D object detection
  - 3D surface regression (occupancy volumes)
    - on #ASE, #ADT#footnote[#text(size: 12pt)[Aria Digital Twin]], #AEO#footnote[#text(size: 12pt)[Aria Everyday Objects: small-scale, real-world w/ 3D OBBs]] datasets
  ]

  #color-block(title: [EVL Architecture])[
  - Utilizes #emph-bold[all] available egocentric modalities:
    + multiple (rectified) RGB, grayscale, and semi-dense points inputs
    + camera intrinsics and extrinsics
  - #emph-color[16.7M trainable] + 86.6M frozen params
  - Inherits foundational capabilities from frozen 2D model (DinoV2.5) by lifting 2D features to 3D @EFM3D-straub2024
  ]
  ], [
  #v(0.5em)
  #figure(muchpdf(read(fig_path + "efm3d/efm3d_arch_v1.pdf", encoding: none)), caption: [@EFM3D-straub2024])
  ])
]

// EVL Architecture Details
#slide(title: [EVL: Egocentric Voxel Lifting Architecture])[
  #color-block(title: [Model Overview])[
    *Egocentric Voxel Lifting (EVL)*: Multi-task 3D perception from egocentric video

    #emph-bold[Key Principle]: Lift 2D image features to 3D voxel space using camera geometry
  ]

  #grid(columns: (1fr, 1fr), gutter: 1cm, [
  #color-block(title: [Input Formulation])[
    $ bold(X)_"in" = {bold(I)_1, bold(I)_2, ..., bold(I)_F, bold(D)_"semi", bold(K), bold(T)} $

    Where:
    - $bold(I)_f in bb(R)^(H times W times 3)$: RGB frames ($F$ frames)
    - $bold(D)_"semi" in bb(R)^(N times 3)$: Semi-dense 3D points
    - $bold(K) in bb(R)^(3 times 3)$: Camera intrinsics matrix
    - $bold(T)_f in "SE"(3)$: Camera pose for frame $f$

    #v(0.3em)
    Multiple camera streams supported:
    - RGB (high-res)
    - SLAM cameras (grayscale, rectified)
  ]
  ], [
  #color-block(title: [Output Formulation])[
    *3D Occupancy Volume*:
    $ bold(V)_"out" in bb(R)^(D_x times D_y times D_z times C) $

    - Voxel grid dimensions: $D_x times D_y times D_z$
    - $C$ channels for:
      + Occupancy probability
      + Object class scores
      + Surface normals

    *Detected Objects*:
    $ cal(O) = {(bold(b)_i^"3D", c_i, s_i)}_(i=1)^N $

    - $bold(b)_i^"3D" in bb(R)^9$: Oriented bounding box
    - $c_i$: Object class
    - $s_i$: Confidence score
  ]
  ])

  #color-block(title: [Feature Lifting Process])[
    1. *2D Feature Extraction*: Frozen DinoV2.5 backbone
       $ bold(F)_"2D" = phi_"DINOv2.5"(bold(I)_f) in bb(R)^(H' times W' times D_"feat") $

    2. *3D Projection*: For each voxel $bold(v) in bb(R)^3$, aggregate features from all frames
       $ bold(F)_"3D"(bold(v)) = "Aggregate"({pi(bold(T)_f^(-1) bold(v), bold(K), bold(F)_"2D"^f)}_( f=1)^F) $

       where $pi(dot)$ is the camera projection function

    3. *3D Convolution*: Process lifted features
       $ bold(V)_"out" = psi_"3D-CNN"(bold(F)_"3D", bold(D)_"semi") $
  ]
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
  #grid(columns: (1fr, 1fr), gutter: 1.5cm, [
  #color-block(title: [ATEK Data Store])[
  - Pre-processed for various tasks $->$ ready for PyTorch training
  - Local download or cloud streaming
  - Eval metrics (accuracy, completeness, F-score) $->$ adaptation for #RRI
  - Integration w/ Meta's MPS
  - Various example notebooks
  ]

  #color-block(title: [Provided Models])[
  - #textit[Cube R-CNN] @omni3d-cubercnn-brazil2023 for OBBs
  - #textit[EFM] @EFM3D-straub2024 for OBBs & surface reconstruction
  ]
  ], [
  #v(1em)
  #quote-block[
    *Resources*
    - #link("https://github.com/facebookresearch/ATEK")[ATEK GitHub] @ATEK-about-2025
    - #link("https://www.youtube.com/watch?v=m6oFLfYUpoM&t=7242s")[ECCV 2024 Tutorial: Egocentric Research with Project Aria]
    - Atek Context7 ID: `/facebookresearch/atek`
  ]

  #v(1em)
  #text(size: 15pt)[
    ATEK provides #emph-color[streamlined ML workflows] for rapid prototyping and benchmarking on Aria datasets.
  ]
  ])
]

// TODO slide
#slide(title: [Next Steps & TODOs])[
  #color-block(title: [Literature Review])[
    - Read Project Aria paper @ProjectAria-ASE-2025
    - Study #EFM3D & #EVL architecture in depth @EFM3D-straub2024
    - Deep dive into GenNBV's multi-source embeddings @GenNBV-chen2024
    - Compare VIN-NBV vs. GenNBV: #RRI prediction vs. coverage-based rewards
  ]

  #color-block(title: [Technical Exploration])[
    - Explore GT meshes (#code-inline[.ply] files) in #ASE dataset
    - Get familiar with #link("https://github.com/facebookresearch/ATEK")[ATEK] and #link("https://github.com/facebookresearch/ATEK/blob/main/docs/ATEK_Data_Store.md")[ATEK Data Store]
    - Test mesh-based evaluation metrics (accuracy, completeness, F-score)
    - Experiment with probabilistic 3D occupancy grids
  ]

  #color-block(title: [Implementation Goals])[
    - Implement ray-casting for mesh-based visibility computation
    - Develop entity-wise #RRI computation pipeline using GT meshes
    - Design #FiveDoF action space for scene exploration
    - Build multi-source state embedding (geometric + semantic + action)
    - Prototype #RRI prediction network architecture
  ]
]

// Reconstruction Metrics Theory Slide
#slide(title: [Reconstruction Quality Metrics Theory])[
  #grid(columns: (1fr, 1fr), gutter: 1cm, [
  #color-block(title: [Surface-to-Surface Distance Metrics])[
    *Accuracy* (Prediction → GT):
    $ "Acc" = (1)/(|cal(P)|) sum_(bold(p) in cal(P)) min_(bold(q) in cal(M)_"GT") ||bold(p) - bold(q)||_2 $

    *Completeness* (GT → Prediction):
    $ "Comp" = (1)/(|cal(M)_"GT"|) sum_(bold(q) in cal(M)_"GT") min_(bold(p) in cal(P)) ||bold(p) - bold(q)||_2 $

    Where:
    - $cal(P)$: Sampled points from predicted mesh
    - $cal(M)_"GT"$: Sampled points from ground truth mesh
    - Typically sample 10k points from each mesh
  ]
  ], [
  #color-block(title: [Precision, Recall & F-score])[
    At threshold $tau$ (typically 5cm):

    $ "Precision"@tau = (|{bold(p) in cal(P) : min_(bold(q) in cal(M)_"GT") ||bold(p) - bold(q)|| < tau}|)/(|cal(P)|) $

    $ "Recall"@tau = (|{bold(q) in cal(M)_"GT": min_(bold(p) in cal(P)) ||bold(p) - bold(q)|| < tau}|)/(|cal(M)_"GT"|) $

    $ "F-score"@tau = (2 dot "Precision" dot "Recall")/("Precision" + "Recall") $
  ]

  #v(0.5em)
  #color-block(title: [Chamfer Distance (Bidirectional)])[
    $ CD(cal(P), cal(M)_"GT") = "Acc" + "Comp" $

    Combines both directions of surface error
  ]
  ])

  #quote-block[
    *ATEK Implementation*: `evaluate_single_mesh_pair()` computes all metrics using trimesh sampling and PyTorch3D distance functions @ATEK-about-2025
  ]
]

// RRI Computation with Meshes Slide
#slide(title: [Computing RRI with GT Meshes])[
  #color-block(title: [RRI Formulation for Mesh-based Reconstruction])[
    Given:
    - $cal(M)_"GT"$: Ground truth mesh (from #ASE `.ply` files)
    - $cal(M)_t$: Current partial reconstruction at step $t$
    - $v_"cand"$: Candidate viewpoint
    - $cal(M)_(t union v)$: Updated reconstruction after capturing from $v_"cand"$

    #v(0.5em)
    *Mesh-based RRI*:
    $ "RRI"(v_"cand") = frac(d(cal(M)_t, cal(M)_"GT") - d(cal(M)_(t union v), cal(M)_"GT"), d(cal(M)_t, cal(M)_"GT")) $

    where $d(dot, dot)$ can be:
    - Accuracy (one-sided distance)
    - Completeness (reverse distance)
    - Chamfer Distance (bidirectional)
    - F-score improvement
  ]

  #grid(columns: (1fr, 1fr), gutter: 1cm, [
  #color-block(title: [Entity-wise RRI Aggregation])[
    For multi-entity scenes:

    $ RRI_"total"(bold(v)) = sum_(e in cal(E)) w_e dot RRI_e (bold(v)) $

    Where:
    - $cal(E)$ = {walls, doors, windows, objects, ...}
    - $w_e$: Semantic importance weight
    - $RRI_e$: RRI computed per entity using entity-specific GT mesh
  ]
  ], [
  #color-block(title: [Visibility-based RRI Oracle])[
    Using #ASE visibility data:

    1. Ray-cast from $bold(v)_"cand"$ to $cal(M)_"GT"$
    2. Identify newly visible mesh faces
    3. Estimate improvement without actual capture:

    $ RRI_"oracle"(bold(v)) approx (A_"visible-new")/(A_"total-unseen") $

    where $A$ denotes surface area
  ]
  ])
]

// VIN-NBV Overview
#slide(title: [VIN-NBV: Learning-Based Next-Best-View])[
  #grid(columns: (1fr, 1fr), gutter: 1cm, [
  #color-block(title: [Key Innovation])[
    - First #NBV method to directly optimize #emph-bold[reconstruction quality] (not coverage)
    - Predicts #emph-color[Relative Reconstruction Improvement (#RRI)] without capturing new images
    - 30% improvement over coverage-based baselines
    - Trained 24h on 4 A6000 GPUs @VIN-NBV-frahm2025
  ]

  #color-block(title: [Relative Reconstruction Improvement], spacing: 0.5em)[
    For a candidate view $bold(q)$, #RRI quantifies expected improvement:

    $ RRI(bold(q)) = (CD(cal(R)_"base", cal(R)_"GT") - CD(cal(R)_("base" union bold(q)), cal(R)_"GT")) / (CD(cal(R)_"base", cal(R)_"GT")) $

    - Range: $[0, 1]$ where higher = better view
    - Normalized by current error $arrow.r$ scale-independent
    - #CD measures reconstruction quality
  ]
  ], [
  #color-block(title: [VIN Architecture])[
    Predicts #RRI from current reconstruction state:

    $ hat(RRI)(bold(q)) = "VIN"_theta (cal(R)_"base", bold(C)_"base", bold(C)_bold(q)) $

    - *Input*: Partial point cloud + camera poses
    - *Features*: Surface normals, visibility counts, depth, coverage
    - *Output*: Predicted #RRI via ordinal classification (15 bins)
  ]

  #v(1em)
  #quote-block(color: rgb("#285f82"))[
    VIN-NBV demonstrates that #emph-it[learning reconstruction-aware NBV policies] significantly outperforms traditional coverage-based approaches.
  ]
  ])
]

// GenNBV Overview
#slide(title: [GenNBV: Generalizable Next-Best-View Policy])[
  #grid(columns: (1fr, 1fr), gutter: 1cm, [
  #color-block(title: [Key Innovations])[
    - #emph-bold[#FiveDoF free-space action space]: 3D position + 2D rotation (yaw, pitch)
    - #emph-color[Multi-source state embedding]: geometric, semantic, action representations
    - #emph-it[Probabilistic 3D occupancy grid] vs. binary (distinguishes unscanned from empty)
    - Cross-dataset generalization: 98.26% coverage on Houses3K, 97.12% on OmniObject3D
  ]

  #color-block(title: [Action Space Design])[
    $ cal(A) = underbrace(bb(R)^3, "position") times underbrace(S O(2), "heading") $

    - Approximately 20m × 20m × 10m position space
    - Omnidirectional heading subspace
    - #emph-it[No hand-crafted constraints] (e.g., hemisphere)
  ]
  ], [
  #color-block(title: [State Representation])[
    *Geometric Embedding* $bold(s)_t^G$:
    - Probabilistic 3D occupancy grid from depth maps
    - Bresenham ray-casting with log-odds update
    - Three states: #emph-color[occupied], #emph-color[free], #emph-color[unknown]

    *Semantic Embedding* $bold(s)_t^S$:
    - RGB images → grayscale → 2D CNN
    - Helps distinguish holes from incomplete scans

    *Action Embedding* $bold(s)_t^A$:
    - Historical viewpoint sequence encoding

    *Combined*: $bold(s)_t = "Linear"(bold(s)_t^G; bold(s)_t^S; bold(s)_t^A)$
  ]

  #v(0.5em)
  #quote-block[
    RL-based framework with PPO. Reward: $Delta$#CR between steps. @GenNBV-chen2024
  ]
  ])
]

// Putting it together: RRI & NBV with ASE, EFM3D & ATEK
#slide(title: [Synthesis: RRI-based NBV for Scene-Level Reconstruction])[
  #color-block(title: [Combining VIN-NBV & GenNBV Insights])[
    *From VIN-NBV*: Direct reconstruction quality optimization via #RRI

    *From GenNBV*: Free-space exploration + multi-source state embedding

    *Our Approach*: Adapt #RRI prediction to #emph-color[scene-level] environments with #FiveDoF action space
  ]

  #grid(columns: (1fr, 1fr), gutter: 1cm, [
  #color-block(title: [#RRI with GT Meshes], spacing: 0.4em)[
    Use #ASE visibility data + GT meshes for #emph-it[oracle #RRI]:

    $ RRI(bold(q)) = (d(cal(M)_"partial", cal(M)_"GT") - d(cal(M)_"partial" union bold(q), cal(M)_"GT")) / (d(cal(M)_"partial", cal(M)_"GT")) $

    where $cal(M)$ represents meshes, $d(dot, dot)$ is mesh distance

    #emph-bold[Entity-wise #RRI]:
    $ RRI_"total" = sum_(e in cal(E)) w_e dot RRI_e $
    where $cal(E)$ = {walls, doors, objects, ...}
  ]
  ], [
  #color-block(title: [Proposed Pipeline])[
    1. *Reconstruct*: Build partial mesh from historical trajectory
    2. *Sample*: Generate candidate viewpoints in free space
    3. *Compute Features*: Extract geometric + semantic embeddings (à la GenNBV)
    4. *Predict*: Use network to predict #RRI per candidate
    5. *Select*: Choose #NBV with highest predicted #RRI
  ]
  ])

  #quote-block(color: rgb("#fc5555"))[
    *Key Challenge*: Ray-casting from candidate views to compute visibility on GT meshes for entity-wise #RRI computation
  ]
]

// Bibliography slide
#slide(title: [Bibliography])[
  #bibliography("/references.bib", style: "/ieee.csl")
]
