#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": *
#import "@preview/booktabs:0.0.4": *

== Finite-Candidate Value Model

// source: .agents/memory/state/DECISIONS.md:97-99 fixes finite-candidate #symb.rl.qh as a hard thesis deliverable; current wording instantiates it as candidate-to-state queries first.
// source: aria_nbv/aria_nbv/vin/model_v3.py:1-64 fixes VINv3 as the myopic one-step baseline/control, not the final multi-step model.
The value-model hypothesis is that a masked finite-candidate model can recover positive oracle-lookahead headroom from actor-visible state. #symb.rl.qh maps each valid candidate row to a finite-horizon value using actor-visible scene, target, selected-history, budget, candidate, mask, and reason-code features. Its outputs select actions, but thesis evidence comes from oracle re-scoring of the selected trajectories. The model is therefore judged as a planner over a documented finite action table, not as a proxy reconstruction metric or an ungrounded scene encoder.

The model class follows the structure of the decision problem. The action space is a masked finite set of candidate views, each defined relative to a target, selected history, and partially observed geometry. Geometric deep learning supplies vocabulary for these regularities without committing the thesis to a full equivariant tensor network @GeometricDeepLearning-bronstein2021. Candidate-row permutation requires equivariant per-candidate outputs; local camera and target frames reduce dependence on global coordinates; $bb(S)^2$ visibility memory records where the target has already been observed; and the target record acts as the query that determines which reconstruction errors matter.

// source: docs/contents/theory/candidate_view_dependence.qmd:405-421 critiques absolute-label contamination and generator overfitting.
// source: aria_nbv/aria_nbv/rollouts/zarr_store.py:224-260 and aria_nbv/aria_nbv/rollouts/zarr_store.py:2534-2603 show that replay already exposes masks, provenance, target gains, and selected-transition TD fields.
The architecture critique is therefore simple: the first serious model should not be a monolithic transformer over every available tensor or over arbitrary candidate rows. The clean object is a calibrated one-step target utility field plus an uncentred finite-horizon residual from candidate-to-state evidence. The one-step field owns immediate target-gain calibration; the residual owns downstream effects from candidate regeneration, selected-history geometry, occlusion, free/unknown evidence, and support overlap. Unrelated sampled rows should not change the physical value of candidate $q_i$ except through explicitly modeled support or policy-context ablations.

$
  #eqs.rl.qh_residual_decomposition
$

The residual can be kept small with a norm penalty or dataset-level regularization, but it should not be exactly mean-centred within each sampled candidate table. Per-set centering changes absolute Q values when duplicate or unrelated valid rows are added, which is unsafe for TD targets. Candidate-candidate interaction remains useful for policy logits, diversity, or top-$k$ selection ablations, but the default finite-horizon value head stays in continuous target-gain units. Recent object-centric view-planning work reinforces this separation: target-centric visibility and feasibility should be explicit scoring factors, while difficulty, reachability, budget, and object saturation must be reported separately because they can change planner rankings and failure modes @OANBV-hu2026 @ObjViewBench-pan2026.

#validation_todo(
  [Do not use OANBV or ObjViewBench to support the uncentred-residual decomposition. They support visibility, feasibility, difficulty, and reporting factors; the residual architecture needs its own derivation or ablation evidence.],
  source: [literature cross-check; bibliography records],
  gate: [architecture claim and citation audit],
)

#prune_todo(
  [The adopt/reject architecture table below is a design memo. Replace it with the final implemented architecture and concise rationale; move rejected alternatives to ablations or Discussion only when evidence makes them relevant.],
  source: [thesis peer review],
  gate: [final model implementation freeze],
)

