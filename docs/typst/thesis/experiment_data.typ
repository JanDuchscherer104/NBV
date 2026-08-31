#let report-schema-version = "aria-nbv-thesis-report-v1"
#let scientific-report-schema-version = "aria-nbv-report-bundle-v2"

// Typst 0.14 has no native SHA-256 primitive. This small implementation keeps
// the thesis admission boundary aligned with the Python report writer without
// introducing a second package dependency or a weaker synthetic identifier.
#let sha256-constants = (
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
)

#let unsigned-32(value) = calc.rem(value, 0x100000000)
#let rotate-right-32(value, shift) = value.bit-rshift(shift).bit-or(
  unsigned-32(value.bit-lshift(32 - shift)),
)
#let hex-32(value) = {
  let encoded = str(unsigned-32(value), base: 16)
  "0" * (8 - encoded.len()) + encoded
}

#let sha256-hex(input) = {
  let encoded = bytes(input)
  let message = range(encoded.len()).map(index => encoded.at(index))
  let bit-length = message.len() * 8
  message.push(0x80)
  while calc.rem(message.len(), 64) != 56 { message.push(0) }
  for shift in range(8).rev() {
    message.push(bit-length.bit-rshift(shift * 8).bit-and(0xff))
  }

  let hash = (
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  )
  for offset in range(0, message.len(), step: 64) {
    let words = range(16).map(index => {
      let base = offset + index * 4
      unsigned-32(
        message.at(base).bit-lshift(24) +
        message.at(base + 1).bit-lshift(16) +
        message.at(base + 2).bit-lshift(8) +
        message.at(base + 3)
      )
    })
    for index in range(16, 64) {
      let x = words.at(index - 15)
      let y = words.at(index - 2)
      let sigma-zero = rotate-right-32(x, 7).bit-xor(
        rotate-right-32(x, 18),
      ).bit-xor(x.bit-rshift(3))
      let sigma-one = rotate-right-32(y, 17).bit-xor(
        rotate-right-32(y, 19),
      ).bit-xor(y.bit-rshift(10))
      words.push(unsigned-32(
        words.at(index - 16) + sigma-zero + words.at(index - 7) + sigma-one,
      ))
    }

    let a = hash.at(0)
    let b = hash.at(1)
    let c = hash.at(2)
    let d = hash.at(3)
    let e = hash.at(4)
    let f = hash.at(5)
    let g = hash.at(6)
    let h = hash.at(7)
    for index in range(64) {
      let sigma-one = rotate-right-32(e, 6).bit-xor(
        rotate-right-32(e, 11),
      ).bit-xor(rotate-right-32(e, 25))
      let choice = e.bit-and(f).bit-xor(e.bit-not().bit-and(g))
      let temp-one = unsigned-32(
        h + sigma-one + choice + sha256-constants.at(index) + words.at(index),
      )
      let sigma-zero = rotate-right-32(a, 2).bit-xor(
        rotate-right-32(a, 13),
      ).bit-xor(rotate-right-32(a, 22))
      let majority = a.bit-and(b).bit-xor(a.bit-and(c)).bit-xor(
        b.bit-and(c),
      )
      let temp-two = unsigned-32(sigma-zero + majority)
      h = g
      g = f
      f = e
      e = unsigned-32(d + temp-one)
      d = c
      c = b
      b = a
      a = unsigned-32(temp-one + temp-two)
    }
    hash = (
      unsigned-32(hash.at(0) + a), unsigned-32(hash.at(1) + b),
      unsigned-32(hash.at(2) + c), unsigned-32(hash.at(3) + d),
      unsigned-32(hash.at(4) + e), unsigned-32(hash.at(5) + f),
      unsigned-32(hash.at(6) + g), unsigned-32(hash.at(7) + h),
    )
  }
  hash.map(hex-32).join()
}

#let canonical-sidecar-id(logical-name, payload-sha256) = sha256-hex(
  logical-name + "\u{0}" + payload-sha256,
)

#let required-report-columns = (
  stores: ("store_id", "name", "manifest_sha256", "validation_ok"),
  parameters: ("store_id", "key", "value_type", "is_missing"),
  statistics: ("store_id", "key", "value_type", "is_missing"),
  facts: ("store_id", "key", "value", "unit", "n", "aggregation", "status", "source"),
  source_coverage: ("store_id", "dimension", "value", "count"),
  targets: ("store_id", "target_id", "target_valid", "target_invalid_reason"),
  validity: ("store_id", "stage", "count", "fraction_of_full"),
  candidate_groups: ("store_id", "group_by", "group", "total", "actor_valid"),
  steps: ("store_id", "step_index", "policy", "cumulative_target_rri"),
  rollout_tree: ("store_id", "policy", "step_index", "selected_steps"),
  selected_depth: ("store_id", "step_index", "available", "valid_fraction"),
  runtime_storage: ("store_id", "file_count", "total_bytes", "status", "source"),
  failures: ("store_id", "kind", "severity", "status", "source"),
  sidecars: ("sidecar_id", "path", "name", "sha256", "format", "status"),
  sidecar_values: ("sidecar_id", "key", "value_type", "is_missing"),
)

#let required-report-facts = (
  "candidate_validity.valid",
  "candidate_validity.total",
  "candidate_validity.fraction",
  "candidate_validity.valid_per_step.mean",
  "candidate_validity.valid_per_step.median",
  "selected.total",
  "selected.path_length_m.mean",
  "selected.path_length_m.median",
  "selected.path_length_m.p5",
  "selected.path_length_m.p95",
)

#let paired-interval-method = "scene_clustered_percentile_bootstrap_95"
#let q1-ranking-interval-method = "scene_clustered_jackknife_normal_95_v1"
#let recovery-interval-method = "paired_scene_joint_ratio_bootstrap_95_v1"
#let recovery-ratio-definition = "ratio_of_paired_scene_mean_differences"
#let q1-pairwise-chance = 0.5
#let repeatability-decision-rule = "max_abs_diff_lte_tolerance_and_rank_identity_v2"
#let measurement-protocol-receipt-name = "oracle-measurement-repeatability-v1"
#let measurement-protocol-receipt-schema = "oracle_measurement_repeatability_receipt_v2"
#let measurement-benchmark-name = "oracle-measurement-benchmark-plan-v1"
#let measurement-benchmark-schema = "oracle_measurement_benchmark_plan_v1"
#let measurement-rank-direction = "descending_root_normalized_gain"
#let measurement-rank-tie-policy = "competition_equal_rank_v1"
#let headroom-decision-rule = "effect_gte_minimum_and_ci_low_gt_zero_v1"
#let candidate-support-decision-rule = "p05_support_gte_minimum_and_failed_root_rate_lte_maximum_v1"
#let candidate-support-receipt-name = "candidate-support-attempts-v2"
#let candidate-support-receipt-schema = "candidate_support_attempt_receipt_v2"
#let candidate-support-benchmark-name = "candidate-support-benchmark-plan-v2"
#let candidate-support-benchmark-schema = "candidate_support_benchmark_plan_v2"
#let q1-decision-rule = "ranking_gte_minimum_and_ci_low_gt_chance_and_calibration_mae_lte_maximum_v1"
#let q1-analysis-receipt-name = "q1-actor-analysis-v3"
#let q1-protocol-receipt-name = "q1-actor-protocol-audit-v7"
#let q1-protocol-receipt-schema = "actor_visible_q1_protocol_receipt_v7"
#let q1-population-benchmark-name = "q1-population-benchmark-v2"
#let q1-population-benchmark-schema = "q1_population_benchmark_v2"
#let q1-bundle-manifest-name = "manifest.json"
#let q1-scene-role = "held_out_scene_v1"
#let q1-target-source-protocol = "observation_derived_actor_visible_target_v1"
#let q1-audit-target-protocol = "v1_observed"
#let q1-audit-campaign-target-source = "detected_obbs"
#let q1-audit-campaign-descriptor-provenance = "actor_visible_detector"
#let q1-audit-gt-match-status = "admitted"
#let q1-audit-experiment-profile = "qh_cf0_v1"
#let q1-audit-selected-observation-protocol = "none"
#let q1-audit-action-mask-semantics = "actor_observed_action_mask_v1"
#let q1-audit-actor-input-manifest-schema = "qh_cf0_actor_input_leaf_manifest_v2"
#let q1-audit-prediction-semantics = "decoded_actor_visible_conditional_q_h1_v1"
#let q1-audit-label-semantics = "persisted_one_step_target_root_gain_v1"
#let q1-audit-ranking-pair-policy = "unordered_unequal_label_pairs_prediction_ties_incorrect_v1"
#let q1-audit-calibration-aggregation = "candidate_then_state_then_scene_macro_v1"
#let q1-audit-independent-unit-semantics = "ase_scene_id_v1"
#let q1-audit-actor-input-leaves = (
  (name: "root_observation_evidence", role: "actor_root_evidence", schema-id: "qh_root_observation_evidence_v1", source-owner: "actor_manifest", derivation: "actor_manifest_member_v1", presence: true),
  (name: "root_reference_pose", role: "actor_reference_frame", schema-id: "pose_tw_12_float32_v1", source-owner: "rollout_manifest", derivation: "rollout_state_projection_v1", presence: true),
  (name: "observed_target_descriptor", role: "actor_target_condition", schema-id: "observed_target_obb_pose12_extents3_float32_v1", source-owner: "rollout_manifest", derivation: "v1_observed_target_projection_v1", presence: true),
  (name: "candidate_pose_shell", role: "actor_candidate_geometry", schema-id: "candidate_pose_shell_s_n_pose12_float32_v1", source-owner: "rollout_manifest", derivation: "rollout_state_projection_v1", presence: true),
  (name: "actor_action_support", role: "actor_action_mask", schema-id: "actor_action_mask_s_n_bool_v1", source-owner: "rollout_manifest", derivation: "rollout_state_projection_v1", presence: true),
  (name: "factual_pose_history", role: "actor_causal_history", schema-id: "factual_pose_history_s_s_pose12_mask_v1", source-owner: "rollout_manifest", derivation: "prior_selected_rows_v1", presence: true),
  (name: "remaining_budget", role: "actor_budget", schema-id: "horizon_remaining_int64_v1", source-owner: "rollout_manifest", derivation: "rollout_state_projection_v1", presence: true),
  (name: "requested_horizon_q1", role: "actor_requested_horizon", schema-id: "requested_horizon_int64_v1", source-owner: "implementation_contract", derivation: "constant_one_v1", presence: true),
  (name: "selected_observation_prefix_absent", role: "actor_selected_observation", schema-id: "selected_observation_prefix_none_v1", source-owner: "actor_state_contract", derivation: "qh_cf0_absence_v1", presence: false),
)
#let q2-decision-rule = "all_units_support_and_rowwise_abs_plus_relative_tolerance_v1"
#let q2-certification-receipt-schema = "qh-exact-q2-certification-receipt-v5"
#let q2-certification-schema = "qh-exact-q2-certification-v5"
#let q2-selection-semantics = "balanced-hash-within-scene-target-support-strata-v2"
#let q2-independent-unit-semantics = "ordered-store-manifest-and-scene-v1"
#let q2-independent-unit-aggregation = "all_units_v1"
#let float32-epsilon = 0.00000011920928955078125
#let float32-maximum = 340282346638528859811704183484516925440.0
#let recovery-decision-rule = "fraction_gte_minimum_and_ci_low_gt_zero_v1"
#let derived-identity-abs-tolerance = 1e-10
#let endpoint-evidence-facts = (
  "policy.endpoint_gain.oracle_one_step.mean",
  "policy.endpoint_gain.oracle_one_step.ci_low",
  "policy.endpoint_gain.oracle_one_step.ci_high",
  "policy.endpoint_gain.oracle_lookahead.mean",
  "policy.endpoint_gain.oracle_lookahead.ci_low",
  "policy.endpoint_gain.oracle_lookahead.ci_high",
  "policy.endpoint_gain.learned_q.mean",
  "policy.endpoint_gain.learned_q.ci_low",
  "policy.endpoint_gain.learned_q.ci_high",
  "policy.endpoint_gain.learned_q.bundle_manifest_sha256",
  "policy.endpoint_gain.interval_method",
  "policy.endpoint_gain.n_scenes",
  "policy.endpoint_gain.cohort_sha256",
)
#let endpoint-evidence-contract = (
  (key: "policy.endpoint_gain.oracle_one_step.mean", aggregation: "paired_scene_endpoint_gain", unit: "fraction", value_kind: "number", maximum: 1),
  (key: "policy.endpoint_gain.oracle_one_step.ci_low", aggregation: "paired_scene_endpoint_gain", unit: "fraction", value_kind: "number", maximum: 1),
  (key: "policy.endpoint_gain.oracle_one_step.ci_high", aggregation: "paired_scene_endpoint_gain", unit: "fraction", value_kind: "number", maximum: 1),
  (key: "policy.endpoint_gain.oracle_lookahead.mean", aggregation: "paired_scene_endpoint_gain", unit: "fraction", value_kind: "number", maximum: 1),
  (key: "policy.endpoint_gain.oracle_lookahead.ci_low", aggregation: "paired_scene_endpoint_gain", unit: "fraction", value_kind: "number", maximum: 1),
  (key: "policy.endpoint_gain.oracle_lookahead.ci_high", aggregation: "paired_scene_endpoint_gain", unit: "fraction", value_kind: "number", maximum: 1),
  (key: "policy.endpoint_gain.learned_q.mean", aggregation: "paired_scene_endpoint_gain", unit: "fraction", value_kind: "number", maximum: 1),
  (key: "policy.endpoint_gain.learned_q.ci_low", aggregation: "paired_scene_endpoint_gain", unit: "fraction", value_kind: "number", maximum: 1),
  (key: "policy.endpoint_gain.learned_q.ci_high", aggregation: "paired_scene_endpoint_gain", unit: "fraction", value_kind: "number", maximum: 1),
  (key: "policy.endpoint_gain.learned_q.bundle_manifest_sha256", aggregation: "policy_identity", unit: "sha256", value_kind: "string"),
  (key: "policy.endpoint_gain.interval_method", aggregation: "analysis_identity", unit: "identity", value_kind: "string"),
  (key: "policy.endpoint_gain.n_scenes", aggregation: "count", unit: "count", value_kind: "integer"),
  (key: "policy.endpoint_gain.cohort_sha256", aggregation: "cohort_binding_sha256", unit: "sha256", value_kind: "string"),
)
#let oracle-endpoint-evidence-facts = endpoint-evidence-facts.filter(
  key => not key.starts-with("policy.endpoint_gain.learned_q."),
)
#let learned-endpoint-evidence-facts = endpoint-evidence-facts.filter(
  key => key.starts-with("policy.endpoint_gain.learned_q.") or key in (
    "policy.endpoint_gain.interval_method",
    "policy.endpoint_gain.n_scenes",
    "policy.endpoint_gain.cohort_sha256",
  ),
)
#let oracle-endpoint-evidence-contract = endpoint-evidence-contract.filter(
  item => item.key in oracle-endpoint-evidence-facts,
)
#let learned-endpoint-evidence-contract = endpoint-evidence-contract.filter(
  item => item.key in learned-endpoint-evidence-facts,
)
#let headroom-evidence-facts = (
  "policy.paired_scene_endpoint.effect",
  "policy.paired_scene_endpoint.ci_low",
  "policy.paired_scene_endpoint.ci_high",
  "policy.paired_scene_endpoint.interval_method",
  "policy.paired_scene_endpoint.n_scenes",
  "policy.paired_scene_endpoint.cohort_sha256",
  "headroom_gate.minimum_effect",
  "headroom_gate.rule",
  "headroom_gate.passed",
)
#let headroom-evidence-contract = (
  (key: "policy.paired_scene_endpoint.effect", aggregation: "paired_scene_mean_difference", unit: "fraction", value_kind: "number"),
  (key: "policy.paired_scene_endpoint.ci_low", aggregation: "paired_scene_mean_difference", unit: "fraction", value_kind: "number"),
  (key: "policy.paired_scene_endpoint.ci_high", aggregation: "paired_scene_mean_difference", unit: "fraction", value_kind: "number"),
  (key: "policy.paired_scene_endpoint.interval_method", aggregation: "analysis_identity", unit: "identity", value_kind: "string"),
  (key: "policy.paired_scene_endpoint.n_scenes", aggregation: "count", unit: "count", value_kind: "integer"),
  (key: "policy.paired_scene_endpoint.cohort_sha256", aggregation: "cohort_binding_sha256", unit: "sha256", value_kind: "string"),
  (key: "headroom_gate.minimum_effect", aggregation: "analysis_threshold", unit: "fraction", value_kind: "number", minimum: 0),
  (key: "headroom_gate.rule", aggregation: "analysis_identity", unit: "identity", value_kind: "string"),
  (key: "headroom_gate.passed", aggregation: "paired_scene_decision", unit: "bool", value_kind: "boolean"),
)
#let recovery-evidence-facts = (
  "policy.q_recovery.fraction",
  "policy.q_recovery.ci_low",
  "policy.q_recovery.ci_high",
  "policy.q_recovery.ratio_definition",
  "policy.q_recovery.interval_method",
  "policy.q_recovery.n_scenes",
  "policy.q_recovery.cohort_sha256",
  "policy.q_recovery.minimum_fraction",
  "policy.q_recovery.rule",
  "policy.q_recovery.passed",
)
#let recovery-evidence-contract = (
  (key: "policy.q_recovery.fraction", aggregation: "paired_scene_ratio_of_mean_differences", unit: "fraction", value_kind: "number"),
  (key: "policy.q_recovery.ci_low", aggregation: "paired_scene_ratio_of_mean_differences", unit: "fraction", value_kind: "number"),
  (key: "policy.q_recovery.ci_high", aggregation: "paired_scene_ratio_of_mean_differences", unit: "fraction", value_kind: "number"),
  (key: "policy.q_recovery.ratio_definition", aggregation: "analysis_identity", unit: "identity", value_kind: "string"),
  (key: "policy.q_recovery.interval_method", aggregation: "analysis_identity", unit: "identity", value_kind: "string"),
  (key: "policy.q_recovery.n_scenes", aggregation: "count", unit: "count", value_kind: "integer"),
  (key: "policy.q_recovery.cohort_sha256", aggregation: "cohort_binding_sha256", unit: "sha256", value_kind: "string"),
  (key: "policy.q_recovery.minimum_fraction", aggregation: "analysis_threshold", unit: "fraction", value_kind: "number", minimum: 0, maximum: 1),
  (key: "policy.q_recovery.rule", aggregation: "analysis_identity", unit: "identity", value_kind: "string"),
  (key: "policy.q_recovery.passed", aggregation: "paired_scene_decision", unit: "bool", value_kind: "boolean"),
)
#let population-evidence-facts = (
  "study.population.scenes",
  "study.population.targets",
  "study.population.exclusions",
)
#let population-evidence-contract = (
  (key: "study.population.scenes", aggregation: "count", unit: "count", value_kind: "integer", minimum: 1),
  (key: "study.population.targets", aggregation: "count", unit: "count", value_kind: "integer", minimum: 1),
  (key: "study.population.exclusions", aggregation: "count", unit: "count", value_kind: "integer", minimum: 0),
)
#let measurement-evidence-facts = (
  "oracle.metric.protocol.receipt_schema",
  "oracle.metric.protocol.id",
  "oracle.metric.protocol.benchmark_sha256",
  "oracle.metric.protocol.config_sha256",
  "oracle.metric.protocol.store_manifest_sha256",
  "oracle.metric.protocol.rank_direction",
  "oracle.metric.protocol.rank_tie_policy",
  "oracle.metric.repeatability.max_abs_diff",
  "oracle.metric.repeatability.tolerance",
  "oracle.metric.repeatability.rule",
  "oracle.metric.repeatability.n_repeats",
  "oracle.metric.repeatability.n_measurement_units",
  "oracle.metric.repeatability.ranking_agreement",
  "oracle.metric.repeatability.passed",
)
#let measurement-evidence-contract = (
  (key: "oracle.metric.protocol.receipt_schema", aggregation: "protocol_identity", unit: "identity", value_kind: "string"),
  (key: "oracle.metric.protocol.id", aggregation: "protocol_identity", unit: "identity", value_kind: "string"),
  (key: "oracle.metric.protocol.benchmark_sha256", aggregation: "protocol_binding_sha256", unit: "sha256", value_kind: "string"),
  (key: "oracle.metric.protocol.config_sha256", aggregation: "protocol_binding_sha256", unit: "sha256", value_kind: "string"),
  (key: "oracle.metric.protocol.store_manifest_sha256", aggregation: "protocol_binding_sha256", unit: "sha256", value_kind: "string"),
  (key: "oracle.metric.protocol.rank_direction", aggregation: "protocol_identity", unit: "identity", value_kind: "string"),
  (key: "oracle.metric.protocol.rank_tie_policy", aggregation: "protocol_identity", unit: "identity", value_kind: "string"),
  (key: "oracle.metric.repeatability.max_abs_diff", aggregation: "repeatability_max_abs_difference", unit: "fraction", value_kind: "number", minimum: 0),
  (key: "oracle.metric.repeatability.tolerance", aggregation: "analysis_threshold", unit: "fraction", value_kind: "number", minimum: 0),
  (key: "oracle.metric.repeatability.rule", aggregation: "analysis_identity", unit: "identity", value_kind: "string"),
  (key: "oracle.metric.repeatability.n_repeats", aggregation: "count", unit: "count", value_kind: "integer", minimum: 2),
  (key: "oracle.metric.repeatability.n_measurement_units", aggregation: "count", unit: "count", value_kind: "integer", minimum: 1),
  (key: "oracle.metric.repeatability.ranking_agreement", aggregation: "matched_unit_rank_identity", unit: "bool", value_kind: "boolean"),
  (key: "oracle.metric.repeatability.passed", aggregation: "repeatability_decision", unit: "bool", value_kind: "boolean"),
)
#let candidate-support-evidence-facts = (
  "candidate-support.receipt.schema",
  "candidate-support.receipt.benchmark_sha256",
  "candidate-support.receipt.config_sha256",
  "candidate-support.receipt.store_manifest_sha256",
  "candidate-support.receipt.expected_attempts",
  "candidate-support.actor-valid-fraction",
  "candidate-support.valid-support-p05",
  "candidate-support.failed-root-rate",
  "candidate-support.configured-family-zero-rate",
  "candidate-support.target-side-balance",
  "candidate-support.circular-orbit-span",
  "candidate-support.valid-support-p05.minimum",
  "candidate-support.failed-root-rate.maximum",
  "candidate-support.gate.rule",
  "candidate-support.gate.passed",
)
#let candidate-support-evidence-contract = (
  (key: "candidate-support.receipt.schema", aggregation: "protocol_identity", unit: "identity", value_kind: "string"),
  (key: "candidate-support.receipt.benchmark_sha256", aggregation: "protocol_binding_sha256", unit: "sha256", value_kind: "string"),
  (key: "candidate-support.receipt.config_sha256", aggregation: "protocol_binding_sha256", unit: "sha256", value_kind: "string"),
  (key: "candidate-support.receipt.store_manifest_sha256", aggregation: "protocol_binding_sha256", unit: "sha256", value_kind: "string"),
  (key: "candidate-support.receipt.expected_attempts", aggregation: "protocol_expected_count", unit: "count", value_kind: "integer", minimum: 1),
  (key: "candidate-support.actor-valid-fraction", aggregation: "state_then_scene_macro", unit: "fraction", value_kind: "number", minimum: 0, maximum: 1),
  (key: "candidate-support.valid-support-p05", aggregation: "state_then_scene_p05", unit: "count", value_kind: "number", minimum: 0),
  (key: "candidate-support.failed-root-rate", aggregation: "state_then_scene_macro", unit: "fraction", value_kind: "number", minimum: 0, maximum: 1),
  (key: "candidate-support.configured-family-zero-rate", aggregation: "state_then_scene_macro", unit: "fraction", value_kind: "number", minimum: 0, maximum: 1),
  (key: "candidate-support.target-side-balance", aggregation: "state_then_scene_macro", unit: "fraction", value_kind: "number", minimum: 0, maximum: 1),
  (key: "candidate-support.circular-orbit-span", aggregation: "state_then_scene_macro", unit: "deg", value_kind: "number", minimum: 0, maximum: 360),
  (key: "candidate-support.valid-support-p05.minimum", aggregation: "analysis_threshold", unit: "count", value_kind: "number", minimum: 0),
  (key: "candidate-support.failed-root-rate.maximum", aggregation: "analysis_threshold", unit: "fraction", value_kind: "number", minimum: 0, maximum: 1),
  (key: "candidate-support.gate.rule", aggregation: "analysis_identity", unit: "identity", value_kind: "string"),
  (key: "candidate-support.gate.passed", aggregation: "state_then_scene_decision", unit: "bool", value_kind: "boolean"),
)
#let q1-evidence-facts = (
  "q1.model.bundle_manifest_sha256",
  "q1.protocol.audit_receipt_sha256",
  "q1.protocol.receipt_schema",
  "q1.protocol.scene_role",
  "q1.protocol.target_source",
  "q1.protocol.target_matching_passed",
  "q1.protocol.actor_input_manifest_audited",
  "q1.protocol.actor_oracle_mask_separation_audited",
  "q1.protocol.hard_mask_applied",
  "q1.protocol.causal_history_only",
  "q1.ranking.pairwise_accuracy",
  "q1.ranking.pairwise_accuracy.ci_low",
  "q1.ranking.pairwise_accuracy.ci_high",
  "q1.ranking.interval_method",
  "q1.calibration.mae",
  "q1.population.n_scenes",
  "q1.ranking.chance",
  "q1.ranking.pairwise_accuracy.minimum",
  "q1.calibration.mae.maximum",
  "q1.gate.rule",
  "q1.gate.passed",
)
#let q1-evidence-contract = (
  (key: "q1.model.bundle_manifest_sha256", aggregation: "model_identity", unit: "sha256", value_kind: "string"),
  (key: "q1.protocol.audit_receipt_sha256", aggregation: "protocol_binding_sha256", unit: "sha256", value_kind: "string"),
  (key: "q1.protocol.receipt_schema", aggregation: "protocol_identity", unit: "identity", value_kind: "string"),
  (key: "q1.protocol.scene_role", aggregation: "protocol_identity", unit: "identity", value_kind: "string"),
  (key: "q1.protocol.target_source", aggregation: "protocol_identity", unit: "identity", value_kind: "string"),
  (key: "q1.protocol.target_matching_passed", aggregation: "protocol_audit", unit: "bool", value_kind: "boolean"),
  (key: "q1.protocol.actor_input_manifest_audited", aggregation: "protocol_audit", unit: "bool", value_kind: "boolean"),
  (key: "q1.protocol.actor_oracle_mask_separation_audited", aggregation: "protocol_audit", unit: "bool", value_kind: "boolean"),
  (key: "q1.protocol.hard_mask_applied", aggregation: "protocol_audit", unit: "bool", value_kind: "boolean"),
  (key: "q1.protocol.causal_history_only", aggregation: "protocol_audit", unit: "bool", value_kind: "boolean"),
  (key: "q1.ranking.pairwise_accuracy", aggregation: "state_then_scene_macro", unit: "fraction", value_kind: "number", minimum: 0, maximum: 1),
  (key: "q1.ranking.pairwise_accuracy.ci_low", aggregation: "scene_clustered_interval", unit: "fraction", value_kind: "number", minimum: 0, maximum: 1),
  (key: "q1.ranking.pairwise_accuracy.ci_high", aggregation: "scene_clustered_interval", unit: "fraction", value_kind: "number", minimum: 0, maximum: 1),
  (key: "q1.ranking.interval_method", aggregation: "analysis_identity", unit: "identity", value_kind: "string"),
  (key: "q1.calibration.mae", aggregation: "state_then_scene_macro", unit: "root_normalized_return", value_kind: "number", minimum: 0),
  (key: "q1.population.n_scenes", aggregation: "count", unit: "count", value_kind: "integer", minimum: 1),
  (key: "q1.ranking.chance", aggregation: "analysis_threshold", unit: "fraction", value_kind: "number", minimum: 0, maximum: 1),
  (key: "q1.ranking.pairwise_accuracy.minimum", aggregation: "analysis_threshold", unit: "fraction", value_kind: "number", minimum: 0, maximum: 1),
  (key: "q1.calibration.mae.maximum", aggregation: "analysis_threshold", unit: "root_normalized_return", value_kind: "number", minimum: 0),
  (key: "q1.gate.rule", aggregation: "analysis_identity", unit: "identity", value_kind: "string"),
  (key: "q1.gate.passed", aggregation: "state_then_scene_decision", unit: "bool", value_kind: "boolean"),
)
#let q2-evidence-facts = (
  "q2.exact.certification_receipt_sha256",
  "q2.exact.bundle_manifest_sha256",
  "q2.exact.mae",
  "q2.exact.coverage",
  "q2.exact.minimum_support_stratum_rows",
  "q2.exact.minimum_rows_per_independent_unit",
  "q2.exact.maximum_tolerance_excess",
  "q2.exact.n_independent_units",
  "q2.exact.coverage.minimum",
  "q2.exact.minimum_independent_units",
  "q2.exact.minimum_rows_per_independent_unit.required",
  "q2.exact.absolute_tolerance",
  "q2.exact.relative_tolerance",
  "q2.exact.rule",
  "q2.exact.passed",
)
#let q2-evidence-contract = (
  (key: "q2.exact.certification_receipt_sha256", aggregation: "receipt_binding_sha256", unit: "sha256", value_kind: "string"),
  (key: "q2.exact.bundle_manifest_sha256", aggregation: "policy_identity", unit: "sha256", value_kind: "string"),
  (key: "q2.exact.mae", aggregation: "independent_unit_macro", unit: "root_normalized_return", value_kind: "number", minimum: 0),
  (key: "q2.exact.coverage", aggregation: "selected_chain_fraction", unit: "fraction", value_kind: "number", minimum: 0, maximum: 1),
  (key: "q2.exact.minimum_support_stratum_rows", aggregation: "support_stratum_minimum", unit: "count", value_kind: "integer", minimum: 0),
  (key: "q2.exact.minimum_rows_per_independent_unit", aggregation: "independent_unit_minimum", unit: "count", value_kind: "integer", minimum: 0),
  (key: "q2.exact.maximum_tolerance_excess", aggregation: "exact_row_maximum", unit: "root_normalized_return", value_kind: "number"),
  (key: "q2.exact.n_independent_units", aggregation: "count", unit: "count", value_kind: "integer", minimum: 1),
  (key: "q2.exact.coverage.minimum", aggregation: "analysis_threshold", unit: "fraction", value_kind: "number", minimum: 0, maximum: 1),
  (key: "q2.exact.minimum_independent_units", aggregation: "analysis_threshold", unit: "count", value_kind: "integer", minimum: 5),
  (key: "q2.exact.minimum_rows_per_independent_unit.required", aggregation: "analysis_threshold", unit: "count", value_kind: "integer", minimum: 1),
  (key: "q2.exact.absolute_tolerance", aggregation: "analysis_threshold", unit: "root_normalized_return", value_kind: "number", minimum: 0),
  (key: "q2.exact.relative_tolerance", aggregation: "analysis_threshold", unit: "dimensionless", value_kind: "number", minimum: 0),
  (key: "q2.exact.rule", aggregation: "analysis_identity", unit: "identity", value_kind: "string"),
  (key: "q2.exact.passed", aggregation: "all_units_v1", unit: "bool", value_kind: "boolean"),
)

