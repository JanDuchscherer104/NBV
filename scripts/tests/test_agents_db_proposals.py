from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import agents_db  # noqa: E402


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def proposal_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repo"
    agents = root / ".agents"
    history = agents / "memory/history/2026/08"
    history.mkdir(parents=True)
    (agents / "issues.toml").write_text("# issues\n", encoding="utf-8")
    (agents / "todos.toml").write_text("# todos\n", encoding="utf-8")
    (agents / "refactors.toml").write_text("# refactors\n", encoding="utf-8")
    (agents / "resolved.toml").write_text("# resolved\n", encoding="utf-8")
    (agents / "proposals.toml").write_text("# proposals\n", encoding="utf-8")
    (agents / "proposals_resolved.toml").write_text(
        "# resolved proposals\n", encoding="utf-8"
    )
    (history / "source.md").write_text("proposal evidence\n", encoding="utf-8")
    (root / "owner.md").write_text("old\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    monkeypatch.setattr(agents_db, "REPO_ROOT", root)
    monkeypatch.setattr(agents_db, "AGENTS_ROOT", agents)
    monkeypatch.setattr(
        agents_db,
        "ACTIVE_FILES",
        {
            "issue": agents / "issues.toml",
            "todo": agents / "todos.toml",
            "refactor": agents / "refactors.toml",
        },
    )
    monkeypatch.setattr(agents_db, "RESOLVED_FILE", agents / "resolved.toml")
    monkeypatch.setattr(agents_db, "PROPOSALS_FILE", agents / "proposals.toml")
    monkeypatch.setattr(
        agents_db, "RESOLVED_PROPOSALS_FILE", agents / "proposals_resolved.toml"
    )
    return root


def _open() -> int:
    return agents_db.proposal_open(
        "proposal-001",
        source_debrief=".agents/memory/history/2026/08/source.md",
        target_owner="owner.md",
        statement="Use one factory owner for custom configuration.",
        evidence="Current-user preference repeated across configuration tasks.",
        conflict="No accepted scoped requirement settles the construction pattern.",
        scope="Python configuration construction",
    )


def test_open_and_defer_retains_active_typed_receipt(proposal_repo: Path) -> None:
    assert _open() == 0
    assert agents_db.proposal_review(
        "proposal-001",
        disposition="defer",
        reviewer="current-user",
        receipt="current task: defer pending another implementation",
        owner_edit_commit=None,
        proof=None,
        reason=None,
    ) == 0
    active = agents_db._load_proposals(agents_db.PROPOSALS_FILE)
    assert active[0]["status"] == "deferred"
    assert active[0]["disposition"] == "defer"
    assert agents_db.validate(quiet=True) == 0


def test_accept_requires_target_commit_then_resolves(proposal_repo: Path) -> None:
    assert _open() == 0
    (proposal_repo / "owner.md").write_text("new\n", encoding="utf-8")
    _git(proposal_repo, "add", "owner.md")
    _git(proposal_repo, "commit", "-qm", "install proposal")
    commit = _git(proposal_repo, "rev-parse", "HEAD")
    assert agents_db.proposal_review(
        "proposal-001",
        disposition="accept",
        reviewer="current-user",
        receipt="current task: accept factory policy",
        owner_edit_commit=commit,
        proof="pytest -q tests/config",
        reason=None,
    ) == 0
    assert agents_db.proposal_resolve("proposal-001") == 0
    assert agents_db._load_proposals(agents_db.PROPOSALS_FILE) == []
    resolved = agents_db._load_proposals(agents_db.RESOLVED_PROPOSALS_FILE)
    assert resolved[0]["target_owner"] == "owner.md"
    assert resolved[0]["owner_edit_commit"] == commit
    assert agents_db.validate(quiet=True) == 0


def test_accept_rejects_unrelated_commit(proposal_repo: Path) -> None:
    assert _open() == 0
    (proposal_repo / "other.md").write_text("other\n", encoding="utf-8")
    _git(proposal_repo, "add", "other.md")
    _git(proposal_repo, "commit", "-qm", "unrelated")
    commit = _git(proposal_repo, "rev-parse", "HEAD")
    assert agents_db.proposal_review(
        "proposal-001",
        disposition="accept",
        reviewer="current-user",
        receipt="current task: accept",
        owner_edit_commit=commit,
        proof="proof",
        reason=None,
    ) == 1
