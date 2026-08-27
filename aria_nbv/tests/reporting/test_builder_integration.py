"""Tracer-bullet recipe spanning rollout and W&B evidence families."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

import aria_nbv.reporting.builder as builder_module
from aria_nbv.reporting import ScientificReportConfig, SourceIdentity
from aria_nbv.reporting._rollouts import _RolloutEvidence
from aria_nbv.reporting._wandb import _FrozenRun, _WandbEvidence


def test_one_toml_builds_both_source_families(monkeypatch, tmp_path: Path) -> None:
    recipe_path = tmp_path / "combined.toml"
    recipe_path.write_text(
        """\
schema_version = "aria-nbv-report-config-v1"
evidence_status = "pilot"

[sources.rollout]
store_paths = ["rollout.zarr"]

[sources.wandb]
entity = "entity"
project = "project"
run_ids = ["run-a"]
history_keys = ["trainer/global_step", "val/loss"]
history_mode = "sampled"

[[sections]]
kind = "rollout"
id = "rollout"
include_tables = ["facts"]
quantity_fact_key = "candidate_validity.fraction"
quantity_symbol_id = "rl.validity_mask"
figure_fact_keys = ["candidate_validity.valid", "candidate_validity.total"]

[[sections]]
kind = "wandb"
id = "training"
metric = "val/loss"
""",
        encoding="utf-8",
    )
    rollout_identity = SourceIdentity("rollout", "rollout", "a" * 64, (("store_count", 1),))
    rollout_evidence = _RolloutEvidence(
        identity=rollout_identity,
        frames={
            "facts": pd.DataFrame(
                [
                    {
                        "store_id": "store-a",
                        "key": "candidate_validity.fraction",
                        "value": 0.5,
                        "unit": "fraction",
                        "n": 2,
                        "aggregation": "fraction",
                        "status": "pilot",
                        "source": "manifest",
                    },
                    {
                        "store_id": "store-a",
                        "key": "candidate_validity.valid",
                        "value": 1,
                        "unit": "count",
                        "n": 2,
                        "aggregation": "count",
                        "status": "pilot",
                        "source": "manifest",
                    },
                    {
                        "store_id": "store-a",
                        "key": "candidate_validity.total",
                        "value": 2,
                        "unit": "count",
                        "n": 2,
                        "aggregation": "count",
                        "status": "pilot",
                        "source": "manifest",
                    },
                ]
            )
        },
    )
    wandb_identity = SourceIdentity(
        "wandb",
        "wandb",
        "b" * 64,
        (
            ("entity", "entity"),
            ("history_complete", False),
            ("history_mode", "sampled"),
            ("project", "project"),
            ("run_count", 1),
        ),
    )
    wandb_evidence = _WandbEvidence(
        identity=wandb_identity,
        runs=(
            _FrozenRun(
                id="run-a",
                name="run-a",
                state="finished",
                config=(),
                summary=(),
                history=pd.DataFrame(
                    [
                        {"trainer/global_step": 0, "val/loss": 1.0},
                        {"trainer/global_step": 1, "val/loss": 0.5},
                    ]
                ),
            ),
        ),
        history_mode="sampled",
    )
    monkeypatch.setattr(builder_module, "_acquire_rollout_evidence", lambda *args, **kwargs: rollout_evidence)
    monkeypatch.setattr(builder_module, "_acquire_wandb_evidence", lambda *args, **kwargs: wandb_evidence)

    recipe = ScientificReportConfig.from_toml(recipe_path)
    snapshot = recipe.setup_target(wandb_api=object(), root=Path(__file__).parents[3]).build()

    assert len(snapshot.source_identities) == 2
    assert len(snapshot.figures) == 2
    assert snapshot.tables
    assert snapshot.quantities
