# Human Owner Intent

This file owns durable human preferences for the ARIA-NBV agent scaffold. It
does not own current implementation truth, scientific claims, project status,
or repeatable workflows.

## Core Principles

- **Context hygiene:** Keep default context small. Load detailed guidance,
  history, and generated context only when the task needs them, and stop
  retrieval once the work is grounded.
- **Single source of truth:** Give every durable meaning one authoritative
  owner. Derived indexes, graphs, reports, plans, debriefs, and agent output may
  link to that owner but must not compete with it.
- **Progressive disclosure:** Keep root guidance thin. Put local contracts and
  verification beside the package, document, or workflow that owns them.
- **Upstream first:** Prefer maintained upstream behavior and native tool
  interfaces. Add repository-owned adapters only for a demonstrated local gap,
  and keep their code and policy surface minimal.
- **Evidence before assertion:** Exact source and fresh verification establish
  current truth. Retrieval, inferred links, similarity, plans, and agent
  confidence are discovery aids only.
- **Reviewability:** Prefer small, owner-scoped, reversible changes and pull
  requests. Do not combine scaffold migration, domain changes, generated
  artifacts, and unrelated cleanup into one review unit.

## Ownership

- Code, tests, and active configuration own executable behavior and contracts.
- The active Typst thesis owns scientific narrative, notation, and research
  direction. Exact papers own external claims. Skills must not duplicate domain
  knowledge from either source.
- Root and nearest `AGENTS.md` files own repository and local invariants.
- Skills own repeatable workflows, activation, handoffs, and verification. A
  skill should be a compact front door whose detail is loaded on demand.
- This file owns reviewed human scaffold preferences.
- Agents DB TOMLs own actionable issues, TODOs, and refactors.
- Debriefs, conversations, and OMX artifacts are evidence and history, not
  automatic current truth. Promotion into an owner requires human review.
- Generated navigation and retrieval artifacts remain reproducible,
  non-authoritative, and outside normal startup context.

## Scaffold Preferences

- Keep `.agents/` as the canonical repository scaffold and keep the root
  dispatcher concise.
- Keep OMX, Graphify, MemPalace, and similar tools optional. Normal repository
  work and CI must still work from exact source without them.
- Graphify should preserve native source hierarchy and provenance, use upstream
  behavior wherever possible, and remain a navigation accelerator rather than
  a knowledge owner.
- Keep raw transcripts, runtime identifiers, machine paths, credentials, and
  private retrieval corpora untracked. Publish only reviewed distillations.
- Preserve `measured-autoresearch` as a bounded, measurement-gated companion to
  generic research loops. It must support research-only, evaluator-design,
  measured implementation, and keep-or-discard iterations.
- Keep `agents-db` as the actionable-work owner for now. Keep debriefs concise
  and episodic rather than loading them as default project state.
- Prefer a small set of independently useful ARIA skills. Consolidation must
  preserve meaningful triggers, exclusions, helpers, tests, and verification;
  an arbitrary skill-count target is not a goal.
- Keep thesis notation, equations, bibliography, draft markers, build profiles,
  and source links in shared Typst ownership. Cross-modal links should resolve
  to real code symbols, thesis sections, or exact literature sources.
- Prefer package READMEs only where they provide useful subsystem orientation;
  do not generate symbol matrices or duplicate routing policy in them.
- Keep retained public documentation renderable and clearly separate current
  thesis direction from historical implementation evidence.
- Manage versioned checkpoints and model artifacts through Git LFS.
- Do not restore legacy cache-migration or runtime-training APIs solely for
  compatibility.

## Non-Goals

- Do not build repository-owned replacements for Graphify, OMX, MemPalace, or a
  literature engine when maintained functionality already exists.
- Do not treat a graph, wiki, transcript corpus, generated report, debrief, or
  agent memory as an authoritative representation of project truth.
- Do not create a comprehensive scaffold handbook or mirror scientific/domain
  information in skills.
- Do not infer acceptance, truth, conflict resolution, or supersession from
  similarity scores or agent consensus.
- Do not migrate the entire scaffold in one pull request.

## Open Choices

These are intentionally unresolved and must not be presented as accepted
policy:

- Graphify's exact corpus, refresh model, and retained generated artifacts.
- Whether LitKG remains useful after exact-source and literature workflows are
  verified without it.
- Whether `aria-nbv-context` remains a thin router or owns a small amount of
  stable project orientation.
- Which handwritten project-state surfaces can be retired after their facts
  have verified owners.
- Which external skills should be referenced, allowlisted, or vendored.

## Instruction Capture

- Repository invariant or safety rule: root or nearest nested `AGENTS.md`.
- Repeatable workflow: the narrow owning `.agents/skills/*/SKILL.md`.
- Human scaffold preference: this file.
- Current technical or scientific truth: exact owning code, configuration,
  test, thesis source, evidence bundle, or paper.
- Actionable work: `.agents/issues.toml`, `.agents/todos.toml`, or
  `.agents/refactors.toml`.
- Generated routing or context: ignored, reproducible output with provenance.

Use the smallest authoritative surface that preserves the information without
creating a second source of truth.
