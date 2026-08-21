from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import validate_agent_memory as validator  # noqa: E402


def _record(*, record_date: str, codex_thread: str | None = None) -> str:
    thread_line = f"codex_thread: {codex_thread}\n" if codex_thread else ""
    return (
        "---\n"
        "id: example\n"
        f"date: {record_date}\n"
        'title: "Example"\n'
        "status: done\n"
        "topics: [scaffold]\n"
        "confidence: high\n"
        "canonical_updates_needed: []\n"
        f"{thread_line}"
        "---\n"
    )


def _check(tmp_path: Path, monkeypatch, text: str) -> list[str]:
    history = tmp_path / "history"
    history.mkdir()
    (history / "record.md").write_text(text, encoding="utf-8")
    monkeypatch.setattr(validator, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(validator, "HISTORY_ROOT", history)
    return validator.check_history_records()


def test_pre_cutoff_native_record_is_grandfathered(tmp_path: Path, monkeypatch) -> None:
    assert _check(tmp_path, monkeypatch, _record(record_date="2026-08-20")) == []


def test_cutoff_record_requires_thread_uri(tmp_path: Path, monkeypatch) -> None:
    errors = _check(tmp_path, monkeypatch, _record(record_date="2026-08-21"))
    assert any("`codex_thread` must be" in error for error in errors)


def test_cutoff_record_rejects_malformed_thread_uri(
    tmp_path: Path, monkeypatch
) -> None:
    errors = _check(
        tmp_path,
        monkeypatch,
        _record(record_date="2026-08-21", codex_thread="codex://threads/not-a-uuid"),
    )
    assert any("`codex_thread` must be" in error for error in errors)


def test_cutoff_record_accepts_exact_thread_uri(tmp_path: Path, monkeypatch) -> None:
    errors = _check(
        tmp_path,
        monkeypatch,
        _record(
            record_date="2026-08-21",
            codex_thread="codex://threads/019fff4c-cc77-7351-bb81-9759852617c6",
        ),
    )
    assert errors == []
