---
description: Apply the plan-grill skill — stress-test ambiguous high-impact decisions.
argument-hint: "<decision or scope question>"
---

Apply `.agents/skills/plan-grill/SKILL.md`. Before asking the user, resolve
discoverable facts from `.agents/references/source_order.md` and the owning
source for the decision.

For "$ARGUMENTS":

1. Search `.agents/resolved.toml` for prior decisions on this surface.
2. Ground in the source-order owner: exact code/tests, the active Typst thesis,
   the shared glossary, measured evidence, or the agents DB.
3. Ask one material decision at a time. State the recommended answer with the
   tradeoff. Test fuzzy plans against three concrete scenarios (normal,
   boundary, failure).
4. End with a decision-complete plan: goal/success criteria, in/out of scope,
   public surfaces affected, implementation packages, verification commands,
   assumptions and deferred decisions.

For advisor-facing claims, run `make kg-claim-check KG_CLAIM="..."` before
treating the claim as supported.
