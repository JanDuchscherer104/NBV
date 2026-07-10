# Section-By-Section Thesis Peer-Review Log

Date: 2026-06-18

Purpose: close the arch-goal evidence gap by recording an explicit review of
every active thesis section and the whole-document coherence after the
autoresearch and patch pass.

## Include Graph Reviewed

- Body includes: `docs/typst/thesis/main.typ:51-55`
- Nested background includes: `docs/typst/thesis/sections/02-background.typ:9-11`
- Nested method includes: `docs/typst/thesis/sections/03-method.typ:11-13`
- Appendix include: `docs/typst/thesis/appendix/index.typ:9`

## Section Review

| Surface | Review Question | Evidence Checked | Finding | Result |
|---|---|---|---|---|
| `main.typ` | Does the active thesis body have the right order and avoid planning material after the conclusion? | `main.typ:37-55`, appendix include | Abstract states target-conditioned finite-candidate RRI claim; body ends at Conclusion; draft/open work moved to Appendix. | Pass |
| `01-introduction.typ` | Does it state problem, gap, thesis contribution, and scope boundaries without overclaiming? | Active perception/VIN-NBV framing, finite-candidate thesis box, actor-visible V1 caveat | The introduction now separates oracle target-task sampling from V1 actor-visible target descriptors and keeps GenNBV/Hestia/3DGS as bridge pressure. | Pass |
| `02-background.typ` | Does it ground ARIA/ASE/EFM3D roles and route related/theory material cleanly? | Background substrate paragraph; includes of related work and geometric theory; source-positioning table | EVL is local target/support evidence, not full long-horizon memory. The chapter includes both related work and dedicated theory. | Pass |
| `02-01-related-work.typ` | Are claims close to citations and bounded to ARIA-NBV? | Classical NBV, VIN-NBV/CORAL, Aria/ASE/EFM3D, coverage/3DGS, continuous-policy, set/geometric, offline RL paragraphs | Citation clusters were split by contribution. Offline value-learning, support constraints, sequence models, and recurrence are scoped as controls/bridges. | Pass |
| `02-02-geometric-learning.typ` | Does it synthesize the literature into a theory section rather than a shopping list? | Candidate-row equivariance, gauge discipline, directional memory, architecture ladder tables | New section turns Deep Sets / Set Transformer / QCNet / GDL / equivariance literature into a testable symmetry and architecture contract. | Pass |
| `03-01-formal-state.typ` | Does the formal state split keep actor-visible, counterfactual, and oracle-only state distinct? | Included by `03-method.typ`; state equations and prose | Existing state split remains consistent with current method/data-generation prose; no extra patch required. | Pass |
| `03-02-data-generation.typ` | Does data generation own target selection and adapt seminar content without drift? | Target-task sampler, seminar-substrate table, conflict marker, target-RRI equations, decision/validation TODOs | Automatic target selection is oracle/data-generation. Seminar RRI/CORAL/offline-store material is included as substrate/provenance, not current target-Q_H evidence. | Pass |
| `03-method.typ` | Does method cover backbone, candidate/replay, geometry tests, and value model with clear implementation vs hypothesis boundaries? | Backbone requirements, descriptor plan, candidate/replay contract, architecture tests, finite-candidate value model | EFM3D/EVL remains OBB-capable anchor; free-shell sampler is demoted to ablation; all-candidate oracle scoring vs selected-transition persistence is clarified; VINv3 is myopic substrate. | Pass |
| `04-evaluation.typ` | Does evaluation define objectives, evidence gates, policy comparisons, and failure interpretation? | Objective matrix, support-coverage table, seminar-to-thesis evidence matrix, policy table, validation TODOs | Evaluation requires target matching, myopic scorer calibration, replay support, oracle headroom, paired policy comparison, and manifest-backed scale before final claims. | Pass |
| `05-conclusion.typ` | Does conclusion preserve conditional claims and bridge boundaries? | Conditional success / negative-result / failure-analysis paragraphs | Conclusion does not force a positive planning result; continuous/online/semantic/3DGS bridges are scoped after target-RRI finite-candidate evidence. | Pass |
| `06-draft-open-work.typ` | Is draft/open material kept out of final numbered body while preserving source content? | Appendix inclusion and dashy markers | Draft intake remains available in appendix with explicit TODO/decision/question markers; it no longer interrupts the main thesis body after conclusion. | Pass |
| `appendix/index.typ` | Does appendix avoid raw TODO text and use dashy helpers? | `appendix/index.typ:1-9` | Raw placeholder was replaced by `#impl_todo`; draft/open-work intake is included as supplementary material. | Pass |

## Total Coherence Review

The patched thesis now follows one spine:

1. Motivation: target-conditioned quality-driven NBV over finite candidate views.
2. Background: Aria/ASE/EFM3D substrate, VIN-NBV RRI precedent, bounded bridge literature.
3. Theory: candidate-set geometric learning, permutation/mask/local-frame/directional-memory contract.
4. Method: actor/oracle state split, oracle target-task data generation, target-RRI labels, candidate/replay rows, geometric acceptance tests, residual `Q_H`.
5. Evaluation: myopic scorer, oracle headroom, `Q_H` recovery, paired policy comparison, failure interpretation.
6. Conclusion: conditional success, negative-result reporting, and bridge boundaries.

This coherence check was challenged by a read-only architect subagent, which
returned `CLEAR` and found no objective blocker in the active thesis body.

## Residual Risks

- The thesis still intentionally contains dashy TODO markers for final
  thresholds, manifest-backed counts, final experiment tables, appendix details,
  and representation ablation evidence.
- Those markers are expected under this goal because the objective asked to flag
  current inconsistencies and TODOs rather than complete all future research.
