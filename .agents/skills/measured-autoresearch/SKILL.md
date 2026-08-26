---
name: measured-autoresearch
description: Measure executable candidates inside an active OMX autoresearch or autoresearch-goal mission when a frozen evaluator can decide an empirical hypothesis; do not use for literature-only work.
---

# Measured Autoresearch

Run a tight empirical loop. The enclosing OMX skill owns lifecycle state; this
sidecar owns measurements under the active mission root.

## Boundary

- `$autoresearch` owns validator mode, continuation, `result.json`, and terminal
  validation.
- `$autoresearch-goal` owns its mission, rubric, critic ledger, Codex goal, and
  completion reconciliation.
- This sidecar owns only `<mission>/measurements/`, candidate patches, and the
  measured keep/discard decision.
- The helper records and renders evidence. It never runs the evaluator, mutates
  OMX state, changes Git state, or declares the enclosing workflow complete.

## Resolve one active mission

Resolve by owner evidence, in this order:

- `$autoresearch`: require the enclosing handoff or native-hook context to name
  its active `.omx/state/.../autoresearch-state.json`; never discover that file.
  Take the parent `.omx/specs/autoresearch-<slug>/` containing its
  `completion_artifact_path` and, when present, require `output_artifact_path` to
  resolve under the same root.
- `$autoresearch-goal`: take `<slug>` from the current `handoff --slug` payload,
  require `.omx/goals/autoresearch/<slug>/mission.json`, and require the active
  Codex goal objective to match that mission.

Never select by recency, glob historical missions, invent a slug, or create a
second root. Return a blocker unless one existing root and one lifecycle owner
are unambiguous.

## Active mission procedure

After resolving one mission, read [the measurement loop](references/measurement-loop.md)
before initializing the contract or mutating a candidate. It contains the
branch-specific evaluator, artifact, restoration, inspiration, and handoff
procedure.

## Universal invariants

- Freeze the evaluator contract before candidate mutation, and start a new
  series when its contract changes.
- Record ownership hashes before mutation and preserve unrelated worktree paths.
- Measure one falsifiable candidate at a time against the unchanged evaluator.
- Let the helper compute keep/discard decisions; never hand-author ledger rows.
- Keep every artifact path inside the mission root unless the manifest records
  the configured external location, hash, size, and provenance.
- Return evidence to the enclosing validator or critic; this sidecar never owns
  lifecycle state or a terminal verdict.

## Verification

Inspect the helper contract before use:

```bash
python3 .agents/skills/measured-autoresearch/scripts/experiment.py --help
python3 .agents/skills/measured-autoresearch/scripts/experiment.py example-contract
python3 .agents/skills/measured-autoresearch/scripts/experiment.py example-result
```

After changes to the helper or its procedure, run:

```bash
python3 -m unittest discover -s .agents/skills/measured-autoresearch/tests
```

For current external dependency API or version uncertainty, route through
[`aria-nbv-context`](../aria-nbv-context/SKILL.md) and its
[`Context7 registry`](../aria-nbv-context/references/context7_library_ids.md)
before changing the evaluator contract.
