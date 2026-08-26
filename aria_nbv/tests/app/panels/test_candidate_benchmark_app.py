"""Real Streamlit AppTest coverage for the immutable benchmark card."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from streamlit.testing.v1 import AppTest
from typer.testing import CliRunner

from aria_nbv.rollouts.candidate_benchmark import (
    BINDING_KEYS,
    SCHEMA_ID,
    CandidateBenchmark,
    CandidateFamilyCounts,
    CandidatePoint,
    benchmark_binding_from_reader,
    read_bundle_bytes,
    serialize_bundle_bytes,
    sha256_bytes,
    write_bundle,
)
from aria_nbv.rollouts.info_cli import app as rollouts_info_app
from aria_nbv.rollouts.zarr_store import RolloutZarrStoreReader, write_rollout_zarr_store
from tests.rollout_fixtures import build_rollout_records


def _binding() -> dict[str, str]:
    return {
        key: (
            SCHEMA_ID
            if key == "schema_id"
            else "candidate_benchmark"
            if key == "evidence_class"
            else "complete"
            if key == "completion"
            else "1"
            if key == "implementation_revision"
            else sha256_bytes(key.encode())
        )
        for key in BINDING_KEYS
    }


def _record() -> CandidateBenchmark:
    return CandidateBenchmark(
        "state-1",
        "scene-a",
        (CandidateFamilyCounts("forward", True, 1, 1, 1, 1),),
        candidate_ids=(1,),
        coordinates=((0.1, 0.2, 0.3),),
        points=(
            CandidatePoint(
                1, (0.1, 0.2, 0.3), "forward", "forward_local", True, True, "state-1", "cfg", "roll", "branch"
            ),
        ),
    )


class FakeSession:
    """Deterministic persisted-session substitute used inside AppTest."""

    def __init__(self) -> None:
        import streamlit as st

        st.session_state.setdefault("benchmark_records_calls", [])
        st.session_state.setdefault("benchmark_export_calls", [])

    def candidate_benchmark_records(self, **kwargs: Any) -> tuple[CandidateBenchmark, ...]:
        import streamlit as st

        st.session_state["benchmark_records_calls"].append(kwargs)
        return (_record(),)

    def candidate_benchmark_export(self, **kwargs: Any) -> bytes:
        import streamlit as st

        st.session_state["benchmark_export_calls"].append(kwargs)
        payload = serialize_bundle_bytes((_record(),), provenance=_binding())
        st.session_state["benchmark_export_hash"] = sha256_bytes(payload)
        return payload


def _app(tmp_path: Path) -> AppTest:
    script = tmp_path / "render_candidate_benchmark_card.py"
    script.write_text(
        "from aria_nbv.app.panels._stored_rollouts.validity_support import _render_candidate_benchmark_card\n"
        "_render_candidate_benchmark_card(__import__('tests.app.panels.test_candidate_benchmark_app', fromlist=['FakeSession']).FakeSession())\n",
        encoding="utf-8",
    )
    return AppTest.from_file(str(script), default_timeout=30)


def test_candidate_benchmark_card_is_lazy_and_renders_real_plots_and_download(tmp_path: Path) -> None:
    app = _app(tmp_path).run()
    assert not app.exception
    assert app.session_state["benchmark_records_calls"] == []
    assert app.session_state["benchmark_export_calls"] == []
    assert not app.get("download_button")
    assert not app.get("plotly_chart")

    app.toggle[0].set_value(True)
    app = app.run()
    assert not app.exception
    app.session_state["benchmark_records_calls"] = []
    app.session_state["benchmark_export_calls"] = []
    app.text_input[0].set_value("state-1")
    app.number_input[0].set_value(123)
    app = app.run()
    assert not app.exception
    assert app.session_state["benchmark_records_calls"] == [{"state_key": "state-1", "candidate_limit": 123}]
    assert app.session_state["benchmark_export_calls"] == [{"state_key": "state-1"}]
    assert len(app.get("plotly_chart")) == 4
    titles = [json.loads(chart.proto.spec)["layout"]["title"]["text"] for chart in app.get("plotly_chart")]
    assert titles == [
        "Candidate family attempted → valid → selected funnel",
        "Candidate support (target-normalized ground plane)",
        "Candidate support (target-normalized 3D)",
        "Candidate benchmark resource and timing summary",
    ]
    assert len(app.get("download_button")) == 1
    payload = serialize_bundle_bytes((_record(),), provenance=_binding())
    assert app.session_state["benchmark_export_hash"] == sha256_bytes(payload)
    assert read_bundle_bytes(payload, expected_binding=_binding()).records[0].state_key == "state-1"


def test_cli_requires_binding_and_attaches_validated_candidate_bundle(tmp_path: Path) -> None:
    store = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr", build_rollout_records(horizon=1, num_samples=2, seed=19)[:1]
    )
    reader = RolloutZarrStoreReader(store.store_dir)
    binding = benchmark_binding_from_reader(reader, reader.manifest())
    benchmark = write_bundle(tmp_path / "benchmark", (_record(),), provenance=binding)
    output = tmp_path / "thesis.json"
    runner = CliRunner()
    missing = runner.invoke(
        rollouts_info_app,
        [
            "--store",
            str(store.store_dir),
            "--thesis-bundle-output",
            str(output),
            "--thesis-evidence-status",
            "pilot",
            "--candidate-benchmark-bundle",
            str(benchmark),
        ],
    )
    assert missing.exit_code != 0
    assert "candidate-benchmark-binding-json" in missing.output
    binding_path = tmp_path / "binding.json"
    binding_path.write_text(json.dumps(_binding()), encoding="utf-8")
    mismatched = runner.invoke(
        rollouts_info_app,
        [
            "--store",
            str(store.store_dir),
            "--thesis-bundle-output",
            str(output),
            "--thesis-evidence-status",
            "pilot",
            "--candidate-benchmark-bundle",
            str(benchmark),
            "--candidate-benchmark-binding-json",
            str(binding_path),
        ],
    )
    assert mismatched.exit_code != 0
    assert "candidate benchmark binding does not match the selected" in mismatched.output
    assert "rollout store" in mismatched.output
    binding_path.write_text(json.dumps(binding), encoding="utf-8")
    attached = runner.invoke(
        rollouts_info_app,
        [
            "--store",
            str(store.store_dir),
            "--thesis-bundle-output",
            str(output),
            "--thesis-evidence-status",
            "pilot",
            "--candidate-benchmark-bundle",
            str(benchmark),
            "--candidate-benchmark-binding-json",
            str(binding_path),
        ],
    )
    assert attached.exit_code == 0, attached.output
    assert output.is_file()
