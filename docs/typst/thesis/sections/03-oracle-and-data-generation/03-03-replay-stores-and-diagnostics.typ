#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../../shared/tables.typ": publication-table

== Dataset and Storage Semantics

The replay dataset is organized around decision-state relations. Each state
binds an information state $s_t$ and target $e$ to a candidate table
#symb.rl.candidate_table, row-specific feasibility and label masks, oracle
outcomes where defined, and the selected successor. Its normalized lineage
connects a source to target tasks, retained chains, decision states, and
candidate rows.

One logged source can support several target tasks. Each task can be explored by
several rollout recipes. A retained chain contains ordered selected steps, and
each step owns the full finite candidate shell. This layout preserves two forms
of supervision. Candidate rows record the counterfactual outcomes available at
one state; the selected row $a_t$ links that state to the factual successor
$s_(t+1)$. The first supports dense one-step ranking, while the second supports
finite-horizon returns along a causal trajectory.

#figure(
  align(center, image(
    "../../figures/replay_lineage_relations.pdf",
    width: 100%,
  )),
  caption: [Normalized replay lineage. A source defines target tasks; each task
  produces recipe-specific retained chains; each chain orders factual decision
  states; and each state owns one complete candidate shell. Model-ready tensors
  are derived by padding and batching these relations.],
) <fig:offline-rollout-store-relation>

#figure(
  publication-table(
    columns: (0.75fr, 0.85fr, 1.45fr),
    header: ([*Stored relation*], [*Mathematical role*], [*Scientific meaning*]),
    rows: (
      (
        [Source--target],
        [$s_0, e$],
        [Binds a task to one immutable logged substrate and one declared target source.],
      ),
      (
        [State--candidate],
        [$s_t, q_(t,i)$],
        [Preserves the full proposal support, hard feasibility, label availability, and proposal provenance.],
      ),
      (
        [Selected transition],
        [$(s_t, a_t, r_t^e, s_(t+1))$],
        [Records the causal edge created by the selected action.],
      ),
      (
        [Retained chain],
        [$(s_0, a_0, dots, s_H)$],
        [Identifies the recipe-specific trajectory from which finite-horizon returns may be derived.],
      ),
      (
        [Derived training view],
        [$(bold(X), bold(m), bold(y))$],
        [Pads and batches factual relations without changing their information or missingness semantics.],
      ),
    ),
  ),
  caption: [Scientific roles of the normalized replay relations. State, target,
  action support, supervision, and lineage are bound before model-specific
  tensorization.],
) <tab:current-rollout-store-audit>

=== Immutable Sources and Causal Replay

An immutable source store owns the logged actor substrate and one-step oracle
products. A replay store references those identities and adds target tasks,
retained chains, per-state candidate shells, selected-action successors, and
recipe provenance. Changing a rollout recipe creates a new replay dataset over
the same source facts. Observations and one-step oracle products keep stable
identities across those experiments, which enables paired comparison.

For each selected action, replay stores one calibrated depth raster. The ordered
rasters reconstruct the selected-observation prefix without duplicating every
candidate render inside each chain. Source role stays attached to each raster:
mesh-rendered depth defines the privileged causal control, and sensor-like or
observed depth defines an actor-side successor. Candidate renders for unselected
rows stay with the one-step oracle products used to construct labels.

The stored data-generation transition is

$
  #eqs.rl.replay_transition
$

It updates reference pose, selected history, budget, and the next candidate
table under generation context $xi_t$. A visual successor adds a separately
specified observation operator and state update for RGB, depth, EFM3D features,
or surface memory. The rollout recipe retains the chains it selects or keeps in
its beam. Matched oracle endpoint re-evaluation then supplies a common
fixed-budget outcome for policy comparison.

=== Missingness and Derived Views

Every candidate row carries separate predicates for materialization,
actor-feasible action #symb.rl.action_mask, finite value label
#symb.rl.q_label_mask, and factual successor #symb.rl.successor_mask. These
predicates describe structure, action support, supervision support, and
trajectory heritage. A training objective may select their intersection; the
stored fields preserve the reason each row enters or leaves that population.

Model-ready arrays are deterministic projections of the normalized store. They
pad candidate shells, expand a chain into state queries, and cache features
while preserving source identity, target identity, state order, masks,
requested horizon, and label provenance. Several states from one chain may
share a batch, but each query receives only its own causal prefix.

Reproducibility requires content identity and transformation identity.
The source manifest fixes scene, snippet, target, geometry, and oracle products;
the rollout manifest fixes proposal profile, pruning, recipe, seed, and
retention; the training view fixes tensorization and supported horizons.
Coverage, failed roots, family survival, undefined metrics, source-role counts,
and exclusions define the population to which a learned value claim applies.
Compression, chunking, hashes, and execution commands complete the
reproducibility record. Development bandwidth pilots contribute cost estimates;
held-out policy evidence comes from the evaluation protocol in Chapter 5.
