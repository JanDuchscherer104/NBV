---
id: 2026-06-25_candidate_generation_geometry_figure
date: 2026-06-25
title: "Thesis Geometry And Architecture Figures"
status: done
topics: [thesis, typst, diagrams, candidate-generation, candidate-validity, directional-memory, symmetry-contract, learning-evidence, oracle-lookahead, teacher-student, leakage-boundary, qh, rri, actor-oracle-boundary, rollout-replay, camera-frames, scene-encoding, target-task-sampler, citations]
confidence: high
canonical_updates_needed: []
artifacts:
  - docs/typst/thesis/figures/candidate_generation_geometry.typ
  - docs/typst/thesis/figures/candidate_generation_geometry.pdf
  - docs/typst/thesis/figures/qh_candidate_query_architecture.typ
  - docs/typst/thesis/figures/qh_candidate_query_architecture.pdf
  - docs/typst/thesis/figures/target_rri_point_mesh_geometry.typ
  - docs/typst/thesis/figures/target_rri_point_mesh_geometry.pdf
  - docs/typst/thesis/figures/actor_oracle_boundary.typ
  - docs/typst/thesis/figures/actor_oracle_boundary.pdf
  - docs/typst/thesis/figures/rollout_replay_doubleq_process.typ
  - docs/typst/thesis/figures/rollout_replay_doubleq_process.pdf
  - docs/typst/thesis/figures/camera_frame_ray_contract.typ
  - docs/typst/thesis/figures/camera_frame_ray_contract.pdf
  - docs/typst/thesis/figures/feature_bank_query_pools.typ
  - docs/typst/thesis/figures/feature_bank_query_pools.pdf
  - docs/typst/thesis/figures/target_task_sampler_contract.typ
  - docs/typst/thesis/figures/target_task_sampler_contract.pdf
  - docs/typst/thesis/figures/candidate_validity_pruning_examples.typ
  - docs/typst/thesis/figures/candidate_validity_pruning_examples.pdf
  - docs/typst/thesis/figures/oracle_lookahead_tree.typ
  - docs/typst/thesis/figures/oracle_lookahead_tree.pdf
  - docs/typst/thesis/figures/teacher_student_render_path.typ
  - docs/typst/thesis/figures/teacher_student_render_path.pdf
  - docs/typst/thesis/figures/directional_memory_view_novelty.typ
  - docs/typst/thesis/figures/directional_memory_view_novelty.pdf
  - docs/typst/thesis/figures/qh_symmetry_acceptance_contract.typ
  - docs/typst/thesis/figures/qh_symmetry_acceptance_contract.pdf
  - docs/typst/thesis/figures/qh_learning_evidence_loop.typ
  - docs/typst/thesis/figures/qh_learning_evidence_loop.pdf
  - docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ
  - docs/typst/thesis/sections/05-experimental-design/05-01-objectives-and-hypotheses.typ
  - docs/typst/thesis/sections/05-experimental-design/05-02-learning-objective-and-replay-evidence.typ
  - docs/typst/thesis/sections/04-method/index.typ
  - docs/typst/thesis/sections/04-method/04-01-scene-representation-requirements.typ
  - docs/typst/thesis/sections/04-method/04-02-descriptor-and-encoding-plan.typ
  - docs/typst/thesis/sections/04-method/04-04-architecture-contract.typ
  - docs/typst/thesis/sections/04-method/04-05-finite-candidate-value-model.typ
  - docs/references.bib
  - /tmp/aria-thesis-candidate-geometry.pdf
  - /tmp/aria-thesis-qh-architecture-final.pdf
  - /tmp/aria-thesis-target-rri-geometry-v2.pdf
  - /tmp/aria-thesis-actor-oracle-boundary-v2.pdf
  - /tmp/aria-thesis-rollout-doubleq-v3.pdf
  - /tmp/aria-thesis-camera-ray-final.pdf
  - /tmp/aria-thesis-scientific-coherence.pdf
  - /tmp/aria-thesis-feature-bank-query-pools.pdf
  - /tmp/aria-thesis-target-task-sampler.pdf
  - /tmp/aria-thesis-candidate-validity-pruning-final.pdf
  - /tmp/aria-thesis-oracle-lookahead-tree-final.pdf
  - /tmp/aria-thesis-teacher-student-render-path-final.pdf
  - /tmp/aria-thesis-directional-memory-final.pdf
  - /tmp/aria-thesis-symmetry-contract.pdf
  - /tmp/aria-thesis-learning-evidence-loop.pdf
