// Shared equation dictionary composed from domain-specific modules.

#import "equations/rri.typ": rri
#import "equations/coverage.typ": coverage
#import "equations/binning.typ": binning
#import "equations/coral.typ": coral
#import "equations/vin.typ": vin
#import "equations/metrics.typ": metrics
#import "equations/features.typ": features
#import "equations/scene.typ": scene
#import "equations/spatial.typ": spatial
#import "equations/model.typ": model
#import "equations/rl.typ": rl
#import "equations/action.typ": action
#import "equations/entity.typ": entity

#let eqs = (
  rri: rri,
  coverage: coverage,
  binning: binning,
  coral: coral,
  vin: vin,
  metrics: metrics,
  features: features,
  scene: scene,
  spatial: spatial,
  model: model,
  rl: rl,
  action: action,
  entity: entity,
)

// Machine-readable notation records. `scripts/glossary_build.py` queries this
// canonical Typst source to derive every notation adapter.
#let aria-notation-equations = (
  (key: "rri.cd", tex: "D(\\mathcal{P},\\mathcal{M}^{\\mathrm{GT}})=D_{P\\to M}(\\mathcal{P},\\mathcal{M}^{\\mathrm{GT}})+D_{M\\to P}(\\mathcal{P},\\mathcal{M}^{\\mathrm{GT}})", description: "", thesis_list: false, order: 9999),
  (key: "rri.acc", tex: "D_{P\\to M}(\\mathcal{P},\\mathcal{M}^{\\mathrm{GT}})=\\frac{1}{\\lVert\\mathcal{P}\\rVert}\\sum_{\\boldsymbol{p}\\in\\mathcal{P}}\\min_{\\boldsymbol{f}\\in\\mathcal{F}^{\\mathrm{GT}}} d(\\boldsymbol{p},\\boldsymbol{f})^2", description: "", thesis_list: false, order: 9999),
  (key: "rri.comp", tex: "D_{M\\to P}(\\mathcal{P},\\mathcal{M}^{\\mathrm{GT}})=\\frac{1}{\\lVert\\mathcal{F}^{\\mathrm{GT}}\\rVert}\\sum_{\\boldsymbol{f}\\in\\mathcal{F}^{\\mathrm{GT}}}\\min_{\\boldsymbol{p}\\in\\mathcal{P}} d(\\boldsymbol{p},\\boldsymbol{f})^2", description: "", thesis_list: false, order: 9999),
  (key: "rri.point_sampled_chamfer", tex: "D_{\\mathrm{PS-Chamfer}}(\\mathcal{P},\\mathcal{Q})=\\frac{1}{|\\mathcal{P}|}\\sum_{\\boldsymbol{p}\\in\\mathcal{P}}\\min_{\\boldsymbol{q}\\in\\mathcal{Q}}\\lVert\\boldsymbol{p}-\\boldsymbol{q}\\rVert_2^2+\\frac{1}{|\\mathcal{Q}|}\\sum_{\\boldsymbol{q}\\in\\mathcal{Q}}\\min_{\\boldsymbol{p}\\in\\mathcal{P}}\\lVert\\boldsymbol{q}-\\boldsymbol{p}\\rVert_2^2", description: "", thesis_list: false, order: 9999),
  (key: "rri.union", tex: "\\mathcal{P}_{t\\cup q}=\\mathcal{P}_t\\cup\\mathcal{P}_q", description: "", thesis_list: false, order: 9999),
  (key: "rri.rri", tex: "\\mathrm{RRI}(q)=\\frac{D(\\mathcal{P}_t,\\mathcal{M}^{\\mathrm{GT}})-D(\\mathcal{P}_t\\cup\\mathcal{P}_q,\\mathcal{M}^{\\mathrm{GT}})}{D(\\mathcal{P}_t,\\mathcal{M}^{\\mathrm{GT}})+\\varepsilon}", description: "", thesis_list: false, order: 9999),
  (key: "rri.target_rri", tex: "\\mathrm{RRI}_e(q)=\\frac{D(\\mathcal{P}_t^e,\\mathcal{M}_e^{\\mathrm{GT}})-D(\\mathcal{P}_t^e\\cup\\mathcal{P}_q^e,\\mathcal{M}_e^{\\mathrm{GT}})}{D(\\mathcal{P}_t^e,\\mathcal{M}_e^{\\mathrm{GT}})+\\varepsilon}", description: "", thesis_list: false, order: 9999),
  (key: "rri.greedy", tex: "q^*=\\operatorname*{argmax}_{q\\in\\mathcal{Q}}\\mathrm{RRI}(q)", description: "", thesis_list: false, order: 9999),
  (key: "binning.edges", tex: "e_k=\\operatorname{Quantile}(\\{r_i\\}_{i=1}^{N}, k/K),\\quad k\\in\\{1,\\ldots,K-1\\}", description: "", thesis_list: false, order: 9999),
  (key: "binning.label", tex: "y(r)=\\sum_{k=1}^{K-1}\\mathbb{1}[r>e_k],\\quad y(r)\\in\\{0,\\ldots,K-1\\}", description: "", thesis_list: false, order: 9999),
  (key: "binning.levels", tex: "t_k=\\mathbb{1}[y>k],\\quad k\\in\\{0,\\ldots,K-2\\}", description: "", thesis_list: false, order: 9999),
  (key: "coral.loss", tex: "\\mathcal{L}_{\\mathrm{coral}}(y,\\boldsymbol{p})=-\\sum_{k=0}^{K-2}\\left(t_k\\log p_k+(1-t_k)\\log(1-p_k)\\right)", description: "", thesis_list: false, order: 9999),
  (key: "coral.rel_random", tex: "\\mathcal{L}_{\\mathrm{rel}}=\\mathcal{L}_{\\mathrm{coral}}/((K-1)\\log 2)", description: "", thesis_list: false, order: 9999),
  (key: "vin.loss_total", tex: "\\mathcal{L}=\\mathcal{L}_{\\mathrm{coral}}+\\lambda\\mathcal{L}_{\\mathrm{reg}}", description: "", thesis_list: false, order: 9999),
  (key: "vin.aux_reg_mse", tex: "\\mathcal{L}_{\\mathrm{reg}}=\\frac{1}{N}\\sum_i(\\hat{r}_i-r_i)^2", description: "", thesis_list: false, order: 9999),
  (key: "metrics.spearman", tex: "\\rho=\\operatorname{corr}(\\operatorname{rank}(\\hat{r}_i),\\operatorname{rank}(r_i))", description: "", thesis_list: false, order: 9999),
  (key: "metrics.topk_acc", tex: "\\mathrm{TopKAcc}(k)=\\frac{1}{N}\\sum_i\\mathbb{1}[y_i\\in\\mathrm{TopK}(\\boldsymbol{\\pi}_i,k)]", description: "", thesis_list: false, order: 9999),
  (key: "metrics.candidate_validity", tex: "m_i=\\mathbb{1}[\\mathrm{finite}]\\mathbb{1}[v_i>0]\\mathbb{1}[v_i^{\\mathrm{sem}}>0]", description: "", thesis_list: false, order: 9999),
  (key: "rl.mdp", tex: "\\mathcal{M}=(\\mathcal{S},\\mathcal{A},P,r,\\gamma)", description: "", thesis_list: false, order: 9999),
  (key: "rl.nbv_mdp", tex: "\\mathcal{M}_{\\mathrm{NBV}}=(\\mathcal{S},\\mathcal{A},T,r_e,\\gamma,H)", description: "", thesis_list: false, order: 9999),
  (key: "rl.nbv_process_tuple", tex: "\\mathcal{M}_{\\mathrm{NBV}}=(\\mathcal{S}^{\\mathrm{hist}},\\mathcal{S}^{\\mathrm{cf0}},\\mathcal{S}^{\\mathrm{oracle}},\\{\\mathcal{A}_t\\},T,r_t^e,\\gamma,H)", description: "", thesis_list: false, order: 9999),
  (key: "rl.evidence_chain", tex: "\\mathcal{U}_{\\mathrm{cov/unc}}\\to\\hat r_t^e(i)\\to r_t^e\\to G_t^{(H)}\\to Q_{H,\\theta}", description: "", thesis_list: false, order: 9999),
  (key: "rl.candidate_row_equivariance", tex: "f_\\theta(\\Pi X_t,\\Pi m_t)=\\Pi f_\\theta(X_t,m_t)", description: "", thesis_list: false, order: 9999),
  (key: "rl.masked_candidate_selection", tex: "\\mathcal{A}_t=\\{i:m_{t,i}=1\\},\\quad a_t^\\theta=\\operatorname*{argmax}_{i\\in\\mathcal{A}_t} f_{\\theta,i}(X_t,m_t)", description: "", thesis_list: false, order: 9999),
  (key: "rl.s_hist", tex: "s_t^{\\mathrm{hist}}=(I_{1:t},T_{1:t},P_{1:t}^{\\mathrm{semi}},V^{\\mathrm{root}},e_t,b_t)", description: "", thesis_list: false, order: 9999),
  (key: "rl.s_off", tex: "s_t^{\\mathrm{off}}=(\\mathrm{VinSnippetView},\\mathcal{Q}_t,N_t,m_{t,i},\\ell_{t,i})", description: "", thesis_list: false, order: 9999),
  (key: "rl.s_cf0", tex: "s_t^{\\mathrm{cf0}}=(V^{\\mathrm{root}},\\mathcal{P}_t,\\mathcal{Q}_t,m_{t,i},\\rho_{t,i},e_t,b_t)", description: "", thesis_list: false, order: 9999),
  (key: "rl.s_pose", tex: "s_t^{\\mathrm{S0-pose}}=(\\mathcal{S}_{\\mathrm{root}}^{\\mathrm{VIN}},V^{\\mathrm{root}},(T_{r,e},l_e),\\mathcal{Q}_t,m_{t,i},H_t^{\\mathrm{pose}},b_t)", description: "Implemented qh_cf0_v1 actor carrier.", thesis_list: true, order: 301),
  (key: "rl.s_cf_geom", tex: "s_t^{\\mathrm{cf+}}=(s_t^{\\mathrm{cf0}},D_{1:t}^{\\mathrm{sel}},P_{1:t}^{\\mathrm{sel}},N_{1:t}^{\\mathrm{sel}})", description: "", thesis_list: false, order: 9999),
  (key: "rl.s_cf_gt_carrier", tex: "s_t^{\\mathrm{CF-GT-carrier}}=(s_t^{\\mathrm{S0-pose}},(D,V,K,T_{\\mathrm{root}\\leftarrow\\mathrm{cam}})_{1:t}^{\\mathrm{sel}})", description: "Implemented qh_cfplus_gt_depth_v1 carrier; no fused points or normals are claimed.", thesis_list: true, order: 311),
  (key: "rl.s_oracle", tex: "s_t^{\\mathrm{oracle}}=(s_t^{\\mathrm{cf+}},\\mathcal{M}^{\\mathrm{GT}},\\mathcal{M}_e^{\\mathrm{GT}},\\{D_{t,i}^{\\mathrm{GT}},\\mathcal{P}_{t,i}^{\\mathrm{GT}},\\mathrm{RRI}_{t,i}\\}_{i=1}^{N_t})", description: "", thesis_list: false, order: 9999),
  (key: "rl.finite_action_set", tex: "\\mathcal{Q}_t=\\{q_{t,i}\\}_{i=1}^{N_t},\\quad \\mathcal{A}(s_t)=\\{i\\in\\{1,\\ldots,N_t\\}:m_{t,i}=1\\},\\quad q_t=q_{t,a_t}", description: "", thesis_list: false, order: 9999),
  (key: "rl.counterfactual_transition", tex: "\\mathcal{P}_{t+1}=\\mathcal{P}_t\\cup\\mathcal{P}_{q_t}", description: "", thesis_list: false, order: 9999),
  (key: "rl.marginal_target_rri", tex: "\\mathrm{RRI}_{t,i}^e=(\\Delta_t^e-\\Delta_{t\\mid i}^e)/\\max(\\Delta_t^e,\\varepsilon)", description: "State-relative candidate diagnostic persisted as one_step_target_rri.", thesis_list: true, order: 204),
  (key: "rl.cumulative_target_rri", tex: "C_t^{\\mathrm{RRI},e}=\\sum_{k=0}^{t-1}\\mathrm{RRI}_{k,a_k}^e", description: "Running selected-chain diagnostic persisted as cumulative_target_rri.", thesis_list: true, order: 205),
  (key: "rl.target_root_gain_reward", tex: "r_t^e=(\\Delta_t^e-\\Delta_{t+1}^e)/\\max(\\Delta_0^e,\\varepsilon)", description: "Root-normalized target gain optimized by Q_H.", thesis_list: true, order: 206),
  (key: "rl.cumulative_target_root_gain", tex: "J_t^e=\\sum_{k=0}^{t-1}r_k^e=(\\Delta_0^e-\\Delta_t^e)/\\max(\\Delta_0^e,\\varepsilon)", description: "Telescoping cumulative target root gain.", thesis_list: true, order: 207),
  (key: "rl.finite_horizon_return", tex: "G_t^{(H)}=\\sum_{k=0}^{H-1}\\gamma^k r_{t+k}^e", description: "", thesis_list: false, order: 9999),
  (key: "rl.q_h", tex: "Q_H(s_t^{\\mathrm{cf0}},a_t)=\\mathbb{E}\\left[G_t^{(H)}\\mid s_t=s_t^{\\mathrm{cf0}},a_t\\right]", description: "", thesis_list: false, order: 9999),
  (key: "rl.qh_scorer_interface", tex: "(Q_{h,\\theta,e,i}^{\\mathrm{cond}},\\ell_{t,i}^{\\mathrm{feas}})=f_\\theta(s_t,e,q_{t,i},h),\\quad h=b_t\\ \\mathrm{if\\ omitted},\\quad 1\\le h\\le b_t\\le H_{\\mathrm{max}}", description: "Mask-independent scorer output and scalar horizon contract.", thesis_list: false, order: 9999),
  (key: "rl.qh_conditional_mask_independence", tex: "(Q^{\\mathrm{cond}},\\ell^{\\mathrm{feas}})(s_t,e,q_{t,i},h,\\boldsymbol{m}_t)=(Q^{\\mathrm{cond}},\\ell^{\\mathrm{feas}})(s_t,e,q_{t,i},h,\\boldsymbol{m}'_t)", description: "Raw scorer outputs do not depend on the authoritative action mask.", thesis_list: false, order: 9999),
  (key: "rl.reward_geom", tex: "r_t^{\\mathrm{geom}}=\\log(D(\\mathcal{P}_t,\\mathcal{M}^{\\mathrm{GT}})+\\varepsilon)-\\log(D(\\mathcal{P}_{t+1},\\mathcal{M}^{\\mathrm{GT}})+\\varepsilon)-\\alpha\\mathbb{1}[\\mathrm{collision}(a_t)]-\\beta c(a_t)", description: "", thesis_list: false, order: 9999),
  (key: "rl.q_backup", tex: "y_t^Q=r_t+\\gamma V(s_{t+1})", description: "", thesis_list: false, order: 9999),
  (key: "action.space", tex: "\\mathcal{A}^{\\mathrm{cont}}\\subset\\mathbb{R}^3\\times \\operatorname{SO}(2)", description: "", thesis_list: false, order: 9999),
  (key: "action.candidate_shell", tex: "\\mathcal{Q}_t=\\{q_{t,i}\\}_{i=1}^{N_q},\\quad N_q=60", description: "", thesis_list: false, order: 9999),
  (key: "action.robust_temperature_softmax", tex: "\\ell_i=(s_i-\\operatorname{median}(s))/(\\operatorname{IQR}(s)\\tau),\\quad P(i\\mid m_i=1)=\\exp(\\ell_i)/\\sum_{j:m_j=1}\\exp(\\ell_j)", description: "", thesis_list: false, order: 9999),
  (key: "entity.target_descriptor", tex: "\\boldsymbol{\\phi}_e=\\operatorname{Enc}_{\\mathrm{tgt}}(\\hat{\\boldsymbol{B}}_e,\\hat{\\boldsymbol{y}}_e,\\hat{\\pi}_e,A_e^{\\mathrm{proj}},n_e^{\\mathrm{semi}},n_e^{\\mathrm{EVL}},\\omega_e^{\\mathrm{EVL}},\\ell_e^{\\mathrm{src}},\\boldsymbol{T}_{r_t,e},\\boldsymbol{T}_{c_t,e})", description: "", thesis_list: false, order: 9999),
  (key: "entity.target_identity_iou", tex: "\\mu_{\\mathrm{IoU}}(\\hat e,e)=\\operatorname{IoU}_{3D}(\\hat{\\boldsymbol{B}}_{\\hat e},\\boldsymbol{B}_e)", description: "Same-class oriented 3D IoU used by the V1 observed-target matcher.", thesis_list: true, order: 207),
  (key: "entity.target_identity_threshold", tex: "\\tau_{\\mathrm{IoU}}=0.20", description: "Strict V1 observed-target IoU threshold; equality is rejected.", thesis_list: true, order: 208),
  (key: "entity.target_identity_qualified_count", tex: "n_{\\mathrm{qual}}(\\hat e)=\\left|\\{e:\\operatorname{class}(e)=\\operatorname{class}(\\hat e),\\ \\mu_{\\mathrm{IoU}}(\\hat e,e)>\\tau_{\\mathrm{IoU}}\\}\\right|", description: "Number of same-class GT OBBs whose oriented IoU is strictly above the V1 threshold.", thesis_list: true, order: 209),
  (key: "entity.target_identity_acceptance", tex: "a_{\\mathrm{id}}(\\hat e)=1\\ \\Longleftrightarrow\\ n_{\\mathrm{qual}}(\\hat e)=1", description: "V1 target admission requires exactly one qualifying GT OBB; zero or multiple qualifiers are rejected.", thesis_list: true, order: 210),
  (key: "features.point_dino_token", tex: "\\boldsymbol{x}_j^{\\mathrm{pt}}=\\operatorname{concat}(\\boldsymbol{p}_j,\\boldsymbol{f}_j^{\\mathrm{DINO-comp}},\\sigma_j^{-1},n_j,\\boldsymbol{a}_j^{\\mathrm{hist}})", description: "", thesis_list: false, order: 9999),
  (key: "scene.evl_local_support_read", tex: "\\omega_{t,i}^{\\mathrm{EVL}}=\\frac{1}{K}\\sum_{k=1}^{K}\\mathbb{1}[x_{t,i,k}\\in\\mathcal{V}_0^{\\mathrm{EVL}}]", description: "", thesis_list: false, order: 9999),
  (key: "scene.ray_memory_update", tex: "\\boldsymbol{M}_{t+1}^{\\mathrm{ray}}=\\operatorname{Fuse}(\\boldsymbol{M}_t^{\\mathrm{ray}},\\mathcal{P}_{t,i}^{\\mathrm{cand}},\\mathcal{R}_{t,i}^{\\mathrm{sel}})", description: "", thesis_list: false, order: 9999),
  (key: "scene.qh_scene_memory", tex: "\\boldsymbol{\\Phi}_t^{\\mathrm{scene}}=(\\boldsymbol{M}_t^{\\mathrm{ray}},\\boldsymbol{X}_t^{\\mathrm{pt}},\\boldsymbol{F}_t^{\\mathrm{DINO@pt}},\\boldsymbol{E}_0^{\\mathrm{EVL-local}},\\boldsymbol{O}_t^{\\mathrm{pred}},\\boldsymbol{M}^{\\mathrm{dir}})", description: "", thesis_list: false, order: 9999),
  (key: "scene.candidate_query_pools", tex: "\\boldsymbol{g}_e^{\\mathrm{tgt}},\\boldsymbol{g}_{t,i}^{\\mathrm{fr}},\\boldsymbol{g}_{t,e,i}^{\\cap}=\\operatorname{Pool}(\\boldsymbol{x}_j^{\\mathrm{pt}})", description: "", thesis_list: false, order: 9999),
  (key: "scene.candidate_ray_query", tex: "\\boldsymbol{g}_{t,i}^{\\mathrm{ray}}=\\operatorname{RenderQuery}(\\boldsymbol{M}_t^{\\mathrm{ray}},q_{t,i},\\hat{\\boldsymbol{B}}_e)", description: "", thesis_list: false, order: 9999),
  (key: "spatial.candidate_reference_transform", tex: "\\boldsymbol{T}_{r_t,i}^{\\mathrm{rel}}=\\boldsymbol{T}_{w,r_t}^{-1}\\boldsymbol{T}_{w,c_{t,i}},\\quad \\boldsymbol{\\delta}_{r_t,i}^{p}=\\boldsymbol{R}_{r_t}^{\\top}(\\boldsymbol{c}_{t,i}-\\boldsymbol{c}_{r_t}),\\quad \\boldsymbol{R}_{r_t,i}=\\boldsymbol{R}_{r_t}^{\\top}\\boldsymbol{R}_{t,i}", description: "", thesis_list: false, order: 9999),
  (key: "spatial.candidate_pose_features", tex: "\\boldsymbol{h}_{t,i}^{\\mathrm{pose}}=\\operatorname{concat}(\\boldsymbol{\\delta}_{r_t,i}^{p},\\operatorname{R6D}(\\boldsymbol{R}_{r_t,i}),\\|\\boldsymbol{\\delta}_{r_t,i}^{p}\\|_2,\\operatorname{atan2}(\\delta_{r_t,i}^{y},\\delta_{r_t,i}^{x}),\\Delta h_{t,i},\\boldsymbol{u}_{t,i}^{\\mathrm{up/frustum}})", description: "", thesis_list: false, order: 9999),
  (key: "spatial.candidate_target_relation", tex: "\\boldsymbol{h}_{t,e\\mid i}^{\\mathrm{rel}}=\\operatorname{concat}(\\boldsymbol{\\delta}_{e\\mid i}^{p},\\|\\boldsymbol{\\delta}_{e\\mid i}^{p}\\|_2,\\cos\\theta_{t,e,i}^{\\mathrm{opt}},\\beta_{t,e,i}^{\\mathrm{elev}},\\lambda_{t,e,i}^{\\mathrm{obb}})", description: "", thesis_list: false, order: 9999),
  (key: "spatial.candidate_query_local_frame", tex: "\\boldsymbol{\\delta}_{a\\mid i}^{p}=\\boldsymbol{R}_{t,i}^{\\top}(\\boldsymbol{p}_a-\\boldsymbol{c}_{t,i})", description: "", thesis_list: false, order: 9999),
  (key: "spatial.candidate_query_rpe", tex: "\\boldsymbol{e}_{a\\mid i}^{\\mathrm{rel}}=\\psi_{\\mathrm{rel}}(\\mathcal{F}(\\boldsymbol{\\eta}_{a\\mid i}))", description: "", thesis_list: false, order: 9999),
  (key: "spatial.direction_unit", tex: "\\boldsymbol{d}_k(\\boldsymbol{v})=(\\boldsymbol{c}_k-\\boldsymbol{v})/\\|\\boldsymbol{c}_k-\\boldsymbol{v}\\|_2", description: "", thesis_list: false, order: 9999),
  (key: "spatial.direction_memory_sh", tex: "\\boldsymbol{h}^{\\mathrm{dir}}(\\boldsymbol{v})=\\sum_{k<t}w_k(\\boldsymbol{v})\\boldsymbol{Y}_L(\\boldsymbol{d}_k(\\boldsymbol{v}))", description: "", thesis_list: false, order: 9999),
  (key: "spatial.direction_memory_moment", tex: "\\boldsymbol{M}^{\\mathrm{dir}}(\\boldsymbol{v})=\\sum_{k<t}w_k(\\boldsymbol{v})\\boldsymbol{d}_k(\\boldsymbol{v})\\boldsymbol{d}_k(\\boldsymbol{v})^\\top", description: "", thesis_list: false, order: 9999),
  (key: "spatial.direction_novelty", tex: "\\nu_{t,i}^{\\mathrm{dir}}(\\boldsymbol{v})=1-\\frac{\\boldsymbol{d}_{t,i}(\\boldsymbol{v})^\\top\\boldsymbol{M}^{\\mathrm{dir}}(\\boldsymbol{v})\\boldsymbol{d}_{t,i}(\\boldsymbol{v})}{\\operatorname{tr}(\\boldsymbol{M}^{\\mathrm{dir}}(\\boldsymbol{v}))+\\varepsilon}", description: "", thesis_list: false, order: 9999),
  (key: "model.qh_target_token", tex: "\\boldsymbol{h}_e^{\\mathrm{tgt}}=\\operatorname{MLP}_{\\mathrm{tgt}}(\\operatorname{concat}(\\boldsymbol{\\phi}_e,\\boldsymbol{g}_e^{\\mathrm{tgt}}))", description: "", thesis_list: false, order: 9999),
  (key: "model.qh_frozen_interface", tex: "f_\\theta(s_t^{\\mathrm{S0-pose}},\\boldsymbol{\\phi}_e,\\{q_{t,i}\\}_{i=1}^{N_q},h)\\to(\\{Q_{h,\\theta,e,i}^{\\mathrm{cond}}\\}_{i=1}^{N_q},\\{\\ell_{t,i}^{\\mathrm{feas}}\\}_{i=1}^{N_q})", description: "Frozen scalar requested-horizon scorer interface.", thesis_list: false, order: 9999),
  (key: "model.candidate_row_features", tex: "\\boldsymbol{x}_{t,i}=\\operatorname{concat}(\\boldsymbol{h}_{t,i}^{\\mathrm{pose+rel}},\\boldsymbol{h}_{t,i}^{\\mathrm{geom}},\\boldsymbol{h}_{t,i}^{\\mathrm{valid}},\\boldsymbol{h}_{t,i}^{\\mathrm{prov}},\\boldsymbol{H}_t)", description: "", thesis_list: false, order: 9999),
  (key: "rl.qh_residual_decomposition", tex: "Q_{H,\\theta,i}=b_{\\psi,i}+\\delta_{\\theta,i}^{H}", description: "", thesis_list: false, order: 9999),
  (key: "entity.objective", tex: "\\mathrm{RRI}_{\\mathrm{total}}(q)=\\sum_{e\\in\\mathcal{E}}w_e\\mathrm{RRI}_e+\\lambda_{\\mathrm{scene}}\\mathrm{RRI}", description: "", thesis_list: false, order: 9999),
  (key: "action.angle_cap_transform", tex: "\\psi_{\\mathrm{cap}}=\\psi\\Delta_\\psi/(2\\pi),\\quad y_{\\mathrm{cap}}=\\sin\\theta_{\\min}+(u_y+1)(\\sin\\theta_{\\max}-\\sin\\theta_{\\min})/2", description: "", thesis_list: false, order: 9999),
  (key: "action.candidate_center_world", tex: "r_i\\sim\\mathcal{U}(0.25,1.1),\\quad \\boldsymbol{c}_i^w=\\boldsymbol{T}_r^w(r_i\\boldsymbol{d}_i^{k(i)})", description: "", thesis_list: false, order: 9999),
  (key: "action.capped_direction", tex: "\\boldsymbol{d}_i^0=\\operatorname{norm}(\\sqrt{1-y_{\\mathrm{cap}}^2}(\\sin\\psi_{\\mathrm{cap}},\\cos\\psi_{\\mathrm{cap}}),y_{\\mathrm{cap}})", description: "", thesis_list: false, order: 9999),
  (key: "action.family_directions", tex: "\\boldsymbol{d}_i^{\\mathrm{forward}},\\boldsymbol{d}_i^{\\mathrm{target}},\\boldsymbol{d}_i^{\\mathrm{bypass}}", description: "", thesis_list: false, order: 9999),
  (key: "action.motion_pruning_limits", tex: "\\lVert\\boldsymbol{o}_i\\rVert_2\\le1.0\\,\\mathrm{m},\\ |\\Delta h_i|\\le0.25\\,\\mathrm{m},\\ \\Delta\\psi_i\\le70^\\circ", description: "", thesis_list: false, order: 9999),
  (key: "action.power_spherical_forward", tex: "\\boldsymbol{u}_i\\sim\\mathrm{PS}(\\boldsymbol{e}_z,\\kappa),\\quad p(\\boldsymbol{u})=c_\\kappa(1+\\boldsymbol{e}_z^\\top\\boldsymbol{u})^\\kappa", description: "", thesis_list: false, order: 9999),
  (key: "action.target_lookat_frame", tex: "\\boldsymbol{z}_i^w=\\operatorname{norm}(\\boldsymbol{p}_e-\\boldsymbol{c}_i^w),\\quad\\boldsymbol{x}_i^w=\\boldsymbol{y}_i^w\\times\\boldsymbol{z}_i^w", description: "", thesis_list: false, order: 9999),
  (key: "action.valid_support_threshold", tex: "N_{\\mathrm{valid}}\\ge\\max(12,\\lceil0.25N_q\\rceil)", description: "", thesis_list: false, order: 9999),
  (key: "entity.endpoint_gain", tex: "J_e^{(H)}=(\\Delta_{t=0}^e-\\Delta_{t=H}^e)/(\\Delta_{t=0}^e+\\varepsilon)", description: "", thesis_list: false, order: 9999),
  (key: "entity.log_gain", tex: "J_{e,\\mathrm{log}}^{(H)}=\\log(\\Delta_{t=0}^e+\\varepsilon)-\\log(\\Delta_{t=H}^e+\\varepsilon)", description: "", thesis_list: false, order: 9999),
  (key: "entity.lookahead_headroom", tex: "\\Delta_{\\mathrm{look}}=J_e^{(H)}(\\pi_{\\mathrm{oracle-look}})-J_e^{(H)}(\\pi_{\\mathrm{oracle-1}})", description: "", thesis_list: false, order: 9999),
  (key: "entity.q_recovery", tex: "\\eta_Q=(J_e^{(H)}(\\pi_Q)-J_e^{(H)}(\\pi_{\\mathrm{learned-1}}))/(J_e^{(H)}(\\pi_{\\mathrm{oracle-look}})-J_e^{(H)}(\\pi_{\\mathrm{learned-1}})+\\varepsilon)", description: "", thesis_list: false, order: 9999),
  (key: "entity.target_error", tex: "\\Delta_t^e=d(C_e(\\mathcal{P}_t),\\mathcal{M}_e^{\\mathrm{GT}})", description: "", thesis_list: false, order: 9999),
  (key: "model.qh_input_contract", tex: "\\mathcal{I}_{t,e}=(\\boldsymbol{h}_e^{\\mathrm{tgt}},\\boldsymbol{\\Phi}_t^{\\mathrm{scene}},\\boldsymbol{H}_t,\\boldsymbol{b}_t,t,H,\\{\\boldsymbol{x}_{t,i},\\boldsymbol{e}_{a\\mid i}^{\\mathrm{rel}},m_{t,i},\\boldsymbol{\\rho}_{t,i}\\}_{i=1}^{N_q})", description: "", thesis_list: false, order: 9999),
  (key: "model.qh_state_fusion_controls", tex: "\\boldsymbol{Z}_t=(\\boldsymbol{\\Phi}_t^{\\mathrm{scene}},\\boldsymbol{h}_e^{\\mathrm{tgt}},\\boldsymbol{h}_t^{\\mathrm{hist}},\\operatorname{Emb}(b_t/H_{\\max}),\\operatorname{Emb}(h/H_{\\max})),\\quad \\boldsymbol{c}_{t,i}^{\\mathrm{A0}}=\\operatorname{MLP}_{\\mathrm{A0}}([\\boldsymbol{x}_{t,i};\\operatorname{vec}(\\boldsymbol{Z}_t)]),\\quad \\boldsymbol{c}_{t,i}^{\\mathrm{A1}}=\\operatorname{CrossAttn}_{\\mathrm{A1}}(\\boldsymbol{x}_{t,i},\\boldsymbol{Z}_t,\\boldsymbol{Z}_t)", description: "Feature-matched independent-row MLP and candidate-to-state attention controls.", thesis_list: false, order: 9999),
  (key: "rl.candidate_mask_isolation", tex: "\\operatorname{Mask}(\\boldsymbol{X}_t,\\boldsymbol{m}_t)=\\operatorname{Mask}(\\widetilde{\\boldsymbol{X}}_t,\\boldsymbol{m}_t)", description: "", thesis_list: false, order: 9999),
  (key: "rl.qh_candidate_token", tex: "\\boldsymbol{u}_{t,i}=\\operatorname{Enc}_\\theta(\\mathcal{I}_{t,e},q_{t,i})", description: "", thesis_list: false, order: 9999),
  (key: "rl.qh_coral_interface", tex: "\\begin{gathered}c_n^Q=\\sum_{k=0}^{K-2}\\mathbb{1}[y_n>e_k^Q],\\quad l_{n,k}=\\mathbb{1}[c_n^Q>k];\\\\ \\mathcal{L}_Q^{\\mathrm{CORAL}}=-\\sum_n\\sum_{k=0}^{K-2}\\left(l_{n,k}\\log p_{n,k}+(1-l_{n,k})\\log(1-p_{n,k})\\right),\\quad p_{n,k}=\\sigma(o_{n,k});\\\\ \\pi_{n,k}^{\\mathrm{raw}}=p_{n,k-1}-p_{n,k},\\quad \\widetilde{\\pi}_{n,k}=\\frac{\\max(\\pi_{n,k}^{\\mathrm{raw}},0)}{\\sum_j\\max(\\pi_{n,j}^{\\mathrm{raw}},0)+\\varepsilon},\\quad Q_n^{\\mathrm{cond}}=\\sum_{k=0}^{K-1}\\widetilde{\\pi}_{n,k}u_k^Q\\end{gathered}", description: "Fixed-support CORAL loss and continuous conditional-Q decoding.", thesis_list: false, order: 9999),
  (key: "rl.qh_masked_argmax", tex: "a_t^\\theta=\\operatorname*{argmax}_{i:m_{t,i}=1}Q_{H,\\theta,i}", description: "", thesis_list: false, order: 9999),
  (key: "rl.qh_doubleq_index", tex: "B_t^{(h,e)}=Q_{h-1,\\theta^-}(s_{t+1},\\operatorname*{argmax}_{i:m_{t+1,i}=1}Q_{h-1,\\theta}(s_{t+1},i))", description: "", thesis_list: false, order: 9999),
  (key: "rl.qh_doubleq_target", tex: "y_t^{(h,e)}=r_t^e+\\gamma B_t^{(h,e)}", description: "", thesis_list: false, order: 9999),
  (key: "rl.qh_exact_q2_target", tex: "y_t^{(2,\\mathrm{exact})}=r_t^e+\\gamma_t\\max_{j:m_{t+1,j}^{\\mathrm{train}}=1}r_{t+1,j}^e", description: "Factual dense-successor exact-Q2 control.", thesis_list: false, order: 9999),
  (key: "rl.qh_exact_q2_error", tex: "\\varepsilon_t^{(2)}=|y_t^{(2,\\mathrm{recursive})}-y_t^{(2,\\mathrm{exact})}|\\leq\\tau_{\\mathrm{abs}}+\\tau_{\\mathrm{rel}}|y_t^{(2,\\mathrm{exact})}|", description: "Versioned absolute-plus-relative learned-recursion agreement gate.", thesis_list: false, order: 9999),
  (key: "rl.qh_uncentered_residual", tex: "Q_{H,\\theta,i}=b_{\\psi,i}+\\delta_{\\theta,i}^H", description: "", thesis_list: false, order: 9999),
  (key: "rl.replay_transition", tex: "(x_{t+1},\\boldsymbol{H}_{t+1},b_{t+1},\\mathcal{Q}_{t+1})=\\operatorname{Step}(x_t,\\boldsymbol{H}_t,b_t,q_{t,a_t},\\xi_t)", description: "", thesis_list: false, order: 9999),
  (key: "scene.actor_state_read", tex: "\\boldsymbol{h}_{t,e,i}=\\operatorname{Read}(\\boldsymbol{\\Phi}_t^{\\mathrm{scene}},\\boldsymbol{h}_e^{\\mathrm{tgt}},q_{t,i},\\boldsymbol{H}_t,t,H)", description: "", thesis_list: false, order: 9999),
  (key: "spatial.candidate_proposal_support_normalization", tex: "d_{t,e}^{\\mathrm{current}}=\\lVert\\boldsymbol{p}_e^w-\\boldsymbol{c}_{r_t}^w\\rVert_2,\\quad \\widetilde{\\boldsymbol{c}}_{t,i}^{\\mathrm{support}}=(\\boldsymbol{B}_{r,t}^{\\mathrm{Z-up}})^\\top(\\boldsymbol{c}_{t,i}^w-\\boldsymbol{c}_{r_t}^w)/d_{t,e}^{\\mathrm{current}},\\quad \\widetilde{\\boldsymbol{p}}_{t,e}^{\\mathrm{support}}=(\\boldsymbol{B}_{r,t}^{\\mathrm{Z-up}})^\\top(\\boldsymbol{p}_e^w-\\boldsymbol{c}_{r_t}^w)/d_{t,e}^{\\mathrm{current}},\\quad \\lVert\\widetilde{\\boldsymbol{p}}_{t,e}^{\\mathrm{support}}\\rVert_2=1", description: "Candidate support centered on the factual expansion pose, yaw-aligned with Z-up, and scaled by current target distance.", thesis_list: false, order: 9999),
  (key: "spatial.rollout_trajectory_normalization", tex: "d_{0,e}^{\\mathrm{initial}}=\\lVert\\boldsymbol{p}_e^w-\\boldsymbol{c}_{r_0}^w\\rVert_2,\\quad \\widetilde{\\boldsymbol{x}}_{r,t}^{\\mathrm{trajectory}}=(\\boldsymbol{B}_{r,0}^{\\mathrm{target-Z-up}})^\\top(\\boldsymbol{x}_{r,t}^w-\\boldsymbol{c}_{r_0}^w)/d_{0,e}^{\\mathrm{initial}}", description: "Factual selected trajectory in one initial-root, target-aligned Z-up frame and scale.", thesis_list: false, order: 9999),
)

#for entry in aria-notation-equations [
  #metadata(entry) <aria-notation-equation>
]
