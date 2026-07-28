#!/usr/bin/env python3
"""Validate registered current and superseded OMX evidence bundles.

Registered evidence is public-by-default. The privacy scan therefore rejects
machine/runtime locators, private paths and HTML, plus explicit credential
formats. It intentionally has no generic high-entropy or catch-all secret
regex because those produce unactionable false positives in technical prose.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

REGISTRY = ".agents/omx_artifacts.toml"
REQUIRED_FAMILIES = {
    "context",
    "specification",
    "plan",
    "test_specification",
    "review",
    "handoff",
}
CURRENT_ROOTS = (".omx/context/", ".omx/specs/", ".omx/plans/")
FAMILY_NATIVE_ROOT = {
    "context": ".omx/context/",
    "specification": ".omx/specs/",
    "test_specification": ".omx/specs/",
    "plan": ".omx/plans/",
    "review": ".omx/plans/",
    "handoff": ".omx/plans/",
}
PRIVATE_PARTS = {
    "cache",
    "logs",
    "private",
    "raw",
    "runtime",
    "sessions",
    "state",
    "tmux",
    "transcripts",
    "ultragoal",
}
ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
IMMUTABLE_BUNDLE_FIELDS = (
    "id",
    "task",
    "classification",
    "baseline_commit",
    "handoff_sha256",
    "acceptance_sha256",
    "contract_version",
    "predecessor_bundle_id",
    "predecessor_bundle_sha256",
    "predecessor_chain_sha256",
    "predecessor_registry_commit",
)
REGISTRY_FIELDS = {"schema_version", "bundle"}
BUNDLE_FIELDS = {
    *IMMUTABLE_BUNDLE_FIELDS,
    "status",
    "superseded_by",
    "artifact",
}
ARTIFACT_FIELDS = {
    "family",
    "role",
    "path",
    "native_path",
    "sha256",
    "bytes",
    "review_kinds",
}
RUNTIME_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
RUNTIME_UUID_V1 = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
ABSOLUTE_PATH_V1 = re.compile(
    r"(?<![A-Za-z0-9_.:/-])(?:/[A-Za-z0-9._-]+){2,}(?=$|[\s`'\"),:;])"
    r"|\b[A-Za-z]:\\(?:[^\s`'\"<>|]+\\)+[^\s`'\"<>|]*"
)
ABSOLUTE_PATH = re.compile(
    r"(?<![A-Za-z0-9_./\\])/(?!/)[^\s`'\"),:;]+"
    r"|(?<!__pycache__)(?<=_)/(?!/)[^\s`'\"),:;]+"
    r"|(?<=[A-Za-z0-9_]\.)/(?!/)[^\s`'\"),:;]+"
    r"|\b[A-Za-z]:\\(?:[^\s`'\"<>|]+\\)*[^\s`'\"<>|]+"
)
WINDOWS_ABSOLUTE_PATH = re.compile(
    r"(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/]|\\\\[^\\/\s`'\"<>|]+[\\/]"
    r"[^\\/\s`'\"<>|]+)[^\s`'\"<>|]*"
)
FILE_URI = re.compile(r"\bfile:(?://)?/[^\s`'\"),:;]+", re.IGNORECASE)
URI_CANDIDATE = re.compile(
    r"(?<![A-Za-z0-9])(?P<uri>[A-Za-z0-9][A-Za-z0-9+.-]*:[^\s`'\"<>]+)"
)
UNSUPPORTED_AUTHORITY_URI = re.compile(
    r"(?<![A-Za-z0-9])(?!(?:https?)://)[A-Za-z0-9][A-Za-z0-9+.-]*://",
    re.IGNORECASE,
)
MARKDOWN_AUTHORITY_URI = re.compile(
    r"(?:\*\*[A-Za-z0-9+.-]+:\*\*|__[A-Za-z0-9+.-]+:__|"
    r"(?<!\*)\*[A-Za-z0-9+.-]+:\*(?!\*)|"
    r"(?<!_)_[A-Za-z0-9+.-]+:_(?!_))//"
)
REPOSITORY_SOURCE_LOCATOR = re.compile(
    r"(?:"
    r"(?:HEAD|main|master|origin/(?:HEAD|main|master)|[0-9a-f]{7,40}):"
    r"(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+"
    r"|(?:[A-Za-z0-9_.-]+/)*(?:"
    r"[A-Za-z0-9_.-]+\.(?:bib|c|cc|cfg|cpp|csv|h|hpp|html|ini|js|json|jsx|"
    r"lock|md|mmd|py|qmd|rs|sh|tex|toml|ts|tsx|txt|typ|yaml|yml|zsh)|"
    r"Makefile|post-commit|\.graphifyignore)"
    r"):[0-9]+(?:-[0-9]+)?",
    re.IGNORECASE,
)
SIMPLE_HTTP_URL = re.compile(
    r"https?://"
    r"(?P<host>(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)"
    r"(?::(?P<port>[0-9]{1,5}))?"
    r"(?:/[A-Za-z0-9._~!$&*+,;=:@%/()\-]*)?"
    r"(?:\?[A-Za-z0-9._~!$&*+,;=:@%/?()\-]*)?"
    r"(?:#[A-Za-z0-9._~!$&*+,;=:@%/?()\-]*)?",
    re.IGNORECASE,
)
FORWARD_UNC_PATH = re.compile(
    r"(?<!:)//[^/\\\s`'\"<>|]+[\\/][^\s`'\"<>|]+", re.IGNORECASE
)
DOUBLE_SLASH_PATH = re.compile(r"(?<!:)//")
ANGLE_ABSOLUTE_PATH = re.compile(r"</[^>\s]+>")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_NESTED_JSON_DEPTH = 4
MAX_NESTED_JSON_BYTES = 1_000_000
MAX_JSON_STRUCTURE_DEPTH = 64
MAX_JSON_STRUCTURE_NODES = 100_000
MAX_EMBEDDED_JSON_VALUES = 1_024
MAX_EMBEDDED_JSON_ATTEMPTS = 1_024
MAX_DECODED_TEXT_VARIANTS = 256
MAX_BUNDLE_CHAIN_LENGTH = 1_000
MAX_REGISTRY_BYTES = 1_000_000
MAX_REGISTRY_BUNDLES = 1_024
MAX_ARTIFACTS_PER_BUNDLE = 256
MAX_REGISTRY_ARTIFACTS = 4_096
MAX_ARTIFACT_BYTES = 2_000_000
MAX_TOTAL_ARTIFACT_BYTES = 20_000_000
LFS_POINTER = re.compile(
    r"\Aversion https://git-lfs\.github\.com/spec/v1\n"
    r"(?:ext-[^\n]+\n)*"
    r"oid sha256:[0-9a-f]{64}\nsize [0-9]+\n?\Z"
)
ACCEPTANCE_FIELDS_V2 = {
    "schema_version",
    "bundle_id",
    "task",
    "status",
    "accepted_scope",
    "excluded_scope",
    "actor_class",
    "instruction_channel",
    "date",
    "request_digest",
    "request_digest_normalization",
}
HANDOFF_FIELDS_V2 = {
    "schema_version",
    "bundle_id",
    "task",
    "status",
    "predecessor_bundle_id",
    "predecessor_bundle_sha256",
    "predecessor_chain_sha256",
    "roles",
    "review",
    "execution",
    "constraints",
}
REVIEW_FIELDS_V2 = {
    "schema_version",
    "bundle_id",
    "task",
    "status",
    "architect",
    "critic",
}
PRIVATE_PATH_V1 = re.compile(
    r"(?<![A-Za-z0-9_.-])(?:"
    r"(?:\.?[A-Za-z0-9_.-]+/)+(?:private|raw)/"
    r"|(?:private|raw)/(?:[A-Za-z0-9_.-]+/)+"
    r")(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+",
    re.IGNORECASE,
)
PRIVATE_PATH = re.compile(
    r"(?<![A-Za-z0-9_.-])(?:private|raw)"
    r"(?:[\\/?#=:]|\*\*/\*\*|__/__|$)",
    re.IGNORECASE,
)
HTML_V1 = re.compile(r"<!doctype\s+html\b|<html(?:\s|>)", re.IGNORECASE)
HTML = re.compile(
    r"<!doctype\s+html\b|<!--|"
    r"<(?!https?://)/?[A-Za-z][A-Za-z0-9:-]*(?:(?:\s|/)[^>]*)?>",
    re.IGNORECASE,
)
BARE_RESERVED_URI = re.compile(
    r"(?<![A-Za-z0-9+.-])(?:https?|file|javascript|data|urn|mailto|tel|geo|"
    r"[0-9][A-Za-z0-9+.-]*):(?=$|[\s`'\"<>])",
    re.IGNORECASE,
)
EMPHASIZED_SCHEME_PART = (
    r"(?:\*\*[A-Za-z0-9+.-]+\*\*|__[A-Za-z0-9+.*-]+__|"
    r"(?<!\*)\*[A-Za-z0-9+.-]+\*(?!\*)|"
    r"(?<!_)_[A-Za-z0-9+.*-]+_(?!_))"
)
OBFUSCATED_BARE_URI = re.compile(
    r"(?<![A-Za-z0-9+.-])(?:"
    rf"[A-Za-z0-9+.-]+(?:{EMPHASIZED_SCHEME_PART}[A-Za-z0-9+.-]*)+|"
    rf"{EMPHASIZED_SCHEME_PART}[A-Za-z0-9+.-]+"
    rf"(?:{EMPHASIZED_SCHEME_PART}[A-Za-z0-9+.-]*)*"
    r"):(?=$|[\s`'\"<>])"
)
MARKDOWN_LABEL = re.compile(
    r"(?<![A-Za-z0-9_/])(?:\*\*[A-Za-z0-9](?:[^*]|\*(?!\*))*:\*\*|"
    r"__(?!pycache__(?:/|$))[A-Za-z0-9](?:[^_]|_(?!_))*:__)"
    r"(?=$|\s|[>,.;)\]](?=$|\s)|['\"](?=$|[\s,}\]])|=(?=https?://))"
)
MARKDOWN_EMPHASIS = re.compile(
    r"(?<![A-Za-z0-9_/])(?:\*\*[A-Za-z0-9](?:[^*]|\*(?!\*))*\*\*|"
    r"__(?!pycache__(?:/|$))[A-Za-z0-9](?:[^_]|_(?!_))*__)(?![A-Za-z0-9_])"
)
EMPHASIS_ABSOLUTE_PATH = re.compile(
    r"(?:\*\*(?:[^*]|\*(?!\*))+(?<!\n)\*\*|"
    r"__(?:[^_]|_(?!_))+(?<!\n)__|"
    r"(?<!\*)\*[^*\n]+\*(?!\*)|(?<!_)_[^_\n]+_(?!_))"
    r"[\\/][^\s`'\"),:;\\/]+(?:[\\/][^\s`'\"),:;\\/]+)+"
)
MARKDOWN_SEPARATOR = re.compile(r"(?:\*\*([:/\\])\*\*|__([:/\\])__)")
MARKDOWN_TOKEN = re.compile(
    r"(?:\*\*([A-Za-z0-9+._-]+)\*\*|__([A-Za-z0-9+.*-]+)__|"
    r"(?<!\*)\*([A-Za-z0-9+._-]+)\*(?!\*)|"
    r"(?<!_)_([A-Za-z0-9+.*-]+)_(?!_))"
)
RELATIVE_GLOB = re.compile(
    r"(?<![A-Za-z0-9_.*?/\\])[A-Za-z0-9_.+-]+/"
    r"(?:[A-Za-z0-9_.?*+-]+/)*[A-Za-z0-9_.?*+-]+"
)
LEADING_RECURSIVE_GLOB = re.compile(
    r"(?<![A-Za-z0-9_.*?/\\])\*\*/"
    r"(?:(?:[A-Za-z0-9_.+-]+/)+\*\*|\*\.[A-Za-z0-9_.+-]+)"
)
COMMONMARK_ESCAPE = re.compile(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\]\\^_`{|}~])")
# fmt: off
SENSITIVE_TEXT = (
    (re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"), "private key"),
    (re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"), "GitHub token"),
    (re.compile(r"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}"), "OpenAI API key"),
    (re.compile(r"(?:AKIA|ASIA|AIDA|AROA)[A-Z0-9]{16}"), "AWS access key ID"),
    (re.compile(r"aws_secret_access_key\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{40}", re.IGNORECASE), "AWS secret access key"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "Slack token"),
    (re.compile(r"AIza[0-9A-Za-z_-]{30,}"), "Google API key"),
    (re.compile(r"glpat-[A-Za-z0-9_-]{20,}"), "GitLab token"),
    (re.compile(r"hf_[A-Za-z0-9]{20,}"), "Hugging Face token"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}", re.IGNORECASE), "bearer token"),
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE), "email address"),
)
SENSITIVE_TEXT_V1 = (
    (re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"), "private key"),
    (re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"), "GitHub token"),
    (re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}\b"), "OpenAI API key"),
    (re.compile(r"\b(?:AKIA|ASIA|AIDA|AROA)[A-Z0-9]{16}\b"), "AWS access key ID"),
    (re.compile(r"\baws_secret_access_key\b\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{40}\b", re.IGNORECASE), "AWS secret access key"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "Slack token"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"), "Google API key"),
    (re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"), "GitLab token"),
    (re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"), "Hugging Face token"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}\b", re.IGNORECASE), "bearer token"),
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE), "email address"),
)
# fmt: on

V2_PATH_CHECKS = (
    (FILE_URI, "absolute path"),
    (ABSOLUTE_PATH, "absolute path"),
    (WINDOWS_ABSOLUTE_PATH, "absolute path"),
    (DOUBLE_SLASH_PATH, "absolute path"),
    (FORWARD_UNC_PATH, "absolute path"),
    (ANGLE_ABSOLUTE_PATH, "absolute path"),
)
V2_URL_PATH_CHECKS = (
    (FILE_URI, "absolute path"),
    (WINDOWS_ABSOLUTE_PATH, "absolute path"),
    (FORWARD_UNC_PATH, "absolute path"),
    (ANGLE_ABSOLUTE_PATH, "absolute path"),
)


class ValidationError(ValueError):
    """Raised when a registry or artifact violates the lifecycle contract."""


@dataclass(frozen=True)
class Artifact:
    family: str
    role: str
    path: str
    native_path: str
    sha256: str
    bytes: int
    review_kinds: tuple[str, ...]


def _run(repo: Path, *args: str) -> str:
    result = subprocess.run(
        args,
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _safe_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or str(path) != value:
        raise ValidationError(f"unsafe repository path: {value}")
    if path.suffix.lower() in {".html", ".htm"}:
        raise ValidationError(f"HTML is not accepted evidence: {value}")
    if PRIVATE_PARTS.intersection(part.lower() for part in path.parts):
        raise ValidationError(f"raw or private evidence directory: {value}")
    return path


def _digest(path: Path) -> tuple[str, int]:
    payload = path.read_bytes()
    return hashlib.sha256(payload).hexdigest(), len(payload)


def _read_utf8(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValidationError(f"invalid UTF-8 {label}: {path}: {exc}") from exc


def _contract_version(bundle: dict[str, Any]) -> int:
    version = bundle.get("contract_version", 1)
    if type(version) is not int or version not in {1, 2}:
        raise ValidationError(
            f"invalid contract version for {bundle.get('id')}: {version}"
        )
    return version


def _without_markdown_spans(text: str, pattern: re.Pattern[str]) -> str:
    visible = list(text)
    for match in pattern.finditer(text):
        visible[match.start() : match.end()] = " " * (match.end() - match.start())
    return "".join(visible)


def _without_spans(text: str, spans: list[tuple[int, int]]) -> str:
    visible = list(text)
    for start, end in spans:
        visible[start:end] = " " * (end - start)
    return "".join(visible)


def _without_relative_globs(text: str) -> str:
    visible = list(text)
    for pattern in (RELATIVE_GLOB, LEADING_RECURSIVE_GLOB):
        for match in pattern.finditer(text):
            if "*" not in match.group() and "?" not in match.group():
                continue
            if pattern is RELATIVE_GLOB and any(
                "**" in segment and segment != "**"
                for segment in match.group().split("/")
            ):
                continue
            visible[match.start() : match.end()] = " " * (match.end() - match.start())
    return "".join(visible)


def _decoded_text_variants(text: str, subject: object) -> list[str]:
    pending = [text]
    seen: set[str] = set()
    variants: list[str] = []
    while pending:
        candidate = pending.pop()
        if candidate in seen:
            continue
        if len(seen) >= MAX_DECODED_TEXT_VARIANTS:
            raise ValidationError(
                f"decoded text exceeds variant limit in registered evidence: {subject}"
            )
        seen.add(candidate)
        variants.append(candidate)
        try:
            decoded_layers = {
                unquote(candidate),
                html.unescape(candidate),
                COMMONMARK_ESCAPE.sub(r"\1", candidate),
                MARKDOWN_SEPARATOR.sub(r"\1\2", candidate),
                MARKDOWN_TOKEN.sub(r"\1\2\3\4", candidate),
            }
        except UnicodeError as exc:
            raise ValidationError(
                f"invalid Unicode in registered evidence: {subject}"
            ) from exc
        try:
            json_decoded = json.loads(f'"{candidate}"')
        except ValueError:
            pass
        else:
            if isinstance(json_decoded, str):
                decoded_layers.add(json_decoded)
        pending.extend(decoded_layers - seen)
    return variants


def _http_mask_length(uri: str) -> int:
    parentheses = 0
    for index, char in enumerate(uri[:-1]):
        if uri[index : index + 2] in {"**", "__"} and uri[index + 2 : index + 3] in {
            "/",
            "\\",
        }:
            return index
        if char == "(":
            parentheses += 1
        elif char == ")":
            if parentheses:
                parentheses -= 1
            else:
                return index
        elif char in ",]}" and uri[index + 1] == "/":
            return index
    return len(uri)


def _validate_http_uri(uri: str, subject: object, *, strict: bool) -> bool:
    parsed = SIMPLE_HTTP_URL.fullmatch(uri)
    malformed = parsed is None or re.search(r"%(?![0-9A-Fa-f]{2})", uri) is not None
    if not malformed and parsed is not None:
        port = parsed.group("port")
        malformed = port is not None and not 1 <= int(port) <= 65535
    if malformed and strict:
        raise ValidationError(
            f"privacy threat (malformed HTTP URI) in registered evidence: {subject}"
        )
    return not malformed


def _validate_uri_candidates(
    text: str, subject: object, *, strict: bool = True
) -> list[tuple[int, int]]:
    visible_text = _without_markdown_spans(text, MARKDOWN_LABEL)
    validated_http_spans: list[tuple[int, int]] = []
    if strict and OBFUSCATED_BARE_URI.search(text):
        raise ValidationError(
            f"privacy threat (unsupported URI scheme) in registered evidence: {subject}"
        )
    if strict and BARE_RESERVED_URI.search(visible_text):
        raise ValidationError(
            f"privacy threat (unsupported or malformed URI) in registered evidence: {subject}"
        )
    for match in URI_CANDIDATE.finditer(visible_text):
        raw_uri = match.group("uri")
        if raw_uri.endswith(":") and raw_uri[-2:-1] in ")]}":
            raw_uri = raw_uri[:-1]
        uri = raw_uri.rstrip(".,;]}*_")
        while uri.endswith(")") and uri.count(")") > uri.count("("):
            uri = uri[:-1]
        scheme = uri.partition(":")[0].lower()
        if scheme not in {"http", "https"}:
            if REPOSITORY_SOURCE_LOCATOR.fullmatch(uri):
                continue
            if strict:
                raise ValidationError(
                    f"privacy threat (unsupported URI scheme) in registered evidence: {subject}"
                )
            continue
        if not _validate_http_uri(uri, subject, strict=strict):
            continue
        nested_scheme = False
        parsed_url = urlsplit(uri)
        for component in (parsed_url.path, parsed_url.query, parsed_url.fragment):
            for nested_match in URI_CANDIDATE.finditer(component):
                nested_uri = nested_match.group("uri")
                scheme = nested_uri.partition(":")[0].lower()
                if scheme in {"http", "https"}:
                    if _validate_http_uri(nested_uri, subject, strict=strict):
                        continue
                    nested_scheme = True
                    break
                if REPOSITORY_SOURCE_LOCATOR.fullmatch(nested_uri):
                    continue
                nested_scheme = True
                break
            if nested_scheme:
                break
        if nested_scheme:
            if strict:
                raise ValidationError(
                    f"privacy threat (unsupported URI scheme) in registered evidence: {subject}"
                )
            continue
        url_path = parsed_url.path.removeprefix("/")
        url_components = (
            (url_path, V2_URL_PATH_CHECKS),
            (parsed_url.query, V2_PATH_CHECKS),
            (parsed_url.fragment, V2_PATH_CHECKS),
        )
        component_threat = (
            "absolute path"
            if parsed_url.path.startswith("//") or "//" in url_path
            else None
        )
        for component, checks in url_components:
            for pattern, label in checks:
                if pattern.search(component):
                    component_threat = label
                    break
            if component_threat is not None:
                break
        if component_threat is not None:
            if strict:
                raise ValidationError(
                    f"privacy threat ({component_threat}) in registered evidence: {subject}"
                )
            continue
        start = match.start("uri")
        validated_http_spans.append((start, start + _http_mask_length(uri)))
    return validated_http_spans


def _scan_text(text: str, subject: object, contract_version: int = 2) -> None:
    if contract_version < 2:
        checks = (
            (ABSOLUTE_PATH_V1, "absolute path"),
            (RUNTIME_UUID_V1, "runtime UUID"),
            (PRIVATE_PATH_V1, "private or raw path part"),
            (HTML_V1, "HTML content"),
            *SENSITIVE_TEXT_V1,
        )
        for pattern, label in checks:
            if pattern.search(text):
                raise ValidationError(
                    f"privacy threat ({label}) in registered evidence: {subject}"
                )
        return

    try:
        text.encode("utf-8")
    except UnicodeError as exc:
        raise ValidationError(
            f"invalid Unicode in registered evidence: {subject}"
        ) from exc

    content_checks = (
        (UNSUPPORTED_AUTHORITY_URI, "unsupported URI scheme"),
        (MARKDOWN_AUTHORITY_URI, "unsupported URI scheme"),
        (EMPHASIS_ABSOLUTE_PATH, "absolute path"),
        (HTML, "HTML content"),
        (RUNTIME_UUID, "runtime UUID"),
        (PRIVATE_PATH, "private or raw path part"),
        *SENSITIVE_TEXT,
    )
    for candidate in _decoded_text_variants(text, subject):
        http_spans = _validate_uri_candidates(candidate, subject, strict=False)
        for pattern, label in content_checks:
            if pattern.search(candidate):
                raise ValidationError(
                    f"privacy threat ({label}) in registered evidence: {subject}"
                )
        portable_text = _without_relative_globs(_without_spans(candidate, http_spans))
        path_candidates = (
            portable_text,
            _without_markdown_spans(portable_text, MARKDOWN_EMPHASIS),
        )
        for path_candidate in path_candidates:
            for pattern, label in V2_PATH_CHECKS:
                if pattern.search(path_candidate):
                    raise ValidationError(
                        f"privacy threat ({label}) in registered evidence: {subject}"
                    )
        _validate_uri_candidates(portable_text, subject)
        _validate_uri_candidates(candidate, subject)


def _scan(path: Path, contract_version: int) -> None:
    text = _read_utf8(path, "registered evidence")
    if LFS_POINTER.fullmatch(text):
        raise ValidationError(f"Git LFS pointers are not accepted evidence: {path}")
    if contract_version >= 2 and path.suffix.lower() == ".json":
        try:
            payload = json.loads(text, object_pairs_hook=_unique_json_object)
        except ValidationError:
            raise
        except (ValueError, RecursionError) as exc:
            raise ValidationError(
                f"invalid registered JSON evidence: {path}: {exc}"
            ) from exc
        _scan_decoded_strings(payload, path, contract_version)
    elif contract_version >= 2:
        _scan_decoded_strings(text, path, contract_version)
    else:
        _scan_text(text, path, contract_version)


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValidationError(f"duplicate JSON key: {key}")
        payload[key] = value
    return payload


def _embedded_json_values(text: str, subject: object) -> list[Any]:
    starts: list[int] = []
    for index, char in enumerate(text):
        if char not in '[{"':
            continue
        starts.append(index)
        if len(starts) > MAX_EMBEDDED_JSON_ATTEMPTS:
            raise ValidationError(
                f"nested JSON exceeds attempt limit in registered evidence: {subject}"
            )
    if not starts:
        return []
    try:
        encoded_bytes = len(text.encode("utf-8"))
    except UnicodeError as exc:
        raise ValidationError(
            f"invalid Unicode in registered evidence: {subject}"
        ) from exc
    if encoded_bytes > MAX_NESTED_JSON_BYTES:
        raise ValidationError(
            f"nested JSON exceeds scan limit in registered evidence: {subject}"
        )
    decoder = json.JSONDecoder(object_pairs_hook=_unique_json_object)
    values: list[Any] = []
    for start in starts:
        try:
            value, _ = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            continue
        except ValidationError:
            raise
        except ValueError as exc:
            raise ValidationError(
                f"invalid nested JSON value in registered evidence: {subject}"
            ) from exc
        except RecursionError as exc:
            raise ValidationError(
                f"nested JSON exceeds parser depth in registered evidence: {subject}"
            ) from exc
        values.append(value)
        if len(values) > MAX_EMBEDDED_JSON_VALUES:
            raise ValidationError(
                f"nested JSON exceeds candidate limit in registered evidence: {subject}"
            )
    return values


def _scan_decoded_strings(
    value: Any, subject: object, contract_version: int, depth: int = 0
) -> None:
    if contract_version < 2:
        return
    pending: list[tuple[Any, int, int]] = [(value, depth, 0)]
    visited = 0
    while pending:
        item, embedded_depth, structure_depth = pending.pop()
        visited += 1
        if visited > MAX_JSON_STRUCTURE_NODES:
            raise ValidationError(
                f"nested JSON exceeds node limit in registered evidence: {subject}"
            )
        if structure_depth > MAX_JSON_STRUCTURE_DEPTH:
            raise ValidationError(
                f"nested JSON exceeds structure depth in registered evidence: {subject}"
            )
        if isinstance(item, str):
            _scan_text(item, subject, contract_version)
            for candidate in _decoded_text_variants(item, subject):
                for nested in _embedded_json_values(candidate, subject):
                    if embedded_depth >= MAX_NESTED_JSON_DEPTH:
                        raise ValidationError(
                            f"nested JSON exceeds scan depth in registered evidence: {subject}"
                        )
                    pending.append((nested, embedded_depth + 1, structure_depth + 1))
        elif isinstance(item, dict):
            for key, nested in item.items():
                pending.append((key, embedded_depth, structure_depth + 1))
                pending.append((nested, embedded_depth, structure_depth + 1))
        elif isinstance(item, list):
            pending.extend(
                (nested, embedded_depth, structure_depth + 1) for nested in item
            )


def _json_payload(
    path: Path, bundle_id: str, label: str, contract_version: int
) -> dict[str, Any]:
    try:
        payload = json.loads(
            _read_utf8(path, label), object_pairs_hook=_unique_json_object
        )
    except ValidationError:
        raise
    except (ValueError, OSError, RecursionError) as exc:
        raise ValidationError(f"invalid {label} JSON for {bundle_id}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("bundle_id") != bundle_id:
        raise ValidationError(f"{label} identity mismatch for {bundle_id}")
    _scan_decoded_strings(payload, path, contract_version)
    return payload


def _validate_handoff(path: Path, bundle: dict[str, Any]) -> None:
    bundle_id = bundle["id"]
    payload = _json_payload(path, bundle_id, "handoff", _contract_version(bundle))
    if (
        type(payload.get("schema_version")) is not int
        or payload["schema_version"] != 1
        or payload.get("task") != bundle["task"]
        or payload.get("status") != "accepted"
        or payload.get("review") != {"architect": "APPROVED", "critic": "APPROVED"}
    ):
        raise ValidationError(f"handoff acceptance mismatch for {bundle_id}")
    if _contract_version(bundle) >= 2 and (
        set(payload) != HANDOFF_FIELDS_V2
        or payload.get("predecessor_bundle_id") != bundle.get("predecessor_bundle_id")
        or payload.get("predecessor_bundle_sha256")
        != bundle.get("predecessor_bundle_sha256")
        or payload.get("predecessor_chain_sha256")
        != bundle.get("predecessor_chain_sha256")
        or not isinstance(payload.get("roles"), list)
        or not all(isinstance(value, str) for value in payload["roles"])
        or len(payload["roles"]) != len(REQUIRED_FAMILIES)
        or set(payload["roles"]) != REQUIRED_FAMILIES
        or not isinstance(payload.get("execution"), dict)
        or set(payload["execution"]) != {"mode", "next_package", "write_scope"}
        or not all(
            isinstance(value, str) and value.strip()
            for value in payload["execution"].values()
        )
        or not isinstance(payload.get("constraints"), list)
        or not all(isinstance(value, str) for value in payload["constraints"])
    ):
        raise ValidationError(f"handoff contract mismatch for {bundle_id}")


def _validate_acceptance(
    path: Path, bundle_id: str, task: str, contract_version: int
) -> None:
    payload = _json_payload(path, bundle_id, "acceptance record", contract_version)
    if (
        type(payload.get("schema_version")) is not int
        or payload["schema_version"] != 1
        or payload.get("actor_class") != "repository-owner"
        or payload.get("instruction_channel") != "direct-user-instruction"
        or not isinstance(payload.get("accepted_scope"), str)
        or not payload["accepted_scope"].strip()
        or ("task" in payload and payload["task"] != task)
        or (contract_version >= 2 and payload.get("task") != task)
    ):
        raise ValidationError(f"acceptance record semantics mismatch for {bundle_id}")
    if contract_version >= 2 and (
        set(payload) != ACCEPTANCE_FIELDS_V2
        or payload.get("status") != "accepted"
        or not isinstance(payload.get("excluded_scope"), list)
        or not all(isinstance(value, str) for value in payload["excluded_scope"])
        or not isinstance(payload.get("date"), str)
        or not ISO_DATE.fullmatch(payload["date"])
        or not isinstance(payload.get("request_digest"), str)
        or not HEX_64.fullmatch(payload["request_digest"])
        or not isinstance(payload.get("request_digest_normalization"), str)
        or not payload["request_digest_normalization"].strip()
    ):
        raise ValidationError(f"acceptance record contract mismatch for {bundle_id}")


def _validate_review(path: Path, bundle: dict[str, Any]) -> None:
    bundle_id = bundle["id"]
    text = _read_utf8(path, "review")
    if _contract_version(bundle) >= 2 or text.lstrip().startswith("{"):
        payload = _json_payload(path, bundle_id, "review", _contract_version(bundle))
        if (
            set(payload) != REVIEW_FIELDS_V2
            or type(payload.get("schema_version")) is not int
            or payload["schema_version"] != 1
            or payload.get("task") != bundle["task"]
            or payload.get("status") != "approved"
            or payload.get("architect") != "APPROVED"
            or payload.get("critic") != "APPROVED"
        ):
            raise ValidationError(f"review contract mismatch for {bundle_id}")
        return
    for role in ("Architect", "Critic"):
        verdicts = re.findall(rf"(?im)^##\s+{role}\s+verdict:\s+([A-Z]+)\s*$", text)
        if verdicts != ["APPROVED"]:
            raise ValidationError(f"review verdict mismatch for {bundle_id}: {role}")


def _parse_registry(payload: bytes) -> dict[str, Any]:
    if len(payload) > MAX_REGISTRY_BYTES:
        raise ValidationError("registry exceeds byte limit")
    try:
        text = payload.decode("utf-8")
    except UnicodeError as exc:
        raise ValidationError(f"invalid UTF-8 registry: {exc}") from exc
    _scan_text(text, REGISTRY)
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ValidationError(f"invalid registry TOML: {exc}") from exc
    _scan_decoded_strings(data, REGISTRY, contract_version=2)
    unknown = set(data) - REGISTRY_FIELDS
    if unknown:
        raise ValidationError(f"unknown registry fields: {sorted(unknown)}")
    if type(data.get("schema_version")) is not int or data["schema_version"] not in {
        1,
        2,
    }:
        raise ValidationError("registry schema_version must be 1 or 2")
    bundles = data.get("bundle")
    if not isinstance(bundles, list) or not bundles:
        raise ValidationError("registry must contain at least one bundle")
    if len(bundles) > MAX_REGISTRY_BUNDLES:
        raise ValidationError("registry exceeds bundle-count limit")
    artifact_count = 0
    for bundle in bundles:
        if not isinstance(bundle, dict):
            raise ValidationError("registry bundle must be a mapping")
        unknown = set(bundle) - BUNDLE_FIELDS
        if unknown:
            raise ValidationError(
                f"unknown bundle fields for {bundle.get('id')}: {sorted(unknown)}"
            )
        artifacts = bundle.get("artifact")
        if not isinstance(artifacts, list):
            raise ValidationError(f"bundle {bundle.get('id')} artifacts must be a list")
        if len(artifacts) > MAX_ARTIFACTS_PER_BUNDLE:
            raise ValidationError(
                f"bundle {bundle.get('id')} exceeds artifact-count limit"
            )
        artifact_count += len(artifacts)
        if artifact_count > MAX_REGISTRY_ARTIFACTS:
            raise ValidationError("registry exceeds total artifact-count limit")
        string_fields = (
            "id",
            "task",
            "status",
            "classification",
            "baseline_commit",
            "handoff_sha256",
            "acceptance_sha256",
            "predecessor_registry_commit",
            "superseded_by",
        )
        for field in string_fields:
            if field in bundle and not isinstance(bundle[field], str):
                raise ValidationError(
                    f"bundle {bundle.get('id')} field {field} must be a string"
                )
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                raise ValidationError(
                    f"bundle {bundle.get('id')} artifact must be a mapping"
                )
            unknown = set(artifact) - ARTIFACT_FIELDS
            if unknown:
                raise ValidationError(
                    f"unknown artifact fields for {bundle.get('id')}: {sorted(unknown)}"
                )
            for field in ("family", "role", "path", "native_path", "sha256"):
                if not isinstance(artifact.get(field), str):
                    raise ValidationError(
                        f"bundle {bundle.get('id')} artifact field {field} must be a string"
                    )
            if type(artifact.get("bytes")) is not int:
                raise ValidationError(
                    f"bundle {bundle.get('id')} artifact bytes must be an integer"
                )
            review_kinds = artifact.get("review_kinds", [])
            if not isinstance(review_kinds, list) or not all(
                isinstance(value, str) for value in review_kinds
            ):
                raise ValidationError(
                    f"bundle {bundle.get('id')} review_kinds must be a string list"
                )
            if len(review_kinds) != len(set(review_kinds)):
                raise ValidationError(
                    f"bundle {bundle.get('id')} review_kinds must be unique"
                )
            if artifact.get("family") != "review" and review_kinds:
                raise ValidationError("only review artifacts may declare review_kinds")
    return data


def load_registry(path: Path, *, live: bool = True) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValidationError(f"registry must be a regular file: {path}")
    with path.open("rb") as stream:
        registry = _parse_registry(stream.read(MAX_REGISTRY_BYTES + 1))
    if live and registry["schema_version"] != 2:
        raise ValidationError("live registry schema_version must be 2")
    return registry


def _artifacts(bundle: dict[str, Any]) -> list[Artifact]:
    items = bundle.get("artifact")
    if not isinstance(items, list) or not items:
        raise ValidationError(f"bundle {bundle.get('id')} has no artifacts")
    try:
        return [
            Artifact(
                family=item["family"],
                role=item["role"],
                path=item["path"],
                native_path=item["native_path"],
                sha256=item["sha256"],
                bytes=item["bytes"],
                review_kinds=tuple(item.get("review_kinds", ())),
            )
            for item in items
        ]
    except (KeyError, TypeError) as exc:
        raise ValidationError(f"invalid artifact in {bundle.get('id')}: {exc}") from exc


def _validate_baseline(repo: Path, bundle_id: str, baseline: object) -> None:
    if not HEX_40.fullmatch(str(baseline or "")):
        raise ValidationError(f"invalid baseline commit for {bundle_id}")
    commit = subprocess.run(
        ["git", "cat-file", "-e", f"{baseline}^{{commit}}"],
        cwd=repo,
        check=False,
        capture_output=True,
    )
    if commit.returncode:
        raise ValidationError(
            f"baseline is not a git commit for {bundle_id}: {baseline}"
        )
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", str(baseline), "HEAD"],
        cwd=repo,
        check=False,
        capture_output=True,
    )
    if ancestor.returncode:
        raise ValidationError(
            f"baseline is not an ancestor of HEAD for {bundle_id}: {baseline}"
        )


def validate_registry(
    repo: Path, registry_path: Path, *, live: bool = True
) -> set[str]:
    registry = load_registry(registry_path, live=live)
    bundles = registry["bundle"]
    ids: set[str] = set()
    owned: set[str] = set()
    current_tasks: set[str] = set()
    total_artifact_bytes = 0
    parsed: dict[str, tuple[dict[str, Any], list[Artifact]]] = {}
    for bundle in bundles:
        bundle_id = bundle.get("id")
        task = bundle.get("task")
        status = bundle.get("status")
        contract_version = _contract_version(bundle)
        predecessor_id = bundle.get("predecessor_bundle_id")
        predecessor_digest = bundle.get("predecessor_bundle_sha256")
        predecessor_chain = bundle.get("predecessor_chain_sha256")
        if (
            not isinstance(bundle_id, str)
            or not ID.fullmatch(bundle_id)
            or bundle_id in ids
        ):
            raise ValidationError(f"duplicate or invalid bundle id: {bundle_id}")
        if not isinstance(task, str) or not ID.fullmatch(task):
            raise ValidationError(f"invalid task for {bundle_id}: {task}")
        if status not in {"current", "superseded"}:
            raise ValidationError(f"invalid status for {bundle_id}: {status}")
        if (
            registry["schema_version"] >= 2
            and status == "current"
            and contract_version < 2
        ):
            raise ValidationError(
                f"schema v2 current bundle must use contract v2: {bundle_id}"
            )
        if contract_version >= 2:
            if predecessor_id is None:
                if predecessor_digest is not None or predecessor_chain is not None:
                    raise ValidationError(
                        f"contract v2 bundle {bundle_id} has orphan predecessor receipts"
                    )
            elif (
                not isinstance(predecessor_id, str)
                or not ID.fullmatch(predecessor_id)
                or not isinstance(predecessor_digest, str)
                or not HEX_64.fullmatch(predecessor_digest)
                or not isinstance(predecessor_chain, str)
                or not HEX_64.fullmatch(predecessor_chain)
            ):
                raise ValidationError(
                    f"contract v2 bundle {bundle_id} lacks predecessor receipts"
                )
            if bundle.get("predecessor_registry_commit") is not None:
                raise ValidationError(
                    f"contract v2 bundle {bundle_id} uses a legacy predecessor commit"
                )
        _validate_baseline(repo, bundle_id, bundle.get("baseline_commit"))
        if bundle.get("classification") != "accepted-decision-evidence":
            raise ValidationError(f"invalid classification for {bundle_id}")
        if status == "current":
            if task in current_tasks:
                raise ValidationError(f"multiple current bundles for task {task}")
            current_tasks.add(task)
            if bundle.get("superseded_by"):
                raise ValidationError(f"current bundle {bundle_id} has a successor")
        elif not isinstance(bundle.get("superseded_by"), str):
            raise ValidationError(f"superseded bundle {bundle_id} lacks successor")
        ids.add(bundle_id)
        parsed[bundle_id] = (bundle, _artifacts(bundle))
    for bundle_id, (bundle, artifacts) in parsed.items():
        status = bundle["status"]
        contract_version = _contract_version(bundle)
        families = [artifact.family for artifact in artifacts]
        if set(families) != REQUIRED_FAMILIES:
            raise ValidationError(f"bundle {bundle_id} role families differ")
        repeated = {family for family in families if families.count(family) > 1}
        if repeated - {"specification"}:
            raise ValidationError(
                f"bundle {bundle_id} has invalid repeated role families"
            )
        reviews = [a for a in artifacts if a.family == "review"]
        if (
            len(reviews) != 1
            or len(reviews[0].review_kinds) != 2
            or set(reviews[0].review_kinds) != {"architect", "critic"}
        ):
            raise ValidationError(f"bundle {bundle_id} lacks Architect+Critic review")
        if (
            _contract_version(bundle) >= 2
            and PurePosixPath(reviews[0].path).suffix != ".json"
        ):
            raise ValidationError(f"contract v2 review must be JSON for {bundle_id}")
        handoffs = [a for a in artifacts if a.family == "handoff"]
        if (
            len(handoffs) != 1
            or bundle.get("handoff_sha256") != handoffs[0].sha256
            or not HEX_64.fullmatch(str(bundle.get("handoff_sha256", "")))
        ):
            raise ValidationError(f"invalid handoff for {bundle_id}")
        acceptances = [
            a
            for a in artifacts
            if a.family == "specification" and a.role == "acceptance-record"
        ]
        if (
            len(acceptances) != 1
            or PurePosixPath(acceptances[0].path).suffix != ".json"
            or bundle.get("acceptance_sha256") != acceptances[0].sha256
            or not HEX_64.fullmatch(str(bundle.get("acceptance_sha256", "")))
        ):
            raise ValidationError(f"invalid acceptance record for {bundle_id}")

        for artifact in artifacts:
            path = _safe_path(artifact.path)
            native = _safe_path(artifact.native_path)
            if artifact.family not in REQUIRED_FAMILIES or not ID.fullmatch(
                artifact.role
            ):
                raise ValidationError(f"invalid role for {artifact.path}")
            if contract_version >= 2 and not artifact.native_path.startswith(
                FAMILY_NATIVE_ROOT[artifact.family]
            ):
                raise ValidationError(
                    f"invalid native role path for {artifact.family}: "
                    f"{artifact.native_path}"
                )
            if artifact.path in owned:
                raise ValidationError(
                    f"artifact path has multiple owners: {artifact.path}"
                )
            if (
                not HEX_64.fullmatch(artifact.sha256)
                or type(artifact.bytes) is not int
                or artifact.bytes < 0
            ):
                raise ValidationError(f"invalid digest metadata: {artifact.path}")
            if artifact.bytes > MAX_ARTIFACT_BYTES:
                raise ValidationError(f"artifact exceeds byte limit: {artifact.path}")
            if status == "current":
                if (
                    artifact.path != artifact.native_path
                    or not artifact.path.startswith(CURRENT_ROOTS)
                ):
                    raise ValidationError(
                        f"current artifact not at native role path: {artifact.path}"
                    )
            else:
                prefix = f".omx/archive/accepted-bundles/{bundle_id}/"
                expected = prefix + artifact.native_path.removeprefix(".omx/")
                if artifact.path != expected or not str(native).startswith(
                    CURRENT_ROOTS
                ):
                    raise ValidationError(f"invalid archive placement: {artifact.path}")
            disk = repo / path
            if not disk.is_file() or disk.is_symlink():
                raise ValidationError(f"missing or unsafe artifact: {artifact.path}")
            try:
                actual_bytes = disk.stat().st_size
            except OSError as exc:
                raise ValidationError(
                    f"cannot stat registered artifact: {artifact.path}: {exc}"
                ) from exc
            if actual_bytes > MAX_ARTIFACT_BYTES:
                raise ValidationError(f"artifact exceeds byte limit: {artifact.path}")
            total_artifact_bytes += actual_bytes
            if total_artifact_bytes > MAX_TOTAL_ARTIFACT_BYTES:
                raise ValidationError(
                    "registered artifacts exceed aggregate byte limit"
                )
            if actual_bytes != artifact.bytes:
                raise ValidationError(f"hash or byte drift: {artifact.path}")
            if _digest(disk) != (artifact.sha256, artifact.bytes):
                raise ValidationError(f"hash or byte drift: {artifact.path}")
            _scan(disk, _contract_version(bundle))
            owned.add(artifact.path)
        _validate_handoff(repo / handoffs[0].path, bundle)
        _validate_acceptance(
            repo / acceptances[0].path,
            bundle_id,
            bundle["task"],
            _contract_version(bundle),
        )
        _validate_review(repo / reviews[0].path, bundle)
    bundle_map = {item_id: item[0] for item_id, item in parsed.items()}
    for bundle_id, (bundle, _) in parsed.items():
        predecessor_id = bundle.get("predecessor_bundle_id")
        if predecessor_id is None:
            continue
        predecessor = bundle_map.get(predecessor_id)
        if (
            predecessor is None
            or predecessor_id == bundle_id
            or predecessor["task"] != bundle["task"]
            or predecessor["status"] != "superseded"
            or predecessor.get("superseded_by") != bundle_id
        ):
            raise ValidationError(f"invalid predecessor link for {bundle_id}")
    chain_digests = _bundle_chain_digests(bundle_map)
    for bundle_id, (bundle, _) in parsed.items():
        if bundle["status"] == "current":
            continue
        successor_id = bundle.get("superseded_by")
        if not isinstance(successor_id, str):
            raise ValidationError(f"invalid successor for {bundle_id}")
        successor = parsed.get(successor_id)
        if not successor or successor[0]["task"] != bundle["task"]:
            raise ValidationError(f"invalid successor {successor_id} for {bundle_id}")
        _validate_archive_source(
            bundle,
            successor[0],
            bundle_map,
            chain_digests,
        )
    return owned


def _membership(bundle: dict[str, Any]) -> set[tuple[Any, ...]]:
    return {
        (
            item["family"],
            item["role"],
            item["native_path"],
            item["sha256"],
            item["bytes"],
            tuple(item.get("review_kinds", ())),
        )
        for item in bundle["artifact"]
    }


def bundle_content_sha256(bundle: dict[str, Any]) -> str:
    """Hash the accepted bundle state independently of archive placement."""
    metadata = {
        key: (
            _contract_version(bundle) if key == "contract_version" else bundle.get(key)
        )
        for key in IMMUTABLE_BUNDLE_FIELDS
    }
    artifacts = [
        {
            "family": item[0],
            "role": item[1],
            "native_path": item[2],
            "sha256": item[3],
            "bytes": item[4],
            "review_kinds": list(item[5]),
        }
        for item in sorted(_membership(bundle))
    ]
    payload = json.dumps(
        {"metadata": metadata, "artifacts": artifacts},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _chain_link_sha256(bundle: dict[str, Any], predecessor: str | None) -> str:
    payload = json.dumps(
        {
            "bundle_sha256": bundle_content_sha256(bundle),
            "predecessor_chain_sha256": predecessor,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _bundle_chain_digests(
    bundles: dict[str, dict[str, Any]],
) -> dict[str, str]:
    digests: dict[str, str] = {}
    depths: dict[str, int] = {}
    for bundle_id in bundles:
        if bundle_id in digests:
            continue
        chain: list[tuple[str, dict[str, Any]]] = []
        local_ids: set[str] = set()
        current_id: str | None = bundle_id
        while current_id is not None and current_id not in digests:
            if current_id in local_ids:
                raise ValidationError(f"cyclic predecessor chain for {current_id}")
            if len(chain) >= MAX_BUNDLE_CHAIN_LENGTH:
                raise ValidationError(
                    f"predecessor chain exceeds limit for {bundle_id}"
                )
            bundle = bundles.get(current_id)
            if bundle is None:
                raise ValidationError(f"missing predecessor bundle: {current_id}")
            local_ids.add(current_id)
            chain.append((current_id, bundle))
            predecessor_id = bundle.get("predecessor_bundle_id")
            current_id = predecessor_id if isinstance(predecessor_id, str) else None

        predecessor = digests.get(current_id) if current_id is not None else None
        predecessor_depth = depths.get(current_id, 0) if current_id is not None else 0
        for current_id, bundle in reversed(chain):
            predecessor_depth += 1
            if predecessor_depth > MAX_BUNDLE_CHAIN_LENGTH:
                raise ValidationError(
                    f"predecessor chain exceeds limit for {bundle_id}"
                )
            predecessor = _chain_link_sha256(bundle, predecessor)
            digests[current_id] = predecessor
            depths[current_id] = predecessor_depth
    return digests


def bundle_chain_sha256(
    bundle_id: str, bundles: dict[str, dict[str, Any]], seen: set[str] | None = None
) -> str:
    """Hash one bundle and every predecessor named by the registry."""
    if seen:
        current_id: str | None = bundle_id
        while current_id is not None:
            if current_id in seen:
                raise ValidationError(f"cyclic predecessor chain for {current_id}")
            bundle = bundles.get(current_id)
            if bundle is None:
                raise ValidationError(f"missing predecessor bundle: {current_id}")
            predecessor_id = bundle.get("predecessor_bundle_id")
            current_id = predecessor_id if isinstance(predecessor_id, str) else None
    return _bundle_chain_digests(bundles)[bundle_id]


def validate_transition(
    previous: dict[str, Any], current: dict[str, Any], *, live: bool = True
) -> None:
    if live and current.get("schema_version") != 2:
        raise ValidationError("live registry schema_version must be 2")
    if current["schema_version"] < previous.get("schema_version", 1):
        raise ValidationError("registry schema version cannot decrease")
    old = {bundle["id"]: bundle for bundle in previous.get("bundle", [])}
    new = {bundle["id"]: bundle for bundle in current.get("bundle", [])}
    for bundle_id, before in old.items():
        after = new.get(bundle_id)
        if not after:
            raise ValidationError(f"registered bundle removed: {bundle_id}")
        if before["status"] == "superseded" or after["status"] == "current":
            if before != after:
                raise ValidationError(f"accepted bundle mutated: {bundle_id}")
            continue
        if (
            after["status"] != "superseded"
            or _membership(before) != _membership(after)
            or any(before.get(key) != after.get(key) for key in IMMUTABLE_BUNDLE_FIELDS)
        ):
            raise ValidationError(f"invalid or non-identical supersession: {bundle_id}")
        successor = new.get(after.get("superseded_by"))
        if (
            not successor
            or successor["status"] != "current"
            or successor["task"] != before["task"]
            or _contract_version(successor) < _contract_version(before)
        ):
            raise ValidationError(f"invalid successor for {bundle_id}")
    for bundle_id, bundle in new.items():
        if bundle_id not in old and bundle["status"] != "current":
            raise ValidationError(f"new bundle must first be current: {bundle_id}")
        if (
            current.get("schema_version", 1) >= 2
            and bundle["status"] == "current"
            and _contract_version(bundle) < 2
        ):
            raise ValidationError(
                f"schema v2 current bundle must use contract v2: {bundle_id}"
            )


def _previous_registry(repo: Path, ref: str) -> dict[str, Any] | None:
    _run(repo, "git", "rev-parse", "--verify", f"{ref}^{{commit}}")
    object_name = f"{ref}:{REGISTRY}"
    tree = subprocess.run(
        ["git", "ls-tree", ref, "--", REGISTRY],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    entry = tree.stdout.strip()
    if not entry:
        return None
    try:
        metadata, path = entry.split("\t", 1)
        mode, kind, object_id = metadata.split()
    except ValueError as exc:
        raise ValidationError(f"invalid historical registry entry: {entry}") from exc
    if path != REGISTRY or mode not in {"100644", "100755"} or kind != "blob":
        raise ValidationError("historical registry must be a regular file")
    size = subprocess.run(
        ["git", "cat-file", "-s", object_id],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        registry_bytes = int(size.stdout.strip())
    except ValueError as exc:
        raise ValidationError(
            f"invalid registry size for {object_name}: {size.stdout.strip()}"
        ) from exc
    if registry_bytes > MAX_REGISTRY_BYTES:
        raise ValidationError("historical registry exceeds byte limit")
    shown = subprocess.run(
        ["git", "cat-file", "-p", object_id],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return _parse_registry(shown.stdout)


def _validate_archive_source(
    archived: dict[str, Any],
    successor: dict[str, Any],
    bundles: dict[str, dict[str, Any]],
    chain_digests: dict[str, str] | None = None,
) -> None:
    bundle_id = archived["id"]
    if successor.get("predecessor_bundle_id") != bundle_id:
        raise ValidationError(f"successor predecessor mismatch for {bundle_id}")
    if _contract_version(successor) < _contract_version(archived):
        raise ValidationError(f"contract version downgrade after {bundle_id}")
    digest = successor.get("predecessor_bundle_sha256")
    if _contract_version(successor) >= 2:
        if digest != bundle_content_sha256(archived):
            raise ValidationError(f"predecessor content digest drift for {bundle_id}")
        expected_chain = (
            chain_digests[bundle_id]
            if chain_digests is not None
            else bundle_chain_sha256(bundle_id, bundles)
        )
        if successor.get("predecessor_chain_sha256") != expected_chain:
            raise ValidationError(f"predecessor chain digest drift for {bundle_id}")
    elif digest is not None and (
        not HEX_64.fullmatch(str(digest)) or digest != bundle_content_sha256(archived)
    ):
        raise ValidationError(f"predecessor content digest drift for {bundle_id}")
    commit = successor.get("predecessor_registry_commit")
    if commit is not None and not HEX_40.fullmatch(str(commit)):
        raise ValidationError(f"invalid legacy predecessor commit for {bundle_id}")


def validate_tracked(repo: Path, owned: set[str]) -> None:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", ".omx"],
        cwd=repo,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        raise ValidationError(
            "git ls-files failed while checking OMX membership: "
            f"{os.fsdecode(result.stderr).strip()}"
        )
    tracked = {os.fsdecode(path) for path in result.stdout.split(b"\0") if path}
    if tracked != owned:
        raise ValidationError(
            f"tracked OMX membership differs; extra={sorted(tracked - owned)}, "
            f"missing={sorted(owned - tracked)}"
        )


def validate_committed_history(repo: Path, previous_ref: str) -> dict[str, Any] | None:
    resolved_previous = _run(
        repo, "git", "rev-parse", "--verify", f"{previous_ref}^{{commit}}"
    ).strip()
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", resolved_previous, "HEAD"],
        cwd=repo,
        check=False,
        capture_output=True,
    )
    if ancestor.returncode:
        raise ValidationError("previous_ref must be an ancestor of HEAD")

    first_parent_commits = set(
        filter(
            None, _run(repo, "git", "rev-list", "--first-parent", "HEAD").splitlines()
        )
    )
    if resolved_previous not in first_parent_commits:
        raise ValidationError("previous_ref must be on HEAD's first-parent chain")

    commits = [resolved_previous]
    commits.extend(
        filter(
            None,
            _run(
                repo,
                "git",
                "rev-list",
                "--first-parent",
                "--reverse",
                f"{resolved_previous}..HEAD",
            ).splitlines(),
        )
    )
    previous_registry: dict[str, Any] | None = None
    registry_seen = False
    with tempfile.TemporaryDirectory(prefix="omx-artifact-history-") as temporary:
        snapshot = Path(temporary) / "snapshot"
        added = False
        try:
            _run(
                repo,
                "git",
                "worktree",
                "add",
                "--detach",
                "--no-checkout",
                "--quiet",
                str(snapshot),
                commits[0],
            )
            added = True
            lfs_neutral = (
                "-c",
                "filter.lfs.process=",
                "-c",
                "filter.lfs.smudge=cat",
                "-c",
                "filter.lfs.required=false",
            )
            _run(
                snapshot,
                "git",
                *lfs_neutral,
                "sparse-checkout",
                "init",
                "--no-cone",
            )
            _run(
                snapshot,
                "git",
                *lfs_neutral,
                "sparse-checkout",
                "set",
                REGISTRY,
                ".omx/",
            )
            for commit in commits:
                _run(
                    snapshot,
                    "git",
                    *lfs_neutral,
                    "checkout",
                    "--detach",
                    "--force",
                    "--quiet",
                    commit,
                )
                try:
                    registry = _previous_registry(repo, commit)
                    if registry is None:
                        if registry_seen:
                            raise ValidationError(
                                "accepted OMX artifact registry must not disappear"
                            )
                        if (
                            commit != resolved_previous
                            and _run(
                                snapshot,
                                "git",
                                "diff",
                                "--name-only",
                                resolved_previous,
                                commit,
                                "--",
                                ".omx",
                            ).strip()
                        ):
                            raise ValidationError(
                                "registry-free OMX payload changed after previous_ref"
                            )
                        continue

                    registry_seen = True
                    owned = validate_registry(snapshot, snapshot / REGISTRY, live=False)
                    validate_tracked(snapshot, owned)
                    if previous_registry is not None:
                        validate_transition(previous_registry, registry, live=False)
                    previous_registry = registry
                except ValidationError as exc:
                    raise ValidationError(
                        f"committed snapshot {commit}: {exc}"
                    ) from exc
        finally:
            if added:
                _run(repo, "git", "worktree", "remove", "--force", str(snapshot))
    return previous_registry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--registry", type=Path, default=Path(REGISTRY))
    parser.add_argument("--previous-ref")
    parser.add_argument("--check-tracked", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    registry = args.registry if args.registry.is_absolute() else repo / args.registry
    try:
        owned = validate_registry(repo, registry)
        if args.previous_ref:
            previous = validate_committed_history(repo, args.previous_ref)
            if previous is not None:
                validate_transition(previous, load_registry(registry))
        if args.check_tracked:
            validate_tracked(repo, owned)
    except (
        OSError,
        KeyError,
        subprocess.CalledProcessError,
        tomllib.TOMLDecodeError,
        ValidationError,
    ) as exc:
        print(f"OMX artifact validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"OMX artifact validation passed: {len(owned)} registered artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