#let status-report-tables = ("facts", "runtime_storage", "failures", "sidecars")

#let default-thesis-report-path = "/typst/thesis/data/report-bundle-fixture.json"

#let thesis-report-settings() = {
  let mode = sys.inputs.at("aria-thesis-mode", default: "development")
  assert(mode in ("development", "submission"), message: "invalid aria-thesis-mode")

  let explicit-path = sys.inputs.at("aria-thesis-data", default: none)
  let evidence-status = sys.inputs.at("aria-thesis-evidence-status", default: "pilot")
  if mode == "submission" {
    assert(explicit-path != none, message: "submission mode requires explicit aria-thesis-data")
    assert(
      evidence-status == "confirmatory",
      message: "submission mode requires aria-thesis-evidence-status=confirmatory",
    )
  }

  (
    mode: mode,
    path: if explicit-path == none { default-thesis-report-path } else { explicit-path },
    evidence-status: evidence-status,
    required-role: if mode == "submission" { "evidence" } else { none },
  )
}

#let load-thesis-report(path, evidence-status: "pilot", required-role: none) = {
  assert(evidence-status in ("pilot", "confirmatory"), message: "invalid thesis evidence status")
  let report = json(path)
  assert(report.at("schema_version", default: none) == report-schema-version, message: "unsupported thesis report schema")
  let bundle-role = report.at("bundle_role", default: none)
  assert(bundle-role in ("fixture", "evidence"), message: "invalid or missing thesis report bundle_role")
  if required-role != none {
    assert(bundle-role == required-role, message: "thesis report bundle_role does not satisfy publication gate")
  }
  let tables = report.at("tables", default: none)
  assert(type(tables) == dictionary, message: "thesis report tables must be a dictionary")

  for (name, required-columns) in required-report-columns {
    let table-data = tables.at(name, default: none)
    assert(type(table-data) == dictionary, message: "missing thesis report table: " + name)
    let columns = table-data.at("columns", default: ())
    assert(type(columns) == array, message: "invalid columns for thesis report table: " + name)
    assert(required-columns.all(column => column in columns), message: "missing required columns in thesis report table: " + name)
    assert(type(table-data.at("rows", default: none)) == array, message: "invalid rows for thesis report table: " + name)
  }

  let fact-rows = tables.facts.rows
  for key in required-report-facts {
    assert(fact-rows.any(row => row.at("key", default: none) == key), message: "missing required thesis report fact: " + key)
  }
  for name in status-report-tables {
    assert(
      tables.at(name).rows.all(row => row.at("status", default: none) == evidence-status),
      message: "thesis report status does not match aria-thesis-evidence-status: " + name,
    )
  }
  report
}

#let report-stores-have-facts(report, keys, denominators: false) = {
  report.tables.stores.rows.len() > 0 and report.tables.stores.rows.all(store => {
    keys.all(key => {
      let matches = report.tables.facts.rows.filter(
        row => row.store_id == store.store_id and row.key == key,
      )
      matches.len() == 1 and matches.first().value != none and (
        not denominators or (
          type(matches.first().at("n", default: none)) == int and matches.first().n > 0
        )
      )
    })
  })
}

#let report-stores-have-boolean-fact(report, key) = {
  report-stores-have-facts(report, (key,)) and report.tables.stores.rows.all(store => {
    let matches = report.tables.facts.rows.filter(
      row => row.store_id == store.store_id and row.key == key,
    )
    type(matches.first().value) == bool
  })
}

#let report-store-count-binds-facts(report, store-id, count-key, keys) = {
  let count-matches = report.tables.facts.rows.filter(
    row => row.store_id == store-id and row.key == count-key,
  )
  count-matches.len() == 1 and {
    let count = count-matches.first().value
    type(count) == int and count > 0 and keys.all(key => {
      let matches = report.tables.facts.rows.filter(
        row => row.store_id == store-id and row.key == key,
      )
      matches.len() == 1 and matches.first().n == count
    })
  }
}

#let report-stores-decision-passed(report, key) = {
  report-stores-have-boolean-fact(report, key) and report.tables.stores.rows.all(store => {
    let matches = report.tables.facts.rows.filter(
      row => row.store_id == store.store_id and row.key == key,
    )
    matches.first().value == true
  })
}

#let report-store-facts-have-provenance(
  report,
  store-id,
  keys,
  required-fragment: none,
) = {
  let sidecar-rows = report.tables.at(
    "sidecars",
    default: (rows: ()),
  ).rows
  keys.all(key => {
    let matches = report.tables.facts.rows.filter(
      row => row.store_id == store-id and row.key == key,
    )
    matches.len() == 1 and {
      let source = matches.first().source
      type(source) == str and source.len() > 0 and (
        required-fragment == none or (
          source.contains(required-fragment) and (
            required-fragment != "|sidecar:" or
            {
              let sidecar-id = source.split(required-fragment).last()
              let matching-sidecars = sidecar-rows.filter(
                row => row.sidecar_id == sidecar-id,
              )
              sidecar-id.match(regex("^[0-9a-f]{64}$")) != none and matching-sidecars.len() == 1 and {
                let sidecar = matching-sidecars.first()
                let path-valid = type(sidecar.path) == str and sidecar.path.len() > 0
                let name-valid = type(sidecar.name) == str and sidecar.name == sidecar.path
                let digest-valid = type(sidecar.sha256) == str and sidecar.sha256.match(
                  regex("^[0-9a-f]{64}$"),
                ) != none
                let identity-valid = name-valid and digest-valid and sidecar.sidecar_id == canonical-sidecar-id(
                  sidecar.name,
                  sidecar.sha256,
                )
                let format-valid = sidecar.format in ("json", "jsonl")
                let status-valid = sidecar.status == "confirmatory"
                path-valid and name-valid and digest-valid and identity-valid and format-valid and status-valid
              }
            }
          )
        )
      )
    }
  })
}

#let report-store-facts-share-value(report, store-id, keys) = {
  let rows = keys.map(key => {
    let matches = report.tables.facts.rows.filter(
      row => row.store_id == store-id and row.key == key,
    )
    if matches.len() == 1 { matches.first() } else { none }
  })
  rows.all(row => row != none and row.value != none) and rows.all(
    row => row.value == rows.first().value,
  )
}

#let report-store-facts-share-source(report, store-id, keys) = {
  let rows = keys.map(key => {
    let matches = report.tables.facts.rows.filter(
      row => row.store_id == store-id and row.key == key,
    )
    if matches.len() == 1 { matches.first() } else { none }
  })
  rows.all(
    row => row != none and type(row.source) == str and row.source.len() > 0,
  ) and rows.all(row => row.source == rows.first().source)
}

// Dependent learned claims may combine evidence only when every report profile
// names the same content-addressed inference bundle. Per-store equality is not
// sufficient because otherwise two internally consistent stores could still
// refer to different selected models.
#let report-stores-facts-share-sha256(report, keys) = {
  let stores = report.tables.stores.rows
  let rows = stores.map(store => keys.map(key => {
    let matches = report.tables.facts.rows.filter(
      row => row.store_id == store.store_id and row.key == key,
    )
    if matches.len() == 1 { matches.first() } else { none }
  })).flatten()
  rows.len() == stores.len() * keys.len() and rows.all(
    row => row != none and type(row.value) == str and row.value.match(
      regex("^[0-9a-f]{64}$"),
    ) != none,
  ) and rows.map(row => row.value).dedup().len() == 1
}

// A globally rendered result may select one storage row only after every
// profile repeats the same validated receipt-derived value for every key.
#let report-stores-facts-share-values(report, keys) = {
  let stores = report.tables.stores.rows
  stores.len() > 0 and keys.all(key => {
    let rows = stores.map(store => {
      let matches = report.tables.facts.rows.filter(
        row => row.store_id == store.store_id and row.key == key,
      )
      if matches.len() == 1 { matches.first() } else { none }
    })
    rows.all(row => row != none and row.value != none) and rows.map(
      row => row.value,
    ).dedup().len() == 1
  })
}

// Cross-store source equality is separate from value equality: two profiles
// must not reproduce the same numbers from different analysis projections.
#let report-stores-facts-share-sources(report, keys) = {
  let stores = report.tables.stores.rows
  let rows = stores.map(store => keys.map(key => {
    let matches = report.tables.facts.rows.filter(
      row => row.store_id == store.store_id and row.key == key,
    )
    if matches.len() == 1 { matches.first() } else { none }
  })).flatten()
  stores.len() > 0 and rows.len() == stores.len() * keys.len() and rows.all(
    row => row != none and type(row.source) == str and row.source.len() > 0,
  ) and rows.map(row => row.source).dedup().len() == 1
}

#let evidence-gate-state(
  evidence-available,
  decision-passed,
  prerequisites-passed: true,
) = {
  let gate-passed = evidence-available and decision-passed
  (
    evidence_available: evidence-available,
    gate_passed: gate-passed,
    claim_admissible: prerequisites-passed and gate-passed,
  )
}

#let conditional-ratio-gate-state(
  raw-evidence-available,
  denominator-admissible,
  ratio-contract-available,
  decision-passed,
  remaining-prerequisites-passed: true,
) = {
  let ratio-evidence-available = raw-evidence-available and denominator-admissible and ratio-contract-available
  let state = evidence-gate-state(
    ratio-evidence-available,
    decision-passed,
    prerequisites-passed: remaining-prerequisites-passed,
  )
  (
    raw_evidence_available: raw-evidence-available,
    ratio_evidence_available: ratio-evidence-available,
    state: state,
  )
}

#let report-fact(report, key) = {
  let matches = report.tables.facts.rows.filter(row => row.key == key)
  assert(matches.len() == 1, message: "expected one thesis report fact: " + key)
  matches.first()
}

#let report-store-fact(report, store-id, key) = {
  let matches = report.tables.facts.rows.filter(
    row => row.store_id == store-id and row.key == key,
  )
  assert(
    matches.len() == 1,
    message: "expected one thesis report fact for store and key: " + store-id + " / " + key,
  )
  matches.first()
}

#let report-value-matches-kind(value, value-kind) = {
  if value-kind == "number" {
    type(value) == int or type(value) == float
  } else if value-kind == "integer" {
    type(value) == int
  } else if value-kind == "string" {
    type(value) == str
  } else if value-kind == "boolean" {
    type(value) == bool
  } else {
    false
  }
}

#let report-value-is-finite-float32(value) = report-value-matches-kind(
  value,
  "number",
) and calc.abs(value) <= float32-maximum

#let report-store-facts-match-contract(report, store-id, contracts, expected-n) = {
  contracts.all(contract => {
    let matches = report.tables.facts.rows.filter(
      row => row.store_id == store-id and row.key == contract.key,
    )
    matches.len() == 1 and {
      let row = matches.first()
      let expected-unit = contract.at("unit", default: none)
      let expected-kind = contract.at("value_kind", default: none)
      let minimum = contract.at("minimum", default: none)
      let maximum = contract.at("maximum", default: none)
      row.value != none and row.n == expected-n and row.aggregation == contract.aggregation and (
        expected-unit == none or row.at("unit", default: none) == expected-unit
      ) and (
        expected-kind == none or report-value-matches-kind(row.value, expected-kind)
      ) and (
        minimum == none or (
          report-value-matches-kind(row.value, "number") and row.value >= minimum
        )
      ) and (
        maximum == none or (
          report-value-matches-kind(row.value, "number") and row.value <= maximum
        )
      )
    }
  })
}

#let report-store-fact-values-match(report, store-id, expected-values) = {
  expected-values.all(expected => {
    let matches = report.tables.facts.rows.filter(
      row => row.store_id == store-id and row.key == expected.key,
    )
    matches.len() == 1 and matches.first().value == expected.value
  })
}

#let report-store-interval-is-ordered(report, store-id, low-key, high-key) = {
  let low-matches = report.tables.facts.rows.filter(
    row => row.store_id == store-id and row.key == low-key,
  )
  let high-matches = report.tables.facts.rows.filter(
    row => row.store_id == store-id and row.key == high-key,
  )
  low-matches.len() == 1 and high-matches.len() == 1 and {
    let low = low-matches.first().value
    let high = high-matches.first().value
    report-value-matches-kind(low, "number") and report-value-matches-kind(
      high,
      "number",
    ) and low <= high
  }
}

#let report-store-fact-is-sha256(report, store-id, key) = {
  let matches = report.tables.facts.rows.filter(
    row => row.store_id == store-id and row.key == key,
  )
  matches.len() == 1 and {
    let value = matches.first().value
    type(value) == str and value.match(regex("^[0-9a-f]{64}$")) != none
  }
}

#let report-sidecar-row-value-matches(row, expected) = row != none and row.is_missing == false and if type(expected) == bool {
  row.value_type == "bool" and row.at("value_bool", default: none) == expected
} else if type(expected) == int {
  row.value_type == "int" and row.at("value_int", default: none) == expected
} else if type(expected) == float {
  row.value_type == "float" and row.at("value_float", default: none) == expected
} else if type(expected) == str {
  row.value_type == "str" and row.at("value_text", default: none) == expected
} else {
  false
}

#let report-sidecar-value-matches(report, sidecar-id, key, expected) = {
  let matches = report.tables.sidecar_values.rows.filter(
    row => row.sidecar_id == sidecar-id and row.key == key,
  )
  matches.len() == 1 and report-sidecar-row-value-matches(
    matches.first(),
    expected,
  )
}

#let report-sidecar-value-index(report, sidecar-id) = {
  let rows = (:)
  let duplicates = ()
  for row in report.tables.sidecar_values.rows {
    if row.sidecar_id == sidecar-id {
      if row.key in rows {
        duplicates.push(row.key)
      } else {
        rows.insert(row.key, row)
      }
    }
  }
  (rows: rows, duplicates: duplicates)
}

#let report-sidecar-indexed-row-or-none(index, key) = if index.duplicates.contains(
  key,
) {
  none
} else {
  index.rows.at(key, default: none)
}