#figure(
  text(size: 8.6pt, table(
    columns: (0.68fr, 1.22fr, 1.28fr),
    toprule(),
    table.header([*Design principle*], [*Adopt in #symb.rl.qh*], [*Reject or defer*]),
    midrule(),
    [Calibrated absolute field],
    [Keep a one-step target-gain head that can be evaluated candidate-by-candidate under fixed masks.],

    [Letting attention over unrelated rows redefine the absolute immediate-RRI label.],
    [Finite-horizon residual context],
    [Use candidate-to-state cross-attention for the default residual; regularize residual magnitude without exact per-set centering.],

    [A pooled scene embedding with no per-row path, exact candidate-table mean centering for TD values, or unmasked invalid-row attention.],
    [Typed relative geometry],
    [Encode target-current-candidate-history relations in local frames; use QCNet-style RPE as an ablation.],

    [Claiming full global $op("SE")(3)$ equivariance for an egocentric, gravity-aligned, frustum-limited task.],
    [Directional visibility],
    [Represent selected history on $bb(S)^2$ and keep it distinct from generic pose tokens.],

    [Collapsing target-local observability into a scalar distance or sampler family prior.],
    [Support and difficulty reporting],
    [Report EVL extent, semidense support, reachability, validity, budget, and target saturation bins.],

    [Using support, Fisher/coverage proxies, or target area as the thesis reward instead of oracle target-RRI.],
    [Late geometric transformers],
    [Treat EGNN, SE(3)-Transformer, and GATr-style equivariant modules as support-encoder or candidate-graph ablations.],

    [Making exact equivariance the first thesis claim before the replay/mask/target-RRI contract is stable @EGNN-satorras2021 @SE3Transformer-fuchs2020 @GATr-brehmer2023.],
    bottomrule(),
  )),
  caption: [Architecture critique distilled into a conservative design order. The clean first model preserves a calibrated candidate-local field and allows actor-visible state, history, and geometry context to explain finite-horizon residual value under explicit masks and evaluation gates.],
) <tab:thesis-qh-clean-architecture>

The one-step target scorer is adapted to counterfactual rollout rows rather than reusing the seminar @view-introspection-network:short checkpoint unchanged. It remains myopic and predicts immediate target-specific @relative-reconstruction-improvement:short evidence for each candidate; the seminar VINv3 scorer is therefore a control architecture and implementation substrate, not already a target-conditioned finite-horizon #symb.rl.qh result. #symb.rl.qh is residual around this calibrated base, with an uncentred continuous residual head as the canonical finite-horizon value definition. The myopic scorer uses the CORAL ordinal-regression interface of Cao et al., adapted to ARIA-NBV's skewed oracle @relative-reconstruction-improvement:short labels @CORAL-cao2019:

#validation_todo(
  [Establish and report the target-specific label distribution before calling it skewed. VIN-NBV motivates ordinal calibration, but scene-level or source-paper label behavior is not evidence for the final target-task distribution.],
  source: [VIN-NBV literature review; thesis peer review],
  gate: [target-label distribution audit],
)

$
  #eqs.rl.qh_coral_interface
$

ARIA-NBV's adaptation is in the binning and decoding around that interface. Continuous oracle target gains are fitted to empirical quantile edges $tau_1 <= dots <= tau_(K-1)$, and each sample receives the ordinal label $y = sum_(j=1)^(K-1) bb(1)[r^e > tau_j]$. CORAL levels are threshold indicators $ell_k = bb(1)[y > k]$ for $k=0,dots,K-2$. The scorer then decodes logits both as cumulative probabilities $P(y>k)=sigma(o_k)$ and as a ranking proxy $E[y]=sum_k sigma(o_k)$; when calibrated bin representatives are available, the expectation over $u_k$ maps the ordinal distribution back to target-gain units. This preserves the VIN-NBV ordinal-ranking precedent while making calibration, bin drift, and residual #symb.rl.qh recovery explicit ARIA-NBV diagnostics.

Training is staged to preserve the residual interpretation: train and calibrate $hat(r)_psi^e$, then freeze or slow-finetune it while fitting residual #symb.rl.qh in continuous return units with Huber or distributional/quantile losses, and finally ablate whether end-to-end fine-tuning improves oracle-evaluated policy performance. CORAL remains the one-step ranking/calibration interface; finite-horizon #symb.rl.qh must preserve the metric structure of additive returns. This also keeps the educational story clean: VINv3 answers "which single candidate looks good now?", while #symb.rl.qh answers "which first action has the best bounded downstream target gain under the same finite candidate and mask contract?".

