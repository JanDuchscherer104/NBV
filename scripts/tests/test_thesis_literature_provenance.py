"""Deterministic provenance checks for the active Foundations literature."""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from literature_catalog import (  # noqa: E402
    LiteratureAssets,
    LiteratureCatalog,
    LiteratureCatalogConfig,
    load_literature_catalog,
)


FOUNDATIONS_LITERATURE = tuple(
    ROOT / "docs/typst/thesis/sections/02-foundations" / name
    for name in (
        "02-01-active-perception-and-view-utility.typ",
        "02-02-targets-actions-and-support.typ",
        "02-03-candidate-support-and-motion-feasibility.typ",
        "02-04-finite-horizon-value-learning.typ",
        "02-05-egocentric-and-geometric-representations.typ",
        "02-06-literature-positioning.typ",
    )
)
LITERATURE_ROOT = ROOT / "docs/literature"
GLOSSARY = ROOT / "docs/typst/shared/glossary.typ"
LOCATOR_RE = re.compile(
    r"(?P<path>docs/literature/[^\s:,()]+)"
    r"(?::(?P<start>\d+)(?:-(?P<end>\d+))?"
    r"|#(?P<kind>page|section|figure|table)=(?P<selector>[^\s,()]+))"
)
CITATION_RE = re.compile(r"@([A-Za-z][A-Za-z0-9_:-]*)")
GLOSSARY_KEY_RE = re.compile(
    r'^\s{4}key:\s*"([A-Za-z][A-Za-z0-9_.-]*)",\s*$', re.MULTILINE
)
LOCATOR_TEXT = r"docs/literature/[^\s,()]+"
EVIDENCE_LINE_RE = re.compile(
    r"^[ \t]*//[ \t]+-[ \t]+"
    r"(?P<key>@[A-Za-z][A-Za-z0-9_:-]*)[ \t]+->[ \t]+"
    rf"(?P<locators>(?:{LOCATOR_TEXT})"
    rf"(?:[ \t]*,[ \t]*(?:{LOCATOR_TEXT}))*"
    r")[ \t]*(?:\([^\r\n]*\))?[ \t]*$"
)
EVIDENCE_MARKER_LIKE_RE = re.compile(r"^[ \t]*//[ \t]*evidence[ \t]*:", re.IGNORECASE)


@dataclass(frozen=True)
class SourceLocator:
    """A direct source locator: ``path:line[-line]`` or ``path#selector``.

    Selector locators are restricted to ``#page=n[-n]``, ``#section=id``,
    ``#figure=id``, and ``#table=id``.  All paths are repository-relative and
    must resolve to existing files below ``docs/literature``.
    """

    path: Path
    kind: str
    start: int | None = None
    end: int | None = None
    selector: str | None = None


def _literature_catalog() -> LiteratureCatalog:
    """Load the canonical literature identity and asset owner."""
    return load_literature_catalog(LiteratureCatalogConfig(repo_root=ROOT))


def _literature_assets() -> dict[str, LiteratureAssets]:
    """Resolve manifest-owned local assets by citation identity."""
    catalog = _literature_catalog()
    return {
        key: assets
        for key in catalog.joined
        if (assets := catalog.assets_for(key)) is not None
    }


def _paragraph_citations(text: str, catalog: LiteratureCatalog) -> set[str]:
    """Classify every Typst reference as a citation or canonical glossary key."""
    references = set(CITATION_RE.findall(text))
    glossary_keys = set(GLOSSARY_KEY_RE.findall(GLOSSARY.read_text(encoding="utf-8")))
    unknown = references - set(catalog.bibliography) - glossary_keys
    if unknown:
        raise AssertionError(
            f"unknown Typst reference(s): {', '.join(sorted(unknown))}"
        )
    return set(catalog.citations(text))


def _path_is_owned(path: Path, assets: LiteratureAssets) -> bool:
    """Return whether a locator path is inside the cited work's local assets."""
    return any(path == root or path.is_relative_to(root) for root in assets.roots) or (
        path in assets.pdfs
    )


