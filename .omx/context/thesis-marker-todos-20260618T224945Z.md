# Thesis Marker TODO Inventory

Generated: 2026-06-18T22:49:45Z

Scope: remaining explicit thesis draft-marker macros after the plain `// TODO`
cleanup. These markers are intentional gates, not accidental prose residue.
Keep them until the owning evidence, decision, or final-writing pass is complete.

Extraction command:

```bash
rg -n '//\s*TODO|TODO\(|#(validation|research|decision|impl|question|conflict)_todo' docs/typst/thesis/main.typ docs/typst/thesis/sections
```

Plain inline TODO comments: none found.

## Final Writing And Submission Gates

- `docs/typst/thesis/main.typ:41`: German abstract translation or final local-language policy.
- `docs/typst/thesis/main.typ:47`: acknowledgements close to submission.
- `docs/typst/thesis/main.typ:50`: AI-assisted-tools transparency statement against final institutional requirements.
- `docs/typst/thesis/sections/01-introduction.typ:22`: final title, RQ wording, and evidence scale after freeze.
- `docs/typst/thesis/sections/05-conclusion.typ:12`: rewrite conclusion after final evidence exists.
- `docs/typst/thesis/sections/06-draft-open-work.typ:54`: resolve proposal-date/current-roadmap conflict.
- `docs/typst/thesis/sections/06-draft-open-work.typ:94`: decide whether the final chapter skeleton stays here or moves into a detailed outline.

Primary DB owners:

- `todo-049`: advisor-grade thesis seed polish/freeze.
- `todo-050`: bibliography and citation metadata audit.
- `todo-055`: doc spine and source-backed wording refinement.

## Target And Rollout Protocol Gates

- `docs/typst/thesis/sections/03-02-data-generation.typ:53`: do not treat old seminar evidence as current thesis evidence.
- `docs/typst/thesis/sections/03-02-data-generation.typ:134`: lock identity IoU, ambiguity gap, per-class caps, area/support filters, clipping, and sampling gamma.
- `docs/typst/thesis/sections/06-draft-open-work.typ:104`: lock final scene-level split and acceptable scale fallback.
- `docs/typst/thesis/sections/06-draft-open-work.typ:106`: lock target-match thresholds, ambiguity gap, target eligibility, and target-invalid reporting.

Primary DB owners:

- `todo-080`: target-first RRI theory and advisor alignment.
- `todo-085`: target sampling coverage audit.
- `todo-084`: scene-level split manifests.
- `todo-092`: oracle target-task sampler in rollout generation.

## Evidence And Validation Gates

- `docs/typst/thesis/sections/03-02-data-generation.typ:140`: replace placeholder scale counts with generated-manifest counts.
- `docs/typst/thesis/sections/02-02-geometric-learning.typ:114`: add row-shuffle, mask, translation, and rotation stress results.
- `docs/typst/thesis/sections/03-method.typ:202`: insert feature-bank and encoder ablation evidence.
- `docs/typst/thesis/sections/04-evaluation.typ:160`: replace planned scale bars with generated manifest statistics.
- `docs/typst/thesis/sections/04-evaluation.typ:188`: replace evaluation placeholders with final tables and failure cases.
- `docs/typst/thesis/sections/06-draft-open-work.typ:114`: validate Rerun examples, replay integrity, shuffled-candidate evaluation, duplicate-row robustness, and valid-count sensitivity.

Primary DB owners:

- `todo-018`: experiment registry and final claim matrix.
- `todo-037`: Q_H evidence report and success bar.
- `todo-048`: controlled VIN ablation and calibration gate.
- `todo-087`: rollout readiness/preflight report.
- `todo-091`: H=1 target-label rollout profile.

## Architecture, Q_H, And Bridge Gates

- `docs/typst/thesis/sections/03-method.typ:282`: decide final placement for Fisher, SCONE, QCNet, and ablation hypotheses.
- `docs/typst/thesis/sections/03-method.typ:388`: audit implemented, planned, and deferred architecture-ladder details.
- `docs/typst/thesis/sections/06-draft-open-work.typ:108`: lock whether the myopic scorer freezes, slow-finetunes, or end-to-end fine-tunes when fitting Q_H.
- `docs/typst/thesis/sections/06-draft-open-work.typ:110`: decide whether privileged critic signals can be used without weakening non-privileged policy claims.
- `docs/typst/thesis/sections/06-draft-open-work.typ:112`: decide whether RGB, semantics, or 3DGS enter the thesis core or stay bridge studies.

Primary DB owners:

- `todo-037`: Q_H evidence report and success bar.
- `todo-052`: Q_H baseline and bridge design.
- `todo-038`: simulator/core-vs-stretch decision.
- `todo-048`: controlled VIN ablation and calibration gate.

## Literature And Future-Work Routing Gates

- `docs/typst/thesis/sections/02-background.typ:61`: after the final framing decision, decide whether bridge literature stays or moves to future work.
- `docs/typst/thesis/sections/06-draft-open-work.typ:120`: route Habitat, Isaac, 3DGS, SceneScript, real-device AR, and human-in-the-loop material to bridge, future-work, appendix, or deletion.

Primary DB owners:

- `todo-038`: ASE core versus external simulator/data stretch decision.
- `todo-055`: source-backed wording and evidence-gate refinements.
- `todo-050`: bibliography and citation metadata audit.

## Operating Rule

Do not remove marker macros just to make grep clean. Replace a marker only when
the corresponding evidence, protocol decision, or final-writing pass is complete,
and then resolve or update the owning agents-db record.
