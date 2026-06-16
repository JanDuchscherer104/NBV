// Advisor meeting deck for the ARIA-NBV master-thesis phase.
// Style follows docs/typst/seminar_slides/slides_4.typ.

#import "../shared/slide-template.typ": *
#import "@preview/muchpdf:0.1.1": muchpdf
#import "@preview/booktabs:0.0.4": *
#show: booktabs-default-table-style

#import "../shared/macros.typ": *

#let fig_path = "../../figures/"
#let thesis_fig_path = "figures/"

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
#show bibliography: set text(size: 14pt)
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

#title-slide()

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
          Delta_0^e
          =
          d(C_e (cal(P)_0), cal(M)_e^"GT")
          quad
          Delta_H^e
          =
          d(C_e (cal(P)_0 union cal(P)_1 union dots.c union cal(P)_H), cal(M)_e^"GT")
          \
          J_e^((H))(tau)
          =
          (Delta_0^e - Delta_H^e) / (Delta_0^e + epsilon)
        $
      ]
    ],
    [
      #color-block(title: [Gated Research Questions], spacing: 0.32em)[
        #text(size: 8.6pt)[
          #table(
            columns: (0.55fr, 2.08fr),
            align: (left, left),

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
          )
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
              #eqs.features.qh_scene_memory
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
            #eqs.features.candidate_query_pools
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
      #table(
        columns: (0.48fr, 1.25fr, 1.18fr),
        align: (left, left, left),
        toprule(),
        table.header([Block], [Baseline], [Extensions]),
        midrule(),
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
        bottomrule(),
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
            #eqs.features.candidate_pose_features
          $
        ]
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
          #table(
            columns: (0.32fr, 0.98fr, 1.44fr),
            align: (left, left, left),
            toprule(),
            table.header([Gate], [Check], [Purpose]),
            midrule(), [S0], [H=1 label profile],
            [target gain is non-flat and valid rows exist], [S1], [mixed candidate preflight],
            [target-aware support plus exploration], [S2], [H>1 replay traces],
            [successor tables and selected-depth lineage], [S3], [stochastic support],
            [avoid fitting only greedy chains], [S4], [scene-level scale],
            [held-out generalization without split leakage], [M0], [MLP / DeepSets / Set Transformer],
            [model-control ladder for attribution], bottomrule(),
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
          3. Fit residual dueling $Q_H$ on selected-action transitions.
          4. Decode only over hard-valid candidates.
          #v(0.18em)
          #text(
            size: 10.7pt,
            fill: theme_color_footer.darken(35%),
          )[Why this RQ exists: test the actual planning claim after the myopic control and replay support are trusted.]
        ]
      ]
      #text(size: 12.0pt)[
        $
          Q_(H,theta)
          =
          hat(r)_psi^e + V_theta + A_(theta,i)^H - overline(A)_(theta)^H
          ,
          quad
          overline(A)_(theta)^H
          =
          (1)/(abs(cal(A)_t))
          sum_(j in cal(A)_t) A_(theta,j)^H
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
            i^*
            =
            arg max_(i in cal(A)_(t+1))
            Q_theta (s_(t+1)^"cf0", z_e, q_(t+1,i))
            \
            y_t
            =
            r_(t,"root")^e
            +
            gamma(1-d_t)
            Q_(theta^-)(s_(t+1)^"cf0", z_e, q_(t+1,i^*))
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
          - $pi_"rand"$: random valid lower reference.
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
          #table(
            columns: (0.36fr, 1.05fr, 1.3fr),
            align: (left, left, left),
            toprule(),
            table.header([M], [Gate], [Exit]),
            midrule(), [M1], [data, cache, oracle],
            [frame/CW90/RRI contract and throughput], [M2], [one-step baseline],
            [calibration/ranking and scale plan], [M3], [target RRI],
            [V0/V1 target contract and sharding gate], [M4], [target scorer],
            [observed/predicted target-conditioned RRI], [M5], [rollouts and $Q_H$],
            [headroom, $eta_Q$, oracle-evaluated actions], [M6], [online / continuous],
            [RQ5/RQ6 only after offline finite-candidate evidence], bottomrule(),
          )
        ],
      )
    ],
    [
      #color-block(title: [Immediate next edits before scale], spacing: 0.42em)[
        #slide-small[
          - Fix all-hard-diagnostic invalidity consistency.
          - Add production preflight JSON and stale-schema checks.
          - Require scene-level split manifest before shard grouping.
          - Retune three-family sampler after per-family validity reports.
          - Reduce Zarr chunk/file bloat.
          - Validate H=1 target-label profile, then H>1 rollout traces.
        ]
      ]
    ],
  )
]

#slide(title: [What I Need Feedback On: RQ Locks])[
  #grid(
    columns: (1fr, 1fr),
    gutter: 0.5cm,
    [
      #color-block(title: [Decisions to lock], spacing: 0.45em)[
        #slide-small[
          1. Does RQ1 lock objective, fixed-budget evaluation, root-normalized training return, and offline fitted $Q_H$ as first method?
          2. What pass/fail bar defines positive offline $Q_H$ recovery?
          3. Which RQ3 ablations are mandatory before $Q_H$: semidense+DINO, target crop, $bb(S)^2$ memory, candidate-query pooling?
          4. Does RQ4 cover invalidity, candidate diversity, support scale, and the external-data caveat clearly enough?
        ]
      ]
    ],
    [
      #color-block(title: [Evidence protocol to lock], spacing: 0.45em)[
        #slide-small[
          - Scene-level split and acceptable scale fallback.
          - Target matching thresholds and ambiguity policy.
          - Invalidity as hard masks/reasons.
          - LRZ/Zarr preflight before broad generation.
          - RQ5/RQ6 extension wording and optional $Q_H$-as-critic bridge.
        ]
      ]
      #good-note[
        #text(size: 11.8pt)[Meeting goal: align scope, RQs, and next gates before more rollout data is generated.]
      ]
    ],
  )
]
