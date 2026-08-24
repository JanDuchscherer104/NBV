"""Load bibliography identities and their manifest-owned local assets."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlsplit, urlunsplit


class LiteratureCatalogError(RuntimeError):
    """Report malformed or ambiguous literature ownership metadata."""


@dataclass(frozen=True)
class LiteratureCatalogConfig:
    """Locate the canonical bibliography and literature-manifest owners."""

    repo_root: Path
    bibliography_paths: tuple[Path, ...] = (
        Path("docs/references.bib"),
        Path("docs/references-qh.bib"),
    )
    manifest_path: Path = Path("docs/literature/sources.jsonl")
    tex_root: Path = Path("docs/literature/tex-src")
    pdf_root: Path = Path("docs/literature/pdf")


@dataclass(frozen=True)
class BibliographyEntry:
    """One citation identity and its normalized external identifiers."""

    key: str
    owner: Path
    locator: str
    arxiv: str | None = None
    doi: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class ManifestEntry:
    """One manifest row with stable identity and validated local asset paths."""

    line: int
    data: Mapping[str, object]
    identity: str
    arxiv: str | None
    doi: str | None
    url: str | None
    tex_path: Path | None
    pdf_path: Path | None


@dataclass(frozen=True)
class LiteratureAssets:
    """Resolved local assets owned by one bibliography citation."""

    roots: tuple[Path, ...]
    pdfs: tuple[Path, ...]


@dataclass(frozen=True)
class LiteratureCatalog:
    """Canonical citation identities, manifest rows, joins, and local assets."""

    config: LiteratureCatalogConfig
    bibliography: Mapping[str, BibliographyEntry]
    manifest: tuple[ManifestEntry, ...]
    joined: Mapping[str, ManifestEntry]

    def citations(self, text: str) -> Counter[str]:
        """Count only known bibliography citations in Typst source text."""
        alternation = "|".join(
            re.escape(key)
            for key in sorted(self.bibliography, key=lambda key: (-len(key), key))
        )
        if not alternation:
            return Counter()
        pattern = re.compile(rf"(?<![\w])@({alternation})(?![A-Za-z0-9_+-])")
        return Counter(pattern.findall(text))

    def assets_for(self, key: str) -> LiteratureAssets | None:
        """Resolve the manifest-owned local asset paths for ``key``."""
        row = self.joined.get(key)
        if row is None:
            return None
        roots = (
            ((self.config.repo_root / row.tex_path).resolve(),)
            if row.tex_path is not None
            else ()
        )
        pdfs = (
            ((self.config.repo_root / row.pdf_path).resolve(),)
            if row.pdf_path is not None
            else ()
        )
        return LiteratureAssets(roots, pdfs)


def _owner_path(config: LiteratureCatalogConfig, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise LiteratureCatalogError(
            f"owner must be a repository-relative path: {relative}"
        )
    repository = config.repo_root.resolve()
    try:
        path = (repository / relative).resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise LiteratureCatalogError(
            f"owner path cannot be resolved safely: {relative}: {error}"
        ) from error
    if not path.is_relative_to(repository):
        raise LiteratureCatalogError(
            f"owner path physically escapes repository: {relative}"
        )
    return path


def _normalize_arxiv(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().casefold()
    normalized = re.sub(r"^(?:arxiv:|https?://arxiv\.org/(?:abs|pdf)/)", "", normalized)
    normalized = re.sub(r"\.pdf$", "", normalized)
    return re.sub(r"v\d+$", "", normalized)


def _normalize_doi(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return re.sub(
        r"^(?:doi:|https?://doi\.org/)", "", value.strip(), flags=re.IGNORECASE
    ).casefold()


def _normalize_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = urlsplit(value.strip())
    if not parsed.scheme or not parsed.netloc:
        return value.strip()
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit(
        (
            parsed.scheme.casefold(),
            parsed.netloc.casefold(),
            path,
            parsed.query,
            parsed.fragment,
        )
    )


def _bib_entry_end(text: str, owner: Path, body_start: int, opener: str) -> int:
    closer = "}" if opener == "{" else ")"
    depth = 1
    cursor = body_start
    while cursor < len(text) and depth:
        if text[cursor] == opener:
            depth += 1
        elif text[cursor] == closer:
            depth -= 1
        cursor += 1
    if depth:
        raise LiteratureCatalogError(f"{owner.as_posix()}: malformed BibTeX entry")
    return cursor


def _bib_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for name in ("eprint", "arxiv", "doi", "url"):
        match = re.search(rf'(?is)\b{name}\s*=\s*(?:{{([^{{}}]*)}}|"([^"]*)")', body)
        if match:
            fields[name] = (match.group(1) or match.group(2)).strip()
    return fields


def _load_bibliography(
    config: LiteratureCatalogConfig,
) -> dict[str, BibliographyEntry]:
    entries: dict[str, BibliographyEntry] = {}
    for owner in config.bibliography_paths:
        text = _owner_path(config, owner).read_text(encoding="utf-8")
        index = 0
        while True:
            start = re.search(r"@[A-Za-z]+\s*[{(]\s*([^,\s]+)\s*,", text[index:])
            if start is None:
                break
            absolute = index + start.start()
            body_start = index + start.end()
            opener = "{" if "{" in start.group(0) else "("
            cursor = _bib_entry_end(text, owner, body_start, opener)
            key = start.group(1)
            if key in entries:
                raise LiteratureCatalogError(f"duplicate bibliography key {key}")
            fields = _bib_fields(text[body_start : cursor - 1])
            line = text.count("\n", 0, absolute) + 1
            entries[key] = BibliographyEntry(
                key=key,
                owner=owner,
                locator=f"{owner.as_posix()}:{line}",
                arxiv=_normalize_arxiv(fields.get("eprint") or fields.get("arxiv")),
                doi=_normalize_doi(fields.get("doi")),
                url=_normalize_url(fields.get("url")),
            )
            index = cursor
    return entries


def _asset_relative(root: Path, value: object, *, line: int) -> Path | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise LiteratureCatalogError(
            f"manifest line {line}: asset path must be a string"
        )
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise LiteratureCatalogError(
            f"manifest line {line}: asset path escapes its root: {value}"
        )
    return Path(PurePosixPath((root / path).as_posix()))


def _manifest_explicit_id(data: Mapping[str, object], *, line: int) -> str | None:
    values = [data[key] for key in ("stable_id", "id") if key in data]
    if not values:
        return None
    if not all(isinstance(value, str) and value.strip() for value in values):
        raise LiteratureCatalogError(
            f"manifest line {line}: explicit ID must be non-empty text"
        )
    normalized = {str(value).strip() for value in values}
    if len(normalized) != 1:
        raise LiteratureCatalogError(f"manifest line {line}: conflicting explicit IDs")
    explicit_id = normalized.pop()
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", explicit_id) is None:
        raise LiteratureCatalogError(
            f"manifest line {line}: explicit ID must use letters, digits, '.', '_', or '-'"
        )
    return explicit_id


def _manifest_content_digest(data: Mapping[str, object]) -> str:
    canonical = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _load_manifest(config: LiteratureCatalogConfig) -> tuple[ManifestEntry, ...]:
    result: list[ManifestEntry] = []
    text = _owner_path(config, config.manifest_path).read_text(encoding="utf-8")
    for line, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as error:
            raise LiteratureCatalogError(
                f"{config.manifest_path.as_posix()}:{line}: invalid JSON"
            ) from error
        if not isinstance(data, dict):
            raise LiteratureCatalogError(
                f"{config.manifest_path.as_posix()}:{line}: expected object"
            )
        arxiv = _normalize_arxiv(data.get("arxiv_id") or data.get("arxiv"))
        doi = _normalize_doi(data.get("doi"))
        url = _normalize_url(data.get("url"))
        if arxiv:
            identity = f"literature:arxiv:{arxiv}"
        elif doi:
            identity = f"literature:doi:{doi}"
        elif url:
            identity = f"literature:url:{url}"
        else:
            explicit_id = _manifest_explicit_id(data, line=line)
            identity = (
                f"literature:id:{explicit_id}"
                if explicit_id is not None
                else f"literature:metadata-sha256:{_manifest_content_digest(data)}"
            )
        result.append(
            ManifestEntry(
                line=line,
                data=data,
                identity=identity,
                arxiv=arxiv,
                doi=doi,
                url=url,
                tex_path=_asset_relative(
                    config.tex_root, data.get("tex_dir"), line=line
                ),
                pdf_path=_asset_relative(
                    config.pdf_root, data.get("pdf_file"), line=line
                ),
            )
        )
    identities = [entry.identity for entry in result]
    if len(identities) != len(set(identities)):
        raise LiteratureCatalogError(
            "duplicate or colliding manifest generated identity"
        )
    return tuple(result)


def _join(
    bibliography: Mapping[str, BibliographyEntry],
    manifest: Sequence[ManifestEntry],
) -> dict[str, ManifestEntry]:
    indexes: dict[str, dict[str, list[ManifestEntry]]] = {
        "arxiv": defaultdict(list),
        "doi": defaultdict(list),
        "url": defaultdict(list),
    }
    for row in manifest:
        for field_name in indexes:
            value = getattr(row, field_name)
            if value:
                indexes[field_name][value].append(row)
    joined: dict[str, ManifestEntry] = {}
    for key, entry in bibliography.items():
        signal_matches: list[tuple[str, list[ManifestEntry]]] = []
        for field_name in ("arxiv", "doi", "url"):
            value = getattr(entry, field_name)
            matches = indexes[field_name].get(value, []) if value else []
            if len(matches) > 1:
                raise LiteratureCatalogError(
                    f"ambiguous {field_name} join for bibliography key {key}"
                )
            if matches:
                signal_matches.append((field_name, matches))
        distinct = {
            match.identity for _, matches in signal_matches for match in matches
        }
        if len(distinct) > 1:
            raise LiteratureCatalogError(
                f"conflicting identity signals for bibliography key {key}"
            )
        if signal_matches:
            joined[key] = signal_matches[0][1][0]
    return joined


def load_literature_catalog(config: LiteratureCatalogConfig) -> LiteratureCatalog:
    """Load and deterministically join canonical literature owners."""
    config = LiteratureCatalogConfig(
        **{**config.__dict__, "repo_root": config.repo_root.absolute()}
    )
    bibliography = _load_bibliography(config)
    manifest = _load_manifest(config)
    return LiteratureCatalog(
        config, bibliography, manifest, _join(bibliography, manifest)
    )
