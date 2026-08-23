= Results <sec:thesis-results>

#import "../experiment_data.typ": thesis-report-settings, load-thesis-report, short-store-label, format-report-value
#import "../draft_markers.typ": validation_todo

#validation_todo(
  [Replace fixture- and readiness-oriented output with confirmatory results that answer each research question using matched endpoint evaluation, denominators, exclusions, aggregation units, independent-run uncertainty, and immutable artifact provenance.],
  source: [confirmatory report bundle and analysis manifest],
  gate: [submission evidence bundle passes all report assertions and every stated result resolves to raw and derived artifacts],
)

#let report-settings = thesis-report-settings()
#let thesis_evidence_status = report-settings.evidence-status
#let thesis_data = load-thesis-report(
  report-settings.path,
  evidence-status: thesis_evidence_status,
  required-role: report-settings.required-role,
)
#let all-stores-valid = thesis_data.tables.stores.rows.len() > 0 and thesis_data.tables.stores.rows.all(store => store.validation_ok == true)
#let store-fact(store-id, key) = {
  let matches = thesis_data.tables.facts.rows.filter(row => row.store_id == store-id and row.key == key)
  assert(matches.len() == 1, message: "expected one thesis result fact per store and key")
  matches.first()
}
#let stores-have-facts(keys, denominators: false) = thesis_data.tables.stores.rows.len() > 0 and thesis_data.tables.stores.rows.all(store => keys.all(key => {
  let matches = thesis_data.tables.facts.rows.filter(row => row.store_id == store.store_id and row.key == key)
  matches.len() == 1 and matches.first().value != none and (not denominators or (matches.first().n != none and matches.first().n > 0))
}))
#let fact-value(store-id, key, digits: none, with-unit: false) = {
  let row = store-fact(store-id, key)
  format-report-value(row.value, digits: digits, unit: if with-unit { row.unit } else { none })
}
#let result-status(predicate) = if predicate [available] else [not available]

#let population-facts = ("study.population.scenes", "study.population.targets", "study.population.exclusions")
#let candidate-support-facts = ("candidate_validity.total", "candidate_validity.valid", "candidate_support.no_valid_action_failures")
#let paired-effect-facts = ("policy.paired_scene_endpoint.effect", "policy.paired_scene_endpoint.ci_low", "policy.paired_scene_endpoint.ci_high", "policy.paired_scene_endpoint.n_scenes", "headroom_gate.passed")
#let resource-facts = ("runtime.wall_time_s", "runtime.peak_gpu_bytes", "storage.total_bytes")

#let confirmatory-evidence = thesis_evidence_status == "confirmatory" and all-stores-valid
#let population-available = confirmatory-evidence and stores-have-facts(population-facts, denominators: true)
#let candidate-support-available = confirmatory-evidence and stores-have-facts(candidate-support-facts)
#let paired-effect-available = confirmatory-evidence and stores-have-facts(paired-effect-facts)
#let resource-available = confirmatory-evidence and stores-have-facts(resource-facts)

