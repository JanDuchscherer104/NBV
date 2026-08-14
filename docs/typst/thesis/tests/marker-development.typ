#import "../draft_markers.typ": development_only, promotion_entry, thesis_status

#development_only[
  [Development-only roadmap content.]
  #promotion_entry(
    [Candidate pointer],
    source: [roadmap.typ:1],
    target-section: [04-method],
    gate: [pilot evidence],
    disposition: "candidate",
  )
  #promotion_entry(
    [Blocked pointer],
    source: [blocked.typ:2],
    target-section: [05-experiments],
    gate: [dataset access],
    disposition: "blocked",
  )
  #promotion_entry(
    [Deferred pointer],
    source: [deferred.typ:3],
    target-section: [06-conclusion],
    gate: [scope review],
    disposition: "deferred",
  )
  #promotion_entry(
    [Rejected pointer],
    source: [rejected.typ:4],
    target-section: [06-conclusion],
    gate: [advisor decision],
    disposition: "rejected",
  )
]

#thesis_status(
  implementation: "planned",
  evidence: "pending",
)[Development status remains descriptive.]