def _selector_exists(path: Path, kind: str, selector: str) -> bool:
    """Resolve a section, figure, or table label in a local text source."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if kind == "section":
        return bool(
            re.search(
                rf"\\(?:sub)*section\*?\s*(?:\[[^]]*\])?\{{[^}}]*\}}\s*"
                rf"(?:\\label\{{{re.escape(selector)}\}}|<{re.escape(selector)}>)",
                text,
            )
        )
    label = rf"(?:\\label\{{{re.escape(selector)}\}}|<{re.escape(selector)}>)"
    return bool(
        re.search(
            rf"\\begin\{{(?P<environment>{kind}\*?)\}}.*?{label}.*?"
            rf"\\end\{{(?P=environment)\}}",
            text,
            re.DOTALL,
        )
    ) or bool(re.search(rf"#{kind}\s*\(.*?<{re.escape(selector)}>", text, re.DOTALL))


def _pdf_page_count(path: Path) -> int:
    """Read the page count through the bounded PDF-aware Poppler utility."""
    if path.stat().st_size > 64 * 1024 * 1024:
        raise AssertionError(f"PDF is too large for bounded page validation: {path}")
    try:
        result = subprocess.run(
            ["pdfinfo", str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        raise AssertionError(
            "pdfinfo is required for bounded PDF page validation"
        ) from error
    if result.returncode:
        raise AssertionError(f"pdfinfo failed for {path}: {result.stderr.strip()}")
    match = re.search(r"^Pages:\s*(\d+)\s*$", result.stdout, re.MULTILINE)
    if match is None:
        raise AssertionError(f"pdfinfo returned no page count for {path}")
    return int(match.group(1))


def _resolve_locator(locator: SourceLocator, key: str) -> None:
    """Require a typed locator to resolve within the cited work's assets."""
    assets = _literature_assets().get(key)
    if assets is None or not _path_is_owned(locator.path, assets):
        raise AssertionError(
            f"source path is not owned by citation @{key}: {locator.path}"
        )
    if locator.kind == "line":
        assert locator.start is not None and locator.end is not None
        line_count = len(locator.path.read_text(encoding="utf-8").splitlines())
        if not 1 <= locator.start <= locator.end <= line_count:
            raise AssertionError(f"line locator is out of range: {locator.path}")
        if not _has_active_source_line(locator.path, locator.start, locator.end):
            raise AssertionError(f"line locator has no active source: {locator.path}")
    elif locator.kind == "page":
        if locator.path.suffix.lower() != ".pdf":
            raise AssertionError(f"page locator requires a PDF: {locator.path}")
        assert locator.selector is not None
        page_range = re.fullmatch(r"(\d+)(?:-(\d+))?", locator.selector)
        assert page_range is not None
        start = int(page_range.group(1))
        end = int(page_range.group(2) or page_range.group(1))
        if not 1 <= start <= end <= _pdf_page_count(locator.path):
            raise AssertionError(f"page locator is out of range: {locator.path}")
    else:
        assert locator.selector is not None
        if locator.path.suffix.lower() != ".tex" or not _selector_exists(
            locator.path, locator.kind, locator.selector
        ):
            raise AssertionError(
                f"{locator.kind} selector does not resolve for @{key}: {locator.selector}"
            )


def _paragraphs_with_adjacent_evidence(
    path: Path,
) -> list[tuple[str, list[str]]]:
    """Parse claim blocks and fail closed on every evidence block."""
    lines = path.read_text(encoding="utf-8").splitlines()
    result: list[tuple[str, list[str]]] = []
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if EVIDENCE_MARKER_LIKE_RE.match(lines[index]) and stripped != "// evidence:":
            raise AssertionError(f"malformed evidence marker at line {index + 1}")
        if stripped == "// evidence:":
            raise AssertionError(f"orphan evidence block at line {index + 1}")
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
            if not evidence:
                raise AssertionError(f"empty evidence block after: {text}")
            _evidence_entries(evidence, resolve=False)
        result.append((text, evidence))
    markers = [
        number
        for number, line in enumerate(lines, start=1)
        if line.strip() == "// evidence:"
    ]
    parsed_markers = sum(bool(evidence) for _, evidence in result)
    if len(markers) != parsed_markers:
        raise AssertionError("unpaired evidence block")
    return result


