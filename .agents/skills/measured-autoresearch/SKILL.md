---
name: measured-autoresearch
description: Measure executable candidates inside an active OMX autoresearch or autoresearch-goal mission. Use when a frozen evaluator can decide an empirical hypothesis; do not use for literature-only work.
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

## Steps

### 1. Resolve one active mission

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

### 2. Freeze and initialize the contract

Before candidate edits, write a contract JSON containing the evaluator command
and fingerprint, data/split identity, hard gates, primary metric and tolerance,
ordered secondary metrics, mutable paths, fixed budget, device, seed, output
paths, and safe rollback method. Run:

```bash
python3 <skill>/scripts/experiment.py init \
  --mission-root <mission> --contract <contract.json>
```

The command screens unsafe evaluator text, normalizes the contract, fingerprints
it, and creates `<mission>/measurements/experiments.tsv`. Inspect `--help` and
`example-contract` for the accepted schema.

Capture `git status --short` and baseline hashes for every mutable path. Prefer
an isolated worktree. In a shared worktree, touch only paths proven clean or
experiment-owned; block on unrelated or uncertain changes. A contract change
starts a new measurement series and baseline.

Write `<mission>/measurements/ownership.json` with `git_status`, `git_root`, and
`mutable_paths`, an object mapping every declared path to its pre-mutation SHA-256
or `MISSING`. Do not store this evidence elsewhere.

Complete when `validate` passes and the declared candidate surface is cleanly
owned.

### 3. Measure the baseline

Run hard gates and the frozen evaluator with the exact candidate budget. The
enclosing owner executes commands; the helper does not. Save evaluator output,
logs, and at least one inspectable sample when the mission generates artifacts.
Write a result JSON using `example-result`, set `iteration` to `0`, and run:

```bash
python3 <skill>/scripts/experiment.py append \
  --mission-root <mission> --result <result.json>
```

Complete when `validate` reports one reproducible baseline with an existing
artifact manifest.

### 4. Measure one falsifiable candidate

State one hypothesis and make its smallest causal change inside the frozen
surface. Before mutation, copy `ownership.json` to the run directory and refresh
its hashes/status for the current incumbent. Save the exact candidate diff as
`runs/<iteration>-<candidate>/candidate.patch`. Run hard gates, then the unchanged
evaluator. Synchronize asynchronous accelerators before timing and inspect saved
outputs rather than trusting metrics alone. Include the contract ID and evaluator
fingerprint printed by `init` in the result JSON, then append it with the same
command as the baseline. List the ownership snapshot and patch in that run's
artifact manifest so the helper verifies their paths, sizes, and hashes.

The helper rejects stale contracts, malformed metrics, missing gates, invalid
artifact paths, non-monotonic iterations, and decisions inconsistent with the
frozen tolerances. It computes the keep/discard decision; do not hand-author TSV
rows.

Complete when `append` records a valid result or a classified invalid/crash row.

### 5. Make code match the recorded decision

Keep a candidate only when the helper records `keep`. Otherwise reverse only the
candidate patch or restore exact baseline bytes for explicitly owned paths.
Never use repository-wide `reset`, `checkout`, `restore`, `clean`, or stash-based
rollback against pre-existing work. Never rewrite old rows.

For a discard, write `runs/<iteration>-<candidate>/restore-proof.json` containing
`before_git_status`, `after_git_status`, and `mutable_paths`; each path maps to
`{"before_sha256": ..., "after_sha256": ...}`. Every before/after status and hash
must match. Add the proof to the artifact manifest before validation. For a keep,
record `restore-proof.json` as `{"status": "retained", "revision": ...}`.

Run:

```bash
python3 <skill>/scripts/experiment.py validate --mission-root <mission>
```

Complete when validation passes and the retained bytes match the recorded
revision.

### 6. Render evidence and return control

Run:

```bash
python3 <skill>/scripts/experiment.py report --mission-root <mission>
```

This writes `summary.json`, `summary.md`, and dependency-free `progress.svg`
under `<mission>/measurements/`. Return their paths, the candidate artifact,
baseline comparison, tests, metrics, limitations, and every attempted row to the
enclosing validator or critic. That owner decides whether to continue or finish.

Complete when one fresh measured decision and its rendered evidence have returned
to the owner without a sidecar-authored lifecycle verdict.

## Inspiration branch

When `summary.json` reports `plateau: true`, or the enclosing owner explicitly
requests new inspiration, pause candidate mutation:

1. Search scoped code, local `docs/literature/`, and repository literature
   indexes first.
2. If they do not yield a testable mechanism, inspect primary public papers and
   official upstream repositories. Use a bounded `researcher` subagent when it
   improves coverage; do not switch the active lifecycle to a terminal research
   workflow.
3. Append the source path or URL, version/commit, derived hypothesis, mechanism,
   and confidence to `<mission>/measurements/inspiration.jsonl`.

Research proposes the next falsifiable candidate. It never changes the frozen
evaluator, counts as an experiment row, or owns lifecycle state.

## Artifact policy

All measurement metadata and small inspectable outputs live in
`<mission>/measurements/`. Put each run's logs, evaluator result, sample, and
`artifact-manifest.json` under `runs/<iteration>-<candidate>/`; ledger artifact
paths must remain inside the mission root. Keep large checkpoints and publishable
deliverables in their configured external location and record path, hash, size,
and provenance in the manifest. The enclosing OMX ledger remains reserved for
workflow and critic events.

For blocked attempts, return the classified row when a run occurred, logs,
missing-item reasons, and proof that owned paths were restored while unrelated
paths were preserved.