---

## Task

Continue the thesis diagram goal by adding clean scientific visualizations for
architecture/process or geometric isomorphisms in the current thesis.

## Output

Added a standalone CeTZ source/PDF figure for the target-conditioned candidate
generation geometry. The figure shows the reference-frame direction cap, the
three center-family reinterpretations of the same shell support, and the
target-look camera/frustum relation. It is integrated in
`docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ`
beside the sampler equations.

Added a standalone Fletcher source/PDF figure for the default `Q_H`
candidate-query architecture. It replaces the broad Mermaid VIN/GNN graph in
`docs/typst/thesis/sections/04-method/04-05-finite-candidate-value-model.typ`
with a cleaner actor-visible context, candidate-row, candidate-to-state query,
residual value-head, hard-mask, optional-set-context, and oracle-supervision
contract.

Added a standalone CeTZ source/PDF figure for target-specific point-mesh RRI
geometry. The figure shows the before/after target crop, point-to-mesh accuracy
witnesses, mesh-to-point completeness witnesses, selected candidate points, and
the root-normalized target reward connection. It is integrated in the
target-specific RRI subsection before the formal target-error equation.

Added a standalone Fletcher source/PDF figure for the actor/oracle leakage
boundary. The figure replaces the broad Mermaid graph in
`docs/typst/thesis/sections/03-oracle-and-data-generation/03-01-state-and-visibility.typ`
with a compact three-column contract: actor-visible evidence, legal `Q_H`
interface, and oracle-only products. The surrounding prose now cites the
Project Aria/ASE, EFM3D/EVL, and VIN-NBV sources before stating the leakage
constraint.

Added a standalone Fletcher source/PDF figure for rollout materialization and
masked Double-Q learning. The figure is integrated in
`docs/typst/thesis/sections/04-method/04-03-candidate-and-replay-contract.typ`
after the minimum replay-row contract. It shows that all valid rows can receive
one-step oracle labels, but only the selected action creates successor
observations; the paired learning lane shows replay sampling, online valid-row
selection, target-network backup, masked loss, and held-out oracle re-scoring.

Added a standalone CeTZ source/PDF figure for the camera-frame and ray contract
behind oracle labels. The figure is integrated in
`docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ`
after the seminar oracle substrate paragraph. It shows the LUF candidate camera,
mesh-rendered depth, pixel/ray unprojection, world-frame transform, selected
candidate point set, and target crop used for point-mesh scoring.

Added `cetz.md` to the Typst package references with the checked package
version, source URL, and compile commands required by the local package policy.

Patched the Chapter 04 method sections for a stronger scientific through-line:
the chapter now states its dependency order; the scene-representation
requirements distinguish target proposer, queryable memory, and modality
availability; the descriptor protocol introduces descriptor blocks in causal
order; relative candidate descriptors are justified as query-frame gauge
choices; and the architecture/value sections frame attention and set
interaction as acceptance-tested ablations rather than default complexity.
Added a primary DINOv2 bibliography entry so the logged DINO-on-point branch is
cited directly alongside EFM3D.

Added a standalone CeTZ source/PDF figure for the actor-visible feature-bank
query pools. The figure is integrated in
`docs/typst/thesis/sections/04-method/04-02-descriptor-and-encoding-plan.typ`
after the candidate-pool equation. It visualizes the same actor-visible memory
being queried by target OBB support, candidate-frustum support,
target-frustum-intersection support, and ray render/query predicates, while
separating point carriers, optional logged DINO, ray memory, local EVL support,
and missing-modality masks.

