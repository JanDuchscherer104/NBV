# VIN

`aria_nbv.vin` owns scorer architecture, model objectives, and tensorized model inputs. This pass moves CORAL model/loss/decoding primitives here without changing their implementation.

Baseline: `6b72b62639e24fc13bba845ec63bc8fc72c77aae`

Inventory generated: `2026-07-10T15:58:15.078783+00:00`

## Current And Target Layout

```text
vin/
  ordinal.py           # moved from rri_metrics/coral.py
  candidate_scorer.py  # unchanged
  scorer_context.py    # unchanged
  ...                  # existing subpackages are outside this mechanical pass
```

## Symbol Ownership Matrix

### `candidate_scorer.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `CandidateScorer` | `class` | `public` | `vin.candidate_scorer` | `vin.candidate_scorer` | `vin.candidate_scorer` | `already aligned` |
| `CandidateScorerPrediction` | `class` | `public` | `vin.candidate_scorer` | `vin.candidate_scorer` | `vin.candidate_scorer` | `already aligned` |
| `CandidateScorerConfig` | `type alias` | `public` | `vin.candidate_scorer` | `vin.candidate_scorer` | `vin.candidate_scorer` | `already aligned` |
| `CandidateScorerTrainingContract` | `type alias` | `public` | `vin.candidate_scorer` | `vin.candidate_scorer` | `vin.candidate_scorer` | `already aligned` |
| `candidate_scorer_training_contract` | `function` | `public` | `vin.candidate_scorer` | `vin.candidate_scorer` | `vin.candidate_scorer` | `already aligned` |

### `ordinal.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `coral_loss` | `function` | `public` | `rri_metrics.coral` | `vin.ordinal` | `vin.ordinal` | `moved` |
| `coral_logits_to_prob` | `function` | `public` | `rri_metrics.coral` | `vin.ordinal` | `vin.ordinal` | `moved` |
| `coral_random_loss` | `function` | `public` | `rri_metrics.coral` | `vin.ordinal` | `vin.ordinal` | `moved` |
| `_softplus_inverse` | `function` | `private` | `rri_metrics.coral` | `vin.ordinal` | `vin.ordinal` | `moved` |
| `MonotoneBinValues` | `class` | `public` | `rri_metrics.coral` | `vin.ordinal` | `vin.ordinal` | `moved` |
| `coral_expected_from_logits` | `function` | `public` | `rri_metrics.coral` | `vin.ordinal` | `vin.ordinal` | `moved` |
| `coral_logits_to_label` | `function` | `public` | `rri_metrics.coral` | `vin.ordinal` | `vin.ordinal` | `moved` |
| `coral_monotonicity_violation_rate` | `function` | `public` | `rri_metrics.coral` | `vin.ordinal` | `vin.ordinal` | `moved` |
| `CoralLayer` | `class` | `public` | `rri_metrics.coral` | `vin.ordinal` | `vin.ordinal` | `moved` |

### `scorer_context.py`

| Symbol | Kind | Visibility | Before module | Mechanical module | Final owner | Status |
|---|---|---|---|---|---|---|
| `build_vin_scorer_scene_field` | `function` | `public` | `vin.scorer_context` | `vin.scorer_context` | `vin.scorer_context` | `already aligned` |
| `apply_vin_scorer_film` | `function` | `public` | `vin.scorer_context` | `vin.scorer_context` | `vin.scorer_context` | `already aligned` |
| `_snippet_trajectory_world_rig` | `function` | `private` | `vin.scorer_context` | `vin.scorer_context` | `vin.scorer_context` | `already aligned` |
| `encode_trajectory_context` | `function` | `public` | `vin.scorer_context` | `vin.scorer_context` | `vin.scorer_context` | `already aligned` |
| `encode_pose_features` | `function` | `public` | `vin.scorer_context` | `vin.scorer_context` | `vin.scorer_context` | `already aligned` |
| `compute_global_context` | `function` | `public` | `vin.scorer_context` | `vin.scorer_context` | `vin.scorer_context` | `already aligned` |
