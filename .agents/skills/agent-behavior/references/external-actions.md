# Git And External Actions

Load this branch only when work includes staging, committing, pushing, opening
or changing a pull request, publishing review comments, retargeting, releasing,
or another action that changes external state.

## Local Git Scope

- Stage only request-owned paths. Preserve unrelated dirty and generated state.
- After each completed workpackage or self-contained task, make a focused local
  commit before starting unrelated work. A local commit is a rollback boundary,
  not authorization for an external action.
- Make the commit message describe the actual responsibility change, retained
  contract, and verification rather than an implementation chronology.
- Keep one reviewable concern and an independent rollback boundary per commit or
  pull request.
- For a completed implementation workpackage, record its immutable commit link
  in the matching native debrief before regenerating the derived memory index.
  The later debrief/index commit is a separate provenance step.

## External Boundary

- Require explicit current user authorization for the exact external action and
  repository. Authorization for one push, pull request, review, comment,
  retarget, or release does not silently authorize another.
- Confirm the live branch, remote, target, diff, and verification immediately
  before acting.
- When the current user explicitly authorizes both push and pull-request
  publication for a durable implementation or fix, complete both in the same
  task after verification. Without that authorization, stop at the focused
  local commit and name the publication boundary.
- Report the resulting URL, identifier, or exact blocker. Do not describe a
  local draft or successful command preparation as a completed external action.
- Publish actionable code-review findings as resolvable review threads. After a
  fix, reply with what changed and exact-head proof, then resolve the thread.
- A code review also leaves one concise handoff covering verdict, architecture,
  verification, and residual risk.
- For an Ultragoal with continuing authorization to publish, open a draft pull
  request after its first coherent verified workpackage and push later completed
  workpackages to that same branch.

## Pull Request Description

- Open with a conceptual TL;DR that tells the reviewer what changed and why it
  matters before listing implementation details.
- Include a concise, educational account of the governing theory, assumptions,
  and relevant failure boundary so the review does not depend on hidden task
  context.
- When the change adds or materially edits an important decision-relevant
  figure, embed its rendered form with a caption or nearby explanation of what
  it establishes.
- Describe the published exact head and its current evidence accurately.

## Completion

- Only request-owned paths entered the change.
- The external action, if any, matches the authorized repository and operation.
- Every currently authorized publication has a pushed branch and pull request.
- The handoff states retained behavior, verification, exclusions, and unresolved
  risk.
