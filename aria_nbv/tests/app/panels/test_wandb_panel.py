"""Tests for W&B comparison helpers."""

# ruff: noqa: S101, D103, SLF001, PLR2004

import numpy as np
import pandas as pd

from aria_nbv.utils import wandb_utils


class _DummyRun:
    def __init__(self, **kwargs: object) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_flatten_mapping_skips_private_and_normalizes() -> None:
    config = {
        "_private": 1,
        "model": {"lr": 1e-3, "layers": [1, 2], "flags": {"use": True}},
        "name": "run-a",
    }
    flat = wandb_utils._flatten_mapping(config)
    assert "_private" not in flat
    assert flat["model.lr"] == 1e-3
    assert flat["model.layers"] == "1, 2"
    assert flat["model.flags.use"] is True
    assert flat["name"] == "run-a"


def test_summarize_metric_linear_trend() -> None:
    df = pd.DataFrame({"step": np.arange(10), "train/loss": np.arange(10) * 2.0})
    summary = wandb_utils._summarize_metric(
        df,
        metric_key="train/loss",
        x_key="step",
        segment_frac=0.2,
    )
    assert summary["last"] == 18.0
    assert np.isclose(summary["slope_late"], 2.0)


def test_summarize_gap_tracks_last_value() -> None:
    df = pd.DataFrame(
        {
            "step": np.arange(5),
            "train/loss": [1.0, 2.0, 3.0, 4.0, 5.0],
            "val/loss": [1.0, 1.5, 2.5, 3.5, 4.0],
        },
    )
    summary = wandb_utils._summarize_gap(
        df,
        x_key="step",
        train_key="train/loss",
        val_key="val/loss",
    )
    assert summary["gap_last"] == 1.0


def test_extract_run_steps_prefers_summary_keys() -> None:
    run = _DummyRun(summary={"global_step": 123, "_step": 999})
    steps = wandb_utils._extract_run_steps(run)
    assert steps == 123.0


def test_filter_runs_by_steps() -> None:
    runs = [
        _DummyRun(id="a", name="run-a", state="finished", summary={"global_step": 50}),
        _DummyRun(id="b", name="run-b", state="finished", summary={"global_step": 200}),
        _DummyRun(id="c", name="run-c", state="finished", summary={}),
    ]
    filtered = wandb_utils._filter_runs(
        runs,
        name_regex=None,
        states=["finished"],
        tags=set(),
        group="",
        job_type="",
        min_steps=100.0,
        max_steps=None,
    )
    assert [run.id for run in filtered] == ["b"]


def test_build_autoresearch_run_dataframe_uses_explicit_config_namespace() -> None:
    runs = [
        _DummyRun(
            id="result-run",
            name="evaluator",
            state="finished",
            config={
                "aria_autoresearch": {
                    "goal_slug": "latency",
                    "iteration": 3,
                    "checkpoint_status": "pass",
                    "hypothesis": "Cache the resolved command graph.",
                    "candidate_revision": "candidate",
                    "baseline_revision": "baseline",
                    "evaluator_fingerprint": "evaluator-v1",
                    "research_source_count": 2,
                    "result_sha256": "digest",
                }
            },
            summary={"aria_autoresearch/runtime_s": 3.5},
        ),
        _DummyRun(id="training", name="train", state="finished", config={}, summary={}),
    ]

    result = wandb_utils.build_autoresearch_run_dataframe(runs)

    assert result.to_dict(orient="records") == [
        {
            "id": "result-run",
            "run_name": "evaluator",
            "state": "finished",
            "goal_slug": "latency",
            "iteration": 3,
            "checkpoint_status": "pass",
            "hypothesis": "Cache the resolved command graph.",
            "research_source_count": 2,
            "candidate_revision": "candidate",
            "baseline_revision": "baseline",
            "evaluator_fingerprint": "evaluator-v1",
            "result_sha256": "digest",
            "runtime_s": 3.5,
            "peak_memory_mb": None,
        }
    ]
