# Selective review profiles

Read one profile only when its trigger appears in the frozen candidate.

## Computational evidence

For a model, policy, rollout, or result claim, trace the exact state or input,
action or prediction, objective or metric, update or aggregation, and evaluation
boundary. Check that the prose names the same objects as the defining code,
configuration, report, and tests. Record an evidence gap rather than filling a
missing transition from a plausible implementation.

## Display provenance

For a derived figure, table, or displayed equation, trace
`source → transform → aggregate → display → claim`. Check units, denominators,
labels, uncertainty, and any lossy selection at the link that can change the
claim. This profile does not replace the exact source, report, or Typst proof.

These bounded profiles adapt the computational and display-provenance checks in
[WenyuChiou/paper-review at
`cb56a7d`](https://github.com/WenyuChiou/academic-writing-skills/tree/cb56a7d0175f532a6c628c9829e1df824fa938d7/skills/paper-review).
They are prompts for independent review, not scientific truth owners. Their
grounding is registered as `wenyu-academic-writing` in
`.agents/skill-sources.toml` and never activates upstream maintenance.
