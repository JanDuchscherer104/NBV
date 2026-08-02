---
id: 2026-08-02_restore_rerun_inspector_procedure
date: 2026-08-02
title: "Restore Rerun Inspector Procedure"
status: done
topics: [scaffold, skills, rerun, progressive-disclosure]
confidence: high
canonical_updates_needed:
  - .omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md
files_touched:
  - .agents/skills/rerun-nbv-inspector/
  - aria_nbv/aria_nbv/rerun_inspector/README.md
  - AGENTS.md
  - scripts/scaffold/fixtures/routing.json
  - scripts/tests/test_agent_governance_g002.py
---

# Task

Restore the useful Rerun-specific procedure removed by the domain-skill
route-only pruning while keeping scientific and implementation truth in package
and thesis owners.

# Decision

`rerun-nbv-inspector` again owns the repeatable observer workflow: select the
offline or rollout branch, inspect the complete logging path, consult current
official Rerun evidence for SDK changes, prefer saved `.rrd` review artifacts,
fall back to fixture tests when stores are blocked, and report focused evidence.

The module README, source, configuration, and tests continue to own commands and
implemented behavior. The restored Context7 prompts and official-example map are
conditional routing aids and explicitly non-authoritative.

# Verification

- System skill validation passed.
- `make scaffold-audit` passed with 12 skills, zero errors, and the 13 existing
  warnings on other retained skills.
- `make scaffold-audit-self-test` passed 15 negative probes and all five G002
  governance tests; the focused G002 pytest also passed five tests.
- `make check-agent-memory` and `git diff --check` passed.
- `make ci` passed: 266 package smoke tests, 112 focused package tests, 42
  Graphify projection tests, and the 33-page core docs render.
