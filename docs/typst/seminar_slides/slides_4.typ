// Final presentation slides for Aria-NBV (Oracle RRI + VIN v3 baseline).
//
// Target audience: my Professor whose expertise is 3D Deep Learning in Visual Computing, he is already familiar with the project from various update meetings and our previous slides_{1,2,3}.typ, so we can skip basic explanations of concepts;
// Goal: present the final architecture, empirical findings, and limitations to guide next steps
// for the master-thesis continuation (dataset scale + compute needs).
//
// NOTE: numeric values must be imported from data artifacts (cache metadata, W&B summaries,
// Optuna exports) to avoid inconsistencies.
// Target structure:
// Overview of implemented components
// Dataset + offline dataset (coverage, important distributions, batching, data contracts)
// Oracle RRI pipeline (candidates, rendering, backprojection, scoring (P <-> M metrics, RRI metric))
// VIN v3 architecture
//  - general architecture
//  - feature branches + I/O forumlations (frames + shapes + computation flow within each branch)
//  - CORAL head + losses + binning
// - training dynamics + metrics logged
// - evidence so far (Optuna patterns + best run)
// - limitations + next steps

#import "../shared/slide-template.typ": *
#import "../shared/tables.typ": presentation-table
#import "@preview/muchpdf:0.1.1": muchpdf

// Shared macros and symbols (paper + slides)
#import "../shared/macros.typ": *

#let fig_path = "../../figures/"

// ---------------------------------------------------------------------------
// Imported slide data (single source of truth for numbers shown in the deck)
// ---------------------------------------------------------------------------

#let cache = json("/typst/shared/data/vin_offline_store_stats.json").vin_offline_store
#let wb = json("/typst/shared/data/wandb_rtjvfyyp_summary.json").wandb
#let wb_dyn = json("/typst/shared/data/wandb_rtjvfyyp_dynamics.json").wandb_dynamics
#let wb_top2 = json("/typst/shared/data/wandb_top2_improvements.json").wandb_top2
#let v3_vs_t41 = json("/typst/shared/data/vin_v3_01_vs_t41_summary.json").vin_v3_01_vs_t41
#let top_trials = csv("/typst/seminar_paper/data/optuna_v2_top_trials.csv", row-type: dictionary)
#let labeler_cfg = toml("/typst/shared/data/paper_figures_oracle_labeler.toml")
#let gen_cfg = labeler_cfg.labeler.generator
#let depth_cfg = labeler_cfg.labeler.depth
#let renderer_cfg = depth_cfg.renderer

#let round(x, digits: 3) = {
  let s = calc.pow(10, digits)
  calc.round(x * s) / s
}

#let pct(x, digits: 1) = round(100 * x, digits: digits)

// ---------------------------------------------------------------------------
// Theme
// ---------------------------------------------------------------------------

#show: definitely-not-isec-theme.with(
  aspect-ratio: "16-9",
  slide-alignment: top,
  progress-bar: true,
  institute: [Munich University of Applied Sciences],
  logo: [#image(fig_path + "branding/hm-logo.svg", width: 2cm)],
  config-info(
    title: [Aria-NBV: Oracle RRI + VIN v3 Candidate Scoring],
    subtitle: [Offline oracle supervision, diagnostics, and learned NBV baseline],
    authors: [*Jan Duchscherer*],
    extra: [VCML Project WS24/25],
    footer: [
      #grid(
        columns: (1fr, auto, 1fr),
        align: bottom,
        align(left)[Jan Duchscherer],
        align(center)[VCML Project WS24/25],
        align(right)[#datetime.today().display("[day padding:none]. [month repr:short] [year]")],
      )
    ],
    download-qr: "",
  ),
  config-common(handout: false),
  config-colors(
    primary: theme_color_primary_hm,
    lite: theme_color_block,
  ),
)

// Global style overrides
#set text(size: 17pt, font: "Open Sans")
#show figure.caption: set text(size: 12pt, weight: "medium", fill: theme_color_footer.darken(40%))
#show grid: set grid(columns: (1fr, 1fr), gutter: 0.8cm)
#show cite: set text(size: 10pt)
#show bibliography: set text(size: 14pt)
#show link: set text(fill: blue)
#show link: it => underline(it)

// ---------------------------------------------------------------------------
// Title + agenda
// ---------------------------------------------------------------------------

#title-slide()

// ---------------------------------------------------------------------------
// Data + oracle pipeline
// ---------------------------------------------------------------------------

#section-slide(
  title: [Data and Oracle Pipeline],
  subtitle: [
    Candidate generation + depth rendering + RRI computation

    #figure(
      image(fig_path + "app-paper/data_frames_81022_11.png", width: 100%),
      caption: [First/last RGB, SLAM-L/R, and depth frames (example snippet).],
    )

  ],
)

#slide(title: [ASE ATEK Dataset])[
  #grid(
    [
      #color-block(title: [ASE ATEK overview (what we need)], spacing: 0.5em)[
        #set text(size: 15pt)
        - Scale (full ASE): 100k scenes, 58M+ RGB frames, 67 days.
        - Per snippet (ATEK/EFM view):
          + Trajectory #symb.ase.traj (20 frames \@10 Hz; 2 s window).
          + Semi-dense SLAM points #symb.ase.points_semi.
          + 3M OBBs (43 classes).
        - Local shard snapshot (`.data/ase_efm`): 100 scenes, 576 shards, 4,608 snippets (~49 GB).
      ]
    ],
    [

      #color-block(title: [ATEK-EFM snippet format (key facts)], spacing: 0.5em)[
        #set text(size: 15pt)
        - WebDataset shards: per-scene folders with `shards-*.tar` (streamed, then windowed).
        - Window stride: 10 frames (1 s overlap between consecutive 2 s snippets).
        - Resized streams: RGB 240x240, SLAM ~320x240 (calibration + rig poses preserved).
        - GT meshes: #symb.ase.mesh for 100 validation scenes (watertight).
      ]
    ],
  )
  #grid(
    columns: (1fr,),
    [
      #figure(
        image(fig_path + "app-paper/scene_view_81022_11.png", width: 92%),
        caption: [One snippet: #symb.ase.mesh + #symb.ase.points_semi + #symb.ase.traj + camera frustum.],
      )
    ],
  )
]

// #slide(title: [Mesh subset + cached snippet distribution])[
//   #grid(
//     [
//       #figure(
//         image(fig_path + "dataset/gt_mesh_manhattan_sample.png", width: 100%),
//         caption: [GT mesh example (oracle supervision target).],
//       )
//     ],
//     [
//       #figure(
//         image(fig_path + "dataset/ase_efm_snippet_hist.png", width: 100%),
//         caption: [Snippet counts per scene in the current local snapshot.],
//       )
//     ],
//   )
// ]

