#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb

== Finite-Horizon Value Interface

// implementation boundary: vin/models/target_finite_horizon.py; lightning/_candidate_scorer_contract.py; rollouts/zarr_store.py
The intended learned quantity is the value of choosing one valid row from the current finite table and then following a bounded policy for at most $H-1$ further selections. With target-root-gain reward $r_(t+k)^e$ and discount $gamma$, the training target is

$
  Q_H(s_t, a_t)
  =
  bb(E) [sum_(k=0)^(H-1) gamma^k r_(t+k)^e mid s_t, a_t].
$

The action dimension is the padded full-shell axis of the `q_h/` view. Every predicted value must remain aligned with its candidate row, and invalid rows must be excluded from action selection and bootstrap maximization. The selected-transition fields provide the observed reward, successor step identifier, terminal flag, and discount needed for a masked temporal-difference objective. Held-out policy quality must still be measured by oracle re-scoring the trajectories selected by the learned model rather than by training loss alone.

The existing myopic VINv3 scorer is a control, not an implementation of this value function. It predicts per-candidate ordinal one-step RRI scores through the current CORAL training path and consumes scene evidence plus candidate geometry without a target token. The target-conditioned myopic configuration is runnable only with target-descriptor width zero. Positive target widths are deliberately rejected until target-token ownership is implemented.

The finite-horizon scorer is likewise an explicit scaffold. Its configuration records a horizon, discount, and candidate-token width, but constructing the model raises `NotImplementedError`. The existing Lightning module rejects this configuration because its CORAL `VinPrediction` objective does not consume rollout returns, hard valid-action masks, or selected-transition links. Therefore no candidate-query Transformer, residual value head, target network, Double-Q update, distributional head, or trained multi-step policy is claimed here.

The immediate implementation task is narrow: build a dedicated reader and training module over the validated `q_h/` arrays, join only actor-admissible target and candidate fields, emit one value per padded shell row, and enforce the masks described in @sec:thesis-method-geometry-contract. A row-independent masked MLP is the necessary first control because its semantics are easy to test. Candidate-to-state attention or candidate-candidate interaction should be introduced only after the control passes the same oracle-evaluated policy comparison. This order tests whether multi-step replay contains learnable headroom before attributing gains to a more elaborate architecture.

The method is consequently complete at the data-contract level but not at the learned-planner level. The present thesis can evaluate rollout coverage, target-root-gain headroom, mask correctness, and policy baselines from the stored artifacts. Claims about learned finite-horizon improvement require a subsequent trained checkpoint, frozen configuration, held-out split, and oracle re-evaluation.