#let report-sidecar-indexed-value-matches(index, key, expected) = report-sidecar-row-value-matches(
  report-sidecar-indexed-row-or-none(index, key),
  expected,
)

#let report-sidecar-row-value-or-none(row) = if row == none or row.is_missing != false {
  none
} else if row.value_type == "bool" {
  row.at("value_bool", default: none)
} else if row.value_type == "int" {
  row.at("value_int", default: none)
} else if row.value_type == "float" {
  row.at("value_float", default: none)
} else if row.value_type == "str" {
  row.at("value_text", default: none)
} else {
  none
}

#let report-sidecar-indexed-value-or-none(index, key) = report-sidecar-row-value-or-none(
  report-sidecar-indexed-row-or-none(index, key),
)

#let report-store-fact-index(report) = {
  let rows = (:)
  let duplicates = ()
  for row in report.tables.facts.rows {
    let indexed-key = row.store_id + "\u{1f}" + row.key
    if indexed-key in rows {
      duplicates.push(indexed-key)
    } else {
      rows.insert(indexed-key, row)
    }
  }
  (rows: rows, duplicates: duplicates)
}

#let report-store-indexed-row-or-none(index, store-id, key) = {
  let indexed-key = store-id + "\u{1f}" + key
  if index.duplicates.contains(indexed-key) {
    none
  } else {
    index.rows.at(indexed-key, default: none)
  }
}

#let report-store-analysis-sidecar-binds-facts(
  report,
  store-id,
  facts,
  required-name: none,
) = {
  let fact-index = report-store-fact-index(report)
  let fact-rows = facts.map(
    key => report-store-indexed-row-or-none(fact-index, store-id, key),
  )
  let sidecar-rows = report.tables.at(
    "sidecars",
    default: (rows: ()),
  ).rows
  fact-rows.len() > 0 and fact-rows.all(row => row != none) and {
    let source = fact-rows.first().source
    let source-valid = (
      type(source) == str,
      type(source) == str and source.contains("|sidecar:"),
      fact-rows.all(row => row.source == source),
    ).all(value => value)
    let sidecar-id = if source-valid { source.split("|sidecar:").last() } else { "" }
    let matching-sidecars = sidecar-rows.filter(
      row => row.sidecar_id == sidecar-id,
    )
    (
      source-valid,
      sidecar-id.match(regex("^[0-9a-f]{64}$")) != none,
      matching-sidecars.len() == 1,
    ).all(value => value) and {
        let sidecar = matching-sidecars.first()
        let logical-name = if required-name == none { sidecar.name } else { required-name }
        let sidecar-value-index = report-sidecar-value-index(report, sidecar-id)
        let fact-prefix-index = (:)
        let duplicate-fact-keys = ()
        for row in sidecar-value-index.rows.values() {
          if row.key.match(regex("^facts\\[[0-9]+\\]\\.key$")) != none and row.value_type == "str" {
            let fact-key = row.at("value_text", default: none)
            let fact-prefix = row.key.replace(regex("\\.key$"), "")
            let fact-store = report-sidecar-indexed-value-or-none(
              sidecar-value-index,
              fact-prefix + ".store_id",
            )
            if fact-key != none and type(fact-store) == str {
              let fact-identity = fact-store + "\u{1f}" + fact-key
              if fact-identity in fact-prefix-index {
                duplicate-fact-keys.push(fact-identity)
              } else {
                fact-prefix-index.insert(
                  fact-identity,
                  fact-prefix,
                )
              }
            }
          }
        }
        let sidecar-digest-valid = type(sidecar.sha256) == str and sidecar.sha256.match(
          regex("^[0-9a-f]{64}$"),
        ) != none
        let sidecar-identity-valid = type(logical-name) == str and sidecar-digest-valid and sidecar.sidecar_id == canonical-sidecar-id(
          logical-name,
          sidecar.sha256,
        )
        let sidecar-valid = (
          type(sidecar.path) == str and sidecar.path.len() > 0,
          type(logical-name) == str and logical-name.len() > 0,
          sidecar.path == logical-name,
          sidecar.name == logical-name,
          sidecar-digest-valid,
          sidecar-identity-valid,
          sidecar.format in ("json", "jsonl"),
          sidecar.status == "confirmatory",
        ).all(value => value)
        let envelope-valid = (
          (key: "schema_version", value: "aria-nbv-analysis-facts-v1"),
          (key: "bundle_role", value: "analysis_facts"),
          (key: "status", value: "confirmatory"),
        ).all(expected => report-sidecar-indexed-value-matches(
          sidecar-value-index,
          expected.key,
          expected.value,
        )) and if "logical_name" in sidecar-value-index.rows {
          report-sidecar-indexed-value-matches(
            sidecar-value-index,
            "logical_name",
            logical-name,
          )
        } else { true }
        let payload-valid = fact-rows.all(fact => {
          let fact-identity = store-id + "\u{1f}" + fact.key
          let prefix = fact-prefix-index.at(fact-identity, default: none)
          prefix != none and not duplicate-fact-keys.contains(fact-identity) and {
            let provenance = source.split("|sidecar:").first()
            (
              (key: prefix + ".store_id", value: store-id),
              (key: prefix + ".key", value: fact.key),
              (key: prefix + ".value", value: fact.value),
              (key: prefix + ".unit", value: fact.unit),
              (key: prefix + ".n", value: fact.n),
              (key: prefix + ".aggregation", value: fact.aggregation),
              (key: prefix + ".provenance", value: provenance),
            ).all(expected => report-sidecar-indexed-value-matches(
              sidecar-value-index,
              expected.key,
              expected.value,
            ))
          }
        })
        sidecar-valid and envelope-valid and payload-valid
      }
  }
}

#let report-sha256-value-valid(value) = type(value) == str and value.match(
  regex("^[0-9a-f]{64}$"),
) != none

#let report-identity16-value-valid(value) = type(value) == str and value.match(
  regex("^[0-9a-f]{16}$"),
) != none

#let report-store-manifest-sha256(report, store-id) = {
  let matches = report.tables.stores.rows.filter(row => row.store_id == store-id)
  if matches.len() == 1 and report-sha256-value-valid(
    matches.first().at("manifest_sha256", default: none),
  ) {
    matches.first().manifest_sha256
  } else { none }
}

#let report-confirmatory-sidecar-by-digest(
  report,
  digest,
  required-name: none,
) = {
  let matches = report.tables.at(
    "sidecars",
    default: (rows: ()),
  ).rows.filter(sidecar => {
    let path-valid = type(sidecar.path) == str and sidecar.path.len() > 0
    let name-valid = type(sidecar.name) == str and path-valid and sidecar.path == sidecar.name
    let digest-valid = type(sidecar.sha256) == str and report-sha256-value-valid(
      sidecar.sha256,
    )
    let identity-valid = name-valid and digest-valid and sidecar.sidecar_id == canonical-sidecar-id(
      sidecar.name,
      sidecar.sha256,
    )
    sidecar.sha256 == digest and name-valid and (
      required-name == none or sidecar.name == required-name
    ) and identity-valid and sidecar.format in ("json", "jsonl") and sidecar.status == "confirmatory"
  })
  if matches.len() == 1 { matches.first() } else { none }
}

// Bundle manifests identify their canonical JSON payload with the embedded
// manifest_sha256, while report sidecar metadata independently identifies the
// serialized file bytes. Preserve both identities instead of conflating them.
#let report-confirmatory-sidecar-by-embedded-digest(
  report,
  digest,
  embedded-key,
  required-name: none,
) = {
  let matches = report.tables.at(
    "sidecars",
    default: (rows: ()),
  ).rows.filter(sidecar => {
    let path-valid = type(sidecar.path) == str and sidecar.path.len() > 0
    let name-valid = type(sidecar.name) == str and path-valid and sidecar.path == sidecar.name
    let file-digest-valid = type(sidecar.sha256) == str and report-sha256-value-valid(
      sidecar.sha256,
    )
    let identity-valid = name-valid and file-digest-valid and sidecar.sidecar_id == canonical-sidecar-id(
      sidecar.name,
      sidecar.sha256,
    )
    let index = report-sidecar-value-index(report, sidecar.sidecar_id)
    let embedded-digest = report-sidecar-indexed-value-or-none(index, embedded-key)
    embedded-digest == digest and report-sha256-value-valid(
      embedded-digest,
    ) and name-valid and (
      required-name == none or sidecar.name == required-name
    ) and identity-valid and sidecar.format in ("json", "jsonl") and sidecar.status == "confirmatory"
  })
  if matches.len() == 1 { matches.first() } else { none }
}

#let report-sidecar-record-prefixes(index, collection, identity-field) = {
  let pattern = regex("^" + collection + "\\[[0-9]+\\]\\." + identity-field + "$")
  index.rows.values().filter(
    row => row.key.match(pattern) != none,
  ).map(row => row.key.replace(regex("\\." + identity-field + "$"), ""))
}

#let report-store-number-value(report, store-id, key) = {
  let matches = report.tables.facts.rows.filter(
    row => row.store_id == store-id and row.key == key,
  )
  if matches.len() == 1 and report-value-matches-kind(
    matches.first().value,
    "number",
  ) {
    matches.first().value
  } else {
    none
  }
}

#let report-store-boolean-value(report, store-id, key) = {
  let matches = report.tables.facts.rows.filter(
    row => row.store_id == store-id and row.key == key,
  )
  if matches.len() == 1 and type(matches.first().value) == bool {
    matches.first().value
  } else {
    none
  }
}

#let report-store-headroom-identity-valid(
  report,
  store-id,
  tolerance: derived-identity-abs-tolerance,
) = {
  let one-step = report-store-number-value(
    report,
    store-id,
    "policy.endpoint_gain.oracle_one_step.mean",
  )
  let lookahead = report-store-number-value(
    report,
    store-id,
    "policy.endpoint_gain.oracle_lookahead.mean",
  )
  let effect = report-store-number-value(
    report,
    store-id,
    "policy.paired_scene_endpoint.effect",
  )
  (one-step, lookahead, effect).all(value => value != none) and calc.abs(
    effect - (lookahead - one-step),
  ) <= tolerance
}

#let report-store-recovery-identity-valid(
  report,
  store-id,
  tolerance: derived-identity-abs-tolerance,
) = {
  let one-step = report-store-number-value(
    report,
    store-id,
    "policy.endpoint_gain.oracle_one_step.mean",
  )
  let lookahead = report-store-number-value(
    report,
    store-id,
    "policy.endpoint_gain.oracle_lookahead.mean",
  )
  let learned = report-store-number-value(
    report,
    store-id,
    "policy.endpoint_gain.learned_q.mean",
  )
  let recovery = report-store-number-value(
    report,
    store-id,
    "policy.q_recovery.fraction",
  )
  (one-step, lookahead, learned, recovery).all(value => value != none) and {
    let denominator = lookahead - one-step
    calc.abs(denominator) > tolerance and calc.abs(
      recovery - (learned - one-step) / denominator,
    ) <= tolerance
  }
}

#let report-store-analysis-family-valid(
  report,
  store-id,
  facts,
  contract,
  expected-n,
  expected-values: (),
  interval-pairs: (),
  digest-keys: (),
  required-source-fragment: none,
) = {
  report-store-facts-match-contract(
    report,
    store-id,
    contract,
    expected-n,
  ) and report-store-fact-values-match(
    report,
    store-id,
    expected-values,
  ) and interval-pairs.all(pair => report-store-interval-is-ordered(
    report,
    store-id,
    pair.low,
    pair.high,
  )) and digest-keys.all(key => report-store-fact-is-sha256(
    report,
    store-id,
    key,
  )) and report-store-facts-have-provenance(
    report,
    store-id,
    facts,
    required-fragment: required-source-fragment,
  ) and report-store-facts-share-source(
    report,
    store-id,
    facts,
  ) and report-store-analysis-sidecar-binds-facts(
    report,
    store-id,
    facts,
  )
}

#let report-store-gated-family-valid(
  report,
  store-id,
  facts,
  contract,
  count-key,
) = {
  let count-matches = report.tables.facts.rows.filter(
    row => row.store_id == store-id and row.key == count-key,
  )
  count-matches.len() == 1 and {
    let count = count-matches.first().value
    type(count) == int and count > 0 and report-store-analysis-family-valid(
      report,
      store-id,
      facts,
      contract,
      count,
      required-source-fragment: "|sidecar:",
    ) and report-store-count-binds-facts(
      report,
      store-id,
      count-key,
      facts,
    )
  }
}

#let report-store-record-prefixes(report, store-id, collection, identity-field) = {
  let pattern = regex("^" + collection + "\\[[0-9]+\\]\\." + identity-field + "$")
  report.tables.facts.rows.filter(row => (
    row.store_id == store-id,
    row.key.match(pattern) != none,
  ).all(value => value)).map(
    row => row.key.replace(regex("\\." + identity-field + "$"), ""),
  )
}

#let report-store-candidate-support-receipt-valid(report, store-id) = {
  let scene-count = report-store-number-value(
    report,
    store-id,
    "study.population.scenes",
  )
  let target-count = report-store-number-value(
    report,
    store-id,
    "study.population.targets",
  )
  let reported-p05 = report-store-number-value(
    report,
    store-id,
    "candidate-support.valid-support-p05",
  )
  let reported-failed-rate = report-store-number-value(
    report,
    store-id,
    "candidate-support.failed-root-rate",
  )
  let expected-attempts = report-store-number-value(
    report,
    store-id,
    "candidate-support.receipt.expected_attempts",
  )
  let store-manifest = report-store-manifest-sha256(report, store-id)
  let fact-index = report-store-fact-index(report)
  let benchmark-row = report-store-indexed-row-or-none(
    fact-index,
    store-id,
    "candidate-support.receipt.benchmark_sha256",
  )
  let benchmark-digest = if benchmark-row != none and report-sha256-value-valid(
    benchmark-row.value,
  ) { benchmark-row.value } else { "" }
  let benchmark-sidecar = report-confirmatory-sidecar-by-digest(
    report,
    benchmark-digest,
    required-name: candidate-support-benchmark-name,
  )
  let benchmark-index = report-sidecar-value-index(
    report,
    if benchmark-sidecar == none { "" } else { benchmark-sidecar.sidecar_id },
  )
  let benchmark-prefixes = report-sidecar-record-prefixes(
    benchmark-index,
    "roots",
    "scene_id",
  )
  let identity-pattern = regex("^[A-Za-z0-9._:-]+$")
  let benchmark-roots = benchmark-prefixes.map(prefix => (
    scene: report-sidecar-indexed-row-or-none(benchmark-index, prefix + ".scene_id"),
    target: report-sidecar-indexed-row-or-none(benchmark-index, prefix + ".target_id"),
    root: report-sidecar-indexed-row-or-none(benchmark-index, prefix + ".root_id"),
  ))
  let benchmark-roster-valid = benchmark-sidecar != none and expected-attempts != none and benchmark-prefixes.len() == expected-attempts and benchmark-roots.all(root => (
    root.scene != none and root.scene.value_type == "str" and type(root.scene.at("value_text", default: none)) == str and root.scene.value_text.match(identity-pattern) != none,
    root.target != none and root.target.value_type == "str" and type(root.target.at("value_text", default: none)) == str and root.target.value_text.len() > 0,
    root.root != none and root.root.value_type == "str" and type(root.root.at("value_text", default: none)) == str and root.root.value_text.match(identity-pattern) != none,
  ).all(value => value)) and (
    (key: "schema_version", value: candidate-support-benchmark-schema),
    (key: "bundle_role", value: "candidate_support_benchmark_plan"),
    (key: "logical_name", value: candidate-support-benchmark-name),
    (key: "status", value: "confirmatory"),
    (key: "expected_attempts", value: expected-attempts),
  ).all(expected => report-sidecar-indexed-value-matches(
    benchmark-index,
    expected.key,
    expected.value,
  ))
  let prefixes = report-store-record-prefixes(
    report,
    store-id,
    "candidate-support.attempts",
    "scene_id",
  )
  let record-pattern = regex("^candidate-support\\.attempts\\[[0-9]+\\]\\.(scene_id|target_id|root_id|valid_count|minimum_valid_count|passed)$")
  let record-rows = report.tables.facts.rows.filter(row => (
    row.store_id == store-id,
    row.key.match(record-pattern) != none,
  ).all(value => value))
  let attempts = prefixes.map(prefix => (
    scene: report-store-indexed-row-or-none(fact-index, store-id, prefix + ".scene_id"),
    target: report-store-indexed-row-or-none(fact-index, store-id, prefix + ".target_id"),
    root: report-store-indexed-row-or-none(fact-index, store-id, prefix + ".root_id"),
    valid: report-store-indexed-row-or-none(fact-index, store-id, prefix + ".valid_count"),
    minimum: report-store-indexed-row-or-none(fact-index, store-id, prefix + ".minimum_valid_count"),
    passed: report-store-indexed-row-or-none(fact-index, store-id, prefix + ".passed"),
  ))
  let attempt-count = attempts.len()
  let records-valid = attempt-count > 0 and record-rows.len() == attempt-count * 6 and attempts.all(attempt => (
    attempt.values().all(row => row != none),
    attempt.values().all(row => row != none and row.n == attempt-count),
    attempt.scene != none and type(attempt.scene.value) == str and attempt.scene.value.match(identity-pattern) != none and attempt.scene.unit == "identity" and attempt.scene.aggregation == "attempt_identity",
    attempt.target != none and type(attempt.target.value) == str and attempt.target.value.len() > 0 and attempt.target.unit == "identity" and attempt.target.aggregation == "attempt_identity",
    attempt.root != none and type(attempt.root.value) == str and attempt.root.value.match(identity-pattern) != none and attempt.root.unit == "identity" and attempt.root.aggregation == "attempt_identity",
    attempt.valid != none and type(attempt.valid.value) == int and attempt.valid.value >= 0 and attempt.valid.unit == "count" and attempt.valid.aggregation == "attempt_count",
    attempt.minimum != none and type(attempt.minimum.value) == int and attempt.minimum.value > 0 and attempt.minimum.unit == "count" and attempt.minimum.aggregation == "attempt_threshold",
    attempt.passed != none and type(attempt.passed.value) == bool and attempt.passed.unit == "bool" and attempt.passed.aggregation == "attempt_outcome",
    attempt.valid != none and type(attempt.valid.value) == int and attempt.minimum != none and type(
      attempt.minimum.value,
    ) == int and attempt.passed != none and type(attempt.passed.value) == bool and attempt.passed.value == (
      attempt.valid.value >= attempt.minimum.value
    ),
  ).all(value => value))
  let record-keys = record-rows.map(row => row.key)
  records-valid and benchmark-roster-valid and expected-attempts != none and type(expected-attempts) == int and expected-attempts == attempt-count and type(scene-count) == int and scene-count > 0 and type(target-count) == int and target-count > 0 and reported-p05 != none and reported-failed-rate != none and store-manifest != none and report-store-fact-values-match(
    report,
    store-id,
    (
      (key: "candidate-support.receipt.schema", value: candidate-support-receipt-schema),
      (key: "candidate-support.receipt.store_manifest_sha256", value: store-manifest),
    ),
  ) and (
    "candidate-support.receipt.benchmark_sha256",
    "candidate-support.receipt.config_sha256",
    "candidate-support.receipt.store_manifest_sha256",
  ).all(key => report-store-fact-is-sha256(report, store-id, key)) and report-store-analysis-sidecar-binds-facts(
    report,
    store-id,
    candidate-support-evidence-facts + ("study.population.scenes", "study.population.targets") + record-keys,
    required-name: candidate-support-receipt-name,
  ) and {
    let identities = attempts.map(
      attempt => attempt.scene.value + "|" + attempt.target.value + "|" + attempt.root.value,
    )
    let benchmark-identities = benchmark-roots.map(root => (
      root.scene.value_text + "|" + root.target.value_text + "|" + root.root.value_text
    ))
    let thresholds = attempts.map(attempt => attempt.minimum.value).dedup()
    let scene-ids = attempts.map(attempt => attempt.scene.value).dedup()
    let target-tasks = attempts.map(
      attempt => attempt.scene.value + "|" + attempt.target.value,
    ).dedup()
    let scene-groups = (:)
    for attempt in attempts {
      let scene-id = attempt.scene.value
      let group = scene-groups.at(scene-id, default: ())
      group.push(attempt)
      scene-groups.insert(scene-id, group)
    }
    let scene-means = scene-ids.map(scene-id => {
      let rows = scene-groups.at(scene-id)
      rows.map(attempt => attempt.valid.value).sum() / rows.len()
    })
    let scene-failed-rates = scene-ids.map(scene-id => {
      let rows = scene-groups.at(scene-id)
      rows.filter(attempt => not attempt.passed.value).len() / rows.len()
    })
    let ordered-means = scene-means.sorted()
    let p05-index = calc.ceil(0.05 * ordered-means.len()) - 1
    let derived-p05 = ordered-means.at(p05-index)
    let derived-failed-rate = scene-failed-rates.sum() / scene-failed-rates.len()
    identities.sorted().dedup().len() == identities.len() and benchmark-identities.sorted().dedup().len() == benchmark-identities.len() and identities.sorted() == benchmark-identities.sorted() and thresholds.len() == 1 and scene-ids.len() == scene-count and target-tasks.len() == target-count and calc.abs(
      reported-p05 - derived-p05,
    ) <= derived-identity-abs-tolerance and calc.abs(
      reported-failed-rate - derived-failed-rate,
    ) <= derived-identity-abs-tolerance
  }
}

