# Empirical Reporting And Reproducibility

Use this reference for experimental design, results, discussion, and any prose
that presents measured behavior.

## Core Invariant

Every empirical sentence must resolve four questions: what population and
protocol does it cover, which artifact supports it, how uncertainty was
estimated, and which immutable run identity reproduces it. If any answer is
missing, write the statement as a hypothesis, pilot observation, limitation,
or unresolved result rather than a general finding.

## Experimental Contract

Freeze before confirmatory analysis:

- data version, eligible population, split unit, exclusions, preprocessing,
  target and candidate protocols, and leakage checks;
- method versions, hyperparameters, selection criteria, stopping rules,
  baselines, ablations, tuning budgets, and information available to each
  policy;
- primary estimands and metrics, aggregation unit, independent runs or seeds,
  uncertainty intervals, minimum meaningful effect, and multiplicity policy;
- run manifests, commands, environment and hardware metadata, raw artifacts,
  derived tables and figures, and the transformation linking them.

Do not select a method on confirmatory evidence and then report that evidence as
an unbiased evaluation. Keep model and analysis choices behind a validation-to-
test firewall.

## Fair Comparisons

Use the same eligible tasks, candidate support, acquisition budget, validity
rules, oracle evaluation, information boundary, and comparable tuning effort.
Report any unequal compute, privileged inputs, early stopping, missing runs, or
excluded failures. A screenshot, one seed, training loss, or predicted value is
not a population-level policy result.

## Results And Discussion

- Results state the estimand, comparison, magnitude, uncertainty, denominator,
  aggregation unit, and artifact locator before interpretation.
- Distinguish statistical uncertainty from practical relevance and systems
  feasibility.
- Report negative results and failure modes under the same protocol as positive
  results; do not silently omit failed or resource-constrained runs.
- Discussion separates measured findings, plausible mechanisms, alternative
  explanations, limitations, and future tests.
- Figures and tables are self-contained and traceable to immutable inputs and a
  reproducible generation command.

## Reproducibility Record

A reader should be able to move from a result sentence to the table or figure,
analysis output, run manifest, raw store, exact code revision, command,
environment, data identity, and expected output. Record compute and storage cost
when they materially constrain feasibility or comparison fairness.

Venue and institutional policies are dynamic external constraints. Check their
current official versions when preparing a submission; do not hard-code them as
the scientific owner of this thesis.