#slide(title: [Oracle RRI Pipeline])[

  #figure(
    muchpdf(read(fig_path + "diagrams/oracle_rri/oracle_rri_compact.pdf", encoding: none), width: 100%),
    caption: [Oracle RRI Pipeline.],
  )
  #grid(
    columns: (1fr, 1fr),
    [
      #color-block(title: [Stages])[
        1. Sample candidate poses #symb.oracle.candidates around the reference rig pose.
        2. Render candidate depth maps #symb.oracle.depth_q (metric z-buffer from #(symb.ase.mesh)).
        3. Backproject valid depths #sym.arrow.r candidate point clouds #symb.oracle.points_q.
        4. Evaluate point-to-mesh quality before/after and compute RRI.
      ]
      // #color-block(title: [Reusable compute path])[
      //   - `OracleRriLabeler` orchestrates generation #sym.arrow.r rendering #sym.arrow.r scoring.
      //   - Same components are used in Streamlit diagnostics and offline preprocessing.
      //   - Output is a single batch with all intermediate tensors needed for debugging.
      // ]
    ],
    [
      #figure(
        image(fig_path + "impl/oracle-rri-sample.png", width: 85%),
        caption: [Oracle RRI Sample.],
      )
    ],
  )
]

//  Now slides on the different stages, on each of these slides include a table with the key parameters, and include a place holder figure for relevant visualizations!
#slide(title: [Candidate Generation])[
  #grid(
    columns: (2fr, 1fr),
    [
      #io-formulation(
        [
          - Trajectory #symb.ase.traj
          - GT Mesh #symb.ase.mesh
        ],
        [
          - Candidate views $#symb.oracle.candidates subset "SE"(3)^#symb.shape.Nq$ + cameras #symb.oracle.cameras_q
          - Reference pose #symb.ase.traj_final
          - Valid + debug masks
        ],
      )
      #color-block(title: [Summary])[
        - Sample candidate centers on a constrained shell around the reference pose.
        - Assign view directions (radial-away or forward) and optional jitter.
        - Prune using collision + free-space rules and min-distance checks.
      ]
    ],
    [
      #figure(
        kind: "table",
        supplement: [Table],
        caption: [Key parameters (candidate generation).],
        text(size: 12pt)[
          #let gen_rows = (
            ([$#symb.shape.Nq$], [#gen_cfg.num_samples]),
            ([$r_"min"$], [#gen_cfg.min_radius]),
            ([$r_"max"$], [#gen_cfg.max_radius]),
            ([$theta_"min"$], [#gen_cfg.min_elev_deg]),
            ([$theta_"max"$], [#gen_cfg.max_elev_deg]),
            ([$psi_"span"$], [#gen_cfg.delta_azimuth_deg]),
            ([$psi_delta$], [#gen_cfg.view_max_azimuth_deg]),
            ([$theta_delta$], [#gen_cfg.view_max_elevation_deg]),
            ([$phi_delta$], [#gen_cfg.view_roll_jitter_deg]),
            (code-inline("align_to_gravity"), [#gen_cfg.align_to_gravity]),
            (code-inline("min_dist_to_mesh"), [#gen_cfg.min_distance_to_mesh]),
          )
          #let gen_cells = gen_rows.flatten()
          #presentation-table(
            columns: (14em, auto),
            align: (left, left),
            text-size: 12pt,
            header: ([Setting], [Value]),
            rows: gen_cells,
          )
        ],
      )
    ],
  )
]

#slide(title: [Candidate Generation: Position sampling])[
  #grid(
    columns: (1.2fr, 1fr),
    [
      #color-block(title: [Position sampling])[
        - Sample directions on the unit sphere $bb(S)^2 subset bb(R)^3$, then rescale into $(psi, theta)$ caps.
        - Gravity-aligned sampling uses #T(symb.frame.w, symb.frame.s) (roll/pitch removed).
        - #T(symb.frame.w, symb.frame.r) is the reference pose rotation; $(psi, theta)$ only
          parameterize the direction $bold(s)_q in bb(S)^2$.

        #v(0.3em)
        $
          bold(s)_q ~ cal(U)(bb(S)^2),
          quad
          r_q ~ cal(U)(r_"min", r_"max")
        $
        $
          (psi, theta) = "angles"(bold(s)_q) \
          (psi, theta) <- "lin"([psi_"min", psi_"max"] times [theta_"min", theta_"max"]; (psi, theta))
        $
        $
          bold(s)_q' = (cos theta sin psi, sin theta, cos theta cos psi)
        $
        $
          #(symb.oracle.center) _q = #T(symb.frame.w, symb.frame.r) (r_q bold(s)_q')
        $
        #cite(<Formelsammlung-papula2024>, supplement: [p.43])
      ]
    ],
    [
      #figure(
        image(fig_path + "app-paper/pos_ref.png", width: 100%),
        caption: [Candidate centers in the reference frame.],
      )
    ],
  )
]

#slide(title: [Candidate Generation: View directions])[
  #grid(
    columns: (1.2fr, 1fr),
    [
      #color-block(title: [Direction + pose])[
        - Base orientation from `view_direction_mode` (e.g., radial-away).
        - $(psi, theta)$ caps apply to the *jitter delta* (box-uniform), not the base view.
        - Compose candidate pose #T(symb.frame.w, symb.frame.cq) from center + base + delta.

        #v(0.3em)
        $
          bold(R)_("base") = "look-away"(#symb.frame.cq, #(symb.ase.traj_final)) \
          psi ~ cal(U)(-psi_delta/2, psi_delta/2),
          theta ~ cal(U)(-theta_delta/2, theta_delta/2)
        $
        $
          #T(symb.frame.w, symb.frame.cq) =
          (bold(R)_("base") compose bold(R)_("delta"), #symb.frame.cq)
        $
      ]
    ],
    [
      #figure(
        image(fig_path + "app-paper/view_dirs_ref.png", width: 100%),
        caption: [View direction density (azimuth/elevation).],
      )
    ],
  )
]

#slide(title: [Candidate Generation: Jitter + rules])[
  #grid(
    columns: (1fr, 1.6fr),
    [
      #color-block(title: [View jitter])[
        - Box-uniform jitter in yaw/pitch within caps:
          $
            psi ~ cal(U)(-psi_delta /2, psi_delta/2) \
            theta ~ cal(U)(-theta_delta/2, theta_delta/2).
          $
        - Optional roll:
        $
          phi ~ cal(U)(-phi_delta, phi_delta)
        $

        $
          bold(R)_(delta) = bold(R)_z (psi) bold(R)_y (theta) bold(R)_x (phi) \
          #T(symb.frame.w, symb.frame.cq) = #T(symb.frame.w, symb.frame.cq) compose mat(bold(R)_(delta), bold(0); bold(0)^T, 1)
        $
      ]
    ],
    [
      #figure(
        image(fig_path + "app-paper/orientation_jitter.png", width: 105%),
        caption: [Orientation jitter distribution (delta yaw/pitch/roll, deg).],
      )
      #figure(
        image(fig_path + "app-paper/ypr_reference.png", width: 105%),
        caption: [Reference-frame yaw/pitch/roll distribution (deg).],
      )
      #v(0.3em)
      #color-block(title: [Pruning Rules])[
        - *Rules*: min distance to mesh, collision-free ray, free-space AABB.
      ]
    ],
  )
]
//  TODO: currently we just replace invalid candidates and mask them if Nq is not reached


#slide(title: [Candidate Depth Rendering])[
  #grid(
    columns: (1.35fr, 1fr),
    gutter: 0.4cm,
    [
      #text(size: 17pt)[
        #io-formulation(
          [
            - Candidate views #symb.oracle.candidates, #symb.oracle.cameras_q
            - GT mesh #symb.ase.mesh, #symb.ase.faces
          ],
          [
            - Depth maps $#symb.oracle.depth_q$
            - Valid mask $bold(M)_q$
            - #symb.oracle.cameras_q' (P3D cameras)
          ],
        )
      ]
      #v(0.3em)
      #color-block(title: [Transforms + ops])[
        - Build PyTorch3D #symb.oracle.cameras_q' with extrinsics #T(symb.frame.w, symb.frame.cq) and $(#symb.shape.Wdim / 2, #symb.shape.H / 2)$ from #code-inline("CameraTW").
        - Rasterize #symb.ase.mesh to depth $#symb.oracle.depth_q subset R^(#symb.shape.Nq times #symb.shape.H' times #symb.shape.Wdim')$.
        - Valid mask: #text(size: 15pt)[#code-inline("pix_to_face") $>=$ 0 and #code-inline("znear") $<$ #symb.oracle.depth_q $<$ #code-inline("zfar")]\
          - $bold(M)_q subset {0,1}^(#symb.shape.Nq' times #symb.shape.H' times #symb.shape.Wdim)$
      ]
    ],
    [

      #figure(
        image(fig_path + "app-paper/cand_renders_1x3.png", width: 100%),
        caption: [Candidate depth renders (1x3).],
      )
      #figure(
        image(fig_path + "app-paper/depth_histograms_3x3.png", width: 100%),
        caption: [Depth histograms across candidates (3x3).],
      )
    ],
  )
]

