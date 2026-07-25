#import "../draft_markers.typ": archive_note, thesis_box

== Draft Invariant Trees

#archive_note(
  [Development-only governance map distilled from the ARIA interaction archive. It is included through the gated Development Diary and does not define submission claims, implementation behavior, or a new scaffold policy.],
  source: [deduplicated ARIA user records, plan answers, and exact July owners],
)

This map records how draft evidence should move without turning transcripts,
plans, or retrieval products into authority. The source review covers *3,027
deduplicated ARIA messages*. Its newest transcript user timestamp is
*2026-06-22*; July currentness comes only from the exact owners named below.

=== Authority Tree

#thesis_box([Authority tree], [
- *Scientific meaning*
  - Active Typst owns scientific narrative, research questions, priorities,
    calibrated claim wording, and interpretation boundaries.
- *Executable facts*
  - Python owners define behavior, schemas, and interfaces.
  - Tests define checked invariants and regression boundaries.
  - A prose statement that disagrees with code or tests is stale.
- *Empirical facts*
  - Immutable manifests and evidence bundles own empirical facts.
  - They bind the population, configuration, outputs, metrics, exclusions,
    failures, and digests.
  - A mutable dashboard or remembered run is navigation, not a result.
- *External claims*
  - Exact papers and primary sources support literature claims.
  - The locator and claim strength travel together.
- *Preferences and work*
  - `human_owner_intent` owns Jan-specific preferences.
  - The agents DB owns actionable issues, todos, refactors, and resolutions.
- *Evidence-only surfaces*
  - Prompts and debriefs show how a conclusion was reached.
  - OMX artifacts show planning, review, and acceptance history.
  - Graphify shows source-derived navigation when fresh.
  - None of these surfaces overrides the owners above.
])

#archive_note(
  [User prompts can be high signal, especially for preferences and explicit
  rejections. They can also be ambiguous, task-local, superseded, or wrong.
  This diary does not claim that every prompt is an invariant.],
  source: [transcript evidence boundary],
)

=== Scientific Gate Tree

#thesis_box([Scientific gate tree], [
- *Finite candidates and oracle contract*
  - complete candidate tables, hard masks/reasons, oracle labels, and provenance
  - *then: actor-visible matching and myopic control*
    - match observed or predicted targets to GT evaluation targets
    - validate a target-conditioned one-step scorer on the same support
    - *then: lookahead headroom*
      - compare bounded oracle lookahead with one-step oracle greedy under matched
        roots, candidates, validity rules, and acquisition budgets
      - null headroom is a bounded scientific result, not a reason to add complexity
      - *then: Q_H recovery*
        - train only when measurable non-myopic headroom exists
        - re-evaluate selections with the same frozen oracle
        - *then: confirmatory held-out report*
          - scene-disjoint paired endpoint outcomes and uncertainty
          - exclusions, support, failures, runtime, and storage accounting
- *Deferred branch*
  - online discrete planning follows stable offline finite-candidate evidence
  - continuous control and generic simulator integration follow the online gate
])

=== Evidence Promotion Tree

#thesis_box([Evidence promotion tree], [
- *Prompt, debrief, or retained QMD candidate*
  - *project relevance*
    - reject coincidental ARIA keywords and unrelated project or desktop material
    - *current-owner check*
      - locate the Typst, code/test, manifest, paper, preference, or DB owner
      - *recency and temporal discount*
        - newer evidence receives attention, not automatic authority
        - old evidence remains scoped to its pinned code, data, and configuration
        - *supersession and conflict*
          - prefer an explicit successor; preserve unresolved conflict as conflict
          - *exact-source validation*
            - inspect the paper, executable source, test, manifest, or current owner
            - preserve identifiers that make the check repeatable
            - *disposition*
              - promote a verified durable delta into the exact owner
              - retain useful non-owning material as provenance
              - reject irrelevant, ambiguous, contradicted, or stale material
])

=== Research Iteration Tree

#thesis_box([Research iteration tree], [
- *Research-only synthesis pass*
  - Read exact papers and current owners.
  - Produce hypotheses, discriminating measurements, and stop conditions.
  - A valid pass may conclude that no code change is justified.
