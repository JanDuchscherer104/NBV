---
kind: plan
status: current
supersedes: .omx/plans/measured-autoresearch-sidecar.md
---

# Performance-goal W&B bridge

`$performance-goal` owns evaluator contracts, checkpoints, and completion. A
version-one immutable evaluator `result.json` is validated and digested by the
package bridge, then checkpointed through OMX; W&B is an optional artifact and
metric mirror. The W&B Runs panel presents only explicitly namespaced bridge
runs and does not retrieve their histories.

This supersedes the standalone measured-autoresearch sidecar without importing
SENPAI's runtime control plane. The retained upstream-inspired mechanics are
the frozen contract, baseline/candidate provenance, immutable evidence, and
explicit keep/discard checkpoint.