#slide(title: [Backprojection])[
  #grid(
    columns: (1.15fr, 1fr),
    gutter: 0.4cm,
    [
      #text(size: 16pt)[
        #io-formulation(
          [
            - Depth maps #symb.oracle.depth_q + #symb.oracle.cameras_q
            - Semi-dense PC $#(symb.ase.points_semi)$
          ],
          [
            - Candidate PCs $#symb.oracle.points_q subset R^(#symb.shape.Nq times #symb.shape.P times 3)$
            - $ell_q subset {0, dots, #symb.shape.H dot #symb.shape.Wdim}^(#symb.shape.Nq)$
            - AABBs $bold(b)_{"aabb"} subset R^6$
          ],
        )
      ]
    ],
    [
      #grid(
        rows: (auto, auto),
        gutter: 0.25cm,
        [
          #figure(
            image(fig_path + "app-paper/backproj+semi.png", width: 75%),
            caption: [Backprojected candidate points + semi-dense SLAM points.],
          )
        ],
        [
          #figure(
            image(fig_path + "app-paper/semi-dense-pc-cand-vis.png", width: 75%),
            caption: [Candidate visibility in semi-dense point cloud.],
          )
        ],
      )
    ],
  )
  #color-block(title: [Transforms + ops])[
    + Subsample pixel centers $(u, v)$ by stride $k$.
    + Map to NDC with $s = min(#symb.shape.H, #symb.shape.Wdim)$ @PyTorch3D-Cameras-2025:
      $
        x_"ndc" = - (u + 1/2 - #symb.shape.Wdim'/2) (2/s) quad
        y_"ndc" = - (v + 1/2 - #symb.shape.H'/2) (2/s)
      $
    + Unproject: $bold(p)_"world" = Pi^(-1)(x_"ndc", y_"ndc", d_q)$, where $d_q$ is sampled from #symb.oracle.depth_q.
    + Pad per-candidate PCs; fuse with $#(symb.ase.points_semi)$ for AABB cropping.
  ]
]



#slide(title: [Oracle RRI: Accuracy + Completeness])[
  #grid(
    columns: (1.1fr, 1fr),
    [
      #good-note[$ #eqs.rri.acc $]
      #figure(
        image(fig_path + "app-paper/acc_top10.png", height: 50%),
        caption: [Candidates by accuracy (lower is better).],
      )
    ],
    [
      #good-note[$ #eqs.rri.comp $]
      #figure(
        image(fig_path + "app-paper/comp_top10.png", height: 50%),
        caption: [Candidate completeness (lower is better).],
      )
    ],
  )

  - Crop #symb.ase.mesh to AABB, then
    compute $bold(cal(P))_bullet <-> #symb.ase.mesh$ distances with PyTorch3D.
  - $cal(A)$ dominated by #symb.ase.points_semi #sym.arrow not discriminative w.r.t. candidates

]

#slide(title: [Oracle RRI: Relative improvement])[
  #figure(
    image(fig_path + "app-paper/oracle_rri_bar.png", width: 100%),
    caption: [Per-candidate oracle RRI (bar chart).],
  )
  #align(center)[
    #good-note[$ #eqs.rri.rri, quad #eqs.rri.union $]
  ]
]


// #slide(title: [Oracle RRI distribution])[
//   #grid(
//     [
//       #color-block(title: [Skewed candidate gains])[
//         - Most candidates yield marginal improvements.
//         - A small fraction produce large RRI gains.
//         - Diagnostics log accuracy and completeness terms to catch failure cases early.
//       ]
//     ],
//     [
//       #figure(
//         image(fig_path + "app/rri_hist_81056_000022.png", width: 100%),
//         caption: [Oracle RRI histogram for one example snippet.],
//       )
//     ],
//   )
// ]

// ---------------------------------------------------------------------------
// Offline cache + batching
// ---------------------------------------------------------------------------

#section-slide(
  title: [Offline Dataset and Batching],
  subtitle: [Fast training iterations without recomputing the oracle],
)

//  TODO: motivate usage of offline dataset:
// Oracle RRI pipeline uses PyTorch and takes about 30s per snippet for #symb.shape.Nq = 60 candidates.
// Should cache backbone outputs once (for each of the 4608 snippets) as single forward requires 8+ GB GPU memory and takes up to 60s
// Training signal is very noisy - higher batch size stabilizes gradients
// Now we can easily train with B >= 16; single epoch on 798 samples takes approx 8 minutes vs > 24 hours if we compute oracle and EVL scene encoding on-line.
#slide(title: [Offline cache: Motivation])[
  #color-block(title: [Why offline?])[
    - Oracle pipeline uses P3D rendering + backprojection mesh ops.
      + >30s for #symb.shape.Nq = 60
      + cannot be parallelized
    - Single EVL forward-pass requires:
      + 8+ GB VRAM
      + >60s per sample
    - VIN offline store enables:
      + batching ($nabla$ stablization)
      + reproducible splits & validation monitoring
      + >180x speedup (8 min vs >24 h)
      + enables HParam sweeps
  ]
]

