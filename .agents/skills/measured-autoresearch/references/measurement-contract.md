# Measurement Contract

Resolve the mission exactly as named by the active OMX handoff or goal. The
contract records evaluator command and fingerprint, data/split identity, hard
gates, primary metric and tolerance, ordered secondary metrics, mutable paths,
budget, device, seed, outputs, and safe rollback method.

Initialize with:

```bash
python3 <skill>/scripts/experiment.py init --mission-root <mission> --contract <contract.json>
```

Capture `git status --short` and SHA-256 or `MISSING` for every mutable path in
`measurements/ownership.json`. Baseline iteration is zero. Each candidate run
contains evaluator output, logs, an inspectable sample when applicable,
`candidate.patch`, the ownership snapshot, and `artifact-manifest.json`.

Append only through:

```bash
python3 <skill>/scripts/experiment.py append --mission-root <mission> --result <result.json>
```

The helper rejects stale contracts, malformed metrics, missing gates, invalid
artifact paths, non-monotonic iterations, and decisions inconsistent with the
frozen tolerance. A discarded candidate includes `restore-proof.json` showing
matching before/after status and hashes for every mutable path; a retained
candidate records its revision.

Finish the sidecar pass with:

```bash
python3 <skill>/scripts/experiment.py validate --mission-root <mission>
python3 <skill>/scripts/experiment.py report --mission-root <mission>
```

If `summary.json` reports a plateau, search local code and literature owners
before external primary sources. Record any derived mechanism and falsifiable
hypothesis in `measurements/inspiration.jsonl`; research never changes the
frozen evaluator or counts as an experiment row.