- *Measurement-backed implementation pass*
  - Freeze the evaluator, data slice, masks, baselines, and acceptance threshold.
  - Make the smallest change needed to run the discriminating measurement.
  - Lock behavior with tests and freeze evidence provenance.
  - Measure before broadening architecture or data scope.
- *Research-only interpretation pass*
  - Compare the result with the hypothesis and exact papers.
  - Record contradictions, null results, and uncertainty.
  - Choose the next question; do not manufacture an implementation task.
- *Repeat only while information gain is plausible.*
  - Alternate synthesis and measurement-backed implementation.
  - Stop on answered question, invalid premise, absent headroom, or weak ROI.
])

=== Commit Traceability Tree

#thesis_box([Commit traceability tree], [
- *Commit*
  - *changed executable or scientific owner*
    - name the code, test, or Typst owner whose contract changed
  - *evidence and paper identifiers*
    - link the exact paper, test, manifest, bundle, or experiment identifier
  - *relevant agents-DB item*
    - link the existing issue, todo, refactor, or resolution when applicable
  - *links without duplicated truth*
    - keep one owner; connect other surfaces with links
    - do not repeat scientific truth across prompts, debriefs, OMX, Graphify,
      QMD, commits, and Typst
])

=== QMD Migration Ledger

The eleven collapsed QMD pages remain renderable navigation indexes. Their old
blocks fall into four categories: scientific narrative, mathematical contract,
implementation/status detail, and operational snippets. Scientific and
mathematical content moves to the exact Typst owner below; implementation and
status claims defer to code, tests, and immutable evidence; operational snippets
defer to code, tests, commands, or primary sources rather than being copied into
the thesis.

#thesis_box([questions.qmd], [
- *Index contract:* mirrors only canonical RQ1--RQ4 labels and exact Typst
  destinations; online, continuous, simulator, and deployment material appears
  only as deferred-extension navigation, not as RQ5--RQ6.
- *Removed:* duplicate objectives, definitions, RQ wording, boundaries, evidence
  gates, scale constraints, matrix, and deferred-scope claims.
- *Typst:* `01-introduction.typ`; `03-01-state-and-visibility.typ`;
  `03-02-target-task-and-rri-labels.typ`; `03-03-replay-stores-and-diagnostics.typ`;
  `04-01-scene-representation-requirements.typ`; `04-02-descriptor-and-encoding-plan.typ`;
  `04-05-finite-candidate-value-model.typ`; `05-01-objectives-and-hypotheses.typ`;
  `05-02-learning-objective-and-replay-evidence.typ`;
  `05-03-policy-comparison-and-failure-interpretation.typ`; `06-results.typ`;
  `07-discussion.typ`; `08-conclusion.typ`; and development-profile
  `06-draft-open-work.typ` for deferred extensions.
- *Delegated:* KG-writing mechanics and checks stay with guidance, code/tests,
  agents DB, and exact sources.
])

#thesis_box([roadmap.qmd], [
- *Index contract:* navigates the canonical Typst chapter and section sequence.
  Former M0--M8 labels survive only as historical/development provenance and do
  not define a second current milestone taxonomy.
- *Removed:* duplicate outcome, claim ladder, model, evidence flows, milestone
  status, ablations, risks, and reporting contract.
- *Typst:* `01-introduction.typ`; `02-01-related-work.typ`; all three
  `03-oracle-and-data-generation` sections; all five `04-method` sections;
  all three `05-experimental-design` sections; `06-results.typ`;
  `07-discussion.typ`; `08-conclusion.typ`; `appendix/index.typ`; and
  `06-draft-open-work.typ` for the evidence sequence and deferred scope.
- *Delegated:* milestone tasks, standing commands, and status stay with tests,
  manifests, and agents DB.
])

#thesis_box([m1_contract_report.qmd], [
- *Removed:* dated status, evidence snapshot, contract map, passing checks,
  blockers, and command ledger.
- *Typst:* `03-03-replay-stores-and-diagnostics.typ`;
  `04-03-candidate-and-replay-contract.typ`; `06-results.typ`;
  `06-draft-open-work.typ`; and `appendix/index.typ`.
- *Delegated:* transient command output and executable status stay with code,
  tests, stores, and immutable report bundles.
])