def _parse_locator(raw_locator: str) -> SourceLocator:
    """Parse and resolve one documented typed direct-source locator."""
    match = LOCATOR_RE.fullmatch(raw_locator.strip())
    if match is None:
        raise AssertionError(f"malformed source locator: {raw_locator}")

    relative_path = Path(match.group("path"))
    if (
        relative_path.is_absolute()
        or ".." in relative_path.parts
        or not (ROOT / relative_path).is_relative_to(ROOT)
        or not (ROOT / relative_path).is_relative_to(LITERATURE_ROOT)
    ):
        raise AssertionError(
            f"source path must be an existing literature file: {raw_locator}"
        )
    lexical_path = ROOT / relative_path
    if not lexical_path.is_file():
        raise AssertionError(
            f"source path must be an existing literature file: {raw_locator}"
        )
    path = lexical_path.resolve()

    start = match.group("start")
    if start is not None:
        end = match.group("end")
        return SourceLocator(
            path=path,
            kind="line",
            start=int(start),
            end=int(end or start),
        )

    kind = match.group("kind")
    selector = match.group("selector")
    assert kind is not None
    assert selector is not None
    if kind == "page":
        page_range = re.fullmatch(r"(?P<start>\d+)(?:-(?P<end>\d+))?", selector)
        page_start = int(page_range.group("start")) if page_range else 0
        page_end = (
            int(page_range.group("end") or page_range.group("start"))
            if page_range
            else 0
        )
        if page_range is None or not 1 <= page_start <= page_end:
            raise AssertionError(f"malformed source locator: {raw_locator}")
        if path.suffix.lower() != ".pdf":
            raise AssertionError(f"page locator requires a PDF: {raw_locator}")
    elif not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*(?::[A-Za-z0-9_.-]+)*", selector):
        raise AssertionError(f"malformed source locator: {raw_locator}")
    return SourceLocator(path=path, kind=kind, selector=selector)


def _evidence_entries(
    evidence: list[str],
    *,
    resolve: bool = True,
) -> list[tuple[str, list[SourceLocator]]]:
    """Return each evidence citation and its exact source locators."""
    entries: list[tuple[str, list[SourceLocator]]] = []
    for line in evidence:
        match = EVIDENCE_LINE_RE.fullmatch(line)
        if match is None:
            raise AssertionError(f"malformed evidence line: {line}")
        key = match.group("key")[1:]
        if CITATION_RE.findall(line) != [key]:
            raise AssertionError(f"evidence line must contain one citation key: {line}")
        locators = [
            _parse_locator(locator) for locator in match.group("locators").split(",")
        ]
        if resolve:
            for locator in locators:
                _resolve_locator(locator, key)
        entries.append((key, locators))
    return entries


