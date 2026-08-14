#import "../draft_markers.typ": development_only, promotion_entry, thesis_status

// This is a development-only evidence view.  Python modules, focused tests,
// configuration, and immutable artifacts remain the owners of implementation
// contracts and measurements.
#development_only[
  #heading(level: 1, numbering: none)[M1 Contract Report] <m1-contract-report>

  #heading(level: 2, numbering: none)[Status] <m1-status>

  #thesis_status(
    implementation: "partial",
    evidence: "pending",
    source: [
      thesis M1 gate notes and executable package owners (not a second
      contract owner)
    ],
    gate: [fresh store, scene-split, Rerun, and throughput evidence],
  )[
    Synthetic contract guards are available, but the configured local store
    and scale evidence do not yet close the M1 exit gate.
  ]

  #table(
    columns: (1.1fr, 0.8fr, 2.3fr),
    stroke: 0.35pt + luma(70%),
    inset: 5pt,
    table.header([*Area*], [*Status*], [*Owner and evidence pointer*]),
    [Source-contract guards], [validated], [
      Focused tests under `aria_nbv/tests/data_handling/`,
      `aria_nbv/tests/pose_generation/`, and `aria_nbv/tests/rollouts/` own
      the executable checks; this view records only their M1 status.
    ],
    [Configured local store], [blocked], [
      `.configs/offline_only.toml` and the resolved
      `.data/offline_cache/vin_offline` artifact are the smoke-evidence owners.
    ],
    [Scene-level split evidence], [blocked], [
      The store artifact and its split metadata require a scene-level
      train/validation proof before promotion.
    ],
    [Rerun diagnostics], [blocked], [
      No M1 Rerun recordings are present in this worktree. The recording gate
      remains open; absence is reported explicitly rather than linked to a
      nonexistent artifact.
    ],
    [Oracle throughput], [blocked], [
      Representative mesh, rendering, backprojection, and RRI timing remains
      to be captured in the experiment evidence owner.
    ],
  )

  #heading(level: 2, numbering: none)[Evidence] <m1-evidence>

  The current evidence view is intentionally pointer-only.  The defining
  Python modules, tests, active configuration, and generated artifacts remain
  authoritative; no schema, tensor shape, formula, serialized value, or
  command ledger is reproduced here.

  - Synthetic guard results: `aria_nbv/tests/data_handling/`,
    `aria_nbv/tests/pose_generation/`, and `aria_nbv/tests/rollouts/`.
  - Local smoke configuration and artifact root: `.configs/offline_only.toml`
    and `.data/offline_cache/vin_offline/`.
  - Rerun evidence: absent in the current worktree; the normal/boundary/failure
    recording gate remains open.

  #heading(level: 2, numbering: none)[Blockers] <m1-blockers>

  #promotion_entry(
    [Refresh the configured-store evidence and report coverage status.],
    source: [M1 gate notes and executable package owners],
    target-section: [M1 status and evidence],
    gate: [fresh immutable-store inspection],
    disposition: "blocked",
  )
  #promotion_entry(
    [Replace the one-scene diagnostic split with scene-level evidence or record
    the exact residual blocker.],
    source: [`.data/offline_cache/vin_offline/`],
    target-section: [M1 evidence],
    gate: [scene-level split proof],
    disposition: "blocked",
  )
  #promotion_entry(
    [Collect normal, boundary, and failure Rerun recordings.],
    source: [`.artifacts/rerun/`],
    target-section: [M1 evidence],
    gate: [three diagnostic recordings],
    disposition: "blocked",
  )
  #promotion_entry(
    [Measure representative oracle throughput and preserve the measurement
    artifact for review.],
    source: [`aria_nbv/` and active experiment configuration],
    target-section: [M1 evidence],
    gate: [representative timing receipt],
    disposition: "blocked",
  )
]
