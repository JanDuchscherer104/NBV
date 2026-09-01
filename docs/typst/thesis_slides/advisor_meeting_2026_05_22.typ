// Advisor meeting deck for the ARIA-NBV master-thesis phase.
// Style follows docs/typst/seminar_slides/slides_4.typ.

#import "../shared/slide-template.typ": *
#import "@preview/muchpdf:0.1.1": muchpdf
#import "@preview/dashy-todo:0.1.3": todo as dashy_todo
#import "../shared/tables.typ": presentation-table

#import "../shared/macros.typ": *

#let fig_path = "../../figures/"
#let thesis_fig_path = "figures/"
#let hestia_url = "https://johnnylu305.github.io/hestia_web"
#let gymnasium_url = "https://gymnasium.farama.org/"
#let sb3_url = "https://stable-baselines3.readthedocs.io/"
#let isaac_sim_url = "https://developer.nvidia.com/isaac/sim"
#let habitat_sim_url = "https://aihabitat.org/"
#let ai2thor_url = "https://ai2thor.allenai.org/"
#let procthor_url = "https://ai2thor.allenai.org/procthor/"

#set document(
  title: [ARIA-NBV: Target-Conditioned NBV Planning in Egocentric Scenarios],
  author: "Jan Duchscherer",
)

#show: definitely-not-isec-theme.with(
  aspect-ratio: "16-9",
  slide-alignment: top,
  progress-bar: true,
  font: "DejaVu Sans",
  institute: [Munich University of Applied Sciences],
  logo: [#image(fig_path + "branding/hm-logo.svg", width: 2cm)],
  config-info(
    title: [ARIA-NBV: Target-Conditioned RRI + $Q_H$],
    subtitle: [Rollout data, finite-candidate planning, advisor alignment],
    authors: [*Jan Duchscherer*],
    extra: [Advisor Meeting #sym.dot 22 May 2026],
    footer: [
      #grid(
        columns: (1fr, auto, 1fr),
        align: bottom,
        align(left)[Jan Duchscherer], align(center)[ARIA-NBV thesis alignment], align(right)[22 May 2026],
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

#set text(size: 17pt, font: "DejaVu Sans")
#show figure.caption: set text(size: 12pt, weight: "medium", fill: theme_color_footer.darken(40%))
#show grid: set grid(columns: (1fr, 1fr), gutter: 0.8cm)
#show cite: set text(size: 10pt)
#show bibliography: set text(size: 7pt)
#show link: set text(fill: blue)
#show link: it => underline(it)

#let muted(body) = text(fill: theme_color_footer.darken(25%))[#body]
#let slide-small(body) = {
  set text(size: 14.7pt)
  set par(leading: 0.72em)
  body
}
#let slide-tiny(body) = {
  set text(size: 12.4pt)
  set par(leading: 0.68em)
  body
}
#let tag(body, fill: theme_color_block, stroke: theme_color_block.darken(15%)) = rect(
  radius: 5pt,
  inset: (x: 6pt, y: 3pt),
  fill: fill,
  stroke: 0.6pt + stroke,
)[#text(size: 10.5pt, weight: 650)[#body]]

#let mini-flow(items) = {
  grid(
    columns: items.map(_ => 1fr),
    gutter: 0.18cm,
    ..items.map(item => rect(
      width: 100%,
      radius: 6pt,
      inset: (x: 5pt, y: 5pt),
      fill: theme_color_block,
      stroke: 0.45pt + theme_color_block.darken(18%),
    )[
      #align(center + horizon)[#text(size: 12.2pt, weight: 650)[#item]]
    ])
  )
}

#let zarr-node(title, body, fill: theme_color_block, stroke: theme_color_block.darken(18%)) = rect(
  width: 100%,
  radius: 5pt,
  inset: (x: 6pt, y: 5pt),
  fill: fill,
  stroke: 0.55pt + stroke,
)[
  #text(size: 11.4pt, weight: 700)[#title]
  #v(0.12em)
  #text(size: 9.3pt, fill: theme_color_footer.darken(45%))[#body]
]

#let zarr-arrow(label) = align(center)[
  #text(size: 9.4pt, fill: theme_color_footer.darken(25%))[
    #sym.arrow.b #h(0.25em) #label
  ]
]

#let todo_marker(kind, body, stroke: orange, sources: none) = text(size: 8.6pt)[
  #dashy_todo(position: "inline", stroke: stroke)[
    *#kind:* #body
    #if sources != none [
      \
      #text(size: 7.4pt, fill: theme_color_footer.darken(45%))[Sources: #sources]
    ]
  ]
]

#let conflict_todo(body, sources: none) = todo_marker([Conflict], body, stroke: red, sources: sources)
#let decision_todo(body, owner: [advisor], sources: none) = todo_marker(
  [Open decision (#owner)],
  body,
  stroke: orange,
  sources: sources,
)
#let necessary_todo(body, gate: none, sources: none) = todo_marker(
  [WIP necessary],
  [
    #body
    #if gate != none [
      \
      #text(size: 7.4pt, fill: theme_color_footer.darken(45%))[Gate: #gate]
    ]
  ],
  stroke: blue,
  sources: sources,
)
#let optional_todo(body, sources: none) = todo_marker([Optional ablation], body, stroke: purple, sources: sources)
#let prune_todo(body, sources: none) = todo_marker([Prune candidate], body, stroke: gray, sources: sources)

#title-slide()

#slide(title: [Source Governance / Highest Truth])[
  #grid(
    columns: (1fr, 1fr),
    gutter: 0.5cm,
    [
      #color-block(title: [Owner after this consolidation], spacing: 0.4em)[
        #slide-small[
          This deck is an _advisor-facing thesis summary_. The active Typst thesis owns current RQ order, target-RRI/$Q_H$ scope, state boundaries, and evidence gates; advisor review records unresolved locks.

          #v(0.2em)
          This summary follows the active Typst RQ section and development roadmap. Historical seminar and outlook decks remain evidence, not priority.
        ]
      ]
    ],
    [
      #color-block(title: [Conflict rule], spacing: 0.4em)[
        #slide-small[
          - Current deck claim beats historical seminar/outlook wording.
          - Current code and generated API pages beat planned implementation claims.
          - The development roadmap and advisor review notes record unresolved decisions.
          - Any imported historical claim must be marked as conflict, WIP, optional, or prune.
        ]
      ]
      #v(0.18em)
      #decision_todo(
        [After advisor acceptance, mirror this owner promotion into the context hierarchy, roadmap/questions, and memory.],
        sources: [`aria-nbv-context`; autoresearch report],
      )
    ],
  )
]

