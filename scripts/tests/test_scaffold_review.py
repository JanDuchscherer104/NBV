from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
from argparse import Namespace
from pathlib import Path

import pytest

from scripts.scaffold_review import (
    ReviewItem,
    _deduplicate,
    _render_html,
    build,
    load_corpus,
    load_omx,
    load_pr,
    load_review_items,
    summarize,
)


def test_load_corpus_uses_reconciled_statements_without_raw_messages(
    tmp_path: Path,
) -> None:
    path = tmp_path / "clusters.jsonl"
    path.write_text(
        json.dumps(
            {
                "cluster_id": "cluster-1",
                "canonical_statement": "Keep one authoritative owner.",
                "themes": ["core", "privacy_provenance"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    items = load_corpus(path)

    assert [item.id for item in items] == ["intent:cluster-1"]
    assert items[0].statement == "Keep one authoritative owner."
    assert items[0].sources == ("private:clusters.jsonl#cluster-1",)


def test_load_omx_limits_extraction_to_goal_sections(tmp_path: Path) -> None:
    path = tmp_path / "plan.md"
    path.write_text(
        "# Plan\n\n## Outcome\n\n- Keep the review interface small and source backed.\n"
        "\n## Implementation detail\n\n- This must not become a review item.\n",
        encoding="utf-8",
    )

    items = load_omx([path])

    assert len(items) == 1
    assert "interface small" in items[0].statement


def test_deduplicate_collapses_equivalent_statements(tmp_path: Path) -> None:
    path = tmp_path / "clusters.jsonl"
    first = load_corpus_from_rows(path, "One owner of truth.", "cluster-1")
    second = load_corpus_from_rows(path, "One owner of truth!", "cluster-2")

    assert len(_deduplicate([first, second])) == 1


def test_rendered_board_has_review_and_export_controls(tmp_path: Path) -> None:
    item = load_corpus_from_rows(
        tmp_path / "clusters.jsonl", "Keep it simple.", "cluster-1"
    )

    rendered = _render_html([item])

    assert "Y · Accept" in rendered
    assert "N · Reject" in rendered
    assert "C · Revise" in rendered
    assert "Export decisions" in rendered
    assert "localStorage" in rendered
    assert "dataset_digest" in rendered
    assert "statement:x.statement" in rendered
    assert "aria-pressed" in rendered
    assert "Keep it simple." in rendered
    assert "\nexport.onclick" not in rendered


def test_browser_escapes_content_and_exports_review_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    if chrome is None:
        pytest.skip("headless Chrome is not installed")
    item = ReviewItem(
        id="review:xss",
        kind="finding",
        theme="core",
        title="<img src=x onerror=alert(1)>",
        statement="</script><img src=x onerror=alert(1)>",
        sources=("private:test",),
    )
    rendered = _render_html(_deduplicate([item])).replace(
        "</script></body>",
        "decide('yes');document.body.dataset.answer=decisions[ITEMS[0].id].answer;"
        "document.body.dataset.aria=document.querySelector('.yes').getAttribute('aria-pressed');"
        "document.body.dataset.payload=btoa(JSON.stringify(exportPayload()));"
        "</script></body>",
    )
    page = tmp_path / "review.html"
    page.write_text(rendered, encoding="utf-8")

    result = subprocess.run(
        [
            chrome,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            f"--user-data-dir={tmp_path / 'chrome'}",
            "--dump-dom",
            page.as_uri(),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert 'data-answer="yes"' in result.stdout
    assert 'data-aria="true"' in result.stdout
    assert '<img src="x"' not in result.stdout
    match = re.search(r'data-payload="([A-Za-z0-9+/=]+)"', result.stdout)
    assert match is not None
    payload = json.loads(base64.b64decode(match.group(1)))
    assert payload["schema_version"] == 2
    assert payload["decisions"][0]["item_id"] == item.id
    assert payload["decisions"][0]["sources"] == ["private:test"]

    decisions = tmp_path / "decisions.json"
    decisions.write_text(json.dumps(payload), encoding="utf-8")
    summarize(Namespace(decisions=decisions))
    assert item.statement in capsys.readouterr().out


def test_load_pr_emits_observations_only(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "number": 30,
        "title": "Large scaffold change",
        "state": "OPEN",
        "isDraft": True,
        "headRefName": "feature",
        "headRefOid": "a" * 40,
        "baseRefName": "main",
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "UNSTABLE",
        "additions": 20,
        "deletions": 10,
        "changedFiles": 5,
        "statusCheckRollup": [{"name": "ci", "conclusion": "FAILURE"}],
        "url": "https://example.test/pr/30",
    }
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, stdout=json.dumps(payload), stderr=""
        ),
    )

    items = load_pr("owner/repo", 30)

    assert len(items) == 3
    assert all("split" not in item.statement.casefold() for item in items)
    assert all("recommend" not in item.statement.casefold() for item in items)


def test_loads_explicit_owner_findings(tmp_path: Path) -> None:
    path = tmp_path / "items.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "owner-choice",
                "title": "Owner choice",
                "statement": "Keep this recommendation explicit.",
                "theme": "core",
                "sources": ["private:review"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    item = load_review_items([path])[0]

    assert item.id == "review:owner-choice"
    assert item.statement == "Keep this recommendation explicit."


def test_rejects_unknown_theme_and_duplicate_ids(tmp_path: Path) -> None:
    malicious = tmp_path / "items.jsonl"
    malicious.write_text(
        json.dumps(
            {
                "id": "bad",
                "title": "Bad",
                "statement": "Bad",
                "theme": "<img src=x onerror=alert(1)>",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown review theme"):
        load_review_items([malicious])

    item = load_corpus_from_rows(tmp_path / "clusters.jsonl", "One.", "same")
    duplicate = ReviewItem(**{**item.__dict__, "statement": "Two."})
    with pytest.raises(ValueError, match="duplicate review item id"):
        _deduplicate([item, duplicate])


def test_build_rejects_tracked_repo_output(tmp_path: Path) -> None:
    args = type(
        "Args",
        (),
        {
            "corpus": None,
            "repo_root": tmp_path,
            "omx": [],
            "items": [],
            "no_pr": True,
            "github_repo": "unused",
            "pr": 0,
            "output": tmp_path / "docs" / "review",
        },
    )()

    with pytest.raises(ValueError, match="must remain under .artifacts"):
        build(args)


def test_build_writes_private_artifact_bundle(tmp_path: Path) -> None:
    output = tmp_path / ".artifacts" / "review"
    args = Namespace(
        corpus=None,
        repo_root=tmp_path,
        omx=[],
        items=[],
        no_pr=True,
        github_repo="unused",
        pr=0,
        output=output,
    )

    assert build(args) == 0
    assert (output / "index.html").is_file()
    assert json.loads((output / "manifest.json").read_text())["item_count"] == 8


def load_corpus_from_rows(path: Path, statement: str, cluster_id: str) -> ReviewItem:
    path.write_text(
        json.dumps(
            {
                "cluster_id": cluster_id,
                "canonical_statement": statement,
                "themes": ["core"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return load_corpus(path)[0]
