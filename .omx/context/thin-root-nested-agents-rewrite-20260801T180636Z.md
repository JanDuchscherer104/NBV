# Thin Root/Nested AGENTS Rewrite Context

Captured: 2026-08-01T18:06:36Z

## Task statement

Produce a consensus implementation plan for rewriting the ARIA-NBV root and
nested `AGENTS.md` scaffold around a thin-root, nearest-owner model. The plan
must incorporate the accepted target-state specification and the completed
best-practice research without implementing the rewrite.

## Desired outcome

- Root guidance contains only repository-wide safety, source-order and
  nearest-guide pointers, compact routing/capture guidance, optional-tool
  evidence boundaries, and a minimal verification rule.
- Package, module, and docs guidance contain only materially local contracts
  and validation.
- Repeatable procedures remain in skills; dynamic implementation and thesis
  truth remain in their canonical code, test, configuration, Quarto, Typst, or
  memory owners.
- Guidance consolidation preserves current routing and safety capabilities
  through a small outcome-oriented smoke set rather than exact prose or fixed
  skill-name assertions.
- Concurrent MemPalace and domain-skill edits are preserved and integrated
  rather than overwritten.

## Known facts and evidence

- Accepted owner and acceptance boundary:
  `.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md`, especially
  the thin-root/nested-guide requirements around lines 394-455, evaluator
  requirements around lines 610-661, and planning handoff around lines 955-968.
- Existing external synthesis:
  `.omx/specs/autoresearch-agent-scaffold-external-best-practices-20260730/report.md`,
  especially root/nested scope, progressive disclosure, outcome evaluation,
  stable invariants, and small review units around lines 48-186 and 327-371.
- Refreshed official evidence retrieved 2026-08-01:
  - https://developers.openai.com/codex/guides/agents-md
  - https://github.com/openai/codex/blob/main/codex-rs/protocol/src/prompts/base_instructions/default.md
  - https://openai.com/index/harness-engineering/
  - https://developers.openai.com/plugins/build/skills
  - https://agentskills.io/skill-creation/best-practices
  - https://agentskills.io/skill-creation/evaluating-skills
  - https://agents.md/
- OpenAI's current Codex behavior composes instruction files from root to leaf,
  lets nearer files override broader files, and has a default 32 KiB combined
  project-instruction discovery cap. The cap is not a target size.
- OpenAI's harness-engineering report identifies large root guidance as a
  context, staleness, and verification failure mode and recommends using the
  root as a progressively disclosed table of contents.
- Current root overreach candidates include:
  - detailed Mermaid/review/LRZ procedures in `AGENTS.md:13-36`;
  - package/scientific claims in `AGENTS.md:42-51`;
  - MemPalace operational policy in `AGENTS.md:63-70`;
  - duplicated capture, commands, and verification in `AGENTS.md:72-103`;
  - Graphify cache/setup mechanics in `AGENTS.md:112-120`.
- Existing nested guides are locally meaningful but contain pruning candidates:
  duplicated commands, dynamic public-contract inventories, historical seminar
  links, and the exact eight-symbol rollout allowlist.
- `scripts/scaffold/fixtures/routing.json` and
  `scripts/tests/test_agent_governance_g002.py` currently protect lexical
  details, exact fixture IDs, and skill names in addition to useful behavioral
  boundaries.
- `scripts/scaffold_audit.py` is a broad static validator; each retained check
  needs a stable recurring failure, positive/negative fixture, useful
  remediation, hermetic execution, and complexity smaller than the protected
  capability.
- Fresh baseline on 2026-08-01:
  - `make scaffold-audit`: exit 0, 20 skills, 0 errors, 21 warnings;
  - `make scaffold-audit-self-test`: exit 0, 11 self-tests and 6 G002 tests pass;
  - `make check-agent-memory`: exit 0.

## Current worktree and concurrency constraints

- HEAD: `2ef2cf07` on `codex/mempalace-compositional-integration`.
- Concurrent tracked edits currently touch:
  - `AGENTS.md`;
  - `.agents/references/source_order.md`;
  - `.agents/references/human_owner_intent.md`;
  - `.agents/skills/aria-nbv-context/SKILL.md`;
  - `scripts/scaffold/fixtures/routing.json`;
  - `scripts/tests/test_agent_governance_g002.py`.
- One concurrent untracked native debrief is present under
  `.agents/memory/history/2026/08/`.
- The overlapping diff adds compositional MemPalace corpus and semantic-recall
  policy. Planning must preserve its intended capability while relocating
  universal versus operational detail to the correct owners.
- A domain-skill consolidation is running in thread
  `019fb9c4-ba5a-7340-9ea5-b7d35db95cfb`; source-editing work packages that
  overlap skills or their routing consumers must begin from its integrated
  result, not from this snapshot alone.

## Constraints

- Planning mode only: no source, guidance, fixture, or test implementation edits.
- Preserve dirty-worktree changes and never use destructive Git restoration.
- Do not delete or merge guidance until each claim has a retained, relocated,
  replaced, deferred, or unresolved disposition and live consumers are known.
- Keep Graphify upstream skill byte-identical; ARIA-specific activation and
  safety remain in repository-owned companion surfaces.
- Optional Graphify, MemPalace, OMX, MCP, and autoresearch surfaces remain
  evidence/proposal mechanisms, never project truth owners or mandatory normal
  workflow dependencies.
- Prefer deletion and existing owners over new abstraction or another policy
  layer.
- Avoid arbitrary line-count acceptance criteria.

## Unknowns and decisions for the plan

- Exact claim-by-claim disposition after the concurrent domain-skill and
  MemPalace revisions land.
- Whether `scripts/scaffold_audit.py` should retain a narrowed lexical/static
  role or be decomposed into static schema checks plus separate behavioral
  smoke tests.
- Which current routing fixtures protect distinct outcomes versus duplicate the
  same capability under different skill names.
- Whether any nested guide can be removed after consumer and failure-history
  review; current evidence supports pruning, not blanket deletion.

## Likely touchpoints

- `AGENTS.md`
- `aria_nbv/AGENTS.md`
- `aria_nbv/aria_nbv/{data_handling,rollouts,rri_metrics,vin}/AGENTS.md`
- `docs/AGENTS.md`
- `.agents/references/source_order.md`
- `.agents/references/human_owner_intent.md`
- `.agents/skills/aria-nbv-context/SKILL.md`
- `scripts/scaffold/fixtures/routing.json`
- `scripts/tests/test_agent_governance_g002.py`
- `scripts/scaffold_audit.py`
- `scripts/tests/test_scaffold_audit.py`
- `.agents/memory/README.md`

## Planning stop condition

A durable PRD, test specification, and consensus handoff exist; Architect and
Critic approve in sequence; the plan names ownership dispositions, ordered work
packages, measurable acceptance criteria, concurrency gates, staffing, and a
verification path. No implementation begins in this workflow.
