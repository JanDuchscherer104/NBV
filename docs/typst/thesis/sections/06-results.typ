= Results <sec:thesis-results>

#import "../experiment_data.typ": thesis-report-settings, load-thesis-report, report-store-fact, report-store-facts-match-contract, short-store-label, format-report-value
#import "../draft_markers.typ": validation_todo
#import "../../shared/tables.typ": publication-table, index-cell

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
#let stores-have-facts(keys, denominators: false) = thesis_data.tables.stores.rows.len() > 0 and thesis_data.tables.stores.rows.all(store => keys.all(key => {
  let matches = thesis_data.tables.facts.rows.filter(row => row.store_id == store.store_id and row.key == key)
  matches.len() == 1 and matches.first().value != none and (not denominators or (matches.first().n != none and matches.first().n > 0))
}))
#let fact-value(store-id, key, digits: none, with-unit: false) = {
  let row = report-store-fact(thesis_data, store-id, key)
  format-report-value(row.value, digits: digits, unit: if with-unit { row.unit } else { none })
}
#let result-status(predicate) = if predicate [available] else [not available]

#let population-facts = ("study.population.scenes", "study.population.targets", "study.population.exclusions")
#let candidate-support-facts = (
  "candidate-support.actor-valid-fraction",
  "candidate-support.valid-support-p05",
  "candidate-support.configured-family-zero-rate",
  "candidate-support.target-side-balance",
  "candidate-support.circular-orbit-span",
)
#let candidate-support-contract = (
  (key: "candidate-support.actor-valid-fraction", aggregation: "state_then_scene_macro"),
  (key: "candidate-support.valid-support-p05", aggregation: "state_then_scene_p05"),
  (key: "candidate-support.configured-family-zero-rate", aggregation: "state_then_scene_macro"),
  (key: "candidate-support.target-side-balance", aggregation: "state_then_scene_macro"),
  (key: "candidate-support.circular-orbit-span", aggregation: "state_then_scene_macro"),
)
#let paired-effect-facts = ("policy.paired_scene_endpoint.effect", "policy.paired_scene_endpoint.ci_low", "policy.paired_scene_endpoint.ci_high", "policy.paired_scene_endpoint.n_scenes", "headroom_gate.passed")
#let paired-effect-contract = (
  (key: "policy.paired_scene_endpoint.effect", aggregation: "paired_scene_mean_difference"),
  (key: "policy.paired_scene_endpoint.ci_low", aggregation: "paired_scene_mean_difference"),
  (key: "policy.paired_scene_endpoint.ci_high", aggregation: "paired_scene_mean_difference"),
  (key: "policy.paired_scene_endpoint.n_scenes", aggregation: "count"),
  (key: "headroom_gate.passed", aggregation: "paired_scene_decision"),
)
#let resource-facts = ("runtime.wall_time_s", "runtime.peak_gpu_bytes", "storage.total_bytes")

#let confirmatory-evidence = thesis_evidence_status == "confirmatory" and all-stores-valid
#let population-available = confirmatory-evidence and stores-have-facts(population-facts, denominators: true)
#let candidate-support-available = confirmatory-evidence and population-available and stores-have-facts(candidate-support-facts, denominators: true) and thesis_data.tables.stores.rows.all(store => {
  let scene-count = report-store-fact(thesis_data, store.store_id, "study.population.scenes").value
  scene-count != none and scene-count > 0 and report-store-facts-match-contract(
    thesis_data,
    store.store_id,
    candidate-support-contract,
    scene-count,
  )
})
#let paired-effect-available = confirmatory-evidence and stores-have-facts(paired-effect-facts) and thesis_data.tables.stores.rows.all(store => {
  let paired-scenes = report-store-fact(thesis_data, store.store_id, "policy.paired_scene_endpoint.n_scenes").value
  paired-scenes != none and paired-scenes > 0 and report-store-facts-match-contract(
    thesis_data,
    store.store_id,
    paired-effect-contract,
    paired-scenes,
  )
})
#let resource-available = confirmatory-evidence and stores-have-facts(resource-facts)

