#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "@preview/booktabs:0.0.4": *

== Persisted Descriptor Interface

// implementation: rollouts/zarr_store.py; targets/descriptor.py; vin/models/target_myopic.py
The rollout store is the reproducible interface between data generation and finite-horizon learning. It preserves factual source, target, rollout, step, candidate, diagnostic, and lineage tables; the `q_h/` group is a validated dense view derived from those tables. A model reader may transform these fields into tensors, but it must not change their identity, mask, or provenance semantics. In the implemented V0 task, target pose and extents may be GT-derived: they are a privileged oracle-task instruction sanitized to the target-descriptor interface, not actor-visible evidence. Candidate geometry and masks are decision inputs, whereas oracle gains, GT associations, crops, and renders remain labels or audit metadata. Any non-privileged learned-policy claim requires observation-derived or predicted target fields with explicit provenance.

The target table records the target row and stable target identifier, selection policy and rank, source and source index, semantic and instance identifiers, class and confidence, geometric support fields, centre, extents, world pose, reference-relative pose, target-invalidity fields, and GT-association diagnostics. Only the semantic and geometric instruction fields are admitted to the current V0 generator, but sanitizing their interface does not remove their privileged GT origin. Selection statistics may be used to stratify the dataset, while matched-GT identifiers, match scores, crop policy, and target-validity outcomes remain supervision or provenance.

Each candidate row records its persistent row, step, rollout, shell, and compact-valid indices; world and root-relative camera poses; actor, oracle-label, training, and selected masks; strategy, position, and mixture identifiers; sampling probability; invalid-reason codes; target and scene metrics; support measurements; and selection statistics. A companion diagnostic row contains mesh clearance, collision, free-space margin, motion, target-distance, and target-bearing measurements. Some diagnostics depend on privileged mesh geometry and must therefore be excluded from a deployable actor even though they are readable from the training artifact.

#figure(
  text(size: 8.5pt, table(
    columns: (0.72fr, 1.45fr, 1.05fr),
    toprule(),
    table.header([*Carrier*], [*Fields retained by the replay contract*], [*Learning role*]),
    midrule(),
    [Target],
    [semantic identity, class, pose, extents, reference-relative pose, source and validity provenance],
    [privileged V0 task instruction; learned actors require observed or predicted equivalents],
    [Candidate],
    [row identities, world/root-relative pose, masks, reason codes, sampler provenance, support and selection fields],
    [finite action row; privileged diagnostics require source gating],
    [Selected chain],
    [root pose, selected row and shell indices, step order, policy, seed, next-step link, terminal state],
    [history and temporal-difference linkage],
    [Oracle labels],
    [target RRI, target root gain, point--mesh errors, optional target crops and selected depth],
    [loss, evaluation, and audit only],
    bottomrule(),
  )),
  caption: [Implemented replay carriers and their admissible learning roles. Readability from the store does not by itself make a field actor-visible.],
) <tab:thesis-descriptor-schema>

The current V0 candidate descriptor is consequently a function of the sanitized but privileged target geometry, the current/root reference pose, the selected-pose history, the candidate pose, its hard mask and reason code, and sampler provenance. Relative translation and rotation may be derived from `pose_relative_root`; target range and bearing may be recomputed from the V0 target instruction. A non-privileged actor must instead receive an observation-derived or predicted target pose, extent, and identity under the same typed interface. Global target gains, all-candidate oracle renders, matched-GT rows, mesh-clearance diagnostics, and GT target crops must not enter either descriptor.

The current model path does not yet consume a positive-width target descriptor. The target-conditioned myopic configuration accepts the existing VINv3 path only with descriptor width zero and rejects positive widths explicitly. Likewise, no training reader currently assembles the above replay fields into a #symb.rl.qh network batch. The table is therefore an implemented storage interface and leakage boundary, not a claim that every stored field is admissible to, or already encoded by, a trained model.