#let report-store-measurement-protocol-receipt-valid(report, store-id) = {
  let fact-index = report-store-fact-index(report)
  let repeat-count = report-store-number-value(
    report,
    store-id,
    "oracle.metric.repeatability.n_repeats",
  )
  let reported-max-diff = report-store-number-value(
    report,
    store-id,
    "oracle.metric.repeatability.max_abs_diff",
  )
  let measurement-unit-count = report-store-number-value(
    report,
    store-id,
    "oracle.metric.repeatability.n_measurement_units",
  )
  let reported-ranking-agreement = report-store-boolean-value(
    report,
    store-id,
    "oracle.metric.repeatability.ranking_agreement",
  )
  let protocol-id-row = report-store-indexed-row-or-none(
    fact-index,
    store-id,
    "oracle.metric.protocol.id",
  )
  let protocol-config-row = report-store-indexed-row-or-none(
    fact-index,
    store-id,
    "oracle.metric.protocol.config_sha256",
  )
  let benchmark-row = report-store-indexed-row-or-none(
    fact-index,
    store-id,
    "oracle.metric.protocol.benchmark_sha256",
  )
  let benchmark-digest = if benchmark-row != none and report-sha256-value-valid(
    benchmark-row.value,
  ) { benchmark-row.value } else { "" }
  let benchmark-sidecar = report-confirmatory-sidecar-by-digest(
    report,
    benchmark-digest,
    required-name: measurement-benchmark-name,
  )
  let benchmark-index = report-sidecar-value-index(
    report,
    if benchmark-sidecar == none { "" } else { benchmark-sidecar.sidecar_id },
  )
  let benchmark-prefixes = report-sidecar-record-prefixes(
    benchmark-index,
    "units",
    "measurement_id",
  )
  let benchmark-repeat-prefixes = report-sidecar-record-prefixes(
    benchmark-index,
    "repeats",
    "repeat_id",
  )
  let identity-pattern = regex("^[A-Za-z0-9._:-]+$")
  let benchmark-units = benchmark-prefixes.map(prefix => (
    measurement: report-sidecar-indexed-row-or-none(
      benchmark-index,
      prefix + ".measurement_id",
    ),
    group: report-sidecar-indexed-row-or-none(
      benchmark-index,
      prefix + ".ranking_group_id",
    ),
  ))
  let benchmark-repeats = benchmark-repeat-prefixes.map(prefix => report-sidecar-indexed-row-or-none(
    benchmark-index,
    prefix + ".repeat_id",
  ))
  let benchmark-roster-valid = benchmark-sidecar != none and repeat-count != none and measurement-unit-count != none and benchmark-prefixes.len() == measurement-unit-count and benchmark-repeat-prefixes.len() == repeat-count and benchmark-repeats.all(row => row != none and row.value_type == "str" and type(row.at("value_text", default: none)) == str and row.value_text.match(identity-pattern) != none) and benchmark-units.all(unit => (
    unit.measurement != none and unit.measurement.value_type == "str" and type(unit.measurement.at("value_text", default: none)) == str and unit.measurement.value_text.match(identity-pattern) != none,
    unit.group != none and unit.group.value_type == "str" and type(unit.group.at("value_text", default: none)) == str and unit.group.value_text.match(identity-pattern) != none,
  ).all(value => value)) and (
    (key: "schema_version", value: measurement-benchmark-schema),
    (key: "bundle_role", value: "oracle_measurement_benchmark_plan"),
    (key: "logical_name", value: measurement-benchmark-name),
    (key: "status", value: "confirmatory"),
    (key: "expected_repeats", value: repeat-count),
    (key: "expected_measurement_units", value: measurement-unit-count),
    (key: "rank_direction", value: measurement-rank-direction),
    (key: "rank_tie_policy", value: measurement-rank-tie-policy),
  ).all(expected => report-sidecar-indexed-value-matches(
    benchmark-index,
    expected.key,
    expected.value,
  ))
  let store-manifest = report-store-manifest-sha256(report, store-id)
  let prefixes = report-store-record-prefixes(
    report,
    store-id,
    "oracle.metric.observations",
    "repeat_id",
  )
  let record-pattern = regex("^oracle\\.metric\\.observations\\[[0-9]+\\]\\.(repeat_id|measurement_id|ranking_group_id|input_sha256|artifact_sha256|protocol_id|protocol_config_sha256|root_normalized_gain)$")
  let record-rows = report.tables.facts.rows.filter(row => (
    row.store_id == store-id,
    row.key.match(record-pattern) != none,
  ).all(value => value))
  let observations = prefixes.map(prefix => (
    repeat: report-store-indexed-row-or-none(fact-index, store-id, prefix + ".repeat_id"),
    measurement: report-store-indexed-row-or-none(fact-index, store-id, prefix + ".measurement_id"),
    group: report-store-indexed-row-or-none(fact-index, store-id, prefix + ".ranking_group_id"),
    input: report-store-indexed-row-or-none(fact-index, store-id, prefix + ".input_sha256"),
    artifact: report-store-indexed-row-or-none(fact-index, store-id, prefix + ".artifact_sha256"),
    protocol: report-store-indexed-row-or-none(fact-index, store-id, prefix + ".protocol_id"),
    config: report-store-indexed-row-or-none(fact-index, store-id, prefix + ".protocol_config_sha256"),
    gain: report-store-indexed-row-or-none(fact-index, store-id, prefix + ".root_normalized_gain"),
  ))
  let observation-count = observations.len()
  let records-valid = benchmark-roster-valid and repeat-count != none and measurement-unit-count != none and repeat-count >= 2 and measurement-unit-count >= 1 and observation-count == repeat-count * measurement-unit-count and record-rows.len() == observation-count * 8 and protocol-id-row != none and protocol-config-row != none and observations.all(observation => (
    observation.values().all(row => row != none and row.n == observation-count),
    observation.repeat != none and type(observation.repeat.value) == str and observation.repeat.value.match(identity-pattern) != none and observation.repeat.unit == "identity" and observation.repeat.aggregation == "repeat_identity",
    observation.measurement != none and type(observation.measurement.value) == str and observation.measurement.value.match(identity-pattern) != none and observation.measurement.unit == "identity" and observation.measurement.aggregation == "measurement_identity",
    observation.group != none and type(observation.group.value) == str and observation.group.value.match(identity-pattern) != none and observation.group.unit == "identity" and observation.group.aggregation == "ranking_group_identity",
    observation.input != none and report-sha256-value-valid(observation.input.value) and observation.input.unit == "sha256" and observation.input.aggregation == "measurement_input_sha256",
    observation.artifact != none and report-sha256-value-valid(observation.artifact.value) and observation.artifact.unit == "sha256" and observation.artifact.aggregation == "measurement_output_sha256",
    observation.protocol != none and observation.protocol.value == protocol-id-row.value and observation.protocol.unit == "identity" and observation.protocol.aggregation == "protocol_identity",
    observation.config != none and observation.config.value == protocol-config-row.value and observation.config.unit == "sha256" and observation.config.aggregation == "protocol_binding_sha256",
    observation.gain != none and report-value-is-finite-float32(observation.gain.value) and observation.gain.value <= 1 and observation.gain.unit == "fraction" and observation.gain.aggregation == "matched_unit_measurement",
  ).all(value => value))
  let record-keys = record-rows.map(row => row.key)
  records-valid and reported-max-diff != none and reported-ranking-agreement != none and store-manifest != none and type(protocol-id-row.value) == str and protocol-id-row.value.match(identity-pattern) != none and report-store-fact-values-match(
    report,
    store-id,
    (
      (key: "oracle.metric.protocol.receipt_schema", value: measurement-protocol-receipt-schema),
      (key: "oracle.metric.protocol.store_manifest_sha256", value: store-manifest),
      (key: "oracle.metric.protocol.rank_direction", value: measurement-rank-direction),
      (key: "oracle.metric.protocol.rank_tie_policy", value: measurement-rank-tie-policy),
    ),
  ) and (
    "oracle.metric.protocol.benchmark_sha256",
    "oracle.metric.protocol.config_sha256",
    "oracle.metric.protocol.store_manifest_sha256",
  ).all(key => report-store-fact-is-sha256(report, store-id, key)) and report-store-analysis-sidecar-binds-facts(
    report,
    store-id,
    measurement-evidence-facts + record-keys,
    required-name: measurement-protocol-receipt-name,
  ) and {
    let benchmark-identities = benchmark-units.map(unit => (
      unit.measurement.value_text + "|" + unit.group.value_text
    ))
    let benchmark-repeat-identities = benchmark-repeats.map(row => row.value_text)
    let record-identities = observations.map(observation => (
      observation.repeat.value + "|" + observation.measurement.value
    ))
    let repeat-ids = observations.map(observation => observation.repeat.value).dedup()
    let repeat-groups = (:)
    let measurement-groups = (:)
    let artifact-groups = (:)
    let ranking-groups = (:)
    for observation in observations {
      let repeat-key = observation.repeat.value
      let repeat-rows = repeat-groups.at(repeat-key, default: ())
      repeat-rows.push(observation)
      repeat-groups.insert(repeat-key, repeat-rows)
      let measurement-key = observation.measurement.value
      let measurement-rows = measurement-groups.at(measurement-key, default: ())
      measurement-rows.push(observation)
      measurement-groups.insert(measurement-key, measurement-rows)
      let artifact-key = observation.artifact.value
      let artifact-rows = artifact-groups.at(artifact-key, default: ())
      artifact-rows.push(observation)
      artifact-groups.insert(artifact-key, artifact-rows)
      let ranking-key = repeat-key + "|" + observation.group.value
      let ranking-rows = ranking-groups.at(ranking-key, default: ())
      ranking-rows.push(observation)
      ranking-groups.insert(ranking-key, ranking-rows)
    }
    let rectangular = repeat-ids.sorted().dedup().len() == repeat-ids.len() and benchmark-repeat-identities.sorted().dedup().len() == benchmark-repeat-identities.len() and repeat-ids.sorted() == benchmark-repeat-identities.sorted() and repeat-groups.values().all(group => {
      let identities = group.map(
        observation => observation.measurement.value + "|" + observation.group.value,
      )
      group.len() == measurement-unit-count and identities.sorted().dedup().len() == identities.len() and identities.sorted() == benchmark-identities.sorted()
    }) and measurement-groups.len() == measurement-unit-count and measurement-groups.values().all(
      group => group.len() == repeat-count,
    )
    let inputs-stable = measurement-groups.values().all(
      group => group.map(observation => observation.input.value).dedup().len() == 1,
    )
    let derived-ranks = (:)
    for (ranking-key, group) in ranking-groups.pairs() {
      let gain-counts = (:)
      for observation in group {
        let gain-key = str(observation.gain.value)
        gain-counts.insert(
          gain-key,
          gain-counts.at(gain-key, default: 0) + 1,
        )
      }
      let ordered-gains = group.map(
        observation => observation.gain.value,
      ).sorted().dedup()
      let below-count = 0
      for gain in ordered-gains {
        let gain-key = str(gain)
        let equal-count = gain-counts.at(gain-key)
        let rank = group.len() - below-count - equal-count + 1
        derived-ranks.insert(ranking-key + "|" + gain-key, rank)
        below-count += equal-count
      }
    }
    let ranking-agreement = measurement-groups.values().all(group => group.map(
      observation => derived-ranks.at(
        observation.repeat.value + "|" + observation.group.value + "|" + str(
          observation.gain.value,
        ),
      ),
    ).dedup().len() == 1)
    let unit-ranges = measurement-groups.values().map(group => {
      let values = group.map(observation => observation.gain.value).sorted()
      values.last() - values.first()
    }).sorted()
    let artifact-consistent = artifact-groups.values().all(rows => (
      rows.map(observation => observation.measurement.value).dedup().len() == 1 and rows.map(
        observation => observation.gain.value,
      ).dedup().len() == 1
    ))
    benchmark-identities.sorted().dedup().len() == benchmark-identities.len() and record-identities.sorted().dedup().len() == record-identities.len() and rectangular and inputs-stable and artifact-consistent and reported-ranking-agreement == ranking-agreement and calc.abs(
      reported-max-diff - unit-ranges.last(),
    ) <= derived-identity-abs-tolerance
  }
}

#let report-store-candidate-support-evidence-valid(report, store-id) = {
  let support-p05 = report-store-number-value(report, store-id, "candidate-support.valid-support-p05")
  let failed-root-rate = report-store-number-value(report, store-id, "candidate-support.failed-root-rate")
  let support-minimum = report-store-number-value(report, store-id, "candidate-support.valid-support-p05.minimum")
  let failed-root-maximum = report-store-number-value(report, store-id, "candidate-support.failed-root-rate.maximum")
  let passed = report-store-boolean-value(report, store-id, "candidate-support.gate.passed")
  report-store-gated-family-valid(
    report,
    store-id,
    candidate-support-evidence-facts,
    candidate-support-evidence-contract,
    "study.population.scenes",
  ) and report-store-candidate-support-receipt-valid(
    report,
    store-id,
  ) and report-store-fact-values-match(
    report,
    store-id,
    ((key: "candidate-support.gate.rule", value: candidate-support-decision-rule),),
  ) and (support-p05, failed-root-rate, support-minimum, failed-root-maximum).all(
    value => value != none,
  ) and support-minimum > 0 and failed-root-maximum < 1 and passed != none and passed == (
    support-p05 >= support-minimum and failed-root-rate <= failed-root-maximum
  )
}

#let report-store-population-evidence-valid(report, store-id) = {
  report-store-gated-family-valid(
    report,
    store-id,
    population-evidence-facts,
    population-evidence-contract,
    "study.population.scenes",
  )
}

#let report-store-measurement-evidence-valid(report, store-id) = {
  let max-abs-diff = report-store-number-value(
    report,
    store-id,
    "oracle.metric.repeatability.max_abs_diff",
  )
  let tolerance = report-store-number-value(
    report,
    store-id,
    "oracle.metric.repeatability.tolerance",
  )
  let ranking-agreement = report-store-boolean-value(
    report,
    store-id,
    "oracle.metric.repeatability.ranking_agreement",
  )
  let passed-matches = report.tables.facts.rows.filter(
    row => row.store_id == store-id and row.key == "oracle.metric.repeatability.passed",
  )
  report-store-gated-family-valid(
    report,
    store-id,
    measurement-evidence-facts,
    measurement-evidence-contract,
    "oracle.metric.repeatability.n_repeats",
  ) and report-store-measurement-protocol-receipt-valid(
    report,
    store-id,
  ) and report-store-fact-values-match(
    report,
    store-id,
    ((key: "oracle.metric.repeatability.rule", value: repeatability-decision-rule),),
  ) and max-abs-diff != none and tolerance != none and ranking-agreement != none and passed-matches.len() == 1 and passed-matches.first().value == (
    max-abs-diff <= tolerance and ranking-agreement
  )
}

