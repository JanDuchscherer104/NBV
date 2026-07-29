# Scaffold Review Board

The scaffold review board is a private decision aid, not a new truth store.
It gives the human owner a simple `yes` / `no` / revised-statement workflow
over reconciled intent clusters, selected OMX goals, active Agents DB records,
the current scaffold map, and live PR metadata.

## Ownership

- Exact code, tests, thesis sources, and primary evidence remain authoritative.
- `.agents/references/human_owner_intent.md` owns accepted current human intent.
- `.agents/{issues,todos,refactors}.toml` own actionable work.
- OMX artifacts remain planning evidence.
- Private transcript evidence and generated review bundles stay under
  `.artifacts/` and remain untracked.
- Graphify may index this orientation page and the canonical owners it links;
  it must not ingest private decisions or raw transcript material.
- MemPalace may assist recall over private evidence but does not establish
  acceptance or truth.

## Build

```bash
python3 scripts/scaffold_review.py build \
  --corpus <private-corpus>/review/clusters.jsonl \
  --items <private-owner-findings.jsonl> \
  --omx <selected-plan.md>
```

The command writes a self-contained `index.html`, a local Quarto wrapper, and a
source manifest under `.artifacts/scaffold-review/`. Open the HTML directly.
Decisions remain in browser local storage until exported as JSON.
The manifest records the exact corpus SHA-256 used to build the board.
The optional `--items` input contains explicit owner-authored findings; live PR
metadata contributes observations only. Repo-local output is restricted to the
ignored `.artifacts/` directory.

```bash
python3 scripts/scaffold_review.py summarize scaffold-decisions-<digest>.json
```

Exported decisions are review evidence. Promote accepted intent or actionable
work deliberately through their existing owners; the board never writes those
owners itself.

## Interface

The module has two commands:

- `build`: read existing owner surfaces and produce one private review bundle.
- `summarize`: render an exported decision file for deliberate promotion.

The deletion test is explicit: removing this module removes only the review
convenience. It does not remove or relocate project truth.