The descriptor protocol in @tab:thesis-descriptor-schema supplies the model input: actor-visible target token, scene/support memory, selected-history state, candidate self tokens, query-local relations, ray queries, hard masks, and reason codes. The default candidate-query encoder is candidate-to-state cross-attention, so each physical candidate reads the same fixed target, map, history, budget, and local-EVL tokens without unrelated candidate rows redefining its absolute value:

$
  #eqs.model.qh_candidate_state_cross_attention
$

The candidate-query architecture in @fig:qh-candidate-query-architecture expands the same contract into the default value-model hypothesis: one physical candidate row queries a fixed actor-visible state, optional set context remains an ablation, and oracle labels only supervise losses and evaluation outside the actor-input graph.

#figure(
  image(
    "../../figures/qh_candidate_query_architecture.pdf",
    width: 100%,
  ),
  caption: [Default candidate-query #symb.rl.qh architecture contract. Actor-visible target, scene, history, budget, candidate self/relation, mask, and provenance descriptors feed a candidate-to-state query encoder; the residual value head decodes finite-horizon values only for hard-valid rows, while oracle target @relative-reconstruction-improvement:short, TD targets, and endpoint metrics supervise losses and evaluation outside the actor-input graph. Optional set context is an ablation rather than the default source of absolute value calibration.],
) <fig:qh-candidate-query-architecture>

No-interaction candidate MLP scoring and candidate-to-state cross-attention are required baselines before attributing gains to masked Set Transformer interaction or QCNet-style RPE. For immediate target-specific @relative-reconstruction-improvement:short, the physical oracle label of candidate $q_i$ does not change when unrelated rows are added to $cal(Q)_t$. Candidate interaction can therefore corrupt absolute calibration if it replaces the independent scorer. The safer finite-horizon ablation lets candidate context influence policy logits, diversity, or a separately regularized residual, but not an exact per-set mean-centred TD value.

The value head is an uncentred residual decomposition over valid actions, with residual regularization rather than exact candidate-table centering:

$
  #eqs.rl.qh_uncentered_residual
$

#figure(
  table(
    columns: (0.62fr, 1.76fr),
    toprule(),
    table.header([*Model role*], [*Content*]),
    midrule(), [Hypothesis model],
    [adapted target-conditioned myopic scorer, candidate-to-state residual #symb.rl.qh in continuous return units, hard masks/reasons, matched-budget oracle re-scoring],
    [Required controls],

    [independent candidate MLP, calibrated myopic scorer, and candidate-to-state cross-attention without candidate-candidate self-attention],
    [Ablations],

    [pooled DeepSets context, masked Set Transformer policy context, QCNet-style candidate-local RPE, Fisher/SCONE support-overlap attention bias, $bb(S)^2$ memory variants, EGNN-style candidate graph, privileged-teacher distillation, distributional #symb.rl.qh heads],
    [Architecture ladder],

    [A0 independent scorer; A1 candidate-to-state cross-attention; A2 pooled DeepSets context; A3 masked Set Transformer policy/context ablation; A4 query-local relative bias; A5 Fisher/SCONE overlap bias; A6 distributional or quantile #symb.rl.qh],
    [Bridges],

    [Hestia-style target-then-pose policies, online discrete interaction, external mesh/oracle-compatible simulators, sparse/point backbones],
    bottomrule(),
  ),
  caption: [Value-model hypothesis, controls, and ablations. Dense @ground-truth:short candidate renders may supervise later ablations, while learned policy inputs use the configured state and target-task descriptors.],
) <tab:thesis-value-ladder>

#prune_todo(
  [The hypothesis/control/ablation/bridge ledger above is not a final Method description. Replace it with the trained architecture, loss, target-network update, masks, hyperparameters, and frozen/fine-tuned components; retain only executed ablations.],
  source: [thesis peer review],
  gate: [final model and ablation inventory],
)

#impl_todo(
  [Confirm which architecture ladder levels are implemented, planned, or deferred once the final code state is frozen.],
  source: [advisor handout; proposal method],
  gate: [method implementation audit],
)