#slide(title: [State Matrix For The Thesis Contract])[
  #figure(
    kind: "table",
    supplement: [Table],
    caption: [Classification used by this deck to separate implemented evidence, current claims, WIP, and open advisor locks.],
    text(size: 8.9pt)[
      #presentation-table(
        columns: (0.72fr, 1.58fr, 1.2fr),
        align: (left, left, left),
        text-size: 8.9pt,
        header: ([State], [Meaning], [Owner / action]),
        rows: ([Implemented substrate], [Code, data paths, diagnostics, or historical results already present.],
        [deck summary plus code/API/seminar links],
        [Current thesis core],
        [Required claim path for thesis success: target-RRI, finite candidates, offline $Q_H$.],

        [this deck], [WIP necessary], [Must land before thesis-grade quantitative claims.],
        [roadmap/backlog owner], [Optional ablation], [Useful only if schedule/support allows.],
        [appendix or roadmap], [Open decision], [Advisor-facing unresolved choice.],
        [advisor-review notes],
        [Conflict / historical],
        [Older source that contradicts the current contract unless demoted.],

        [typed TODO or archive note], [Prune candidate], [Operational detail that should leave the main flow.],
        [appendix/backlog/debrief]),
      )
    ],
  )
]

#slide(title: [Todo Flavor Legend])[
  #grid(
    columns: (1fr, 1fr),
    gutter: 0.5cm,
    [
      #color-block(title: [Decision markers], spacing: 0.4em)[
        #slide-small[
          #decision_todo(
            [Advisor must choose or accept the contract before this becomes thesis-grade truth.],
            sources: [deck; advisor review],
          )
          #v(0.25em)
          #conflict_todo(
            [A historical source disagrees with the current deck or code and must be demoted, rewritten, or archived.],
            sources: [seminar / outlook / memory],
          )
        ]
      ]
    ],
    [
      #color-block(title: [Work markers], spacing: 0.4em)[
        #slide-small[
          #necessary_todo(
            [Required before quantitative advisor-facing claims.],
            gate: [roadmap milestone],
            sources: [roadmap; backlog],
          )
          #v(0.25em)
          #optional_todo([Useful ablation if support, time, or compute allows.])
          #v(0.25em)
          #prune_todo([Operational detail that should leave the main deck flow.])
        ]
      ]
    ],
  )
]

#slide(title: [Central Research Question])[
  #grid(
    columns: (1fr, 1fr),
    gutter: 0.55cm,
    [
      #color-block(title: [Main Thesis Question], spacing: 0.45em)[
        #slide-small[
          Can ARIA-NBV perform _target-conditioned_, _RRI-based_ multi-step NBV by training a _discrete finite-candidate_ value model $Q_(H,theta)$ that predicts _fixed-horizon cumulative target-specific RRI_ and improves _endpoint target reconstruction quality_ over a _myopic scorer_?
        ]
      ]
      #text(size: 12.8pt)[
        $
          #eqs.entity.target_error
          \
          #eqs.entity.endpoint_gain
        $
      ]
      #text(size: 9.4pt, fill: theme_color_footer.darken(35%))[
        Substrate and objective anchors: Project Aria / ASE @projectaria-engel2023 @ProjectAria-ASE-2025, VIN-NBV quality-driven RRI @VIN-NBV-frahm2025, EFM3D/EVL actor-visible state @EFM3D-straub2024 @EVL-Doc-2025.
      ]
    ],
    [
      #color-block(title: [Gated Research Questions], spacing: 0.32em)[
        #text(size: 8.6pt)[
          #presentation-table(
            columns: (0.55fr, 2.08fr),
            align: (left, left),
            text-size: 8.6pt,
            header: ([RQ], [Question]),
            rows: (

            [*RQ1 Method*],
            [Which target-RRI objective, RL methodology and offline finite-candidate $Q_H$ formulation are most idiomatic? Fixed vs variable horizon?
            ],

            [*RQ2 Offline*],
            [Can offline finite-candidate $Q_H$ recover headroom over a learned myopic scorer, myopically sampled oracle rollouts or even Gumbel-Top-$k$ oracle rollouts?
            ],

            [*RQ3 Repr.*],
            [Which actor-visible scene, target, history, visibility, and candidate-view representations improve $Q_H$ under RQ2: semidense geometry, DINO-on-point, EVL/OBB evidence, crop descriptors, $bb(S)^2$ view memory, and candidate frustum/support?],

            [*RQ4 Support*],
            [Do realistic mixed candidates and replayable rollout traces provide hard-valid, diverse support, and does scaling this support improve held-out $Q_H$ generalization? How can we scale beyond the GT mesh-labeled dataset?],

            [*RQ5 Online*],
            [After offline $Q_H$, does online training over the same discrete finite-candidate contract improve endpoint gain? Can the multi-step scorer predict invalid actions?],

            [*RQ6 Cont.*],
            [Do continuous/hierarchical target-then-pose policies, e.g. actor-critic, yield headroom over the best finite-candidate policy under the same target-RRI objective?],
            ),
          )
        ]
      ]
    ],
  )
]

