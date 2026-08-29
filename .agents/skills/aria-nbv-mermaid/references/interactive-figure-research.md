# Interactive Figure Research Packet

Use this packet for a skill-first OMX autoresearch loop. The unit of work is one
figure or one tightly coupled figure family, never the whole thesis diff.

The `$autoresearch` workflow owns `validation_mode`, the canonical
`.omx/state/.../autoresearch-state.json`, and the mission, sandbox, report, and
result schemas under `.omx/specs/autoresearch-{slug}/`. This reference defines
only the figure candidate packet and its domain gates; it does not create a
second state or completion protocol. The thesis-wide mission requested for this
workflow uses `.omx/specs/autoresearch-thesis-figures/{mission.md,sandbox.md,report.md,result.json}`.

## Required Candidate Packet

1. Exact source commit/digest and canonical source path.
2. Exact thesis passages, figure call site, caption, and intended reader insight.
3. Baseline standalone render and baseline thesis-page render at actual size.
4. Relevant Context7 query, primary-source fallback, and the specific guidance
   that changed the design.
5. Professor critique and student critique.
6. Decision: retain, simplify, revise, replace, merge, or remove.
7. One bounded accepted action, with assumptions and geometry/data provenance.
   Retain/no-change packets explicitly record that no source mutation occurred.
8. Candidate standalone render, final-page render, and grayscale render.
9. Typst/Mermaid build evidence and independent scientific-review findings.
10. Before/after interpretation and remaining limitations. If the task
    authorizes publication and source changed, also record commit, PR,
    exact-head CI/mergeability, and review-thread status.

Store temporary visual evidence outside tracked thesis paths unless a canonical
source or derived asset is intentionally changed. Generated files never outrank
their source or thesis passage.

## Prompt-Architect-Artifact Validator

The architect receives the exact packet, not a prose claim that the figure is
better. Approve only when all of these are evidenced:

- scientific and geometric correctness;
- one clear explanatory contribution;
- canonical notation and truthful epistemic status;
- unambiguous frames, labels, relationships, and reading order;
- legibility at final page size and in grayscale;
- caption complements rather than repeats the figure;
- no unsupported empirical or causal implication;
- clean deterministic source/render/PDF verification;
- zero unresolved P0--P2 scientific-review findings;
- one canonical source of truth and no unsafe orphaned replacement.

A no-change iteration is evidence, not completion. Completion requires architect
approval of the exact rendered candidate set and the mission's `result.json`
link to the final `report.md`.

## Interaction Loop

Render source and final pages on each iteration so an operator can compare them
visually while the source remains editable. Use Typst's watch mode or the local
Mermaid renderer only as a feedback accelerator; neither is the validator.

The sandbox permits edits only to the selected figure family, its caption and
adjacent interpretation when needed, derived renders, and the matching
review/report artifacts. Publish only accepted source changes, and only when the
task grants branch/PR authority. Retain/no-change classifications stay in the
research report; failed candidates stay in OMX artifacts, not thesis history.