#let result-summary-rows = {
  let rows = ()
  for store in thesis_data.tables.stores.rows {
    let store-id = store.store_id
    let label = short-store-label(thesis_data, store-id)
    if population-available {
      rows.push(([Population], [#label], [scenes #fact-value(store-id, "study.population.scenes"); targets #fact-value(store-id, "study.population.targets"); exclusions #fact-value(store-id, "study.population.exclusions")]))
    }
    if candidate-support-available {
      rows.push(([Candidate support], [#label], [#fact-value(store-id, "candidate_validity.valid") / #fact-value(store-id, "candidate_validity.total") valid; zero-action failures #fact-value(store-id, "candidate_support.no_valid_action_failures")]))
    }
    if paired-effect-available {
      rows.push(([Paired effect], [#label], [#fact-value(store-id, "policy.paired_scene_endpoint.effect", digits: 3) [#fact-value(store-id, "policy.paired_scene_endpoint.ci_low", digits: 3), #fact-value(store-id, "policy.paired_scene_endpoint.ci_high", digits: 3)]; $n$=#fact-value(store-id, "policy.paired_scene_endpoint.n_scenes"); headroom #fact-value(store-id, "headroom_gate.passed")]))
    }
    if resource-available {
      rows.push(([Resources], [#label], [wall #fact-value(store-id, "runtime.wall_time_s", digits: 1, with-unit: true); peak GPU #fact-value(store-id, "runtime.peak_gpu_bytes", with-unit: true); storage #fact-value(store-id, "storage.total_bytes", with-unit: true)]))
    }
  }
  rows
}

The thesis report bundle is loaded through the strict schema checked in `experiment_data.typ`. Its declared evidence class is #emph(thesis_evidence_status). Schema validity establishes only that provenance, missingness, and table contracts are readable; it does not turn a development fixture or an incomplete pilot into scientific evidence.

#figure(
  table(
    columns: (1.05fr, 1.75fr, 0.7fr),
    inset: 5pt,
    table.header([*Result*], [*Required evidence*], [*Status*]),
    [Population and targets], [population facts with denominators in every validated store], [#result-status(population-available)],
    [Candidate support], [valid/total candidates and zero-action failures in every validated store], [#result-status(candidate-support-available)],
    [Paired policy effect], [effect, interval, scene count, and headroom gate in every validated store], [#result-status(paired-effect-available)],
    [Resource feasibility], [wall time, peak GPU memory, and storage in every validated store], [#result-status(resource-available)],
  ),
  caption: [Evidence availability in the loaded report bundle. “Not available” means that no thesis result is inferred from fixture values, train-only attempts, or an incomplete store.],
) <tab:thesis-result-availability>

#if result-summary-rows.len() > 0 [
  #figure(
    table(
      columns: (0.85fr, 0.7fr, 2.35fr),
      inset: 4pt,
      table.header([*Result*], [*Profile*], [*Confirmatory value*]),
      ..result-summary-rows.flatten(),
    ),
    caption: [Compact confirmatory values, reported per validated store/profile. No aggregation across profiles is performed in Typst.],
  ) <tab:thesis-confirmatory-values>
]

== Candidate and Store Feasibility

#if candidate-support-available [
  The confirmatory bundle supplies finite-candidate support for every validated store. Valid and total candidate counts and no-valid-action failures are reported per profile in @tab:thesis-confirmatory-values; the table does not pool profiles or infer support beyond the recorded study population.
] else [
  The available artifacts show that the finite-candidate rollout path reaches mesh rendering, target-specific oracle scoring, and selected-action replay on training sources. They therefore support an implementation-readiness claim only. A CUDA out-of-memory failure in an unbatched candidate render and later memory-bounded attempts identify rendering as a scale gate; neither establishes rollout throughput, storage cost, candidate-family support, or policy quality for the intended study population.
]
// - repo:docs/typst/thesis/sections/06-results.typ:99-99
// evidence:
// claims: pc-c1-auditable-experiment-contract

== Target-Task Coverage

#if population-available [
  The confirmatory bundle records scene, target, and exclusion counts with non-zero denominators for every validated profile. These per-profile population values appear in @tab:thesis-confirmatory-values; eligibility and exclusion semantics remain those fixed in the experimental-design contract.
] else [
  The implemented pipeline samples geometry-valid GT target tasks and records target and validity fields in the rollout schema. The loaded bundle does not contain a validated population and exclusion table for the study. Scene coverage, eligible-target coverage, invalid-reason frequencies, and their denominators are consequently unavailable as results.
]

== Policy Comparison

#if paired-effect-available [
  The primary estimand is the paired per-scene fixed-budget endpoint difference defined in @sec:thesis-experimental-design. The confirmatory effect, interval, scene count, and headroom-gate decision are reported per validated profile in @tab:thesis-confirmatory-values. Their interpretation remains conditional on the matched-policy and held-out-population contracts rather than on schema validity alone.
] else [
  The primary estimand is not estimable from the current evidence because no validated held-out bundle contains the matched policy outcomes and aggregation inputs. Oracle repeatability, oracle-lookahead headroom, learned one-step performance, finite-horizon recovery, uncertainty intervals, and sensitivity analyses are therefore not reported.
]
// - repo:docs/typst/thesis/sections/06-results.typ:119-119
// evidence:
// claims: pc-r0-no-confirmatory-policy-result

== Runtime and Storage Gate

#if resource-available [
  Completed validated stores provide wall time, peak GPU memory, and storage for every profile in @tab:thesis-confirmatory-values. These observed values support feasibility assessment for the recorded runs; extrapolation to cluster throughput or a larger dataset still requires an explicit scaling model.
] else [
  The runtime and storage claim requires completed validated stores whose resolved manifests, failure records, and resource summaries refer to the same run. Until that evidence exists for both rollout profiles, the large-scale data-generation gate remains pending. The current attempts justify memory-bounded rendering and retained failure provenance, but no extrapolation to cluster throughput or dataset volume.
]
