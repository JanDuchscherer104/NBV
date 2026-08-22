---
id: 2026-08-21_g002_read_only_agent_status
date: 2026-08-21
title: "G002 Read-Only Agent Status"
status: done
topics: [scaffold, git, worktree, graphify]
confidence: high
canonical_updates_needed: []
codex_thread: codex://threads/01a0263b-dddc-75d1-ad6f-8026e0362f3f
---

## Task
Implement the independent G002 read-only checkout/worktree status command.

## Method
Repaired the adapter with one sealed `GIT_OPTIONAL_LOCKS=0` Git subprocess
boundary that disables system/global config, forces fsmonitor and untracked
cache off, removes ambient Git repository/discovery overrides, and preserves
probe return codes and streams. Added typed success/error envelopes, explicit
bare/primary/linked/standalone topology, unborn and unregistered handling,
validated upstream setup advice, unavailable dirty/readiness states,
owner-validated executable next actions, stdlib-only Make invocation, and
workflow path coverage. Graphify still delegates freshness semantics, retains
checker state/reasons/next_action as evidence, and no repair command executes.
Text rendering gives an unregistered worktree repair action precedence over
optional capability actions. Linked Graphify setup is offered only for a
wholly absent bootstrap; existing `graphify-out` or seed artifacts retain
checker evidence but produce no generic setup action.

## Scope
Changed only `scripts/agent_status.py`,
`scripts/tests/test_agent_status.py`, `scripts/ci_impact.py`,
`scripts/tests/test_ci_impact.py`, `Makefile`, `.github/workflows/ci.yml`, and
this debrief.

## Findings
`scripts/agent_status.py` reports stable JSON and concise text for bare,
primary, standalone, linked, detached, dirty, unborn, registered,
unregistered, upstream, runtime, submodule, and Graphify states. Tests cover
malicious local/global executable fsmonitor configuration with a positive
control, ambient Git-variable leakage, moved linked worktrees, missing
upstream refs, and healthy/unusable delegated Graphify. They snapshot the
checkout and common Git directory directly,
including regular-file hashes, symlink targets, mode, size, mtime/ctime, and
directory metadata; repeated invocation does not change repository files or
Git metadata.

## Verification
The focused agent-status suite passed 17 tests; the combined agent-status and
CI-impact pytest run reported 31 passing subtests. Coverage includes malformed
or non-object Graphify checker JSON and return-code/state consistency probes.
Text and JSON
`make agent-status` checks passed on linked, primary, and temporary bare
paths. `make scaffold-audit`, `make check-agent-memory`,
`make ci-impact-self-test`, Ruff, mypy, compilation, and `git diff --check`
passed. System `python3 -m pytest` remains unavailable because system pytest
is not installed; the repository virtualenv pytest suite passed. The
delegated existing Graphify checker may create its own temporary files outside
the repository; repository filesystem and Git metadata immutability, not
global filesystem immutability, is the proven boundary.

## Canonical Owner Impact
`agent_status.py` and the `agent-status` Make target are the canonical owners
of this diagnostic JSON/text contract; existing Git, Graphify, and setup
owners remain authoritative for repository facts and repair actions.
