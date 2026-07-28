# OMX artifact lifecycle test specification

## Required checks

1. A complete current bundle with all six role families validates.
2. Byte or SHA drift fails.
3. Contract-v2 evidence rejects plain, percent-encoded, and repeatedly encoded
   POSIX, Windows-drive, and UNC absolute paths, runtime UUIDs, credential
   markers, private and raw path parts, HTML, malformed HTTP(S), and unsupported URI
   schemes. Contract-v1 archives retain the complete HEAD-era scanner: its
   original POSIX/backslash-drive, bounded UUID/credential, private-path, and
   HTML checks, with no repeated decoding or new URI, file-URI, forward-drive, or UNC
   checks. Plain HTTP(S), source locators, and relative glob syntax remain valid.
4. A missing family, incomplete Architect+Critic review, non-approved or
   duplicate structured review decision, or malformed owner-acceptance/handoff
   semantics fails for current and superseded bundles. Contract v2 uses a
   closed JSON review record; legacy Markdown is read only for contract v1.
5. Tracked `.omx` membership must equal registered artifact membership.
6. A current bundle may become superseded only with unchanged native membership,
   hashes, byte counts, and review roles, and only when it names a current
   successor for the same task.
7. Each bundle baseline is a Git commit and an ancestor of `HEAD`.
8. Exactly one JSON specification has role `acceptance-record`, and the bundle's
   `acceptance_sha256` exactly matches it. Acceptance and handoff JSON identities
   and approval semantics match the registry's bundle ID and task.
9. The production memory gate compares against the merge-base registry, while a
   first registry on a base without that path is a valid bootstrap.
10. A contract-v2 successor names the predecessor bundle and binds its accepted
    metadata and native artifact membership through immediate and recursively
    transitive SHA-256 receipts. Validation covers the deployed v1 to v1 to v2
    migration shape and remains internally consistent after squash-like history
    rewriting. The first merged registry is the external trust root; later
    transitions reject dangling or non-reciprocal predecessor links, contract
    downgrade, incomplete historical bundles, transitive chain mutation, or
    receipt drift against that root.
11. Explicit transition refs fail closed when unresolved. Local snapshot-only
    fallback is permitted only when no explicit ref was requested.
12. The LOC manifest owns its selection rules and sorted rows. The test reads
    those rules and regenerates all rows and summaries from baseline Git blobs.
    Path and commit inventories validate exact headers, row counts, unique
    sources, Git-derived subjects and path states, closed vocabularies, and
    non-empty decision fields. `target_pr`, `disposition`, `owner`, `reason`,
    `verification`, and commit-level `final_state` remain reviewed planning
    judgments rather than Git-derived facts.
13. Hosted lifecycle CI checks out complete history and triggers on accepted
    OMX, registry, validator, test, ignore-policy, and workflow changes.

## Commands

```text
python3 scripts/scaffold/validate_omx_artifacts.py --check-tracked --previous-ref {merge-base}
python3 -m unittest scripts.tests.test_validate_omx_artifacts -v
git rev-list --first-parent --reverse b8166fc8ab60c41d0f8a6eecfef8e4a2bf3b161c..5bc48d461eb6679a28d45fc0f2bf7fc6a1222121
git log --first-parent --format= --name-only b8166fc8ab60c41d0f8a6eecfef8e4a2bf3b161c..5bc48d461eb6679a28d45fc0f2bf7fc6a1222121
git diff --name-only b8166fc8ab60c41d0f8a6eecfef8e4a2bf3b161c..5bc48d461eb6679a28d45fc0f2bf7fc6a1222121
git diff --check
```