#slide(title: [Implemented Substrate vs Current Thesis Core])[
  #grid(
    columns: (1fr, 1fr),
    gutter: 0.5cm,
    [
      #color-block(title: [Implemented substrate], spacing: 0.35em)[
        #slide-small[
          - ASE/Project-Aria data plumbing, calibrated poses, mesh/oracle assets, and offline cache operations are available as the supervised substrate.
          - Oracle target/scene RRI, VIN-style one-step scoring, feature/cache diagnostics, Streamlit, and Rerun/offline-store inspection already exist as evidence surfaces.
          - Seminar paper and older slides document this implemented substrate historically; they do not set current thesis priority.
        ]
      ]
    ],
    [
      #color-block(title: [Current thesis core], spacing: 0.35em)[
        #slide-small[
          1. Define target-conditioned root-normalized endpoint gain.
          2. Trust actor-visible target/candidate state and hard-valid masks.
          3. Establish one-step target scorer and rollout support.
          4. Train/evaluate finite-candidate offline fitted $Q_H$.
          5. Gate online discrete $Q_H$ and continuous target-then-pose policies only after offline evidence.
        ]
      ]
    ],
  )
]

#slide(title: [Advisor Decisions From Outlook])[
  #grid(
    columns: (1fr, 1fr),
    gutter: 0.48cm,
    [
      #color-block(title: [Operational locks], spacing: 0.36em)[
        #slide-small[
          - Compute first: LRZ/Slurm and storage gates before broad generation; if local, keep the stack reproducible under WSL/workstation constraints.
          - Access now: Project Aria Gen2 and ASE/generation-stack availability determine whether the thesis remains mesh-backed or needs a simulator sidecar.
          - Core stays ASE / mesh-backed until target-specific RRI, finite candidates, and offline $Q_H$ are interpretable.
          - Semantic-global VLA/VLM planning remains outside thesis core.
        ]
      ]
    ],
    [
      #color-block(title: [VIN and method budget], spacing: 0.36em)[
        #slide-small[
          - Prefer the minimum single-step VIN work needed for trust: calibration, CORAL/binning, auxiliary loss, and key-input ablations.
          - Avoid broad VIN-v4/backbone search before the multi-step target-RRI protocol and support gates pass.
          - Phase 1 stays discrete finite-candidate: beam/MPC/close-greedy/offline $Q_H$ before continuous actor-critic.
          - Candidate rules are hard masks/reasons first; learned feasibility or rule-violation prediction is an optional extension.
        ]
      ]
    ],
  )
]

#slide(title: [Formal State Split])[
  #grid(
    columns: (0.92fr, 1.08fr),
    gutter: 0.45cm,
    [
      #color-block(title: [Three visibility regimes], spacing: 0.35em)[
        #text(size: 10.55pt)[
          #presentation-table(
            columns: (0.38fr, 1.34fr, 1.22fr),
            align: (left, left, left),
            text-size: 10.55pt,
            header: ([State], [Contains], [Allowed use]),
            rows: (
            [#symb.rl.s_hist],
            [logged RGB/pose, semidense history, root EVL, observed or predicted target hypotheses],
            [target selection and root descriptor construction],

            [#symb.rl.s_cf0],
            [accumulated counterfactual geometry, fixed root EVL/local evidence, target descriptor, selected-view history, candidate table, masks/reasons],
            [actor-visible scorer and $Q_H$ input],

            [#symb.rl.s_oracle],
            [#symb.rl.s_cf0 plus GT mesh, matched target mesh, all-candidate renders, oracle labels],
            [labels, upper bounds, matching checks, evaluation only],
            ),
          )
        ]
      ]
    ],
    [
      #color-block(title: [Shared notation anchors], spacing: 0.28em)[
        #text(size: 10.2pt)[
          $
            #eqs.rl.s_hist
            \
            #eqs.rl.s_cf0
            \
            #eqs.rl.s_oracle
          $
        ]
        #v(0.15em)
        #good-note[
          #text(size: 10.8pt)[
            The leak boundary is symbolic: GT OBBs, target meshes, all-candidate renders, and oracle scores never become V1 actor-visible policy inputs.
          ]
        ]
        #v(0.16em)
        #necessary_todo(
          [Mirror this split in any remaining proposal/roadmap text that still conflates logged state, counterfactual actor state, and privileged oracle state.],
          gate: [source-truth cleanup],
          sources: [`main.typ`; archived advisor handout; shared symbols/equations],
        )
      ]
    ],
  )
]

#slide(title: [Target Selection And GT-EVAL Contract])[
  #grid(
    columns: (0.94fr, 1.06fr),
    gutter: 0.45cm,
    [
      #color-block(title: [Protocol variants], spacing: 0.34em)[
        #text(size: 10.7pt)[
          #presentation-table(
            columns: (0.38fr, 1.5fr, 1.08fr),
            align: (left, left, left),
            text-size: 10.7pt,
            header: ([Mode], [Meaning], [Status]),
            rows: (
            [V0], [GT OBB target input], [diagnostic upper bound],
            [V1], [actor-visible target hypotheses only], [main thesis protocol],
            [OBS-SEL], [choose observed/predicted target hypothesis from #symb.rl.s_hist], [selection step],
            [PRED-Q], [$hat(r)_psi^e$ or $Q_H$ conditions on actor-visible target descriptor], [learned policy input],
            [GT-EVAL], [GT OBBs/meshes used for labels, deterministic matching, evaluation], [privileged evaluation],
            ),
          )
        ]
      ]
      #v(0.16em)
      #text(size: 9.2pt, fill: theme_color_footer.darken(35%))[
        Target selection and target-to-GT matching are distinct operations. V1 chooses a target without GT; GT-EVAL matches only after selection.
      ]
    ],
    [
      #color-block(title: [Eligibility and matching], spacing: 0.28em)[
        #text(size: 9.6pt)[
          $
            #eqs.entity.target_descriptor
            \
            #eqs.entity.target_match_acceptance
          $
        ]
        #v(0.16em)
        #slide-small[
          - Actor-visible eligibility: support, projected visibility, confidence, class, distance, and target-interest sampler.
          - Deterministic GT match: class-compatible 3D IoU plus top-1/top-2 ambiguity gap.
          - Target-invalid cases: unmatched, unsupported, or ambiguous targets are excluded/reportable protocol failures, not low-RRI training samples.
          - Projected target feasibility uses clipped image-overlap area, not raw extents outside the image.
        ]
        #decision_todo(
          [Lock numeric acceptance thresholds, ambiguity gap, and target-interest sampling policy.],
          sources: [`main.typ`; archived advisor handout; advisor review],
        )
      ]
    ],
  )
]