#slide(title: [VIN offline store: coverage + footprint])[
  #grid(
    columns: (1.1fr, 1fr),
    gutter: 0.35cm,
    [
      #color-block(title: [Coverage numbers])[
        - Stored scenes: #cache.unique_scenes / #cache.meta_scenes_total (#pct(cache.meta_scenes_covered_frac)%)
        - Stored samples: #cache.index_entries / #cache.total_snippets (_#pct(cache.index_entries / cache.total_snippets)%_)
        - Split: (train: #cache.train_entries, val: #cache.val_entries)
      ]
      #color-block(title: [Storage snapshot])[
        - EFM ATEK: 49 GB
        - Oracle/backbone payloads: #cache.samples_size_gb GB (current subset).
        - Minimal VIN snippets: #cache.vin_snippet_cache_gb GB.
        - Full coverage estimate:
          #(round(cache.full_coverage_total_gb / 1000, digits: 2)) TB
      ]
      #quote-block[Memory footprint dominated by voxel grid features in EVL backbone (> 90%).]
    ],
    [
      #figure(
        image(fig_path + "vin_offline_store/coverage.png", width: 72%),
        caption: [Coverage snapshot for the cached subset.],
      )
      #figure(
        image(fig_path + "vin_offline_store/footprint.png", width: 75%),
        caption: [Per-sample memory footprint (mean).],
      )
    ],
  )
]

// #slide(title: [VIN offline store: implementation])[
//   #figure(
//     image(fig_path + "diagrams/vin_nbv/mermaid/vin_offline_store_training.png", width: 55%),
//     caption: [Per-sample memory footprint (mean).],
//   )
// ]

#slide(title: [VIN offline store: what is stored?])[
  #grid(
    [
      #color-block(title: [Store structure])[

        - Full Oracle pipeline outputs:
          + Candidates views #symb.oracle.candidates + #symb.oracle.cameras_q
          + Depth renders #symb.oracle.depth_q + valid mask
          + Candidate PCs #symb.oracle.points_q
          + RRI Labels: #symb.oracle.rri, #symb.oracle.acc, #symb.oracle.comp
          + EVL backbone outputs
          + VinSnippetView: #symb.ase.traj + #symb.ase.points_semi
      ]
      #quote-block[Training only requires RRI labels + #symb.oracle.candidates + #symb.oracle.cameras_q + #symb.oracle.points_q + #symb.ase.points_semi & EVL head features.]
    ],
    [
      #figure(
        caption: [VIN offline-store sample: candidates, depths, points, and RRI.],
      )[
        #image(fig_path + "impl/vin-oracle-cache-sample.png", width: 100%)
      ]
    ],
  )
]
#slide(title: [VinOracleBatch + VinSnippetView])[
  #grid(
    [
      #color-block(title: [Key typed tensors (padded + batched)])[
        - Candidate poses: #code-inline[PoseTW[#(symb.shape.B), #(symb.shape.Nq), 12]].
        - Reference pose: #code-inline[PoseTW[#(symb.shape.B), 12]].
        - Labels: #code-inline[rri[#(symb.shape.B), #(symb.shape.Nq)]] + (#(symb.oracle.acc), #(symb.oracle.comp)) + lenghts.
        - #code-inline[PerspectiveCameras[#(symb.shape.B), #(symb.shape.Nq)]].
        - VinSnippetView:\
          #code-inline[points_world[#(symb.shape.B), #(symb.shape.P), 3 + #(symb.shape.Csem)]] + #code-inline[lengths[#(symb.shape.B)]].
      ]
    ],
    [
      #figure(caption: [VinOracleBatch Sample.])[
        #image(fig_path + "vin_offline_store/vin_oracle_batch.png", width: 100%)
      ]
    ],
  )
]


#slide(title: [Data Flow: VinDataModule + VinOfflineDataset])[
  #grid(
    columns: (1.1fr, 1fr),
    gutter: 0.35cm,
    [
      #color-block(title: [Pipeline (immutable VIN offline store)], spacing: 0.5em)[
        #text(size: 16pt)[
          - #code-inline[VinDataModule] builds a map-style #code-inline[`VinOfflineDataset`].
          - #code-inline[manifest.json] + #code-inline[sample_index.jsonl] route train/val rows into immutable shards.
          - Zarr blocks provide fixed tensor reads; indexed MessagePack blocks preserve diagnostics on demand.
          - Each row reconstructs a #code-inline[`VinOracleBatch`] with padded candidates, oracle RRI, cameras, and a minimal #code-inline[`VinSnippetView`].
          - Legacy oracle/VIN caches are removed; rebuild immutable stores with #code-inline[`VinOfflineWriter`] when data is available.
        ]
      ]
      #quote-block[Streamline, simplify, keep only necessary components]
    ],
    [

      #figure(
        image(fig_path + "diagrams/vin_nbv/mermaid/vin_offline_store_training.png", width: 105%),
        caption: [Data Flow: immutable VIN offline store #sym.arrow.r VinOracleBatch.],
      )
    ],
  )
]

// ---------------------------------------------------------------------------
// CORAL + ordinal binning (target discretization + loss)
// ---------------------------------------------------------------------------

#section-slide(
  title: [CORAL & Ordinal Binning],
  subtitle: [Skewed RRI #sym.arrow.r Quantile Bins #sym.arrow.r CORAL],
)

#slide(title: [Ordinal Binning])[
  #grid(
    [
      // Keep this slide compact: move baselines inline and slightly reduce text size.
      #color-block(title: [Motivation (binning + CORAL)])[
        - Oracle RRI is heavy-tailed / right-skewed (many near-zero #symb.oracle.rri, few large gains).
        - Direct regression is sensitive to outliers and scene effects. @VIN-NBV-frahm2025
        - Use $K=15$ ordered quantile bins + CORAL thresholds. @CORAL-cao2019
        - Random Classifier:\
          $cal(L)_("rnd") approx (K-1) dot "log"(2)$ _?_
      ]
    ],
    [
      #grid(
        columns: 1fr,
        rows: (auto, 1fr),
        gutter: 0.25cm,
        [
          #figure(
            image(fig_path + "coral/rri_distribution_linear.png", width: 100%),
            caption: [Raw oracle RRI distribution (linear counts).],
          )
        ],
      )
    ],
  )
]

#slide(title: [Quantile binning (equal-mass ordinal classes)])[
  #grid(
    [
      #color-block(title: [Our Binner])[
        - Bins define the target label $y in {0, dots, K-1}$.
        - Fit empirical quantiles on oracle RRIs (equal-mass bins):
          #block[#align(center)[#eqs.binning.edges]]
        - Assign ordinal label via edge counting (`torch.bucketize`):
          #block[#align(center)[#eqs.binning.label]]
      ]
    ],
    [
      #figure(
        image(fig_path + "coral/rri_distribution_log_with_bin_edges.png", width: 100%),
        caption: [Log-count RRI distribution with fitted quantile edges (vertical lines).],
      )
    ],
  )
]

