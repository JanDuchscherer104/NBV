---
id: 2026-08-27_candidate_generation_scale_up_pilot
date: 2026-08-27
title: "Candidate generation scale-up pilot"
status: done
topics: [candidate-generation, rollouts, autoresearch, cuda, data-quality]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - docs/contents/evidence/candidate_generation_scaleup_pilot.qmd
  - docs/contents/evidence/candidate_generation_scaleup_pilot/
  - scripts/render_candidate_generation_scaleup_pilot.py
codex_thread: codex://threads/01a033a6-100a-73d2-83bb-4a4153903cc4
repo_object_format: sha1
repo_head: b79c865ae86901443e8a846b992b5c018f1f75c1
repo_branch: "codex/candidate-family-experiments"
worktree_kind: linked
---

## Task
Evaluate remaining candidate-generation scale blockers with a matched CUDA pilot,
inspect realism and training-signal proxies, and publish only measured positive
or negative evidence without changing the production mixture.

## Method
Froze two reviewed real-data rows, seed `20260728`, 60 candidates per row, the
V0/GT target-RRI evaluator, and the RTX 3080 Ti device. Compared the production
`realistic_core` mixture with `forward_target_glance` and `radius_stratified`,
then rendered deterministic public SVG and JSON evidence from the persisted
candidate audit rows.

## Findings
The production reference yielded 74/120 hard-valid candidates but still had one
zero-valid family/state cell. Both challengers were tied on mean best
target-root gain within the frozen tolerance, yet each increased zero-valid
family/state cells from one to two and was discarded. The result keeps the
scale decision at NO-GO and prioritizes family-aware bounded refill before new
families. The public report and exact limitations live in
`docs/contents/evidence/candidate_generation_scaleup_pilot.qmd`; its generated
evidence bundle is reproducible with
`scripts/render_candidate_generation_scaleup_pilot.py`.

## Commits
- [b79c865ae86901443e8a846b992b5c018f1f75c1](https://github.com/JanDuchscherer104/ARIA-NBV/commit/b79c865ae86901443e8a846b992b5c018f1f75c1)

## Verification
- Deterministic regeneration: two independent renders matched each other and
  the committed evidence bundle byte-for-byte.
- `ruff check scripts/render_candidate_generation_scaleup_pilot.py`: passed.
- `python3 scripts/validate_qmd_frontmatter.py docs/contents`: passed.
- `quarto render docs/contents/evidence/candidate_generation_scaleup_pilot.qmd --no-execute`:
  passed.
- Frozen critic suite: 48 passed, 1 real-data skip.
- Large-scale rollout generation remains blocked by family support collapse;
  this is a measured NO-GO, not a completion claim for the scale gate.

## Canonical Owner Impact
The public evidence page now owns this bounded two-scene pilot result. Production
candidate configuration and generation behavior were deliberately unchanged;
the diagnostic schema remains owned by the parent PR branch.
