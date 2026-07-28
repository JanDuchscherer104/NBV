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

Every bundle contains six role families: context, specification, plan, test
specification, review, and execution handoff. Contract-v2 review evidence is a
closed JSON decision record with Architect and Critic approval; contract-v1
archives retain their accepted Markdown review. The handoff and owner-acceptance JSON must
carry the matching bundle and task identity. Extra specification ledgers are
allowed when registered individually. Exactly one JSON specification has role
`acceptance-record`; the bundle's `acceptance_sha256` must match its registered
SHA-256. A bundle-level `baseline_commit` must resolve to a Git commit that is an
ancestor of `HEAD`.

## Integrity And Transition

Registry membership, native paths, byte counts, SHA-256 hashes, baseline commit,
and accepted payload bytes are immutable. Artifact content provenance is its
native path, SHA-256, and byte count. Evidence ledgers may record historical
source commits as data, but lifecycle validity never depends on a branch-local
commit remaining reachable. Contract-v2 successors bind the immediate archived
predecessor through `predecessor_bundle_sha256` and bind the complete predecessor
chain through `predecessor_chain_sha256`. The chain receipt recursively covers
each accepted bundle's metadata and native artifact membership, including a
legacy contract-v1 prefix. Registry schema v2 requires a contract-v2 current
bundle, so successors cannot downgrade this chain. A current bundle may transition only
to `superseded`, with a current successor and complete byte-identical
privacy-safe archive. Accepted bytes are never edited in place; corrections
require a successor.

Every predecessor reference resolves to a same-task superseded bundle with a
reciprocal successor link and a non-decreasing contract version. Ordinary
HTTP(S) links remain allowed without URL masking; malformed, custom-scheme, or
punctuation-adjacent absolute-path forms fail closed. Privacy, credential,
runtime-identifier, and HTML checks inspect all decoded text.

The first registry merged onto a base without this registry is a reviewed
bootstrap, not a self-authenticating historical proof. Its merged Git tree is
the initial external trust root. Content receipts prove internal consistency of
the imported chain and become immutable transition evidence once that root is
present on the comparison base; they cannot authenticate a coordinated rewrite
of the bootstrap PR itself.

A behavioral rollback is also a successor transition: restore implementation
behavior separately, archive the current bundle, and register a new current
rollback successor. Never revert the registry to an earlier accepted state.

Every registered artifact, current or superseded, is checked against the
acceptance contract that applied when it was accepted. Contract v2 rejects
single-component absolute paths in addition to the contract-v1 privacy checks.
The validator rejects missing or unregistered tracked `.omx` files, path
escapes, duplicate ownership, hash drift, incomplete roles, invalid
transitions, plain or percent-encoded POSIX, Windows-drive, and UNC machine
paths, runtime IDs, credential-like content, generated HTML, and raw/private
path parts. Production validation compares the
current registry with its merge-base registry; absence of the registry at that
base is the valid PR1 bootstrap. An explicitly requested comparison ref fails
closed when it cannot be resolved.
Run:

```text
python3 scripts/scaffold/validate_omx_artifacts.py --check-tracked --previous-ref <merge-base>
python3 -m unittest scripts.tests.test_validate_omx_artifacts -v
```