#slide(title: [RQ Dependency Chain])[
  #grid(
    columns: (0.74fr, 1.26fr),
    gutter: 0.45cm,
    [
      #color-block(title: [Dependency order], spacing: 0.28em)[
        #text(size: 11.5pt)[
          #mini-flow((
            [objective + metrics],
            [target + matching],
            [candidate + replay],
          ))
          #v(0.22em)
          #mini-flow((
            [headroom + $Q_H$],
            [scale],
            [escalation],
          ))
        ]
      ]
    ],
    [
      #color-block(title: [Interpretation rule], spacing: 0.35em)[
        #slide-small[
          Objective and target matching are prerequisites for every downstream claim. Candidate support is the prerequisite for headroom. Headroom is the prerequisite for interpreting $Q_H$ recovery. Scale and online/continuous extensions are meaningful only after the finite-candidate contract is stable.

          #v(0.2em)
          This dependency DAG is stricter than a meeting agenda: a later RQ can be deferred without weakening the core thesis if the upstream evidence is clean.
        ]
      ]
      #v(0.16em)
      #good-note[
        #text(size: 10.8pt)[
          RQ5 online discrete $Q_H$ and RQ6 continuous target-then-pose remain gated extensions, not substitutes for offline finite-candidate evidence.
        ]
      ]
    ],
  )
]

#slide(title: [RQ3: Scene / Target / Candidate Tokens])[
  #grid(
    columns: (1.0fr, 1.0fr),
    gutter: 0.45cm,
    [
      #color-block(title: [Scene memory stance], spacing: 0.35em)[
        #text(size: 12.2pt)[
          - EVL: actor-visible target support and local evidence.
          - Semidense/fused points: broader scene memory.
          - DINO-on-point features: planned representation ablation, not current cache schema.
          - Target-specific RRI and $Q_H$ remain the utility and oracle-evaluation signal.

          #v(0.2em)
          #text(size: 11.6pt)[
            $
              #eqs.scene.qh_scene_memory
              \
              #eqs.features.point_dino_token
            $
          ]
        ]
      ]
    ],
    [
      #color-block(title: [Queryable target and candidate evidence], spacing: 0.35em)[
        #text(size: 11.7pt)[
          Candidate rows query the same actor-visible feature bank through target, frustum, and target-frustum intersection reads:

          #v(0.18em)
          $
            #eqs.scene.candidate_query_pools
          $

          #v(0.22em)
          #mini-flow((
            [scene bank],
            [target token $bold(T)_e$],
            [candidate rows],
          ))

          #v(0.25em)
          Target crops use observed/predicted OBBs. GT crops and meshes remain labels/evaluation only.
        ]
      ]
    ],
  )
]

#slide(title: [RQ3 Detail: Target / View / History Budget])[
  #figure(
    kind: "table",
    supplement: [Table],
    caption: [Actor-visible feature budget and missing ablations before interpreting set-interaction gains.],
    text(size: 8.55pt)[
      #presentation-table(
        columns: (0.48fr, 1.25fr, 1.18fr),
        align: (left, left, left),
        text-size: 8.55pt,
        header: ([Block], [Baseline], [Extensions]),
        rows: (
        [Target encoding],
        [observed/predicted OBB geometry; class/confidence; projected area; semidense/EVL features; relative target pose],

        [actor-visible crop descriptor ablation; final match/support thresholds and ambiguity policy],
        [View / candidate encoding],
        [pose; target-relative pose; R6D rotation; target bearing/incidence; path cost; strategy provenance; frustum and target-frustum support],

        [query-centric relative bias; Fisher/SCONE overlap channels; held-out candidate-generator stress],
        [History / direction],
        [selected-view history; remaining budget; accumulated geometry; direction moment/novelty around target-local cells],

        [richer counterfactual RGB/SLAM/semantic history unless synthesized later],
        [Validity / provenance],
        [hard mask; invalid reason; valid count; strategy/mixture ids; per-family support and gain diagnostics],

        [row shuffle; duplicate-row; mask isolation; valid-count sensitivity; with/without-strategy tests],
        ),
      )
    ],
  )

  #grid(
    columns: (1fr, 1fr),
    gutter: 0.45cm,
    [
      #color-block(title: [Compact notation], spacing: 0.28em)[
        #text(size: 9.45pt)[
          $
            #eqs.entity.target_descriptor
            \
            #eqs.spatial.candidate_pose_features
          $
        ]
        #v(0.12em)
        #decision_todo(
          [Lock candidate-pose descriptor: R6D plus translation/bearing features, or a query-centric QCNet-style relative descriptor.],
          sources: [shared feature equations; RQ3 representation text],
        )
      ]
    ],
    [
      #good-note[
        #text(size: 11.2pt)[
          Boundary: GT OBBs, GT target crops, GT meshes, oracle RRI, and all-candidate GT renders are labels/evaluation only, not V1 actor-visible encodings.
        ]
      ]
      #v(0.18em)
      #text(size: 10.4pt, fill: theme_color_footer.darken(35%))[
        Conservative rule: feature channels and set interaction stay ablations until myopic calibration, masks, replay support, and oracle-rescored selected actions are trusted.
      ]
    ],
  )
]

