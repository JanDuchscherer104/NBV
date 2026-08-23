"""Regression tests for deterministic debrief navigation and capture gates."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
THREAD_ID = "019fff4c-cc77-7351-bb81-9759852617c6"
THREAD_URI = f"codex://threads/{THREAD_ID}"
sys.path.insert(0, str(ROOT / "scripts"))

import debrief_index  # noqa: E402
import new_debrief  # noqa: E402
import validate_agent_memory as validator  # noqa: E402


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _env_without_thread(**updates: str) -> dict[str, str]:
    env = dict(os.environ)
    env.pop("CODEX_THREAD_ID", None)
    env.update(updates)
    return env


def _record(
    path: Path,
    record_id: str = "record",
    *,
    record_date: str = "2026-08-21",
    touched_owner_paths: list[str] | None = None,
    files_touched: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    touched_lines = ""
    if touched_owner_paths is not None:
        touched_lines = "touched_owner_paths:\n" + "".join(
            f"  - {item}\n" for item in touched_owner_paths
        )
    elif files_touched is not None:
        touched_lines = "files_touched:\n" + "".join(
            f"  - path: {item}\n    kind: fixture\n" for item in files_touched
        )
    path.write_text(
        "---\n"
        f"id: {record_id}\n"
        f"date: {record_date}\n"
        "title: Test\n"
        "status: done\n"
        "topics: [test]\n"
        "confidence: high\n"
        "canonical_updates_needed: []\n"
        f"{touched_lines}"
        f"codex_thread: {THREAD_URI}\n"
        "---\n\nBody\n",
        encoding="utf-8",
    )


def _repo(tmp_path: Path, *, object_format: str | None = None) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    init_args = ("init", "-q")
    if object_format is not None:
        init_args += (f"--object-format={object_format}",)
    _git(root, *init_args)
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    _git(root, "branch", "-M", "main")
    _record(root / ".agents/memory/history/2026/08/record.md")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "initial")
    return root


def test_current_history_count_and_bytes_are_stable() -> None:
    first = debrief_index.render_index(ROOT)
    second = debrief_index.render_index(ROOT)
    assert first == second
    rows = [json.loads(line) for line in first.splitlines()]
    visible_paths = {
        path.relative_to(ROOT).as_posix()
        for path in debrief_index.visible_history_paths(ROOT)
    }
    assert {row["source_path"] for row in rows} == visible_paths
    assert len(rows) == len(visible_paths)
    assert len({row["source_path"] for row in rows}) == len(rows)
    assert all("touched_owner_paths" in row for row in rows)
    assert all(
        "codex_thread" in row
        and (row["codex_thread"] is None or isinstance(row["codex_thread"], str))
        for row in rows
    )
    for row in rows:
        provenance = row.get("checkout_provenance")
        if provenance is not None:
            assert provenance["repo_object_format"] in {"sha1", "sha256"}
    assert (ROOT / ".agents/memory/index/debriefs.jsonl").read_bytes() == first


def test_index_detects_edit_add_delete_and_rename(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    index = root / ".agents/memory/index/debriefs.jsonl"
    index.parent.mkdir(parents=True)
    index.write_bytes(debrief_index.render_index(root))
    source = root / ".agents/memory/history/2026/08/record.md"
    source.write_text(source.read_text(encoding="utf-8") + "edit\n", encoding="utf-8")
    assert debrief_index.check_index(root, index)
    index.write_bytes(debrief_index.render_index(root))
    renamed = root / ".agents/memory/history/2026/08/renamed.md"
    source.rename(renamed)
    assert debrief_index.check_index(root, index)
    index.write_bytes(debrief_index.render_index(root))
    _record(root / ".agents/memory/history/2026/08/added.md", "added")
    assert debrief_index.check_index(root, index)
    index.write_bytes(debrief_index.render_index(root))
    (root / ".agents/memory/history/2026/08/added.md").unlink()
    assert debrief_index.check_index(root, index)


def test_malformed_frontmatter_is_an_index_error(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / ".agents/memory/history/2026/08/record.md").write_text(
        "not frontmatter\n", encoding="utf-8"
    )
    errors = debrief_index.check_index(
        root, root / ".agents/memory/index/debriefs.jsonl"
    )
    assert errors and "cannot render" in errors[0]


def test_native_touched_owner_paths_are_preserved(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    history = root / ".agents/memory/history/2026/08"
    native = history / "native.md"
    _record(native, "native", touched_owner_paths=["scripts/new_debrief.py"])
    assert debrief_index.row_for_path(native, root)["touched_owner_paths"] == [
        "scripts/new_debrief.py"
    ]


def test_legacy_files_touched_are_normalized_without_source_backfill(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    legacy = root / ".agents/memory/history/2026/08/legacy.md"
    _record(legacy, "legacy", files_touched=["AGENTS.md", "docs/index.qmd"])
    assert debrief_index.row_for_path(legacy, root)["touched_owner_paths"] == [
        "AGENTS.md",
        "docs/index.qmd",
    ]
    assert "touched_owner_paths:" not in legacy.read_text(encoding="utf-8")


def test_missing_touched_metadata_is_grandfathered_as_empty(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    missing = root / ".agents/memory/history/2026/08/record.md"
    assert debrief_index.row_for_path(missing, root)["touched_owner_paths"] == []


def test_grandfathered_missing_thread_is_indexed_as_null(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    source = root / ".agents/memory/history/2026/08/record.md"
    source.write_text(
        source.read_text(encoding="utf-8").replace(f"codex_thread: {THREAD_URI}\n", ""),
        encoding="utf-8",
    )
    row = debrief_index.row_for_path(source, root)
    assert "codex_thread" in row
    assert row["codex_thread"] is None


def _proposal_body(disposition: str = "proposed") -> str:
    return (
        "---\n"
        "id: proposal\n"
        "date: 2026-08-23\n"
        "title: Proposal\n"
        "status: done\n"
        "topics: [test]\n"
        "confidence: high\n"
        "canonical_updates_needed:\n"
        "  - .agents/references/human_owner_intent.md\n"
        f"codex_thread: {THREAD_URI}\n"
        "---\n\n"
        "## Human Intent Proposal\n"
        "- Proposed statement: Keep one owner per durable policy.\n"
        "- Evidence: exact bounded task evidence.\n"
        "- Current owner or conflict: current policy is unsettled.\n"
        "- Scope and target owner: scaffold guidance; exact owner path.\n"
        f"- Disposition: {disposition}\n"
    )


@pytest.mark.parametrize(
    "disposition", ["proposed", "accept", "reject", "narrow", "defer"]
)
def test_human_intent_proposal_body_uses_existing_target_and_review_dispositions(
    tmp_path: Path, disposition: str
) -> None:
    source = tmp_path / "proposal.md"
    source.write_text(_proposal_body(disposition), encoding="utf-8")
    assert (
        validator.check_proposal_body(
            source, [".agents/references/human_owner_intent.md"]
        )
        == []
    )


def test_proposal_target_requires_exact_five_field_body(tmp_path: Path) -> None:
    source = tmp_path / "proposal.md"
    source.write_text(
        _proposal_body().replace("- Evidence:", "- Extra: x\n- Evidence:"),
        encoding="utf-8",
    )
    assert validator.check_proposal_body(
        source, [".agents/references/human_owner_intent.md"]
    )


def test_jq_candidate_listing_requires_opening_and_proposed_disposition(
    tmp_path: Path,
) -> None:
    readme = (ROOT / ".agents/memory/README.md").read_text(encoding="utf-8")
    query = "jq -r 'select(.canonical_update_paths | index(\".agents/references/human_owner_intent.md\")) | .source_path'"
    assert query in readme
    legacy = tmp_path / "legacy.md"
    legacy.write_text("---\nstatus: done\n---\n\nBody\n", encoding="utf-8")
    assert validator.check_proposal_body(
        legacy, [".agents/references/human_owner_intent.md"]
    )
    proposed = tmp_path / "proposed.md"
    proposed.write_text(_proposal_body("proposed"), encoding="utf-8")
    assert (
        validator.check_proposal_body(
            proposed, [".agents/references/human_owner_intent.md"]
        )
        == []
    )


@pytest.mark.parametrize(
    "field, replacement",
    [
        ("Proposed statement", "<reusable statement>"),
        ("Evidence", "none"),
        ("Current owner or conflict", "<unresolved conflict>"),
        ("Scope and target owner", "none"),
    ],
)
def test_proposal_target_rejects_placeholders_and_none(
    tmp_path: Path, field: str, replacement: str
) -> None:
    source = tmp_path / "proposal.md"
    source.write_text(
        _proposal_body().replace(
            next(
                line
                for line in _proposal_body().splitlines()
                if line.startswith(f"- {field}:")
            ),
            f"- {field}: {replacement}",
        ),
        encoding="utf-8",
    )
    assert validator.check_proposal_body(
        source, [".agents/references/human_owner_intent.md"]
    )


def test_proposal_disposition_is_case_sensitive(tmp_path: Path) -> None:
    source = tmp_path / "proposal.md"
    source.write_text(_proposal_body("Accept"), encoding="utf-8")
    assert validator.check_proposal_body(
        source, [".agents/references/human_owner_intent.md"]
    )


def test_native_commit_section_is_required_and_nonempty(tmp_path: Path) -> None:
    source = tmp_path / "record.md"
    for section in ("", "## Commits\n"):
        source.write_text(f"---\nstatus: done\n---\n\n{section}", encoding="utf-8")
        assert validator.check_commit_links(
            source,
            {"repo_object_format": "sha1", "repo_head": "f" * 40},
            date(2026, 8, 23),
        )


def test_commit_links_require_matching_full_ancestor_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    (root / "file").write_text("one\n", encoding="utf-8")
    _git(root, "add", "file")
    _git(root, "commit", "-qm", "first")
    linked = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    (root / "file").write_text("two\n", encoding="utf-8")
    _git(root, "commit", "-qam", "second")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    source = root / "proposal.md"
    source.write_text(
        "---\nstatus: done\n---\n\n## Commits\n"
        f"- [{linked}](https://github.com/JanDuchscherer104/ARIA-NBV/commit/{linked}) — WP1: first\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validator, "REPO_ROOT", root)
    assert (
        validator.check_commit_links(
            source,
            {"repo_object_format": "sha1", "repo_head": head},
            date(2026, 8, 23),
        )
        == []
    )


@pytest.mark.parametrize(
    "line",
    [
        "- [abc](https://github.com/JanDuchscherer104/ARIA-NBV/commit/abc) — WP1: short",
        "- [0000000000000000000000000000000000000000](https://github.com/JanDuchscherer104/ARIA-NBV/commit/1111111111111111111111111111111111111111) — WP1: mismatch",
        "- [0000000000000000000000000000000000000000](https://github.com/JanDuchscherer104/ARIA-NBV/commit/0000000000000000000000000000000000000000) — WP1: missing",
    ],
)
def test_invalid_commit_link_forms_fail(tmp_path: Path, line: str) -> None:
    source = tmp_path / "record.md"
    source.write_text(
        f"---\nstatus: done\n---\n\n## Commits\n{line}\n", encoding="utf-8"
    )
    assert validator.check_commit_links(
        source,
        {"repo_object_format": "sha1", "repo_head": "f" * 40},
        date(2026, 8, 23),
    )


def test_none_commit_form_is_exclusive(tmp_path: Path) -> None:
    source = tmp_path / "record.md"
    source.write_text(
        "---\nstatus: done\n---\n\n## Commits\n- none — no repository commit (planning only)\n- none — no repository commit (duplicate)\n",
        encoding="utf-8",
    )
    assert validator.check_commit_links(
        source, {"repo_object_format": "sha1", "repo_head": "f" * 40}, date(2026, 8, 23)
    )


def test_final_workpackage_at_current_head_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    (root / "file").write_text("one\n", encoding="utf-8")
    _git(root, "add", "file")
    _git(root, "commit", "-qm", "first")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    source = root / "record.md"
    source.write_text(
        f"---\nstatus: done\n---\n\n## Commits\n- [{head}](https://github.com/JanDuchscherer104/ARIA-NBV/commit/{head}) — WP1: self\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validator, "REPO_ROOT", root)
    assert (
        validator.check_commit_links(
            source, {"repo_object_format": "sha1", "repo_head": head}, date(2026, 8, 23)
        )
        == []
    )


def test_linked_commit_cannot_modify_debrief_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    source = root / ".agents/memory/history/2026/08/record.md"
    source.write_text(
        source.read_text(encoding="utf-8")
        + "\n## Commits\n- none — no repository commit (planning only)\nchanged\n",
        encoding="utf-8",
    )
    _git(root, "add", str(source.relative_to(root)))
    _git(root, "commit", "-qm", "modify debrief")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "- none — no repository commit (planning only)",
            f"- [{head}](https://github.com/JanDuchscherer104/ARIA-NBV/commit/{head}) — WP1: modify",
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(validator, "REPO_ROOT", root)
    assert any(
        "creates or modifies the debrief source" in error
        for error in validator.check_commit_links(
            source, {"repo_object_format": "sha1", "repo_head": head}, date(2026, 8, 23)
        )
    )


def test_linked_commit_cannot_modify_debrief_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    index = root / ".agents/memory/index/debriefs.jsonl"
    index.parent.mkdir(parents=True)
    index.write_bytes(debrief_index.render_index(root))
    _git(root, "add", str(index.relative_to(root)))
    _git(root, "commit", "-qm", "modify debrief index")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    source = root / ".agents/memory/history/2026/08/record.md"
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "---\n\nBody\n",
            f"---\n\n## Commits\n- [{head}](https://github.com/JanDuchscherer104/ARIA-NBV/commit/{head}) — WP1: index\n\nBody\n",
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(validator, "REPO_ROOT", root)
    assert any(
        "creates or modifies the debrief index" in error
        for error in validator.check_commit_links(
            source, {"repo_object_format": "sha1", "repo_head": head}, date(2026, 8, 23)
        )
    )


def test_merge_commit_cannot_modify_debrief_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    index = root / ".agents/memory/index/debriefs.jsonl"
    index.parent.mkdir(parents=True)
    index.write_bytes(debrief_index.render_index(root))
    _git(root, "add", str(index.relative_to(root)))
    _git(root, "commit", "-qm", "add debrief index")
    _git(root, "checkout", "-qb", "side")
    index.write_text(index.read_text(encoding="utf-8") + "side\n", encoding="utf-8")
    _git(root, "add", str(index.relative_to(root)))
    _git(root, "commit", "-qm", "side index change")
    _git(root, "checkout", "-q", "main")
    (root / "file").write_text("main\n", encoding="utf-8")
    _git(root, "add", "file")
    _git(root, "commit", "-qm", "main change")
    _git(root, "merge", "--no-ff", "-m", "merge index change", "side")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    source = root / ".agents/memory/history/2026/08/record.md"
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "---\n\nBody\n",
            f"---\n\n## Commits\n- [{head}](https://github.com/JanDuchscherer104/ARIA-NBV/commit/{head}) — WP1: merge\n\nBody\n",
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(validator, "REPO_ROOT", root)
    assert any(
        "creates or modifies the debrief index" in error
        for error in validator.check_commit_links(
            source, {"repo_object_format": "sha1", "repo_head": head}, date(2026, 8, 23)
        )
    )


def test_check_history_records_rejects_stale_post_rebase_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    old_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    native = root / ".agents/memory/history/2026/08/native.md"
    native.write_text(
        "---\n"
        "id: native\n"
        "date: 2026-08-23\n"
        "title: Native\n"
        "status: done\n"
        "topics: []\n"
        "confidence: high\n"
        "canonical_updates_needed: []\n"
        f"codex_thread: {THREAD_URI}\n"
        "repo_object_format: sha1\n"
        f"repo_head: {old_head}\n"
        "repo_branch: main\n"
        "worktree_kind: primary\n"
        "---\n\n## Commits\n- none — no repository commit (planning only)\n",
        encoding="utf-8",
    )
    _git(root, "checkout", "--orphan", "rebased")
    _git(root, "rm", "-rf", ".")
    native.write_text(native.read_text(encoding="utf-8"), encoding="utf-8")
    _git(root, "add", str(native.relative_to(root)))
    _git(root, "commit", "-qm", "rebased live head")
    monkeypatch.setattr(validator, "REPO_ROOT", root)
    monkeypatch.setattr(validator, "HISTORY_ROOT", root / ".agents/memory/history")
    assert any(
        "repo_head is not an ancestor of live HEAD" in error
        for error in validator.check_history_records()
    )


@pytest.mark.parametrize(
    ("title", "expected_slug"),
    [
        ('Quoted "title"', "quoted_title"),
        ("Line one\nline two", "line_one_line_two"),
        ("Résumé #1: !important | result", "r_sum_1_important_result"),
    ],
)
def test_title_round_trips_generator_and_canonical_parser(
    tmp_path: Path, title: str, expected_slug: str
) -> None:
    path, body = new_debrief.render(
        date(2026, 8, 22),
        title,
        THREAD_ID,
        {
            "repo_object_format": "sha1",
            "repo_head": "a" * 40,
            "repo_branch": "main",
            "worktree_kind": "primary",
        },
    )
    assert path.name == f"2026-08-22_{expected_slug}.md"
    payload = body.split("\n---\n", 1)[0].removeprefix("---\n")
    assert yaml.safe_load(payload)["title"] == title
    assert "## Commits\n- none — no repository commit (not yet recorded)" in body
    source = tmp_path / "record.md"
    source.write_text(body, encoding="utf-8")
    assert validator.parse_frontmatter(source)["title"] == title


def test_fresh_native_debrief_is_validator_valid_before_manual_filling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    history_root = root / ".agents/memory/history"
    monkeypatch.setattr(new_debrief, "REPO_ROOT", root)
    monkeypatch.setattr(new_debrief, "HISTORY_ROOT", history_root)
    monkeypatch.setattr(validator, "REPO_ROOT", root)
    monkeypatch.setattr(validator, "HISTORY_ROOT", history_root)

    provenance = new_debrief.git_provenance()
    path, body = new_debrief.render(
        date(2026, 8, 23), "Fresh native debrief", THREAD_ID, provenance
    )
    path.write_text(body, encoding="utf-8")

    assert validator.check_history_records() == []


@pytest.mark.parametrize(
    "branch",
    ["!feature", "#feature", "|feature", "feature@x", 'feature"x', "föö"],
)
def test_branch_round_trips_generator_parser_validator_and_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, branch: str
) -> None:
    subprocess.run(
        ["git", "check-ref-format", "--branch", branch],
        check=True,
        capture_output=True,
    )
    root = _repo(tmp_path)
    _git(root, "branch", "-m", branch)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    _, body = new_debrief.render(
        date(2026, 8, 22),
        "Example",
        THREAD_ID,
        {
            "repo_object_format": "sha1",
            "repo_head": head,
            "repo_branch": branch,
            "worktree_kind": "linked",
        },
    )
    payload = body.split("\n---\n", 1)[0].removeprefix("---\n")
    frontmatter = yaml.safe_load(payload)
    assert "touched_owner_paths: []\n" in body
    assert frontmatter["repo_branch"] == branch
    source = root / ".agents/memory/history/2026/08/generated.md"
    source.write_text(body, encoding="utf-8")
    assert validator.parse_frontmatter(source)["repo_branch"] == branch
    monkeypatch.setattr(validator, "REPO_ROOT", root)
    monkeypatch.setattr(validator, "HISTORY_ROOT", root / ".agents/memory/history")
    assert validator.check_history_records() == []
    rows = [
        json.loads(line)
        for line in debrief_index.render_index(root).decode("utf-8").splitlines()
    ]
    generated = next(row for row in rows if row["id"] == "2026-08-22_example")
    assert generated["checkout_provenance"]["repo_branch"] == branch
    assert generated["checkout_provenance"]["repo_object_format"] == "sha1"


def test_backslash_branch_is_not_git_valid() -> None:
    result = subprocess.run(
        ["git", "check-ref-format", "--branch", r"feature\x"],
        check=False,
        capture_output=True,
    )
    assert result.returncode != 0


@pytest.mark.parametrize("codex_thread", [42, [], {}])
def test_index_parser_rejects_non_string_non_null_thread(codex_thread: object) -> None:
    row = {
        "source_path": ".agents/memory/history/2026/08/record.md",
        "source_sha256": "a" * 64,
        "id": "record",
        "date": "2026-08-21",
        "status": "done",
        "topics": [],
        "confidence": "high",
        "canonical_update_paths": [],
        "touched_owner_paths": [],
        "codex_thread": codex_thread,
    }
    with pytest.raises(TypeError, match="string or null"):
        debrief_index._parse_index((json.dumps(row) + "\n").encode())


def test_index_parser_requires_explicit_thread_key() -> None:
    row = {
        "source_path": ".agents/memory/history/2026/08/record.md",
        "source_sha256": "a" * 64,
        "id": "record",
        "date": "2026-08-21",
        "status": "done",
        "topics": [],
        "confidence": "high",
        "canonical_update_paths": [],
        "touched_owner_paths": [],
    }
    with pytest.raises(KeyError, match="codex_thread"):
        debrief_index._parse_index((json.dumps(row) + "\n").encode())


@pytest.mark.parametrize(
    "provenance",
    [
        {
            "repo_object_format": "sha1",
            "repo_head": "a" * 64,
            "repo_branch": "main",
            "worktree_kind": "primary",
        },
        {
            "repo_object_format": "sha256",
            "repo_head": "a" * 40,
            "repo_branch": "main",
            "worktree_kind": "primary",
        },
        {
            "repo_object_format": "unknown",
            "repo_head": "a" * 40,
            "repo_branch": "main",
            "worktree_kind": "primary",
        },
    ],
)
def test_index_parser_rejects_mismatched_provenance(
    provenance: dict[str, str],
) -> None:
    row = {
        "source_path": ".agents/memory/history/2026/08/record.md",
        "source_sha256": "a" * 64,
        "id": "record",
        "date": "2026-08-22",
        "status": "done",
        "topics": [],
        "confidence": "high",
        "canonical_update_paths": [],
        "touched_owner_paths": [],
        "codex_thread": THREAD_URI,
        "checkout_provenance": provenance,
    }
    with pytest.raises((TypeError, ValueError), match="checkout_provenance"):
        debrief_index._parse_index((json.dumps(row) + "\n").encode())


def test_query_prints_original_source(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)
    index = root / ".agents/memory/index/debriefs.jsonl"
    index.parent.mkdir(parents=True)
    index.write_bytes(debrief_index.render_index(root))
    assert debrief_index._query(root, "record") == 0
    assert "Body" in capsys.readouterr().out


def test_query_fails_closed_on_stale_and_malformed_index(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)
    index = root / ".agents/memory/index/debriefs.jsonl"
    index.parent.mkdir(parents=True)
    index.write_bytes(debrief_index.render_index(root))
    source = root / ".agents/memory/history/2026/08/record.md"
    source.write_text(source.read_text(encoding="utf-8") + "stale\n", encoding="utf-8")
    assert debrief_index._query(root, "record") == 1
    assert "stale debrief index" in capsys.readouterr().err
    index.write_text("{not-json}\n", encoding="utf-8")
    assert debrief_index._query(root, "record") == 1
    assert "malformed debrief index" in capsys.readouterr().err


@pytest.mark.parametrize(
    "query",
    [
        "../secret.md",
        "/tmp/secret.md",
        "docs/secret.md",
        ".agents/memory/history/../../secret.md",
    ],
)
def test_query_rejects_paths_outside_history(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    query: str,
) -> None:
    root = _repo(tmp_path)
    secret = root / "secret.md"
    secret.write_text("must not print\n", encoding="utf-8")
    index = root / ".agents/memory/index/debriefs.jsonl"
    index.parent.mkdir(parents=True)
    index.write_bytes(debrief_index.render_index(root))
    assert debrief_index._query(root, query) == 1
    captured = capsys.readouterr()
    assert "unsafe debrief query path" in captured.err
    assert "must not print" not in captured.out


def test_generation_and_check_reject_symlinked_history_source(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    source = root / ".agents/memory/history/2026/08/record.md"
    secret = root / "secret.md"
    secret.write_bytes(source.read_bytes())
    source.unlink()
    source.symlink_to(secret)
    index = root / ".agents/memory/index/debriefs.jsonl"
    with pytest.raises(ValueError, match="symlinked debrief source"):
        debrief_index.render_index(root)
    errors = debrief_index.check_index(root, index)
    assert errors and "symlinked debrief source" in errors[0]


def test_generation_and_check_reject_source_resolved_outside_history(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    month = root / ".agents/memory/history/2026/08"
    outside = tmp_path / "outside-month"
    month.rename(outside)
    month.symlink_to(outside, target_is_directory=True)
    index = root / ".agents/memory/index/debriefs.jsonl"
    with pytest.raises(ValueError, match="resolves outside history"):
        debrief_index.render_index(root)
    errors = debrief_index.check_index(root, index)
    assert errors and "resolves outside history" in errors[0]


def test_provenance_is_full_and_linked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    monkeypatch.setattr(new_debrief, "REPO_ROOT", root)
    provenance = new_debrief.git_provenance()
    assert provenance["repo_object_format"] == "sha1"
    assert len(provenance["repo_head"]) == 40
    assert provenance["repo_branch"] == "main"
    _git(root, "branch", "-m", "feature@x")
    assert new_debrief.git_provenance()["repo_branch"] == "feature@x"
    _git(root, "checkout", "--detach", "-q")
    assert new_debrief.git_provenance()["repo_branch"] == "detached"
    linked = tmp_path / "linked"
    _git(root, "worktree", "add", "-q", "-b", "linked-branch", str(linked))
    monkeypatch.setattr(new_debrief, "REPO_ROOT", linked)
    assert new_debrief.git_provenance()["worktree_kind"] == "linked"


def test_sha256_provenance_round_trips_generator_validator_and_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path, object_format="sha256")
    monkeypatch.setattr(new_debrief, "REPO_ROOT", root)
    provenance = new_debrief.git_provenance()
    assert provenance["repo_object_format"] == "sha256"
    assert len(provenance["repo_head"]) == 64

    _, body = new_debrief.render(
        date(2026, 8, 22), "SHA-256 repository", THREAD_ID, provenance
    )
    source = root / ".agents/memory/history/2026/08/generated.md"
    source.write_text(body, encoding="utf-8")
    monkeypatch.setattr(validator, "REPO_ROOT", root)
    monkeypatch.setattr(validator, "HISTORY_ROOT", root / ".agents/memory/history")
    assert validator.check_history_records() == []
    row = debrief_index.row_for_path(source, root)
    assert row["checkout_provenance"] == provenance
    debrief_index._parse_index(debrief_index.render_index(root))


def test_nudge_requires_matching_thread_and_ignores_runtime_only(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    script = ROOT / "scripts/debrief_nudge.sh"
    today = date.today()
    history_dir = root / ".agents/memory/history" / f"{today:%Y/%m}"
    env = {
        **os.environ,
        "DEBRIEF_NUDGE_THRESHOLD": "1",
        "CODEX_THREAD_ID": THREAD_ID,
    }
    initial = root / ".agents/memory/history/2026/08/record.md"
    initial.write_text(
        initial.read_text(encoding="utf-8").replace(
            THREAD_ID,
            "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        ),
        encoding="utf-8",
    )
    (root / "README.md").write_text("change\n", encoding="utf-8")
    warning = subprocess.run(
        [script], cwd=root, env=env, text=True, capture_output=True
    )
    assert "[debrief-nudge]" in warning.stderr
    matching_path = history_dir / f"{today:%Y-%m-%d}_matching.md"
    _record(matching_path, "matching")
    matching = matching_path.read_text(encoding="utf-8")
    assert THREAD_ID in matching
    suppressed = subprocess.run(
        [script], cwd=root, env=env, text=True, capture_output=True
    )
    assert suppressed.stderr == ""
    other_env = {**env, "CODEX_THREAD_ID": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"}
    other = subprocess.run(
        [script], cwd=root, env=other_env, text=True, capture_output=True
    )
    assert "[debrief-nudge]" in other.stderr
    (root / "README.md").unlink()
    matching_path.unlink()
    _git(root, "add", "-A")
    runtime = subprocess.run(
        [script], cwd=root, env=env, text=True, capture_output=True
    )
    assert runtime.stderr == ""


def test_no_thread_nudge_requires_related_touched_paths(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    script = ROOT / "scripts/debrief_nudge.sh"
    today = date.today()
    history_dir = root / ".agents/memory/history" / f"{today:%Y/%m}"
    env = _env_without_thread(DEBRIEF_NUDGE_THRESHOLD="1")
    (root / "README.md").write_text("change\n", encoding="utf-8")
    unrelated = history_dir / f"{today:%Y-%m-%d}_unrelated.md"
    _record(
        unrelated,
        "unrelated",
        record_date=today.isoformat(),
        touched_owner_paths=["docs/index.qmd"],
    )
    warning = subprocess.run(
        [script], cwd=root, env=env, text=True, capture_output=True
    )
    assert "[debrief-nudge]" in warning.stderr
    related = history_dir / f"{today:%Y-%m-%d}_related.md"
    _record(
        related,
        "related",
        record_date=today.isoformat(),
        touched_owner_paths=["README.md"],
    )
    suppressed = subprocess.run(
        [script], cwd=root, env=env, text=True, capture_output=True
    )
    assert suppressed.stderr == ""


def test_nudge_explicit_eligibility_overrides_auto_heuristic(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    script = ROOT / "scripts/debrief_nudge.sh"
    (root / "README.md").write_text("change\n", encoding="utf-8")
    base = _env_without_thread(DEBRIEF_NUDGE_THRESHOLD="99")
    auto = subprocess.run([script], cwd=root, env=base, text=True, capture_output=True)
    assert auto.stderr == ""
    eligible = subprocess.run(
        [script],
        cwd=root,
        env={**base, "DEBRIEF_NUDGE_ELIGIBLE": "true"},
        text=True,
        capture_output=True,
    )
    assert "[debrief-nudge]" in eligible.stderr
    ineligible = subprocess.run(
        [script],
        cwd=root,
        env={
            **base,
            "DEBRIEF_NUDGE_THRESHOLD": "1",
            "DEBRIEF_NUDGE_ELIGIBLE": "false",
        },
        text=True,
        capture_output=True,
    )
    assert ineligible.stderr == ""
