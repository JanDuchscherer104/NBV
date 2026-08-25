---
id: 2026-08-25_hm_primuss_release_gate
date: 2026-08-25
title: "HM PRIMUSS release gate"
status: done
topics: [thesis, hm, primuss, release]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - docs/typst/thesis/development/roadmap.typ
codex_thread: codex://threads/01a03839-e87c-7160-a79d-7cc1e8c6d588
repo_object_format: sha1
repo_head: 4c644d057f5ab628b76785f9cfdc1f1838e502c4
repo_branch: "codex/hm-primuss-release-gate"
worktree_kind: linked
---

## Task
Add current HM/FK07 and authenticated PRIMUSS checks to the existing M8 release-freeze owner.

## Method
Validated the current ASPO, Master Informatik SPO, FK07 thesis page, and PRIMUSS registration/submission guides, then deepened the existing development-only M8/freeze gate without creating a second checklist or executable submission oracle.

## Findings
`docs/typst/thesis/development/roadmap.typ` now records the applicable-SPO, registration, pre-submission readiness, conditional-copy, and final-PDF human checks. The September M8 freeze uses the exact PDF prepared for PRIMUSS upload and authenticated registration records; the later submission closure alone requires the authenticated timestamp and exact submitted PDF. Upload, local builds, PDF digests, and repository fields remain explicitly insufficient to prove submission; signature and attachment requirements remain conditional on authenticated records.

## Commits
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/4c644d057f5ab628b76785f9cfdc1f1838e502c4
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/1d8fbee71810a23f82c4641b3855ca1460371012

## Verification
- `make thesis-pdf-ci typst-authoring-contract PYTHON_INTERPRETER=/home/jd/repos/ARIA-NBV/aria_nbv/.venv/bin/python CI_RENDER_DIR=/tmp/aria-hm-release-render-v2` — passed.
- Extracted and visually inspected development roadmap pages 85–86; no overflow or clipping.
- Independent review of revised staged diff `f712a7a7b5ea328c4b06006bad8e601f1f7cb70b4929bfdcf039e12b750f1ca1` — approved after making signature requirements conditional.
- Independent review of freeze/submission repair `4406510f485fe4d90513037df521f4c0175a726b4ddcf1e4131a759e677d7364` — approved with no findings after separating the pre-submission upload PDF from the post-submission receipt and archived submitted PDF.
- `git diff --check` — passed.

## Canonical Owner Impact
Updated only the existing M8/freeze readiness owner. The roadmap remains development-only and makes no authenticated submission claim.