Added a standalone CeTZ source/PDF figure for the oracle target-task sampler
contract. It replaces the old Mermaid-rendered sampler include in
`docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ`
while keeping the existing figure label. The native figure emphasizes the
identity gate, best/runner-up OBB IoU ambiguity gap, deterministic target cap,
target-task row, rollout generation, GT-EVAL labels, and the actor-input
boundary that forbids GT boxes as model input.

Added a standalone CeTZ source/PDF figure for candidate validity and pruning
examples. It is integrated in
`docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ`
between the motion-pruning equation and the valid-support threshold. The figure
separates feasible scored rows from path-collision, mesh-clearance, and
out-of-support hard masks, and explicitly keeps valid low-gain/low-support
candidates as supervised low-utility rows rather than invalid actions.

Added a standalone Fletcher source/PDF figure for bounded oracle-lookahead.
It is integrated in
`docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ`
after the canonical rollout recipe table. The tree distinguishes one-step
greedy selection from horizon-two chain selection, shows beam retention over
valid prefixes, and keeps hard-masked invalid rows outside oracle branch
expansion and return-target construction.

Added a standalone Fletcher source/PDF figure for the teacher/student render
path in Chapter 05. It replaces the old Mermaid-rendered include in
`docs/typst/thesis/sections/05-experimental-design/05-01-objectives-and-hypotheses.typ`
while preserving `<fig:qh-teacher-student-render-path>`. The native figure
separates the legal V1 student actor path, privileged GT/teacher/oracle
products, training-only losses/distillation, and forbidden V1 inference
features.

Added a standalone CeTZ source/PDF figure for target-local directional memory.
It replaces the old Mermaid-rendered include in
`docs/typst/thesis/sections/04-method/04-02-descriptor-and-encoding-plan.typ`
while preserving `<fig:qh-directional-memory>`. The native figure shows the
geometric descriptor isomorphism directly: selected camera centers induce unit
directions around a target-local point or voxel, those directions are compressed
as low-order directional coefficients or second moments on $bb(S)^2$, and a
candidate view reads a novelty feature without becoming a new observation.

Added a standalone Fletcher source/PDF figure for the minimum #symb.rl.qh
symmetry and provenance contract. It replaces the old Mermaid-rendered include
in `docs/typst/thesis/sections/04-method/04-04-architecture-contract.typ`
while preserving `<fig:qh-symmetry-contract>`. The native figure frames the
architecture claim as acceptance tests: actor-visible state and candidate rows
are converted into local-frame geometry, target-local directional history, and
a mask-safe scorer; row permutation, mask isolation, and actor/oracle
provenance gates are then explicit checks rather than informal model desiderata.

Added a standalone Fletcher source/PDF figure for the Chapter 05 learning
evidence loop. It replaces the old Mermaid-rendered sequence diagram in
`docs/typst/thesis/sections/05-experimental-design/05-02-learning-objective-and-replay-evidence.typ`
while preserving `<fig:qh-rollout-replay-doubleq>`. The native figure separates
one-step all-valid oracle labels from selected-transition successor evidence,
then shows masked Double-Q training, held-out policy deployment, oracle
re-scoring, and reportable paired comparisons as distinct evidence gates.

## Verification

