#import "../draft_markers.typ": development_only, promotion_entry, thesis_status

#development_only[
  #metadata("development-present") <marker-development>
  [Development-only roadmap content.]
  #promotion_entry(
    [#metadata("promotion-candidate-present") <marker-promotion-candidate> Candidate pointer],
    source: [roadmap.typ:1],
    target-section: [04-method],
    gate: [pilot evidence],
    disposition: "candidate",
  )
  #promotion_entry(
    [#metadata("promotion-blocked-present") <marker-promotion-blocked> Blocked pointer],
    source: [blocked.typ:2],
    target-section: [05-experiments],
    gate: [dataset access],
    disposition: "blocked",
  )
  #promotion_entry(
    [#metadata("promotion-deferred-present") <marker-promotion-deferred> Deferred pointer],
    source: [deferred.typ:3],
    target-section: [06-conclusion],
    gate: [scope review],
    disposition: "deferred",
  )
  #promotion_entry(
    [#metadata("promotion-rejected-present") <marker-promotion-rejected> Rejected pointer],
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