#let report-store-q1-protocol-audit-valid(report, store-id) = {
  let fact-index = report-store-fact-index(report)
  let receipt-row = report-store-indexed-row-or-none(
    fact-index,
    store-id,
    "q1.protocol.audit_receipt_sha256",
  )
  let receipt-digest = if receipt-row != none and report-sha256-value-valid(
    receipt-row.value,
  ) { receipt-row.value } else { "" }
  let receipt-sidecar = report-confirmatory-sidecar-by-digest(
    report,
    receipt-digest,
    required-name: q1-protocol-receipt-name,
  )
  if receipt-sidecar == none { return false }
  let index = report-sidecar-value-index(report, receipt-sidecar.sidecar_id)
  let value(key) = report-sidecar-indexed-value-or-none(index, key)
  let store-manifest = report-store-manifest-sha256(report, store-id)
  let bundle-manifest = report-store-indexed-row-or-none(
    fact-index,
    store-id,
    "q1.model.bundle_manifest_sha256",
  )
  let declared-scenes = report-store-number-value(
    report,
    store-id,
    "q1.population.n_scenes",
  )
  let reported-ranking = report-store-number-value(
    report,
    store-id,
    "q1.ranking.pairwise_accuracy",
  )
  let reported-ranking-ci-low = report-store-number-value(
    report,
    store-id,
    "q1.ranking.pairwise_accuracy.ci_low",
  )
  let reported-ranking-ci-high = report-store-number-value(
    report,
    store-id,
    "q1.ranking.pairwise_accuracy.ci_high",
  )
  let reported-calibration = report-store-number-value(
    report,
    store-id,
    "q1.calibration.mae",
  )
  let manifest-rows = index.rows.values().filter(
    row => row.key.match(regex("^bound_contract\\.ordered_test_store_manifests\\[[0-9]+\\]$")) != none,
  ).sorted(key: row => row.key)
  let manifests = manifest-rows.map(report-sidecar-row-value-or-none)
  let report-store-rows = report.tables.stores.rows
  let report-store-ids = report-store-rows.map(row => row.store_id)
  let report-manifests = report-store-rows.map(row => row.manifest_sha256)
  let current-store-index = manifests.position(manifest => manifest == store-manifest)
  let bundle-sidecar = if bundle-manifest != none and report-sha256-value-valid(
    bundle-manifest.value,
  ) {
    report-confirmatory-sidecar-by-embedded-digest(
      report,
      bundle-manifest.value,
      "manifest_sha256",
      required-name: q1-bundle-manifest-name,
    )
  } else { none }
  let bundle-index = report-sidecar-value-index(
    report,
    if bundle-sidecar == none { "" } else { bundle-sidecar.sidecar_id },
  )
  let bundle-value(key) = report-sidecar-indexed-value-or-none(bundle-index, key)
  let bundle-manifest-rows = bundle-index.rows.values().filter(
    row => row.key.match(regex("^identity\\.ordered_store_manifests\\.test\\[[0-9]+\\]$")) != none,
  ).sorted(key: row => row.key)
  let bundle-manifests = bundle-manifest-rows.map(report-sidecar-row-value-or-none)
  let frozen-population-digest = bundle-value("identity.dataset_payload_sha256s.test")
  let frozen-provenance-digest = bundle-value("identity.dataset_provenance_payload_sha256s.test")
  let population-benchmark-digest = value("population_benchmark_sha256")
  let header-valid = bundle-manifest != none and report-sha256-value-valid(
    bundle-manifest.value,
  ) and bundle-sidecar != none and report-sha256-value-valid(
    frozen-population-digest,
  ) and report-sha256-value-valid(frozen-provenance-digest) and bundle-manifests == manifests and value("schema_version") == q1-protocol-receipt-schema and value(
    "bundle_manifest_sha256",
  ) == bundle-manifest.value and value("test_population_sha256") == frozen-population-digest and value(
    "test_provenance_sha256",
  ) == frozen-provenance-digest and report-sha256-value-valid(population-benchmark-digest) and (
    "actor_manifest_payload_sha256",
    "implementation_contract_payload_sha256",
    "actor_state_contract_payload_sha256",
    "learning_contract_payload_sha256",
  ).all(key => report-sha256-value-valid(value("bound_contract." + key))) and value(
    "target_protocol",
  ) == q1-audit-target-protocol and value(
    "experiment_profile",
  ) == q1-audit-experiment-profile and value(
    "selected_observation_protocol",
  ) == q1-audit-selected-observation-protocol and value(
    "action_mask_semantics",
  ) == q1-audit-action-mask-semantics and value(
    "actor_input_manifest_schema",
  ) == q1-audit-actor-input-manifest-schema and value(
    "metric_contract.prediction_semantics",
  ) == q1-audit-prediction-semantics and value(
    "metric_contract.label_semantics",
  ) == q1-audit-label-semantics and value(
    "metric_contract.ranking_pair_policy",
  ) == q1-audit-ranking-pair-policy and value(
    "metric_contract.calibration_aggregation",
  ) == q1-audit-calibration-aggregation and value(
    "metric_contract.independent_unit_semantics",
  ) == q1-audit-independent-unit-semantics and value(
    "metric_contract.interval_method",
  ) == q1-ranking-interval-method and manifests.len() > 0 and manifests.all(
    report-sha256-value-valid,
  ) and manifests.dedup().len() == manifests.len() and report-store-ids.len() == report-store-ids.dedup().len() and report-manifests.len() > 0 and report-manifests.all(
    report-sha256-value-valid,
  ) and report-manifests.dedup().len() == report-manifests.len() and manifests.sorted() == report-manifests.sorted() and current-store-index != none
  if not header-valid { return false }

  // The content-addressed benchmark owns the expected roster independently of
  // the observed audit receipt. The audit header binds it by digest.
  let benchmark-sidecar = report-confirmatory-sidecar-by-digest(
    report,
    population-benchmark-digest,
    required-name: q1-population-benchmark-name,
  )
  if benchmark-sidecar == none { return false }
  let benchmark-index = report-sidecar-value-index(report, benchmark-sidecar.sidecar_id)
  let benchmark-value(key) = report-sidecar-indexed-value-or-none(benchmark-index, key)
  let benchmark-manifest-rows = benchmark-index.rows.values().filter(
    row => row.key.match(regex("^ordered_test_store_manifests\\[[0-9]+\\]$")) != none,
  ).sorted(key: row => row.key)
  let benchmark-manifests = benchmark-manifest-rows.map(report-sidecar-row-value-or-none)
  let benchmark-header-valid = benchmark-value(
    "schema_version",
  ) == q1-population-benchmark-schema and benchmark-value(
    "bundle_role",
  ) == "q1_population_benchmark" and benchmark-value(
    "logical_name",
  ) == q1-population-benchmark-name and benchmark-value(
    "status",
  ) == "confirmatory" and benchmark-value(
    "bundle_manifest_sha256",
  ) == bundle-manifest.value and benchmark-value(
    "test_population_sha256",
  ) == frozen-population-digest and benchmark-value(
    "test_provenance_sha256",
  ) == frozen-provenance-digest and benchmark-manifests == bundle-manifests and benchmark-manifests == manifests
  if not benchmark-header-valid { return false }
  let expected-target-prefixes = report-sidecar-record-prefixes(
    benchmark-index,
    "expected_targets",
    "target_row_id",
  )
  let expected-targets = expected-target-prefixes.map(prefix => (
    store: benchmark-value(prefix + ".store_index"),
    scene: benchmark-value(prefix + ".scene_id"),
    row: benchmark-value(prefix + ".target_row_id"),
    id: benchmark-value(prefix + ".target_id"),
    descriptor-hash: benchmark-value(prefix + ".descriptor_hash"),
  ))
  let expected-state-prefixes = report-sidecar-record-prefixes(
    benchmark-index,
    "expected_states",
    "step_row_id",
  )
  let expected-states = expected-state-prefixes.map(prefix => (
    store: benchmark-value(prefix + ".store_index"),
    scene: benchmark-value(prefix + ".scene_id"),
    rollout: benchmark-value(prefix + ".rollout_row_id"),
    step-row: benchmark-value(prefix + ".step_row_id"),
    step: benchmark-value(prefix + ".step_index"),
    target-row: benchmark-value(prefix + ".target_row_id"),
    candidate-width: benchmark-value(prefix + ".candidate_width"),
    selected-row: benchmark-value(prefix + ".selected_candidate_row_id"),
    candidate-config: benchmark-value(prefix + ".candidate_config_hash"),
    root-observation: benchmark-value(prefix + ".root_observation_evidence_sha256"),
    root-reference-pose: benchmark-value(prefix + ".root_reference_pose_sha256"),
    candidate-pose-shell: benchmark-value(prefix + ".candidate_pose_shell_sha256"),
    actor-action-support: benchmark-value(prefix + ".actor_action_support_sha256"),
    remaining-budget: benchmark-value(prefix + ".remaining_budget"),
  ))
  let expected-candidate-prefixes = report-sidecar-record-prefixes(
    benchmark-index,
    "expected_candidates",
    "candidate_row_id",
  )
  let expected-candidates = expected-candidate-prefixes.map(prefix => (
    store: benchmark-value(prefix + ".store_index"),
    rollout: benchmark-value(prefix + ".rollout_row_id"),
    step-row: benchmark-value(prefix + ".step_row_id"),
    row: benchmark-value(prefix + ".candidate_row_id"),
    index: benchmark-value(prefix + ".candidate_index"),
    action-mask: benchmark-value(prefix + ".actor_action_mask"),
  ))
  let expected-target-identities = expected-targets.map(
    target => (target.store, target.scene, target.row, target.id, target.descriptor-hash).map(str).join("|"),
  ).sorted()
  let expected-state-identities = expected-states.map(state => (
    state.store,
    state.scene,
    state.rollout,
    state.step-row,
    state.step,
    state.target-row,
    state.candidate-width,
    state.selected-row,
    state.candidate-config,
    state.root-observation,
    state.root-reference-pose,
    state.candidate-pose-shell,
    state.actor-action-support,
    state.remaining-budget,
  ).map(str).join("|")).sorted()
  let expected-candidate-identities = if expected-candidates.all(
    candidate => type(candidate.action-mask) == bool,
  ) {
    expected-candidates.map(candidate => (
      candidate.store,
      candidate.rollout,
      candidate.step-row,
      candidate.row,
      candidate.index,
      if candidate.action-mask { "true" } else { "false" },
    ).map(str).join("|")).sorted()
  } else { () }
  let expected-roster-payload = "targets\n" + expected-target-identities.join(
    "\n",
  ) + "\nstates\n" + expected-state-identities.join(
    "\n",
  ) + "\ncandidates\n" + expected-candidate-identities.join("\n")
  let expected-roster-valid = expected-targets.len() > 0 and expected-states.len() > 0 and expected-candidates.len() > 0 and expected-targets.all(target => (
    type(target.store) == int and target.store >= 0 and target.store < manifests.len(),
    type(target.scene) == str and target.scene.len() > 0,
    type(target.row) == int and target.row >= 0,
    type(target.id) == str and target.id.len() > 0,
    report-sha256-value-valid(target.descriptor-hash),
  ).all(check => check)) and expected-states.all(state => (
    type(state.store) == int and state.store >= 0 and state.store < manifests.len(),
    type(state.scene) == str and state.scene.len() > 0,
    type(state.rollout) == int and state.rollout >= 0,
    type(state.step-row) == int and state.step-row >= 0,
    type(state.step) == int and state.step >= 0,
    type(state.target-row) == int and state.target-row >= 0,
    type(state.candidate-width) == int and state.candidate-width >= 1,
    type(state.selected-row) == int and state.selected-row >= 0,
    report-sha256-value-valid(state.candidate-config),
    report-sha256-value-valid(state.root-observation),
    report-sha256-value-valid(state.root-reference-pose),
    report-sha256-value-valid(state.candidate-pose-shell),
    report-sha256-value-valid(state.actor-action-support),
    type(state.remaining-budget) == int and state.remaining-budget >= 1,
  ).all(check => check)) and expected-candidates.all(candidate => (
    type(candidate.store) == int and candidate.store >= 0 and candidate.store < manifests.len(),
    type(candidate.rollout) == int and candidate.rollout >= 0,
    type(candidate.step-row) == int and candidate.step-row >= 0,
    type(candidate.row) == int and candidate.row >= 0,
    type(candidate.index) == int and candidate.index >= 0,
    type(candidate.action-mask) == bool,
  ).all(check => check)) and expected-target-identities.dedup().len() == expected-targets.len() and expected-state-identities.dedup().len() == expected-states.len() and expected-candidate-identities.dedup().len() == expected-candidates.len() and benchmark-value(
    "roster_sha256",
  ) == sha256-hex(expected-roster-payload)
  if not expected-roster-valid { return false }

  let target-prefixes = report-sidecar-record-prefixes(
    index,
    "targets",
    "target_row_id",
  )
  let targets = target-prefixes.map(prefix => (
    prefix: prefix,
    store: value(prefix + ".store_index"),
    scene: value(prefix + ".scene_id"),
    row: value(prefix + ".target_row_id"),
    id: value(prefix + ".target_id"),
    protocol: value(prefix + ".target_protocol"),
    target-source: value(prefix + ".target_source"),
    descriptor-source: value(prefix + ".descriptor_source"),
    descriptor-provenance: value(prefix + ".descriptor_provenance"),
    descriptor-hash: value(prefix + ".descriptor_hash"),
    explicit-hash: value(prefix + ".explicit_target_hash"),
    match-status: value(prefix + ".gt_match_status"),
    matched-row: value(prefix + ".matched_target_row_id"),
    matched-id: value(prefix + ".matched_target_id"),
    match-iou: value(prefix + ".match_iou"),
    target-valid: value(prefix + ".target_valid"),
    label-valid: value(prefix + ".gt_label_valid"),
  ))
  let target-trainable(target) = (
    target.protocol == q1-audit-target-protocol,
    target.target-source == q1-audit-campaign-target-source,
    target.descriptor-source == target.target-source,
    target.descriptor-provenance == q1-audit-campaign-descriptor-provenance,
    report-sha256-value-valid(target.descriptor-hash),
    type(target.explicit-hash) == str and target.explicit-hash.match(regex("^[0-9a-f]{16}$")) != none,
    target.match-status == q1-audit-gt-match-status,
    type(target.matched-row) == int and target.matched-row >= 0,
    type(target.matched-id) == str and target.matched-id.len() > 0,
    report-value-is-finite-float32(target.match-iou) and target.match-iou > 0.20 and target.match-iou <= 1,
    target.target-valid == true,
  ).all(check => check)
  let target-identities = targets.map(
    target => (target.store, target.scene, target.row, target.id, target.descriptor-hash).map(str).join("|"),
  )
  let targets-valid = targets.len() > 0 and targets.all(target => (
    type(target.store) == int and target.store >= 0 and target.store < manifests.len(),
    type(target.scene) == str and target.scene.len() > 0,
    type(target.row) == int and target.row >= 0,
    type(target.id) == str and target.id.len() > 0,
    type(target.target-source) == str and target.target-source.len() > 0,
    type(target.target-valid) == bool,
    type(target.label-valid) == bool and target.label-valid == target-trainable(target),
  ).all(check => check)) and target-identities.dedup().len() == targets.len() and targets.map(
    target => (target.store, target.row).map(str).join("|"),
  ).dedup().len() == targets.len()
  if not targets-valid { return false }
  let target-by-identity = (:)
  for target in targets {
    target-by-identity.insert(str(target.store) + "|" + str(target.row), target)
  }

  let state-prefixes = report-sidecar-record-prefixes(index, "states", "step_row_id")
  let states = state-prefixes.map(prefix => {
    let history-prefixes = index.rows.values().filter(row => (
      row.key.starts-with(prefix + ".history["),
      row.key.ends-with(".history_position"),
    ).all(check => check)).map(
      row => row.key.replace(regex("\\.history_position$"), ""),
    )
    let history = history-prefixes.map(history-prefix => (
      position: value(history-prefix + ".history_position"),
      source-step: value(history-prefix + ".source_step_index"),
      selected-row: value(history-prefix + ".selected_candidate_row_id"),
    )).sorted(key: entry => entry.position)
    let actor-leaf-prefixes = index.rows.values().filter(row => (
      row.key.starts-with(prefix + ".actor_input_leaves["),
      row.key.ends-with(".name"),
    ).all(check => check)).map(row => row.key.replace(regex("\\.name$"), ""))
    let actor-leaves = actor-leaf-prefixes.map(leaf-prefix => (
      name: value(leaf-prefix + ".name"),
      role: value(leaf-prefix + ".role"),
      member-schema-sha256: value(leaf-prefix + ".member_schema_sha256"),
      content-sha256: value(leaf-prefix + ".content_sha256"),
      source-owner: value(leaf-prefix + ".source_owner"),
      source-manifest-sha256: value(leaf-prefix + ".source_manifest_sha256"),
      derivation: value(leaf-prefix + ".derivation"),
      presence: value(leaf-prefix + ".presence"),
    )).sorted(key: leaf => str(leaf.name) + "|" + str(leaf.role) + "|" + str(leaf.derivation))
    (
      prefix: prefix,
      store: value(prefix + ".store_index"),
      scene: value(prefix + ".scene_id"),
      rollout: value(prefix + ".rollout_row_id"),
      step-row: value(prefix + ".step_row_id"),
      step: value(prefix + ".step_index"),
      target-row: value(prefix + ".target_row_id"),
      selected-row: value(prefix + ".selected_candidate_row_id"),
      candidate-config: value(prefix + ".candidate_config_hash"),
      root-observation: value(prefix + ".root_observation_evidence_sha256"),
      root-reference-pose: value(prefix + ".root_reference_pose_sha256"),
      candidate-pose-shell: value(prefix + ".candidate_pose_shell_sha256"),
      actor-action-support: value(prefix + ".actor_action_support_sha256"),
      remaining-budget: value(prefix + ".remaining_budget"),
      actor-payload: value(prefix + ".actor_input_payload_sha256"),
      actor-contract: value(prefix + ".actor_state_contract_payload_sha256"),
      actor-leaves: actor-leaves,
      history: history,
    )
  })
  let state-identities = states.map(
    state => (state.store, state.rollout, state.step-row).map(str).join("|"),
  )
  let states-valid = states.len() > 0 and states.all(state => {
    let target = target-by-identity.at(
      str(state.store) + "|" + str(state.target-row),
      default: none,
    )
    let scalar-fields-valid = target != none and (
      type(state.store) == int and state.store >= 0 and state.store < manifests.len(),
      type(state.scene) == str and state.scene.len() > 0,
      type(state.rollout) == int and state.rollout >= 0,
      type(state.step-row) == int and state.step-row >= 0,
      type(state.step) == int and state.step >= 0,
      type(state.target-row) == int and state.target-row >= 0,
      type(state.selected-row) == int and state.selected-row >= 0,
      report-sha256-value-valid(state.candidate-config),
      report-sha256-value-valid(state.root-observation),
      report-sha256-value-valid(state.root-reference-pose),
      report-sha256-value-valid(state.candidate-pose-shell),
      report-sha256-value-valid(state.actor-action-support),
      type(state.remaining-budget) == int and state.remaining-budget >= 1,
      report-sha256-value-valid(state.actor-payload),
      state.actor-contract == value("bound_contract.actor_state_contract_payload_sha256"),
    ).all(check => check)
    let leaf-presence-valid = state.actor-leaves.all(
      leaf => type(leaf.presence) == bool,
    )
    if not scalar-fields-valid or not leaf-presence-valid { false } else {
      let expected-leaf-identities = q1-audit-actor-input-leaves.map(
        leaf => leaf.name + "|" + leaf.role + "|" + leaf.schema-id + "|" + leaf.source-owner + "|" + leaf.derivation + "|" + if leaf.presence { "true" } else { "false" },
      ).sorted()
      let leaf-identities = state.actor-leaves.map(
        leaf => str(leaf.name) + "|" + str(leaf.role) + "|" + if type(leaf.name) == str {
          let expected = q1-audit-actor-input-leaves.find(spec => spec.name == leaf.name)
          if expected == none { "" } else { expected.schema-id + "|" + expected.source-owner }
        } else { "" } + "|" + str(leaf.derivation) + "|" + if leaf.presence { "true" } else { "false" },
      )
      let actor-payload = state.actor-leaves.map(leaf => (
        leaf.name,
        leaf.role,
        leaf.member-schema-sha256,
        leaf.content-sha256,
        leaf.source-owner,
        leaf.source-manifest-sha256,
        leaf.derivation,
        if leaf.presence { "true" } else { "false" },
      ).map(str).join("|")).join("\n")
      let leaf-by-name = (:)
      for leaf in state.actor-leaves { leaf-by-name.insert(leaf.name, leaf) }
      let target-leaf = leaf-by-name.at("observed_target_descriptor", default: none)
      let root-observation-leaf = leaf-by-name.at("root_observation_evidence", default: none)
      let root-reference-pose-leaf = leaf-by-name.at("root_reference_pose", default: none)
      let candidate-pose-shell-leaf = leaf-by-name.at("candidate_pose_shell", default: none)
      let actor-action-support-leaf = leaf-by-name.at("actor_action_support", default: none)
      let history-leaf = leaf-by-name.at("factual_pose_history", default: none)
      let remaining-budget-leaf = leaf-by-name.at("remaining_budget", default: none)
      let horizon-leaf = leaf-by-name.at("requested_horizon_q1", default: none)
      let absent-prefix-leaf = leaf-by-name.at("selected_observation_prefix_absent", default: none)
      let history-payload = if state.history.len() == 0 { "" } else {
        state.history.map(entry => (
          entry.position,
          entry.source-step,
          entry.selected-row,
        ).map(str).join("|")).join("\n")
      }
      let expected-history-content = sha256-hex(history-payload)
      let leaves-exact = state.actor-leaves.all(leaf => if type(leaf.name) == str {
        let expected = q1-audit-actor-input-leaves.find(spec => spec.name == leaf.name)
        if expected == none { false } else {
          let expected-source = if expected.source-owner == "actor_manifest" {
            value("bound_contract.actor_manifest_payload_sha256")
          } else if expected.source-owner == "rollout_manifest" {
            manifests.at(state.store)
          } else if expected.source-owner == "implementation_contract" {
            value("bound_contract.implementation_contract_payload_sha256")
          } else if expected.source-owner == "actor_state_contract" {
            value("bound_contract.actor_state_contract_payload_sha256")
          } else { none }
          leaf.member-schema-sha256 == sha256-hex(expected.schema-id) and leaf.source-owner == expected.source-owner and leaf.source-manifest-sha256 == expected-source and report-sha256-value-valid(leaf.content-sha256)
        }
      } else { false })
      target.scene == state.scene and state.history.len() == state.step and state.history.map(
        entry => entry.position,
      ) == range(state.step) and state.history.all(entry => (
        type(entry.source-step) == int and entry.source-step == entry.position,
        type(entry.selected-row) == int and entry.selected-row >= 0,
      ).all(check => check)) and state.actor-leaves.len() == q1-audit-actor-input-leaves.len() and leaf-identities == expected-leaf-identities and leaves-exact and root-observation-leaf != none and root-observation-leaf.content-sha256 == state.root-observation and root-reference-pose-leaf != none and root-reference-pose-leaf.content-sha256 == state.root-reference-pose and target-leaf != none and target-leaf.content-sha256 == target.descriptor-hash and candidate-pose-shell-leaf != none and candidate-pose-shell-leaf.content-sha256 == state.candidate-pose-shell and actor-action-support-leaf != none and actor-action-support-leaf.content-sha256 == state.actor-action-support and history-leaf != none and history-leaf.content-sha256 == expected-history-content and remaining-budget-leaf != none and remaining-budget-leaf.content-sha256 == sha256-hex(str(state.remaining-budget)) and horizon-leaf != none and horizon-leaf.content-sha256 == sha256-hex("1") and absent-prefix-leaf != none and absent-prefix-leaf.content-sha256 == sha256-hex("absent") and state.actor-payload == sha256-hex(actor-payload)
    }
  }) and state-identities.dedup().len() == states.len()
  if not states-valid { return false }
  let state-chain-groups = (:)
  for state in states {
    let chain-key = (state.store, state.rollout).map(str).join("|")
    state-chain-groups.insert(
      chain-key,
      state-chain-groups.at(chain-key, default: ()) + (state,),
    )
  }
  let fixed-chain-states-valid = state-chain-groups.values().all(chain => {
    let ordered = chain.sorted(key: state => state.step)
    (
      ordered.map(state => state.step) == range(ordered.len()),
      chain.map(state => state.scene).dedup().len() == 1,
      chain.map(state => state.target-row).dedup().len() == 1,
      chain.map(state => state.candidate-config).dedup().len() == 1,
      chain.map(state => state.root-observation).dedup().len() == 1,
      chain.map(state => state.root-reference-pose).dedup().len() == 1,
      ordered.map(state => state.remaining-budget + state.step).dedup().len() == 1,
      chain.map(state => state.step-row).dedup().len() == chain.len(),
    ).all(check => check)
  })
  if not fixed-chain-states-valid { return false }
  let state-by-step = (:)
  let state-by-row = (:)
  for state in states {
    state-by-step.insert((state.store, state.rollout, state.step).map(str).join("|"), state)
    state-by-row.insert((state.store, state.rollout, state.step-row).map(str).join("|"), state)
  }
  let causal-history-only = states.all(state => state.history.all(entry => {
    let prior = state-by-step.at(
      (state.store, state.rollout, entry.source-step).map(str).join("|"),
      default: none,
    )
    prior != none and prior.scene == state.scene and prior.target-row == state.target-row and prior.candidate-config == state.candidate-config and entry.source-step < state.step and entry.selected-row == prior.selected-row
  }))

  let candidate-prefixes = report-sidecar-record-prefixes(
    index,
    "candidates",
    "candidate_row_id",
  )
  let candidates = candidate-prefixes.map(prefix => (
    prefix: prefix,
    store: value(prefix + ".store_index"),
    rollout: value(prefix + ".rollout_row_id"),
    step-row: value(prefix + ".step_row_id"),
    row: value(prefix + ".candidate_row_id"),
    index: value(prefix + ".candidate_index"),
    action-mask: value(prefix + ".actor_action_mask"),
    label-mask: value(prefix + ".oracle_label_mask"),
    q-train-mask: value(prefix + ".q_train_mask"),
    prediction-row: report-sidecar-indexed-row-or-none(index, prefix + ".prediction"),
    label-row: report-sidecar-indexed-row-or-none(index, prefix + ".label"),
    prediction: value(prefix + ".prediction"),
    label: value(prefix + ".label"),
    prediction-finite: value(prefix + ".prediction_finite"),
    label-finite: value(prefix + ".label_finite"),
    included: value(prefix + ".included_in_q1_metric"),
  ))
  let candidate-identities = candidates.map(
    candidate => (candidate.store, candidate.rollout, candidate.step-row, candidate.row).map(str).join("|"),
  )
  let candidates-valid = candidates.len() > 0 and candidates.all(candidate => {
    let state = state-by-row.at(
      (candidate.store, candidate.rollout, candidate.step-row).map(str).join("|"),
      default: none,
    )
    let prediction-finite = report-value-is-finite-float32(candidate.prediction)
    let label-finite = report-value-is-finite-float32(candidate.label)
    state != none and (
      type(candidate.store) == int and candidate.store >= 0 and candidate.store < manifests.len(),
      type(candidate.rollout) == int and candidate.rollout >= 0,
      type(candidate.step-row) == int and candidate.step-row >= 0,
      type(candidate.row) == int and candidate.row >= 0,
      type(candidate.index) == int and candidate.index >= 0,
      type(candidate.action-mask) == bool,
      type(candidate.label-mask) == bool,
      type(candidate.q-train-mask) == bool and candidate.q-train-mask == (candidate.action-mask and candidate.label-mask),
      candidate.prediction-row != none,
      candidate.label-row != none,
      candidate.prediction == none or report-value-matches-kind(candidate.prediction, "number"),
      candidate.label == none or (
        report-value-matches-kind(candidate.label, "number") and (
          not label-finite or candidate.label <= 1
        )
      ),
      type(candidate.prediction-finite) == bool and candidate.prediction-finite == prediction-finite,
      type(candidate.label-finite) == bool and candidate.label-finite == label-finite,
      not candidate.q-train-mask or (prediction-finite and label-finite),
      type(candidate.included) == bool and candidate.included == (
        candidate.q-train-mask and candidate.prediction-finite and candidate.label-finite
      ),
    ).all(check => check)
  }) and candidate-identities.dedup().len() == candidates.len()
  if not candidates-valid { return false }

  // Reconstruct both Q1 estimands from the content-addressed candidate rows.
  // Ranking is macro-averaged within state and then scene; calibration follows
  // the same state-then-scene weighting. Equal oracle labels are not ranking
  // comparisons, and a prediction tie is incorrect for a strict label order.
  let state-metrics = states.map(state => {
    let included = candidates.filter(candidate => (
      candidate.store == state.store,
      candidate.rollout == state.rollout,
      candidate.step-row == state.step-row,
      candidate.included,
    ).all(check => check)).sorted(key: candidate => candidate.index)
    let pair-scores = ()
    for left-index in range(included.len()) {
      for right-index in range(left-index + 1, included.len()) {
        let left = included.at(left-index)
        let right = included.at(right-index)
        if left.label != right.label {
          let correct = if left.label > right.label {
            left.prediction > right.prediction
          } else {
            left.prediction < right.prediction
          }
          pair-scores.push(if correct { 1.0 } else { 0.0 })
        }
      }
    }
    if included.len() == 0 {
      none
    } else {
      (
        scene-key: state.scene,
        ranking: if pair-scores.len() == 0 { none } else {
          pair-scores.sum() / pair-scores.len()
        },
        calibration: included.map(
          candidate => calc.abs(candidate.prediction - candidate.label),
        ).sum() / included.len(),
      )
    }
  })
  if state-metrics.any(metric => metric == none) { return false }
  let scene-groups = (:)
  for metric in state-metrics {
    scene-groups.insert(
      metric.scene-key,
      scene-groups.at(metric.scene-key, default: ()) + (metric,),
    )
  }
  let scene-keys = scene-groups.keys().sorted()
  if scene-keys.len() < 2 { return false }
  let scene-rankings = scene-keys.map(scene-key => {
    let group = scene-groups.at(scene-key)
    let supported = group.filter(metric => metric.ranking != none)
    if supported.len() == 0 { none } else {
      supported.map(metric => metric.ranking).sum() / supported.len()
    }
  })
  if scene-rankings.any(score => score == none) { return false }
  let scene-calibrations = scene-keys.map(scene-key => {
    let group = scene-groups.at(scene-key)
    group.map(metric => metric.calibration).sum() / group.len()
  })
  let derived-ranking = scene-rankings.sum() / scene-rankings.len()
  let derived-calibration = scene-calibrations.sum() / scene-calibrations.len()
  let leave-one-scene-out = range(scene-rankings.len()).map(omitted-index => {
    let subtotal = 0.0
    for (scene-index, score) in scene-rankings.enumerate() {
      if scene-index != omitted-index { subtotal += score }
    }
    subtotal / (scene-rankings.len() - 1)
  })
  let jackknife-centre = leave-one-scene-out.sum() / leave-one-scene-out.len()
  let jackknife-se = calc.sqrt(
    (scene-rankings.len() - 1) / scene-rankings.len() * leave-one-scene-out.map(
      value => calc.pow(value - jackknife-centre, 2),
    ).sum(),
  )
  let normal-95 = 1.959963984540054
  let derived-ranking-ci-low = calc.max(0.0, derived-ranking - normal-95 * jackknife-se)
  let derived-ranking-ci-high = calc.min(1.0, derived-ranking + normal-95 * jackknife-se)
  let derived-metrics-valid = (
    declared-scenes == scene-keys.len(),
    reported-ranking != none and calc.abs(reported-ranking - derived-ranking) <= derived-identity-abs-tolerance,
    reported-ranking-ci-low != none and calc.abs(reported-ranking-ci-low - derived-ranking-ci-low) <= derived-identity-abs-tolerance,
    reported-ranking-ci-high != none and calc.abs(reported-ranking-ci-high - derived-ranking-ci-high) <= derived-identity-abs-tolerance,
    reported-calibration != none and calc.abs(reported-calibration - derived-calibration) <= derived-identity-abs-tolerance,
  ).all(check => check)
  if not derived-metrics-valid { return false }

  let measured-state-identities = states.map(state => {
    let roster = candidates.filter(candidate => (
      candidate.store == state.store,
      candidate.rollout == state.rollout,
      candidate.step-row == state.step-row,
    ).all(check => check))
    (
      state.store,
      state.scene,
      state.rollout,
      state.step-row,
      state.step,
      state.target-row,
      roster.len(),
      state.selected-row,
      state.candidate-config,
      state.root-observation,
      state.root-reference-pose,
      state.candidate-pose-shell,
      state.actor-action-support,
      state.remaining-budget,
    ).map(str).join("|")
  }).sorted()
  let measured-candidate-identities = candidates.map(candidate => (
    candidate.store,
    candidate.rollout,
    candidate.step-row,
    candidate.row,
    candidate.index,
    if candidate.action-mask { "true" } else { "false" },
  ).map(str).join("|")).sorted()
  let state-candidate-roster-valid = states.all(state => {
    let roster = candidates.filter(candidate => (
      candidate.store == state.store,
      candidate.rollout == state.rollout,
      candidate.step-row == state.step-row,
    ).all(check => check))
    let selected = roster.filter(candidate => candidate.row == state.selected-row)
    let expected-state = expected-states.filter(expected => (
      expected.store == state.store,
      expected.rollout == state.rollout,
      expected.step-row == state.step-row,
    ).all(check => check))
    let expected-candidate-roster = expected-candidates.filter(candidate => (
      candidate.store == state.store,
      candidate.rollout == state.rollout,
      candidate.step-row == state.step-row,
    ).all(check => check))
    expected-state.len() == 1 and {
      let width = expected-state.first().candidate-width
      let expected = expected-state.first()
      let support-payload = roster.sorted(key: candidate => candidate.index).map(
        candidate => str(candidate.index) + "|" + if candidate.action-mask { "true" } else { "false" },
      ).join("\n")
      roster.len() == width and state.selected-row == expected.selected-row and state.candidate-config == expected.candidate-config and state.root-observation == expected.root-observation and state.root-reference-pose == expected.root-reference-pose and state.candidate-pose-shell == expected.candidate-pose-shell and state.actor-action-support == expected.actor-action-support and state.actor-action-support == sha256-hex(support-payload) and state.remaining-budget == expected.remaining-budget and roster.map(
        candidate => candidate.index,
      ).sorted() == range(width) and expected-candidate-roster.len() == width and expected-candidate-roster.map(
        candidate => candidate.index,
      ).sorted() == range(width) and roster.sorted(key: candidate => candidate.index).map(
        candidate => candidate.action-mask,
      ) == expected-candidate-roster.sorted(key: candidate => candidate.index).map(
        candidate => candidate.action-mask,
      ) and selected.len() == 1 and selected.first().action-mask
    }
  }) and target-identities.sorted() == expected-target-identities and measured-state-identities == expected-state-identities and measured-candidate-identities == expected-candidate-identities
  let target-matching-passed = targets.all(target-trainable)
  let actor-input-manifest-audited = states.all(state => state.actor-leaves.len() == q1-audit-actor-input-leaves.len())
  let actor-oracle-mask-separation-audited = value(
    "action_mask_semantics",
  ) == q1-audit-action-mask-semantics and candidates.all(
    candidate => candidate.q-train-mask == (candidate.action-mask and candidate.label-mask),
  )
  let hard-mask-applied = candidates.all(
    candidate => not candidate.included or candidate.action-mask,
  )
  let declared-counts-valid = type(declared-scenes) == int and declared-scenes > 0 and type(
    value("population.target_count"),
  ) == int and value("population.target_count") == targets.len() and type(
    value("population.state_count"),
  ) == int and value("population.state_count") == states.len() and type(
    value("population.candidate_count"),
  ) == int and value("population.candidate_count") == candidates.len()
  declared-counts-valid and state-candidate-roster-valid and targets.filter(
    target => target.store == current-store-index,
  ).len() > 0 and states.filter(
    state => state.store == current-store-index,
  ).len() > 0 and candidates.filter(
    candidate => candidate.store == current-store-index,
  ).len() > 0 and (
    (key: "summary.target_matching_passed", value: target-matching-passed),
    (key: "summary.actor_input_manifest_audited", value: actor-input-manifest-audited),
    (key: "summary.actor_oracle_mask_separation_audited", value: actor-oracle-mask-separation-audited),
    (key: "summary.hard_mask_applied", value: hard-mask-applied),
    (key: "summary.causal_history_only", value: causal-history-only),
  ).all(item => value(item.key) == item.value) and report-store-fact-values-match(
    report,
    store-id,
    (
      (key: "q1.protocol.target_matching_passed", value: target-matching-passed),
      (key: "q1.protocol.actor_input_manifest_audited", value: actor-input-manifest-audited),
      (key: "q1.protocol.actor_oracle_mask_separation_audited", value: actor-oracle-mask-separation-audited),
      (key: "q1.protocol.hard_mask_applied", value: hard-mask-applied),
      (key: "q1.protocol.causal_history_only", value: causal-history-only),
    ),
  )
}

