# Git And External Actions

Load this branch only when work includes staging, committing, pushing, opening
or changing a pull request, publishing review comments, retargeting, releasing,
or another action that changes external state.

## Local Git Scope

- Stage only request-owned paths. Preserve unrelated dirty and generated state.
- Make the commit message describe the actual responsibility change, retained
  contract, and verification rather than an implementation chronology.
- Keep one reviewable concern and an independent rollback boundary per commit or
  pull request.

## External Boundary

- Require explicit current user authorization for the exact external action and
  repository. Authorization for one push, pull request, review, comment,
  retarget, or release does not silently authorize another.
- Confirm the live branch, remote, target, diff, and verification immediately
  before acting.
- Report the resulting URL, identifier, or exact blocker. Do not describe a
  local draft or successful command preparation as a completed external action.

## Publication Completion

When the user authorizes both a push and pull request for a durable change,
finish that publication in the same task: verify, make the focused commit, push
the intended branch, open a draft pull request, and report its URL. Without that
authorization, stop at the focused local commit and name the publication
boundary.

## Completion

- Only request-owned paths entered the change.
- The external action, if any, matches the authorized repository and operation.
- Every authorized publication has its remote URL or exact blocker.
- The handoff states retained behavior, verification, exclusions, and unresolved
  risk.
