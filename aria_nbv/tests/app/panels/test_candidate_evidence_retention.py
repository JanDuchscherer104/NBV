"""Contract tests for acquire-once candidate evidence presentation."""

from __future__ import annotations

import ast
import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

from aria_nbv.app import controller as controller_module
from aria_nbv.app.candidate_evidence import (
    CandidateEvidenceView,
    candidate_evidence_view_from_snapshots,
)
from aria_nbv.app.controller import PipelineController
from aria_nbv.app.panels._stored_rollouts import session
from aria_nbv.app.panels._stored_rollouts.session import StoredCandidateEvidenceRequest
from aria_nbv.app.state_types import CandidatesCache
from aria_nbv.reporting.results import canonical_plotly_json
from aria_nbv.rollouts.candidate_evidence import (
    CandidateRolloutOverlay,
    _candidate_evidence_snapshot_from_complete_stored,
    _CompleteStoredCandidateTransport,
    candidate_evidence_snapshot_from_live,
)
from aria_nbv.rollouts.read_model import rollout_at
from aria_nbv.rollouts.zarr_store import RolloutZarrStoreReader, write_rollout_zarr_store
from tests.rollout_fixtures import build_rollout_records
from tests.rollouts.test_candidate_evidence_snapshot import _candidate_set


def _view(source_identity: str, *, title: str = "Candidate support · H=8, t=0, remaining=8") -> CandidateEvidenceView:
    del title
    snapshot = candidate_evidence_snapshot_from_live(
        _candidate_set(),
        selected_attempt_indices=(2,),
        state_key="rollout:1/step:2",
        overlay=CandidateRolloutOverlay(8, 2, 6, 2),
        execution_hash="execution-hash",
    )
    return candidate_evidence_view_from_snapshots((snapshot,), source_identity=source_identity)


def _equivalent_live_and_stored_views() -> tuple[CandidateEvidenceView, CandidateEvidenceView]:
    live_snapshot = candidate_evidence_snapshot_from_live(
        _candidate_set(),
        selected_attempt_indices=(2,),
        state_key="rollout:1/step:2",
        overlay=CandidateRolloutOverlay(8, 2, 6, 2),
        execution_hash="execution-hash",
    )
    stored_snapshot = _candidate_evidence_snapshot_from_complete_stored(
        _CompleteStoredCandidateTransport(
            canonical_json=json.dumps(
                asdict(live_snapshot),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        )
    )
    return (
        candidate_evidence_view_from_snapshots((live_snapshot,), source_identity="candidate-live"),
        candidate_evidence_view_from_snapshots((stored_snapshot,), source_identity="candidate-stored"),
    )


def test_stored_session_acquires_typed_shell_once_and_returns_reader_free_view(monkeypatch: Any) -> None:
    calls: list[str] = []
    rollout = SimpleNamespace(rollout_row_id=7, target_row_id=11)
    previous = SimpleNamespace(step_index=0)
    current = SimpleNamespace(step_index=1)
    target = object()
    snapshot = object()
    expected = _view("store:stable:rollout=7:step=1:directions=0")
    monkeypatch.setattr(session, "_store_projection_identity", lambda _path: "store:stable")
    monkeypatch.setattr(
        session, "rollout_by_id", lambda _reader, row_id: (calls.append(f"rollout:{row_id}"), rollout)[1]
    )
    monkeypatch.setattr(
        session, "rollout_steps", lambda _reader, _rollout: (calls.append("steps"), (previous, current))[1]
    )
    monkeypatch.setattr(session, "target_by_id", lambda _reader, row_id: (calls.append(f"target:{row_id}"), target)[1])
    monkeypatch.setattr(
        session,
        "candidate_evidence_snapshot_from_stored",
        lambda *args, **kwargs: (calls.append(f"snapshot:{kwargs['previous_step'].step_index}"), snapshot)[1],
    )

    def build_view(snapshots: tuple[object, ...], **kwargs: Any) -> CandidateEvidenceView:
        calls.append(f"models:{len(snapshots)}")
        assert kwargs == {"source_identity": expected.source_identity, "show_view_directions": False}
        return expected

    monkeypatch.setattr(session, "candidate_evidence_view_from_snapshots", build_view)
    handle = session.StoredRolloutSession(Path("/selected.zarr"), "store:stable", object(), object(), {})

    actual = handle.acquire_candidate_evidence(StoredCandidateEvidenceRequest(7, 1))

    assert actual is expected
    assert calls == ["rollout:7", "steps", "target:11", "snapshot:0", "models:1"]
    assert not hasattr(actual, "reader")


def test_stored_session_real_store_retains_snapshot_and_canonical_plot_bytes(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=3, seed=19)[:1],
    )
    reader = RolloutZarrStoreReader(result.store_dir)
    rollout = rollout_at(reader, 0)
    identity = session._store_projection_identity(result.store_dir.as_posix())
    handle = session.StoredRolloutSession(
        result.store_dir,
        identity,
        reader,
        object(),
        {},
    )

    view = handle.acquire_candidate_evidence(StoredCandidateEvidenceRequest(rollout.rollout_row_id, 0, False))

    assert len(view.snapshots) == 1
    snapshot = view.snapshots[0]
    assert snapshot.state_key.startswith(f"rollout:{rollout.rollout_row_id}/step:")
    assert snapshot.overlay.factual_step == 0
    assert snapshot.attempted_count == len(snapshot.rows) > 0
    assert len(view.plot_models) == 4
    assert all(
        model.figure.source_ids == (f"candidate-snapshot:{snapshot.source_sha256}",) for model in view.plot_models
    )
    assert all(canonical_plotly_json(model.build_figure()) == model.plotly_json for model in view.plot_models)