def _has_active_source_line(path: Path, start: int, end: int) -> bool:
    """Return whether a locator contains active source text.

    This lexical check does not establish that the passage semantically entails
    the thesis claim; that remains an explicit human semantic-review boundary.
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


def test_each_foundations_claim_or_attributed_figure_has_source_evidence() -> None:
    catalog = _literature_catalog()
    for path in FOUNDATIONS_LITERATURE:
        paragraphs = _paragraphs_with_adjacent_evidence(path)
        for index, (paragraph, evidence) in enumerate(paragraphs):
            cited = _paragraph_citations(paragraph, catalog)
            if paragraph.startswith("#figure(") and not cited:
                assert not evidence, (
                    f"figure evidence belongs on its preceding attribution: "
                    f"{path}: {paragraph}"
                )
                assert index > 0 and paragraphs[index - 1][1], (
                    f"figure lacks an immediately preceding sourced attribution: "
                    f"{path}: {paragraph}"
                )
                assert "caption:" in paragraph
                continue
            entries = _evidence_entries(evidence)
            evidence_keys = {key for key, _ in entries}
            assert cited, (
                f"claim-bearing paragraph lacks a citation: {path}: {paragraph}"
            )
            assert evidence, f"missing adjacent // evidence block: {path}: {paragraph}"
            assert cited <= set(catalog.bibliography)
            assert cited == evidence_keys
            assert all(locators for _, locators in entries)


def test_citation_classification_excludes_glossary_references() -> None:
    catalog = _literature_catalog()
    assert _paragraph_citations("@next-best-view and @VIN-NBV-frahm2025", catalog) == {
        "VIN-NBV-frahm2025"
    }


def test_citation_classification_rejects_unknown_mixed_references() -> None:
    with pytest.raises(AssertionError, match="Future-Citation"):
        _paragraph_citations(
            "@VIN-NBV-frahm2025 and @Future-Citation", _literature_catalog()
        )


def test_foundations_source_locators_are_existing_in_range_lines() -> None:
    for foundations_path in FOUNDATIONS_LITERATURE:
        for _, evidence in _paragraphs_with_adjacent_evidence(foundations_path):
            for _, locators in _evidence_entries(evidence, resolve=False):
                for locator in locators:
                    if locator.kind != "line":
                        continue
                    assert locator.start is not None
                    assert locator.end is not None
                    path, start, end = locator.path, locator.start, locator.end
                    assert path.is_file(), path
                    line_count = len(path.read_text(encoding="utf-8").splitlines())
                    assert 1 <= start <= end <= line_count, (
                        path,
                        start,
                        end,
                        line_count,
                    )
                    assert _has_active_source_line(path, start, end), (
                        path,
                        start,
                        end,
                    )


def test_foundations_evidence_locators_are_existing_literature_paths() -> None:
    for foundations_path in FOUNDATIONS_LITERATURE:
        for _, evidence in _paragraphs_with_adjacent_evidence(foundations_path):
            for _, locators in _evidence_entries(evidence, resolve=False):
                for locator in locators:
                    assert locator.path.is_relative_to(LITERATURE_ROOT), locator.path
                    assert locator.path.is_file(), locator.path


def test_source_locator_rejects_comment_only_ranges(tmp_path: Path) -> None:
    source = tmp_path / "commented.tex"
    source.write_text("% no support here\n% still commented\n", encoding="utf-8")
    assert not _has_active_source_line(source, 1, 2)

    source.write_text("% no support here\nActive source text.\n", encoding="utf-8")
    assert _has_active_source_line(source, 1, 2)


def test_evidence_accepts_all_typed_direct_source_locators() -> None:
    path = "docs/literature/tex-src/arXiv-PB-NBV/sections/related.tex"
    figure_path = "docs/literature/tex-src/arXiv-PB-NBV/sections/method.tex"
    table_path = "docs/literature/tex-src/arXiv-PB-NBV/sections/result.tex"
    entries = _evidence_entries(
        [
            "// - @PB-NBV-jia2025 -> "
            f"{path}:5-24, {path}#section=sec:related, "
            f"{figure_path}#figure=System_Overview, {table_path}#table=comparison_res "
            "(typed sources)"
        ]
    )
    assert len(entries) == 1
    _, locators = entries[0]
    assert [locator.kind for locator in locators] == [
        "line",
        "section",
        "figure",
        "table",
    ]
    assert locators[0].start == 5
    assert locators[0].end == 24
    assert locators[1].selector == "sec:related"


def _write_one_page_pdf(path: Path) -> None:
    """Write a small valid PDF whose content contains a fake page marker."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 10 10] /Contents 4 0 R >>",
        b"<< /Length 19 >>\nstream\nBT /Type /Page ET\nendstream",
    ]
    data = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(data))
        data += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_offset = len(data)
    data += b"xref\n0 5\n0000000000 65535 f \n"
    data += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    data += (
        b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n"
        + str(xref_offset).encode()
        + b"\n%%EOF\n"
    )
    path.write_bytes(data)


def test_pdf_page_locator_is_bounded_and_resolvable(tmp_path: Path) -> None:
    pdf = tmp_path / "paper.pdf"
    _write_one_page_pdf(pdf)
    assets = LiteratureAssets((), (pdf,))
    locator = SourceLocator(pdf, "page", selector="1")
    original = _literature_assets
    try:
        globals()["_literature_assets"] = lambda: {"key": assets}
        _resolve_locator(locator, "key")
        with pytest.raises(AssertionError, match="out of range"):
            _resolve_locator(SourceLocator(pdf, "page", selector="2"), "key")
        with pytest.raises(AssertionError, match="out of range"):
            _resolve_locator(SourceLocator(pdf, "page", selector="0"), "key")
    finally:
        globals()["_literature_assets"] = original


def test_pdf_locator_resolves_through_symlinked_pdf_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    pdf_root = tmp_path / "pdf-cache"
    (repo / "docs/literature").mkdir(parents=True)
    pdf_root.mkdir()
    _write_one_page_pdf(pdf_root / "paper.pdf")
    (repo / "docs/literature/pdf").symlink_to(pdf_root, target_is_directory=True)
    assets = LiteratureAssets((), ((pdf_root / "paper.pdf").resolve(),))
    original_root = globals()["ROOT"]
    original_literature_root = globals()["LITERATURE_ROOT"]
    original_assets = _literature_assets
    try:
        globals()["ROOT"] = repo
        globals()["LITERATURE_ROOT"] = repo / "docs/literature"
        globals()["_literature_assets"] = lambda: {"key": assets}
        entries = _evidence_entries(
            ["// - @key -> docs/literature/pdf/paper.pdf#page=1"]
        )
    finally:
        globals()["ROOT"] = original_root
        globals()["LITERATURE_ROOT"] = original_literature_root
        globals()["_literature_assets"] = original_assets

    assert entries[0][1][0].path == (pdf_root / "paper.pdf").resolve()


