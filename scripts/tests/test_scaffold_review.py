from __future__ import annotations

import json
from pathlib import Path

from scripts.scaffold_review import _deduplicate, _render_html, load_corpus, load_omx


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

    assert [item.id for item in items] == ["cluster-1"]
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
    assert "Keep it simple." in rendered
    assert "\nexport.onclick" not in rendered


def load_corpus_from_rows(path: Path, statement: str, cluster_id: str):
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
