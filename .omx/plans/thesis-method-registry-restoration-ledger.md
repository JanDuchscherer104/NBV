# Thesis method-registry restoration ledger

## Scope and decision rule

This ledger audits the substantive removals made by `9876cb1` and `205b8ab` relative to their first parents. The restoration branch is based on `docs-update-latest` (`252f5f5` plus the unrelated planning-only commit `d923d5b`). It applies the following decisions:

- **Restored**: scientifically central contracts, invariants, transformations, objectives, or testable hypotheses now appear in the thesis with explicit implementation and evidence maturity.
- **Compressed**: the scientific content remains, but operational detail, duplicate equations, or repeated rationale was removed.
- **Archived**: useful development history remains outside the submitted scientific narrative.
- **Rejected**: content is deliberately absent because it would overclaim implementation/results, hard-code experiment state, or mix operations with scientific method.

The thesis status vocabulary is descriptive (`implemented`, `partial`, `planned`, `exploratory`; `validated`, `pending`, `conflicted`, `not-applicable`). Existing TODO markers remain actionable and submission-blocking. Unmarked prose is status-neutral.

## Commit `205b8ab`: submission-gated theory and evaluation protocol

| Deleted substantive block | Decision | Current destination | Scientific reason |
|---|---|---|---|
| Introduction claim that the system already constitutes a target-specific finite-horizon planner | Compressed | `01-introduction.typ`; `04-method/04-05-finite-candidate-value-model.typ` | The research question remains, while the one-step implementation and unimplemented finite-horizon scorer are separated explicitly. |
| Fourfold contribution statement naming the residual value model as a contribution | Rejected as achieved contribution | `04-method/04-05-finite-candidate-value-model.typ` as `exploratory/pending` | A proposed residual decomposition is a hypothesis until a trained checkpoint and policy evaluation exist. |
| Introduction implementation TODOs and open questions | Archived | `06-draft-open-work.typ` and this ledger | Operational completion tracking is not scientific method prose. |
| Related-work explanation of target-specific RRI, actor-visible targets, and one-step CORAL control | Restored and compressed | `02-foundations/02-01-related-work.typ`; `04-method/04-05-finite-candidate-value-model.typ` | These relationships delimit the scientific task and the role of the implemented control. |
| Deep Sets, Set Transformer, query-centric geometry, and equivariant-learning bridge | Restored | `02-foundations/02-01-related-work.typ`; `02-foundations/02-02-geometric-learning.typ`; `04-method/04-04-architecture-contract.typ` | The alternatives now form an ordered architecture ladder rather than an implied implementation inventory. |
| Related-work adoption ledger and repeated literature-role table | Compressed | Foundations prose and `tab:geometric-learning-ladder` | Normal citations and one ranked table replace a duplicate adoption catalogue. |
| Seminar oracle substrate versus thesis migration ledger | Archived | This ledger; repository history | Historical migration does not define the current scientific object. |
| Target-matching conflicts and threshold decisions | Rejected as current Method | A short matcher boundary note in `04-method/04-02-descriptor-and-encoding-plan.typ` | The current actor does not implement proposal identity matching; IoU/ambiguity equations would misstate maturity. |
| Experimental objective prose asserting actor-visible target descriptors | Compressed | `03-oracle-and-data-generation`; `04-method/04-01-scene-representation-requirements.typ` | GT-derived V0 task geometry is now identified as privileged, with deployment promotion gated on observed/predicted descriptors. |
| Policy-comparison TODO scaffold | Restored and consolidated | `05-experimental-design/05-03-policy-comparison-and-failure-interpretation.typ` | One evidence-chain TODO and one invariance-suite TODO replace repeated unresolved blocks. |
| Failure interpretation for invalid metric, negligible headroom, and learned-control failure | Restored and compressed | `05-03-policy-comparison-and-failure-interpretation.typ`; `07-discussion.typ` | Conditional scientific interpretations remain without anticipated results. |
| Results placeholder prose and anticipated evidence inventory | Rejected from Results | `05-experimental-design` as validation obligations | Results remain generated from frozen artifacts rather than prose placeholders. |
| Submission layout and marker behavior that hid all proposal material | Replaced | `draft_markers.typ`; submission fixtures | Descriptive statuses survive submission, while actionable TODO markers still fail compilation. |

