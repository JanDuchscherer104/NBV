# Thesis Teaching Packet

Use this reference only for an `aria-grill` branch that is both thesis-facing
and conceptual, elaborate, theory-rich, or deep-theory. The packet preserves the educational
value of the reasoning before a decision is compressed into academic prose.

The packet is task-local. It does not own thesis claims, architecture, notation,
or implementation behavior. Accepted conclusions move through
`academic-writing`; exact sources remain authoritative.

## 1. Reader contract

Begin with:

- destination chapter or section;
- matching `reader-state.toml` record;
- incoming reader state;
- one active reader question;
- one to three durable takeaways;
- outgoing dependency;
- whether the accepted decision would change the ledger.

A packet that cannot name this transition is not ready to discuss an
architecture.

## 2. Motivating case

Teach one normal case, one boundary case, and one failure case. Prefer a
concrete target, causal observation history, and small candidate set. Explain
what the reader should notice before naming model classes or protocol fields.

For target-conditioned NBV, a useful normal case is an occluded object for which
a modest side-step enables a later informative view. A boundary case may have
no non-myopic headroom on the available candidate support. A failure case may
appear to improve only because privileged geometry or a counterfactual render
entered the actor state.

## 3. Objects and transformations

Name the physical and mathematical objects before discussing an encoder:

- scene evidence and its spatial support;
- requested target and target frame;
- realized causal history;
- candidate poses or rays;
- feasible candidate set;
- remaining budget and requested horizon;
- scalar values, selected actions, and successor states.

For every coordinate frame, state what a global rigid transformation changes
and what it should leave unchanged.

### Invariance and equivariance

Let \(g\) denote a change of global coordinates and let \(\rho(g)\) describe how
a geometric feature transforms. An equivariant representation has the form

$$
F(g \cdot x) = \rho(g) F(x).
$$

A scalar candidate value should normally be invariant to a consistent global
frame change:

$$
Q(g \cdot s,\; g \cdot e,\; g \cdot q,\; h)
= Q(s,\; e,\; q,\; h).
$$

For an ordered materialization of an unordered candidate set, permuting the
candidate rows should permute the output values in the same way:

$$
Q(s,\; e,\; \pi \mathcal{Q},\; h)
= \pi Q(s,\; e,\; \mathcal{Q},\; h).
$$

Use these equations only after defining the state \(s\), target \(e\),
candidate \(q\), candidate set \(\mathcal{Q}\), horizon \(h\), transformation
\(g\), and permutation \(\pi\). State whether the implementation enforces,
approximates, augments for, or merely hopes to learn each property.

### Isomorphism discipline

Use *isomorphism* only for a bijective structure-preserving map with a
structure-preserving inverse. Use *correspondence*, *reparameterization*,
*equivalence under a group action*, or *architectural analogy* when that is what
the evidence supports.

## 4. Spatio-temporal causal state

Explain time through the information boundary:

- the actor state contains only the observation prefix available before the
  current action;
- an unselected candidate outcome is a counterfactual label, not a factual next
  observation;
- the selected action may create one factual successor;
- remaining budget describes opportunity still available;
- requested horizon describes how far the value target summarizes consequences.

Ask which dependency is already represented by poses, timestamps,
observations, and budget. Introduce recurrent, state-space, or sequence models
only for a remaining order- or duration-dependent distinction. A time axis in
the dataset does not by itself justify a temporal architecture.

## 5. Hierarchical structure

Keep these levels distinct:

1. environment or scene;
2. requested target;
3. current causal state;
4. feasible candidate set;
5. individual candidate;
6. selected action and factual successor;
7. rollout;
8. scene-level experimental population.

For each model operation, state the level at which it acts:

- shared scene encoding;
- target conditioning;
- history aggregation;
- candidate-relative relation construction;
- candidate-set interaction;
- action selection;
- rollout-level return construction;
- scene-level aggregation and uncertainty.

This makes the scientific hierarchy visible without mistaking tensor axes for
concepts.

## 6. Scene and target representation design

Compare a representation by the distinctions and symmetries it preserves, its
support, and the failure it is intended to repair.

### EVL voxel fields

A voxel field provides a regular local lattice and convenient neighborhood
structure. It also raises questions about:

- finite spatial support and boundary truncation;
- discretization resolution and aliasing;
- occupied, free, observed, and unknown space;
- sparse evidence inside a dense carrier;
- interpolation between candidate geometry and grid locations;
- arbitrary grid orientation or global frame dependence;
- target alignment and loss of object-relative detail;
- whether the stored channels describe geometry, appearance, semantics,
  uncertainty, or a learned mixture.