#let report-store-q1-evidence-valid(report, store-id) = {
  let fact-index = report-store-fact-index(report)
  let bundle-row = report-store-indexed-row-or-none(
    fact-index,
    store-id,
    "q1.model.bundle_manifest_sha256",
  )
  let bundle-manifest = if bundle-row == none { none } else { bundle-row.value }
  let ranking = report-store-number-value(report, store-id, "q1.ranking.pairwise_accuracy")
  let ranking-ci-low = report-store-number-value(report, store-id, "q1.ranking.pairwise_accuracy.ci_low")
  let calibration = report-store-number-value(report, store-id, "q1.calibration.mae")
  let ranking-minimum = report-store-number-value(report, store-id, "q1.ranking.pairwise_accuracy.minimum")
  let calibration-maximum = report-store-number-value(report, store-id, "q1.calibration.mae.maximum")
  let passed = report-store-boolean-value(report, store-id, "q1.gate.passed")
  report-store-gated-family-valid(
    report,
    store-id,
    q1-evidence-facts,
    q1-evidence-contract,
    "q1.population.n_scenes",
  ) and report-store-q1-protocol-audit-valid(report, store-id) and report-store-fact-values-match(
    report,
    store-id,
    (
      (key: "q1.protocol.receipt_schema", value: q1-protocol-receipt-schema),
      (key: "q1.protocol.scene_role", value: q1-scene-role),
      (key: "q1.protocol.target_source", value: q1-target-source-protocol),
      (key: "q1.protocol.target_matching_passed", value: true),
      (key: "q1.protocol.actor_input_manifest_audited", value: true),
      (key: "q1.protocol.actor_oracle_mask_separation_audited", value: true),
      (key: "q1.protocol.hard_mask_applied", value: true),
      (key: "q1.protocol.causal_history_only", value: true),
      (key: "q1.ranking.interval_method", value: q1-ranking-interval-method),
      (key: "q1.ranking.chance", value: q1-pairwise-chance),
      (key: "q1.gate.rule", value: q1-decision-rule),
    ),
  ) and report-store-analysis-sidecar-binds-facts(
    report,
    store-id,
    q1-evidence-facts,
    required-name: q1-analysis-receipt-name,
  ) and report-sha256-value-valid(bundle-manifest) and report-store-interval-is-ordered(
    report,
    store-id,
    "q1.ranking.pairwise_accuracy.ci_low",
    "q1.ranking.pairwise_accuracy.ci_high",
  ) and (ranking, ranking-ci-low, calibration, ranking-minimum, calibration-maximum).all(
    value => value != none,
  ) and ranking-minimum > q1-pairwise-chance and calibration-maximum > 0 and passed != none and passed == (
    ranking >= ranking-minimum and ranking-ci-low > q1-pairwise-chance and calibration <= calibration-maximum
  )
}

#let report-stores-q1-evidence-valid(report) = {
  let stores = report.tables.stores.rows
  stores.len() > 0 and stores.all(
    store => report-store-q1-evidence-valid(report, store.store_id),
  ) and report-stores-facts-share-values(
    report,
    q1-evidence-facts,
  ) and report-stores-facts-share-sources(report, q1-evidence-facts)
}

#let q2-candidate-branch-bin(width) = {
  let bounds = (1, 4, 8, 16, 32, 64)
  let lower = 1
  for upper in bounds {
    if width <= upper {
      return if lower == upper { str(upper) } else { str(lower) + "-" + str(upper) }
    }
    lower = upper + 1
  }
  str(lower) + "+"
}

#let q2-values-equal(actual, expected) = if report-value-matches-kind(
  actual,
  "number",
) and report-value-matches-kind(expected, "number") {
  calc.abs(actual - expected) <= derived-identity-abs-tolerance
} else {
  actual == expected
}

#let q2-row-aggregate(rows, minimum-rows) = {
  if rows.len() == 0 {
    (
      row-count: 0,
      within-count: 0,
      within-fraction: none,
      mean-absolute-error: none,
      root-mean-squared-error: none,
      max-absolute-error: none,
      max-relative-error: none,
      minimum-support-met: false,
      tolerance-passed: false,
    )
  } else {
    let absolute = rows.map(row => row.absolute-error)
    let relative = rows.map(row => row.relative-error)
    let within-count = rows.filter(row => row.within).len()
    let support-met = rows.len() >= minimum-rows
    (
      row-count: rows.len(),
      within-count: within-count,
      within-fraction: within-count / rows.len(),
      mean-absolute-error: absolute.sum() / absolute.len(),
      root-mean-squared-error: calc.sqrt(absolute.map(value => value * value).sum() / absolute.len()),
      max-absolute-error: absolute.sorted().last(),
      max-relative-error: relative.sorted().last(),
      minimum-support-met: support-met,
      tolerance-passed: support-met and within-count == rows.len(),
    )
  }
}

#let q2-sidecar-aggregate-matches(index, prefix, aggregate) = {
  let expected = (
    (suffix: "factual_selected_action_exact_q2_row_count", value: aggregate.row-count),
    (suffix: "within_tolerance_count", value: aggregate.within-count),
    (suffix: "within_tolerance_fraction", value: aggregate.within-fraction),
    (suffix: "mean_absolute_error", value: aggregate.mean-absolute-error),
    (suffix: "root_mean_squared_error", value: aggregate.root-mean-squared-error),
    (suffix: "max_absolute_error", value: aggregate.max-absolute-error),
    (suffix: "max_relative_error", value: aggregate.max-relative-error),
    (suffix: "minimum_support_met", value: aggregate.minimum-support-met),
    (suffix: "tolerance_passed", value: aggregate.tolerance-passed),
  )
  expected.all(item => {
    let key = prefix + "." + item.suffix
    let row = report-sidecar-indexed-row-or-none(index, key)
    row != none and if item.value == none {
      row.is_missing == true
    } else {
      row.is_missing == false and q2-values-equal(
        report-sidecar-row-value-or-none(row),
        item.value,
      )
    }
  })
}

#let q2-structured-key(parts) = parts.map(part => {
  let encoded = str(part)
  str(encoded.len()) + ":" + encoded
}).join("|")

#let q2-support-key(chain) = q2-structured-key((
  chain.scene,
  chain.store,
  chain.target,
  chain.horizon,
  q2-candidate-branch-bin(chain.width-max),
  chain.candidate-config,
  chain.rollout-config,
  chain.policy,
))

#let q2-chain-identities-equal(left, right) = (
  left.store == right.store,
  left.rollout == right.rollout,
  left.source-sample == right.source-sample,
  left.scene == right.scene,
  left.target == right.target,
  left.horizon == right.horizon,
  left.width-min == right.width-min,
  left.width-max == right.width-max,
  left.candidate-config == right.candidate-config,
  left.rollout-config == right.rollout-config,
  left.policy == right.policy,
).all(check => check)

#let q2-chain-identity-key(chain) = q2-structured-key((
  chain.store,
  chain.rollout,
  chain.source-sample,
  chain.scene,
  chain.target,
  chain.horizon,
  chain.width-min,
  chain.width-max,
  chain.candidate-config,
  chain.rollout-config,
  chain.policy,
))

#let q2-row-stratum-key(row) = q2-structured-key((
  row.scene,
  row.store,
  row.target,
  row.branch-bin,
  row.candidate-config,
  row.rollout-config,
  row.policy,
  row.horizon,
))