#slide(title: [Candidate Transition Contract])[
  #grid(
    columns: (1fr, 1fr),
    gutter: 0.45cm,
    [
      #color-block(title: [One selected candidate transitions state], spacing: 0.35em)[
        #slide-small[
          - Action is a valid candidate row index: choose $a_t=i in cal(A)_t$.
          - Oracle rendering/retrieval materializes only selected $q_(t,i)$ for the transition.
          - Acquired geometry updates the counterfactual point proxy; scalar target distances, support counts, masks, and gains are training-core facts.
          - All-candidate renders remain oracle-only labels or audit payloads.

          #v(0.16em)
          $
            #eqs.rl.finite_action_set
          $
        ]
      ]
    ],
    [
      #color-block(title: [Successor table semantics], spacing: 0.35em)[
        #slide-small[
          - Regenerate $cal(Q)_(t+1)$ from updated geometry, selected-view history, remaining horizon, and the same mixture families.
          - Keep root local EVL fixed unless an explicit ablation recomputes it.
          - Strategy vocabulary: target/look-at, radial-towards, radial-away, forward-rig, bounded yaw/pitch/roll jitter.
          - Fixed root EVL and selected-action replay make $Q_H$ rows comparable.
        ]
      ]
      #v(0.18em)
      #decision_todo(
        [Lock whether successor candidate regeneration may change anchor/candidate bounds, or must preserve root-level candidate budget exactly.],
        sources: [`main.typ`; archived advisor handout; rollout contract],
      )
    ],
  )
]

#slide(title: [RQ4: Support + Scale Controls])[
  #grid(
    columns: (0.92fr, 1.08fr),
    gutter: 0.45cm,
    [
      #color-block(title: [Support contract], spacing: 0.35em)[
        #text(size: 11.6pt)[
          Candidate and rollout data are useful only if they cover valid target-relevant decisions, not just many rows.

          #v(0.16em)
          - Mixed target-centric and exploration families.
          - Regenerated successor candidate tables.
          - Hard-valid masks plus reason codes for invalid rows.
          - Held-out $Q_H$ generalization under fixed target-RRI supervision.
          - External data only if comparable mesh/oracle target labels exist.

          #v(0.15em)
          Invalid candidates are support failures or constraints, never low-RRI examples.
        ]
      ]
    ],
    [
      #figure(
        kind: "table",
        supplement: [Table],
        caption: [Support and model controls before interpreting value-model gains.],
        text(size: 9.65pt)[
          #presentation-table(
            columns: (0.32fr, 0.98fr, 1.44fr),
            align: (left, left, left),
            text-size: 9.65pt,
            header: ([Gate], [Check], [Purpose]),
            rows: ([S0], [H=1 label profile],
            [target gain is non-flat and valid rows exist], [S1], [mixed candidate preflight],
            [target-aware support plus exploration], [S2], [H>1 replay traces],
            [successor tables and selected-depth lineage], [S3], [stochastic support],
            [avoid fitting only greedy chains], [S4], [scene-level scale],
            [held-out generalization without split leakage], [M0], [MLP / DeepSets / Set Transformer],
            [model-control ladder for attribution]),
          )
        ],
      )
    ],
  )
  #v(0.18em)
  #good-note[
    #text(
      size: 11.4pt,
    )[Do not compare architecture, rollout, or $Q_H$ conclusions across runs that silently change scene, target, candidate, or validity coverage.]
  ]
]

#slide(title: [RQ2: Offline Finite-Candidate $Q_H$])[
  #grid(
    columns: (0.9fr, 1.1fr),
    gutter: 0.45cm,
    [
      #color-block(title: [Training path], spacing: 0.42em)[
        #slide-small[
          1. Train target-conditioned one-step scorer $hat(r)_psi^e$ on valid all-candidate labels.
          2. Use held-out rank, top-$k$, calibration, and oracle-selected rollouts as evidence gate.
          3. Fit an uncentred residual $Q_H$ on selected-action transitions.
          4. Decode only over hard-valid candidates.
          #v(0.18em)
          #text(
            size: 10.7pt,
            fill: theme_color_footer.darken(35%),
          )[Why this RQ exists: test the actual planning claim after the myopic control and replay support are trusted.]
        ]
      ]
      #text(size: 9.8pt)[
        $
          #symb.rl.qh_theta (#symb.rl.s_cf0, #symb.entity.target_desc, #symb.rl.candidate_qti)
          =
          hat(r)_psi^e (#symb.rl.s_cf0, #symb.entity.target_desc, #symb.rl.candidate_qti)
          +
          V_theta (#symb.rl.s_cf0, #symb.entity.target_desc, bold(H)_t)
          \
          quad
          +
          A_(theta,i)^H
          -
          (1) / (abs(#symb.rl.action_set))
          sum_(j in #symb.rl.action_set) A_(theta,j)^H
        $
      ]
    ],
    [
      #color-block(title: [Readable replay contract], spacing: 0.38em)[
        #text(size: 12.2pt)[
          #mini-flow((
            [all valid candidate labels],
            [myopic scorer $hat(r)_psi^e$],
            [calibrated control],
          ))
          #v(0.28em)
          #mini-flow((
            [selected transitions],
            [successor $cal(Q)_(t+1)$],
            [masked replay rows],
          ))
          #v(0.28em)
          #mini-flow((
            [residual $Q_H$],
            [oracle-rescore policy],
            [report $eta_Q$],
          ))
        ]
      ]
      #color-block(title: [Masked Double-Q target], spacing: 0.35em)[
        #text(size: 12.2pt)[
          $
            #eqs.rl.qh_doubleq_index
            \
            #eqs.rl.qh_doubleq_target
          $

          #v(0.15em)
          #text(size: 10.7pt, fill: theme_color_footer.darken(35%))[
            Non-expanded candidates train myopic rows only; $Q_H$ backups require selected transitions and successor candidate tables.
          ]
        ]
      ]
    ],
  )
]

