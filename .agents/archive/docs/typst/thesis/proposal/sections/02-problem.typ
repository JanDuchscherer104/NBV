#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "_style.typ": *

= Problem and Research Contract

ARIA-NBV is a target-conditioned, finite-candidate #gls("next-best-view") problem in the
Project Aria / ASE / EFM observation regime. The thesis is deliberately not a
first-order continuous-control claim: it tests whether bounded planning over a
finite valid candidate table improves target reconstruction quality beyond
myopic view selection.

The actor-visible state at decision step $t$ is

$
  #symb.rl.s_obs =
  (#symb.obs.points_semi_t, #symb.vin.field_evl_t, #symb.entity.target_hyp_pred_t,
    bold(h)_t, b_t),
$

where #symb.obs.points_semi_t is the accumulated semi-dense or fused point evidence,
#symb.vin.field_evl_t is the frozen local EFM/EVL evidence field, #symb.entity.target_hyp_pred_t are
observed or predicted target hypotheses, $bold(h)_t$ is selected-view history, and
$b_t$ is remaining budget. The oracle state augments this with ASE GT assets:

$
  #symb.rl.s_oracle =
  (#symb.rl.s_obs, #symb.ase.mesh, {#symb.ase.mesh_target}_(e in cal(E)),
    {#symb.obs.points_cand_ti}_(i=1)^(N_q)).
$

GT meshes, GT OBBs, GT crops, GT semantic labels, and all-candidate GT renders
are label/evaluation assets only. They are not V1 actor inputs.

The planner state is

$
  #symb.rl.s_cf0 =
  (#symb.vin.field_evl_0, #symb.obs.points_t, #symb.entity.target_desc, bold(h)_t, b_t,
    #symb.rl.candidate_table, #symb.rl.candidate_mask, #symb.rl.invalid_reasons),
$

where #symb.rl.candidate_table $={#symb.rl.candidate_qti}_(i=1)^(N_q)$ is the finite candidate table,
$m_(t,i) in {0,1}$ is a hard validity mask, and $rho_(t,i)$ is an invalid
reason. The admissible actions are candidate indices:

$ #symb.rl.action_set_t = {i in {1,dots,N_q}: m_(t,i)=1}. $

Invalidity is a constraint, not low utility. Masks apply before argmax,
softmax, loss targets, and bootstrap maximization.

Counterfactual rollouts keep the root EVL field #symb.vin.field_evl_0 fixed. After
a selected valid view, only the accumulated geometry proxy, history, budget,
candidate table, masks, and reason codes are updated. The proposal therefore
studies geometry-only counterfactual planning, not synthetic future EVL
re-inference.

The V1 target protocol is OBS-SEL / PRED-Q / GT-EVAL. Target selection and
model input use an actor-visible descriptor

$
  #symb.entity.target_desc =
  phi(
    hat(bold(B))_e, hat(bold(y))_e, hat(p)_e, A_e^"proj",
    n_e^"semi", n_e^"EVL", bold(T)_e^"rel"
  ),
$

covering predicted/observed OBB geometry, class, confidence, projected area,
semi-dense support, EVL support, and relative pose. GT crops #symb.ase.mesh_target are used only
after matching #symb.entity.target_desc to GT. The matching score is protocol-level, not an
actor input:

$
  mu(hat(e), e) =
  kappa(hat(y)_(hat(e)), y_e)
  dot op("IoU")_"3D" (hat(bold(B))_(hat(e)), bold(B)_e^"GT")
  dot sigma(A_(hat(e))^"proj", n_(hat(e))^"semi", n_(hat(e))^"EVL").
$

Unmatched or ambiguous targets are target-invalid cases and are counted
separately from low target #RRI.

For target $e$, the implemented oracle error is the point-mesh accuracy plus
mesh-to-point completeness diagnostic:

#block[#align(center)[#eqs.entity.target_error]]

These are the `pm_acc_*` / `pm_comp_*` point-mesh terms used by `aria_nbv`,
not a point-cloud-to-point-cloud distance. If valid action $a_t=i$ selects
#symb.rl.candidate_qti, then

$
  #symb.obs.points_next = #symb.obs.points_t union #symb.obs.points_cand_ti,
  quad
  #symb.entity.target_reward =
  (#symb.entity.target_error - #symb.entity.target_error_next)
  /
  (#symb.entity.target_error_0 + epsilon).
$

The state-relative variant with denominator #symb.entity.target_error remains a
one-step diagnostic rather than the default finite-horizon return component.

The value-learning return and endpoint metric stay separate:

#block[#align(center)[#eqs.entity.finite_horizon_return]]
#block[#align(center)[#eqs.entity.endpoint_gain]]

The log-gain companion
#symb.entity.log_gain is only an ablation.

The non-myopic headroom estimate is

#block[#align(center)[#eqs.entity.lookahead_headroom]]

If #symb.entity.lookahead_headroom is approximately zero, the thesis reports that the current
candidate distribution and target #gls("relative-reconstruction-improvement") objective are effectively myopic. If it
is positive, the learned planner is judged by recovery over the one-step
actor-visible target scorer:

#block[#align(center)[#eqs.entity.q_recovery]]

#thesis-box([Main question])[
  Can a target-conditioned candidate-query Transformer
  #symb.rl.qh_theta (#symb.rl.s_cf0, #symb.entity.target_desc, #symb.rl.candidate_qti) recover measurable
  oracle-lookahead headroom over learned one-step target scoring under equal
  candidate and acquisition budgets?
]

The thesis-core evidence is observed target selection, target #RRI labels,
target-conditioned one-step scoring, replayable oracle rollouts, and masked
finite-candidate #symb.rl.qh. Continuous control, external simulators, 3DGS control,
SceneScript, VLM planning, and real-device guidance are follow-up designs unless
the finite-candidate result first justifies them.