def test_live_controller_retains_once_and_invalidates_on_complete_request_change(monkeypatch: Any) -> None:
    calls: list[dict[str, Any]] = []
    first = _view("candidate-snapshot:first:directions=0")
    second = _view("candidate-snapshot:second:directions=0")

    def build(_candidate_set: object, **kwargs: Any) -> CandidateEvidenceView:
        calls.append(kwargs)
        return first if len(calls) == 1 else second

    monkeypatch.setattr(controller_module, "candidate_evidence_view_from_live", build)
    state = SimpleNamespace(candidates=CandidatesCache())
    controller = PipelineController(state, console=SimpleNamespace(log=lambda _message: None))
    candidate_set = SimpleNamespace(request_binding_hash="request-hash")
    distinct_set = SimpleNamespace(request_binding_hash="request-hash")

    actual = controller.retain_candidate_evidence(candidate_set, selected_attempt_indices=(2,))
    again = controller.retain_candidate_evidence(candidate_set, selected_attempt_indices=(2,))
    changed = controller.retain_candidate_evidence(distinct_set, selected_attempt_indices=(2,))

    assert actual is again is first
    assert changed is second
    assert len(calls) == 2


def test_retained_stored_view_fails_closed_after_same_path_replacement(monkeypatch: Any) -> None:
    monkeypatch.setattr(session, "_store_projection_identity", lambda _path: "store:replacement")
    handle = session.StoredRolloutSession(Path("/selected.zarr"), "store:stable", object(), object(), {})
    retained = _view("store:stable:rollout=7:step=1:directions=0")

    with pytest.raises(RuntimeError, match="changed after this session opened"):
        handle.validate_candidate_evidence(retained, StoredCandidateEvidenceRequest(7, 1))


def _app(tmp_path: Path) -> AppTest:
    script = tmp_path / "candidate_evidence_card.py"
    script.write_text(
        "from aria_nbv.app.panels._stored_rollouts.validity_support import _render_canonical_candidate_evidence_card\n"
        "from tests.app.panels.test_candidate_evidence_retention import FakeSession\n"
        "_render_canonical_candidate_evidence_card(FakeSession())\n",
        encoding="utf-8",
    )
    return AppTest.from_file(str(script), default_timeout=30)


def _renderer_app(tmp_path: Path, *, stored: bool) -> AppTest:
    script = tmp_path / f"candidate_evidence_renderer_{'stored' if stored else 'live'}.py"
    script.write_text(
        "from aria_nbv.app.panels.candidate_evidence import render_candidate_evidence_view\n"
        "from tests.app.panels.test_candidate_evidence_retention import _equivalent_live_and_stored_views\n"
        f"render_candidate_evidence_view(_equivalent_live_and_stored_views()[{int(stored)}], "
        "key='candidate-evidence-test')\n",
        encoding="utf-8",
    )
    return AppTest.from_file(str(script), default_timeout=30)