#slide(title: [Ordinal labels + per-bin statistics (fit data)])[
  #grid(
    [
      #color-block(title: [From labels to CORAL levels])[
        - CORAL converts each label $r$ into $K-1$ binary targets $y$:
          #block[#align(center)[#eqs.binning.levels]]
        - Penalizes far mis-rankings more than near ones.
        - Enables monotonicity diagnostics on $p_k = P(y > k)$.
        - Non-uniform bin widths #sym.arrow near-uniform class counts.
      ]
    ],
    [
      #figure(
        image(fig_path + "coral/ordinal_label_histogram_fit.png", width: 100%),
        caption: [Label histogram after fitting K=15 quantile bins.],
      )
    ],
  )
]

#slide(title: [Bin calibration: midpoints, means, and variance])[
  #grid(
    [
      #color-block(title: [How we recover a scalar])[
        - CORAL predicts cumulative probabilities $p_k = P(y > k)$.
        - Convert to class marginals $pi_k$ and compute expectation:
          #block[#align(center)[#eqs.coral.marginals]]
          #block[#align(center)[#eqs.coral.expected]]
        - We initialize $u_k$ (bin representatives) from fitted *bin means*.
      ]
    ],
    [
      #figure(
        image(fig_path + "coral/bin_means_vs_midpoints.png", width: 60%),
        caption: [Bin means vs midpoints.],
      )
      #figure(
        image(fig_path + "coral/bin_stds_vs_uniform_baseline.png", width: 60%),
        caption: [Per-bin std vs uniform baseline (width/12).],
      )
    ],
  )
]

#slide(title: [CORAL Implementation Deltas])[
  #grid(
    [
      #color-block(title: [What we add on top of coral-pytorch])[
        - Reference layer + loss from @coral-pytorch-2025[coral-pytorch].
        - Learnable monotone bin values $u_k$ (softplus deltas) for learned expectation of RRI.
        - Softplus enforces positive increments, keeping $u_k$ ordered.
        - Diagnostics: monotonicity violations and relative-to-random loss.
        - Learned params: CORAL $(w, b_k)$ and bin values $(u_0, delta_j)$.
      ]
    ],
    [
      #color-block(title: [Key equations])[
        $
          u_k = u_0 + sum_(j=1)^k op("softplus")(delta_j) quad u_k in bb(R) \
          #eqs.coral.expected \
          #eqs.coral.rel_random
        $
      ]
      #good-note[
        *TODO*: Test against baseline!
      ]
    ],
  )
]

// TODO: UNTIL HERE!
// ---------------------------------------------------------------------------
// VIN v3 architecture
// ---------------------------------------------------------------------------

#section-slide(
  title: [VIN Scoring Architecture],
  subtitle: [EVL voxel context #sym.arrow per-candidate evidence #sym.arrow.r ordinal RRI],
)

#slide(title: [VIN Pipeline])[
  #grid(
    [
      //TODO: note all inputs using the notations / symbols from #symb.
      #color-block(title: [Data Flow & Branches], spacing: 1em)[
        - *Inputs*: Candidate Poses, EVL voxel field, semidense points, optional trajectory.
        - *Pose branch* Candidate Poses #sym.arrow.r PoseEncodings #symb.vin.pose_emb.
        - *Scene branch*: EVL Voxel Fields #sym.arrow.r global conditioned features.
        - *Semidense branch*: #symb.ase.points_semi #sym.arrow.r #code-inline[semidense_proj] (+ grid CNN).
        - Concat #sym.arrow.r MLP #sym.arrow.r CORAL logits #sym.arrow.r expected class score (ranking proxy).
        - Continuous expected RRI uses bin reps $u_k$ (paper: Training Objective).
      ]
    ],
    [
      #figure(
        image(fig_path + "app-paper/vin-geom-oc_pr-candfrusta-semi-dense.png", width: 110%),
        caption: [Superposition of all VINv3 inputs.],
      )
    ],
  )
]

// #slide(title: [Design intent])[
//   #grid(
//     [
//       #color-block(title: [Baseline contract])[
//         - Freeze EVL; build #code-inline[field_in] from voxel channels
//           (occ_input, occ_pr, cent_pr, counts_norm, observed/unknown/free, new_surface_prior).
//         - Add *candidate-conditioned* evidence to avoid collapse:
//           + voxel validity/coverage proxies (#code-inline[voxel_valid_frac]),
//           + semidense projection stats + grid CNN (visibility, depth mean/std, empty vs covered),
//           + optional trajectory context for stage bias (rig history).
//         - Every cue must be diagnosable (Streamlit overlays + W&B curves) and robust to frame bugs.
//       ]
//       #color-block(title: [Why view-conditioned evidence?])[
//         - Ranking must vary with candidate pose, not only global scene context.
//         - Pure global context often yields near-uniform scores across candidates.
//         - View-conditioned cues encode *where* new surface might be revealed and
//           drive coverage-weighted training schedules.
//       ]
//     ],
//     [

//       #figure(
//         image(fig_path + "app-paper/vin-geom-oc_pr-candfrusta-semi-dense.png", width: 100%),
//         caption: [View-conditioned evidence: voxel occupancy context + candidate frusta + semidense points.],
//       )

//     ],
//   )
// ]

// #slide(title: [VIN v3: input features])[
//   #grid(
//     [
//       #color-block(title: [Scene field (EVL)])[
//         - Build #code-inline[field_in] by selecting channels from:
//           occ_pr, occ_input, cent_pr, counts_norm, observed, unknown, free_input, new_surface_prior.
//         - Channel selection is configured via #code-inline[scene_field_channels] (not hard-coded).
//         - Project to field_dim=#wb.vin_effective.field_dim channels with Conv3d+GN+GELU.
//       ]
//       #color-block(title: [Per-candidate cues])[
//         - Pose encoding: R6D + LFF in reference rig frame.
//         - Semidense projections:
//           + stats (visibility, coverage, depth moments),
//           + grid CNN (G=#wb.vin_effective.semidense_proj_grid_size).
//         - Optional trajectory encoder: #wb.vin_effective.use_traj_encoder (enabled in best run).
//       ]
//     ],
//     [
//       #figure(
//         image(fig_path + "external/arXiv-EFM3D/evl_output_summary.png", width: 100%),
//         caption: [EVL output summary used to build the scene field. @EFM3D-straub2024],
//       )
//     ],
//   )
// ]

// ---------------------------------------------------------------------------
// EVL backbone features (what VIN v3 consumes)
// ---------------------------------------------------------------------------



// ---------------------------------------------------------------------------
// VIN v3 forward: feature branches (tensors + frames + shapes)
// ---------------------------------------------------------------------------