#thesis_box([candidate_sampling_target_selection.qmd], [
- *Removed:* target-selection proposals, candidate geometry/orientation,
  validity, mixture, branch selection, target RRI, and Q_H links.
- *Typst:* `03-02-target-task-and-rri-labels.typ`;
  `04-03-candidate-and-replay-contract.typ`; `04-04-architecture-contract.typ`.
- *Delegated:* sampler defaults and reason-code behavior stay with code/tests.
])

#thesis_box([candidate_view_dependence.qmd], [
- *Removed:* candidate interaction theory, architecture, tokens, pair features,
  losses, invariance tests, ladder, and failure mitigations.
- *Typst:* `04-05-finite-candidate-value-model.typ`;
  `05-02-learning-objective-and-replay-evidence.typ`;
  `05-03-policy-comparison-and-failure-interpretation.typ`;
  `06-draft-open-work.typ` for the directional-memory hypothesis.
- *Delegated:* unvalidated mechanisms remain hypotheses rather than migrations.
])

#thesis_box([efm3d_scene_embeddings.qmd], [
- *Removed:* local stack, EVL limitations, evidence maps, semidense/DINO tokens,
  projection, query pooling, ablations, and leakage boundaries.
- *Typst:* `03-01-state-and-visibility.typ`;
  `04-01-scene-representation-requirements.typ`;
  `04-02-descriptor-and-encoding-plan.typ`.
- *Delegated:* vendor and API facts stay with exact EFM3D sources and tests.
])

#thesis_box([nbv_background.qmd], [
- *Removed:* classical geometric, GenNBV, and VIN-NBV background summaries.
- *Typst:* `01-introduction.typ`; `02-01-related-work.typ`.
- *Delegated:* external method claims require exact-paper validation.
])

#thesis_box([rl_planning.qmd], [
- *Removed:* state/action, reward/return, baselines, Q_H training, and acceptance.
- *Typst:* `04-05-finite-candidate-value-model.typ`;
  `05-02-learning-objective-and-replay-evidence.typ`;
  `05-03-policy-comparison-and-failure-interpretation.typ`;
  `06-draft-open-work.typ` for deferred online scope.
- *Delegated:* trainer and storage details stay with code, tests, and manifests.
])

#thesis_box([rri_theory.qmd], [
- *Removed:* seminar delta, target error/gain, scene-RRI role, and NBV objective.
- *Typst:* `02-03-reconstruction-metrics.typ`;
  `03-02-target-task-and-rri-labels.typ`.
- *Delegated:* metric implementation stays with evaluator code/tests.
])

#thesis_box([semi-dense-pc.qmd], [
- *Removed:* inverse-distance representation, multiview visibility, Aria files,
  EFM3D context, practical guidance, and GT comparison.
- *Typst:* `03-01-state-and-visibility.typ`;
  `04-01-scene-representation-requirements.typ`;
  `03-02-target-task-and-rri-labels.typ`.
- *Delegated:* file-format and vendor facts stay with primary sources and code.
])

#thesis_box([surface_metrics.qmd], [
- *Removed:* accuracy, completeness, Chamfer, F-score, point-to-mesh witnesses,
  TSDF diagnostics, examples, and computation notes.
- *Typst:* `02-03-reconstruction-metrics.typ`.
- *Delegated:* library-specific computation stays with evaluator code/tests.
])

=== Notes That Must Not Become Truth

#archive_note(
  [The accepted July-14 scaffold bundle is superseded and retained only as
  provenance. Historical M0 and M1 paths are task-local rather than current
  scientific priorities. Unrelated desktop-restoration and PRML transcript
  extraction is rejected rather than promoted into ARIA-NBV owners.],
  source: [OMX successor registry and transcript relevance review],
)

- *Superseded notes* remain provenance only and link to their successor.
- *Task-local notes* expire with the task unless promoted to an exact owner.
- *Untrusted notes* may suggest a search but cannot support a claim.
- Prompt volume is not corroboration; deduplication is not validation.
- July truth comes from exact current owners, not from the June prompt cutoff.
- The current custom `S -> G` Graphify policy is under active upstream-first
  review. This diary records that review state and deliberately does *not*
  canonize the policy.
