from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import validate_agent_memory as validator  # noqa: E402

THREAD_URI = "codex://threads/019fff4c-cc77-7351-bb81-9759852617c6"


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
    history.mkdir(exist_ok=True)
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
            codex_thread=THREAD_URI,
        ),
    )
    assert errors == []


def test_provenance_cutoff_requires_new_checkout_metadata(
    tmp_path: Path, monkeypatch
) -> None:
    record = _record(record_date="2026-08-22", codex_thread=THREAD_URI)
    errors = _check(tmp_path, monkeypatch, record)
    assert any("checkout provenance" in error for error in errors)
    valid = (
        record.rsplit("---\n", 1)[0]
        + "repo_object_format: sha1\nrepo_head: "
        + "a" * 40
        + "\nrepo_branch: detached\nworktree_kind: primary\n---\n"
    )
    assert _check(tmp_path, monkeypatch, valid) == []


def test_provenance_accepts_all_git_valid_branch_names(
    tmp_path: Path, monkeypatch
) -> None:
    record = _record(record_date="2026-08-22", codex_thread=THREAD_URI)
    valid = (
        record.rsplit("---\n", 1)[0]
        + "repo_object_format: sha1\nrepo_head: "
        + "a" * 40
        + "\nrepo_branch: feature@x\nworktree_kind: primary\n---\n"
    )
    assert _check(tmp_path, monkeypatch, valid) == []


def test_provenance_accepts_sha256_oid(tmp_path: Path, monkeypatch) -> None:
    record = _record(record_date="2026-08-22", codex_thread=THREAD_URI)
    valid = (
        record.rsplit("---\n", 1)[0]
        + "repo_object_format: sha256\nrepo_head: "
        + "a" * 64
        + "\nrepo_branch: detached\nworktree_kind: linked\n---\n"
    )
    assert _check(tmp_path, monkeypatch, valid) == []


def test_provenance_rejects_oid_mismatched_to_object_format(
    tmp_path: Path, monkeypatch
) -> None:
    record = _record(record_date="2026-08-22", codex_thread=THREAD_URI)
    invalid = (
        record.rsplit("---\n", 1)[0]
        + "repo_object_format: sha256\nrepo_head: "
        + "a" * 40
        + "\nrepo_branch: detached\nworktree_kind: primary\n---\n"
    )
    errors = _check(tmp_path, monkeypatch, invalid)
    assert any("repo_head must be a full sha256 Git OID" in error for error in errors)