// #slide(title: [VIN v3 forward pass: frames + shape legend])[
//   #grid(
//     [
//       #color-block(title: [Frames used in v3])[
//         - #code-inline[w]: world (ASE global, meters).
//         - #code-inline[r]: reference rig frame at the snippet reference time (rig_ref).
//         - #code-inline[q]: candidate camera frame (one per candidate).
//         - #code-inline[v]: EVL voxel grid frame (axis-aligned metric grid).
//         - #code-inline[s]: screen/pixel space (PyTorch3D projection output).
//       ]
//       #color-block(title: [PoseTW convention])[
//         - Poses are stored as world #sym.arrow.l frame transforms, e.g.
//           #T(symb.frame.w, symb.frame.cq), #T(symb.frame.w, symb.frame.r), #T(symb.frame.w, symb.frame.v).
//         - Relative candidate pose:
//           $#T(symb.frame.r, symb.frame.cq) = #T(symb.frame.w, symb.frame.r)^(-1) dot #T(symb.frame.w, symb.frame.cq).$
//         - Points are always expressed explicitly as #code-inline[x_w], #code-inline[x_r], #code-inline[x_s].
//       ]
//     ],
//     [
//       #color-block(title: [Shape symbols (used below)])[
//         - Batch size: #symb.shape.B. Candidates: #symb.shape.Nq. Trajectory length: #symb.shape.Tlen.
//         - Voxel grid: #symb.shape.D x #symb.shape.H x #symb.shape.Wdim. Voxel centers: #symb.shape.Vvox = #symb.shape.D x #symb.shape.H x #symb.shape.Wdim.
//         - Pooled voxel points: #symb.shape.Pproj = #symb.shape.Gpool^3.
//         - Semidense points: #symb.shape.P (padded) and #symb.shape.Pfr (#sym.arrow.r subsampled for projection).
//       ]
//       #good-note(width: 100%)[
//         In code: see `aria_nbv/aria_nbv/vin/model_v3.py::_forward_impl` for the exact tensor flow.
//       ]
//     ],
//   )
// ]

// #slide(title: [Inputs #sym.arrow.r PreparedInputs])[
//   #grid(
//     [
//       #color-block(title: [Inputs (from VinOracleBatch)])[
//         - Candidate poses: #code-inline[PoseTW[#(symb.shape.B), #(symb.shape.Nq), 12]] (world #sym.arrow.l cam_q).
//         - Reference pose: #code-inline[PoseTW[#(symb.shape.B), 12]] (world #sym.arrow.l rig_ref).
//         - Cameras: #code-inline[PerspectiveCameras] with flat batch size #code-inline[B x N_q].
//           - Ex: #code-inline[R[B x N_q, 3, 3]], #code-inline[T[B x N_q, 3]], intrinsics, #code-inline[image_size[B x N_q, 2]].
//         - EVL backbone output (cached): #code-inline[t_world_voxel], #code-inline[voxel_extent], #code-inline[pts_world] (voxel centers in world).
//         - Semidense snippet: #code-inline[points_world: Tensor[#(symb.shape.B), #(symb.shape.P), C_sem]] (padded) + #code-inline[lengths].
//       ]
//     ],
//     [
//       #color-block(title: [PreparedInputs (after normalization)])[
//         - #code-inline[pose_world_cam: PoseTW[#(symb.shape.B), #(symb.shape.Nq), 12]] stores #T(symb.frame.w, symb.frame.cq).
//         - #code-inline[pose_world_rig_ref: PoseTW[#(symb.shape.B), 12]] stores #T(symb.frame.w, symb.frame.r).
//         - #code-inline[t_world_voxel: PoseTW[#(symb.shape.B), 12]] stores #T(symb.frame.w, symb.frame.v).
//         - Transforms/modules:
//           #code-inline[ensure_candidate_batch] + #code-inline[ensure_pose_batch] (broadcast to B),
//           optional #code-inline[rotate_yaw_cw90(undo=True)] for pose convention alignment.
//         - Optional CW90 undo (poses) must be consistent with #code-inline[p3d_cameras] correction.
//         - Semidense points are required; missing data throws a hard error.
//       ]
//     ],
//   )
// ]

#slide(title: [Candidate Pose Encoding])[
  #grid(
    [
      #color-block(title: [Concept (R6D + LFF)])[
        - Express each candidate in the reference rig frame #symb.frame.r:
          $T_(#symb.frame.r,#symb.frame.cq) = T_(#symb.frame.w,#symb.frame.r)^(-1) dot T_(#symb.frame.w,#symb.frame.cq)$.
        - *R6D SO(3) encoding* #sym.arrow stable pose vector $[bold(t)_(#symb.frame.cq)^(#symb.frame.r), "R6D"(bold(R)_(#symb.frame.cq)^(#symb.frame.r))]$.
        - *LFF+MLP* map pose vector to a learned embedding #(symb.vin.pose_emb).
        - #(symb.vin.pose_emb) conditions the global scene context #(symb.vin.global) and head.
      ]
    ],
    [
      #figure(
        image(fig_path + "diagrams/vin_nbv/mermaid/pose_encoder.png", height: 100%),
        caption: [Candidate Pose Encoding.],
      )
    ],
  )
]

#slide(title: [Scene branch: FieldBundle (EVL voxel field)])[
  #grid(
    [
      #color-block(title: [Concept (EVL scene field)])[
        - EVL evidence heads are stacked into the scene-field input $(#(symb.vin.field_v)^("in"))$:
          (#symb.vin.occ_in, #symb.vin.counts_norm, #symb.vin.occ_pr, #symb.vin.cent_pr).
        - Optional derived channels augment $(#(symb.vin.field_v)^("in"))$:
          #symb.vin.free_in, #symb.vin.unknown, #symb.vin.new_surface_prior.
        - Derived channel definitions:
        #eqs.vin.counts_norm
        #eqs.vin.new_surface_prior
      ]
    ],
    [
      #figure(
        image(fig_path + "app-paper/field_occ_in.png", height: 100%),
        caption: [EVL occupancy evidence slice (scene-field input).],
      )
    ],
  )
]

#slide(title: [Scene branch: voxel_valid_frac (coverage proxy)])[
  #grid(
    [
      #color-block(title: [Concept (coverage proxy)])[
        - Project the input field $(#(symb.vin.field_v)^("in"))$ with #code-inline[Conv3d + GroupNorm + GELU] to the scene field #symb.vin.field_v.
        - The same voxel context drives global pooling and voxel-projection statistics (for FiLM).
        - Sample #symb.vin.counts_norm at each candidate center #symb.oracle.center to get per-candidate voxel validity #symb.vin.voxel_valid in $[0,1]$.
        - Used for candidate validity #symb.vin.cand_valid and coverage scheduling.
      ]
    ],
    [
      #figure(
        image(fig_path + "app-paper/field_counts_norm.png", height: 100%),
        caption: [Normalized observation counts (coverage proxy).],
      )
    ],
  )
]

