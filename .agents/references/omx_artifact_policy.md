# OMX Artifact Retention

OMX drafts, runtime state, logs, sessions, goals, and generated reports remain
operator-local and ignored. Accepted planning evidence is tracked only through
`.agents/omx_artifacts.toml`.

The registry has two states:

- `current` bundle members stay at their native role paths under
  `.omx/context`, `.omx/specs`, and `.omx/plans`;
- `superseded` bundle members are preserved byte-identically under
  `.omx/archive/accepted-bundles/<bundle-id>/`, retaining the path relative to
  `.omx`.

Bundle IDs are `<normalized-task>--<first-16-of-handoff-sha256>`. Promotion
requires the complete six-role successor bundle, Architect then Critic approval,
and `explicit-user-acceptance`. Supersession requires a current same-task
predecessor and records the successor link while archiving every predecessor
artifact. The approved July 2026 scaffold predecessor is the one bootstrap
exception: its exact handoff-bound 17-artifact manifest plus handoff is retained
under the reserved archive and linked to the approved successor task.

Registered bytes, membership, source commits, tombstones, and supersession links
are append-only. Ordinary public documentation URLs are allowed; credentials,
private keys, machine-local paths, and runtime identifiers are rejected. The
byte-identical legacy predecessor is grandfathered for its already-approved
machine-path content and cannot be rewritten.

Run `make omx-artifacts-check` before committing lifecycle changes. Every
tracked or otherwise visible `.omx` file must resolve through the registry;
native OMX archives outside `accepted-bundles` remain ignored and unregistered.
