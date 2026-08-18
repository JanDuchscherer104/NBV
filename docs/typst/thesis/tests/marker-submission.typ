#import "../draft_markers.typ": development_only, submission_only, promotion_entry

#development_only(() => [
  #metadata("development-should-be-absent") <marker-development>
  #panic("development-only body evaluated in submission mode")
])

#submission_only(() => [
  #metadata("submission-present") <marker-submission>
  [Submission-only content.]
])

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

// Invalid promotion fields are guarded by the development-only thunk and must
// therefore neither validate nor render in submission mode.
#promotion_entry(
  [#metadata("invalid-promotion-should-be-absent") <marker-promotion-invalid> Invalid queue entry is omitted.],
  disposition: "not-a-live-disposition",
)