#slide(title: [Scene Branch: Global Context + FiLM])[
  #set text(size: 15pt)
  #grid(
    [
      #color-block(title: [Concept (pose-conditioned pooling)], spacing: 0.4em)[
        // TODO: refer to positional encodings used here - one bullet point to explain conceptualy
        - From #symb.vin.field_v, build voxel tokens #symb.vin.vox_tok and pool with pose queries #(symb.vin.pose_emb) to get per-candidate global context #(symb.vin.global):
          $
            #(symb.vin.global) _i = "MHCA"(q=#(symb.vin.pose_emb), k=#symb.vin.vox_tok + phi(#symb.vin.pos), v=#symb.vin.vox_tok)
          $
        - In parallel, pool voxel centers and project into candidate cameras to get per-candidate projection stats (coverage/validity (visibility) + depth moments).
        - FiLM uses these stats to modulate #(symb.vin.global): #eqs.features.film
      ]
    ],
    [
      #figure(
        image(fig_path + "diagrams/vin_nbv/mermaid/global_pool.png", height: 80%),
        caption: [Global context + voxel-projection FiLM.],
      )
    ],
  )
]

#slide(title: [Semidense Branch: Scalar Stats])[
  #set text(size: 15pt)
  #grid(
    [
      #color-block(title: [Concept (projection stats)], spacing: 0.45em)[
        - Project #symb.ase.points_semi into each candidate view.
        - Compute coverage, visibility, and depth moments from valid projections.
        - Reliability weights combine #symb.vin.n_obs and #symb.vin.inv_dist_std (inverse-distance std).
        - Yields per-candidate scalar evidence #(symb.vin.sem_proj) for the head.
      ]
    ],
    [
      #figure(
        image(fig_path + "diagrams/vin_nbv/mermaid/semidense_proj.png", height: 100%),
        caption: [Semidense projection statistics branch.],
      )
    ],
  )
]

//  DONE UNTILE HERE
#slide(title: [Semidense Projections])[
  #grid(
    [
      #text(size: 16pt)[
        #color-block(title: [Projection])[
          - Use #code-inline[transform_points_screen] to project points into the candidate camera.
          - Valid points are finite, in front of the camera, and inside image bounds.
        ]
        #color-block(title: [Grid binning])[
          - Bin valid projections into a $G_"sem" times G_"sem"$ screen grid.
          - Compute per-bin visibility, mean depth, and depth std. \
            #sym.arrow CNN inputs.
        ]
      ]
    ],
    [
      #color-block(title: [Grid], spacing: 0.45em)[
        - If H=W=120, G=12 #sym.arrow each cell covers ~10x10 pixels.
      ]
      #figure(
        caption: [Semidense projection maps (counts / weights / depth std).],
      )[
        #grid(
          columns: (1fr, 1fr, 1fr),
          gutter: 0.2cm,
          [
            #image(fig_path + "app-paper/semi-dense-counts-proj.png", width: 100%)
          ],
          [
            #image(fig_path + "app-paper/semi-dense-weight-proj.png", width: 100%)
          ],
          [
            #image(fig_path + "app-paper/semi-dense-std-proj.png", width: 100%)
          ],
        )
      ]
      #quote-block[
        Why so coarse _!?_
      ]
    ],
  )
]

#slide(title: [Semidense Branch: Grid CNN])[
  #set text(size: 15pt)
  #grid(
    [
      #color-block(title: [Concept (projection grid)], spacing: 0.45em)[
        - Keep coarse view-plane structure that scalar stats discard.
        - Bin valid projections into a $G_"sem" times G_"sem"$ grid.
        - Tiny CNN encodes occupancy + depth moments into #(symb.vin.sem_grid).
        - Appended to the head with #(symb.vin.sem_proj).
        - Grid channels: $bold(H)_i in bb(R)^(3 times #symb.shape.Gsem times #symb.shape.Gsem)$ with $[O_i, mu_z_i, sigma_z_i]$.
      ]
    ],
    [
      #figure(
        image(fig_path + "diagrams/vin_nbv/mermaid/semidense_frustum.png", height: 100%),
        caption: [Semidense grid CNN branch.],
      )
    ],
  )
]

#slide(title: [MLP & Coral Head])[
  #grid(
    [
      #color-block(title: [Concept (fusion + CORAL head)])[
        - Concatenate features:
          $
            bold(h) =
            [#(symb.vin.pose_emb) ;
              #(symb.vin.global) ;
              #(symb.vin.sem_proj) ;
              #(symb.vin.sem_grid)]
          $
        - MLP scorer #sym.arrow.r CORAL logits #sym.arrow.r expected class score #(symb.vin.rri_hat) (regression proxy).
        - Continuous expected RRI uses class probs with bin reps $u_k$ from learned $u_0$, $delta_k$.
        - Naive candidate validity:
        #eqs.metrics.candidate_validity
      ]
      #quote-block[
        Candidate validity should be soft_!_]
    ],
    [
      #figure(
        image(fig_path + "diagrams/vin_nbv/mermaid/head_paper.png", height: 100%),
        caption: [Feature fusion + CORAL head.],
      )
    ],
  )
]



// #slide(title: [VIN-NBV (Frahm 2025) vs our VIN v3])[
//   #grid(
//     [
//       #color-block(title: [VIN-NBV feature construction])[
//         - Enrich a reconstructed point cloud with normals, visibility count, and depth.
//         - Per candidate view:
//           + project to a dense screen-space grid #code-inline[512x512x5] (then downsample to #code-inline[256x256]),
//           + compute per-pixel variance plus pooled grid features,
//           + compute an "emptiness" feature from empty pixels (inside/outside the hull).
//         - Add stage cue: number of base views.
//         - CNN encodes the grid to a global view feature; an MLP scores candidates.
//         - Candidate visibility enters explicitly (visibility count + empty-pixel counting). @VIN-NBV-frahm2025
//       ]
//     ],
//     [
//       #color-block(title: [VIN v3 (oracle_rri) design])[
//         - Use EVL voxel evidence as scene context (frozen backbone) plus semidense SLAM points.
//         - Per candidate view:
//           + rig-relative pose encoding (R6D + LFF),
//           + semidense projection stats (visibility, coverage, depth moments; reliability-weighted),
//           + coarse grid + tiny CNN for view-plane structure (#code-inline[G_sem] from config).
//         - Pose-conditioned global attention pools the voxel field to a per-candidate feature vector #symb.vin.global.
//         - CORAL ordinal head (fixed bins) instead of continuous regression.
//         - Candidate visibility enters as a feature; training can additionally reweight losses by visibility/coverage proxies.
//       ]
//     ],
//   )
// ]


// ---------------------------------------------------------------------------
// Training: Objective, Metrics & Diagnostics
// ---------------------------------------------------------------------------

#section-slide(
  title: [Training: Objective, Metrics & Diagnostics],
  subtitle: [Ordinal supervision + diagnostics-first monitoring],
)

// Ordering: (1) objective, (2) metric definitions + curves, (3) aux schedule,
// (4) start→finish summary, (5) best-vs-baseline comparison.
#slide(title: [Training objective (ordinal supervision)])[
  #grid(
    columns: (1.25fr, 1fr),
    gutter: 0.35cm,
    [
      #color-block(title: [Objective])[
        - CORAL loss + aux. regression loss $#(symb.vin.loss) _("reg")$
        #eqs.vin.loss_total
        #eqs.vin.aux_reg_huber
        #eqs.vin.aux_weight
        #v(0.5em)
        - Coverage/visibility curriculum: reweight per-candidate loss by evidence $w_i(t) = (1 - lambda_t) + lambda_t ( #symb.vin.voxel_valid _i dot #symb.vin.sem_valid _i )$ and anneal $lambda_t -> 0$ over training.
      ]
    ],
    [
      #figure(
        image(fig_path + "wandb/train-corlal-rel-step.png", width: 80%),
        caption: [Training CORAL relative loss.],
      )
      #figure(
        image(fig_path + "wandb/train-coral-rel-epoch.png", width: 90%),
        caption: [Epoch-level training CORAL relative loss.],
      )
    ],
  )
]