#let report-store-q2-certification-receipt-valid(report, store-id) = {
  let fact-index = report-store-fact-index(report)
  let receipt-row = report-store-indexed-row-or-none(
    fact-index,
    store-id,
    "q2.exact.certification_receipt_sha256",
  )
  let receipt-digest = if receipt-row != none and report-sha256-value-valid(
    receipt-row.value,
  ) { receipt-row.value } else { "" }
  let receipt-sidecar = report-confirmatory-sidecar-by-digest(
    report,
    receipt-digest,
  )
  let receipt-index = report-sidecar-value-index(
    report,
    if receipt-sidecar == none { "" } else { receipt-sidecar.sidecar_id },
  )
  let value(key) = report-sidecar-indexed-value-or-none(receipt-index, key)
  let bundle-digest = value("bundle_manifest_sha256")
  let bundle-sidecar = if report-sha256-value-valid(bundle-digest) {
    report-confirmatory-sidecar-by-embedded-digest(
      report,
      bundle-digest,
      "manifest_sha256",
      required-name: q1-bundle-manifest-name,
    )
  } else { none }
  let bundle-index = report-sidecar-value-index(
    report,
    if bundle-sidecar == none { "" } else { bundle-sidecar.sidecar_id },
  )
  let bundle-value(key) = report-sidecar-indexed-value-or-none(bundle-index, key)
  let payload-matches(receipt-prefix, bundle-prefix) = {
    let receipt-payload = receipt-index.rows.values().filter(
      row => row.key.starts-with(receipt-prefix),
    ).map(row => (
      key: row.key.slice(receipt-prefix.len()),
      missing: row.is_missing,
      value: report-sidecar-row-value-or-none(row),
    )).sorted(key: row => row.key)
    let bundle-payload = bundle-index.rows.values().filter(
      row => row.key.starts-with(bundle-prefix),
    ).map(row => (
      key: row.key.slice(bundle-prefix.len()),
      missing: row.is_missing,
      value: report-sidecar-row-value-or-none(row),
    )).sorted(key: row => row.key)
    receipt-payload.len() > 0 and receipt-payload == bundle-payload
  }
  let store-manifest = report-store-manifest-sha256(report, store-id)
  let manifest-rows = receipt-index.rows.values().filter(
    row => row.key.match(regex("^bound_contract\\.ordered_test_store_manifests\\[[0-9]+\\]$")) != none,
  )
  let manifest-values = range(manifest-rows.len()).map(index => value(
    "bound_contract.ordered_test_store_manifests[" + str(index) + "]",
  ))
  let ordered-manifest-json = "[" + manifest-values.map(
    manifest => "\"" + str(manifest) + "\"",
  ).join(",") + "]"
  let expected-ordered-manifest-digest = if manifest-values.all(
    report-sha256-value-valid,
  ) { sha256-hex(ordered-manifest-json) } else { "" }
  let bundle-manifest-rows = bundle-index.rows.values().filter(
    row => row.key.match(regex("^identity\\.ordered_store_manifests\\.test\\[[0-9]+\\]$")) != none,
  )
  let bundle-manifests = range(bundle-manifest-rows.len()).map(index => bundle-value(
    "identity.ordered_store_manifests.test[" + str(index) + "]",
  ))
  let report-manifests = report.tables.stores.rows.map(
    row => row.at("manifest_sha256", default: none),
  )
  let scorer-experiment-profile = value("bound_contract.scorer_config.experiment_profile")
  let experiment-profile = value("bound_contract.module_config.experiment_profile")
  let actor-experiment-profile = value("bound_contract.actor_state_contract.experiment_profile")
  let module-root-evl-profile = value("bound_contract.module_config.root_evl_profile")
  let actor-root-evl-profile = value("bound_contract.actor_state_contract.root_evl_profile")
  let learning-target-protocol = value("bound_contract.learning_contract.data_contract.target_protocol")
  let selected-observation-protocol = value(
    "bound_contract.module_config.selected_observation_protocol",
  )
  let actor-selected-observation-protocol = value(
    "bound_contract.actor_state_contract.selected_observation_protocol",
  )
  let geometry-rows = (
    report-sidecar-indexed-row-or-none(
      receipt-index,
      "bound_contract.geometry_contract_hash",
    ),
    report-sidecar-indexed-row-or-none(
      receipt-index,
      "bound_contract.module_config.geometry_contract_hash",
    ),
    report-sidecar-indexed-row-or-none(
      receipt-index,
      "bound_contract.actor_state_contract.geometry_contract_hash",
    ),
  )
  let geometry-valid = experiment-profile == "qh_cf0_v1" and selected-observation-protocol == "none" and actor-selected-observation-protocol == "none" and geometry-rows.all(
    row => row != none and row.is_missing == true,
  )
  let bundle-contract-valid = bundle-sidecar != none and bundle-value(
    "scorer_config_hash",
  ) == value("bound_contract.scorer_config_hash") and bundle-value(
    "identity.learning_contract_hash",
  ) == value("bound_contract.learning_contract_hash") and bundle-value(
    "identity.learning_contract_payload_sha256",
  ) == value("bound_contract.learning_contract_payload_sha256") and bundle-value(
    "identity.actor_state_contract_hash",
  ) == value("bound_contract.actor_state_contract_hash") and bundle-value(
    "identity.actor_state_contract_payload_sha256",
  ) == value("bound_contract.actor_state_contract_payload_sha256") and payload-matches(
    "bound_contract.scorer_config.",
    "scorer_config.",
  ) and payload-matches(
    "bound_contract.module_config.",
    "module_config.",
  ) and payload-matches(
    "bound_contract.learning_contract.",
    "identity.learning_contract.",
  ) and payload-matches(
    "bound_contract.actor_state_contract.",
    "identity.actor_state_contract.",
  ) and bundle-manifests.len() > 0 and bundle-manifests.all(
    report-sha256-value-valid,
  ) and bundle-manifests == manifest-values
  let lineage-valid = receipt-sidecar != none and store-manifest != none and bundle-contract-valid and (
    "bundle_manifest_sha256",
    "test_population_sha256",
    "test_provenance_sha256",
    "bound_contract.scorer_config_hash",
    "bound_contract.learning_contract_payload_sha256",
    "bound_contract.actor_state_contract_payload_sha256",
  ).all(key => report-sha256-value-valid(value(key))) and (
    "bound_contract.learning_contract_hash",
    "bound_contract.actor_state_contract_hash",
  ).all(key => report-identity16-value-valid(value(key))) and scorer-experiment-profile == experiment-profile and actor-experiment-profile == experiment-profile and module-root-evl-profile == "evl_v1" and actor-root-evl-profile == "evl_v1" and learning-target-protocol == "v1_observed" and geometry-valid and manifest-values.len() > 0 and manifest-values.all(
    report-sha256-value-valid,
  ) and manifest-values.dedup().len() == manifest-values.len() and report-manifests.all(
    report-sha256-value-valid,
  ) and manifest-values.sorted() == report-manifests.sorted() and manifest-values.contains(store-manifest)
  if not lineage-valid { return false }

  let selected-prefixes = report-sidecar-record-prefixes(
    receipt-index,
    "exact_q2.selected_chain_support",
    "selection_rank",
  )
  let row-prefixes = report-sidecar-record-prefixes(
    receipt-index,
    "exact_q2.factual_selected_action_exact_q2_rows",
    "selection_rank",
  )
  let selected = selected-prefixes.map(prefix => (
    prefix: prefix,
    rank: value(prefix + ".selection_rank"),
    dataset: value(prefix + ".dataset_index"),
    store: value(prefix + ".identity.store_index"),
    rollout: value(prefix + ".identity.rollout_row_id"),
    source-sample: value(prefix + ".identity.source_sample_index"),
    scene: value(prefix + ".identity.scene_id"),
    target: value(prefix + ".identity.target_row_id"),
    horizon: value(prefix + ".identity.configured_horizon"),
    width-min: value(prefix + ".identity.candidate_width_min"),
    width-max: value(prefix + ".identity.candidate_width_max"),
    candidate-config: value(prefix + ".identity.candidate_config_hash"),
    rollout-config: value(prefix + ".identity.rollout_config_hash"),
    policy: value(prefix + ".identity.selection_policy"),
    unit-manifest: value(prefix + ".independent_unit.ordered_store_manifest_sha256"),
    unit-scene: value(prefix + ".independent_unit.scene_id"),
    factual-states: value(prefix + ".factual_state_count"),
    materialized-successors: value(prefix + ".states_with_materialized_successors_count"),
    complete-successors: value(prefix + ".states_with_complete_hard_valid_successor_labels_count"),
    exact-rows: value(prefix + ".factual_selected_action_exact_q2_row_count"),
  ))
  let selected-valid = selected.len() > 0 and selected.all(chain => (
    type(chain.rank) == int and chain.rank >= 0,
    type(chain.dataset) == int and chain.dataset >= 0,
    type(chain.store) == int and chain.store >= 0 and chain.store < manifest-values.len(),
    type(chain.rollout) == int and chain.rollout >= 0,
    type(chain.source-sample) == int and chain.source-sample >= 0,
    type(chain.scene) == str and chain.scene.len() > 0,
    type(chain.target) == int and chain.target >= 0,
    type(chain.horizon) == int and chain.horizon >= 1,
    type(chain.width-min) == int and chain.width-min >= 1,
    type(chain.width-max) == int and type(chain.width-min) == int and chain.width-max >= chain.width-min,
    type(chain.candidate-config) == str and chain.candidate-config.len() > 0,
    type(chain.rollout-config) == str and chain.rollout-config.len() > 0,
    type(chain.policy) == str and chain.policy.len() > 0,
    report-sha256-value-valid(chain.unit-manifest),
    chain.unit-manifest == expected-ordered-manifest-digest,
    chain.unit-scene == chain.scene,
    (chain.factual-states, chain.materialized-successors, chain.complete-successors, chain.exact-rows).all(
      count => type(count) == int and count >= 0,
    ),
  ).all(check => check)) and selected.map(chain => chain.rank).sorted() == range(
    selected.len(),
  ) and selected.map(
    chain => str(chain.store) + "|" + str(chain.rollout),
  ).dedup().len() == selected.len()
  if not selected-valid { return false }
  let population-prefixes = report-sidecar-record-prefixes(
    receipt-index,
    "exact_q2.population_census.chains",
    "dataset_index",
  )
  let population = population-prefixes.map(prefix => (
    prefix: prefix,
    dataset: value(prefix + ".dataset_index"),
    store: value(prefix + ".identity.store_index"),
    rollout: value(prefix + ".identity.rollout_row_id"),
    source-sample: value(prefix + ".identity.source_sample_index"),
    scene: value(prefix + ".identity.scene_id"),
    target: value(prefix + ".identity.target_row_id"),
    horizon: value(prefix + ".identity.configured_horizon"),
    width-min: value(prefix + ".identity.candidate_width_min"),
    width-max: value(prefix + ".identity.candidate_width_max"),
    candidate-config: value(prefix + ".identity.candidate_config_hash"),
    rollout-config: value(prefix + ".identity.rollout_config_hash"),
    policy: value(prefix + ".identity.selection_policy"),
  ))
  let population-valid = population.len() > 0 and population.all(chain => (
    type(chain.dataset) == int and chain.dataset >= 0,
    type(chain.store) == int and chain.store >= 0 and chain.store < manifest-values.len(),
    type(chain.rollout) == int and chain.rollout >= 0,
    type(chain.source-sample) == int and chain.source-sample >= 0,
    type(chain.scene) == str and chain.scene.len() > 0,
    type(chain.target) == int and chain.target >= 0,
    type(chain.horizon) == int and chain.horizon >= 1,
    type(chain.width-min) == int and chain.width-min >= 1,
    type(chain.width-max) == int and type(chain.width-min) == int and chain.width-max >= chain.width-min,
    type(chain.candidate-config) == str and chain.candidate-config.len() > 0,
    type(chain.rollout-config) == str and chain.rollout-config.len() > 0,
    type(chain.policy) == str and chain.policy.len() > 0,
  ).all(check => check)) and population.map(chain => chain.dataset).sorted() == range(
    population.len(),
  ) and population.map(
    chain => str(chain.store) + "|" + str(chain.rollout),
  ).dedup().len() == population.len() and population.map(q2-chain-identity-key).dedup().len() == population.len()
  if not population-valid { return false }
  let population-by-dataset = (:)
  for chain in population {
    population-by-dataset.insert(str(chain.dataset), chain)
  }
  let selected-population-binding-valid = selected.all(chain => {
    let population-chain = population-by-dataset.at(str(chain.dataset), default: none)
    population-chain != none and q2-chain-identities-equal(population-chain, chain)
  })
  if not selected-population-binding-valid { return false }
  let current-store-index = manifest-values.position(
    manifest => manifest == store-manifest,
  )
  let selected-by-rank = (:)
  for chain in selected {
    if type(chain.rank) == int { selected-by-rank.insert(str(chain.rank), chain) }
  }

  let rows = row-prefixes.map(prefix => {
    let ledger-prefixes = receipt-index.rows.values().filter(row => (
      row.key.starts-with(prefix + ".successor_reward_ledger["),
      row.key.ends-with(".candidate_index"),
    ).all(check => check)).map(
      row => row.key.replace(regex("\\.candidate_index$"), ""),
    )
    let successor-ledger = ledger-prefixes.map(ledger-prefix => (
      candidate: value(ledger-prefix + ".candidate_index"),
      reward: value(ledger-prefix + ".reward"),
    ))
    (
    prefix: prefix,
    rank: value(prefix + ".selection_rank"),
    dataset: value(prefix + ".dataset_index"),
    store: value(prefix + ".store_index"),
    rollout: value(prefix + ".rollout_row_id"),
    source-sample: value(prefix + ".source_sample_index"),
    scene: value(prefix + ".scene_id"),
    manifest: value(prefix + ".ordered_store_manifest_sha256"),
    unit-manifest: value(prefix + ".independent_unit.ordered_store_manifest_sha256"),
    unit-scene: value(prefix + ".independent_unit.scene_id"),
    target: value(prefix + ".target_row_id"),
    step: value(prefix + ".step_index"),
    horizon: value(prefix + ".configured_horizon"),
    requested-horizon: value(prefix + ".requested_horizon"),
    candidate-config: value(prefix + ".candidate_config_hash"),
    rollout-config: value(prefix + ".rollout_config_hash"),
    policy: value(prefix + ".selection_policy"),
    current-count: value(prefix + ".current_candidate_count"),
    successor-candidate-count: value(prefix + ".successor_candidate_count"),
    successor-action-count: value(prefix + ".successor_action_count"),
    successor-count: value(prefix + ".successor_backup_count"),
    branch-bin: value(prefix + ".candidate_branch_bin"),
    selected-index: value(prefix + ".selected_index"),
    immediate-reward: value(prefix + ".immediate_reward"),
    discount: value(prefix + ".discount"),
    terminal: value(prefix + ".terminal"),
    successor-max-reward: value(prefix + ".successor_max_reward"),
    recursive: value(prefix + ".recursive_target"),
    exact: value(prefix + ".exact_target"),
    absolute-error: value(prefix + ".absolute_error"),
    relative-error: value(prefix + ".relative_error"),
    tolerance: value(prefix + ".tolerance"),
    within: value(prefix + ".within_tolerance"),
    successor-ledger: successor-ledger,
    )
  })
  let absolute-tolerance = value("exact_q2.spec.absolute_tolerance")
  let relative-tolerance = value("exact_q2.spec.relative_tolerance")
  let rows-valid = rows.len() > 0 and report-value-is-finite-float32(
    absolute-tolerance,
  ) and absolute-tolerance >= 0 and report-value-is-finite-float32(
    relative-tolerance,
  ) and relative-tolerance >= 0 and rows.all(row => {
    let chain = if type(row.rank) == int {
      selected-by-rank.at(str(row.rank), default: none)
    } else { none }
    let targets-valid = report-value-is-finite-float32(
      row.recursive,
    ) and report-value-is-finite-float32(row.exact)
    let derived-absolute-error = if targets-valid {
      calc.abs(row.recursive - row.exact)
    } else { none }
    let derived-tolerance = if targets-valid {
      absolute-tolerance + relative-tolerance * calc.abs(row.exact)
    } else { none }
    let derived-relative-error = if report-value-is-finite-float32(
      derived-absolute-error,
    ) and report-value-is-finite-float32(derived-tolerance) {
      derived-absolute-error / calc.max(calc.abs(row.exact), float32-epsilon)
    } else { none }
    let successor-candidates = row.successor-ledger.map(entry => entry.candidate)
    let successor-cardinality-valid = if chain != none and type(
      row.successor-candidate-count,
    ) == int and type(row.successor-action-count) == int {
      row.successor-candidate-count >= 1 and row.successor-candidate-count >= chain.width-min and row.successor-candidate-count <= chain.width-max and row.successor-action-count >= 1 and row.successor-action-count <= row.successor-candidate-count
    } else { false }
    let successor-ledger-valid = successor-cardinality-valid and row.successor-ledger.len() > 0 and row.successor-ledger.all(entry => if type(entry.candidate) == int {
      entry.candidate >= 0 and entry.candidate < row.successor-candidate-count and report-value-is-finite-float32(entry.reward)
    } else { false }) and successor-candidates == successor-candidates.sorted() and successor-candidates.dedup().len() == successor-candidates.len()
    let ledger-max-reward = if successor-ledger-valid {
      row.successor-ledger.map(entry => entry.reward).sorted().last()
    } else { none }
    let transition-operands-valid = report-value-is-finite-float32(
      row.immediate-reward,
    ) and report-value-is-finite-float32(row.discount) and row.discount >= 0 and report-value-is-finite-float32(
      row.successor-max-reward,
    ) and report-value-is-finite-float32(ledger-max-reward) and q2-values-equal(
      row.successor-max-reward,
      ledger-max-reward,
    )
    let discounted-successor = if transition-operands-valid {
      row.discount * ledger-max-reward
    } else { none }
    let derived-exact = if report-value-is-finite-float32(discounted-successor) {
      row.immediate-reward + discounted-successor
    } else { none }
    let exact-identity-tolerance = if report-value-is-finite-float32(
      derived-exact,
    ) and targets-valid {
      8 * float32-epsilon * calc.max(
        1.0,
        calc.max(
          calc.abs(row.immediate-reward),
          calc.max(calc.abs(discounted-successor), calc.abs(row.exact)),
        ),
      )
    } else { none }
    let exact-q2-provenance-valid = if chain != none and type(
      chain.horizon,
    ) == int and type(row.step) == int and type(row.requested-horizon) == int {
      chain.horizon >= 2 and row.requested-horizon == 2 and row.step >= 0 and row.step + 1 < chain.factual-states and row.step == chain.horizon - row.requested-horizon
    } else { false }
    chain != none and (
      row.dataset == chain.dataset,
      row.store == chain.store,
      row.rollout == chain.rollout,
      row.source-sample == chain.source-sample,
      row.scene == chain.scene,
      row.manifest == chain.unit-manifest,
      row.unit-manifest == chain.unit-manifest,
      row.unit-scene == chain.scene,
      row.target == chain.target,
      row.horizon == chain.horizon,
      row.candidate-config == chain.candidate-config,
      row.rollout-config == chain.rollout-config,
      row.policy == chain.policy,
      exact-q2-provenance-valid,
      successor-cardinality-valid,
      type(row.successor-count) == int and row.successor-count >= 1 and row.successor-count == row.successor-action-count and row.branch-bin == q2-candidate-branch-bin(row.successor-count),
      successor-ledger-valid and row.successor-ledger.len() == row.successor-action-count,
      type(row.current-count) == int and row.current-count >= chain.width-min and row.current-count <= chain.width-max and type(row.selected-index) == int and row.selected-index >= 0 and row.selected-index < row.current-count,
      transition-operands-valid,
      type(row.terminal) == bool and row.terminal == false,
      report-value-is-finite-float32(derived-exact) and report-value-is-finite-float32(exact-identity-tolerance) and calc.abs(row.exact - derived-exact) <= exact-identity-tolerance,
      report-value-is-finite-float32(derived-relative-error) and report-value-is-finite-float32(row.relative-error) and q2-values-equal(row.relative-error, derived-relative-error),
      report-value-is-finite-float32(derived-absolute-error) and report-value-is-finite-float32(row.absolute-error) and calc.abs(row.absolute-error - derived-absolute-error) <= derived-identity-abs-tolerance,
      report-value-is-finite-float32(derived-tolerance) and report-value-is-finite-float32(row.tolerance) and calc.abs(row.tolerance - derived-tolerance) <= derived-identity-abs-tolerance,
      derived-absolute-error != none and derived-tolerance != none and type(row.within) == bool and row.within == (derived-absolute-error <= derived-tolerance),
    ).all(check => check)
  }) and rows.map(
    row => str(row.store) + "|" + str(row.rollout) + "|" + str(row.step),
  ).dedup().len() == rows.len()
  if not rows-valid { return false }

  let selected-row-groups = (:)
  let unit-row-groups = (:)
  for row in rows {
    if type(row.rank) == int {
      let rank-key = str(row.rank)
      selected-row-groups.insert(
        rank-key,
        selected-row-groups.at(rank-key, default: ()) + (row,),
      )
    }
    if report-sha256-value-valid(row.unit-manifest) and type(row.unit-scene) == str {
      let unit-key = q2-structured-key((row.unit-manifest, row.unit-scene))
      unit-row-groups.insert(
        unit-key,
        unit-row-groups.at(unit-key, default: ()) + (row,),
      )
    }
  }
  let chain-counts-valid = selected.all(chain => selected-row-groups.at(
    str(chain.rank),
    default: (),
  ).len() == chain.exact-rows)
  let selected-unit-keys = selected.map(
    chain => q2-structured-key((chain.unit-manifest, chain.unit-scene)),
  ).dedup()
  let selected-unit-chain-groups = (:)
  for chain in selected {
    let unit-key = q2-structured-key((chain.unit-manifest, chain.unit-scene))
    selected-unit-chain-groups.insert(
      unit-key,
      selected-unit-chain-groups.at(unit-key, default: ()) + (chain,),
    )
  }
  let unit-row-counts = selected-unit-keys.map(
    unit-key => unit-row-groups.at(unit-key, default: ()).len(),
  )
  let supported-unit-maes = selected-unit-keys.map(unit-key => unit-row-groups.at(
    unit-key,
    default: (),
  )).filter(group => group.len() > 0).map(
    group => group.map(row => row.absolute-error).sum() / group.len(),
  )
  let derived-mae = if supported-unit-maes.len() > 0 {
    supported-unit-maes.sum() / supported-unit-maes.len()
  } else { none }

  let support-groups = (:)
  let support-chain-groups = (:)
  for chain in selected {
    if type(chain.width-max) == int and chain.width-max >= 1 {
      let support-key = q2-support-key(chain)
      support-groups.insert(
        support-key,
        support-groups.at(support-key, default: 0) + chain.exact-rows,
      )
      support-chain-groups.insert(
        support-key,
        support-chain-groups.at(support-key, default: ()) + (chain,),
      )
    }
  }
  let row-stratum-groups = (:)
  for row in rows {
    let stratum-key = q2-row-stratum-key(row)
    row-stratum-groups.insert(
      stratum-key,
      row-stratum-groups.at(stratum-key, default: ()) + (row,),
    )
  }
  let population-stratum-groups = (:)
  for chain in population {
    let stratum-key = q2-support-key(chain)
    population-stratum-groups.insert(
      stratum-key,
      population-stratum-groups.at(stratum-key, default: ()) + (chain,),
    )
  }
  let population-chain-count = value("exact_q2.population_census.population_chain_count")
  let selected-chain-count = value("exact_q2.population_census.selected_chain_count")
  let reported-coverage = value("exact_q2.population_census.selected_chain_fraction")
  let coverage-minimum = value("exact_q2.spec.minimum_population_coverage")
  let minimum-units-required = value("exact_q2.spec.minimum_independent_units")
  let minimum-unit-rows-required = value(
    "exact_q2.spec.minimum_exact_rows_per_independent_unit",
  )
  let specification-valid = report-value-matches-kind(
    coverage-minimum,
    "number",
  ) and coverage-minimum >= 0 and coverage-minimum <= 1 and type(
    minimum-units-required,
  ) == int and minimum-units-required >= 1 and type(
    minimum-unit-rows-required,
  ) == int and minimum-unit-rows-required >= 1 and type(
    population-chain-count,
  ) == int and population-chain-count == population.len() and type(
    selected-chain-count,
  ) == int and selected-chain-count == selected.len() and report-value-matches-kind(
    reported-coverage,
    "number",
  )
  if not specification-valid { return false }
  let safe-minimum-units-required = if type(minimum-units-required) == int {
    minimum-units-required
  } else { 0 }
  let safe-minimum-unit-rows-required = if type(minimum-unit-rows-required) == int {
    minimum-unit-rows-required
  } else { 0 }
  let derived-coverage = if population.len() > 0 {
    selected.len() / population.len()
  } else { none }
  let derived-minimum-support-rows = if support-groups.len() > 0 {
    support-groups.values().sorted().first()
  } else { none }
  let derived-minimum-unit-rows = if unit-row-counts.len() > 0 {
    unit-row-counts.sorted().first()
  } else { none }
  let derived-maximum-excess = if rows.len() > 0 {
    rows.map(row => row.absolute-error - row.tolerance).sorted().last()
  } else { none }
  let derived-unit-pass = type(minimum-units-required) == int and type(
    minimum-unit-rows-required,
  ) == int and derived-minimum-unit-rows != none and derived-maximum-excess != none and (
    selected-unit-keys.len() >= minimum-units-required,
    derived-minimum-unit-rows >= minimum-unit-rows-required,
    derived-maximum-excess <= 0,
  ).all(check => check)
  let derived-pass = derived-coverage != none and type(coverage-minimum) in (
    int,
    float,
  ) and derived-minimum-support-rows != none and derived-unit-pass and (
    derived-coverage >= coverage-minimum,
    derived-minimum-support-rows >= 1,
  ).all(check => check)

  let census-prefixes = report-sidecar-record-prefixes(
    receipt-index,
    "exact_q2.population_census.strata",
    "stratum.scene_id",
  )
  let census-strata = census-prefixes.map(prefix => (
    prefix: prefix,
    scene: value(prefix + ".stratum.scene_id"),
    store: value(prefix + ".stratum.store_index"),
    target: value(prefix + ".stratum.target_row_id"),
    horizon: value(prefix + ".stratum.configured_horizon"),
    branch-bin: value(prefix + ".stratum.candidate_branch_bin"),
    candidate-config: value(prefix + ".stratum.candidate_config_hash"),
    rollout-config: value(prefix + ".stratum.rollout_config_hash"),
    policy: value(prefix + ".stratum.selection_policy"),
    population: value(prefix + ".population_chain_count"),
    selected: value(prefix + ".selected_chain_count"),
    fraction: value(prefix + ".selected_chain_fraction"),
  ))
  let census-keys = census-strata.map(stratum => q2-structured-key((
    stratum.scene,
    stratum.store,
    stratum.target,
    stratum.horizon,
    stratum.branch-bin,
    stratum.candidate-config,
    stratum.rollout-config,
    stratum.policy,
  )))
  let census-valid = census-strata.len() > 0 and census-strata.all(stratum => {
    let key = q2-structured-key((
      stratum.scene,
      stratum.store,
      stratum.target,
      stratum.horizon,
      stratum.branch-bin,
      stratum.candidate-config,
      stratum.rollout-config,
      stratum.policy,
    ))
    let selected-count = support-chain-groups.at(key, default: ()).len()
    let population-count = population-stratum-groups.at(key, default: ()).len()
    type(stratum.scene) == str and stratum.scene.len() > 0 and type(
      stratum.store,
    ) == int and stratum.store >= 0 and stratum.store < manifest-values.len() and type(stratum.target) == int and stratum.target >= 0 and type(
      stratum.horizon,
    ) == int and stratum.horizon >= 1 and type(stratum.branch-bin) == str and stratum.branch-bin.len() > 0 and type(
      stratum.candidate-config,
    ) == str and stratum.candidate-config.len() > 0 and type(stratum.rollout-config) == str and stratum.rollout-config.len() > 0 and type(
      stratum.policy,
    ) == str and stratum.policy.len() > 0 and type(stratum.population) == int and stratum.population == population-count and stratum.population >= 1 and type(
      stratum.selected,
    ) == int and stratum.selected >= 0 and stratum.selected <= stratum.population and report-value-matches-kind(
      stratum.fraction,
      "number",
    ) and stratum.selected == selected-count and q2-values-equal(
      stratum.fraction,
      stratum.selected / stratum.population,
    )
  }) and census-keys.dedup().len() == census-keys.len() and census-keys.sorted() == population-stratum-groups.keys().sorted() and support-chain-groups.keys().all(
    key => census-keys.contains(key),
  ) and census-strata.map(stratum => stratum.population).sum(default: 0) == population.len() and census-strata.map(
    stratum => stratum.selected,
  ).sum(default: 0) == selected.len()
  if not census-valid { return false }
  let current-store-in-population = current-store-index != none and population.any(
    chain => chain.store == current-store-index,
  )
  if not current-store-in-population { return false }
  let census-scenes = population.map(chain => chain.scene).dedup()
  let census-targets = population.map(
    chain => q2-structured-key((chain.scene, chain.target)),
  ).dedup()
  let branch-bin-values = range(6).map(index => value(
    "exact_q2.population_census.candidate_branch_bins[" + str(index) + "]",
  ))
  let census-summary-valid = branch-bin-values == (1, 4, 8, 16, 32, 64) and (
    (key: "exact_q2.population_census.near_exhaustive", value: selected.len() == population.len()),
    (key: "exact_q2.population_census.eligible_scene_count", value: census-scenes.len()),
    (key: "exact_q2.population_census.eligible_target_count", value: census-targets.len()),
    (key: "exact_q2.population_census.eligible_chain_count", value: population.len()),
    (key: "exact_q2.population_census.independent_unit_count", value: census-scenes.len()),
  ).all(expected => report-sidecar-indexed-value-matches(
    receipt-index,
    expected.key,
    expected.value,
  ))

  let support-prefixes = report-sidecar-record-prefixes(
    receipt-index,
    "exact_q2.support_stratum_aggregates",
    "stratum.scene_id",
  )
  let support-key-types-valid = support-prefixes.all(prefix => (
    type(value(prefix + ".stratum.scene_id")) == str,
    type(value(prefix + ".stratum.store_index")) == int,
    type(value(prefix + ".stratum.target_row_id")) == int,
    type(value(prefix + ".stratum.configured_horizon")) == int,
    type(value(prefix + ".stratum.candidate_branch_bin")) == str,
    type(value(prefix + ".stratum.candidate_config_hash")) == str,
    type(value(prefix + ".stratum.rollout_config_hash")) == str,
    type(value(prefix + ".stratum.selection_policy")) == str,
  ).all(check => check))
  let support-aggregate-keys = support-prefixes.map(prefix => q2-structured-key((
    value(prefix + ".stratum.scene_id"),
    value(prefix + ".stratum.store_index"),
    value(prefix + ".stratum.target_row_id"),
    value(prefix + ".stratum.configured_horizon"),
    value(prefix + ".stratum.candidate_branch_bin"),
    value(prefix + ".stratum.candidate_config_hash"),
    value(prefix + ".stratum.rollout_config_hash"),
    value(prefix + ".stratum.selection_policy"),
  )))
  let support-aggregates-valid = support-key-types-valid and support-prefixes.len() == support-chain-groups.len() and support-aggregate-keys.dedup().len() == support-aggregate-keys.len() and support-aggregate-keys.sorted() == support-chain-groups.keys().sorted() and support-prefixes.enumerate().all(((index, prefix)) => {
    let key = support-aggregate-keys.at(index)
    let chains = support-chain-groups.at(key)
    (
      (key: prefix + ".selected_chain_count", value: chains.len()),
      (key: prefix + ".chains_with_factual_selected_action_exact_q2_count", value: chains.filter(chain => chain.exact-rows > 0).len()),
      (key: prefix + ".factual_selected_action_exact_q2_row_count", value: chains.map(chain => chain.exact-rows).sum(default: 0)),
    ).all(expected => report-sidecar-indexed-value-matches(
      receipt-index,
      expected.key,
      expected.value,
    ))
  })

  let evidence-denominators-valid = (
    (key: "factual_state_count", selector: chain => chain.factual-states),
    (key: "states_with_materialized_successors_count", selector: chain => chain.materialized-successors),
    (key: "states_with_complete_hard_valid_successor_labels_count", selector: chain => chain.complete-successors),
    (key: "factual_selected_action_exact_q2_row_count", selector: chain => chain.exact-rows),
  ).all(field => report-sidecar-indexed-value-matches(
    receipt-index,
    "exact_q2.evidence_denominators." + field.key,
    selected.map(field.selector).sum(default: 0),
  ))
  let global-aggregate = q2-row-aggregate(rows, 1)
  let aggregate-valid = q2-sidecar-aggregate-matches(
    receipt-index,
    "exact_q2.aggregate",
    global-aggregate,
  )

  let stored-stratum-prefixes = report-sidecar-record-prefixes(
    receipt-index,
    "exact_q2.stratum_aggregates",
    "stratum.scene_id",
  )
  let stored-stratum-key-types-valid = stored-stratum-prefixes.all(prefix => (
    type(value(prefix + ".stratum.scene_id")) == str,
    type(value(prefix + ".stratum.store_index")) == int,
    type(value(prefix + ".stratum.target_row_id")) == int,
    type(value(prefix + ".stratum.candidate_branch_bin")) == str,
    type(value(prefix + ".stratum.candidate_config_hash")) == str,
    type(value(prefix + ".stratum.rollout_config_hash")) == str,
    type(value(prefix + ".stratum.selection_policy")) == str,
    type(value(prefix + ".stratum.configured_horizon")) == int,
  ).all(check => check))
  let stored-stratum-keys = stored-stratum-prefixes.map(prefix => q2-structured-key((
    value(prefix + ".stratum.scene_id"),
    value(prefix + ".stratum.store_index"),
    value(prefix + ".stratum.target_row_id"),
    value(prefix + ".stratum.candidate_branch_bin"),
    value(prefix + ".stratum.candidate_config_hash"),
    value(prefix + ".stratum.rollout_config_hash"),
    value(prefix + ".stratum.selection_policy"),
    value(prefix + ".stratum.configured_horizon"),
  )))
  let stratum-aggregates-valid = stored-stratum-key-types-valid and stored-stratum-prefixes.len() == row-stratum-groups.len() and stored-stratum-keys.dedup().len() == stored-stratum-keys.len() and stored-stratum-keys.sorted() == row-stratum-groups.keys().sorted() and stored-stratum-prefixes.enumerate().all(((index, prefix)) => q2-sidecar-aggregate-matches(
    receipt-index,
    prefix,
    q2-row-aggregate(row-stratum-groups.at(stored-stratum-keys.at(index)), 1),
  ))

  let ordered-unit-manifests = selected.map(chain => chain.unit-manifest).dedup()
  let ordered-unit-manifest = if ordered-unit-manifests.len() == 1 {
    ordered-unit-manifests.first()
  } else { "" }
  let population-unit-keys = census-scenes.map(
    scene => q2-structured-key((ordered-unit-manifest, scene)),
  )
  let unit-prefixes = report-sidecar-record-prefixes(
    receipt-index,
    "exact_q2.independent_unit_aggregates",
    "independent_unit.scene_id",
  )
  let unit-key-types-valid = unit-prefixes.all(prefix => report-sha256-value-valid(value(
    prefix + ".independent_unit.ordered_store_manifest_sha256",
  )) and type(value(prefix + ".independent_unit.scene_id")) == str)
  let stored-unit-keys = unit-prefixes.map(prefix => q2-structured-key((
    value(prefix + ".independent_unit.ordered_store_manifest_sha256"),
    value(prefix + ".independent_unit.scene_id"),
  )))
  let unit-aggregates-valid = unit-key-types-valid and ordered-unit-manifests.len() == 1 and unit-prefixes.len() == population-unit-keys.len() and stored-unit-keys.dedup().len() == stored-unit-keys.len() and stored-unit-keys.sorted() == population-unit-keys.sorted() and unit-prefixes.enumerate().all(((index, prefix)) => {
    let unit-key = stored-unit-keys.at(index)
    let scene = value(prefix + ".independent_unit.scene_id")
    let population-count = census-strata.filter(
      stratum => stratum.scene == scene,
    ).map(stratum => stratum.population).sum(default: 0)
    let chains = selected-unit-chain-groups.at(unit-key, default: ())
    let unit-rows = unit-row-groups.at(unit-key, default: ())
    let unit-aggregate = q2-row-aggregate(unit-rows, safe-minimum-unit-rows-required)
    let admitted = chains.len() > 0
    let expected-scalars = (
      (key: prefix + ".population_chain_count", value: population-count),
      (key: prefix + ".selected_chain_count", value: chains.len()),
      (key: prefix + ".admitted", value: admitted),
      (key: prefix + ".factual_state_count", value: chains.map(chain => chain.factual-states).sum(default: 0)),
      (key: prefix + ".states_with_materialized_successors_count", value: chains.map(chain => chain.materialized-successors).sum(default: 0)),
      (key: prefix + ".states_with_complete_hard_valid_successor_labels_count", value: chains.map(chain => chain.complete-successors).sum(default: 0)),
      (key: prefix + ".factual_selected_action_exact_q2_row_count", value: chains.map(chain => chain.exact-rows).sum(default: 0)),
      (key: prefix + ".unit_gate_passed", value: admitted and unit-aggregate.tolerance-passed),
    )
    expected-scalars.all(expected => report-sidecar-indexed-value-matches(
      receipt-index,
      expected.key,
      expected.value,
    )) and q2-sidecar-aggregate-matches(
      receipt-index,
      prefix + ".error",
      unit-aggregate,
    )
  })
  let supported-unit-count = selected-unit-keys.filter(
    unit-key => unit-row-groups.at(unit-key, default: ()).len() >= safe-minimum-unit-rows-required,
  ).len()
  let passing-unit-count = selected-unit-keys.filter(unit-key => q2-row-aggregate(
    unit-row-groups.at(unit-key, default: ()),
    safe-minimum-unit-rows-required,
  ).tolerance-passed).len()
  let minimum-units-met = supported-unit-count >= safe-minimum-units-required
  let all-selected-units-passed = selected-unit-keys.len() > 0 and passing-unit-count == selected-unit-keys.len()
  let independent-gate-valid = (
    (key: "exact_q2.independent_unit_gate.independent_unit_semantics", value: q2-independent-unit-semantics),
    (key: "exact_q2.independent_unit_gate.aggregation", value: q2-independent-unit-aggregation),
    (key: "exact_q2.independent_unit_gate.population_independent_unit_count", value: population-unit-keys.len()),
    (key: "exact_q2.independent_unit_gate.selected_independent_unit_count", value: selected-unit-keys.len()),
    (key: "exact_q2.independent_unit_gate.supported_independent_unit_count", value: supported-unit-count),
    (key: "exact_q2.independent_unit_gate.passing_independent_unit_count", value: passing-unit-count),
    (key: "exact_q2.independent_unit_gate.minimum_independent_units", value: minimum-units-required),
    (key: "exact_q2.independent_unit_gate.minimum_exact_rows_per_independent_unit", value: minimum-unit-rows-required),
    (key: "exact_q2.independent_unit_gate.minimum_independent_units_met", value: minimum-units-met),
    (key: "exact_q2.independent_unit_gate.all_selected_units_passed", value: all-selected-units-passed),
    (key: "exact_q2.independent_unit_gate.passed", value: minimum-units-met and all-selected-units-passed),
  ).all(expected => report-sidecar-indexed-value-matches(
    receipt-index,
    expected.key,
    expected.value,
  ))
  let facts-match = (
    (key: "q2.exact.bundle_manifest_sha256", value: value("bundle_manifest_sha256")),
    (key: "q2.exact.mae", value: derived-mae),
    (key: "q2.exact.coverage", value: derived-coverage),
    (key: "q2.exact.minimum_support_stratum_rows", value: derived-minimum-support-rows),
    (key: "q2.exact.minimum_rows_per_independent_unit", value: derived-minimum-unit-rows),
    (key: "q2.exact.maximum_tolerance_excess", value: derived-maximum-excess),
    (key: "q2.exact.n_independent_units", value: selected-unit-keys.len()),
    (key: "q2.exact.coverage.minimum", value: coverage-minimum),
    (key: "q2.exact.minimum_independent_units", value: minimum-units-required),
    (key: "q2.exact.minimum_rows_per_independent_unit.required", value: minimum-unit-rows-required),
    (key: "q2.exact.absolute_tolerance", value: absolute-tolerance),
    (key: "q2.exact.relative_tolerance", value: relative-tolerance),
    (key: "q2.exact.passed", value: derived-pass),
  ).all(expected => {
    let row = report-store-indexed-row-or-none(fact-index, store-id, expected.key)
    row != none and expected.value != none and if report-value-matches-kind(
      expected.value,
      "number",
    ) and report-value-matches-kind(row.value, "number") {
      calc.abs(row.value - expected.value) <= derived-identity-abs-tolerance
    } else { row.value == expected.value }
  })
  let final-valid = lineage-valid and selected-valid and rows-valid and chain-counts-valid and census-valid and census-summary-valid and support-aggregates-valid and evidence-denominators-valid and aggregate-valid and stratum-aggregates-valid and unit-aggregates-valid and independent-gate-valid and type(
    population-chain-count,
  ) == int and population-chain-count >= selected.len() and selected-chain-count == selected.len() and report-value-matches-kind(
    reported-coverage,
    "number",
  ) and derived-coverage != none and calc.abs(
    reported-coverage - derived-coverage,
  ) <= derived-identity-abs-tolerance and (
    (key: "schema_version", value: q2-certification-receipt-schema),
    (key: "exact_q2.schema_version", value: q2-certification-schema),
    (key: "exact_q2.evidence_semantics.quantity", value: "learned_recursive_q2_target_error_against_factual_dense_successor_control"),
    (key: "exact_q2.evidence_semantics.implementation_recursion_parity", value: false),
    (key: "exact_q2.evidence_semantics.endpoint_policy_evidence", value: false),
    (key: "exact_q2.evidence_semantics.longer_horizon_claim", value: false),
    (key: "bound_contract.learning_contract.objective_profile", value: "qh_dense_valid_fitted_q_v1"),
    (key: "exact_q2.population_census.selection_semantics", value: q2-selection-semantics),
    (key: "exact_q2.population_census.independent_unit_semantics", value: q2-independent-unit-semantics),
    (key: "exact_q2.spec.independent_unit_aggregation", value: q2-independent-unit-aggregation),
    (key: "exact_q2.selection_coverage_passed", value: derived-coverage >= coverage-minimum),
    (key: "exact_q2.support_coverage_passed", value: derived-minimum-support-rows >= 1),
    (key: "exact_q2.independent_unit_gate.passed", value: derived-unit-pass),
    (key: "exact_q2.learned_recursion_passed", value: derived-pass),
  ).all(expected => report-sidecar-indexed-value-matches(
    receipt-index,
    expected.key,
    expected.value,
  )) and facts-match
  final-valid
}

