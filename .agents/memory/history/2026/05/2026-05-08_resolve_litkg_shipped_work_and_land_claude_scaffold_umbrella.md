---
id: 2026-05-08_resolve_litkg_shipped_work_and_land_claude_scaffold_umbrella
date: 2026-05-08
title: "Resolve litkg shipped work and land Claude scaffold umbrella"
status: done
topics: [scaffold, litkg, claude, agents-db, memory, tooling]
confidence: high
canonical_updates_needed: []
---

## Task
Reconcile the agents-DB with reality after the 2026-05-07 litkg-rs +
context-pack work landed in commits `d3e980d` and `152f13b`, and merge the
orphaned Claude Code scaffold from worktree `claude/pedantic-buck-d6f491`
into main as one umbrella record + cherry-picked files.

## Method
1. Smoked the three plan-grill claim-verdict scenarios:
   - V0-OBB GT support claim → `verdict=supported, confidence=1.0`.
   - V1-actor-visible claim → `verdict=contradicted, confidence=0.9`.
   - Habitat-as-main-simulator → `verdict=unverifiable, confidence=0.2`.
2. Resolved four agents-DB records covering shipped work:
   - `issue-029` (claim-check verdict contract) → resolved.
   - `issue-030` (kg-query duplication) → resolved.
   - `todo-061` (verdict logic implementation) → resolved.
   - `refactor-017` (delete kg-query) → resolved.
3. Resolved `refactor-018` (genre tier) wontfix — smoke shows
   `m1_contract_report.qmd` now appears 4× in `evidence_spans` and
   `required_reads` for the registry-design task; the verification-injection
   + lexical-filter changes closed the precedent-discovery gap without a
   genre frontmatter scheme.
4. Amended `todo-056.acceptance` with a wontfix note for verb-intent
   phase 2 — three real tasks (code, process, mixed) all produce reasonable
   `top_sources` without a dedicated boost; existing
   `apply_route_surface_adjustment` plus verification-target injection
   covers the observed gap.
5. Cherry-picked the worktree's Claude scaffold implementation files into
   main: `CLAUDE.md`, `.claude/settings.json`, `.claude/commands/` (7
   commands), `.claude/agents/` (4 sub-agents), `scripts/new_debrief.py`,
   `scripts/debrief_nudge.sh`, `scripts/kg/status.sh`,
   `scripts/sync_claude_skills.sh`, parallel-worktree guidance,
   `.agents/skills/diagnose-aria/agents/openai.yaml`. Deleted empty
   `default_profile.yaml`.
6. Patched `scripts/agents_db.py`:
   - Fixed pre-existing bug in `_dump_records` (KeyError on optional
     `references` field for refactors) by adding `if key in record` guard.
   - Ported the `search` subcommand (active + resolved scope).
7. Patched `Makefile`: added `new-debrief`, `claude-skills`, `kg-status`
   targets and updated `.PHONY` lines.
8. Patched `.codex/hooks.example.json` with the Stop debrief-nudge hook for
   parity with `.claude/settings.json`.
9. Updated `.agents/skills/aria-litkg-memory/SKILL.md`:
   - `kg-search` is now step 1 of the Protocol (empirical "killer verb"
     finding); `kg-route` is step 2 for context packs.
   - Added explicit `kg-status` health probe step + claim-check verdict
     expectations.
10. Added `## litkg Health Probe` section to
    `.agents/references/operator_quick_reference.md` pointing at
    `make kg-status`.
11. Added absolute-date rule to
    `.agents/references/agent_memory_templates.md`.
12. Filed umbrella `refactor-019` "Land Claude Code first-class agent
    scaffold and debrief automation" replacing the three colliding
    worktree records (the worktree's `issue-029`/`refactor-017`/`todo-061`
    are now obsolete; main's IDs at those numbers are the litkg work).
13. Ran `make claude-skills` → 19 symlinks (17 original + 2 new
    `scientific-writing`/`typst-authoring` from main).

## Findings
- `python3 scripts/agents_db.py validate` → passed.
- `python3 scripts/validate_agent_memory.py` → passed.
- `bash scripts/kg/status.sh` → exit 0, `kg-status: ok`.
- `make claude-skills` → idempotent; second run produces 0 new links.
- `python3 scripts/agents_db.py search 'kg-claim-check' --scope resolved` →
  surfaces the resolved `issue-029` and `todo-061` with notes.
- The five resolutions removed five active records and shifted the active
  backlog ranking; main's active `refactor-019` (umbrella) is now the
  ARIA-NBV-side scaffold work owner.

## Verification
- `python3 scripts/agents_db.py validate` → passed.
- `python3 scripts/validate_agent_memory.py` → passed.
- `make kg-claim-check KG_CLAIM='ARIA-NBV uses GT-OBB-cropped target RRI as
  V0 sanity/upper-bound' KG_FORMAT=json | jq '.verdict'` → `"supported"`,
  confidence 1.0.
- `make kg-claim-check KG_CLAIM='GT OBBs are actor-visible in the V1 main
  thesis result' KG_FORMAT=json | jq '.verdict'` → `"contradicted"`,
  confidence 0.9.
- `make kg-claim-check KG_CLAIM='ARIA-NBV uses Habitat as the main
  simulator' KG_FORMAT=json | jq '.verdict'` → `"unverifiable"`,
  confidence 0.2.
- `make kg-route KG_TASK='zzzzz nonsense' KG_FORMAT=json | jq
  '.confidence_summary'` → non-null fall-through string.
- `bash scripts/kg/status.sh; echo $?` → 0.

## Canonical State Impact
None. All edits are scaffold/tooling/DB-hygiene; canonical
`PROJECT_STATE.md`, `DECISIONS.md`, `OPEN_QUESTIONS.md`, and `GOTCHAS.md`
are unchanged. The new `refactor-019` is active backlog, not canonical
truth; resolved records are archive evidence.
