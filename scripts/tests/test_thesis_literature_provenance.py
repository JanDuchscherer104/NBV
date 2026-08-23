"""Deterministic provenance checks for the active Related Work surface."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RELATED_WORK = ROOT / "docs/typst/thesis/sections/02-foundations/02-01-related-work.typ"
BIBLIOGRAPHIES = (ROOT / "docs/references.bib", ROOT / "docs/references-qh.bib")
LOCATOR_RE = re.compile(
    r"(?P<path>(?:aria_nbv|tests|docs)/[^:\s]+):(?P<start>\d+)"
    r"(?:-(?P<end>\d+))?"
)
CITATION_RE = re.compile(r"@([A-Za-z][A-Za-z0-9_:-]*)")


def _paragraphs_with_adjacent_evidence(
    path: Path,
) -> list[tuple[str, list[str]]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    result: list[tuple[str, list[str]]] = []
    index = 0
    while index < len(lines):
        if not lines[index].strip() or lines[index].lstrip().startswith("//"):
            index += 1
            continue
        paragraph: list[str] = []
        while index < len(lines) and lines[index].strip():
            if lines[index].lstrip().startswith("//"):
                break
            paragraph.append(lines[index])
            index += 1
        text = " ".join(paragraph).strip()
        if not text or text.startswith(("#import", "=", "==")):
            continue
        while index < len(lines) and not lines[index].strip():
            index += 1
        evidence: list[str] = []
        if index < len(lines) and lines[index].strip() == "// evidence:":
            index += 1
            while index < len(lines) and lines[index].lstrip().startswith("//"):
                evidence.append(lines[index])
                index += 1
        result.append((text, evidence))
    return result


def _bibliography_keys() -> set[str]:
    keys: set[str] = set()
    for path in BIBLIOGRAPHIES:
        keys.update(
            match.group(1)
            for match in re.finditer(
                r"^\s*@\w+\s*\{\s*([^,\s]+)",
                path.read_text(encoding="utf-8"),
                re.MULTILINE,
            )
        )
    return keys


def _evidence_citations_and_locators(
    evidence: list[str],
) -> tuple[set[str], list[tuple[Path, int, int]]]:
    citations: set[str] = set()
    locators: list[tuple[Path, int, int]] = []
    for line in evidence:
        citations.update(CITATION_RE.findall(line))
        for match in LOCATOR_RE.finditer(line):
            start = int(match.group("start"))
            end = int(match.group("end") or match.group("start"))
            locators.append((ROOT / match.group("path"), start, end))
    return citations, locators


def _evidence_entries(
    evidence: list[str],
) -> list[tuple[str, list[tuple[Path, int, int]]]]:
    """Return each evidence bullet's citation key and its exact source locators."""
    entries: list[tuple[str, list[tuple[Path, int, int]]]] = []
    for line in evidence:
        keys = CITATION_RE.findall(line)
        locators = []
        for match in LOCATOR_RE.finditer(line):
            start = int(match.group("start"))
            end = int(match.group("end") or match.group("start"))
            locators.append((ROOT / match.group("path"), start, end))
        entries.extend((key, locators) for key in keys)
    return entries


def _has_active_source_line(path: Path, start: int, end: int) -> bool:
    """Return whether a locator range contains a non-comment source line.

    This is a lexical locator check only. It does not establish that the active
    passage semantically entails the thesis claim; that remains human review.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines[start - 1 : end]:
        stripped = line.strip()
        if not stripped or stripped.startswith(("%", "//")):
            continue
        if path.suffix == ".tex":
            content = re.split(r"(?<!\\)%", line, maxsplit=1)[0].strip()
            if not content or content.startswith("%"):
                continue
        return True
    return False


def test_related_work_has_four_conceptual_tension_paragraphs() -> None:
    paragraphs = _paragraphs_with_adjacent_evidence(RELATED_WORK)
    assert len(paragraphs) == 4
    assert [
        "tension between cheap coverage-oriented selection",
        "second tension",
        "third tension",
        "fourth tension",
    ] == [
        next(
            phrase
            for phrase in (
                "tension between cheap coverage-oriented selection",
                "second tension",
                "third tension",
                "fourth tension",
            )
            if phrase in paragraph
        )
        for paragraph, _ in paragraphs
    ]


def test_each_related_work_paragraph_has_adjacent_resolvable_source_evidence() -> None:
    bibliography_keys = _bibliography_keys()
    for paragraph, evidence in _paragraphs_with_adjacent_evidence(RELATED_WORK):
        cited = set(CITATION_RE.findall(paragraph))
        evidence_keys, locators = _evidence_citations_and_locators(evidence)
        assert cited, (
            f"claim-bearing Related Work paragraph lacks a citation: {paragraph}"
        )
        assert evidence, f"missing adjacent // evidence: block: {paragraph}"
        assert cited <= bibliography_keys
        assert cited <= evidence_keys
        assert locators, f"missing exact source locator: {paragraph}"


def test_each_related_work_citation_key_has_a_locator_on_its_evidence_entry() -> None:
    """Identity and lexical support are executable; entailment remains human review."""
    for paragraph, evidence in _paragraphs_with_adjacent_evidence(RELATED_WORK):
        cited = set(CITATION_RE.findall(paragraph))
        entries = _evidence_entries(evidence)
        assert cited == {key for key, _ in entries}, paragraph
        for key, locators in entries:
            assert locators, f"citation {key} lacks a locator on its own evidence entry"


def test_related_work_passages_are_active_and_semantic_entailment_is_human_review() -> (
    None
):
    """The checker rejects comment-only locators but does not judge entailment."""
    paragraphs = _paragraphs_with_adjacent_evidence(RELATED_WORK)
    assert all(
        paragraph and not paragraph.startswith("//") for paragraph, _ in paragraphs
    )
    documentation = _has_active_source_line.__doc__ or ""
    assert "semantically entails" in documentation.lower()
    assert "human review" in documentation.lower()


def test_related_work_source_locators_are_existing_in_range_lines() -> None:
    for _, evidence in _paragraphs_with_adjacent_evidence(RELATED_WORK):
        _, locators = _evidence_citations_and_locators(evidence)
        for path, start, end in locators:
            assert path.is_file(), path
            line_count = len(path.read_text(encoding="utf-8").splitlines())
            assert 1 <= start <= end <= line_count, (path, start, end, line_count)
            assert _has_active_source_line(path, start, end), (path, start, end)


def test_source_locator_rejects_comment_only_ranges(tmp_path: Path) -> None:
    source = tmp_path / "commented.tex"
    source.write_text("% no support here\n% still commented\n", encoding="utf-8")
    assert not _has_active_source_line(source, 1, 2)

    source.write_text("% no support here\nActive source text.\n", encoding="utf-8")
    assert _has_active_source_line(source, 1, 2)
