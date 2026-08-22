// Shared symbol dictionary composed from domain-specific modules.

#import "symbols/frame.typ": frame
#import "symbols/ase.typ": ase
#import "symbols/oracle.typ": oracle
#import "symbols/obs.typ": obs
#import "symbols/entity.typ": entity
#import "symbols/rl.typ": rl
#import "symbols/vin.typ": vin
#import "symbols/scene.typ": scene
#import "symbols/spatial.typ": spatial
#import "symbols/model.typ": model
#import "symbols/shape.typ": shape

#let symb = (
  frame: frame,
  ase: ase,
  oracle: oracle,
  obs: obs,
  entity: entity,
  rl: rl,
  vin: vin,
  scene: scene,
  spatial: spatial,
  model: model,
  shape: shape,
)

// Machine-readable notation records. `scripts/glossary_build.py` queries this
// canonical Typst source to derive every notation adapter.
#let aria-notation-symbols = (
  (key: "oracle.rri", tex: "\\mathrm{RRI}", description: "Relative Reconstruction Improvement score for a candidate view.", thesis_list: true, order: 10),
  (key: "oracle.points", tex: "\\mathcal{P}", description: "Actor-visible point set accumulated from observed or replayed views.", thesis_list: true, order: 20),
  (key: "oracle.points_q", tex: "\\mathcal{P}_q", description: "Candidate-view point contribution used in oracle or counterfactual updates.", thesis_list: true, order: 30),
  (key: "oracle.candidates", tex: "\\mathcal{Q}", description: "Finite candidate-view set considered by the planner.", thesis_list: true, order: 40),
  (key: "oracle.candidates_t", tex: "\\mathcal{Q}_t", description: "Candidate-view set available at rollout step t.", thesis_list: true, order: 50),
  (key: "oracle.candidate_qti", tex: "q_{t,i}", description: "Candidate pose i at rollout step t.", thesis_list: true, order: 60),
  (key: "oracle.center", tex: "\\boldsymbol{c}", description: "World-space camera-center vector; subscripts identify a rollout root or candidate pose.", thesis_list: true, order: 65),
  (key: "oracle.depth_q", tex: "\\boldsymbol{D}_q", description: "Oracle-rendered or candidate-specific depth map for a proposed view.", thesis_list: true, order: 70),
  (key: "oracle.acc", tex: "D_{P\\to M}", description: "Point-to-mesh directional error component.", thesis_list: true, order: 80),
  (key: "oracle.comp", tex: "D_{M\\to P}", description: "Mesh-to-point directional error component.", thesis_list: true, order: 90),
  (key: "oracle.err", tex: "D", description: "Aggregate point-mesh reconstruction error used by RRI definitions.", thesis_list: true, order: 100),
  (key: "oracle.dist_pm", tex: "D_{P\\to M}", description: "Point-to-mesh directional reconstruction error component.", thesis_list: true, order: 102),
  (key: "oracle.dist_mp", tex: "D_{M\\to P}", description: "Mesh-to-point directional reconstruction error component.", thesis_list: true, order: 104),
  (key: "ase.mesh", tex: "\\mathcal{M}^{\\mathrm{GT}}", description: "Ground-truth scene mesh used for oracle labels and evaluation.", thesis_list: true, order: 110),
  (key: "ase.mesh_target", tex: "\\mathcal{M}_e^{\\mathrm{GT}}", description: "Ground-truth mesh crop for target e.", thesis_list: true, order: 120),
  (key: "ase.faces", tex: "\\mathcal{F}^{\\mathrm{GT}}", description: "Ground-truth mesh faces used in point-mesh distance calculations.", thesis_list: true, order: 130),
  (key: "ase.traj", tex: "\\boldsymbol{T}_{\\mathrm{rig}}^{\\mathrm{w}}(t)", description: "Project Aria rig pose in the world frame at time t.", thesis_list: true, order: 140),
  (key: "ase.traj_final", tex: "\\boldsymbol{T}_{\\mathrm{rig}}^{\\mathrm{w}}(T)", description: "Final rig pose used as an anchor for gravity-aligned local fields.", thesis_list: true, order: 150),
  (key: "vin.rri", tex: "r", description: "Target or scene RRI value used as a model target.", thesis_list: true, order: 160),
  (key: "vin.rri_hat", tex: "\\hat{r}", description: "Predicted RRI value emitted by the learned scorer.", thesis_list: true, order: 170),
  (key: "vin.loss", tex: "\\mathcal{L}", description: "Training loss for scorer or value-model objectives.", thesis_list: true, order: 180),
  (key: "vin.cand_valid", tex: "m", description: "Candidate validity indicator used by scorer diagnostics.", thesis_list: true, order: 190),
  (key: "entity.rri_e", tex: "\\mathrm{RRI}_e", description: "Target-specific Relative Reconstruction Improvement for entity e.", thesis_list: true, order: 200),
  (key: "entity.target_desc", tex: "\\boldsymbol{\\phi}_e", description: "Actor-visible target/entity descriptor used to condition target-specific value prediction.", thesis_list: true, order: 205),
  (key: "entity.center", tex: "\\boldsymbol{p}_e^w", description: "World-space center of the selected target entity e.", thesis_list: true, order: 206),
  (key: "entity.target_error", tex: "\\Delta_t^e", description: "Target-specific reconstruction error at rollout step t.", thesis_list: true, order: 207),
  (key: "entity.target_error_next", tex: "\\Delta_{t+1}^e", description: "Target-specific reconstruction error after the next observation.", thesis_list: true, order: 208),
  (key: "entity.target_error_0", tex: "\\Delta_0^e", description: "Target-specific reconstruction error at rollout start.", thesis_list: true, order: 209),
  (key: "rl.s", tex: "s", description: "Abstract planning state.", thesis_list: true, order: 210),
  (key: "rl.a", tex: "a", description: "Action index selecting a candidate row.", thesis_list: true, order: 220),
  (key: "rl.r", tex: "r", description: "Scalar reward or immediate gain.", thesis_list: true, order: 230),
  (key: "rl.G", tex: "G", description: "Finite-horizon return accumulated across rollout steps.", thesis_list: true, order: 240),
  (key: "rl.mdp_nbv", tex: "\\mathcal{M}_{\\mathrm{NBV}}", description: "Target-conditioned finite-candidate NBV decision process.", thesis_list: true, order: 250),
  (key: "rl.action_set", tex: "\\mathcal{A}(s_t)", description: "Valid action set available in state s_t.", thesis_list: true, order: 260),
  (key: "rl.transition", tex: "T", description: "State-transition operator for selected candidate actions.", thesis_list: true, order: 270),
  (key: "rl.s_hist", tex: "s_t^{\\mathrm{hist}}", description: "Logged historic snippet state at rollout step t.", thesis_list: true, order: 280),
  (key: "rl.s_off", tex: "s_t^{\\mathrm{off}}", description: "Persisted offline sample state used by training readers.", thesis_list: true, order: 290),
  (key: "rl.s_cf0", tex: "s_t^{\\mathrm{cf0}}", description: "Minimal actor-visible counterfactual state.", thesis_list: true, order: 300),
  (key: "rl.s_cf_geom", tex: "s_t^{\\mathrm{cf+}}", description: "Geometry-enriched counterfactual successor state.", thesis_list: true, order: 310),
  (key: "rl.s_oracle", tex: "s_t^{\\mathrm{oracle}}", description: "Oracle-only state used for labels, upper bounds, and evaluation.", thesis_list: true, order: 320),
  (key: "rl.reward_target", tex: "r_t^e", description: "Target-specific reward at rollout step t.", thesis_list: true, order: 330),
  (key: "entity.target_reward", tex: "r_t^e", description: "Canonical target-specific reward at rollout step t.", thesis_list: true, order: 331),
  (key: "rl.observed_cumulative_root_gain", tex: "G_{0:s,\\mathrm{root}}^e", description: "Observed cumulative target-root gain through factual rollout step s.", thesis_list: true, order: 332),
  (key: "rl.return_h", tex: "G_t^{(H)}", description: "H-step finite-horizon return from rollout step t.", thesis_list: true, order: 340),
  (key: "rl.qh", tex: "Q_H", description: "Finite-horizon candidate-value function.", thesis_list: true, order: 350),
  (key: "rl.gamma", tex: "\\gamma", description: "Return discount factor.", thesis_list: true, order: 360),
  (key: "rl.epsilon", tex: "\\varepsilon", description: "Small positive numerical stabilizer used in denominators and logarithms.", thesis_list: true, order: 365),
  (key: "rl.H", tex: "H", description: "Planning or rollout horizon length.", thesis_list: true, order: 370),
  (key: "rl.validity_mask", tex: "m_{t,i}", description: "Hard validity mask for candidate i at rollout step t.", thesis_list: true, order: 380),
  (key: "rl.invalid_reason", tex: "\\rho_{t,i}", description: "Invalid-action reason code for candidate i at rollout step t.", thesis_list: true, order: 390),
  (key: "rl.target", tex: "e_t", description: "Selected target entity at rollout step t.", thesis_list: true, order: 400),
  (key: "rl.budget", tex: "b_t", description: "Remaining acquisition budget at rollout step t.", thesis_list: true, order: 410),
  (key: "rl.acquisition_cost", tex: "C(\\tau)", description: "Acquisition cost of a selected trajectory.", thesis_list: true, order: 420),
  (key: "shape.Nq", tex: "N_q", description: "Number of candidate views in a candidate table.", thesis_list: true, order: 430),
  (key: "shape.K", tex: "K", description: "Number of ordinal bins or discrete levels when used in scorer losses.", thesis_list: true, order: 440),
  (key: "scene.ray_memory_t", tex: "\\boldsymbol{M}_t^{\\mathrm{ray}}", description: "Sparse actor-visible ray-aware memory separating occupied, free, and unknown support at step t.", thesis_list: true, order: 450),
  (key: "scene.scene_memory_t", tex: "\\boldsymbol{\\Phi}_t^{\\mathrm{scene}}", description: "Composite actor-visible scene-memory descriptor queried by the finite-candidate value model.", thesis_list: true, order: 480),
  (key: "obs.dino_point_bank_t", tex: "\\boldsymbol{F}_t^{\\mathrm{DINO@pt}}", description: "Visibility-gated logged DINO feature bank attached to semidense or fused world points.", thesis_list: true, order: 460),
  (key: "obs.point_tokens_t", tex: "\\boldsymbol{X}_t^{\\mathrm{pt}}", description: "Point-token set combining geometry, support, uncertainty, history, and optional compressed logged descriptors.", thesis_list: true, order: 470),
  (key: "scene.evl_local", tex: "\\boldsymbol{E}_0^{\\mathrm{EVL-local}}", description: "Root local EVL evidence field used for target/candidate support reads.", thesis_list: true, order: 490),
  (key: "scene.evl_support_frac", tex: "\\omega_{t,i}^{\\mathrm{EVL}}", description: "Candidate or target-query fraction supported by the root EVL voxel extent.", thesis_list: true, order: 500),
  (key: "scene.evl_support_token", tex: "\\boldsymbol{g}_{t,i}^{\\mathrm{EVL}}", description: "Pooled local EVL evidence token for a target, candidate frustum, or target-candidate intersection query.", thesis_list: true, order: 510),
  (key: "scene.target_support_pool", tex: "\\boldsymbol{g}_e^{\\mathrm{tgt}}", description: "Pooled target-support descriptor for the selected target hypothesis.", thesis_list: true, order: 520),
  (key: "scene.frustum_support_pool", tex: "\\boldsymbol{g}_{t,i}^{\\mathrm{fr}}", description: "Candidate-frustum support descriptor pooled from actor-visible scene memory.", thesis_list: true, order: 530),
  (key: "scene.target_frustum_pool", tex: "\\boldsymbol{g}_{t,e,i}^{\\cap}", description: "Pooled descriptor over the intersection between target support and candidate frustum support.", thesis_list: true, order: 540),
  (key: "scene.ray_query_ti", tex: "\\boldsymbol{g}_{t,i}^{\\mathrm{ray}}", description: "Candidate-conditioned ray query over occupied, free, unknown, hit, target-support, and uncertainty summaries.", thesis_list: true, order: 550),
  (key: "scene.render_query", tex: "\\operatorname{RenderQuery}", description: "Abstract query operator that summarizes scene memory in a candidate camera/frustum without introducing fresh counterfactual RGB features.", thesis_list: true, order: 560),
  (key: "spatial.ref_pose", tex: "r_t", description: "Reference pose for candidate-relative descriptor construction at decision step t.", thesis_list: true, order: 565),
  (key: "spatial.ref_candidate_transform", tex: "\\boldsymbol{T}_{r_t,i}^{\\mathrm{rel}}", description: "Relative transform from the reference pose r_t to candidate camera i.", thesis_list: true, order: 568),
  (key: "spatial.candidate_pose_feat", tex: "\\boldsymbol{h}_{t,i}^{\\mathrm{pose}}", description: "Relative/local candidate pose descriptor derived from a reference pose rather than raw world coordinates.", thesis_list: true, order: 570),
  (key: "spatial.candidate_target_rel_feat", tex: "\\boldsymbol{h}_{t,e\\mid i}^{\\mathrm{rel}}", description: "Candidate-target relation descriptor in the candidate/query local frame.", thesis_list: true, order: 580),
  (key: "spatial.relation_rpe", tex: "\\boldsymbol{e}_{a\\mid i}^{\\mathrm{rel}}", description: "Query-local relative positional embedding for target, history, support, or candidate relations.", thesis_list: true, order: 590),
  (key: "model.target_token", tex: "\\boldsymbol{h}_e^{\\mathrm{tgt}}", description: "Learned selected-target token built from the actor-visible target descriptor and scene support.", thesis_list: true, order: 600),
  (key: "model.candidate_row", tex: "\\boldsymbol{x}_{t,i}", description: "Per-candidate row feature assembled from pose, relation, support, validity, provenance, and history descriptors.", thesis_list: true, order: 610),
  (key: "entity.endpoint_gain", tex: "J_e^{(H)}", description: "Endpoint reconstruction gain for target e over horizon H.", thesis_list: true, order: 620),
  (key: "entity.log_gain", tex: "J_{e,\\mathrm{log}}^{(H)}", description: "Log-scale endpoint reconstruction gain for target e.", thesis_list: true, order: 630),
  (key: "entity.lookahead_headroom", tex: "\\Delta_{\\mathrm{look}}", description: "Gain available to an oracle lookahead policy beyond one-step selection.", thesis_list: true, order: 640),
  (key: "entity.q_recovery", tex: "\\eta_Q", description: "Fraction of oracle lookahead gain recovered by the Q policy.", thesis_list: true, order: 650),
  (key: "entity.return_h", tex: "G_t^{(H)}", description: "Target-conditioned finite-horizon return.", thesis_list: true, order: 660),
  (key: "obs.depth", tex: "\\boldsymbol{D}", description: "Depth observation sequence.", thesis_list: true, order: 670),
  (key: "obs.face_normal", tex: "\\boldsymbol{n}", description: "Per-point or per-face normal observation.", thesis_list: true, order: 680),
  (key: "obs.img_rgb", tex: "\\boldsymbol{I}^{\\mathrm{rgb}}", description: "RGB image observation.", thesis_list: true, order: 690),
  (key: "obs.points_cf", tex: "\\mathcal{P}^{\\mathrm{cf}}", description: "Counterfactual point observation.", thesis_list: true, order: 700),
  (key: "obs.points_semi", tex: "\\mathcal{P}^{\\mathrm{semi}}", description: "Semi-dense observed point set.", thesis_list: true, order: 710),
  (key: "obs.points_t", tex: "\\mathcal{P}_t", description: "Point set available at rollout step t.", thesis_list: true, order: 720),
  (key: "rl.candidate_table", tex: "\\mathcal{Q}_t", description: "Finite candidate-view table at rollout step t.", thesis_list: true, order: 730),
  (key: "vin.field_v", tex: "\\boldsymbol{F}_v", description: "Learned value field evaluated at v.", thesis_list: true, order: 740),
)

#for entry in aria-notation-symbols [
  #metadata(entry) <aria-notation-symbol>
]
