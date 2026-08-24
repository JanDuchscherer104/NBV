# Human Owner Intent

This file owns durable human preferences for the ARIA-NBV agent scaffold. It
does not own current implementation truth, scientific claims, project status,
or repeatable workflows.

## Core Principles

- **Predictable process:** Prefer a stable sequence of finding evidence,
  locating its owner, executing the bounded change, and verifying the result.
  Consistency does not require identical prose or implementation.
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
- **Qualified provenance:** Derived evidence records its source, freshness and
  worktree, ambiguity, and whether links were extracted or inferred. Stale or
  mismatched artifacts cannot establish current truth.
- **Reviewability:** Prefer small, owner-scoped, reversible changes and pull
  requests. Do not combine scaffold migration, domain changes, generated
  artifacts, and unrelated cleanup into one review unit.
- **Conceptual collaboration:** For meaningful Spatial-AI, ML, MLOps,
  data-science, or statistics work, prefer an explanation of the governing
  model, assumptions, and failure mode. Use diagrams when they clarify a real
  relationship; reserve durable teaching artifacts for deliberate learning.

## Ownership

- Code, tests, and active configuration own executable behavior and contracts.
- The target state is for the active Typst thesis to own scientific narrative,
  notation, and research direction. Until that migration is reviewed,
  the `aria-nbv-context` owner hierarchy resolves current authority. Exact papers
  own external claims, which retain page, section, equation, or source-file
  locators. Skills must not duplicate domain knowledge from either source.
- Immutable manifests and evidence bundles own measurements. Reports and thesis
  prose interpret them without becoming competing measurement stores.
- Root and nearest `AGENTS.md` files own repository and local invariants.
- Skills own repeatable workflows, activation, handoffs, and verification. A
  skill should be a compact front door whose detail is loaded on demand.
- This file owns reviewed human scaffold preferences.
- The accepted scaffold-rework requirements live in
  `.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md`; this
  file retains only general preferences that apply beyond that scoped rework.
- Agents DB TOMLs own actionable issues, TODOs, and refactors.
- Debriefs, conversations, and OMX artifacts are evidence and history, not
  automatic current truth. Promotion into an owner requires human review.
- Newer intent supersedes older intent only within reviewed scope. Older intent
  is weaker evidence for current choices but remains useful for detecting lost
  capabilities; unresolved conflicts remain explicit.
- Generated navigation and retrieval artifacts remain reproducible,
  non-authoritative, and outside normal startup context.

## Scaffold Preferences

- Keep `.agents/` as the canonical repository scaffold and keep the root
  dispatcher concise.
- Require the Graphify executable and usable graph artifacts as navigation
  prerequisites in every Codex worktree. Eligible codebase questions query a
  usable graph first and still verify exact sources; a broken bootstrap or
  unusable artifact permits an explicit direct-source-only degraded route.
  OMX, MemPalace, and similar tools remain optional. Graphify's two
  content-addressed semantic cache namespaces are shared worktree prerequisites;
  mutable graph state stays local.
- Use the official upstream Codex plugin for MemPalace and keep its reviewed
  corpus in user-local wings for the current thesis, curated literature reviews,
  primary-paper PDFs, remaining project documentation, native debriefs, and an
  explicitly opt-in ARIA Codex history. The repository owns neither a wrapper
  nor a tracked runtime corpus.
- Preserve composition through source files and canonical rooms: thesis rooms
  follow the Typst chapter/include structure; literature-review and paper rooms
  follow the domain hierarchy in `docs/contents/literature/index.qmd`; debrief
  and Codex-history sources retain authored-date provenance. Retrieval chunks
  remain evidence, not independent claims or reconstructed document hierarchy.
- Mine all reviewed primary PDFs under `docs/literature/pdf` but not their
  duplicate TeX mirrors. Historical Codex backfill is limited to root ARIA-NBV
  tasks, excludes child-agent/tool/system/runtime content, and remains a
  separate opt-in wing rather than the default search corpus.