#slide(title: [RQ2: Offline $Q_H$ Evidence Gates])[
  #grid(
    columns: (1.05fr, 0.95fr),
    gutter: 0.45cm,
    [
      #color-block(title: [Matched policy ladder], spacing: 0.4em)[
        #slide-small[
          - $pi_"oracle-1"$: one-step oracle greedy upper reference.
          - $pi_"oracle-H"$: bounded oracle lookahead / headroom reference.
          - $pi_"learned-1"$: learned actor-visible myopic scorer.
          - $pi_Q$: offline learned $Q_H$ policy.

          #v(0.22em)
          Gumbel-Top-$k$ belongs to rollout-support diversity, not the main policy ladder.
        ]
      ]
    ],
    [
      #color-block(title: [Headroom and recovery], spacing: 0.35em)[
        #text(size: 13.2pt)[
          $
            #eqs.entity.lookahead_headroom
            \
            #eqs.entity.q_recovery
          $
        ]
      ]
      #color-block(title: [Reported Quantities], spacing: 0.35em)[
        #slide-small[
          - endpoint target gain;
          - cumulative target-root gain;
          - diagnostic target and scene RRI;
          - invalid-action rate and reason distribution;
          - path length, runtime, oracle eval count;
          - coverage gaps and scene-level splits.
        ]
      ]
    ],
  )
]

#slide(title: [Reward / Q / Critic Boundary])[
  #grid(
    columns: (1fr, 1fr),
    gutter: 0.48cm,
    [
      #color-block(title: [Current reward contract], spacing: 0.34em)[
        #slide-small[
          - Default reward is oracle target-root gain, not VIN; state-relative RRI stays diagnostic/VIN-compatible.
          - $gamma$ stays symbolic until RQ1/advisor lock; historical low-$gamma$ PPO diagnostics are not current truth.
          - Hard masks already reject collision, clearance, and bounds failures; invalid rows are constraints, not low-RRI samples.
          - `rollouts.zarr` owns counterfactual rollout chains and returns; VIN offline-store assets remain immutable source data.
        ]
        #v(0.12em)
        #text(size: 9.2pt)[
          $
            #eqs.rl.reward_geom
            \
            #eqs.rl.q_backup
          $
        ]
      ]
    ],
    [
      #color-block(title: [Open critic / surrogate questions], spacing: 0.34em)[
        #slide-small[
          - Make rule penalties explicit in any learned reward or evaluator that goes beyond hard masks.
          - Add VIN-backed counterfactual evaluation only after oracle target labels and myopic calibration are trusted.
          - Decide whether a privileged critic may use GT mesh, GT OBB, or segmentation cues while the actor remains V1 actor-visible.
          - Treat Gymnasium/SB3 PPO as diagnostic scaffolding unless it preserves the finite-candidate target-RRI comparison.
        ]
        #decision_todo(
          [Lock privileged-critic permissions and whether VIN may become a critic/surrogate beyond mesh-backed subsets.],
          sources: [historical outlook deck; advisor review],
        )
      ]
    ],
  )
]

#slide(title: [WIP Necessary Before Claims])[
  #grid(
    columns: (1fr, 1fr),
    gutter: 0.48cm,
    [
      #color-block(title: [Data and support gates], spacing: 0.38em)[
        #slide-small[
          #necessary_todo(
            [LRZ/Zarr preflight, stale-schema checks, and file-count/chunk budget before broad generation.],
            gate: [M1/M2 scale readiness],
            sources: [roadmap; DECISIONS],
          )
          #v(0.22em)
          #necessary_todo(
            [Scene-level split manifest and coverage tuple before shard grouping or thesis-grade split claims.],
            gate: [M4/M5 evaluation],
            sources: [questions; roadmap],
          )
          #v(0.22em)
          #necessary_todo(
            [Validate H=1 target-label profile before H>1 rollout traces and offline $Q_H$.],
            gate: [M2 -> M5],
            sources: [roadmap; rollout contract],
          )
        ]
      ]
    ],
    [
      #color-block(title: [Advisor locks that change interpretation], spacing: 0.38em)[
        #slide-small[
          #decision_todo(
            [Pass/fail threshold for positive $Q_H$ recovery and no-headroom interpretation.],
            sources: [RQ owner; advisor review],
          )
          #v(0.22em)
          #decision_todo(
            [Horizon, symbolic gamma, clipping, and near-solved-target handling.],
            sources: [RQ owner; advisor review],
          )
          #v(0.22em)
          #decision_todo(
            [V1 target matching thresholds and ambiguity policy for observed/predicted targets.],
            sources: [RQ owner; advisor review],
          )
        ]
      ]
    ],
  )
]

#slide(title: [RQ5/RQ6: Online and Continuous Headroom])[
  #grid(
    columns: (1fr, 1fr),
    gutter: 0.48cm,
    [
      #color-block(title: [RQ5: discrete online training], spacing: 0.4em)[
        #slide-small[
          After offline $Q_H$ is stable, test online interaction over the same finite candidate action contract.

          #v(0.25em)
          - Same target-RRI reward and oracle re-evaluation.
          - Same actor-visible state and masks/reasons.
          - Compare offline fitted $Q_H$ vs online-updated finite-candidate policy.
          - Pass only if endpoint gain or recovered headroom improves under matched budget.
        ]
      ]
    ],
    [
      #color-block(title: [RQ6: continuous hierarchical actions], spacing: 0.4em)[
        #slide-small[
          If finite-candidate evidence is stable, test whether continuous target-then-pose or hierarchical actions have extra headroom.

          #v(0.25em)
          - Factor target/look-at choice from feasible pose realization.
          - Compare against the best finite-candidate policy, not random.
          - Keep target-RRI objective and leakage rules unchanged.
          - Actor-critic may reuse learned $Q_H$ as initialization or critic signal.
        ]
      ]
    ],
  )

  #v(0.28em)
  #quote-block[
    #text(
      size: 12.0pt,
    )[RQ5/RQ6 are gated extension RQs: attempt them only when finite-candidate evidence and compute make the comparison interpretable.]
  ]
]

