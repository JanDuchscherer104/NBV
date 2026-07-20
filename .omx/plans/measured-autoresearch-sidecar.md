# Measured Autoresearch Sidecar — Implementation Plan

## Outcome

Ship one minimal, model-reachable `measured-autoresearch` skill that conditions both
`$oh-my-codex:autoresearch` and `$oh-my-codex:autoresearch-goal` when their mission
contains executable experiments. The sidecar owns only the empirical inner loop;
OMX continues to own intake, state, validation, persistence, critic verdicts, goal
state, completion, and cancellation.

The review unit is a skill-only pull request relative to `origin/main`. Installing
the exact reviewed skill into `~/.agents/skills/measured-autoresearch` is a local
post-commit action, not part of the Git diff.

## Current Evidence

- The vendored `$autoresearch` lifecycle chooses one validator, persists native-hook
  state, and finishes only through a passing completion artifact
  (`/Users/jd/.codex/plugins/cache/oh-my-codex-local/oh-my-codex/0.20.1/skills/autoresearch/SKILL.md:25-35,37-66`).
- The vendored `$autoresearch-goal` lifecycle owns mission/rubric/ledger/completion
  artifacts and professor-critic plus Codex-goal reconciliation
  (`/Users/jd/.codex/plugins/cache/oh-my-codex-local/oh-my-codex/0.20.1/skills/autoresearch-goal/SKILL.md:10-21,23-40`).
- Commit `fa4a9dc8` in `/Users/jd/repos/oh-my-codex` put the measured loop inside
  the vendored `autoresearch-goal` skill only. Its reference already contains the
  useful frozen-contract, one-hypothesis, measurement, keep/discard, integrity,
  and completion rules
  (`.../autoresearch-goal/references/measured-experiment-sidecar.md:5-55`).
- There is no installed `~/.agents/skills/measured-autoresearch`, and neither the
  ARIA-NBV branch inspected earlier nor the current project skill tree contains a
  standalone measured sidecar.
- The project-local `.codex/skills/autoresearch-goal/SKILL.md:23-39` is stale and
  lacks the measured reference, while `.codex/skills/autoresearch/SKILL.md:25-66`
  duplicates the OMX lifecycle. These copies are not extension points for this
  change.
- `writing-great-skills` says a sidecar another skill must reach should be
  model-invoked, and that one meaning must have one source of truth
  (`/Users/jd/.agents/skills/writing-great-skills/SKILL.md:11-20,53-59`).

## Requirements

1. **One owner for measured experimentation.** The new local skill is the sole
   source for frozen evaluation, baseline/candidate comparison, experiment rows,
   keep/discard decisions, and experiment completion evidence.
2. **Two lifecycle adapters, no lifecycle duplication.** The skill resolves the
   active enclosing workflow and writes its experimental artifacts beside that
   workflow's mission artifacts:
   - `$autoresearch`: `.omx/specs/autoresearch-<slug>/`
   - `$autoresearch-goal`: `.omx/goals/autoresearch/<slug>/`
3. **Model-reachable but narrowly triggered.** Omit
   `disable-model-invocation`; the description should trigger only when either OMX
   research workflow is active and executable experiments can improve or decide
   the deliverable. Ordinary literature lookup and non-experimental research must
   not activate it.
4. **Instruction-only implementation.** Start with exactly one `SKILL.md`. Add no
   Python recorder, dependency, README, copied OMX reference, or template unless a
   failed behavioral probe demonstrates that prose alone is insufficient.
5. **No vendor or shadow edits.** The skill-only PR must not edit
   `/Users/jd/repos/oh-my-codex/skills/`, plugin-cache files, or the project-local
   `.codex/skills/{autoresearch,autoresearch-goal}` copies.
6. **Dirty-worktree safety.** Candidate rejection must never use repository-wide
   reset, checkout, restore, clean, or stash against pre-existing work. One owner
   controls the declared mutable surface.
7. **Evidence before completion.** Generated-output missions require at least one
   inspectable sample artifact in addition to scalar metrics. Evaluator leakage,
   failed hard gates, and unreproducible candidates cannot be retained.

## Skill Contract

### Invocation

Use frontmatter equivalent to:

```yaml
---
name: measured-autoresearch
description: Measure executable experiments inside active OMX autoresearch or autoresearch-goal missions; use for frozen-evaluator baseline/candidate loops, not literature-only research.
---
```

The leading word is **measure**. It should consistently anchor contract freezing,
baseline parity, candidate evaluation, and keep/discard decisions.

### Ownership boundary

The first section of the skill must state:

- `$autoresearch` owns validator mode, native-hook continuation, `result.json`, and
  terminal validation.
- `$autoresearch-goal` owns mission/rubric/critic ledger, Codex goal state, and
  completion reconciliation.
- `measured-autoresearch` owns only `experiment-contract.md`, `experiments.tsv`,
  candidate artifacts, and the empirical decision within the active mission root.
- The sidecar never creates/completes goals, writes critic verdicts, changes OMX
  state, or decides that the enclosing workflow is complete.

### Ordered workflow

1. **Resolve the enclosing mission.** Detect exactly one active OMX research
   workflow and its existing mission root. If neither or both can be resolved,
   stop the experiment branch with an explicit blocker rather than inventing a
   path. Completion criterion: one existing mission root and one enclosing owner.
2. **Freeze `experiment-contract.md`.** Record evaluator command and fingerprint,
   preparation path, split/data identity, hard gates, primary metric/direction/
   tolerance, ordered secondary metrics and allowed regressions, mutable surface,
   device, seed, budget, timing synchronization, artifact paths, and rollback
   method. Completion criterion: the same contract can evaluate baseline and every
   candidate without editing evaluator semantics.
3. **Measure the baseline.** Run the exact candidate command and budget before any
   mutation, save evaluator output plus required sample artifact, and append the
   baseline row. Completion criterion: a valid reproducible baseline row exists.
4. **Run one falsifiable candidate.** State one hypothesis and smallest causal
   mutation, change only the declared surface, run hard gates then the fixed
   evaluator, synchronize the accelerator before timing, and inspect the output.
   Completion criterion: one valid or explicitly invalid candidate row with an
   artifact path.
5. **Decide immediately.** Keep only a primary improvement beyond tolerance; on a
   primary tie, follow the contract's ordered secondary metrics and reject any
   material regression; otherwise restore only the owned bytes/isolated worktree.
   Completion criterion: retained code and recorded decision agree exactly.
6. **Continue from evidence.** Choose the next hypothesis from retained and failed
   rows. Continue until the enclosing validator/rubric passes, the user interrupts,
   or a hard blocker has no safe recovery. Completion criterion: control returns
   to the enclosing OMX workflow with the measured evidence, never with a
   sidecar-authored lifecycle verdict.

### Experiment ledger

Keep the schema inline because every experimental branch needs it and it is short:

```text
iteration\tcandidate\trevision\thypothesis\tprimary\truntime_s\tpeak_memory_mb\tnon_test_loc\thard_gates\tdecision\tartifact
```

Rules:

- Append exactly one row for the baseline and every attempted candidate, including
  invalid and discarded runs.
- Use `experiments.tsv` only for candidate measurements. OMX `ledger.jsonl` remains
  the critic/workflow ledger.
- Never rewrite failed rows; they prevent repeated dead ends.
- Label real, official synthetic, simulated, and stand-in data accurately.

## Acceptance Criteria

1. A clean branch from ARIA-NBV `origin/main` contains exactly
   `.agents/skills/measured-autoresearch/SKILL.md`; `git diff --name-only
   origin/main...HEAD` prints that path and no other path.
2. `quick_validate.py` returns success for the skill directory:

   ```bash
   python /Users/jd/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
     .agents/skills/measured-autoresearch
   ```

3. The committed skill and installed user-scope copy are byte-identical:

   ```bash
   cmp .agents/skills/measured-autoresearch/SKILL.md \
     /Users/jd/.agents/skills/measured-autoresearch/SKILL.md
   ```

4. Static inspection confirms the skill names both enclosing workflows, both
   mission-root layouts, the two experiment artifacts, baseline parity, tolerance,
   hard gates, artifact inspection, and safe rollback.
5. Static inspection confirms it contains no OMX lifecycle commands such as
   `create_goal`, `update_goal`, `omx autoresearch-goal verdict`, or completion
   reconciliation instructions.
6. An independent behavioral probe for an executable `$autoresearch` mission
   resolves the `.omx/specs/` root, freezes the contract, and requests a baseline
   before suggesting a candidate.
7. An independent behavioral probe for an executable `$autoresearch-goal` mission
   resolves the `.omx/goals/` root and keeps candidate measurements separate from
   the professor-critic ledger.
8. Negative probes for literature-only research, missing evaluator, ambiguous
   mission root, failed hard gates, and dirty unrelated files respectively avoid
   activation, block measurement, block path invention, discard the candidate,
   and preserve unrelated bytes.
9. The PR base is `origin/main`, its diff is skill-only, and its description states
   that local installation is a byte-identical post-commit action.

