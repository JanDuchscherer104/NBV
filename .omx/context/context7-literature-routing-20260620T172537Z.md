# Context Snapshot: Context7 And Literature Routing Alignment

## Task Statement

Plan improvements for ARIA-NBV agent scaffold routing so domain skills link more often and more precisely to local Context7 library identifiers, the paper manifest in `docs/literature/sources.jsonl`, Quarto literature reviews, thesis and seminar Typst sections, BibTeX keys from `docs/references.bib`, and local LaTeX source mirrors under `docs/literature/tex-src/`.

The user requested `$ralplan`, so this is a planning-only consensus pass. No source or scaffold implementation edits should happen in this lane.

## Desired Outcome

Produce an implementation-ready, review-gated plan that increases horizontal linking across skills, docs, code, MCP tools, Context7 libraries, and local literature without creating another source of truth.

## Known Facts And Evidence

- `docs/literature/sources.jsonl` has 43 manifest entries.
- `docs/references.bib` has 896 lines of bibliography entries.
- `docs/contents/literature/` contains local Quarto review pages for ARIA, EFM3D, VIN-NBV, RL planning, GenNBV, Hestia, SceneScript, PB-NBV, SCONE/FisherRF, and active 3DGS NBV.
- `docs/contents/literature/index.qmd:79-82` points to `docs/literature/sources.jsonl` and `docs/literature/tex-src/` as local source mirrors.
- `docs/typst/thesis/main.typ` includes active thesis sections under `docs/typst/thesis/sections/`.
- `.agents/references/source_order.md:15-18` says active thesis Typst prose is the owner for thesis-facing prose once thesis work is in scope.
- `.agents/references/alignment_tools_contract.md:7-11` says optional tools produce evidence and proposals, not durable truth.
- `aria_nbv/AGENTS.md:19-26` and `.agents/references/python_conventions.md:1-15` are the local Python/package standards references.
- Context7 resolved seed library IDs during this planning pass, but those are observations, not owner updates. Implementation must reconcile planning observations such as `/pytorch/pytorch`, `/streamlit/docs`, and `/websites/gymnasium_farama` against `.agents/references/context7_library_ids.md` before metadata edits.
- Context7 did not return a relevant `coral-pytorch` match; use `docs/references.bib` entry `coral-pytorch-2025` and package docs/url there instead of guessing a Context7 ID.

## Constraints

- Skills must not restate formulas, literature claims, or planned thesis detail.
- Durable scientific claims belong in active thesis sections or Quarto literature pages; skills should only route to them.
- Context7 is an evidence lookup surface for external library/API behavior, not a project source of truth.
- Literature citations should use existing BibTeX keys and local section/file anchors where possible.
- The repo worktree is dirty; any future implementation must start with `git status --short -- .agents scripts docs Makefile`, declare its touch set, and preserve unrelated user/agent changes.

## Likely Touchpoints For Implementation

- `.agents/references/context7_library_ids.md` (single Context7 owner)
- `.agents/skills/aria-nbv-context/references/context_map.md` (authored literature route discovery)
- `.agents/skills/plan-grill/SKILL.md`
- selected domain skill metadata
- `scripts/scaffold_audit.py`
- `scripts/nbv_literature_index.sh` only if generated literature output needs derived route support
- `.agents/references/scaffold_routing_fixtures.json`
- `.agents/references/source_order.md`
- `.agents/references/alignment_tools_contract.md`