- `cd docs && typst compile typst/thesis/figures/candidate_generation_geometry.typ typst/thesis/figures/candidate_generation_geometry.pdf --root .`
- `cd docs && typst compile typst/thesis/figures/qh_candidate_query_architecture.typ typst/thesis/figures/qh_candidate_query_architecture.pdf --root .`
- `cd docs && typst compile typst/thesis/figures/target_rri_point_mesh_geometry.typ typst/thesis/figures/target_rri_point_mesh_geometry.pdf --root .`
- `cd docs && typst compile typst/thesis/figures/actor_oracle_boundary.typ typst/thesis/figures/actor_oracle_boundary.pdf --root .`
- `cd docs && typst compile typst/thesis/figures/rollout_replay_doubleq_process.typ typst/thesis/figures/rollout_replay_doubleq_process.pdf --root .`
- `cd docs && typst compile typst/thesis/figures/camera_frame_ray_contract.typ typst/thesis/figures/camera_frame_ray_contract.pdf --root .`
- `cd docs && typst compile typst/thesis/figures/feature_bank_query_pools.typ typst/thesis/figures/feature_bank_query_pools.pdf --root .`
- `cd docs && typst compile typst/thesis/figures/target_task_sampler_contract.typ typst/thesis/figures/target_task_sampler_contract.pdf --root .`
- `cd docs && typst compile typst/thesis/figures/candidate_validity_pruning_examples.typ typst/thesis/figures/candidate_validity_pruning_examples.pdf --root .`
- `cd docs && typst compile typst/thesis/figures/oracle_lookahead_tree.typ typst/thesis/figures/oracle_lookahead_tree.pdf --root .`
- `cd docs && typst compile typst/thesis/figures/teacher_student_render_path.typ typst/thesis/figures/teacher_student_render_path.pdf --root .`
- `cd docs && typst compile typst/thesis/figures/directional_memory_view_novelty.typ typst/thesis/figures/directional_memory_view_novelty.pdf --root .`
- `cd docs && typst compile typst/thesis/figures/qh_symmetry_acceptance_contract.typ typst/thesis/figures/qh_symmetry_acceptance_contract.pdf --root .`
- `cd docs && typst compile typst/thesis/figures/qh_learning_evidence_loop.typ typst/thesis/figures/qh_learning_evidence_loop.pdf --root .`
- `cd docs && typst compile typst/thesis/main.typ /tmp/aria-thesis-candidate-geometry.pdf --root . --input aria-wip-links=false`
- `cd docs && typst compile typst/thesis/main.typ /tmp/aria-thesis-qh-architecture-final.pdf --root . --input aria-wip-links=false`
- `cd docs && typst compile typst/thesis/main.typ /tmp/aria-thesis-target-rri-geometry-v2.pdf --root . --input aria-wip-links=false`
- `cd docs && typst compile typst/thesis/main.typ /tmp/aria-thesis-actor-oracle-boundary-v2.pdf --root . --input aria-wip-links=false`
- `cd docs && typst compile typst/thesis/main.typ /tmp/aria-thesis-rollout-doubleq-v3.pdf --root . --input aria-wip-links=false`
- `cd docs && typst compile typst/thesis/main.typ /tmp/aria-thesis-camera-ray-final.pdf --root . --input aria-wip-links=false`
- `cd docs && typst compile typst/thesis/main.typ /tmp/aria-thesis-scientific-coherence.pdf --root . --input aria-wip-links=false`
- `cd docs && typst compile typst/thesis/main.typ /tmp/aria-thesis-feature-bank-query-pools.pdf --root . --input aria-wip-links=false`
- `cd docs && typst compile typst/thesis/main.typ /tmp/aria-thesis-target-task-sampler.pdf --root . --input aria-wip-links=false`
- `cd docs && typst compile typst/thesis/main.typ /tmp/aria-thesis-candidate-validity-pruning-final.pdf --root . --input aria-wip-links=false`
- `cd docs && typst compile typst/thesis/main.typ /tmp/aria-thesis-oracle-lookahead-tree-final.pdf --root . --input aria-wip-links=false`
- `cd docs && typst compile typst/thesis/main.typ /tmp/aria-thesis-teacher-student-render-path-final.pdf --root . --input aria-wip-links=false`
- `cd docs && typst compile typst/thesis/main.typ /tmp/aria-thesis-directional-memory-final.pdf --root . --input aria-wip-links=false`
- `cd docs && typst compile typst/thesis/main.typ /tmp/aria-thesis-symmetry-contract.pdf --root . --input aria-wip-links=false`
- `cd docs && typst compile typst/thesis/main.typ /tmp/aria-thesis-learning-evidence-loop.pdf --root . --input aria-wip-links=false`
- Rendered and visually inspected `/tmp/aria-thesis-candidate-page-044.png`,
  `/tmp/aria-thesis-candidate-page-045.png`, and
  `/tmp/aria-thesis-candidate-page-046.png`.
