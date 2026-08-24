# Reviewed Intent

Load this branch only when accepted scoped requirements, exact owners, and
accepted sequencing leave a material policy choice unsettled.

## Decision Order

1. **Accepted scoped specification.** Use an accepted specification as the
   requirements owner only for work explicitly inside its scope.
2. **Exact owner.** Open the exact code, test, configuration, documentation, or
   workflow owner for current facts and implementation proof.
3. **Accepted plan.** Use an accepted plan to sequence work within the scoped
   requirements and exact-owner contracts; it overrides neither.
4. **Reviewed human intent.** Only if the choice remains unsettled, apply the
   reviewed general preferences in `.agents/references/human_owner_intent.md`.
   Its `Open Choices` are unresolved evidence, not accepted policy.

Debriefs, transcripts, retrieval output, inferred recurrences, and unaccepted
task artifacts are evidence rather than authority. If authoritative sources
still conflict, report the conflict, scope, and missing decision. Once the
choice is settled, persist it at the smallest exact owner and return to the
owner-first loop.
