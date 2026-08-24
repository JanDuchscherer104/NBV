# SENPAI Selective Adoption And Upstream Updates

This is a reference-only adoption of [W&B SENPAI](https://github.com/wandb/senpai),
pinned to upstream commit `772acc597f29065ccad012c749334a287d89badd` on
2026-08-24. It does not vendor SENPAI, install its runtime, create a GitHub
agent identity, or authorize Kubernetes, credentials, branches, pull requests,
or W&B writes.

## Retained Mechanics

- Write one concise mission contract before an empirical loop: target metric and
  direction, data/split identity, allowed edits, baseline, budget, stopping
  rule, and required evidence.
- Bind each candidate to an exact baseline revision and immutable result
  identity. Changed evidence requires a new candidate revision; do not rewrite
  a published result.
- Treat a supervised evaluator as event-driven: report bounded status, timeout,
  threshold/regression, stale evidence, or terminal state without repeated
  model polling.
- Promote a winner only after confirmation appropriate to the declared noise
  model, then simplify it into the next baseline. Preserve useful negative
  results and stop work that cannot change the next portfolio decision.

The nearest ARIA evaluator, configuration, artifact, and test owners retain
their existing authority. OMX remains the lifecycle owner; W&B is optional
observability and never an admission or promotion authority.

## Deliberately Excluded

SENPAI's Kubernetes runner, OpenHands runtime, GitHub issue/PR coordination,
target-repository write token, persistent advisor/student processes, and direct
W&B/Weave control plane are not part of ARIA by this reference. They require a
separate pilot with explicit external-action authority and infrastructure
review.

## Standard Upstream Update Route

Every external scaffold adoption must name an immutable upstream revision and a
repeatable update command. For this reference, run:

```bash
git ls-remote https://github.com/wandb/senpai.git HEAD
```

If the returned OID differs from the pin, review the upstream compare view:

```text
https://github.com/wandb/senpai/compare/772acc597f29065ccad012c749334a287d89badd...<new-oid>
```

Then update this pin and only the adopted local mechanics, preserving the
excluded-runtime boundary. Validate every changed ARIA owner and
`make check-agent-memory`; a new upstream commit never changes ARIA behavior
without that scoped review and proof.
