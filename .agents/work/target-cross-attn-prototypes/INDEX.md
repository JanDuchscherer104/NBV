# Target-conditioned cross-attention prototype index

Status: preserved research prototypes; not production model implementations.

This branch was created directly from `origin/main` at
`fa45ea64ef2597b7aaccd24c8b55ac58c5da36bc`. It preserves narrowly selected,
previously uncommitted model ideas from the `rri-datasets` worktree without
including them in PR #25.

## Preserved components

| Component | Canonical path | Intended value | Status |
| --- | --- | --- | --- |
| Actor/oracle DTO firewall | `aria_nbv/aria_nbv/learning/bundle.py` | Prevent oracle labels entering the actor forward path | Prototype contract |
| Factorized cross-attention | `aria_nbv/aria_nbv/learning/factorized_rri.py` | Reuse one scene memory across independent target-candidate queries | Runnable prototype |
| Grouped rollout view | `aria_nbv/aria_nbv/learning/grouped_rollouts.py` | Exact state identity and `[target, candidate]` supervision tensors | Prototype data seam |
| Temporal field transformer | `aria_nbv/aria_nbv/vin/models/temporal_field_transformer.py` | Causal attention over historical field summaries | Runnable one-step prototype |
| Temporal field DTO | `aria_nbv/aria_nbv/vin/types/temporal_field.py` | Minimal model-facing historical-field contract | Prototype contract |

Each component remains under `aria_nbv/**` so ordinary Python tooling can inspect
and test it. Nothing in this branch adds Mojo, MPS, Apple-Silicon, rendering,
field-generation, persistence, or PyTorch3D backend behavior.

## Deliberate non-integration

- The prototypes are not registered in production configuration or Lightning
  training entry points.
- `aria_nbv.vin.models` does not re-export the temporal prototype.
- The finite-horizon `MultiStepCandidateScorer` remains an explicit scaffold.
- No code here implements `Q_H`, bootstrap targets, target networks, variable
  horizon conditioning, or candidate-set transitions.
- The temporal prototype predicts ordinal one-step RRI. Its causal attention
  trunk is the reusable part; its head and objective are not the final method.
- Obsolete inter-snippet `EfmFieldTileStream` accumulation was intentionally not
  preserved.

## Suggested extraction order

1. Actor/oracle bundle and invariant tests.
2. Factorized target-candidate queries over shared scene memory.
3. Exact grouped-rollout state and mask contracts.
4. Causal temporal-field tokenization and attention.
5. A separately specified horizon-conditioned return head and objective.

Do not merge this branch wholesale. Cherry-pick or rewrite individual commits
after their contracts have been reconciled with the production dataset and
training interfaces.
