# Target population and campaign admission inspection

## Requirements summary

Add read-only, plot-first statistical evidence for detected and GT target populations without changing VIN, campaign, or rollout persistence contracts.

- VIN root-store evidence owns complete detected/GT availability and geometry. The current deep scan reads only `gt.obbs` and returns counts (`aria_nbv/aria_nbv/dataset_bundle.py:284-359`).
- Campaign evidence owns observed-target matching and admission. The immutable audit already records reason, oriented IoU, match identity, and source-row identity (`aria_nbv/aria_nbv/oracle/pipelines/campaign.py:1137-1272`).
- Rollout evidence remains limited to admitted/persisted targets and downstream support (`aria_nbv/aria_nbv/rollouts/read_model.py:92-125`, `aria_nbv/aria_nbv/rollouts/inspection.py:3100-3132`).
- Same-class filtering precedes IoU, and admission remains exactly one qualifying GT with strict oriented IoU `> 0.20`; no classification-accuracy, mAP, precision, or recall claims (`aria_nbv/aria_nbv/oracle/target_selection.py:106-188`).
- Initial page rendering remains metadata-first. Deep target and admission reads require explicit user action.

## Scope

### Included

1. A typed VIN target-inventory projection for finite, non-padding detected and GT OBB rows.
2. Presentation-free campaign admission-audit validation and statistical summaries.
3. Training Dataset target-inventory plots and metrics.
4. Campaign Generation admission-outcome and IoU plots.
5. Deterministic JSON/CSV evidence under collapsed disclosures.

### Excluded

- VIN, rollout-Zarr, or campaign-plan schema changes.
- Re-running target matching, changing the IoU threshold, or changing admission.
- Generic inspection frameworks, services, polling, or new dependencies.
- Detector mAP/confusion matrices or other metrics requiring a global one-to-one assignment protocol.
- A new Rollout Supervision target dashboard; existing admitted-target diagnostics remain its owner.

## Interface decision

### Considered options

1. **Put all reducers in Streamlit.** Rejected: duplicates semantics, makes testing UI-bound, and violates package ownership.
2. **Deepen `dataset_bundle.py` into a universal target owner.** Rejected: it is a cross-store composer, while OBB decoding belongs to `data_handling.vin_store` and admission belongs to `oracle.pipelines`.
3. **Use two deep, presentation-free modules and thin page adapters.** Chosen:
   - `data_handling/vin_store/target_inventory.py` exposes one `inspect_target_inventory(root_store)` interface.
   - `oracle/pipelines/admission_evidence.py` exposes one `read_campaign_admission_evidence(path, target_inventory=...)` interface.
   - `dataset_bundle.py` composes the inventory result without owning OBB semantics.

## Implementation steps

### WP1 — VIN target inventory

- Add immutable row/summary DTOs in `aria_nbv/aria_nbv/data_handling/vin_store/target_inventory.py`.
- Read only manifest-declared `detected.obbs`, optional `detected.obb_probs`, `gt.obbs`, and semantic-name records.
- Reject malformed shapes; exclude padding/non-finite rows with explicit counts.
- Preserve per-sample, scene, split, source, semantic class, confidence, center, extents, diagonal, volume, and aspect-ratio evidence.
- Replace the legacy GT-only deep scan implementation with a compatibility-shaped projection from this owner in `dataset_bundle.py`.

### WP2 — Campaign admission evidence

- Add typed, fail-closed parsing in `aria_nbv/aria_nbv/oracle/pipelines/admission_evidence.py`.
- Validate supported immutable v1/v2 schemas, campaign/source identities, canonical audit hash, row types, IoU range, and admission/reason consistency so promoted diagnostic v1 evidence remains inspectable.
- Optionally join actor and GT class/geometry through stable `(sample_key, source_row)` identities from WP1.
- Return additive reason, IoU, scene, class, GT-coverage, and duplicate-match rows. Missing joins remain explicit; they never invent class or geometry.

### WP3 — Training Dataset presentation

- Keep the existing explicit `Deep statistics / target scan` action.
- Replace the raw target JSON default with metrics plus:
  - detected/GT rows per sample;
  - detected versus GT class support;
  - target geometry distributions.
- Keep exact rows and download evidence in a collapsed expander directly beneath the plots.
- Do not compute hidden-tab content or deep scans on initial load.

### WP4 — Campaign Generation presentation

- Add an explicit `Load admission audit` action bound to the immutable audit identity.
- Render admission/rejection metrics, reason waterfall, oriented-IoU ECDF with strict threshold, per-scene admission rates, and duplicate-GT support.
- State that `wrong_class` is a same-class availability failure, not classification accuracy.
- Keep raw audit rows and export collapsed beneath the plots.
- Preserve all generation, launch, status, and artifact behavior.

## Acceptance criteria

1. Target inventory returns deterministic rows for both detected and GT blocks and never interprets padding or non-finite rows as targets.
2. Missing detected or GT blocks are represented as unavailable source populations without falling back to raw snippets.
3. Every class and distribution aggregate retains sample/scene identity; UI shows population size and does not silently pool invalid rows.
4. Admission evidence rejects a changed audit hash, malformed IoU, inconsistent admitted/reason values, or unsupported schema.
5. Strict `IoU > 0.20` is presentation-only context; no matching behavior changes.
6. The broad audit's existing rows can produce reason and IoU summaries without a root join.
7. Training Dataset performs no target scan before the existing explicit deep-scan action.
8. Campaign Generation performs no admission-audit read before `Load admission audit`.
9. Plot tables are collapsed beneath the corresponding plot; default views are plot/metric-first.
10. No new dependency, service, compatibility alias, persistence schema, or rollout-generation change appears in the diff.

## Verification

- `uv run pytest -q tests/data_handling/test_target_inventory.py tests/test_dataset_bundle.py`
- `uv run pytest -q tests/oracle/test_admission_evidence.py tests/oracle/test_target_selection.py`
- `uv run pytest -q tests/app/panels/test_training_dataset_panel.py tests/app/panels/test_campaign_generation_panel.py`
- Combined focused suite over all six files.
- Ruff format/check on changed Python files.
- `python -m compileall` on changed package modules.
- `git diff --check` using the worktree's explicit git-dir/work-tree because its Git worktree flag is currently misconfigured.

## Risks and mitigations

- **Root scan cost:** explicit dispatch, manifest-bounded blocks, bounded cache identity, and no raw-snippet fallback.
- **Class-map gaps:** retain numeric semantic IDs and label unknown names explicitly.
- **Selection bias:** keep root availability, campaign admission, and rollout outcomes on their owning pages.
- **Misleading metrics:** label IoU as same-class association quality and avoid unsupported detector-accuracy claims.
- **Page clutter:** no more than two default plots per subsection; raw tables remain collapsed.

## Stop conditions

- Stop rather than infer when manifest/audit identities are inconsistent.
- Defer second-best-IoU margin until the persisted audit contains that fact.
- Defer cross-page selected-versus-available bias aggregation; it requires a separately designed bundle seam and is not needed for factual inventory/admission inspection.
