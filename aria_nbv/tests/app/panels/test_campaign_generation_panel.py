"""Focused contracts for the bounded Campaign Generation Streamlit adapter."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TypeVar

import pytest
import streamlit as st

from aria_nbv.app.panels import campaign_generation as panel

_T = TypeVar("_T")
_R = TypeVar("_R")


def _record(items: list[_T], item: _T, result: _R) -> _R:
    items.append(item)
    return result


@pytest.mark.parametrize("name", ["", "has space", "../escape", "semi;colon", "a/b", "ümlaut"])
def test_tmux_session_name_rejects_unsafe_values(name: str) -> None:
    with pytest.raises(ValueError):
        panel.build_tmux_argv(name, ["nbv-rollout-campaign", "status"])


def test_tmux_argv_is_shell_free_and_preserves_each_argument() -> None:
    command = ["nbv-rollout-campaign", "run", "--config-path", "/tmp/space path.toml", "--flag=semi;colon"]
    argv = panel.build_tmux_argv("cuda-campaign", command)
    assert argv == ["tmux", "new-session", "-d", "-s", "cuda-campaign", "--", *command]


@pytest.mark.parametrize("action", ["preflight", "plan", "smoke", "run", "resume", "status"])
def test_campaign_argv_uses_one_canonical_cli_and_action(action: str, tmp_path: Path) -> None:
    config_path = tmp_path / "campaign.toml"
    plan_path = tmp_path / "plan.json" if action in {"run", "resume"} else None
    source_manifest = tmp_path / "source.json" if action == "plan" else None
    argv = panel.build_campaign_argv(
        action,
        config_path=config_path,
        plan_path=plan_path,
        source_manifest=source_manifest,
    )
    assert argv[:5] == [sys.executable, "-m", "aria_nbv.oracle.pipelines.cli", "--campaign", action]
    assert Path(argv[0]).is_absolute()
    assert str(config_path) in argv
    if action in {"run", "resume"}:
        assert argv[-2:] == ["--plan-path", str(plan_path)]
    if action == "status":
        assert argv[-1] == "--json"


def test_campaign_argv_carries_operational_guards_only_for_execution(tmp_path: Path) -> None:
    argv = panel.build_campaign_argv(
        "run",
        config_path=tmp_path / "campaign.toml",
        plan_path=tmp_path / "plan.json",
        max_new_units=3,
        time_budget_minutes=45,
        free_disk_floor_gb=20,
    )
    assert argv == [
        sys.executable,
        "-m",
        "aria_nbv.oracle.pipelines.cli",
        "--campaign",
        "run",
        "--config-path",
        str(tmp_path / "campaign.toml"),
        "--max-new-units",
        "3",
        "--time-budget-minutes",
        "45",
        "--free-disk-floor-gb",
        "20",
        "--plan-path",
        str(tmp_path / "plan.json"),
    ]
    plan_argv = panel.build_campaign_argv(
        "plan", config_path=tmp_path / "campaign.toml", source_manifest=tmp_path / "source.json"
    )
    assert not any(flag in plan_argv for flag in ("--max-new-units", "--time-budget-minutes", "--free-disk-floor-gb"))


def test_campaign_module_entrypoint_survives_empty_path(tmp_path: Path) -> None:
    """The UI's canonical module entrypoint must not depend on a console script in PATH."""
    argv = panel.build_campaign_argv("status", config_path=tmp_path / "campaign.toml")
    result = subprocess.run(
        [*argv[:4], "--help"],
        check=False,
        capture_output=True,
        text=True,
        env={"PATH": "", "HOME": os.environ.get("HOME", "")},
    )
    assert result.returncode == 0, result.stderr
    assert "campaign" in result.stdout.lower()


