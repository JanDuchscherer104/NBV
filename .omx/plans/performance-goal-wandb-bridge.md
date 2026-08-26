---
kind: plan
status: current
supersedes: .omx/plans/measured-autoresearch-sidecar.md
---

# Performance-goal W&B bridge

`$performance-goal` owns evaluator contracts, checkpoints, and completion. A
version-two immutable evaluator `result.json` binds each candidate to its
hypothesis, research brief, assignment, sources, and revisions. The bridge
keeps OMX blocked until mandatory W&B publication and read-back succeed, then
records the evaluator verdict. The W&B Runs panel presents only explicitly
namespaced bridge runs and does not retrieve their histories.

This supersedes the standalone measured-autoresearch sidecar without importing
SENPAI's runtime control plane. The retained mechanics are the Professor,
Researcher, Implementer, Critic, and Verifier lanes; local-first source
consolidation; frozen contracts; immutable candidate evidence; revision; and
confirmed-winner promotion.
