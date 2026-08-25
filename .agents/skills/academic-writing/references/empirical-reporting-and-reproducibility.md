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
  uncertainty intervals, the variation source and construction method they
  summarize, their assumptions, minimum meaningful effect, and multiplicity
  policy;
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

## Venue Review Overlay

When preparing work for external ML review, use the target venue's current
official checklist as a nonbinding overlay:

- name the source of variation, interval or error-bar method, and assumptions
  for central quantitative results, or justify why uncertainty is inapplicable;
- record per-run and aggregate compute, including material preliminary and
  failed experiments when they affect reproducibility or feasibility;
- state artifact availability, licenses, and access restrictions without
  promising that every dataset, model, or code artifact can be public.

Primary-source basis checked 2026-08-25: the
[NeurIPS Paper Checklist](https://neurips.cc/public/guides/PaperChecklist),
[ICLR 2026 Author Guide](https://iclr.cc/Conferences/2026/AuthorGuide),
[ICML 2026 Author Instructions](https://icml.cc/Conferences/2026/AuthorInstructions),
[JMLR Author Information](https://jmlr.org/author-info.html), and
[TMLR Author Guide](https://jmlr.org/tmlr/author-guide.html). Recheck the
actual venue and year before submission. Venue mechanics such as page limits,
anonymization, or templates are not thesis requirements.

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

## HM/FK07 Branch

For an HM/FK07 thesis or assessment, also apply the dated
[HM scientific-practice overlay](hm-scientific-practice.md). It owns the
institution-specific documentation, retention, access, licensing, and
AI-program disclosure checks; exact thesis sources and experiment artifacts
remain authoritative.

Venue and institutional policies are dynamic external constraints. Check their
current official versions when preparing a submission; do not hard-code them as
the scientific owner of this thesis.
