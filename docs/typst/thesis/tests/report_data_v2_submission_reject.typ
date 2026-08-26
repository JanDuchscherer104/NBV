#import "../experiment_data.typ": load-scientific-report

// This fixture is intentionally pilot and sampled. Compilation must fail when
// the publication gate is requested.
#let _report = load-scientific-report(
  "/typst/thesis/data/report-bundle-v2-fixture.json",
  evidence-status: "pilot",
  require-publication: true,
)