## Commit `9876cb1`: artifact-driven consolidation

### Introduction and foundations

| Deleted substantive block | Decision | Current destination | Scientific reason |
|---|---|---|---|
| Actor/oracle separation, hard invalid-action semantics, and bounded-oracle scope | Restored/retained | `01-introduction.typ`; `03-oracle-and-data-generation`; `04-method/04-01-scene-representation-requirements.typ` | These are implemented information and action-space contracts. |
| Research questions and objectives | Compressed/retained | `01-introduction.typ`; `05-experimental-design` | Objectives remain conditional on frozen evidence. |
| Full geometric-learning theory exposition | Restored and compressed | `02-foundations/02-02-geometric-learning.typ`; `04-method/04-04-architecture-contract.typ` | The essential permutation, mask, gauge, and provenance invariants are stated once. |
| Candidate-row permutation equation and mask isolation requirements | Restored | `04-method/04-04-architecture-contract.typ` | These are architectural acceptance criteria for any scorer. |
| Query-local geometry, continuous rotations, and gravity-aware frame discipline | Restored | `04-method/04-02-descriptor-and-encoding-plan.typ`; `04-method/04-04-architecture-contract.typ` | They remove arbitrary-world-frame shortcuts without claiming inappropriate full SE(3) invariance. |
| Directional observation-memory rationale | Restored and reduced | `04-method/04-02-descriptor-and-encoding-plan.typ` | The second directional moment is retained with a signed first moment so opposite approaches remain distinguishable; full spherical harmonics remain optional. |
| Architecture ladder from independent rows through point/sparse/equivariant encoders | Restored and ranked | `04-method/04-04-architecture-contract.typ` | A0--A7+ now records escalation and promotion gates without equal-weight endorsement. |
| Foundations adoption matrices and duplicate evidence-chain prose | Compressed | `02-foundations/02-01-related-work.typ`; canonical equations in `docs/typst/shared/equations/` | Literature roles remain; duplicate prose/equations do not. |

### Oracle, target task, and data generation

| Deleted substantive block | Decision | Current destination | Scientific reason |
|---|---|---|---|
| Controlled counterfactual-replay formulation and three-state actor/oracle distinction | Retained/compressed | Chapter 03; `04-method/04-03-candidate-and-replay-contract.typ` | The transition is now split into implemented pose/history/budget/table progression and planned scene-memory update. |
| Target descriptor equation | Restored | `04-method/04-02-descriptor-and-encoding-plan.typ`; canonical `entity.typ` definition | It defines the target-token interface while prose states that current V0 values are GT-derived. |
| Target identity IoU and ambiguity acceptance equations | Rejected as current Method | Explicit boundary note in `04-method/04-02-descriptor-and-encoding-plan.typ`; legacy shared definitions remain only for the historical advisor deck | No actor-visible matcher implements this contract. It may return to Method only with an implemented matcher and validation evidence. |
| Deterministic target cap, threshold, and target-distribution audit recipe | Compressed | Chapter 03 manifest-driven target-task contract | Sampling values must come from resolved manifests, not frozen prose. |
| Candidate-family geometry derivation and shell recipe | Compressed/retained | Chapter 03 candidate contract and shared equations where still referenced | Coordinate semantics and hard validity matter; one historical recipe does not define all experiments. |
| Hard-coded minimum valid count, shell size, and audit-store counts | Rejected from prose | Generated manifests and reporting artifacts | These are run-specific observations/configuration, not method invariants. |
| Oracle-lookahead tree explanation and finite candidate bound | Retained/compressed | Chapter 03 and `05-experimental-design` | Headroom is explicitly scoped to the documented candidate generator and horizon. |
| Log-gain variant and metric-choice deliberation | Archived | Repository history/open-work notes | It is not an active, selected ablation in the present experimental contract. |
| Immutable one-step store versus rollout sidecar distinction | Retained/compressed | `03-03-replay-stores-and-diagnostics.typ`; `04-method/04-03-candidate-and-replay-contract.typ` | The scientific distinction between source evidence and selected-transition replay remains. |
| Local store paths, row counts, shapes, chunks, and audit filenames | Rejected from prose | Resolved reporting artifacts | Hand-copied operational state would stale and could be mistaken for final evidence. |
| Streamlit panel and source-file inventory | Archived | Application/repository documentation | UI navigation does not define the scientific method. |

