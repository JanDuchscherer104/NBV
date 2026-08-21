from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "scaffold"))

import run_routing_trials as trials  # noqa: E402


def test_prompt_and_rubric_ids_match_without_prompt_leakage() -> None:
    prompts = trials.load_prompts()
    assert set(prompts) == trials.load_rubric_ids()
    assert set(trials.DEFAULT_TRIAL_IDS) <= set(prompts)
    for task in prompts.values():
        assert "expected_owner_paths" not in task
        assert "required_outcomes" not in task
        assert "forbidden_outcomes" not in task
        assert "mcp__" not in task


def test_codex_command_is_ephemeral_read_only_and_prompt_free(tmp_path: Path) -> None:
    command = trials.build_codex_command(
        checkout=tmp_path,
        model_report=tmp_path / "model.json",
        model="test-model",
        effort="high",
    )
    assert "--ephemeral" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "--json" in command
    assert "--output-schema" in command
    assert command[-1] == "-"
    assert "expected_owner_paths" not in " ".join(command)


def test_trial_report_schema_is_strict_and_policy_neutral() -> None:
    schema = json.loads(trials.REPORT_SCHEMA.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    serialized = json.dumps(schema)
    assert "expected_owner_paths" not in serialized
    assert "forbidden_outcomes" not in serialized
