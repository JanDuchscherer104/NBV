# PR1 Ownership-Route Amendment

Predecessor plan native path:
`.omx/plans/prometheus-strict/aria-nbv-scaffold-five-pr-rebuild.md`.
The registry resolves that immutable predecessor from its accepted-bundle archive.
Baseline commit: `b8166fc8ab60c41d0f8a6eecfef8e4a2bf3b161c`.
Reviewed implementation head: `aa8e17fa3e98238d7e3730d934fc6bde263f3dc9`.

## Purpose

PR1 may close evidence-ownership and lifecycle trust-root defects discovered by
exact-head review. The exceptions below amend path ownership only for the named
hunks. They do not transfer later PR implementation responsibility.

## Exact Path And Hunk Exceptions

| Path or family | Baseline owner | PR1-only hunk | Deferred owner |
| --- | --- | --- | --- |
| `AGENTS.md`, `docs/AGENTS.md`, `CLAUDE.md` | PR3/PR5 | Remove live routes that rank or write retired state journals; point current thesis direction to the active Typst thesis. | PR3 routing compaction; PR5 final integration. |
| `.agents/AGENTS_INTERNAL_DB.md`, `.agents/issues.toml`, `.agents/todos.toml`, `.agents/refactors.toml` | PR1 normal findings | Remove active journal-owner references and classify `.agents/resolved.toml` as resolved history. | PR2 claim disposition; normal later findings. |
| `.agents/memory/README.md` | PR2 | Replace active write instructions with the temporary read-only migration boundary and route promotion to source-order owners. No claim migration or journal deletion. | PR2 claim-level disposition and final memory layout. |
| `.agents/memory/transcripts/{raw,user,distilled}` directories (22 tracked files deleted in this range) | PR2 | Delete the named checked-in transcript payloads strictly for PR1 public-tree privacy and runtime-evidence hygiene. This does not claim a Git-history purge and does not implement transcript completeness, retrieval, or promotion. | PR2 privacy/history decision, all-session completeness, retrieval evaluation, and owner-reviewed promotion. |
| `.agents/memory/history/2026/07/2026-07-26_omx_exact_head_review_blockers.md` | PR2 | Add one PR1 debrief as episodic review evidence only. It does not become current truth or alter the memory architecture. | PR2 claim disposition and memory evaluation. |
| `.agents/references/{source_order,agent_memory_templates,alignment_tools_contract,human_owner_intent,litkg_quick_reference,omx_artifact_policy,omx_quick_reference,operator_quick_reference,worktree_policy}.md` | mixed/shared | State the PR1 authority ladder, immutable accepted-bundle policy, retired-journal migration boundary, and exact-source fallback needed by the PR1 gate. | PR2 memory contract; PR3 routing; PR4 Graphify; PR5 reconciliation. |
| `.agents/references/mattpocock_skills_contract.md` | PR3 | Remove the retired journal from the Matt ADR-assumption mapping only. No pin, allowlist, closure, or routing-policy change. | PR3 Matt integration and evaluation. |
| `.agents/skills/**`, `.claude/agents/**`, `.claude/commands/**` | PR3 | Delete only live journal write/ranking routes. `measured-autoresearch/SKILL.md` receives only the scaffold-audit-required metadata floor; its body/helper/tests are unchanged. | PR3 skill compaction and routing evaluation. |
| `.agents/skills/semantic-scholar-litkg/SKILL.md` | PR3/PR5 | Make the uninitialized optional submodule a conditional deep source instead of an unconditional canonical source because the mandatory PR1 scaffold audit otherwise fails in the clean worktree. No toolkit behavior changes. | PR3 skill routing; PR5 LitKG retirement. |
| `.agents/skills/aria-nbv-context/{references/context_map.md,scripts/nbv_context_index.sh}` | PR3/PR4 | Remove retired journals from generated source lists; no context or Graphify redesign. | PR3 context routing; PR4 Graphify. |
| `Makefile:203` | PR2 | Change only `codex-transcripts` help text to match the extractor's read-only default and explicit ignored `--write` mode. Target name and command are unchanged. | PR2 transcript contract and evaluation. |
| `scripts/codex_transcript_extract.py` and its focused test | PR2 | Make default extraction read-only and emit owner-review candidates rather than writing journal truth. No claim promotion or MemPalace integration. | PR2 transcript completeness and promotion review. |
| `scripts/{new_debrief.py,quarto_generate_agent_docs.py,validate_agent_memory.py}` and focused tests | PR2/PR3/PR5 | Remove generated journal-owner routes and enforce fail-closed complete-record validation, including bare aliases, TOML values, and Typst expressions. | Later simplification after ownership is stable. |
| `.configs/litkg.toml` | PR4/PR5 | Remove retired journals from active authority/ingestion inputs, classify active TOMLs as backlog evidence, and isolate `.agents/resolved.toml` as resolved history. No Graphify or LitKG feature implementation. | PR4 graph integration; PR5 LitKG removal/reconciliation. |
| `scripts/kg/{auto_refresh.sh,ingest_docs.sh}` | PR4/PR5 | Remove retired-journal refresh and ingestion inputs without adding replacement watched or ingested sources. | PR4 graph/hook replacement; PR5 LitKG removal/reconciliation. |
| `scripts/git_hooks/post-commit` | PR4 | Stop dispatching retired state-journal refresh paths only; no new hook behavior. | PR4 hook replacement. |
| `.github/workflows/ci.yml` | PR1 | Run root CI on every PR/main push, check out the real PR head, and derive lifecycle history from `git merge-base HEAD BASE_TIP`. | Later edits require another ledger amendment. |
| `docs/contents/thesis/roadmap.qmd`, `docs/typst/thesis/sections/04-method/04-01-scene-representation-requirements.typ`, `docs/typst/thesis_slides/advisor_meeting_2026_05_22.typ` | PR5 | Remove only stale canonical-memory/journal/deck-self-owner claims exposed by the PR1 owner scan. No scientific claim or thesis architecture change. | PR5 selective documentation. |
| `.agents/memory/history/2026/06/2026-06-17_advisor_deck_source_of_truth_autoresearch.md` | PR2 exception already in plan | Correct only removed advisor-deck owner paths required by the root memory gate. | PR2 claim review. |
| accepted OMX registry, native artifacts, and immutable archive | PR1 | Harden contract-v2 history, exact-path, redaction, Git LFS, and pointer-only evidence validation; preserve predecessor bytes and carry the reproducible path, commit, and LOC ledgers forward unchanged. | Successor registration after approval. |