## Implementation Steps

1. **Create an isolated ARIA-NBV worktree from `origin/main`.** Do not implement in
   the unborn container worktree at `/Users/jd/Documents/Aria-NBV`. Create a named
   branch and verify a zero diff before authoring. This isolates the skill-only PR
   from the existing nested worktrees and untracked files.
2. **Author the single-file skill.** Create
   `.agents/skills/measured-autoresearch/SKILL.md` using the invocation, ownership,
   ordered workflow, ledger, safety, and completion contracts above. Apply the
   no-op and duplication tests sentence by sentence; keep the body below roughly
   120 lines unless a concrete omitted invariant requires more.
3. **Run static and behavioral validation.** Run `quick_validate.py`, required/
   forbidden phrase checks, and the positive and negative independent-agent probes
   from Acceptance Criteria 4-8. Revise only when a probe demonstrates ambiguous
   or missing behavior.
4. **Commit and review the skill-only unit.** Confirm the branch contains one file,
   one purposeful commit, no generated metadata, and no vendor/project lifecycle
   edits. Use an independent code-review/skill-writing pass to check predictability,
   premature-completion gates, duplication, sediment, sprawl, and no-ops.
5. **Install the reviewed bytes locally.** Copy the committed directory to
   `/Users/jd/.agents/skills/measured-autoresearch`, compare it with `cmp`, and
   start a fresh Codex session if catalog discovery is session-bound. Do not copy
   it into `.codex/plugins`, `.codex/skills`, or the OMX repository.
6. **Open the skill-only PR relative to ARIA-NBV `main`.** Include the validation
   commands and behavioral-probe results. Re-check the remote diff after push, not
   only the local working tree.
7. **Handle the existing OMX-fork duplication separately.** In a distinct cleanup
   PR against `/Users/jd/repos/oh-my-codex` `main`, revert the content introduced by
   `fa4a9dc8` and rebuild/reinstall OMX. This is intentionally excluded from the
   skill-only PR. Until that cleanup lands, document that `$autoresearch-goal` may
   load both the old vendored reference and the new local skill; do not claim a
   single source of truth in that interim state.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Model-invocation fires for ordinary research | Keep the description limited to active OMX research plus executable experiments; include a literature-only negative probe. |
| Sidecar accidentally owns completion | Forbid lifecycle commands and test both enclosing workflows with independent probes. |
| Vendored and local measured rules diverge | Make the local skill canonical; remove `fa4a9dc8` in a separate cleanup PR. |
| Project-local `.codex` copies shadow plugin skills | Invoke the plugin-namespaced OMX workflows in probes; do not edit or depend on stale copies. |
| Candidate rollback damages user work | Require isolated worktrees or byte-owned restoration and explicitly forbid repository-wide rollback. |
| Metric gaming or leakage | Freeze evaluator/data fingerprints and make leakage/hard gates precede primary comparison. |
| Skill grows into a framework | One Markdown file, no runtime code or dependency unless a failed probe proves it necessary. |
| Home installation drifts from reviewed source | Copy only after commit and verify with `cmp`; the Git source remains authoritative. |

## Verification Sequence

1. Validate frontmatter and directory naming with `quick_validate.py`.
2. Verify exact PR file scope with `git diff --name-status origin/main...HEAD`.
3. Run required/forbidden contract searches.
4. Run executable positive probes for both OMX enclosing workflows.
5. Run the five negative/safety probes.
6. Obtain an independent skill-writing/code-review verdict.
7. Commit, install, and verify source/install byte identity.
8. Push, inspect the remote PR diff, and record the PR URL.

## Delivery Packages

### Package A — Skill-only PR

- One new file: `.agents/skills/measured-autoresearch/SKILL.md`
- No OMX changes, application changes, scripts, templates, or dependencies
- Safe to review and merge independently

### Package B — Local installation

- Byte-identical copy at `~/.agents/skills/measured-autoresearch/SKILL.md`
- Not a Git change
- Activates the reviewed sidecar for user-scope Codex sessions

### Package C — OMX duplicate cleanup

- Separate PR reverting `fa4a9dc8` from the personal OMX fork
- Rebuild/reinstall verification for both plugin workflows
- Must not be folded into Package A

## Stop Condition

Planning is complete when this artifact is saved. Implementation is complete only
after Package A has a skill-only remote PR, Package B is byte-identical and
discoverable in a fresh session, both positive and all negative probes pass, and
the temporary duplication from `fa4a9dc8` is either removed through Package C or
reported explicitly as the sole remaining integration limitation.