#slide(title: [RQ-Gated Roadmap to Next Milestones])[
  #grid(
    columns: (1fr, 1fr),
    gutter: 0.45cm,
    [
      #figure(
        kind: "table",
        supplement: [Table],
        caption: [Milestones from current docs; current focus is M1/M2 scale readiness before target rollout scale-up.],
        text(size: 10.6pt)[
          #presentation-table(
            columns: (0.36fr, 1.05fr, 1.3fr),
            align: (left, left, left),
            text-size: 10.6pt,
            header: ([M], [Gate], [Exit]),
            rows: ([M1], [data, cache, oracle],
            [frame/CW90/RRI contract and throughput], [M2], [one-step baseline],
            [calibration/ranking and scale plan], [M3], [target RRI],
            [V0/V1 target contract and sharding gate], [M4], [target scorer],
            [observed/predicted target-conditioned RRI], [M5], [rollouts and $Q_H$],
            [headroom, $eta_Q$, oracle-evaluated actions], [M6], [online / continuous],
            [RQ5/RQ6 only after offline finite-candidate evidence]),
          )
        ],
      )
    ],
    [
      #color-block(title: [Scale-readiness gate], spacing: 0.42em)[
        #slide-small[
          #prune_todo(
            [Operational edit list moved out of thesis truth; keep only milestone gates here and track concrete work in backlog/source docs.],
            sources: [autoresearch report],
          )
          #v(0.2em)
          Current gate focus: invalidity consistency, production preflight JSON, scene-level split manifest, sampler validity reports, Zarr file budget, and H=1 label profile before H>1 traces.
        ]
      ]
    ],
  )
]

#slide(title: [Advisor Locks / Open Decisions])[
  #grid(
    columns: (1fr, 1fr),
    gutter: 0.5cm,
    [
      #color-block(title: [Decisions to lock], spacing: 0.45em)[
        #slide-small[
          #decision_todo(
            [Does RQ1 lock objective, fixed-budget evaluation, root-normalized training return, and offline fitted $Q_H$ as first method?],
            sources: [questions; roadmap],
          )
          #v(0.18em)
          #decision_todo(
            [Which RQ3 ablations are mandatory before $Q_H$: semidense+DINO, target crop, $bb(S)^2$ memory, candidate-query pooling?],
            sources: [RQ3; shared features],
          )
          #v(0.18em)
          #decision_todo(
            [Does RQ4 cover invalidity, candidate diversity, support scale, and the external-data caveat clearly enough?],
            sources: [RQ4 support contract],
          )
        ]
      ]
    ],
    [
      #color-block(title: [Evidence protocol to lock], spacing: 0.45em)[
        #slide-small[
          #necessary_todo(
            [Scene-level split, acceptable scale fallback, and coverage tuple.],
            gate: [M4/M5],
            sources: [roadmap],
          )
          #v(0.18em)
          #decision_todo([Target matching thresholds and ambiguity policy.], sources: [advisor review])
          #v(0.18em)
          #decision_todo(
            [RQ5/RQ6 extension wording and optional $Q_H$-as-critic bridge.],
            sources: [RQ owner; literature bridge pages],
          )
        ]
      ]
      #good-note[
        #text(size: 11.8pt)[Meeting goal: align scope, RQs, and next gates before more rollout data is generated.]
      ]
    ],
  )
]

#slide(title: [Backup: Failure Interpretation / Validated Subsets])[
  #grid(
    columns: (1fr, 1fr),
    gutter: 0.5cm,
    [
      #color-block(title: [Failure is still a result], spacing: 0.35em)[
        #slide-small[
          - If oracle geometry or target labels fail, report validation limits and one-step evidence only.
          - If target matching is sparse or ambiguous, report validated subsets, unmatched counts, and acceptance filters.
          - If lookahead headroom is near zero, report a negative planning result for that split, target set, horizon, branch factor, and candidate distribution.
          - Added model complexity is justified only after target matching, candidate support, and supervision scale are ruled out.
        ]
      ]
    ],
    [
      #color-block(title: [Advisor-facing evidence surfaces], spacing: 0.35em)[
        #slide-small[
          - Rollout support: target/candidate strata, valid counts, invalid reasons, successor-table availability, selected-chain diversity.
          - Scorer evidence: rank correlation, top-$k$ oracle hit, calibration, oracle-rescored selected candidates.
          - Replay integrity: seed metadata, mask isolation, shuffled-candidate and duplicate-row robustness.
          - Scale: scene-level splits, paired policy comparison, bootstrap CI, per-scene wins, Zarr asset references.
        ]
      ]
    ],
  )
]

#slide(title: [Backup: Diagnostic Rollout / RL Scaffold])[
  #grid(
    columns: (0.86fr, 1.14fr),
    gutter: 0.42cm,
    [
      #color-block(title: [What the historical outlook contributed], spacing: 0.34em)[
        #slide-small[
          - Rollout code reuses the same candidate-shell contract as one-step NBV.
          - Oracle scorer and plotting surfaces expose incremental/cumulative RRI, horizon, branching, pruning, guards, selected frusta, and trajectory replay.
          - #link(gymnasium_url)[Gymnasium] and #link(sb3_url)[SB3] are diagnostic tools for the discrete shell, not thesis-grade online evidence by themselves.
          - Relevant code surfaces: #gh("aria_nbv/aria_nbv/rollouts/replay/engine.py"), #gh("aria_nbv/aria_nbv/pose_generation/plotting.py"), #gh("aria_nbv/aria_nbv/rl/counterfactual_env.py"), #gh("aria_nbv/aria_nbv/app/panels/rl.py").
        ]
      ]
    ],
    [
      #figure(
        image(fig_path + "app/multi-step/T5K5.png", width: 100%),
        caption: [_Diagnostic only_: multi-step counterfactual rollout tree from the implemented app plotting surface.],
      )
      #v(0.1cm)
      #figure(
        image(fig_path + "app/multi-step/T3-greedy-rl-t3shell.png", width: 100%),
        caption: [_Diagnostic only_: step-level shell / frusta view from the same figure family.],
      )
    ],
  )
]

