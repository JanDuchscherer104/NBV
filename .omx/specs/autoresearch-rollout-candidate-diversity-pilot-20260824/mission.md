# Mission: rollout candidate diversity pilot audit

## Objective

Reconstruct how the 100 one-snippet-per-scene pilot rollouts were generated,
measure their diversity, realism, and data-quality failure modes, and recommend
the highest-ROI generation changes and bounded follow-up experiments before
large-scale generation or training.

## Success criteria

- Identify the exact pilot artifacts, revisions, commands, configuration,
  effective parameters, scene/snippet selection, and candidate families.
- Quantify the available pilot evidence, including view jitter, pose and view
  diversity, degeneracy/duplication, validity, target/candidate balance, and
  other measurable realism or quality risks.
- Trace every consequential claim to current code, configuration, tests, or
  artifact metadata; distinguish fact, inference, literature evidence, and
  untested hypothesis.
- Link every related live GitHub issue and every relevant repository config or
  executable owner used by the report.
- Use primary external sources to justify high-ROI candidate-generation
  improvements, and state where the external evidence does not directly prove
  an ARIA-NBV outcome.
- Produce a prioritized intervention and experiment matrix with expected
  benefit, cost/risk, exact owner/parameter, measurable acceptance criteria,
  and a clear pre-scale launch gate.

## Scope

- Read-only diagnosis of current artifacts, source, configs, tests, Git/GitHub
  state, repository literature, and external primary sources.
- The only durable writes are autoresearch artifacts under this mission root
  and its lifecycle state file.
- No generator, thesis, configuration, rollout artifact, Git branch, or GitHub
  issue/PR mutation is authorized in this run.

## Earliest redirect condition

If the claimed 100 pilot artifacts cannot be uniquely identified from current
workspace or recorded provenance, the report must stop short of artifact-level
claims, document every candidate location checked, and specify the minimum
missing path/provenance needed to continue.

## Validation

Validation mode is `prompt-architect-artifact`. Completion requires an
independent architect approval recorded in `result.json` for `report.md`.
