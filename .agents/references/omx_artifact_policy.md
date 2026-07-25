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
are append-only. A bundle must first appear as `current`; a first-seen
`superseded` row is rejected unless its complete canonical record is the exact
immutable July 2026 bootstrap predecessor already tracked. The exception is
bound by the full-record SHA-256, not merely by bundle ID. Ordinary public
documentation URLs are allowed; credentials, private keys, machine-local paths,
and runtime identifiers are rejected. The byte-identical legacy predecessor has
one path-and-SHA-256 redaction exception for its already-approved machine-path
content; there is no bundle-wide bypass.

Promotion, supersession, seed restoration, and reviewed native OMX operations
use a worktree-specific recovery directory resolved by
`git rev-parse --git-path omx-bootstrap`. Before mutation, the validator rejects
path escapes, symlinks, and destination collisions, then records a versioned
journal plus checksummed byte backups of every owned destination and the Git
index. Writes use fsynced temporary files and atomic replacement. Supersession
publishes the complete predecessor archive before removing or replacing any
native predecessor path, and any pre-existing archive bundle root is a hard
collision. A normal failure rolls back immediately; an interruption leaves the
journal so the next mutation invocation performs idempotent rollback first.
Rollback restores only journal-declared paths and never recursively deletes an
archive root.

For destructive project purge recovery, export the registry and all registered
current/superseded payloads to a deterministic content-addressed seed outside
the repository:

```text
python3 scripts/scaffold/validate_omx_artifacts.py --export-seed <external-dir>
python3 scripts/scaffold/validate_omx_artifacts.py --verify-seed <sha256>.tar
python3 scripts/scaffold/validate_omx_artifacts.py --restore-seed <sha256>.tar
```

The tar has fixed metadata and exact manifest membership. Restore rejects every
pre-existing payload destination; the registry may remain after upstream purge
only when it is byte-identical to the verified seed. Restore validates all paths
and checksums before writing, stages only seed-declared paths, and journals the
original index. The supported purge contract is explicit backup, verification,
separately authorized execution of exactly
`omx uninstall --scope project --keep-config --purge`, proof that the entire
repository `.omx` tree is absent, and exact-hash restore. It does not claim an
upstream purge interlock. The purge may run only in a disposable clone with
HOME, Codex, XDG, and temporary state redirected beneath its enclosing
temporary parent. A sentinel must live outside that parent and remain
byte-identical throughout the purge and restore.

The native-operation wrapper accepts only the reviewed `cleanup --dry-run`,
`cleanup`, `ultragoal create-goals --force --brief ... --json`, and `cancel`
forms. It snapshots the registry and reserved accepted archive, journals all
registered files, and restores any attempted mutation. The review pin is
`oh-my-codex@0.20.3` with integrity
`sha512-7wlSTA1Nc9c31WX9w8THYPwlaleWV1dk/0WXqRgxpph34EI4oJM+Z4Egv04Nn8wN2SLI9K2LMfeOpNKI+06LGg==`;
version or integrity drift requires a new isolation review.

The executable native acceptance test clones the repository into a disposable
repository, redirects home, Codex/XDG state, and temporary storage into the same
disposable parent, verifies the reviewed OMX installation once, then runs the
actual `cleanup --dry-run`, `cleanup`, `ultragoal create-goals`, and `cancel`
commands through the protected wrapper. It asserts byte identity for the exact
approved successor and archived bootstrap predecessor after every command. The
same test exports and verifies a content-addressed seed, executes the exact
project purge command above, proves the complete repository `.omx` tree was
removed, restores only the verified seed membership, and checks every restored
payload against its pre-purge SHA-256. Its sentinel is outside the enclosing
temporary parent and must remain byte-identical. Run the pinned gate with:

```text
make omx-native-acceptance
```

CI installs `oh-my-codex@0.20.3` and runs this target as a required root
verification step. The validator independently compares the installed package
and executable with the reviewed npm tarball and pinned integrity before any
native lifecycle command runs.

Focused fixtures inject faults after every promotion payload/registry phase,
supersession archive/successor/registry phase, and seed-restore
payload/index phase, and require complete rollback before retry.

Run `make omx-artifacts-check` before committing lifecycle changes. Every
tracked or otherwise visible `.omx` file must resolve through the registry;
native OMX archives outside `accepted-bundles` remain ignored and unregistered.
