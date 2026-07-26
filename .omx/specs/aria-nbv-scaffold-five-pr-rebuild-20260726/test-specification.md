# OMX artifact lifecycle test specification

## Required checks

1. A complete current bundle with all six role families validates.
2. Byte or SHA drift fails.
3. Absolute paths, runtime UUIDs, credential markers, private/raw path parts,
   and HTML fail in every registered artifact, current or superseded.
4. A missing family or incomplete Architect+Critic review fails.
5. Tracked `.omx` membership must equal registered artifact membership.
6. A current bundle may become superseded only with unchanged native membership,
   hashes, byte counts, and review roles, and only when it names a current
   successor for the same task.
7. Each bundle baseline is a Git commit and an ancestor of `HEAD`.
8. Exactly one JSON specification has role `acceptance-record`, and the bundle's
   `acceptance_sha256` exactly matches it.
9. The production memory gate compares against the merge-base registry, while a
   first registry on a base without that path is a valid bootstrap.

## Commands

```text
python3 scripts/scaffold/validate_omx_artifacts.py --check-tracked --previous-ref <merge-base>
python3 -m unittest scripts.tests.test_validate_omx_artifacts -v
git diff --check
```