class FakeSession:
    """Session-state observable substitute for the stored acquisition owner."""

    store_identity = "store:stable"

    def __init__(self) -> None:
        import streamlit as st

        st.session_state.setdefault("candidate_evidence_acquisitions", 0)
        st.session_state.setdefault("candidate_evidence_validations", 0)

    def acquire_candidate_evidence(self, request: StoredCandidateEvidenceRequest) -> CandidateEvidenceView:
        import streamlit as st

        st.session_state["candidate_evidence_acquisitions"] += 1
        return _view(
            f"{self.store_identity}:rollout={request.rollout_row_id}:step={request.step_index}:"
            f"directions={int(request.show_view_directions)}"
        )

    def validate_candidate_evidence(self, view: CandidateEvidenceView, request: StoredCandidateEvidenceRequest) -> None:
        import streamlit as st

        st.session_state["candidate_evidence_validations"] += 1
        expected = (
            f"{self.store_identity}:rollout={request.rollout_row_id}:step={request.step_index}:"
            f"directions={int(request.show_view_directions)}"
        )
        if view.source_identity != expected:
            raise RuntimeError("stale")


def test_candidate_evidence_card_is_lazy_and_reuses_retained_models_on_rerun(tmp_path: Path) -> None:
    app = _app(tmp_path).run()
    assert not app.exception
    assert app.session_state["candidate_evidence_acquisitions"] == 0
    assert not app.get("plotly_chart")

    next(button for button in app.button if button.label == "Inspect candidate shell").click()
    app = app.run()
    assert not app.exception
    assert app.session_state["candidate_evidence_acquisitions"] == 1
    assert len(app.get("plotly_chart")) == 1
    spec = json.loads(app.get("plotly_chart")[0].proto.spec)
    assert (
        spec["layout"]["title"]["text"]
        == "Candidate centers in target-aligned support (ground plane) · H=8, t=2, remaining=6"
    )

    app = app.run()
    assert not app.exception
    assert app.session_state["candidate_evidence_acquisitions"] == 1
    assert len(app.get("plotly_chart")) == 1

    app.number_input[1].set_value(1)
    app = app.run()
    assert not app.exception
    assert app.session_state["candidate_evidence_acquisitions"] == 1
    assert not app.get("plotly_chart")

    app.session_state[session.CANDIDATE_EVIDENCE_STATE_KEY] = object()
    app = app.run()
    assert not app.exception
    assert not app.get("plotly_chart")


def test_generic_renderer_preserves_identical_live_and_stored_plot_bytes(tmp_path: Path) -> None:
    live_view, stored_view = _equivalent_live_and_stored_views()
    assert live_view.snapshots == stored_view.snapshots
    assert live_view.plot_models == stored_view.plot_models
    assert tuple(model.figure.id for model in live_view.plot_models) == tuple(
        model.figure.id for model in stored_view.plot_models
    )
    live = _renderer_app(tmp_path, stored=False).run()
    stored = _renderer_app(tmp_path, stored=True).run()

    assert not live.exception and not stored.exception
    assert len(live.get("plotly_chart")) == len(stored.get("plotly_chart")) == 1
    assert live.get("plotly_chart")[0].proto.spec == stored.get("plotly_chart")[0].proto.spec


def test_candidate_evidence_renderer_has_no_scientific_or_storage_imports() -> None:
    source = Path(__file__).parents[3] / "aria_nbv" / "app" / "panels" / "candidate_evidence.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    forbidden = ("pose_generation", "candidate_benchmark", "candidate_plotting", "read_model", "zarr_store")
    imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)] + [
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    ]
    assert not any(token in module for module in imports for token in forbidden)


def test_candidate_evidence_view_rejects_empty_or_unbound_products() -> None:
    valid = _view("candidate-view")
    with pytest.raises(ValueError, match="at least one snapshot"):
        CandidateEvidenceView("empty", (), False, valid.plot_models)
    wrong_source = tuple(
        model
        if index
        else type(model)(
            model.key,
            model.title,
            type(model.figure)(
                model.figure.id,
                model.figure.plotly_json,
                ("candidate-snapshot:wrong",),
                model.figure.source_result_ids,
                model.figure.symbol_ids,
                model.figure.uses_webgl,
            ),
            model.context,
        )
        for index, model in enumerate(valid.plot_models)
    )
    with pytest.raises(ValueError, match="source identities"):
        CandidateEvidenceView("wrong", valid.snapshots, False, wrong_source)
