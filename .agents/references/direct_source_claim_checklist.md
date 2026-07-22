# Direct-Source Claim Checklist

Use this checklist for advisor-facing proposal, roadmap, research-question, or
literature-synthesis claims. It is a review contract, not an automated claim
engine.

1. Resolve every citation key in `docs/references.bib`.
2. Inspect the authoritative local TeX section, local PDF page, or upstream
   primary source. Record the exact path plus line, section, or page locator.
3. Copy only the smallest supporting span into review evidence and calibrate
   the claim to what that span establishes. Reject universal, optimality, or
   implementation wording that the source does not support.
4. Check consistency with the curated literature page and current thesis owner
   named by `.agents/references/source_order.md`.
5. Render the touched Quarto or Typst surface and record the command, affected
   output path, and output digest.

Evidence records use the fixed schema exercised by
`scripts/tests/test_wp6_direct_source_claims.py`: claim id/text, citation key,
authoritative source path/digest, locator type/value, extracted support,
wording verdict, expected/actual reason, touched output paths, render command,
and render digest.
