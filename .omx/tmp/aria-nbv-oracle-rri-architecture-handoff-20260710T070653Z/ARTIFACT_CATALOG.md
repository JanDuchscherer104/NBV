# Artifact Catalog

All files under `artifacts/` are byte-preserving copies made on
2026-07-10T07:06:53Z. They are evidence, not a replacement for the live source.

## Decision Status

| Status | Sources | How to use them |
|---|---|---|
| Latest critique | `autoresearch-aria-nbv-module-pruning-revision-20260710` | Start here. It identifies concrete unresolved defects in the latest draft. |
| Primary evidence | `autoresearch-aria-nbv-module-pruning-20260709`, `autoresearch-aria-nbv-oracle-boundaries-20260709` | Verify their current-source claims before carrying them forward. |
| Current draft, not approved | `autopilot-aria-nbv-oracle-metrics-refactor-20260709T165010Z.md` | Use as a concise candidate implementation sequence. It is explicitly draft-pending review. |
| Superseded/corrected | `plan-aria-nbv-oracle-module-refactor-20260709T123231Z.md` | Retain only for decision history; its `oracle/rewards.py` formula owner is rejected. |
| Earlier alternatives | `ralplan-rri-metrics-*`, `ralplan-rri-rollouts-oracle-pipelines-*` | Mine for evidence and rejected alternatives. Resolve their contradiction instead of combining them. |
| Prior context | `aria-nbv-package-boundary-cleanup-*`, July 2/8/9 debriefs | Constrains scope and records post-PR15/pre-PR15 history. |
| Runtime metadata | `artifacts/.omx/state/**` | Validator provenance only. Do not treat as design authority. |

## Included Evidence Groups

- Package-boundary context and the July 2 architecture-plan/critic/handoff.
- RRI-metrics RALPLAN, architect review, critic review/final, and JSON handoff.
- RRI/rollouts/oracle/pipelines RALPLAN, architect/critic reviews, and JSON
  handoff.
- Oracle module, autopilot, and RL-archive plans.
- The 2026-07-08 refactor evidence report and architecture map.
- The 2026-07-09 oracle-boundary and module-pruning autoresearch packages.
- The 2026-07-10 module-pruning revision package.
- Relevant July 2, July 8, July 9, and July 10 debriefs.
- Guidance snapshots and the user-provided previous-pass artifact listing.

## Deliberately Excluded

- Runtime source code and tests: the reviewer has repository access and must
  inspect the fresh post-PR15 checkout.
- Unrelated docs/API-generation, literature, thesis, and visual-pattern work.
- OMX session state that does not establish planning provenance.
- All dirty source-checkout changes. The handoff records their existence but
  does not freeze or endorse them.
