#import "../draft_markers.typ": development_only, promotion_entry, thesis_status

#development_only[
  #metadata("development-should-be-absent") <marker-development>
  [This must not appear in submission output.]
]

#promotion_entry(
  [#metadata("promotion-candidate-should-be-absent") <marker-promotion-candidate> Submission queue entry is omitted.],
  source: [roadmap.typ:1],
  target-section: [04-method],
  gate: [pilot evidence],
  disposition: "candidate",
)
#promotion_entry(
  [#metadata("promotion-blocked-should-be-absent") <marker-promotion-blocked> Blocked queue entry is omitted.],
  source: [roadmap.typ:2],
  target-section: [04-method],
  gate: [pilot evidence],
  disposition: "blocked",
)
#promotion_entry(
  [#metadata("promotion-deferred-should-be-absent") <marker-promotion-deferred> Deferred queue entry is omitted.],
  source: [roadmap.typ:3],
  target-section: [04-method],
  gate: [pilot evidence],
  disposition: "deferred",
)
#promotion_entry(
  [#metadata("promotion-rejected-should-be-absent") <marker-promotion-rejected> Rejected queue entry is omitted.],
  source: [roadmap.typ:4],
  target-section: [04-method],
  gate: [pilot evidence],
  disposition: "rejected",
)

#thesis_status(
  implementation: "planned",
  evidence: "pending",
)[Descriptive status remains valid in submission mode.]
