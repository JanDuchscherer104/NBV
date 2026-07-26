# ARIA-NBV Scaffold Five-PR Rebuild

## Prometheus Strict Status

- Planning baseline: `b8166fc8ab60c41d0f8a6eecfef8e4a2bf3b161c`
- Evidence branch: `5bc48d461eb6679a28d45fc0f2bf7fc6a1222121`
- Existing PR to supersede: [PR #28](https://github.com/JanDuchscherer104/ARIA-NBV/pull/28), head `6339bb74d8e382937d728318cc18ad07a9063eef`
- Autoresearch report:
  `.omx/specs/autoresearch-agent-scaffold-issue-index-20260726/report.md`
- Report SHA-256 at planning time:
  `8cf4ded5b1da43369674ba0a6ed53bbb4dcb911ea17c2da020b61e1e11032936`
- Report review: Architect `APPROVED`; Critic `APPROVED`
- Prometheus Momus re-review: `APPROVED`
- Post-plan Metis gap check: `CLEAR`
- Execution handoff: sequential `$ultragoal`; no parallel write team

This is a planning artifact. It does not close PR #28, push branches, open pull
requests, or modify the dirty source worktree.

## Target Result

Close PR #28 and replace the 130-commit scaffold mega-branch with five small,
sequential, independently reviewed pull requests reconstructed from
`b8166fc8`. Retain only behavior justified by current owners, measured agent
usefulness, or upstream gaps. Prune custom wrappers, duplicated truth, generated
navigation, and unproven thesis changes.

Every retained source-branch change must map to one target PR. Every omitted
change must be classified as pruned, replaced by upstream, transient/reverted,
or deferred with an owner and reason.

## Non-Goals

- Do not replay, merge, or preserve the 130-commit history as implementation
  ancestry.
- Do not rewrite or reuse PR #28.
- Do not work from the dirty scaffold-distill worktree.
- Do not track raw Codex transcripts, user-message extracts, absolute paths,
  session runtime identifiers, MemPalace palace data, Graphify output, caches,
  credentials, or generated wiki/report HTML.
- Do not make MemPalace, Graphify, OMX, debriefs, transcripts, or agent output a
  current-truth owner.
- Do not infer contradiction, truth, acceptance, or supersession automatically
  from lexical or semantic similarity.
- Do not add RDF, Jena, a custom ontology runtime, another vector store, or
  another issue database.
- Do not restore LitKG, broad generated `make context` snapshots, the 21-skill
  domain catalog, or `.agents/memory/state` as a current-truth layer.
- Do not include thesis/notation changes unless a retained import, source-owner,
  glossary, compile, or render gate proves they are necessary.
- Do not require each PR to reduce LOC. The cumulative final custom production
  LOC must be below the baseline; tests and external/generated code are reported
  separately.

## Authority Model

| Information class | Authoritative owner | Supporting surfaces |
| --- | --- | --- |
| Executable behavior | Code, typed APIs, tests, nearest package guidance | Graphify, debriefs, PRs |
| Scientific narrative and interpretation | Active Typst thesis | Exact papers and evidence bundles |
| Measurements | Immutable manifests/evidence bundles | Thesis interpretation, reports |
| Literature claims | Exact external paper | Bib entries, local TeX mirror, notes |
| Current human preferences | `.agents/references/human_owner_intent.md` | Reviewed transcript evidence |
| Actionable work | Agents DB TOMLs | Debriefs and PR TODO summaries |
| Accepted planning/research evidence | Registered immutable OMX bundle | PR body and debrief |
| Historical execution context | Raw local sessions and reviewed debrief/transcript evidence | MemPalace retrieval |
| Navigation | Graphify and MemPalace | Exact-source confirmation |

Provenance is not truth. A recent user statement may supersede an older user
preference only after a reviewed conflict record identifies both statements,
their scope, and the exact active owner update. Code or test facts are not
superseded by conversational preference alone.

## Before, Current, Target Responsibilities

`Before` means the common base `b8166fc8`. `Current` means the unmerged evidence
branch `5bc48d46`, not repository main. `Target` means the state after PR5.

| Responsibility | Before | Current evidence branch | Target |
| --- | --- | --- | --- |
| Root routing | Root `AGENTS.md` plus 21 ARIA domain skills | Root dispatcher plus 10 compact ARIA skills, but diagnostic routing is unnamed | Compact root dispatcher; explicit diagnostic route; runtime-evaluated activation |
| Skill truth | Domain primers and large skill trees duplicate contracts | Domain truth mostly moved to packages/Typst; Graphify trigger remains broad | Skills own activation and workflow only; exact owners preserve truth |
| Scientific direction | QMD roadmap/questions plus state journals and Typst | Typst is sole narrative owner; QMD is navigation | Preserve Typst ownership and reject duplicate scientific owners |
| Source discovery | Generated context helpers, LitKG, Graphify, `rg` | Graphify plus direct-source fallback; narrow helpers removed | Direct-source scaffold routing; Graphify for code/thesis/literature; native tools first |
| Graph corpus | Broad `.graphifyignore`, including selected scaffold/state sources | Three `.graphify.toml` partitions; active Bib files and scaffold are omitted | Code/thesis/literature only; both Bib files included; scaffold deliberately bypasses graph |
| Graph implementation | Several custom freshness/query/report wrappers | 1,139-line adapter/bridge plus upstream native schema/traversal | Small adapter only for corpus materialization and unsupported Typst/TeX/Bib extraction |
| Memory/current state | Four `.agents/memory/state` journals compete with direct owners | Journals removed; debrief/transcript evidence separated | Claim-level migration ledger; exact owners current; evidence remains historical |
| Transcript use | Heuristic extractor and debrief archive | 1,006-line extractor plus repo-local MemPalace plugin; usefulness unmeasured | Upstream MemPalace retrieval plus a small unsupported audit/manual-promotion delta |
| Conflict and time | Timestamps and prose only | Candidate review statuses but no reviewed conflict/supersession contract | Reviewed provenance, owner, validity, conflict, supersession, and promotion records |
| OMX evidence | Inconsistent ignored/tracked planning artifacts | Strong immutable registry but 2,120-line purge-oriented validator | Minimal current/archive registry, hashes, redaction, transitions, and supersession |
| Matt skills | No pinned project policy | Pinned allowlist and closure validator; prose counts drifted | Optional operator-local pin; tested installed/absent states; no end-to-end catalog claim |
| Prompt budget | ARIA descriptions only | ARIA+selected Matt gate passes but full 67-skill catalog is unmeasured by it | Separate repo-controlled and full-runtime catalog measurements |
| Routing validation | Prose and static checks | Lexical overlap fixtures | Lexical lint plus positive/negative/held-out runtime activation and outcome evals |
| Hooks | Older asynchronous Graphify refresh | Copied synchronous full-sync hook | Observable installed digest; bounded local two-speed refresh; no network/tracked writes |
| Scaffold accounting | Broad source LOC | Net LOC lower, while custom executable/test machinery increased | Production/tests/generated/upstream categories reported separately; cumulative simplification |

## Temporal Decision Ledger

The implementation must preserve this change history rather than flattening it
into a false single consensus.

| Period/decision | Earlier position | Later resolution | Target disposition |
| --- | --- | --- | --- |
| Skill count | Broad domain-specific ARIA catalog | Consolidate to compact operational skills; retain measured autoresearch | Retain compact catalog; prove routing outcomes before further deletion |
| Domain information | Skills carried geometry, RRI, rollout, storage, and thesis scope | Domain truth belongs in code/tests/Typst/nearest package guidance | Skills link to owners; do not restore primers |
| Current state | Four state journals maintained current truth | Journals were stale and poorly maintained | Claim-level migration, then retirement |
| Debriefs | Considered event-trigger-only | User chose the current non-trivial-work debrief policy | Retain, but measure retrieval value and enforce concise owner links |
| Graph outputs | Proposed tracked graph/report/wiki and source/graph commit pairs | Generated graph/report/wiki should remain local; no wiki | Keep ignored and reproducible; exact source authoritative |
| Graph scope | Proposed code, scaffold, thesis, literature partitions | User rejected top-level scaffold/config/skill noise | No scaffold partition; direct-source scaffold routing |
| Graph refresh | Proposed automatic refresh | Later demanded minimal upstream behavior and no custom graph system | Native code refresh under timeout; semantic stale marker and explicit sync |
| Graph hierarchy | Flat nodes and custom god nodes | Native package, Typst include, and paper hierarchy preferred | Preserve native hierarchy; do not invent authority nodes |
| Context tooling | Broad `make context`, UML, indexes, LitKG | Keep narrow stdout inspection and native retrieval only | Restore a helper only after outcome comparison proves value |
| Literature authority | LitKG claim checking | Exact papers and direct-source checklist | MemPalace/Graphify route; exact sources prove claims |
| Transcript invariants | User messages contain high-value preferences | Not every message is true/current; temporal discount and conflict review required | Freeze all ARIA sessions locally; publish reviewed relations, never raw transcript truth |
| MemPalace | Repo-local MCP intended to search docs/chat | Upstream offers hierarchy, conversation mining, provenance, temporal KG; contradiction remains limited/experimental | Use retrieval and temporal provenance; no custom truth engine |
| Measured autoresearch | Compact rewrite lost research-only iteration guidance | User restored alternating research and measured implementation iterations | Retain current mixed-iteration contract |
| OMX retention | `.omx` was ignored and plans were lost | Accepted bundles must be immutable and superseded bundles retained | Minimal registry contract in PR1; discard purge overengineering unless proven necessary |
| README/wiki | Generated wiki and symbol matrices considered | Single-owner and progressive disclosure concerns rejected them | Human orientation only; no generated wiki or duplicated symbol truth |

## Frozen Evidence Inputs

### Git History

PR1 generates a deterministic first-parent inventory from
`b8166fc8..5bc48d46`:

- 130 commits;
- expected 391 unique history-touched paths;
- 366 final-net paths;
- expected 25 transient/reverted paths.

The exact command and path normalization must be stored in the accepted test
specification. If another traversal yields 392/26, execution stops until the
merge-parent-only class is named, hashed, and either included or explicitly
excluded. No count is adjusted silently.

Each commit and each path receives:

`source | type | final_state | target_pr | disposition | owner | reason | verification`

Allowed dispositions:

- `retain-as-is`
- `reimplement-minimally`
- `replace-with-upstream`
- `prune-redundant`
- `transient-or-reverted`
- `defer-with-owner`

### Codex Sessions

Before mining, PR1/PR2 execution freezes a local-only corpus manifest:

- include only sessions whose normalized working directory belongs to ARIA-NBV
  or whose user-authored content explicitly targets ARIA-NBV;
- stable pseudonymous session ID derived from content, not runtime UUID exposure;
- content hash, authored-time range, capture time, parser version, MemPalace pin,
  inclusion reason, and deduplication relation;
- no raw message text, absolute path, user identity, credentials, or machine ID
  in tracked output.

Raw sessions and the reversible local manifest remain ignored. The accepted
bundle records only aggregate counts, corpus digest, reviewed paraphrases,
source hashes, and owner/conflict/supersession relations. Secret/PII detection is
a hard stop before any push.

## External Basis And Reuse Policy

The source/license ledger classifies every external item as `linked`,
`paraphrased`, or `copied`. Default is linked/paraphrased. No upstream prompt,
schema, or implementation is copied without license and hash review.

### Agent Guidance And Skills

- [OpenAI Harness Engineering](https://openai.com/index/harness-engineering/):
  concise repository maps, versioned knowledge, and mechanical consistency.
- [OpenAI Codex repository instructions](https://developers.openai.com/codex/guides/agents-md):
  root and nested `AGENTS.md` ownership.
- [Agent Skills specification](https://agentskills.io/specification): progressive
  disclosure and portable skill structure.
- [Optimizing skill descriptions](https://agentskills.io/skill-creation/optimizing-descriptions):
  positive and negative activation evaluation.
- [Evaluating skills](https://agentskills.io/skill-creation/evaluating-skills):
  realistic with/without or previous-version outcome comparisons.
- [Anthropic, Effective Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents):
  finite attention and smallest useful context.
- [Anthropic, Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents):
  traces are not outcomes; use explicit graders and recorded trials.
- [Matt Pocock skills at the approved pin](https://github.com/mattpocock/skills/tree/ed37663cc5fbef691ddfecd080dff42f7e7e350d):
  generic engineering skills remain external and operator-local.

### Navigation And Memory

- [Graphify at the repository pin](https://github.com/Graphify-Labs/graphify/tree/66d8110a534b52df3d660b5fda5aa5461a6b667a):
  `graphifyy==0.9.26`, native query/path/explain/affected/tree, and
  `EXTRACTED`/`INFERRED` provenance.
- [MemPalace v3.6.0](https://github.com/MemPalace/mempalace/releases/tag/v3.6.0):
  v3.6.0 release; verify package hash, commit, license, and public APIs before
  implementation.
- [The Palace](https://mempalaceofficial.com/concepts/the-palace.html): rooms,
  halls, tunnels, closets, and drawers are navigation/retrieval structure.
- [Mining Your Data](https://mempalaceofficial.com/guide/mining.html): upstream
  conversation mining.
- [MCP Integration](https://mempalaceofficial.com/guide/mcp-integration.html):
  search-first access and MCP boundaries.
- [Knowledge Graph](https://mempalaceofficial.com/concepts/knowledge-graph.html):
  provenance-linked temporal assertions and `as_of` behavior.
- [Contradiction Detection](https://mempalaceofficial.com/concepts/contradiction-detection.html):
  experimental limitation; not a truth-resolution dependency.
- [Closets design](https://github.com/MemPalace/mempalace/blob/8ab251c452c43f2b07a76a28f2433e258307f571/docs/CLOSETS.md):
  drawers preserve content; closets are compact pointers.
- [Source adapter RFC 002](https://github.com/MemPalace/mempalace/blob/8ab251c452c43f2b07a76a28f2433e258307f571/docs/rfcs/002-source-adapter-plugin-spec.md):
  draft evidence only, not a stable API contract.

### Provenance Vocabulary And Governance

- [W3C PROV-O](https://www.w3.org/TR/prov-o/): derivation, attribution,
  revision, invalidation, and provenance bundles.
- [RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/): vocabulary guidance
  only; no RDF runtime is introduced.
- [SHACL](https://www.w3.org/TR/shacl/): structural validation vocabulary only;
  conformance is not factual truth.
- [NIST AI 600-1](https://doi.org/10.6028/NIST.AI.600-1): documentation,
  measurement, and monitoring context.
- OMO Prometheus (`code-yeongyu/oh-my-openagent`): concept-only inspiration.
  This plan and OMX workflow are a clean-room MIT reimplementation; no OMO
  wording, prompts, control flow, hooks, or runtime code are copied.

## Issue-to-PR Crosswalk

All findings in the approved report must appear in PR1's full matrix and in the
description of the implementing or deferring PR.

| Report issue | Target PR | Required disposition |
| --- | --- | --- |
| `SCAFF-001` full prompt budget omitted | PR3 | Separate repository-controlled and actual runtime catalog metrics |
| `SCAFF-002` lexical routing fixtures | PR3 | Relabel lint; add runtime activation/outcome evals |
| `SCAFF-003` graph link correctness | PR4 | Reviewed sampled precision by provenance/relation/modality |
| `SCAFF-004` graph cannot navigate scaffold | PR4 | Resolve by explicit direct-source scaffold bypass |
| `SCAFF-005` bibliography omission | PR4 | Add both active Bib files |
| `SCAFF-006` Graphify trigger/body risk | PR4 | Narrow trigger; retain upstream body without ARIA fork growth |
| `SCAFF-007` tree side effect | PR4 | Explicit ignored temporary output |
| `SCAFF-008` LOC accounting hides custom machinery | PR5 | Disaggregate categories and report cumulative delta |
| `SCAFF-009` adapter growth | PR4, PR5 | Minimize adapter, then reconcile cumulative LOC |
| `SCAFF-010` purge-oriented OMX overengineering | PR1, PR5 | Implement minimal registry; prove heavy purge code unnecessary or defer |
| `SCAFF-011` unnamed diagnostic route | PR3 | Name and evaluate actual route |
| `SCAFF-012` Matt prose drift | PR3 | Remove mutable counts from prose |
| `SCAFF-013` optional Matt config ambiguity | PR3 | Installed/absent doctor and honest scope |
| `SCAFF-014` copied hooks stale | PR4 | Observable digest and uninstall path |
| `SCAFF-015` synchronous full graph refresh | PR4 | Bounded two-speed local policy |
| `SCAFF-016` debrief usefulness unmeasured | PR2 | Retrieval-value benchmark; keep chosen debrief policy |
| `SCAFF-017` transcript completeness unmeasured | PR2 | Hand-labeled temporal sample and precision/recall |
| `SCAFF-018` stale migration-owner wording | PR1, PR2 | Historical annotation plus active owner checks |
| `SCAFF-019` context capability reduction | PR3 | Outcome comparison before restoring any helper |
| `SCAFF-020` retired LitKG references | PR2, PR5 | Historical status, zero active routes, final stale scan |

## Pull Request Series

### PR1: Evidence, Ownership, Minimal OMX

**Branch:** `codex/scaffold-01-evidence-ownership`

**Owns:**

- `.agents/references/source_order.md`
- `.agents/references/human_owner_intent.md`
- `.agents/references/alignment_tools_contract.md`
- minimal `.agents/references/omx_artifact_policy.md`
- `.agents/omx_artifacts.toml`
- agents DB TOMLs
- minimal OMX registry/redaction/hash/transition validator and tests
- `.gitignore` privacy and accepted-bundle rules
- current accepted bundle at native `.omx/context`, `.omx/specs`, and
  `.omx/plans` paths

Current accepted artifacts remain at their native role paths. Privacy-safe
accepted bundles may later move byte-identically to
`.omx/archive/accepted-bundles/<bundle-id>/`; unaccepted pre-policy payloads
containing machine-local paths are removed and represented by a concise
registered disposition specification.

**Deliverables:**

- snapshot PR #28 metadata/check result, then close it with a supersession note;
- accepted six-role bundle with a hashed acceptance record, report, complete responsibility matrix,
  temporal decision/conflict ledger, history/path/issue disposition, primary
  sources, test specification, reviews, and handoff;
- complete 130-commit and history/net/transient path inventory;
- reviewed current preferences in `human_owner_intent.md`;
- current non-duplicate actionable items in agents DB;
- production/test/generated/upstream LOC baseline;
- privacy and clean-room source/license ledger.

**Acceptance:** zero unclassified commits, paths, issues, user invariants,
preferences, conflicts, or TODOs in the frozen corpus; accepted bundle hashes and
redaction pass; no raw/machine-local evidence tracked.

### PR2: Memory And MemPalace

**Branch:** `codex/scaffold-02-memory-mempalace`

**Owns:** `.agents/memory/**`, MemPalace plugin/contract, transcript extractor,
agent-memory tests, and its scoped Make targets.

**Deliverables:**

- one disposition row per state-journal claim/section before deletion;
- verified MemPalace v3.6.0 release pin/license/public commands;
- optional installed and absent behavior;
- ignored local palace and frozen session manifest;
- upstream conversation mining for retrieval;
- pruned custom extractor limited to unsupported audit-grade user/plan-answer
  capture and reviewed promotion records;
- reviewed relation fields: source hash, observed time, scope, status, owner,
  verification references, conflicts-with, supersedes/superseded-by, and
  promotion commit/hash;
- no automatic promotion, contradiction, or truth classification;
- debrief usefulness and transcript extraction benchmark.

**Acceptance:** zero unresolved state claims; secret/PII scan clear; raw data and
palace ignored; installed/absent clean-clone tests pass; exact-source fallback
works with MemPalace unavailable.

### PR3: Skills, Routing, Matt, Runtime Evaluations

**Branch:** `codex/scaffold-03-skills-routing`

**Owns:** root routing sections, `.agents/skills/**`, skill style and Matt
references, Matt scripts/config example, routing fixtures/evals, and related
tests.

**Deliverables:**

- compact ARIA operational skill inventory;
- retain `aria-docs` progressive references and measured-autoresearch's mixed
  research/implementation loop;
- explicit diagnostic route;
- domain facts removed from skill bodies;
- exact-source scaffold routing independent of Graphify/MemPalace/Matt/OMX;
- Matt pin, closure hashes, optional installed/absent doctor;
- lexical fixtures identified as lint;
- realistic positive, near-miss negative, ambiguous handoff, held-out, repeated
  activation and task-outcome evaluations;
- full runtime prompt catalog grouped by repository/plugin/system/global source,
  separate from repository-controlled description bytes.

**Acceptance:** activation precision/recall and task outcome results beat or
match the frozen baseline without material prompt/runtime regression; no
duplicate domain owner is introduced.

### PR4: Graphify And Hooks

**Branch:** `codex/scaffold-04-graphify-hooks`

**Owns:** `.graphify.toml`, Graphify corpus policy, vendored upstream skill
boundary, minimal adapter/bridge, Graphify tests, post-commit hook, hook installer
targets, and Graphify contract text.

**Deliverables:**

- pin `graphifyy==0.9.26` and upstream commit
  `66d8110a534b52df3d660b5fda5aa5461a6b667a`;
- code/thesis/literature corpus with `docs/references.bib` and
  `docs/references-qh.bib`;
- explicit exclusion of scaffold, sessions, transcripts, runtime, accepted OMX,
  caches, and generated output;
- native query/path/explain/affected/tree traversal;
- adapter only for temporary corpus selection and unsupported Typst/TeX/Bib
  extraction;
- fixed reviewed sample of `EXTRACTED` and `INFERRED` links by relation/modality;
- narrow Graphify activation description;
- tree output directed to ignored temporary storage;
- installed-hook digest and uninstall path;
- local/no-network/no-transcript/no-tracked-write hook with hard timeout;
- code changes request native incremental refresh; semantic sources only set an
  ignored stale marker for explicit sync.

**Acceptance:** representative retrieval and precision thresholds pass;
documented commands work in a clean install; optional-tool absence falls back to
exact sources; hook latency/failure/write/network fixtures pass.

### PR5: Integration, Residual Pruning, Selective Docs

**Branch:** `codex/scaffold-05-integration`

**Owns:** final integration sections of shared guidance/Makefile/CI, verification
matrix, final accounting, residual obsolete scaffold, final debrief, and only
proven necessary public-doc changes.

**Deliverables:**

- reconcile every source commit/path and `SCAFF-001..020` row;
- delete remaining redundant adapters, stale references, duplicated byte counts,
  and unused fixtures;
- prove no active LitKG, state-journal, broad-context, generated-wiki, or retired
  route remains;
- include thesis/docs changes only with an exact failed prerequisite and focused
  render evidence;
- final before/current/target matrix and changed-responsibility narrative;
- cumulative LOC accounting for custom production, tests, generated artifacts,
  accepted OMX evidence, and upstream/vendored surfaces separately.

**Acceptance:** cumulative custom production scaffold LOC is strictly below the
PR1 baseline; full clean-clone installed/absent matrix, root CI, and independent
exact-head review pass.

## Shared-Path Mutation Ledger

Shared files are not free-for-all ownership:

| Path | PR allowed to edit | Hunk responsibility |
| --- | --- | --- |
| `AGENTS.md` | PR3, PR4, PR5 | routing; Graphify/hook command; final reconciliation |
| `Makefile` | PR2, PR3, PR4, PR5 | memory; skill/Matt; Graphify/hook; final aggregation |
| `.gitignore` | PR1; PR4 only if required | privacy/OMX; generated Graphify output |
| `source_order.md` | PR1 only | authority ladder |
| `human_owner_intent.md` | PR1 only | reviewed current preferences |
| `verification_matrix.md` | PR5 only | final command matrix |
| agents DB TOMLs | PR1, then normal discovered-work updates | initial reviewed TODOs; later exact findings |

Any additional shared-path edit requires a ledger amendment in the editing PR
with reason and focused diff. It is not silently absorbed.

## Verification Matrix

| Claim | Evidence | PR owner |
| --- | --- | --- |
| Reconstruction is complete | ancestry, commit ledger, history/net/transient reconciliation | PR1 |
| All report findings are owned | `SCAFF-001..020` crosswalk with status/test | PR1, PR5 |
| Publication is privacy-safe | ignored/tracked scans, secret/PII scanner, fixture paths | PR1, PR2 |
| Accepted evidence is immutable | hashes, registry transition/supersession tests | PR1 |
| State retirement is lossless | claim-level disposition, zero unresolved active references | PR2 |
| MemPalace is optional and derived | installed/absent clean clones, exact-source fallback | PR2 |
| User invariants are retrievable but not auto-truth | labeled transcript eval and owner-promotion audit | PR2 |
| Skills route usefully | activation precision/recall, task assertions, previous/no-skill comparison | PR3 |
| Prompt budget is honest | full catalog and repository-controlled categories | PR3 |
| Graph links are useful | sampled precision and representative retrieval | PR4 |
| Graphify remains optional navigation | absent-tool exact-source fallback | PR4 |
| Hooks are bounded | timeout, no-network, no-transcript, no-tracked-write, digest tests | PR4 |
| Thesis scope did not creep | no docs diff or exact prerequisite plus compile/render | PR5 |
| Scaffold is simpler | disaggregated cumulative LOC and deleted-owner ledger | PR5 |
| Each PR is merge-ready | diff check, touched Ruff, targeted tests, agents DB validate/render, scaffold audit/self-test, memory check, CI, exact-head review | Every PR |

## PR Description Contract

Every PR body uses this reviewer-first structure:

```markdown
## Summary
<one paragraph: responsibility moved, why, and what remains unchanged>

## Responsibility Matrix
| Surface | Before | Current source branch | This PR / final target |

## Retained, Replaced, Pruned, Deferred
| Item | Disposition | Owner | Evidence |

## Issue Crosswalk
| SCAFF ID | Status | Change or deferral | Verification |

## User Invariants And Conflicts
<reviewed current preferences, superseded alternatives, unresolved ambiguity>

## External Basis
<primary links, version/commit/license, linked/paraphrased/copied classification>

## Verification
<commands and fresh results>

## Risks And Rollback
<remaining uncertainty, reverse-order rollback, immutable evidence rule>

## Series
<predecessor, successor, PR #28 supersession context>
```

PR1 includes the complete 20-issue index and full responsibility matrix. Later
PRs repeat the relevant subset and link the immutable accepted bundle.

## Rollback And Stop Conditions

Merge sequentially. If a merged PR must be removed, revert in reverse order.
Never rewrite an accepted bundle; create a superseding accepted bundle with a
successor link.

Stop before push or PR creation when:

- history/net/transient path counts do not reconcile;
- any commit, path, report issue, current preference, conflict, or TODO is
  unclassified;
- secret/PII scanning fails;
- raw transcript text, absolute paths, runtime IDs, palace data, or generated
  graph output would become tracked;
- an upstream pin/license/public API cannot be reproduced in a clean environment;
- exact-source fallback fails when an optional tool is absent;
- an accepted artifact hash drifts;
- a PR edits another PR's owner without a ledger amendment;
- targeted tests, root CI, or independent exact-head review fail;
- cumulative final custom production LOC is not below baseline.

## Ultragoal Handoff

Use one serial integrator. Review and verification agents may run independently,
but no parallel write lanes are allowed.

```text
$ultragoal ".omx/plans/prometheus-strict/aria-nbv-scaffold-five-pr-rebuild.md"
```

Recommended story sequence:

1. Snapshot and close PR #28; freeze history and session evidence.
2. Build, validate, publish, and merge PR1.
3. Rebase a fresh worktree on merged main; build and merge PR2.
4. Repeat sequentially for PR3, PR4, and PR5.
5. Run final exact-head review and close the Ultragoal only after all hosted CI
   and immutable-evidence checks are green.

## Clean-Room Credit

Inspired by the high-level OMO Prometheus concept
(`code-yeongyu/oh-my-openagent`) and reimplemented independently under the local
MIT skill contract. No OMO prompts, wording, hooks, runtime code, or control flow
are copied.
