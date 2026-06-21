# ARIA-NBV Skill Prune/Merge Verdict

This reference captures the conservative first-pass verdict for the 2026-06-20
agent-scaffold cleanup. External reviews are advisory; live repo files,
checked-in backlog records, and `make scaffold-audit` are the gates.

## Policy

- Classify now; delete or merge later only after replacement-owner evidence.
- Treat `make scaffold-audit` semantic-drift warnings as review prompts before
  deleting text: move durable truth to canonical owners, but keep compact
  routing cues when they prevent wrong-owner activation.
- Keep `agent-behavior` active until lane selection, dirty-worktree
  preservation, request traceability, and verification have another explicit
  owner.
- Keep `aria-nbv-context` and `aria-litkg-memory` separate until routing
  fixtures prove a merge preserves deterministic local fallback and KG
  claim-check escalation.
- Treat `python-docstrings` as the only clear later-removal candidate, and only
  after its API-contract rules move to package/review/docs owners.

## Disposition

| Skill | Verdict | First gate |
| --- | --- | --- |
| `agent-behavior` | Keep; schema-normalize and later slim. | Replacement owner for universal invariants. |
| `agents-db` | Keep. | Metadata normalization only. |
| `aria-nbv-context` | Keep. | Prove local lookup remains deterministic before any router merge. |
| `aria-litkg-memory` | Keep. | Keep KG non-default except source-backed routing, claim checks, consolidation, or research memory. |
| `aria-nbv-mermaid` | Keep. | Metadata normalization only. |
| `code-review-aria-nbv` | Keep; canonical directory/name. | Remove unresolved plugin-style handoff labels from metadata. |
| `counterfactual-rollout-planner` | Keep. | Metadata normalization only. |
| `dataset-cache-ops` | Keep. | Metadata normalization only. |
| `diagnose-aria` | Keep; prune later. | Replace `omx:*` handoff labels with capability wording. |
| `docs-curator` | Keep. | Metadata normalization only. |
| `entity-aware-rri` | Keep. | Metadata normalization only. |
| `lrz-ai-systems` | Keep. | Metadata normalization only. |
| `nbv-geometry-contracts` | Keep. | Metadata normalization only. |
| `plan-grill` | Keep. | Metadata normalization only. |
| `python-docstrings` | Later removal candidate. | Migrate contract rules and pass routing fixtures before deletion. |
| `rerun-nbv-inspector` | Keep. | Metadata normalization only. |
| `semantic-scholar-litkg` | Keep separate from query/routing. | Rename only if audit proves scope confusion. |
| `simplification` | Keep; later shorten references. | Preserve behavior and one-owner policy. |
| `typst-authoring` | Keep; later slim hot path. | Move long doctrine to references, not deletion. |

## Verification

- `make scaffold-audit`
- `make agents-db AGENTS_ARGS='validate'`
- `make check-agent-memory`

Before any router merge, compare before/after routing fixtures. The merge is
acceptable only when owner selection is identical or explicitly improved and the
deterministic local lookup, KG claim-check escalation, and domain contract
owners remain represented.
