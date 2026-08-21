---
id: 2026-08-21_g004_native_minimal_frontmatter_rationale
date: 2026-08-21
title: "G004 native-minimal frontmatter and progressive-disclosure rationale"
status: done
topics: [agent-scaffold, ultragoal, frontmatter, progressive-disclosure, ownership]
confidence: high
canonical_updates_needed: []
---

## Task

Complete Ultragoal G004 by recording the accepted native-minimal frontmatter
target and the implementation rationale for the ARIA-NBV scaffold migration.
Preserve the existing accepted specification text, current worktree edits, and
commit; write only the target-state amendment and this debrief.

## Method

Read the current dirty diff, the progressive-disclosure implementation plan,
the Agent Memory contract, the active G004 objective, and the existing target
state. Selected the smallest durable owner: append the accepted rationale to
the target-state specification and place the episodic implementation receipt in
the dated history directory. Compared the true pre-migration base commit
`f79c137dd56c4d240d00f6a5b6d9276666ec4a0a` with the migrated worktree for all
11 custom skills while excluding the upstream Graphify bundle. The counting
basis includes both YAML frontmatter delimiter lines and every line between
them in the frontmatter count; the body count includes every remaining line
after the closing delimiter.

## Findings

- Native-minimal frontmatter is now exactly `name` plus `description` for each
  ARIA-owned custom skill. Invocation-wide invariants and branch selectors stay
  in compositional bodies; branch-specific procedures, inventories, and tool
  details move behind conditional references and outcome fixtures.
- `aria-nbv-context/references/context7_library_ids.md` is the single owner of
  exact Context7 IDs and plugin call identifiers. This prevents consumers from
  recreating a second Context7 registry and keeps local owner lookup separate
  from external API/version evidence.
- The Graphify skill is an upstream byte-identity exemption. The local
  `aria-nbv-context/references/graphify-aria-boundary.md` owns the ARIA-specific
  freshness, provenance, fallback, and progressive-disclosure boundary; the
  upstream skill owns Graphify's query/path/explain procedures.
- Final post-reference-pruning counts across the 11 custom skills are
  `533 baseline → 44 current final` frontmatter lines (reduction `489`,
  `91.7%`) and `841 baseline → 809 current final` body lines (reduction `32`,
  `3.8%`).
- G006 review repairs restored semantic hierarchy distinctions and explicit
  progressive-disclosure pointers, superseding the earlier 773/774 snapshot.
  All 11 custom skill files remain 48–117 lines, all under 150 lines.
- The changed owner surfaces are the custom `SKILL.md` bodies/frontmatter, the
  compositional references selected by those bodies, the Context7 registry,
  explicit routing fixtures, and the scaffold audit/governance tests that
  validate those ownership boundaries. No package, scientific, or runtime
  owner was changed.
- The integration test correction updated the positive Context7 routes
  `rerun-sdk-api-change` and `context7-pytorch3d-conceptual-plan` so their
  `expected_owner_paths` include
  `.agents/skills/aria-nbv-context/references/context7_library_ids.md`.
  Their expected plugin calls therefore resolve against an explicit reference
  owner rather than retired skill metadata; non-Context7 fixtures retain their
  forbidden-tool assertions.

## Verification

Evidence already collected before this debrief:

- G001 focused governance red phase: 2 failures and 4 passes against the old
  metadata schema; Graphify upstream integrity: 4 passes and 13 subtests;
  `git diff --check` passed.
- Historical intermediate G002 `python3 scripts/scaffold_audit.py --self-test`:
  9/9; Ruff and diff checks passed. Its remaining focused failures were the
  expected pre-migration failures before G003 moved the skills.
- G003 installed skill validation: 11/11; scaffold audit: zero errors; audit
  self-test: historical intermediate 9/9; governance plus Graphify tests: 25
  passes and 13 subtests; `make check-agent-memory` passed; `git diff --check`
  passed.

G005 recorded historical intermediate verification in an isolated
`/tmp/aria-scaffold-ci.NStYzI/venv` with the exact `graphifyy==0.9.48`
package installed. The scaffold CI suite is green: ci-impact 12, worktree
seed 11, setup shell PASS, Graphify freshness 8, upstream 4, ownership 18,
governance 21, and audit 0/0/self-test 24/0. Package `ruff-full` and
CPU-equivalent `package-smoke` are green (293 + 115 tests); the initial host
CUDA-exposure mismatch was environmental and resolved with
`CUDA_VISIBLE_DEVICES=''`, with no code change. Docs
`qmd-frontmatter-check`, the API docs self-test, and `docs-render-core` are
green with the expected unresolved API-link warnings. Final independent
re-review remains pending.

The scaffold-audit self-test result after validator hardening,
`passed=27 failures=0` (27/0 probes), is a historical intermediate milestone.
After the pointer-bypass probes, the current final result is
`passed=29 failures=0` (29/0 probes). The earlier `9/9` and `24/0` results are
also historical intermediate milestones.

## Canonical-State Impact

The accepted amendment was appended to
`.omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md`; prior
accepted text was not rewritten. This debrief records the rationale and
evidence for G004. No plan, ledger, state artifact, implementation, test,
skill, Graphify bundle, or unrelated history file was changed by this capture.