Useful derived representations may include:

- multiscale target-centred crops;
- sparse occupied or observed/unknown tokens;
- semidense or surface point sets;
- local field gradients, normals, or boundary cues;
- pooled moments with signed directional information;
- candidate-target and candidate-history relative transforms;
- relational graphs or bipartite candidate-to-state neighborhoods;
- renderable fields when differentiable view synthesis is the missing
  capability.

A derived representation is justified by a lost distinction demonstrated in
the current carrier. Architectural novelty is not a diagnosis.

### Representation comparison

For each option, answer:

1. What information enters?
2. In which frame and spatial support?
3. Which transformations should preserve or predictably transform the output?
4. What can be pooled without losing the decision?
5. What target and candidate relations remain explicit?
6. What memory, compute, and sample complexity does it introduce?
7. What matched ablation would reveal its value?

## 7. Limited data and supervision asymmetry

Keep separate counts for independent scenes, logged snippets, overlapping
windows, realized decision states, factual transitions, feasible
counterfactual labels, targets, and simulator trajectories. Generalization
evidence remains scene-level even when other counts grow.

Before proposing a smaller ATEK download or preprocessing stride, inspect the
active configuration owner. A smaller stride may expose more overlapping
factual windows and more starting states. It does not create new environments,
and heavy overlap can increase leakage or reduce effective sample diversity
unless splitting and sampling remain scene-aware.

Distinguish data strategies:

- geometric and photometric augmentation changes nuisance variation;
- self-supervision extracts additional targets from existing observations;
- pretrained representations import structure learned elsewhere;
- repeated factual rollouts add realized causal transitions;
- counterfactual rendering adds privileged action labels;
- simulation adds environments and trajectories only to the extent that its
  distribution and interfaces are credible.

### Factual-counterfactual asymmetry

Record, modality by modality, what exists for:

- logged factual history;
- selected factual successor;
- unselected counterfactual candidate;
- oracle-only geometry;
- simulator-generated observation.

A model comparison is interpretable only when actor-visible modalities are
matched or the asymmetry is the explicit ablation. Ground-truth mesh renders
can leak target geometry, visibility, or future surfaces; provenance and masks
do not by themselves make that information deployable.

## 8. External simulator adapter

A useful simulator is not merely a renderer. To plug it into the existing
environment cleanly, define one adapter contract covering:

1. scene and asset sampling, including target identities and geometry;
2. coordinate frames, units, camera calibration, and timestamps;
3. action or pose requests plus endpoint and transition feasibility;
4. observation modalities, sensor noise, missingness, and latency;
5. factual transition semantics and causal history updates;
6. oracle-only assets and counterfactual label generation;
7. deterministic seeds, provenance, versioning, and replay identity;
8. domain randomization and reality checks against ATEK/ASE statistics.

The lowest-risk first integration is an offline generator that emits the same
normalized state, candidate, selected-transition, and oracle-label concepts as
the existing pipeline. Online closed-loop integration follows only when the
action and observation semantics match.

Compare simulator options by adapter fit, sensor and scene realism, asset
licensing, throughput, headless operation, deterministic replay, and the effort
required to reproduce Project Aria camera and modality characteristics.

## 9. Minimal formalism

After the concepts are clear, list only the equations needed by the decision.
For each equation give:

- conceptual quantity;
- symbols, frames, domain, and units;
- desired invariance or equivariance;
- worked example or limiting case;
- consequence for architecture or experiment design.

Keep implementation identifiers outside the equations.

## 10. Evidence and option ledger

For each material statement, label it as definition, implementation fact,
literature claim, project decision, hypothesis, or inference. For each option,
state preserved information, symmetry behavior, temporal and hierarchical
fit, data requirement, failure modes, evidence strength, and discriminating
test.

End with one recommended option and the explicit tradeoff. Preserve genuinely
open decisions instead of disguising them as prose.

## 11. Academic-writing handoff

Return:

- plain-language answer;
- motivating normal, boundary, and failure cases;
- concept dependency chain;
- minimal formal objects and equations;
- recommended explanation order;
- one to three takeaways;
- exact source owners and evidence status;
- implementation mapping needed, if any;
- main-text versus appendix disposition;
- unresolved questions;
- ledger impact.

`academic-writing` rechecks the sources and converts this packet into a
teaching-first candidate. It does not paste the packet wholesale into the
thesis.
