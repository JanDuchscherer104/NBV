#import "../../shared/macros.typ": *
#import "../../shared/symbols.typ": symb
#import "../draft_markers.typ": *

= Results <sec:thesis-results>

This chapter contains evidence slots, not expected findings. Every subsection remains unresolved until its tables and figures are generated from frozen manifests and analysis code.

== Oracle and Metric Validity

#validation_todo([Report oracle repeatability, numerical failures, sampling-density sensitivity, mesh-tessellation sensitivity, and the resulting metric noise floor and meaningful-headroom threshold.], source: [RQ1], gate: [frozen oracle-validity analysis])

== Target-Task Coverage

#validation_todo([Report scene and target eligibility, identity-match acceptance, ambiguity and unmatched counts, actor-descriptor availability, and exclusions with denominators.], source: [RQ1 and RQ3], gate: [frozen target-task manifest])

== Candidate Validity and Support

#validation_todo([Report valid-action counts, invalid-reason distributions, candidate-family support, no-valid-action failures, and coverage by scene and target.], source: [RQ4], gate: [frozen candidate manifest])

== Oracle-Lookahead Headroom

#validation_todo([Report paired scene-level endpoint-gain differences between bounded oracle lookahead and one-step oracle greedy, including the 10,000-replicate 95% bootstrap interval and sensitivity to horizon, branch factor, and support.], source: [RQ2], gate: [headroom analysis])

== Learned One-Step Control

#validation_todo([Report oracle-rescored endpoint quality, ranking and calibration diagnostics, failures, and paired comparisons for the learned one-step control.], source: [RQ2 and RQ3], gate: [one-step evaluation])

== Finite-Horizon $Q_H$

#validation_todo([If meaningful oracle headroom exists, report the paired endpoint effect and recovered-headroom fraction for the finite-horizon policy; otherwise state why the conditional analysis is not interpreted.], source: [RQ2], gate: [headroom gate and finite-horizon evaluation])

== Failure and Sensitivity Analysis

#validation_todo([Stratify failures and effects by target observability, candidate support, invalidity, rollout diversity, scene, path length, runtime, and exploratory architecture or representation ablations.], source: [RQ3 and RQ4], gate: [frozen sensitivity analysis])
