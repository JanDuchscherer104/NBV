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

Publication lifecycle:

- Preserve immutable workpackage commit links in committed debriefs: publish
  them with GitHub **Create a merge commit** (or an equivalent no-ff merge),
  never squash or rebase them away. If a rebase or amend is unavoidable, update
  every link and `repo_head` in the separate debrief/index owner before
  publication.
- Actionable P0-P2 review findings become resolvable line threads. The fixing
  agent replies with what changed and exact-head proof; only then does the
  orchestrator resolve the thread.
- `$code-review` leaves one holistic verdict, architecture/verification/risk
  handoff in addition to line findings.
- With explicit continuing publication authority, Ultragoal may open a draft
  PR after the first coherent verified workpackage and push completed
  workpackages. Otherwise local commits remain the publication boundary.
- An active external orchestrator owns lifecycle coordination; ARIA skills own
  domain implementation and proof.

Proposal review or resolution also opens this reference. Apply exactly one
disposition only when explicit current-user authority or already-reviewed
policy evidence selects it; an agent cannot self-accept a proposal or choose
accept, reject, narrow, or defer on its own. Route the disposition to a human
reviewer when that authority is absent; this route is not a simulation.
Installation and its proof precede resolution. Without a human disposition,
leave the proposal active. If authority is absent, defer and keep the record active.
Do not mark it resolved without that authority.

## Completion

- Only request-owned paths entered the change.
- The external action, if any, matches the authorized repository and operation.
- Every currently authorized publication has a pushed branch and pull request.
- The handoff states retained behavior, verification, exclusions, and unresolved
  risk.
