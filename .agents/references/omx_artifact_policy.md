# OMX Artifact Retention

OMX drafts, goals, runtime state, logs, raw sessions, generated reports, and
machine-local metadata are ignored. Accepted evidence is tracked only when it is
listed in `.agents/omx_artifacts.toml` and passes the focused validator.

## Placement

- A `current` accepted bundle stays at native role paths under `.omx/context`,
  `.omx/specs`, and `.omx/plans`.
- A privacy-safe `superseded` accepted bundle moves byte-identically to
  `.omx/archive/accepted-bundles/<bundle-id>/`, preserving its path relative to
  `.omx` and recording the native path in the registry.
- `.omx/accepted` is not a valid path.

Each current bundle contains six role families: context, specification, plan,
test specification, review, and execution handoff. Review evidence must cover
both Architect and Critic approval. Extra specification ledgers are allowed when
registered individually. Exactly one JSON specification has role
`acceptance-record`; the bundle's `acceptance_sha256` must match its registered
SHA-256. A bundle-level `baseline_commit` must resolve to a Git commit that is an
ancestor of `HEAD`.

## Integrity And Transition

Registry paths, membership, byte counts, SHA-256 hashes, baseline commit, and
accepted payload bytes are immutable. Artifact content provenance is its native
path, SHA-256, and byte count. Evidence ledgers may record historical source
commits as data. A current bundle may transition only to `superseded`, with a
current successor and complete byte-identical privacy-safe archive. Accepted
bytes are never edited in place; corrections require a successor.

Every registered artifact, current or superseded, is scanned. The validator
rejects missing or unregistered tracked `.omx` files, path escapes, duplicate
ownership, hash drift, incomplete roles, invalid transitions, machine-local
paths, runtime IDs, credential-like content, generated HTML, and raw/private
path parts. Production validation compares the current registry with its merge-
base registry; absence of the registry at that base is the valid PR1 bootstrap.
Run:

```text
python3 scripts/scaffold/validate_omx_artifacts.py --check-tracked --previous-ref <merge-base>
python3 -m unittest scripts.tests.test_validate_omx_artifacts -v
```