#slide(title: [Best-run curves + Metrics])[
  #grid(
    columns: (1fr, 1.2fr),
    gutter: 0.35cm,
    [
      #color-block(title: [Metrics (definition + intuition)], spacing: 0.4em)[
        - Relative CORAL loss:
        #eqs.coral.rel_random
        - Ranking agreement:
        #eqs.metrics.spearman
        - Top-3 bin accuracy:
        #eqs.metrics.topk_acc
      ]
    ],
    [
      #figure(
        image(fig_path + "wandb/val-coral-rel.png", width: 70%),
        caption: [Relative CORAL loss.],
      )
      #figure(
        image(fig_path + "wandb/val-top3-acc.png", width: 70%),
        caption: [Top-3 bin accuracy.],
      )
    ],
  )
]

// #slide(title: [Auxiliary regression: loss + schedule])[
//   #grid(
//     [
//       #color-block(title: [Auxiliary Loss])[
//         - Auxiliary loss $#(symb.vin.loss) _("reg")$ (Huber) stabilizes early training.
//         - Weight schedule $#symb.vin.aux_weight (t)$ anneals over time.
//         - As $#symb.vin.aux_weight (t)$ decays, the ordinal head dominates.
//       ]
//     ],
//     [
//       #grid(
//         rows: (1fr, 1fr),
//         gutter: 0.25cm,
//         figure(
//           image(fig_path + "wandb/train-aux-reg.png", width: 100%),
//           caption: [Train auxiliary regression loss.],
//         ),
//         figure(
//           image(fig_path + "wandb/train-aux-weight.png", width: 100%),
//           caption: [Aux weight schedule.],
//         ),
//       )
//     ],
//   )
// ]

#slide(title: [Best run: start #sym.arrow.r finish summary])[
  #let r = wb_top2.rtjvfyyp

  #let fmt(m, key, digits: 3, pct_digits: 1) = {
    let x = m.at(key)
    let start = round(x.start, digits: digits)
    let end = round(x.end, digits: digits)
    let delta_pct = round(x.delta_pct, digits: pct_digits)
    [#start #sym.arrow.r #end (#delta_pct%)]
  }


  #presentation-table(
    columns: (auto, auto),
    align: (left, left),
    text-size: 17pt,
    header: ([Metric], [Start #sym.arrow.r finish]),
    rows: (
      [Training $#(symb.vin.loss) _("rel")$],
      [#fmt(r.metrics, "train/coral_loss_rel_random_step")],
      [Validation $#(symb.vin.loss) _("rel")$],
      [#fmt(r.metrics, "val/coral_loss_rel_random")],
      [Spearman $rho$],
      [#fmt(r.metrics, "val-aux/spearman")],
      [Top-3 $"TopKAcc"(3)$],
      [#fmt(r.metrics, "val-aux/top3_accuracy")],
    ),
  )
]


#slide(title: [Calibration])[
  #figure(
    image(fig_path + "app-paper/pred_vs_oracle_scatter.png", width: 100%),
    caption: [Predicted vs Oracle RRI scatter.],
  )
]

#slide(title: [Comparison: best run vs baseline run])[
  #let r1 = wb_top2.hq1how1j
  #let r2 = wb_top2.rtjvfyyp

  #grid(
    columns: (1fr, 1.2fr),
    gutter: 0.35cm,
    [
      #color-block(title: [Ablation])[
        + `OneCycleLR` #sym.arrow `ReduceOnPlateau`
        + No trajectory encoder
        + No auxiliary regression loss
        + Batch size 8 #sym.arrow 16
      ]
      #color-block(title: [Final validation metrics (last logged)])[
        #set text(size: 13pt)
        #presentation-table(
          columns: (9em, 1fr, 1fr, 1fr),
          align: (left, left, left, left),
          text-size: 13pt,
          header: ([Run], [$#(symb.vin.loss) _("rel")$], [$rho$], [$"TopKAcc"(3)$]),
          rows: (
            [`base`],
            [#round(r1.metrics.at("val/coral_loss_rel_random").end, digits: 3)],
            [#round(r1.metrics.at("val-aux/spearman").end, digits: 3)],
            [#round(r1.metrics.at("val-aux/top3_accuracy").end, digits: 3)],
            [`ablation`],
            [#round(r2.metrics.at("val/coral_loss_rel_random").end, digits: 3)],
            [#round(r2.metrics.at("val-aux/spearman").end, digits: 3)],
            [#round(r2.metrics.at("val-aux/top3_accuracy").end, digits: 3)],
          ),
        )
      ]
    ],
    [
      #figure(
        grid(
          columns: (1fr, 1fr),
          rows: (auto, 1fr, 1fr),
          gutter: 0.25cm,
          align(center)[#text(weight: "bold")[`ablation`]], align(center)[#text(weight: "bold")[`base`]],
          image(fig_path + "wandb/hq1how1j/val-figures/confusion_start.png", width: 100%),
          image(fig_path + "wandb/rtjvfyyp/val-figures/confusion_start.png", width: 100%),

          image(fig_path + "wandb/hq1how1j/val-figures/confusion_end.png", width: 100%),
          image(fig_path + "wandb/rtjvfyyp/val-figures/confusion_end.png", width: 100%),
        ),
      )
    ],
  )
]


#slide(title: [Key takeaways])[
  #color-block(title: [What is solid now])[
    - Oracle RRI pipeline is implemented end-to-end and fully functional.
    - Offline cache enables fast training/debug loops with a typed batching.
    - Rich training and post-hoc diagnostics.
  ]
  #color-block(title: [Main limitations])[
    - Data scale: Trained on #cache.unique_scenes scenes and #cache.train_entries / #cache.total_snippets snippets (#(round(cache.train_entries / cache.total_snippets))%).
    - Weak component-level signals: Too many DoFs have been changed at once!
    - EVL backbone's Voxel Fields are too narrow (4x4x4)m
  ]
  #color-block(title: [Master thesis next steps])[
    - Scale dataset (more scenes, more snippets, increase variety, *more compute*).
    - Streamline OfflineCacheDataset (it's a mess)
    - Run clean Optuna sweep (stationary regime; architecture toggles only).
    - Strengthen evidences on different architectural choices.
    - Entity-wise RRI should should be feasible now.
  ]
]

#slide(title: [References])[
  #text(size: 10pt)[
    #columns(2, gutter: 0.6cm)[
      #bibliography("/references.bib", style: "/ieee.csl")
    ]
  ]
]
