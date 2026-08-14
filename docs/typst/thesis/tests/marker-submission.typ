#import "../draft_markers.typ": development_only, promotion_entry, thesis_status

#development_only[
  [This must not appear in submission output.]
]

#promotion_entry(
  [Submission queue entry is omitted.],
  source: [roadmap.typ:1],
  target-section: [04-method],
  gate: [pilot evidence],
  disposition: "candidate",
)
#promotion_entry(
  [Blocked queue entry is omitted.],
  source: [roadmap.typ:2],
  target-section: [04-method],
  gate: [pilot evidence],
  disposition: "blocked",
)
#promotion_entry(
  [Deferred queue entry is omitted.],
  source: [roadmap.typ:3],
  target-section: [04-method],
  gate: [pilot evidence],
  disposition: "deferred",
)
#promotion_entry(
  [Rejected queue entry is omitted.],
  source: [roadmap.typ:4],
  target-section: [04-method],
  gate: [pilot evidence],
  disposition: "rejected",
)

#thesis_status(
  implementation: "planned",
  evidence: "pending",
)[Descriptive status remains valid in submission mode.]