#slide(title: [Backup: Architecture Ladder])[
  #figure(
    kind: "table",
    supplement: [Table],
    caption: [Hypothesis, controls, and ablations from the advisor distillation source. Escalate only after support and scorer gates pass.],
    text(size: 8.45pt)[
      #presentation-table(
        columns: (0.58fr, 1.76fr),
        align: (left, left),
        text-size: 8.45pt,
        header: ([Role], [Candidate design]),
        rows: ([A0 control],
        [independent candidate scorer], [A1 control],
        [pooled DeepSets context over valid candidate rows], [A2 hypothesis],
        [masked Set Transformer candidate interaction], [A3 ablation],
        [QCNet-style query-centric relative pose encoding], [A4 ablation],
        [Fisher/SCONE-style support-overlap attention bias], [A5 value head],
        [uncentred residual $Q_H$ with hard masks and matched-budget oracle re-scoring], [Deferred bridges],
        [privileged-teacher distillation, distributional $Q_H$, EGNN candidate graph, Hestia-style target-then-pose]),
      )
    ],
  )
  #v(0.12em)
  #optional_todo(
    [Treat A3+ as attribution ablations, not prerequisites, unless A0-A2 cannot explain observed headroom/recovery.],
    sources: [`main.typ`; archived advisor handout; literature adoption ledger],
  )
]

#slide(title: [Backup: Hestia / VINv4 Bridge])[
  #grid(
    columns: (1fr, 1fr),
    gutter: 0.48cm,
    [
      #color-block(title: [Transfer from #link(hestia_url)[Hestia]], spacing: 0.34em)[
        #slide-small[
          - Adopt directional observability: encode viewing direction, not only seen/unseen state.
          - Adopt local target-then-pose factorization as a possible RQ6 bridge.
          - Supervise target/attention separately if a target head is introduced.
          - Reject coverage reward and monolithic continuous PPO as thesis-core framing.
        ]
      ]
    ],
    [
      #color-block(title: [VINv4-style bridge, if needed], spacing: 0.34em)[
        #slide-small[
          - Predict an intermediate target/look-at latent before pose realization.
          - Supervise it from expected target-RRI gain, uncertainty, or entity deficit.
          - Read local EVL/geometry at the target instead of only scoring fixed shell poses.
          - Route targets through OBBs or SceneScript entities for entity-aware RRI, while keeping the finite-candidate baseline as the control.
        ]
        #v(0.12em)
        #text(size: 10.2pt)[
          $
            #eqs.rl.target_pose_factorization
          $
        ]
      ]
    ],
  )
]

#slide(title: [Backup: Simulator Contingency])[
  #grid(
    columns: (1fr, 1fr),
    gutter: 0.48cm,
    [
      #color-block(title: [Candidate substrates], spacing: 0.34em)[
        #slide-small[
          - ASE simulator / generation stack: best fit if accessible.
          - #link(habitat_sim_url)[Habitat-Sim]: fast geometry-first sidecar.
          - #link(ai2thor_url)[AI2-THOR] / #link(procthor_url)[ProcTHOR]: useful mainly for semantic-global planning.
          - #link(isaac_sim_url)[Isaac Sim]: broad public multimodal fallback.
        ]
      ]
    ],
    [
      #color-block(title: [Contingency rule], spacing: 0.34em)[
        #slide-small[
          This is a data-contract decision, not just a renderer choice. Do not switch ecosystems before the geometry-first baseline is proven.

          #v(0.18em)
          Any external substrate must preserve comparable Aria optics or calibration, RGB/SLAM or semidense streams, GT geometry, OBB/semantic target labels, and a plausible EVL/semidense replacement for actor-visible state.
        ]
      ]
    ],
  )
]

#slide(title: [Backup: Outlook Open Questions Retained])[
  #grid(
    columns: (1fr, 1fr),
    gutter: 0.48cm,
    [
      #color-block(title: [Scientific open questions], spacing: 0.34em)[
        #slide-small[
          - How much logged history should the actor observe, and what is critic-only?
          - Can a privileged critic use GT mesh, OBB, or segmentation cues without weakening the V1 actor-visible claim?
          - How do we scale beyond mesh-backed scenes while preserving target-specific RRI supervision?
          - When, if ever, do RGB, semantics, or 3DGS enter the thesis core rather than a bridge study?
        ]
      ]
    ],
    [
      #color-block(title: [Operational open questions], spacing: 0.34em)[
        #slide-small[
          - Which anchor poses and candidate bounds define the real training distribution?
          - When do we broaden beyond the current candidate budget, e.g. more than 60 visible/evaluated candidates?
          - How much VIN-v4 work is justified once the finite-candidate baseline exists?
          - What is the minimum convincing experiment set for advisor sign-off?
        ]
      ]
    ],
  )
]

#slide(title: [Backup: Literature Adopt / Reject Boundaries])[
  #figure(
    kind: "table",
    supplement: [Table],
    caption: [Literature families used as anchors without promoting them beyond the current ARIA-NBV evidence gate.],
    text(size: 8.55pt)[
      #presentation-table(
        columns: (0.82fr, 1.28fr, 1.42fr),
        align: (left, left, left),
        text-size: 8.55pt,
        header: ([Family], [Adopt], [Reject / gate]),
        rows: ([VIN-NBV @VIN-NBV-frahm2025], [quality-driven RRI ranking and ordinal scorer precedent],
        [unqualified transfer of object-centric results],
        [Project Aria / ASE @projectaria-engel2023 @ProjectAria-ASE-2025],
        [egocentric streams, poses, meshes, and supervised oracle labels],

        [GT mesh/box leakage into actor-visible policy],
        [EFM3D / EVL @EFM3D-straub2024 @EVL-Doc-2025],
        [actor-visible local evidence, OBB support, DINO/voxel features],

        [treating EVL output as GT or full-scene memory],
        [Double DQN / IQL @DoubleDQN-vanHasselt2015 @IQL-kostrikov2021],
        [masked selector/evaluator backup and offline support caution],

        [using offline RL to skip finite-candidate support checks],
        [GenNBV / Hestia / SceneScript @GenNBV-chen2024 @Hestia-lu2026 @SceneScript-avetisyan2024],
        [continuous, hierarchical, or semantic/global bridge ideas],

        [thesis-core replacement before offline $Q_H$ evidence]),
      )
    ],
  )
]

#slide(title: [References])[
  #text(size: 7pt)[
    #set par(leading: 0.54em)
    #bibliography("/references.bib", style: "/ieee.csl")
  ]
]