### Scene representation and descriptors

| Deleted substantive block | Decision | Current destination | Scientific reason |
|---|---|---|---|
| Local EVL support equation and exact grid constants | Restored concept, rejected constants | `04-method/04-01-scene-representation-requirements.typ` | The finite support and persisted voxel transform are factual; dimensions come from manifests/checkpoints. |
| Task-sufficient actor-state/readout interface | Restored | `04-method/04-01-scene-representation-requirements.typ`; `eqs.scene.actor_state_read` | It states what information the planner needs independently of a specific backbone. |
| Scene-memory tokenization and candidate query pools | Restored in minimal form | `04-method/04-01...`; `04-02...`; `04-05...` | The canonical model uses typed shared state tokens and candidate-to-state attention; duplicate pooling formulas were removed. |
| Semidense point memory | Restored as first broad-memory control | `tab:thesis-scene-representation-design-space` | It expands observed-surface coverage cheaply but cannot encode free/unknown space alone. |
| Target-centred EVL relifting and multi-anchor/local-field alternatives | Restored as adaptation ablation | Same design-space table | Promotion is gated on domain shift, support, runtime, and comparison to simpler logged-feature pooling. |
| DINO-on-point formula | Compressed to design-space row | Same design-space table | The concept matters; a decorative token formula does not define an implemented carrier. |
| Sparse ray memory | Restored as planned primary extension | Same design-space table; counterfactual transition prose | It directly addresses occupied/free/unknown distinctions and causal state updates. |
| TSDF/SDF, sparse encoders, object-aware 3DGS, and SceneScript | Restored and ranked | Same design-space table; related work | Each has a concise benefit, cost, evidence state, and promotion gate. |
| Full ray-memory and spherical-harmonic derivations | Not restored | Optional future ablations | They are not selected implementations; the smaller signed first- plus second-moment contract is sufficient now. |
| Candidate reference transform, pose features, target relation, local query frame, and RPE | Restored | `04-method/04-02-descriptor-and-encoding-plan.typ`; canonical spatial equations | These equations define geometric interfaces and testable invariants. |
| Candidate row-token equation | Restored and extended | `04-method/04-02-descriptor-and-encoding-plan.typ`; `eqs.model.candidate_row_features` | Step, requested horizon, and remaining budget are now explicit. |
| Multiple-target parallel evaluation | Restored | `04-method/04-02...`; `04-05...` | Shared scene/candidate encodings can be reused while target--candidate masks isolate tasks. |

### Model, objective, evaluation, and discussion