#let report-store-q2-evidence-valid(report, store-id) = {
  let fact-index = report-store-fact-index(report)
  let bundle-row = report-store-indexed-row-or-none(
    fact-index,
    store-id,
    "q2.exact.bundle_manifest_sha256",
  )
  let bundle-manifest = if bundle-row == none { none } else { bundle-row.value }
  let coverage = report-store-number-value(report, store-id, "q2.exact.coverage")
  let minimum-support-rows = report-store-number-value(report, store-id, "q2.exact.minimum_support_stratum_rows")
  let minimum-unit-rows = report-store-number-value(report, store-id, "q2.exact.minimum_rows_per_independent_unit")
  let maximum-tolerance-excess = report-store-number-value(report, store-id, "q2.exact.maximum_tolerance_excess")
  let independent-units = report-store-number-value(report, store-id, "q2.exact.n_independent_units")
  let coverage-minimum = report-store-number-value(report, store-id, "q2.exact.coverage.minimum")
  let independent-units-minimum = report-store-number-value(report, store-id, "q2.exact.minimum_independent_units")
  let unit-rows-minimum = report-store-number-value(report, store-id, "q2.exact.minimum_rows_per_independent_unit.required")
  let passed = report-store-boolean-value(report, store-id, "q2.exact.passed")
  report-store-gated-family-valid(
    report,
    store-id,
    q2-evidence-facts,
    q2-evidence-contract,
    "q2.exact.n_independent_units",
  ) and report-store-fact-values-match(
    report,
    store-id,
    ((key: "q2.exact.rule", value: q2-decision-rule),),
  ) and report-store-q2-certification-receipt-valid(
    report,
    store-id,
  ) and report-sha256-value-valid(bundle-manifest) and (
    coverage,
    minimum-support-rows,
    minimum-unit-rows,
    maximum-tolerance-excess,
    independent-units,
    coverage-minimum,
    independent-units-minimum,
    unit-rows-minimum,
  ).all(value => value != none) and coverage-minimum > 0 and independent-units-minimum >= 5 and unit-rows-minimum >= 1 and passed != none and passed == (
    coverage >= coverage-minimum and
    minimum-support-rows >= 1 and
    independent-units >= independent-units-minimum and
    minimum-unit-rows >= unit-rows-minimum and
    maximum-tolerance-excess <= 0
  )
}

#let report-store-oracle-endpoint-evidence-valid(report, store-id, expected-n) = {
  report-store-analysis-family-valid(
    report,
    store-id,
    oracle-endpoint-evidence-facts,
    oracle-endpoint-evidence-contract,
    expected-n,
    expected-values: ((key: "policy.endpoint_gain.interval_method", value: paired-interval-method),),
    interval-pairs: (
      (low: "policy.endpoint_gain.oracle_one_step.ci_low", high: "policy.endpoint_gain.oracle_one_step.ci_high"),
      (low: "policy.endpoint_gain.oracle_lookahead.ci_low", high: "policy.endpoint_gain.oracle_lookahead.ci_high"),
    ),
    digest-keys: ("policy.endpoint_gain.cohort_sha256",),
    required-source-fragment: "|sidecar:",
  )
}

#let report-store-learned-endpoint-evidence-valid(report, store-id, expected-n) = {
  report-store-analysis-family-valid(
    report,
    store-id,
    learned-endpoint-evidence-facts,
    learned-endpoint-evidence-contract,
    expected-n,
    expected-values: ((key: "policy.endpoint_gain.interval_method", value: paired-interval-method),),
    interval-pairs: (
      (low: "policy.endpoint_gain.learned_q.ci_low", high: "policy.endpoint_gain.learned_q.ci_high"),
    ),
    digest-keys: (
      "policy.endpoint_gain.cohort_sha256",
      "policy.endpoint_gain.learned_q.bundle_manifest_sha256",
    ),
    required-source-fragment: "|sidecar:",
  )
}

#let report-store-endpoint-evidence-valid(report, store-id, expected-n) = {
  report-store-oracle-endpoint-evidence-valid(
    report,
    store-id,
    expected-n,
  ) and report-store-learned-endpoint-evidence-valid(
    report,
    store-id,
    expected-n,
  ) and report-store-facts-share-source(
    report,
    store-id,
    endpoint-evidence-facts,
  )
}

#let report-store-headroom-evidence-valid(report, store-id, expected-n) = {
  let effect = report-store-number-value(
    report,
    store-id,
    "policy.paired_scene_endpoint.effect",
  )
  let ci-low = report-store-number-value(
    report,
    store-id,
    "policy.paired_scene_endpoint.ci_low",
  )
  let minimum-effect = report-store-number-value(
    report,
    store-id,
    "headroom_gate.minimum_effect",
  )
  let passed-matches = report.tables.facts.rows.filter(
    row => row.store_id == store-id and row.key == "headroom_gate.passed",
  )
  report-store-analysis-family-valid(
    report,
    store-id,
    headroom-evidence-facts,
    headroom-evidence-contract,
    expected-n,
    expected-values: (
      (key: "policy.paired_scene_endpoint.interval_method", value: paired-interval-method),
      (key: "headroom_gate.rule", value: headroom-decision-rule),
    ),
    interval-pairs: ((low: "policy.paired_scene_endpoint.ci_low", high: "policy.paired_scene_endpoint.ci_high"),),
    digest-keys: ("policy.paired_scene_endpoint.cohort_sha256",),
    required-source-fragment: "|sidecar:",
  ) and effect != none and ci-low != none and minimum-effect != none and minimum-effect > 0 and passed-matches.len() == 1 and passed-matches.first().value == (
    effect >= minimum-effect and ci-low > 0
  )
}

#let report-store-recovery-evidence-valid(report, store-id, expected-n) = {
  let fraction = report-store-number-value(report, store-id, "policy.q_recovery.fraction")
  let ci-low = report-store-number-value(report, store-id, "policy.q_recovery.ci_low")
  let minimum-fraction = report-store-number-value(report, store-id, "policy.q_recovery.minimum_fraction")
  let passed = report-store-boolean-value(report, store-id, "policy.q_recovery.passed")
  report-store-analysis-family-valid(
    report,
    store-id,
    recovery-evidence-facts,
    recovery-evidence-contract,
    expected-n,
    expected-values: (
      (key: "policy.q_recovery.ratio_definition", value: recovery-ratio-definition),
      (key: "policy.q_recovery.interval_method", value: recovery-interval-method),
      (key: "policy.q_recovery.rule", value: recovery-decision-rule),
    ),
    interval-pairs: ((low: "policy.q_recovery.ci_low", high: "policy.q_recovery.ci_high"),),
    digest-keys: ("policy.q_recovery.cohort_sha256",),
    required-source-fragment: "|sidecar:",
  ) and (fraction, ci-low, minimum-fraction).all(value => value != none) and minimum-fraction > 0 and passed != none and passed == (
    fraction >= minimum-fraction and ci-low > 0
  )
}

#let short-store-label(report, store-id) = {
  let stores = report.tables.stores.rows
  let matches = stores.filter(store => store.store_id == store-id)
  assert(matches.len() == 1, message: "store_id must map to exactly one report store")
  let index = stores.position(store => store.store_id == store-id)
  assert(index != none, message: "store_id has no stable report position")
  let name = matches.first().name
  let profile = if name.contains("realistic") {
    "realistic"
  } else if name.contains("diverse") {
    "diverse"
  } else {
    "store"
  }
  profile + " S" + str(index + 1)
}

#let digest-prefix(value, length: 12) = {
  assert(type(value) == str, message: "manifest digest must be a string")
  if value.len() <= length { value } else { value.slice(0, length) + "…" }
}

#let format-report-value(value, digits: none, unit: none) = {
  let rendered = if value == none {
    [—]
  } else if type(value) == bool {
    if value { [true] } else { [false] }
  } else if digits != none and type(value) in (float, int) {
    str(calc.round(value, digits: digits))
  } else {
    str(value)
  }
  if unit == none or value == none { rendered } else { [#rendered #unit] }
}

// Bundle v2 is generated by aria_nbv.reporting from an immutable Python
// snapshot. Typst validates and selects frozen results; it performs no Python
// execution, network acquisition, aggregation, or figure construction.
#let load-scientific-report(path, evidence-status: "pilot", require-publication: false) = {
  assert(evidence-status in ("pilot", "confirmatory"), message: "invalid scientific report evidence status")
  let report = json(path)
  assert(
    report.at("schema_version", default: none) == scientific-report-schema-version,
    message: "unsupported scientific report schema",
  )
  assert(
    report.at("evidence_status", default: none) == evidence-status,
    message: "scientific report evidence status does not match the requested status",
  )
  if require-publication {
    assert(evidence-status == "confirmatory", message: "publication requires confirmatory scientific evidence")
    assert(report.at("snapshot_sha256", default: "").len() == 64, message: "publication requires snapshot identity")
    assert(report.at("config_sha256", default: "").len() == 64, message: "publication requires config identity")
    assert(report.at("notation_sha256", default: "").len() == 64, message: "publication requires notation identity")
  }
  assert(type(report.at("sources", default: none)) == array, message: "scientific report sources must be an array")
  assert(type(report.at("quantities", default: none)) == array, message: "scientific report quantities must be an array")
  assert(type(report.at("tables", default: none)) == array, message: "scientific report tables must be an array")
  assert(type(report.at("figures", default: none)) == array, message: "scientific report figures must be an array")
  if require-publication {
    assert(report.sources.len() > 0, message: "publication requires at least one scientific evidence source")
  }
  let source-ids = report.sources.map(source => source.at("id", default: none))
  assert(source-ids.all(id => type(id) == str and id != ""), message: "scientific report source IDs must be non-empty")
  assert(source-ids.dedup().len() == source-ids.len(), message: "scientific report source IDs must be unique")
  for source in report.sources {
    assert(source.at("sha256", default: "").len() == 64, message: "scientific report source requires identity digest")
    let provenance = source.at("provenance", default: none)
    assert(type(provenance) == array, message: "scientific report source provenance must be an array")
    if require-publication {
      assert(provenance.len() > 0, message: "publication requires source provenance")
    }
    if require-publication and source.at("kind", default: none) == "wandb" {
      let history-mode = provenance.find(pair => pair.len() == 2 and pair.first() == "history_mode")
      assert(history-mode != none and history-mode.last() == "complete", message: "publication requires complete W&B history")
      let history-complete = provenance.find(pair => pair.len() == 2 and pair.first() == "history_complete")
      assert(history-complete != none and history-complete.last() == true, message: "publication requires exhaustive W&B rows")
    }
  }
  let results = report.quantities + report.tables + report.figures
  if require-publication {
    assert(results.len() > 0, message: "publication requires at least one scientific report result")
  }
  let result-ids = results.map(result => result.at("id", default: none))
  assert(result-ids.all(id => type(id) == str and id != ""), message: "scientific report result IDs must be non-empty")
  assert(result-ids.dedup().len() == result-ids.len(), message: "scientific report result IDs must be unique")
  for result in results {
    if require-publication {
      assert(result.at("source_ids", default: ()).len() > 0, message: "publication results require source provenance")
    }
    assert(
      result.at("source_ids", default: ()).all(id => id in source-ids),
      message: "scientific report result references unknown source",
    )
  }
  report.insert("_bundle_dir", path.split("/").slice(0, -1).join("/"))
  report
}

#let _report-result(results, id, kind) = {
  let matches = results.filter(result => result.at("id", default: none) == id)
  assert(matches.len() == 1, message: "expected exactly one scientific report " + kind + ": " + id)
  matches.first()
}

#let report-value(report, id) = _report-result(report.quantities, id, "quantity")
#let report-table(report, id) = _report-result(report.tables, id, "table")
#let report-figure(report, id) = _report-result(report.figures, id, "figure")
#let report-figure-path(report, id) = {
  let static-path = report-figure(report, id).static_path
  if static-path.starts-with("/") { static-path } else { report._bundle_dir + "/" + static-path }
}