## Required Behavior

- Legacy state journals are read-only migration evidence, never active truth
  owners or write targets.
- Accepted OMX validation inspects the PR head's complete first-parent range from
  its merge base and cannot execute Git LFS filters or accept pointer-only
  evidence.
- Active owner scans recognize path aliases, semantic aliases, bare uppercase
  journal names, wrapped prose, complete TOML table records, and balanced Typst
  expressions. Capitalized anaphors remain bound to the legacy owner; Typst
  apostrophes do not split records; unrelated sentences do not share write
  routes.
- Direct writes require a legacy alias in the same clause. Anaphoric writes are
  limited to clause-initial `verb + it/them` forms with an earlier legacy
  antecedent. Explicit non-legacy post-mention writes remain valid.
- Root CI has no second path allowlist.
- Resolved agents-DB records remain historical evidence and are not scanned as
  active backlog ownership.

## Preserved Later Ownership

- PR2 retains claim-level journal salvage, MemPalace evaluation, transcript
  completeness, promotion review, and final journal disposition.
- PR3 retains skill compaction, Matt policy, routing evaluation, and runtime
  prompt accounting.
- PR4 retains Graphify 0.9.26, corpus/link extraction, and hook replacement.
- PR5 retains final integration, residual pruning, and selective documentation.

## Commit Boundaries

- `65d7bd70`: bounded lifecycle, registry, metadata, and active-owner review
  corrections preceding the final exact-head review series.
- `651462a7`: accepted-history first-parent and LFS hardening.
- `30c10566`: active legacy-state route retirement.
- `d2a052bc`: semantic-owner, resolved-history, and CI trigger corrections.
- `fda15afd`: alias-aware fail-closed owner validation.
- `7aaab997`: real PR-head checkout and active docs owner cleanup.
- `de48c553`: merge-base derivation, complete TOML/Typst record validation, bare
  alias coverage, and final advisor-deck owner demotion.
- `65569d98`: subject-aware owner classification, short-path and write-verb
  regressions, scientific `canonical state` restoration, and removal of newly
  added hook/LitKG replacement behavior.
- `f1dd9367`: case-normalized anaphoric owner detection and capitalized-anaphor
  regressions.
- `d276dea0`: table-level TOML records, Typst apostrophe handling,
  sentence-bounded write routes, and exact Markdown/TOML/Typst owner probes.
- `6233801b`: separate declarative ownership from direct and anaphoric write
  routes; add cross-format sentence-boundary regressions.
- `aa8e17fa`: restrict anaphoric writes to clause-initial `verb + it/them`
  forms and preserve explicit non-legacy post-mention writes.

## Verification Disposition

- 47 accepted-OMX lifecycle tests pass.
- 80 owner/memory tests and 9 transcript-extractor tests pass.
- Exact `b8166fc8..aa8e17fa` registry history validation passes.
- `make check-agent-memory`, agents-DB validation/render, scaffold audit
  (0 errors, 20 warnings), and scaffold self-test (13/13) pass.
- Ruff format/check, MyPy, Python compilation, advisor-deck Typst compilation,
  and `git diff --check` pass.
- `CUDA_VISIBLE_DEVICES='' make ci PYTEST_ARGS=` passes: 99 package tests and all
  33 Quarto pages. This is the hosted-equivalent CPU contract.
- An unhidden local CUDA run is baseline-incompatible because the workstation
  exposes CUDA while its PyTorch3D extension is CPU-only; the same CPU backend
  test exists at `b8166fc8`.
- Full thesis compilation remains blocked by the pre-existing undefined
  `leftarrow` at `04-05-finite-candidate-value-model.typ:92`; the same source is
  present at `b8166fc8`. The touched advisor deck compiles independently.

## Acceptance Gate

Fresh independent Architect `CLEAR` and Critic `APPROVE` verdicts covered exact
head `aa8e17fa3e98238d7e3730d934fc6bde263f3dc9` and this amendment before
registration. After registration, fresh exact-final-HEAD code review and
architecture clearance remain required.

## Non-Goals

No claim-level journal migration, MemPalace integration, skill consolidation,
Graphify implementation, hook replacement, domain-truth rewrite, broad docs
rewrite, or public history purge is authorized by this amendment.