| Deleted substantive block | Decision | Current destination | Scientific reason |
|---|---|---|---|
| Finite-candidate `Q_H` problem statement | Restored | `04-method/04-05-finite-candidate-value-model.typ` | It is the central planned method, explicitly `planned/pending`. |
| Candidate-to-state cross-attention equation | Restored | Same section; canonical model equation | It is the minimal target-conditioned architecture and preserves independent row queries. |
| Candidate-to-candidate interaction | Restored as ablation only | `04-method/04-04-architecture-contract.typ` | It may model set context but is not required by the core value function. |
| Masked finite-horizon objective and causal horizon semantics | Restored | `04-method/04-05...`; `05-experimental-design/05-02...` | Invalid/padded rows and unavailable future transitions must not enter supervision or bootstrapping. |
| One-step base plus uncentred residual decomposition | Restored as research hypothesis | `04-method/04-05...` | Direct continuous `Q_H` remains the required control; centering is rejected because set composition would alter absolute targets. |
| CORAL threshold interface | Restored as motivated baseline/auxiliary interface | `04-method/04-05...` | The implemented one-step ordinal scorer does not establish the finite-horizon architecture. |
| Freeze, slow-fine-tune, or joint-training choice | Restored as `decision_todo` | `04-method/04-05...` | No choice is claimed without model-selection evidence. |
| Invalid-row learned feasibility head | Restored as planned ablation | `02-foundations/02-02-geometric-learning.typ` | Hard masking remains current invariant; soft rejection cannot replace action admissibility. |
| Exact bootstrap constants and fixed statistical replicate counts | Rejected from prose | Frozen analysis manifests | Statistical choices must be resolved and reported artifact-first. |
| Evidence chain from oracle repeatability through learned-policy evaluation | Restored | `05-experimental-design/05-03...` | It prevents model claims when metric, support, or headroom prerequisites fail. |
| Planned row-shuffle, invalid-isolation, duplicate, valid-count, frame, source, and horizon tests | Restored as `validation_todo` | `05-experimental-design/05-03...` | These are result obligations, not achieved results. |
| Large Results placeholder and anticipated findings | Rejected | Results remain artifact-driven | No unsupported or placeholder result was reintroduced. |
| Failure-conditioned architectural bridges | Restored and ranked | `07-discussion.typ` | Alternatives are promoted only when a diagnosed bottleneck justifies them. |
| Continuous or hierarchical target-then-pose policy equations | Not restored | Concise exploratory discussion paragraph | These policies remain outside the finite-candidate core; full factorization would over-expand the current method. |
| Online RL, simulator, VLM, and other broad bridge catalogue | Compressed/archived | `07-discussion.typ` where causally relevant; otherwise repository history | Only alternatives that constrain present interpretation remain. |
| Preliminary outline, schedule, migration roadmap, and raw open-question inventory | Archived | `.omx/plans`, repository history, and development TODO markers | They govern work but are not thesis scientific content. |
| Expected-contribution conclusion phrased as achieved result | Rejected | Existing conditional conclusion | Contribution claims await frozen evidence. |

## Equation disposition

Canonical restored equations live under `docs/typst/shared/equations/` and are referenced from one source of definition:

- actor-state readout and scene-memory interface;
- target descriptor and target token;
- candidate reference transform, pose features, target relation, local frame, and relative positional encoding;
- candidate-row token and masked candidate-to-state attention;
- implemented replay transition and planned counterfactual scene update;
- finite-horizon return/value and masked training objective;
- one-step/residual and CORAL interfaces;
- signed directional first moment plus second moment;
- oracle-to-policy evidence chain where used.

Not restored into the current Method: target-identity acceptance equations (legacy shared definitions remain referenced only by the historical advisor deck), decorative DINO point-token formula, full ray-memory or spherical-harmonic derivations, continuous-policy factorization, and duplicate definitions formerly spread across `features.typ`.

## Evidence audit policy

- `implemented` requires a code or test pointer; a plan, scaffold, type signature, or `NotImplementedError` is insufficient.
- `validated` requires a frozen scientific artifact pointer. Unit tests support implementation maturity but leave scientific evidence `pending`. A literature citation validates motivation, not local implementation.
- Every planned representation/model block states a promotion gate.
- Normal bibliography citations remain visible in submission mode. Local repository and checked-in TeX provenance appears only in development-mode status metadata.
- No results, performance numbers, rollout sizes, candidate counts, grid dimensions, or statistical constants were copied into the restoration unless they define a mathematical variable rather than a run configuration.
