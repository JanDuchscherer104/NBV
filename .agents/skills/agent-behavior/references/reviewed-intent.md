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

## Candidate Owner Intent

At a completed workpackage, capture a candidate only when a direct user
instruction or repeated task evidence establishes a precise, reusable
cross-task preference and names the owner it could improve. Put it in an
eligible native debrief under `## Candidate Owner Intent` with:

- **Statement:** the proposed preference, stated so a later task can apply it.
- **Evidence:** the direct instruction or bounded recurring evidence.
- **Scope and target owner:** where it applies and the exact owner path.
- **Status:** `proposed for current-user review`.

Omit this section for one-off instructions, task-local choices, or vague
preferences. A candidate remains episodic evidence: do not add it to
`.agents/references/human_owner_intent.md` automatically. Only a current-user
acceptance of the specific statement promotes it; update that owner and link
the resulting implementation commit from the debrief.
