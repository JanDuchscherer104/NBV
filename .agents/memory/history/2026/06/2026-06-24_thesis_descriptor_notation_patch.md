---
id: 2026-06-24_thesis_descriptor_notation_patch
date: 2026-06-24
title: "Thesis descriptor notation patch"
status: done
topics: [thesis, typst, notation, descriptors, q_h, geometry]
confidence: high
canonical_updates_needed: []
---

## Task
Patch the thesis method descriptor narrative and shared notation so ARIA-NBV's
planned `Q_H` inputs use coherent actor-visible target, scene, candidate,
relation, history, validity, and provenance descriptors with local/relative
spatial geometry.

## Method
Inspected shared symbols/equations, `docs/notation.yml`, the current method
sections, and the local QCNet paper text for query-centric relative descriptor
discipline. Patched shared Typst notation first, regenerated generated notation,
then updated the method prose to invoke shared equations instead of redefining
descriptor math inside section files.

## Findings
Added reference-pose notation `r_t` and reference-relative candidate transform
`T_{r_t,i}^{rel}` in `docs/typst/shared/symbols/spatial.typ`,
`docs/typst/shared/equations/spatial.typ`, and `docs/notation.yml`. Replaced the
ambiguous candidate self descriptor with explicit reference-frame translation,
continuous 6D relative rotation, range, azimuth, height/up/frustum scalars, and
optional LFF controls. Kept the duplicated `features` namespace synchronized for
legacy/advisor references.

Updated `docs/typst/thesis/sections/04-method/04-02-descriptor-and-encoding-plan.typ`
so it now defines the model I/O descriptor protocol rather than replay schema or
architecture details. The section introduces target, scene, candidate, relation,
history, validity, and provenance tensors; cites EFM3D/EVL and QCNet-style
query-local relative positional encoding where relevant; and explicitly forbids
GT meshes, GT crops, oracle returns, all-candidate oracle renders, and fresh
counterfactual RGB/DINO/EVL features as actor inputs. Updated
`docs/typst/thesis/sections/04-method/04-04-architecture-contract.typ` to
reference the shared symbols instead of inline ad hoc pose notation.

## Verification
Passed `make glossary`, which validated 56 glossary terms, 64 symbols, and 58
equations. Passed `cd docs && typst compile typst/thesis/main.typ
/tmp/aria-thesis-descriptor-notation.pdf --root . --input aria-wip-links=false`.
Passed `git diff --check`. Ran `pdftotext` audit for descriptor headings,
reference transforms, candidate self descriptors, candidate-target relations,
and missing references; no missing-reference markers were found. Rendered and
visually inspected pages 59-63 of `/tmp/aria-thesis-descriptor-notation.pdf`.

The detailed KG claim check for the full descriptor policy returned
`unverifiable` because the current KG did not expose source paths for the
required literature-backed descriptor claim. Follow-up `make kg-search` and
repo-local `rg` checks found no contradictions and did find supporting thesis,
roadmap, and theory surfaces.

## Canonical State Impact
None. This was a thesis/notation patch plus generated notation refresh; no
canonical `.agents/memory/state/*.md` update was required.