def test_evidence_rejects_locator_owned_by_different_cited_work() -> None:
    with pytest.raises(
        AssertionError, match="not owned by citation @VIN-NBV-frahm2025"
    ):
        _evidence_entries(
            [
                "// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-BCQ/example_paper.tex:134-163"
            ]
        )


@pytest.mark.parametrize(
    "locator",
    (
        "docs/literature/pdf/PB-NBV.pdf#page=0",
        "docs/literature/pdf/PB-NBV.pdf#page=0-1",
        "docs/literature/tex-src/arXiv-PB-NBV/sections/related.tex#page=1-",
        "docs/literature/tex-src/arXiv-PB-NBV/sections/related.tex#page=2-1",
        "docs/literature/tex-src/arXiv-PB-NBV/sections/related.tex#page=one",
        "docs/literature/tex-src/arXiv-PB-NBV/sections/related.tex#section=",
        "docs/literature/tex-src/arXiv-PB-NBV/sections/related.tex#section=sec:",
        "docs/literature/tex-src/arXiv-PB-NBV/sections/related.tex#figure=bad id",
        "docs/literature/tex-src/arXiv-PB-NBV/jzzpb.bib#section=sec:related",
        "docs/literature/tex-src/arXiv-PB-NBV/sections/related.tex:5#page=1",
        "docs/literature/../references.bib:1",
        "docs/source.qmd:1",
        "docs/literature/not-present.tex#table=tab:missing",
    ),
)
def test_evidence_rejects_malformed_or_unresolvable_typed_locator(locator: str) -> None:
    with pytest.raises(
        AssertionError,
        match="(?:malformed|existing literature file|requires a PDF|not owned|does not resolve)",
    ):
        _evidence_entries([f"// - @PB-NBV-jia2025 -> {locator}"])


def test_evidence_rejects_malformed_line(tmp_path: Path) -> None:
    source = tmp_path / "malformed.typ"
    source.write_text(
        "Claim @key.\n\n// evidence:\n// - @key -> docs/source.qmd:1-2 extra\n",
        encoding="utf-8",
    )
    try:
        _paragraphs_with_adjacent_evidence(source)
    except AssertionError as error:
        assert "malformed evidence line" in str(error)
    else:
        raise AssertionError("malformed evidence line was accepted")


def test_evidence_rejects_extra_and_mixed_lines(tmp_path: Path) -> None:
    for evidence in (
        "// - @key -> docs/source.qmd:1-2\n// note: extra\n",
        "// - @key -> docs/source.qmd:1-2\n// malformed\n",
    ):
        source = tmp_path / "mixed.typ"
        source.write_text(f"Claim @key.\n\n// evidence:\n{evidence}", encoding="utf-8")
        try:
            _paragraphs_with_adjacent_evidence(source)
        except AssertionError as error:
            assert "malformed evidence line" in str(error)
        else:
            raise AssertionError("extra/mixed evidence line was accepted")


def test_evidence_rejects_orphan_block(tmp_path: Path) -> None:
    source = tmp_path / "orphan.typ"
    source.write_text(
        "// evidence:\n// - @key -> docs/source.qmd:1-2\n", encoding="utf-8"
    )
    try:
        _paragraphs_with_adjacent_evidence(source)
    except AssertionError as error:
        assert "orphan evidence block" in str(error)
    else:
        raise AssertionError("orphan evidence block was accepted")


def test_evidence_rejects_malformed_marker(tmp_path: Path) -> None:
    source = tmp_path / "marker.typ"
    source.write_text(
        "Claim @key.\n\n// evidence: unexpected\n// - @key -> docs/source.qmd:1-2\n",
        encoding="utf-8",
    )
    try:
        _paragraphs_with_adjacent_evidence(source)
    except AssertionError as error:
        assert "malformed evidence marker" in str(error)
    else:
        raise AssertionError("malformed evidence marker was accepted")


@pytest.mark.parametrize(
    "marker",
    ("//evidence:", "// evidence :", "// Evidence:", "// EVIDENCE :"),
)
def test_evidence_rejects_marker_like_variants(tmp_path: Path, marker: str) -> None:
    source = tmp_path / "marker-variant.typ"
    source.write_text(
        f"Claim @key.\n\n{marker}\n// - @key -> docs/source.qmd:1-2\n",
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="malformed evidence marker"):
        _paragraphs_with_adjacent_evidence(source)