- Rendered and visually inspected `/tmp/aria-thesis-qh-final-page-075.png`.
- Rendered and visually inspected `/tmp/aria-thesis-rri-v2-page-048.png`.
- Rendered and visually inspected `/tmp/aria-thesis-actor-oracle-v2-page-037.png`.
- Rendered and visually inspected `/tmp/aria-thesis-rollout-doubleq-v3-page-068.png`.
- Rendered and visually inspected `/tmp/aria-thesis-camera-ray-final-page-040.png`.
- Rendered and visually inspected `/tmp/aria-feature-bank-query-pools-1.png`
  and `/tmp/aria-thesis-feature-bank-page-065.png`.
- Rendered and visually inspected `/tmp/aria-target-task-sampler-1.png`
  and `/tmp/aria-thesis-target-task-sampler-page-042.png`.
- Rendered and visually inspected `/tmp/aria-candidate-validity-pruning-tworow3-1.png`
  and `/tmp/aria-thesis-candidate-validity-pruning-final-page-047c.png`.
- Rendered and visually inspected `/tmp/aria-oracle-lookahead-tree-final2-1.png`
  and `/tmp/aria-thesis-oracle-lookahead-tree-final-page-048b.png`.
- Rendered and visually inspected `/tmp/aria-teacher-student-render-path-tight-1.png`
  and `/tmp/aria-thesis-teacher-student-render-path-final-page-082c.png`.
- Rendered and visually inspected `/tmp/aria-directional-memory-view-novelty.png`,
  `/tmp/aria-thesis-directional-memory-final-page-068.png`, and
  `/tmp/aria-thesis-directional-memory-final-page-069.png`.
- Rendered and visually inspected `/tmp/aria-qh-symmetry-acceptance-contract.png`
  and `/tmp/aria-thesis-symmetry-contract-page-073.png`.
- Rendered and visually inspected `/tmp/aria-qh-learning-evidence-loop.png`
  and `/tmp/aria-thesis-learning-evidence-loop-page-084.png`.
- `pdftotext /tmp/aria-thesis-candidate-validity-pruning-final.pdf - | rg -n "Candidate validity and pruning examples|missing reference|\?\?"`
- `pdftotext /tmp/aria-thesis-oracle-lookahead-tree-final.pdf - | rg -n "Bounded oracle-lookahead tree|oracle-lookahead recipe differs|missing reference|\?\?"`
- `pdftotext /tmp/aria-thesis-teacher-student-render-path-final.pdf - | rg -n "Teacher/student render path|render-path boundary|missing reference|\?\?"`
- `pdftotext /tmp/aria-thesis-directional-memory-final.pdf - | rg -n "directional-memory diagram|Actor-visible directional memory|missing reference|\?\?"`
- `pdftotext /tmp/aria-thesis-symmetry-contract.pdf - | rg -n "Minimum symmetry|Architecture Contract|Row permutation|Actor provenance gate|missing reference|\?\?"`
- `pdftotext /tmp/aria-thesis-learning-evidence-loop.pdf - | rg -n "Selected-transition replay contract|One-step evidence|Reportable comparison|missing reference|\?\?"`
- `pdftotext /tmp/aria-thesis-scientific-coherence.pdf - | rg -n "missing reference|\?\?|DINOv2|Descriptor and Encoding Protocol|Scene-Representation Requirements|Architecture Contract|Finite-Candidate Value Model"`
- `git diff --check`
- `make check-agent-memory`

## Remaining Diagram Backlog

The persistent diagram goal is still active. Current high-value remaining
work is to re-inspect the thesis for the next architecture, process, or
geometric-isomorphism figure target rather than carrying a known named backlog
item from this debrief.
