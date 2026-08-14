#import "../experiment_data.typ": thesis-report-settings, load-thesis-report, short-store-label, digest-prefix, format-report-value
#import "../draft_markers.typ": development_only
#import "@preview/booktabs:0.0.4": *

#let report-settings = thesis-report-settings()
#let thesis_evidence_status = report-settings.evidence-status
#let thesis_data = load-thesis-report(
  report-settings.path,
  evidence-status: thesis_evidence_status,
  required-role: report-settings.required-role,
)
#let bundle-role = thesis_data.bundle_role
#let bundle-label = if bundle-role == "fixture" {
  "Development fixture"
} else if thesis_evidence_status == "confirmatory" {
  "Confirmatory evidence"
} else {
  "Pilot evidence"
}
#let critical-parameter-specs = (
  (key: "writer_config.max_samples", label: "Source cap"),
  (key: "writer_config.max_targets_per_sample", label: "Global target cap"),
  (key: "writer_config.oracle_target_task_sampler.max_targets_per_sample", label: "Targets / source"),
  (key: "writer_config.oracle_target_task_sampler.policy", label: "Target sampler"),
  (key: "writer_config.candidate_mixture.base.num_samples", label: "Candidates / action"),
  (key: "writer_config.candidate_mixture.base.enforce_motion_realism", label: "Motion realism"),
  (key: "writer_config.target_scorer.depth.renderer.max_views_per_batch", label: "Render batch"),
  (key: "writer_config.target_scorer.depth.resolution_scale", label: "Depth scale"),
  (key: "writer_config.recipes[2].policy.horizon", label: "Lookahead horizon"),
  (key: "writer_config.recipes[2].policy.branch_factor", label: "Lookahead branch"),
)

#let selected-parameter-rows = {
  let selected = ()
  for store in thesis_data.tables.stores.rows {
    for spec in critical-parameter-specs {
      let matches = thesis_data.tables.parameters.rows.filter(row => row.store_id == store.store_id and row.key == spec.key)
      assert(matches.len() <= 1, message: "duplicate thesis-critical parameter for one store")
      if matches.len() == 1 {
        selected.push((store: short-store-label(thesis_data, store.store_id), label: spec.label, row: matches.first()))
      }
    }
  }
  selected
}

#let parameter-value(row) = if row.is_missing {
  [---]
} else if row.value_type == "bool" {
  if row.value_bool { [true] } else { [false] }
} else if row.value_type == "int" {
  str(row.value_int)
} else if row.value_type == "float" {
  format-report-value(row.value_float)
} else {
  row.value_text
}

= Reproducibility Record <sec:thesis-reproducibility>

The report bundle is the single numerical interface between validated rollout artifacts and this manuscript. Its schema version, evidence status, store manifests, typed parameter rows, failure records, and sidecar hashes preserve provenance without duplicating analysis logic in Typst. The document loader rejects schema or status mismatches before any table is rendered. Compact labels and digest prefixes are used below; complete store identifiers, paths, and hashes remain in the machine-readable bundle.

#figure(
  table(
    columns: (1.1fr, 1fr, 1.1fr, 0.7fr),
    toprule(),
    table.header([*Evidence class*], [*Store*], [*Manifest digest*], [*Validated*]),
    midrule(),
    ..thesis_data.tables.stores.rows.map(store => (
      [#bundle-label],
      [#short-store-label(thesis_data, store.store_id)],
      [#digest-prefix(store.manifest_sha256)],
      [#if store.validation_ok { [yes] } else { [no] }],
    )).flatten(),
    bottomrule(),
  ),
  caption: if bundle-role == "fixture" {
    [Loaded development-fixture provenance. The fixture verifies the document interface only and is not scientific evidence.]
  } else {
    [Loaded evidence-bundle provenance. Every row is attributed to a validated rollout-store manifest.]
  },
) <tab:thesis-report-provenance>

#if bundle-role == "evidence" and thesis_evidence_status == "confirmatory" [
  The resolved configuration parameters below are read from the same confirmatory bundle as the reported results. The projection is an explicit ten-key contract covering source and target caps, target sampling, candidate count, motion realism, render batching, depth scale, and lookahead depth and branching. Other flattened manifest values remain available in the bundle. Missing selected values remain explicit rather than being replaced by document defaults.

  #figure(
    table(
      columns: (0.9fr, 1.8fr, 1fr),
      toprule(),
      table.header([*Profile*], [*Resolved parameter*], [*Value*]),
      midrule(),
      ..selected-parameter-rows.map(entry => (
        [#entry.store],
        [#entry.label],
        [#parameter-value(entry.row)],
      )).flatten(),
      bottomrule(),
    ),
    caption: [Thesis-critical resolved parameters. Short profile labels map one-to-one to the provenance rows above; full keys and store identifiers remain in the report bundle.],
  ) <tab:thesis-resolved-parameters>
] else if bundle-role == "fixture" [
  The bundled development fixture contains synthetic values solely to test typed loading and missingness. Its numerical rows are deliberately not rendered or interpreted.
] else [
  This pilot evidence bundle preserves provenance but is not confirmatory. Its numerical parameter rows are not rendered or interpreted as thesis results.
]

#development_only[
  #include "../sections/06-draft-open-work.typ"
]