@pytest.mark.parametrize("name,value", [("max_new_units", 0), ("time_budget_minutes", 1441), ("free_disk_floor_gb", 0)])
def test_campaign_argv_rejects_out_of_bounds_operational_guards(tmp_path: Path, name: str, value: int) -> None:
    with pytest.raises(ValueError):
        if name == "max_new_units":
            panel.build_campaign_argv(
                "run", config_path=tmp_path / "campaign.toml", plan_path=tmp_path / "plan.json", max_new_units=value
            )
        elif name == "time_budget_minutes":
            panel.build_campaign_argv(
                "run",
                config_path=tmp_path / "campaign.toml",
                plan_path=tmp_path / "plan.json",
                time_budget_minutes=value,
            )
        else:
            panel.build_campaign_argv(
                "run",
                config_path=tmp_path / "campaign.toml",
                plan_path=tmp_path / "plan.json",
                free_disk_floor_gb=value,
            )


@dataclass
class _Result:
    returncode: int
    stderr: str = ""


def test_tmux_launch_rejects_existing_session_before_new_session(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def runner(argv: Any, **kwargs: Any) -> Any:
        calls.append(list(argv))
        return _Result(0)

    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/tmux")
    ok, message = panel.launch_campaign_tmux("already-running", ["nbv-rollout-campaign", "run"], runner=runner)
    assert not ok
    assert "already exists" in message
    assert calls == [["tmux", "has-session", "-t", "already-running"]]


def test_tmux_launch_rejects_existing_campaign_claim_before_tmux(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[list[str]] = []

    def runner(argv: Any, **kwargs: Any) -> Any:
        calls.append(list(argv))
        return _Result(1)

    claim = tmp_path / "run-claim.json"
    claim.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/tmux")
    ok, message = panel.launch_campaign_tmux(
        "cuda-campaign", ["nbv-rollout-campaign", "run"], claim_path=claim, runner=runner
    )
    assert not ok
    assert "claim exists" in message
    assert calls == []


def test_tmux_launch_degrades_when_tmux_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    ok, message = panel.launch_campaign_tmux("cuda-campaign", ["nbv-rollout-campaign", "status"])
    assert not ok
    assert "unavailable" in message


def test_tmux_launch_reports_nonzero_new_session_without_running_state(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def runner(argv: Any, **kwargs: Any) -> Any:
        calls.append(list(argv))
        if argv[1] == "has-session":
            return _Result(1)
        return _Result(1, "cannot create session")

    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/tmux")
    ok, message = panel.launch_campaign_tmux("cuda-campaign", ["nbv-rollout-campaign", "run"], runner=runner)
    assert not ok
    assert "cannot create session" in message
    assert len(calls) == 2


def test_tmux_launch_reports_immediate_session_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def runner(argv: Any, **kwargs: Any) -> Any:
        calls.append(list(argv))
        if argv[1] == "has-session":
            return _Result(1 if len(calls) == 1 else 1)
        return _Result(0)

    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/tmux")
    ok, message = panel.launch_campaign_tmux("cuda-campaign", ["nbv-rollout-campaign", "run"], runner=runner)
    assert not ok
    assert "exited immediately" in message


def test_tmux_launch_success_calls_new_session_once_and_keeps_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def runner(argv: Any, **kwargs: Any) -> Any:
        calls.append((list(argv), kwargs))
        return _Result(1 if argv[1] == "has-session" and len(calls) == 1 else 0)

    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/tmux")
    command = ["nbv-rollout-campaign", "run", "--config-path", "/tmp/path with spaces.toml"]
    ok, _ = panel.launch_campaign_tmux("cuda-campaign", command, runner=runner)
    assert ok
    new_session = calls[1]
    assert new_session[0] == ["tmux", "new-session", "-d", "-s", "cuda-campaign", "--", *command]
    assert new_session[1].get("shell", False) is False


def test_capture_tmux_tail_uses_safe_argv_and_bounds_output(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []
    huge = "x" * 5001

    def runner(argv: Any, **kwargs: Any) -> Any:
        calls.append((list(argv), kwargs))
        return type("Result", (), {"returncode": 0, "stdout": huge})()

    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/tmux")
    output = panel.capture_tmux_tail("cuda-campaign", runner=runner)
    assert output == huge[-4000:]
    assert calls == [
        (
            ["tmux", "capture-pane", "-p", "-t", "cuda-campaign", "-S", "-80"],
            {"check": False, "capture_output": True, "text": True, "shell": False},
        )
    ]


def test_capture_tmux_tail_degrades_without_tmux_or_on_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(shutil, "which", lambda _: None)
    assert panel.capture_tmux_tail("cuda-campaign", runner=lambda argv, **kwargs: calls.append(list(argv))) == ""
    assert calls == []
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/tmux")
    assert panel.capture_tmux_tail("cuda-campaign", runner=lambda *args, **kwargs: _Result(1, "failed")) == ""


class _FakeCampaign:
    def __init__(
        self,
        output_root: Path,
        *,
        evidence: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.config = type(
            "Config",
            (),
            {
                "campaign_id": "cuda-campaign",
                "output_root": output_root,
                "writer_config_path": None,
                "profiles": [],
                "temperatures": (0.5, 1.0, 2.0, 4.0),
                "observed_target_iou_threshold": 0.2,
                "seed": 20260728,
                "expected_scene_count": 100,
                "min_valid_root_candidates": 15,
                "stage_timeout_seconds": 120,
                "work_unit_timeout_seconds": 3600,
            },
        )()
        self.evidence = evidence
        self.error = error
        self.progress_calls = 0
        self.event_calls = 0

    def load_plan(self, path: Path) -> Any:
        assert path.exists()
        return SimpleNamespace(source_manifest_hash="source-test", admission_audit_hash="audit-test")

    def smoke_evidence(self, plan: Any) -> Any:
        if self.error:
            raise self.error
        return self.evidence or {}

    def progress_summary(self, plan: Any | None = None) -> Any:
        del plan
        self.progress_calls += 1
        return {"state": "running", "counts": {"pending": 1}}

    def read_events(self) -> Any:
        self.event_calls += 1
        return []


def test_launch_ready_requires_current_smoke_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Smoke success evidence is the gate; a persisted claim blocks launch."""
    plan_path = tmp_path / "plan.json"
    plan_path.write_text("{}", encoding="utf-8")
    campaign = _FakeCampaign(
        tmp_path, evidence={"config_hash": "cfg", "result": {"outcome": "succeeded", "validated": True}}
    )
    assert panel._launch_ready(campaign, plan_path) is True
    (tmp_path / "run-claim.json").write_text("{}", encoding="utf-8")
    assert panel._launch_ready(campaign, plan_path) is False


def test_launch_ready_rejects_stale_smoke_evidence(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text("{}", encoding="utf-8")
    campaign = _FakeCampaign(tmp_path, error=RuntimeError("stale smoke"))
    assert panel._launch_ready(campaign, plan_path) is False


def test_admission_audit_renders_all_three_figures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real audit-shaped payloads reach reason, IoU, and scene plots."""

    figures = []
    monkeypatch.setattr(panel, "_render_plot", lambda figure, *_args, **_kwargs: figures.append(figure))
    metrics: list[tuple[str, str]] = []
    monkeypatch.setattr(
        st,
        "columns",
        lambda count: [SimpleNamespace(metric=lambda label, value: metrics.append((label, value)))] * count,
    )
    monkeypatch.setattr(st, "expander", lambda *_args, **_kwargs: nullcontext())
    monkeypatch.setattr(st, "dataframe", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(st, "download_button", lambda *_args, **_kwargs: None)

    panel._render_admission_audit(
        {
            "counts": {
                "zero_observation_samples": 3,
                "scenes_with_zero_observation_samples": 2,
                "zero_only_scenes": 1,
            },
            "reason_rows": [{"reason": "admitted", "count": 1, "admitted": True}],
            "iou_rows": [{"oriented_iou": 0.4, "reason": "admitted"}],
            "scene_rows": [{"admission_rate": 1.0}],
            "rows": [],
        },
        threshold=0.2,
    )

    assert len(figures) == 3
    assert ("Zero-target samples", "3") in metrics
    assert ("Scenes containing zero-target samples", "2") in metrics
    assert ("Zero-only scenes", "1") in metrics
    assert "with observed targets" in str(figures[-1].layout.title.text)


class _FakeColumn:
    def __init__(self, buttons: set[str]) -> None:
        self.buttons = buttons

    def button(self, label: str, **kwargs: Any) -> bool:
        return label in self.buttons and not kwargs.get("disabled", False)


class _FakeStreamlit:
    def __init__(self, buttons: set[str] | None = None, controls: dict[str, Any] | None = None) -> None:
        self.session_state: dict[str, Any] = {}
        self.buttons = buttons or set()
        self.controls = controls or {}
        self.number_inputs: dict[str, dict[str, Any]] = {}
        self.selectboxes: dict[str, tuple[Any, ...]] = {}
        self.json_payloads: list[Any] = []
        self.messages: list[str] = []
        self.warnings: list[str] = []
        self.captions: list[str] = []
        self.codes: list[str] = []

    def header(self, *args: Any, **kwargs: Any) -> None:
        pass

    def selectbox(self, label: Any, options: Any, **kwargs: Any) -> Any:
        key = kwargs.get("key", label)
        self.selectboxes[key] = tuple(options)
        return self.controls.get(key, options[0])

    def text_input(self, label: Any, value: Any = "", **kwargs: Any) -> Any:
        return value

    def number_input(self, label: Any, value: Any = 0, **kwargs: Any) -> Any:
        self.number_inputs[kwargs.get("key", label)] = {"label": label, **kwargs}
        return self.controls.get(kwargs.get("key", label), value)

    def caption(self, *args: Any, **kwargs: Any) -> None:
        self.captions.extend(str(value) for value in args)

    def json(self, *args: Any, **kwargs: Any) -> None:
        if args:
            self.json_payloads.append(args[0])

    def columns(self, n: Any) -> Any:
        return [_FakeColumn(self.buttons) for _ in range(n)]

    def button(self, label: Any, **kwargs: Any) -> Any:
        return label in self.buttons and not kwargs.get("disabled", False)

    def code(self, *args: Any, **kwargs: Any) -> None:
        self.codes.extend(str(value) for value in args)

    def subheader(self, *args: Any, **kwargs: Any) -> None:
        pass

    def info(self, *args: Any, **kwargs: Any) -> None:
        pass

    def success(self, *args: Any, **kwargs: Any) -> None:
        self.messages.extend(str(value) for value in args)

    def warning(self, *args: Any, **kwargs: Any) -> None:
        self.warnings.extend(str(value) for value in args)

    def error(self, *args: Any, **kwargs: Any) -> None:
        self.messages.extend(str(value) for value in args)

    def dataframe(self, *args: Any, **kwargs: Any) -> None:
        pass


def _patch_fake_page(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    buttons: set[str] | None = None,
    controls: dict[str, Any] | None = None,
) -> Any:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text("{}", encoding="utf-8")
    campaign = _FakeCampaign(tmp_path, evidence={"result": {"outcome": "succeeded", "validated": True}})
    recipes = [
        {"name": "temperature_softmax_h8", "policy": "temperature_softmax", "horizon": 8, "branch": 1, "beam": 1}
    ]
    profile = type(
        "Profile",
        (),
        {
            "name": "realistic_core_60",
            "components": [("forward_local", 24)],
            "total_count": 60,
            "device": "cuda",
            "recipes": recipes,
        },
    )()
    campaign.config.profiles = [profile]
    monkeypatch.setattr(panel, "resolve_config_toml_path", lambda _: tmp_path / "cfg.toml")
    monkeypatch.setattr(panel, "_campaign", lambda _: campaign)
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/tmux")
    monkeypatch.setattr(shutil, "disk_usage", lambda _: SimpleNamespace(free=100 * 1024**3))
    fake_st = _FakeStreamlit(buttons, controls)
    monkeypatch.setattr(panel, "st", fake_st)
    return campaign, fake_st, plan_path


def test_page_exposes_bounded_operational_controls(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _, fake_st, _ = _patch_fake_page(monkeypatch, tmp_path)
    panel.render_campaign_generation_page()
    assert fake_st.number_inputs["campaign_max_units"]["max_value"] == 100
    assert fake_st.number_inputs["campaign_time_budget"]["max_value"] == 1440
    assert fake_st.number_inputs["campaign_free_disk_floor"]["max_value"] == 1024


def test_page_exposes_only_explicitly_reviewed_configs_with_default_unchanged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _, fake_st, _ = _patch_fake_page(monkeypatch, tmp_path)
    panel.render_campaign_generation_page()
    assert fake_st.selectboxes["campaign_config_path"] == panel._REVIEWED_CONFIGS
    assert fake_st.selectboxes["campaign_config_path"][0] == panel._DEFAULT_CONFIG


def test_selected_reviewed_config_drives_admission_audit_without_launch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    selected = panel._REVIEWED_CONFIGS[1]
    campaign, fake_st, _ = _patch_fake_page(
        monkeypatch,
        tmp_path,
        controls={"campaign_config_path": selected},
        buttons={"Load admission audit"},
    )
    selected_config = tmp_path / "pilot-corrected-v10.toml"
    audit_path = campaign.config.output_root / "admission-audit.json"
    audit_path.write_text("{}", encoding="utf-8")
    plan_path = campaign.config.output_root / "plan.json"
    plan_path.write_text("{}", encoding="utf-8")
    resolved: list[str] = []
    monkeypatch.setattr(
        panel,
        "resolve_config_toml_path",
        lambda value: _record(resolved, value, selected_config),
    )
    loaded: list[str] = []
    monkeypatch.setattr(
        panel,
        "_cached_admission_evidence",
        lambda path, *_args, **_kwargs: _record(loaded, path, {"counts": {"observed": 1}}),
    )
    monkeypatch.setattr(panel, "_render_admission_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(panel, "build_campaign_argv", lambda *args, **kwargs: ["not", "invoked"])

    panel.render_campaign_generation_page()

    assert resolved == [selected]
    assert loaded == [audit_path.as_posix()]
    assert not any("not invoked" in code for code in fake_st.codes)


def test_page_disables_launch_for_invalid_operational_control(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _, fake_st, _ = _patch_fake_page(
        monkeypatch,
        tmp_path,
        buttons={"Launch in tmux"},
        controls={"campaign_max_units": 101},
    )
    panel.render_campaign_generation_page()
    assert fake_st.messages == []
    assert any("within their displayed bounds" in warning for warning in fake_st.warnings)


def test_page_does_not_read_admission_audit_until_explicit_load(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    campaign, _, _ = _patch_fake_page(monkeypatch, tmp_path)
    (campaign.config.output_root / "admission-audit.json").write_text("{}", encoding="utf-8")
    calls: list[str] = []
    monkeypatch.setattr(
        panel,
        "_cached_admission_evidence",
        lambda path, *_args, **_kwargs: _record(calls, path, {}),
    )

    panel.render_campaign_generation_page()

    assert calls == []


def test_page_loads_and_renders_identity_bound_admission_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    campaign, fake_st, _ = _patch_fake_page(monkeypatch, tmp_path, buttons={"Load admission audit"})
    audit_path = campaign.config.output_root / "admission-audit.json"
    audit_path.write_text("{}", encoding="utf-8")
    payload = {"counts": {"observed": 1}}
    calls: list[tuple[str, dict[str, Any]]] = []
    rendered: list[tuple[dict[str, Any], float]] = []

    def load(path: str, _identity: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append((path, kwargs))
        return payload

    monkeypatch.setattr(panel, "_cached_admission_evidence", load)
    monkeypatch.setattr(
        panel,
        "_render_admission_audit",
        lambda value, *, threshold: rendered.append((value, threshold)),
    )

    panel.render_campaign_generation_page()

    assert calls == [
        (
            audit_path.as_posix(),
            {
                "campaign_id": "cuda-campaign",
                "source_manifest_hash": "source-test",
                "admission_audit_hash": "audit-test",
            },
        )
    ]
    assert rendered == [(payload, 0.2)]
    assert panel._ADMISSION_STATE_KEY in fake_st.session_state
    assert (
        "aria_nbv/aria_nbv/oracle/pipelines/admission_evidence.py"
        in panel._admission_explanation("reasons", threshold=0.2).external_references[0][1]
    )


def test_campaign_admission_evidence_routes_completed_shard_to_shared_s2_renderer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The campaign page reuses the rollout S² owner without moving plots into the oracle reducer."""

    stores = (tmp_path / "shards" / "unit-a", tmp_path / "shards" / "unit-b")
    rendered: list[tuple[Path, str]] = []
    monkeypatch.setattr(st, "subheader", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(st, "caption", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(st, "selectbox", lambda _label, options, **_kwargs: options[1])
    monkeypatch.setattr(
        panel,
        "render_s2_direction_histograms",
        lambda handle, *, key_prefix: rendered.append((handle.store_path, key_prefix)),
    )

    panel._render_campaign_rollout_s2_evidence(stores)

    assert rendered == [(stores[1], "campaign_admission_unit-b")]


def test_campaign_s2_selector_excludes_nonvalidated_artifact_records(tmp_path: Path) -> None:
    """Only plan-bound validated artifacts may be presented as campaign evidence."""

    validated = tmp_path / "shards" / "planned"
    stale = tmp_path / "shards" / "stale"
    stores = panel._validated_campaign_store_paths(
        {
            "validated_artifacts": [{"store_path": str(validated)}],
            "artifact_records": [{"status": "orphan", "store_path": str(stale)}],
        }
    )

    assert stores == (validated,)


def test_page_warns_and_disables_launch_below_free_disk_floor(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _, fake_st, _ = _patch_fake_page(monkeypatch, tmp_path, buttons={"Launch in tmux"})
    monkeypatch.setattr(shutil, "disk_usage", lambda _: SimpleNamespace(free=2 * 1024**3))
    panel.render_campaign_generation_page()
    assert any("below the configured floor" in warning for warning in fake_st.warnings)
    assert fake_st.messages == []


def test_page_checks_nearest_existing_ancestor_for_fresh_output_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    campaign, _, _ = _patch_fake_page(monkeypatch, tmp_path)
    output_root = tmp_path / "fresh" / "campaign-output"
    campaign.config.output_root = output_root
    monkeypatch.setattr(panel, "_launch_ready", lambda *_args: False)
    usage_paths: list[Path] = []
    monkeypatch.setattr(
        shutil,
        "disk_usage",
        lambda path: _record(usage_paths, Path(path), SimpleNamespace(free=100 * 1024**3)),
    )
    panel.render_campaign_generation_page()
    assert usage_paths == [tmp_path]
    assert not output_root.exists()


def test_page_does_not_read_progress_until_explicit_refresh(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    campaign, fake_st, _ = _patch_fake_page(monkeypatch, tmp_path)
    capture_calls: list[str] = []
    monkeypatch.setattr(panel, "capture_tmux_tail", lambda session: _record(capture_calls, session, "tail"))
    panel.render_campaign_generation_page()
    assert campaign.progress_calls == 0
    assert campaign.event_calls == 0
    assert capture_calls == []
    assert "campaign_generation_view" not in fake_st.session_state


def test_page_refresh_reads_summary_and_events_once(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    campaign, fake_st, _ = _patch_fake_page(monkeypatch, tmp_path, buttons={"Refresh status"})
    capture_calls: list[str] = []
    monkeypatch.setattr(panel, "capture_tmux_tail", lambda session: _record(capture_calls, session, "tail"))
    panel.render_campaign_generation_page()
    assert campaign.progress_calls == 1
    assert campaign.event_calls == 1
    assert capture_calls == ["cuda-campaign-campaign"]
    assert "campaign_generation_view" in fake_st.session_state
    assert fake_st.session_state["campaign_generation_view"]["tmux_output"] == "tail"
    assert "tmux output (bounded)" in fake_st.captions
    assert "tail" in fake_st.codes


def test_page_inspect_handoff_sets_only_validated_absolute_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    campaign, fake_st, _ = _patch_fake_page(monkeypatch, tmp_path, buttons={"Refresh status", "Inspect unit-1"})
    store = (tmp_path / "shards" / "unit-1").resolve()
    campaign.progress_summary = lambda: {
        "state": "completed",
        "counts": {"completed": 1},
        "validated_artifacts": [{"work_unit_hash": "unit-1", "store_path": str(store), "validation": "passed"}],
    }
    panel.render_campaign_generation_page()
    assert fake_st.session_state["rollout_store_manual_path"] == str(store)


def test_page_renders_full_read_only_scientific_recipe_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _, fake_st, _ = _patch_fake_page(monkeypatch, tmp_path)
    panel.render_campaign_generation_page()
    scientific = next(
        payload["scientific_contract"] for payload in fake_st.json_payloads if "scientific_contract" in payload
    )
    assert scientific["recipes"] == [
        {
            "name": "temperature_softmax_h8",
            "policy": "temperature_softmax",
            "horizon": 8,
            "branch": 1,
            "beam": 1,
            "temperatures": [0.5, 1.0, 2.0, 4.0],
        }
    ]
    assert scientific["device"] == "cuda"
    assert scientific["total_candidates"] == 60


def test_page_invalidates_cached_view_when_plan_changes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    campaign, fake_st, plan_path = _patch_fake_page(monkeypatch, tmp_path)
    fake_st.session_state["campaign_generation_view"] = {
        "key": (str(tmp_path / "cfg.toml"), str(plan_path), 0),
        "summary": {"state": "stale"},
        "events": [],
    }
    plan_path.write_text("changed", encoding="utf-8")
    panel.render_campaign_generation_page()
    assert campaign.progress_calls == 0
    assert "campaign_generation_view" not in fake_st.session_state


def test_page_launch_passes_canonical_claim_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    campaign, _, _ = _patch_fake_page(monkeypatch, tmp_path, buttons={"Launch in tmux"})
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        panel,
        "launch_campaign_tmux",
        lambda *args, **kwargs: _record(calls, kwargs, (True, "ok")),
    )
    panel.render_campaign_generation_page()
    assert calls == [{"claim_path": tmp_path / "run-claim.json"}]


def test_page_truncates_synchronous_command_output_before_render_and_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _, fake_st, _ = _patch_fake_page(monkeypatch, tmp_path, buttons={"Validate / preflight"})
    huge = "x" * 5001
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: type("Result", (), {"returncode": 0, "stdout": huge, "stderr": huge})(),
    )
    panel.render_campaign_generation_page()
    last_action = fake_st.session_state["campaign_generation_last_action"]
    assert len(last_action["stdout"]) == 4000
    assert len(last_action["stderr"]) == 4000
    assert all(len(message) <= 4000 for message in fake_st.messages)


def test_campaign_source_excludes_unbounded_or_forbidden_ui_controls() -> None:
    source = Path(panel.__file__).read_text(encoding="utf-8")
    assert "text_area" not in source
    assert "rerun" not in source.lower()
    assert "st.plot" not in source
    assert "st.kill" not in source
    assert "st.delete" not in source
    assert "autopoll" not in source.lower()
    assert "Refresh status" in source
