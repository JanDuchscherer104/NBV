# Section contract

Use this scratch contract before accepting a non-trivial section or paragraph.

```yaml
section: <exact destination>
question: <reader-facing question>
claims:
  - id: <stable local identity>
    scope: <what the claim covers>
    evidence: <exact owner and locator>
    limitation: <boundary or missing evidence>
    status: draft | accepted | review-needed
handoff: typst-authoring | scientific-review
```

Keep the contract beside the drafting task unless a repository owner explicitly
requires durable metadata. It records identities and boundaries, not copied
claim prose, metrics, excerpts, or scientific verdicts.