- Exclude code, tests, active configuration, archives, runtime state, datasets,
  generated artifacts, caches, credentials, and private unrelated sessions.
  Locate implementation behavior only from its defining repository source,
  tests, and configuration. MemPalace retrieval is evidence and never promotes
  content into repository truth automatically.
- Graphify should preserve native source hierarchy and provenance, use upstream
  behavior wherever possible, and remain a navigation accelerator rather than
  a knowledge owner.
- The accepted scaffold target-state specification records the human owner's
  Graphify option-3 selection: the upstream Graphify tool, its project-installed
  skill under `.agents/skills/graphify/`, and one thin deterministic Markdown
  evidence projection for source-owned thesis links, both bibliography owners,
  the literature manifest, and local TeX/PDF asset identities. The upstream
  skill stays byte-identical; root `AGENTS.md` gives the compact mandatory route
  and `aria-nbv-context` owns its detailed ARIA preflight. This file preserves
  the cross-task preference; the specification owns the scoped decision and its
  bounded corpus and capability limits. The projection is
  ignored, reproducible, and derived; it must not grow into a parser framework,
  graph schema, query layer, lifecycle manager, or alternative source of truth.
- The Graphify replacement branch carries the exact upstream skill and all other
  repository-side setup. After merge, the only external operator steps are
  normal Codex authentication and, if absent, installing the upstream Graphify
  package that supplies the `graphify` CLI.
  Semantic extraction may use authenticated Codex host subagents. Never export
  or reuse a ChatGPT/Codex token as `OPENAI_API_KEY` or another provider API
  key, add repository or CI secrets, introduce a Graphify fork or skill overlay,
  repository-owned package import, hook/freshness lifecycle, or patch generated
  graph output.
- The optional upstream Git hook is only a local incremental-code accelerator;
  document and image semantic refresh remains explicit. Mandatory routing comes from worktree setup
  plus the ARIA freshness preflight, not hook success. The hook remains neither
  freshness authority nor lifecycle owner; `aria-nbv-context` owns the detailed
  ARIA-NBV operational route while upstream Graphify owns its lifecycle.
- Keep raw/full transcripts, runtime identifiers, machine paths, credentials,
  and private retrieval corpora untracked. At most one deterministic,
  pattern-sanitized, commit-scoped conversation slice may be tracked for a
  Codex-authored commit only when a repository-owned provenance workflow
  enforces the corresponding sanitization and commit-binding contract. Any
  retained slice is provenance evidence, not a distillation or truth owner.
- Replace the standalone `measured-autoresearch` sidecar with the existing
  `$performance-goal` evaluator-gated lifecycle, using a small immutable-result
  bridge for optional W&B reporting and read-only inspection.
- Keep `agents-db` as the actionable-work owner for now. Keep debriefs concise
  and episodic rather than loading them as default project state. Debriefs
  retain reusable diagnoses, failed approaches, measurements, and handoffs.
- Give every actionable scaffold finding an explicit disposition: reject it,
  deduplicate it, preserve it as a protocol, or record it in Agents DB.
- Retire a handwritten state surface only after every claim has a verified
  owner and every consumer has migrated.
- Treat accepted plans and specifications as immutable evidence. Keep current
  artifacts in native `.omx/context`, `.omx/specs`, and `.omx/plans` paths;
  archive superseded bundles intact with successor provenance. Replace them
  through explicit supersession rather than in-place rewriting. Keep any
  registry and validator implementation minimal.
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

- Whether later evidence justifies changing the selected thin Graphify adapter
  or retaining additional generated outputs; the upstream-first option-3
  boundary remains accepted, with mandatory Codex-worktree routing superseding
  its former optional status.
- LitKG is retired; reintroduction requires a new evidence-backed decision.
- Which handwritten project-state surfaces can be retired after their facts
  have verified owners.
- Which external skills should be referenced, allowlisted, or vendored.

## Instruction Capture

The exact destination map is owned by
`.agents/skills/aria-nbv-context/SKILL.md#capture-rule`. The `agent-behavior` skill
owns the procedure for recognizing explicit current-user capture requests and
applying that map. This file retains only reviewed human preferences.