#let result-summary-families = {
  let families = ()
  if population-available {
    families.push((label: [Population], metrics: (
      (label: [Scenes], key: "study.population.scenes"),
      (label: [Targets], key: "study.population.targets"),
      (label: [Exclusions], key: "study.population.exclusions"),
    )))
  }
  if candidate-support-available {
    families.push((label: [Candidate support], metrics: (
      (label: [Actor-valid fraction], key: "candidate-support.actor-valid-fraction", digits: 3),
      (label: [P05 valid support], key: "candidate-support.valid-support-p05", digits: 1),
      (label: [Configured-family zero rate], key: "candidate-support.configured-family-zero-rate", digits: 3),
      (label: [Target-side balance], key: "candidate-support.target-side-balance", digits: 3),
      (label: [Circular orbit span], key: "candidate-support.circular-orbit-span", digits: 2),
    )))
  }
  if paired-effect-available {
    families.push((label: [Policy comparison], metrics: (
      (
        label: [Paired endpoint effect],
        key: "policy.paired_scene_endpoint.effect",
        low-key: "policy.paired_scene_endpoint.ci_low",
        high-key: "policy.paired_scene_endpoint.ci_high",
        denominator-key: "policy.paired_scene_endpoint.n_scenes",
        digits: 3,
      ),
      (
        label: [Headroom gate],
        key: "headroom_gate.passed",
        denominator-key: "policy.paired_scene_endpoint.n_scenes",
      ),
    )))
  }
  if resource-available {
    families.push((label: [Resources], metrics: (
      (label: [Wall time], key: "runtime.wall_time_s", digits: 1),
      (label: [Peak GPU memory], key: "runtime.peak_gpu_bytes"),
      (label: [Storage], key: "storage.total_bytes"),
    )))
  }
  families
}
#let result-summary-rows = {
  let rows = ()
  let profile-span = result-summary-families.fold(0, (total, family) => total + family.metrics.len())
  for store in thesis_data.tables.stores.rows {
    let store-id = store.store_id
    let label = short-store-label(thesis_data, store-id)
    let first-profile-row = true
    for family in result-summary-families {
      let first-family-row = true
      for metric in family.metrics {
        if first-profile-row {
          rows.push(index-cell([#label], rowspan: profile-span))
          first-profile-row = false
        }
        if first-family-row {
          rows.push(index-cell(family.label, rowspan: family.metrics.len()))
          first-family-row = false
        }
        let digits = metric.at("digits", default: none)
        let low-key = metric.at("low-key", default: none)
        let high-key = metric.at("high-key", default: none)
        let denominator-key = metric.at("denominator-key", default: none)
        let fact = report-store-fact(thesis_data, store-id, metric.key)
        rows.push(metric.label)
        rows.push([#format-report-value(fact.value, digits: digits)])
        rows.push(if low-key == none { [—] } else { [#fact-value(store-id, low-key, digits: digits)] })
        rows.push(if high-key == none { [—] } else { [#fact-value(store-id, high-key, digits: digits)] })
        rows.push(if fact.unit == none { [—] } else { [#fact.unit] })
        rows.push(if denominator-key == none {
          [#format-report-value(fact.n)]
        } else {
          [#fact-value(store-id, denominator-key)]
        })
      }
    }
  }
  rows
}

The thesis report bundle is loaded through the strict schema checked in `experiment_data.typ`. Its declared evidence class is #emph(thesis_evidence_status). Schema validity establishes only that provenance, missingness, and table contracts are readable; it does not turn a development fixture or an incomplete pilot into scientific evidence.

#figure(
  publication-table(
    columns: (1.05fr, 1.75fr, 0.7fr),
    header: ([*Result*], [*Required evidence*], [*Status*]),
    rows: (
      index-cell([Population and targets]), [population facts with denominators in every validated store], [#result-status(population-available)],
      index-cell([Candidate-support QC]), [five descriptive diagnostics with the frozen state--scene macro identities and exact scene denominators], [#result-status(candidate-support-available)],
      index-cell([Paired policy effect]), [paired per-scene effect, interval, exact paired-scene count, and headroom decision in every validated store], [#result-status(paired-effect-available)],
      index-cell([Resource feasibility]), [wall time, peak GPU memory, and storage in every validated store], [#result-status(resource-available)],
    ),
  ),
  caption: [Evidence availability in the loaded report bundle. A status of “not available” means that no thesis result is inferred from fixture values, train-only attempts, or an incomplete store.],
) <tab:thesis-result-availability>

#if result-summary-rows.len() > 0 [
  #figure(
    publication-table(
      columns: (0.72fr, 0.95fr, 1.05fr, 0.62fr, 0.62fr, 0.62fr, 0.55fr, 0.5fr),
      align: (left, left, left, right, right, right, left, right),
      text-size: 7.3pt,
      header: (
        [*Profile*], [*Result family*], [*Measure*], [*Estimate*], [*CI low*], [*CI high*], [*Unit*], [*$n$*],
      ),
      rows: result-summary-rows,
    ),
    caption: [Confirmatory values by profile and result family. Estimates, interval bounds, units, and denominators remain separate; Typst groups neutral report rows without aggregating across profiles.],
  ) <tab:thesis-confirmatory-values>
]

== Candidate and Store Feasibility

#if candidate-support-available [
  The confirmatory bundle supplies descriptive candidate-support quality-control diagnostics for every validated store. Actor-valid fraction, lower-tail valid support, configured-family zero rate, target-side balance, and circular orbit span are reported per profile in @tab:thesis-confirmatory-values with the frozen state--scene macro identities and scene denominators. These values audit candidate support; they are not paired policy effects and carry no comparative inference unless a separately preregistered paired scene contrast and interval are present.
] else [
  The available artifacts show that the finite-candidate rollout path reaches mesh rendering, target-specific oracle scoring, and selected-action replay on training sources. They therefore support an implementation-readiness claim only. A CUDA out-of-memory failure in an unbatched candidate render and later memory-bounded attempts identify rendering as a scale gate; neither establishes rollout throughput, storage cost, candidate-family support, or policy quality for the intended study population.
]

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

== Runtime and Storage Gate

#if resource-available [
  Completed validated stores provide wall time, peak GPU memory, and storage for every profile in @tab:thesis-confirmatory-values. These observed values support feasibility assessment for the recorded runs; extrapolation to cluster throughput or a larger dataset still requires an explicit scaling model.
] else [
  The runtime and storage claim requires completed validated stores whose resolved manifests, failure records, and resource summaries refer to the same run. Until that evidence exists for both rollout profiles, the large-scale data-generation gate remains pending. The current attempts justify memory-bounded rendering and retained failure provenance, but no extrapolation to cluster throughput or dataset volume.
]
