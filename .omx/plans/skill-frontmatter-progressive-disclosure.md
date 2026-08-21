# Plan: native-minimal skill frontmatter and progressive disclosure

## Outcome

Migrate ARIA-NBV custom skills from repository-specific routing registries in
YAML frontmatter to Codex's native loading model:

1. the always-visible layer contains only `name` and a concise, model-facing
   `description`;
2. each selected `SKILL.md` contains only the invariants and branch selector
   needed for every invocation of that skill; and
3. exact source inventories, Context7 library IDs, tool calls, examples, and
   branch-specific procedures are loaded through direct, conditional links to
   `references/*.md`.

This is a behavior-preserving scaffold migration. It must improve context cost
and ownership without weakening owner localization, Graphify/Context7 routing,
dirty-worktree safety, or verification.

## Evidence and current-state diagnosis

- Codex skills progressively disclose three layers: the initial skill list
  contains names and descriptions, while the full `SKILL.md` is loaded only
  after selection. The installed skill-creation guidance likewise defines
  `name` and `description` as the frontmatter fields used for selection and
  reserves `references/` for material loaded as needed
  (`/home/jd/.codex/skills/.system/skill-creator/SKILL.md:56-80`,
  `:103-112`, `:135-145`; [official Codex skills documentation](https://developers.openai.com/codex/skills/)).
- `writing-for-agents` treats a model-invoked description as an always-loaded
  pointer and recommends one distinct trigger branch per pointer, conditional
  disclosure of branch detail, and one owner per meaning
  (`/home/jd/.agents/skills/writing-for-agents/SKILL-MECHANICS.md:5-18`;
  `/home/jd/.agents/skills/writing-for-agents/SKILL.md:76-81`).
- ARIA's current style guide instead requires a large nested `metadata` map
  containing mode, negative routing, handoffs, evidence, path globs, triggers,
  source inventories, Context7 IDs, literature routes, tool names, and
  verification (`.agents/skills/README.md:6-66`).
- The validator makes that duplication mandatory: it defines nine required and
  three optional metadata fields, rejects custom skills without the map, and
  validates every registry entry (`scripts/scaffold_audit.py:22-39`,
  `:321-356`, `:390-559`). Routing fixtures are coupled to this schema because
  their expected tool references are derived from owner-skill metadata
  (`scripts/scaffold_audit.py:701-725`).
- The cost is material. Excluding the byte-identical upstream Graphify skill,
  the 11 custom skills spend 29-69 lines on frontmatter. Examples include
  `agent-behavior` 29/94 lines, `aria-nbv-context` 58/146,
  `python-standards` 58/140, and `typst-authoring` 69/150.
- `aria-nbv-context` demonstrates the duplication directly. Its frontmatter
  repeats the scientific-source hierarchy, eight Context7 IDs, four exact tool
  calls, and verification commands (`.agents/skills/aria-nbv-context/SKILL.md:1-58`),
  while its body already owns the hierarchy, conflict/capture rules, and
  conditional Graphify, semantic-memory, context-map, and Context7 branches
  (`.agents/skills/aria-nbv-context/SKILL.md:60-146`).
- The accepted scaffold target already says that `aria-nbv-context` owns the
  hierarchy and Context7 route, exact IDs remain progressively disclosed in
  `references/context7_library_ids.md`, durable guidance should avoid freezing
  transient transports, and no metadata registry may duplicate scientific or
  implementation truth
  (`.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md:176-196`,
  `:498-505`, `:1038-1045`).

## Decisions

### 1. Use native-minimal frontmatter

Every ARIA-owned `SKILL.md` frontmatter will contain exactly:

```yaml
---
name: <directory-name>
description: <model-facing activation pointer>
---
```

The descriptions remain model-invoked: do not set
`disable-model-invocation: true`, because the repository expects autonomous
skill routing and inter-skill handoff. Each description should identify the
smallest set of distinct positive trigger branches, avoid implementation
detail, and remain one sentence. Use a review budget of 45 words rather than a
hard semantic substitute for routing tests.

The separately pinned `.agents/skills/graphify/SKILL.md` remains byte-identical
to upstream and outside this migration.

### 2. Move each former metadata field to its real owner

| Former field | Target owner |
|---|---|
| `mode` | Delete. It is a local taxonomy, not Codex selection data. |
| `triggers` | Compress distinct activation branches into `description`. |
| `not_when` | Prefer a positive boundary adjacent to the relevant branch in the body; retain a negative guardrail only for a dangerous or repeatedly confused route. |
| `handoff_to` | Put the handoff at the branch endpoint or in a concise `## Handoff` section. |
| `evidence_required` | Co-locate evidence with the workflow step that consumes it. |
| `applies_to` | Delete. Directory layout, nearest `AGENTS.md`, and routing fixtures already own applicability. |
| `must_read` | Replace global lists with `Read <reference> when <branch>` pointers. |
| `canonical_sources` | Delete the inventory. Link the exact owner from the branch that needs it; source files remain authoritative. |
| `context7_refs` | Keep exact IDs only in `aria-nbv-context/references/context7_library_ids.md`; other skills route to that branch. |
| `literature_refs` | Keep cross-surface labels in `aria-nbv-context/references/context_map.md` and exact claims in bibliography/review/primary-source owners. |
| `tool_refs` | Put exact calls in the smallest branch-specific procedure/reference, once. Do not use frontmatter as a tool registry. |
| `verification` | Co-locate completion checks in the body branch or owning executable test/configuration. |

### 3. Keep shared invariants in `SKILL.md`; disclose branch data from references

An invariant stays in the body only when every invocation needs it. A detail
moves to a reference when it is branch-specific, version-sensitive, a lookup
table, an example set, or a long command procedure. Every reference must be
linked directly from the body or a clearly named branch index with a concise
condition explaining when to read it. Do not duplicate the same meaning in the
body and a reference.

## Acceptance criteria

1. All 11 ARIA-owned skills have only `name` and `description` in frontmatter;
   custom frontmatter contains no nested `metadata`, source arrays, library IDs,
   or tool identifiers.
2. Every custom skill remains model-invoked, has a non-empty one-sentence
   activation description, and preserves its current fixture-covered routing
   outcomes.
3. `.agents/skills/graphify/SKILL.md` and its pinned integrity contract are
   byte-identical to the pre-migration upstream copy.
4. `aria-nbv-context` keeps the owner hierarchy, conflict rule, capture rule,
   and high-level branch selector in its body. Exact Context7 IDs and focused
   query seeds have one owner:
   `aria-nbv-context/references/context7_library_ids.md`.
5. A local owner lookup does not load Context7 detail; an external API/version
   question does. A narrow implementation question does not load the full
   scientific-source map.
6. Graphify freshness/provenance and fallback detail remains behind
   `references/graphify-aria-boundary.md`; semantic-memory policy remains behind
   `references/semantic-memory-boundary.md`; non-obvious cross-surface and
   literature routing remains behind `references/context_map.md`.
7. No Context7 ID, deprecated Docker-MCP call, scientific claim, package
   contract, or canonical-source inventory is duplicated across custom skill
   frontmatters or bodies.
8. `scaffold_audit.py` validates native-minimal frontmatter, reference
   integrity, upstream exemptions, hot-path budgets, and deterministic routing
   outcomes without reading a custom `metadata` map.
9. Routing fixtures validate tool use against the explicit owner/reference path
   that contains the procedure, rather than against hidden owner-skill
   metadata. The Context7 fixtures include the Context7 registry reference as
   an expected path; non-Context7 fixtures continue to forbid Context7.
10. Focused governance tests, scaffold audit/self-test, agent-memory checks, and
    full repository CI pass from a clean implementation worktree.

## Patch sequence

### Phase 1 — freeze behavior before changing the schema

1. Extend `scripts/tests/test_agent_governance_g002.py` with failing assertions
   for:
   - exact custom frontmatter keys `{name, description}`;
   - the upstream Graphify exemption and byte identity;
   - direct existence of every conditionally linked skill reference;
   - unique ownership of exact Context7 IDs and plugin call identifiers;
   - absence of Docker-MCP Context7 calls outside explicit negative migration
     fixtures/history;
   - the existing Graphify, Context7, semantic-memory, scientific-language,
     package, Rerun, LRZ, Typst, and failure-first routing outcomes.
2. Adjust `scripts/scaffold/fixtures/routing.json` so branch-specific procedure
   references are explicit expected owners. In particular:
   - Context7 API fixtures point to
     `aria-nbv-context/references/context7_library_ids.md`;
   - Rerun's local workflow and query recipe remain owned by
     `rerun-nbv-inspector`, while the current plugin/ID route is shared through
     `aria-nbv-context`;
   - code-index routing points to the one body/reference location that actually
     names the local discovery calls;
   - fixtures without external API uncertainty retain forbidden Context7
     outcomes/tool refs.
3. Preserve the existing small smoke-set philosophy: owner discovery,
   progressive disclosure, diagnostic routing, and exact-source fallback are
   tested as outcomes, not by snapshotting prose. This follows the accepted
   pre-consolidation gate
   (`.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md:725-745`).

### Phase 2 — replace the frontmatter validator

4. Refactor `scripts/scaffold_audit.py`:
   - remove `ALLOWED_MODES`, `REQUIRED_METADATA`, `OPTIONAL_METADATA`,
     `METADATA_KEYS`, metadata parsing, and metadata-derived route checks;
   - reject unexpected top-level frontmatter keys for ARIA-owned skills;
   - validate directory/name parity, non-empty descriptions, one-sentence
     descriptions, and a soft 45-word description budget;
   - retain the upstream-skill exemption and hot-path line warning;
   - validate conditional Markdown reference links and missing reference files;
   - validate exact Context7 IDs against their single registry owner rather
     than requiring copies in every consumer;
   - validate fixture tool refs against the text of their explicit expected
     owner/reference paths, with forbidden refs checked independently;
   - rewrite self-test probes to cover the new invariants and delete probes that
     exist only to test the retired metadata schema.
5. Update the Makefile target description from “skill metadata” to “skill
   frontmatter, references, handoffs, and routing fixtures.” Keep the existing
   CI impact and workflow gates intact (`Makefile:236-243`;
   `.github/workflows/ci.yml:23-24`, `:140`).

### Phase 3 — migrate custom skills without broad rewrites

6. Rewrite `.agents/skills/README.md` as the canonical style guide for:
   native-minimal frontmatter, model-facing descriptions, body invariants,
   conditional reference pointers, single-owner rules, upstream exemptions,
   and verification. Remove the repository-specific metadata schema and its OMX
   sidecar taxonomy.
7. Migrate each ARIA-owned skill. Preserve behavior and reuse existing
   references before adding files:

| Skill | Planned body/reference treatment |
|---|---|
| `agent-behavior` | Remove metadata; keep the owner-first loop and universal safety invariants. Route durable capture, external actions, and Git safety to existing references. |
| `agents-db` | Remove duplicated must-read/command/verification lists; keep the database lane selector and point to its existing references/CLI owner. |
| `aria-grill` | Keep the high-impact decision gate and branch selector; route external evidence through `aria-nbv-context` and keep theory/interface detail in existing references. |
| `aria-nbv-context` | Apply the detailed decomposition in Phase 4 below. |
| `aria-nbv-mermaid` | Keep local lint/render and thesis-diagram workflow; disclose external Mermaid API/version evidence only when uncertainty activates the Context7 branch. |
| `lrz-ai-systems` | Keep the decision selector; use the existing decision map as the first conditional index to branch-specific LRZ references. |
| `measured-autoresearch` | Remove metadata and split branch-specific artifact/evaluator procedure into direct references if needed to return below the 150-line hot-path budget. |
| `python-standards` | Keep the concise contract loop and conditionally index existing typing, docstring, DTO, shape, and lifecycle references; do not duplicate Context7 IDs/tools. |
| `rerun-nbv-inspector` | Keep ARIA workflow and verification; use existing Context7 query/official-example references and route current plugin/ID selection through `aria-nbv-context`. |
| `simplification` | Keep behavior-preservation and deletion criteria; leave exact tool choice in the existing tool-decision reference. |
| `typst-authoring` | Remove the 69-line frontmatter inventory; keep common Typst/thesis invariants and disclose figures, citations, packages, style, and upstream-writing guidance through the existing indexed references. |

8. Validate existing `agents/openai.yaml` sidecars against the revised skill
   descriptions and regenerate only stale sidecars. Do not require or add a
   sidecar to every skill as part of this migration.

### Phase 4 — make `aria-nbv-context` the exemplar

9. Recompose `.agents/skills/aria-nbv-context/SKILL.md` in this order:
   - minimal frontmatter;
   - one outcome sentence: select the smallest hierarchy leaf, open the exact
     owner, then hand off;
   - concise owner hierarchy, conflict rule, and capture rule, because all
     context-localization branches need them;
   - a branch index with direct conditions:
     - broad architecture/relationship question -> read
       `references/graphify-aria-boundary.md`, classify freshness, then invoke
       upstream Graphify and verify exact owners;
     - external API/version uncertainty -> read
       `references/context7_library_ids.md`, select/resolve one library, and
       issue one focused query per concept;
     - prior decision/failed-approach recall -> read
       `references/semantic-memory-boundary.md`;
     - non-obvious cross-surface/literature owner -> read
       `references/context_map.md`;
     - already-known exact owner -> hand off immediately without loading any
       optional branch reference.
10. Keep exact plugin calls and library IDs in the Context7 reference. Keep
    Graphify pin/freshness/provenance commands in the Graphify boundary. Keep
    literature route labels in the context map. If local code-index call names
    do not fit an existing reference without mixing concerns, add one concise
    `references/local-discovery-tools.md`; otherwise keep them next to the local
    discovery step in the body. Do not create another canonical-source registry.

### Phase 5 — record the accepted target without rewriting history

11. Append a dated amendment to
    `.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md` stating
    that ARIA custom skills now use native-minimal frontmatter and that routing
    registries moved to compositional bodies/references and outcome fixtures.
    Preserve older accepted sections as historical rationale.
12. Add the required implementation debrief under
    `.agents/memory/history/YYYY/MM/`, recording the ownership decision, measured
    frontmatter reduction, test evidence, and any intentionally deferred body
    cleanup.

## Verification plan

Run in this order and capture fresh output:

1. Red phase: focused governance tests fail on the old metadata schema.
2. Per-skill validation: run the installed `quick_validate.py` against every
   ARIA-owned skill and verify the upstream Graphify checksum/integrity test.
3. `python3 scripts/scaffold_audit.py`
4. `python3 scripts/scaffold_audit.py --self-test`
5. `uv run pytest -q scripts/tests/test_agent_governance_g002.py`
6. Focused Graphify upstream/freshness tests and Context7 routing fixture tests.
7. `make check-agent-memory`
8. `make scaffold-check` from an initialized worktree; if strict Graphify state
   is unavailable, report that environmental gap separately and still run all
   non-generated scaffold gates.
9. The repository's full CI-equivalent test/lint/type/build commands selected by
   the changed-file impact tooling.

Then run fresh-agent routing trials with raw task prompts and no leaked expected
answer:

- unknown code owner with usable Graphify;
- unknown code owner with unusable Graphify and exact-source fallback;
- known local owner with no Context7 load;
- current external SDK behavior requiring Context7;
- thesis symbol/equation/glossary ownership;
- Rerun SDK change; and
- LRZ job failure.

For each trial, record selected skill, references actually opened, exact owner
reached, irrelevant branch references avoided, and verification performed.

## Risks and mitigations

- **Routing recall drops when trigger lists disappear.** Make descriptions
  model-facing and test realistic prompt families before deleting metadata.
- **Tool-ref validation becomes a brittle text search.** Require the fixture to
  name the exact procedure/reference owner and parse only explicit backticked
  tool identifiers from those paths; do not scan the repository globally.
- **A body becomes the next monolith.** Retain the 150-line hot-path warning,
  add conditional reference-link checks, and split only branch-specific detail.
- **Single ownership becomes an indirection maze.** Keep one-hop conditional
  pointers from `SKILL.md` wherever practical and use an index only when a
  branch genuinely has multiple subtopics.
- **Upstream Graphify is accidentally normalized.** Preserve the explicit
  upstream exemption and byte-integrity test before bulk editing.
- **Historical spec contradictions resurface.** Add one dated supersession note
  and leave historical sections untouched; current executable tests and style
  guide define the live contract.

## Out of scope

- Changing package behavior, scientific claims, Typst content, or external API
  usage.
- Rebuilding Graphify or committing generated Graphify artifacts.
- Renaming, merging, or deleting custom skills solely to reduce the skill count.
- Adding a new metadata registry outside frontmatter.
- Rewriting every reference file; only duplication or missing branch indexing
  discovered during this migration is in scope.

## Stop condition

The patch is ready when the native-minimal frontmatter invariant is executable,
all current routing outcomes are preserved, branch-specific data has a single
discoverable owner, fresh validation is green (or an external Graphify-state gap
is isolated explicitly), and no custom skill body has become a replacement
registry.
