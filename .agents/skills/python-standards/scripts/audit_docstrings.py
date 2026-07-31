#!/usr/bin/env python3
"""Audit Python docstrings directly or ratchet findings across Git states.

Direct audits report every finding in selected paths. Ratchet audits compare
only changed package files with the immediately preceding Git state, allowing
legacy debt while rejecting findings introduced by a commit, index update, or
worktree edit.
"""

from __future__ import annotations

import argparse
import ast
from enum import IntEnum
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

DiffMode: TypeAlias = Literal["committed", "staged", "unstaged", "all"]
Layer: TypeAlias = Literal["committed", "staged", "unstaged"]
JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
FindingRule: TypeAlias = Literal["docstring", "module-overview", "syntax"]
FindingKey: TypeAlias = tuple[str, str, FindingRule]

MODULE_OVERVIEW_KEYWORDS = (
    "contains",
    "provides",
    "owns",
    "responsib",
    "exports",
    "helpers",
    "wrappers",
    "adapters",
    "protocols",
)
LAYER_ORDER: dict[Layer, int] = {"committed": 0, "staged": 1, "unstaged": 2}
LAYER_STATE: dict[Layer, str] = {
    "committed": "merge-base->HEAD",
    "staged": "HEAD->index",
    "unstaged": "index->worktree",
}


class AuditError(RuntimeError):
    """A handled repository, Git, or source-read failure."""


class FindingSeverity(IntEnum):
    """Ordered ratchet severity for one semantic finding rule."""

    NONE = 0
    NONCOMPLIANT = 1
    ABSENT = 2


@dataclass(frozen=True)
class Finding:
    """One docstring audit finding."""

    path: Path
    """Absolute reporting path for the audited source."""

    line: int
    """One-based source line associated with the finding."""

    kind: str
    """Audited construct category, such as ``module``, ``method``, or ``field``."""

    name: str
    """Qualified source-level name of the audited construct."""

    rule: FindingRule
    """Stable semantic rule used to compare predecessor and successor debt."""

    severity: FindingSeverity
    """Ordered severity within ``rule``; larger values are worse."""

    message: str
    """Human-readable reason the source violates the audit threshold."""

    @property
    def key(self) -> FindingKey:
        """Return the stable symbol-and-rule key used by the ratchet."""

        return (self.kind, self.name, self.rule)

    def render(self, *, root: Path) -> str:
        """Format the finding relative to the reporting root when possible."""

        return (
            f"{_display_path(self.path, root)}:{self.line}: "
            f"{self.kind} {self.name}: {self.message}"
        )

    def as_json(self, *, root: Path) -> dict[str, JsonValue]:
        """Return a deterministic machine-readable representation."""

        return {
            "path": _display_path(self.path, root),
            "line": self.line,
            "kind": self.kind,
            "name": self.name,
            "message": self.message,
        }


@dataclass(frozen=True)
class GitChange:
    """One changed package path in a specific Git-state transition."""

    layer: Layer
    """Transition layer that owns this changed-file observation."""

    path: Path
    """Successor-side package path audited in this transition."""

    baseline_path: Path | None
    """Predecessor path, or ``None`` when no in-package ancestry exists."""

    def as_json(self) -> dict[str, JsonValue]:
        """Return the transition path and ancestry for machine consumers."""

        return {
            "layer": self.layer,
            "state": LAYER_STATE[self.layer],
            "path": self.path.as_posix(),
            "baseline_path": (
                self.baseline_path.as_posix()
                if self.baseline_path is not None
                else None
            ),
        }


@dataclass(frozen=True)
class TransitionFinding:
    """A finding observed in one exact Git-state transition."""

    change: GitChange
    """Changed path and transition in which the finding was observed."""

    finding: Finding
    """Successor-side docstring finding produced by the source audit."""

    @property
    def identity(self) -> tuple[Layer, Path, Path | None, int, str, str, str]:
        """Return an exact transition identity for deterministic deduplication."""

        return (
            self.change.layer,
            self.change.path,
            self.change.baseline_path,
            self.finding.line,
            self.finding.kind,
            self.finding.name,
            self.finding.message,
        )

    def as_json(self, *, root: Path) -> dict[str, JsonValue]:
        """Return a finding annotated with its layer and state transition."""

        payload = self.finding.as_json(root=root)
        payload["layer"] = self.change.layer
        payload["state"] = LAYER_STATE[self.change.layer]
        payload["baseline_path"] = (
            self.change.baseline_path.as_posix()
            if self.change.baseline_path is not None
            else None
        )
        return payload


def _display_path(path: Path, root: Path) -> str:
    """Render ``path`` relative to ``root`` when it is contained there."""

    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _is_public_name(name: str) -> bool:
    return not name.startswith("_")


def _doc_length(text: str | None) -> int:
    if not text:
        return 0
    normalized = " ".join(line.strip() for line in text.splitlines() if line.strip())
    return len(normalized)


def _has_module_overview(text: str | None) -> bool:
    if not text:
        return False
    non_empty = [line.strip() for line in text.splitlines() if line.strip()]
    lower = text.lower()
    return len(non_empty) >= 2 and any(
        keyword in lower for keyword in MODULE_OVERVIEW_KEYWORDS
    )


def _iter_python_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix == ".py":
            files.append(path.resolve())
        elif path.is_dir():
            files.extend(
                candidate.resolve()
                for candidate in path.rglob("*.py")
                if "__pycache__" not in candidate.parts
            )
    return sorted(set(files))


def _adjacent_field_doc(class_node: ast.ClassDef, index: int) -> str | None:
    """Return the literal immediately following an annotated class field."""

    if index + 1 >= len(class_node.body):
        return None
    candidate = class_node.body[index + 1]
    if (
        isinstance(candidate, ast.Expr)
        and isinstance(candidate.value, ast.Constant)
        and isinstance(candidate.value.value, str)
    ):
        return candidate.value.value
    return None


def _symbol_doc_findings(
    *,
    path: Path,
    tree: ast.Module,
    min_symbol_chars: int,
) -> list[Finding]:
    findings: list[Finding] = []

    def check_doc(
        *, node: ast.AST, kind: str, name: str, doc: str | None = None
    ) -> None:
        text = doc
        if doc is None and isinstance(
            node,
            ast.AsyncFunctionDef | ast.FunctionDef | ast.ClassDef | ast.Module,
        ):
            text = ast.get_docstring(node, clean=False)
        length = _doc_length(text)
        if length == 0:
            findings.append(
                Finding(
                    path,
                    getattr(node, "lineno", 1),
                    kind,
                    name,
                    "docstring",
                    FindingSeverity.ABSENT,
                    "missing docstring",
                )
            )
        elif length < min_symbol_chars:
            findings.append(
                Finding(
                    path,
                    getattr(node, "lineno", 1),
                    kind,
                    name,
                    "docstring",
                    FindingSeverity.NONCOMPLIANT,
                    f"docstring is short ({length} chars < {min_symbol_chars})",
                )
            )

    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and _is_public_name(
            node.name
        ):
            check_doc(node=node, kind="function", name=node.name)
        if not isinstance(node, ast.ClassDef) or not _is_public_name(node.name):
            continue
        check_doc(node=node, kind="class", name=node.name)
        for index, child in enumerate(node.body):
            if isinstance(
                child, ast.FunctionDef | ast.AsyncFunctionDef
            ) and _is_public_name(child.name):
                check_doc(node=child, kind="method", name=f"{node.name}.{child.name}")
            elif (
                isinstance(child, ast.AnnAssign)
                and isinstance(child.target, ast.Name)
                and _is_public_name(child.target.id)
            ):
                check_doc(
                    node=child,
                    kind="field",
                    name=f"{node.name}.{child.target.id}",
                    doc=_adjacent_field_doc(node, index),
                )
    return findings


def audit_source(
    *,
    source: str,
    path: Path,
    min_module_chars: int,
    min_symbol_chars: int,
    check_module_overview: bool,
) -> list[Finding]:
    """Return findings for one Python source string, including parse failures."""

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        line = exc.lineno if exc.lineno is not None else 1
        return [
            Finding(
                path,
                line,
                "file",
                path.name,
                "syntax",
                FindingSeverity.NONCOMPLIANT,
                f"could not parse file: {exc.msg}",
            )
        ]

    findings: list[Finding] = []
    module_doc = ast.get_docstring(tree, clean=False)
    module_length = _doc_length(module_doc)
    if module_length == 0:
        findings.append(
            Finding(
                path,
                1,
                "module",
                path.stem,
                "docstring",
                FindingSeverity.ABSENT,
                "missing module docstring",
            )
        )
    elif module_length < min_module_chars:
        findings.append(
            Finding(
                path,
                1,
                "module",
                path.stem,
                "docstring",
                FindingSeverity.NONCOMPLIANT,
                f"module docstring is short ({module_length} chars < {min_module_chars})",
            )
        )
    if (
        check_module_overview
        and module_doc is not None
        and not _has_module_overview(module_doc)
    ):
        findings.append(
            Finding(
                path,
                1,
                "module",
                path.stem,
                "module-overview",
                FindingSeverity.NONCOMPLIANT,
                "module docstring may be missing a high-level overview of contents and responsibilities",
            )
        )
    findings.extend(
        _symbol_doc_findings(path=path, tree=tree, min_symbol_chars=min_symbol_chars)
    )
    return findings


def audit_file(
    *,
    path: Path,
    min_module_chars: int,
    min_symbol_chars: int,
    check_module_overview: bool,
) -> list[Finding]:
    """Return findings for one Python file or raise a handled read error."""

    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise AuditError(f"could not read {path}: {exc}") from exc
    return audit_source(
        source=source,
        path=path,
        min_module_chars=min_module_chars,
        min_symbol_chars=min_symbol_chars,
        check_module_overview=check_module_overview,
    )


def _git(repo: Path, *args: str) -> str:
    """Run Git and return stdout, converting failures into ``AuditError``."""

    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            text=True,
            capture_output=True,
            check=False,
        )
    except (OSError, UnicodeError) as exc:
        raise AuditError(f"could not execute Git: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown Git error"
        raise AuditError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def _git_bytes(repo: Path, *args: str) -> bytes:
    """Run Git and return raw stdout for NUL-delimited path output."""

    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise AuditError(f"could not execute Git: {exc}") from exc
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace").strip()
        stdout = result.stdout.decode(errors="replace").strip()
        detail = stderr or stdout or "unknown Git error"
        raise AuditError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def _git_root(cwd: Path) -> Path:
    """Resolve the containing Git worktree."""

    return Path(_git(cwd, "rev-parse", "--show-toplevel").strip()).resolve()


def _verify_commit(repo: Path, ref: str) -> str:
    """Resolve a ref to a commit or raise a concise handled error."""

    try:
        return _git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").strip()
    except AuditError as exc:
        raise AuditError(f"invalid Git base: {ref}") from exc


def _merge_base(repo: Path, base: str) -> str:
    """Return the single merge base shared by ``base`` and ``HEAD``."""

    output = _git(repo, "merge-base", base, "HEAD").splitlines()
    if len(output) != 1 or not output[0]:
        raise AuditError(f"could not determine one merge base for {base} and HEAD")
    return output[0]


def _is_package_python(path: Path, package_root: Path) -> bool:
    return path.suffix == ".py" and path.is_relative_to(package_root)


def _parse_name_status(
    output: bytes, *, layer: Layer, package_root: Path
) -> list[GitChange]:
    """Parse NUL-delimited changed paths without decoding filename bytes as UTF-8."""

    changes: list[GitChange] = []
    fields = output.split(b"\0")
    if fields[-1:] == [b""]:
        fields.pop()
    index = 0
    while index < len(fields):
        try:
            status = fields[index].decode("ascii")
        except UnicodeDecodeError as exc:
            raise AuditError(
                "git name-status output contained a non-ASCII status"
            ) from exc
        path_count = 2 if status.startswith(("R", "C")) else 1
        if index + path_count >= len(fields):
            raise AuditError("git name-status output ended inside a path record")
        paths = [
            Path(os.fsdecode(raw)) for raw in fields[index + 1 : index + 1 + path_count]
        ]
        index += path_count + 1
        if status.startswith("R"):
            source, destination = paths
            if _is_package_python(destination, package_root):
                baseline_path = (
                    source if _is_package_python(source, package_root) else None
                )
                changes.append(GitChange(layer, destination, baseline_path))
        elif status.startswith("C"):
            destination = paths[1]
            if _is_package_python(destination, package_root):
                changes.append(GitChange(layer, destination, None))
        elif status != "D":
            path = paths[0]
            if _is_package_python(path, package_root):
                changes.append(GitChange(layer, path, None if status == "A" else path))
    return changes


def _layer_changes(
    *,
    repo: Path,
    layer: Layer,
    merge_base: str | None,
    package_root: Path,
) -> list[GitChange]:
    """Return package changes for one predecessor-to-successor transition."""

    common = ("--name-status", "-z", "-M", "-C", "--find-copies-harder")
    if layer == "committed":
        if merge_base is None:
            raise AuditError("committed audit requires a merge base")
        output = _git_bytes(repo, "diff", *common, merge_base, "HEAD", "--")
    elif layer == "staged":
        output = _git_bytes(repo, "diff", "--cached", *common, "HEAD", "--")
    else:
        output = _git_bytes(repo, "diff", *common, "--")
    changes = _parse_name_status(output, layer=layer, package_root=package_root)
    if layer == "unstaged":
        untracked = _git_bytes(repo, "ls-files", "-z", "--others", "--exclude-standard")
        for raw_path in untracked.split(b"\0"):
            if not raw_path:
                continue
            path = Path(os.fsdecode(raw_path))
            if _is_package_python(path, package_root):
                changes.append(GitChange(layer, path, None))
    by_identity = {(change.path, change.baseline_path): change for change in changes}
    return sorted(by_identity.values(), key=lambda change: change.path.as_posix())


def _git_blob(repo: Path, state: str, path: Path) -> str:
    """Read one UTF-8 source blob from a commit or the index."""

    spec = f":{path.as_posix()}" if state == "index" else f"{state}:{path.as_posix()}"
    try:
        return _git(repo, "show", spec)
    except AuditError as exc:
        raise AuditError(f"could not read {path.as_posix()} from {state}") from exc


def _worktree_source(repo: Path, path: Path) -> str:
    """Read one UTF-8 source file from the worktree."""

    try:
        return (repo / path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise AuditError(
            f"could not read worktree file {path.as_posix()}: {exc}"
        ) from exc


def _transition_sources(
    *, repo: Path, change: GitChange, merge_base: str | None
) -> tuple[str | None, str]:
    """Read predecessor and successor contents for one transition."""

    if change.layer == "committed":
        if merge_base is None:
            raise AuditError("committed audit requires a merge base")
        current = _git_blob(repo, "HEAD", change.path)
        baseline_state = merge_base
    elif change.layer == "staged":
        current = _git_blob(repo, "index", change.path)
        baseline_state = "HEAD"
    else:
        current = _worktree_source(repo, change.path)
        baseline_state = "index"
    baseline = (
        _git_blob(repo, baseline_state, change.baseline_path)
        if change.baseline_path is not None
        else None
    )
    return baseline, current


def _evaluate_layers(
    *,
    repo: Path,
    base: str,
    mode: DiffMode,
    package_root: Path,
    min_module_chars: int,
    min_symbol_chars: int,
    check_module_overview: bool,
) -> tuple[
    str | None,
    list[GitChange],
    list[TransitionFinding],
    list[TransitionFinding],
]:
    """Audit each selected Git transition independently against its predecessor."""

    merge_base = _merge_base(repo, base) if mode in {"committed", "all"} else None
    layers: tuple[Layer, ...] = (
        ("committed", "staged", "unstaged") if mode == "all" else (mode,)
    )
    changes: list[GitChange] = []
    findings: list[TransitionFinding] = []
    introduced: list[TransitionFinding] = []
    for layer in layers:
        layer_changes = _layer_changes(
            repo=repo,
            layer=layer,
            merge_base=merge_base,
            package_root=package_root,
        )
        changes.extend(layer_changes)
        for change in layer_changes:
            baseline_source, current_source = _transition_sources(
                repo=repo, change=change, merge_base=merge_base
            )
            display_path = (repo / change.path).resolve()
            current = audit_source(
                source=current_source,
                path=display_path,
                min_module_chars=min_module_chars,
                min_symbol_chars=min_symbol_chars,
                check_module_overview=check_module_overview,
            )
            baseline = (
                audit_source(
                    source=baseline_source,
                    path=display_path,
                    min_module_chars=min_module_chars,
                    min_symbol_chars=min_symbol_chars,
                    check_module_overview=check_module_overview,
                )
                if baseline_source is not None
                else []
            )
            baseline_severity: dict[FindingKey, FindingSeverity] = {}
            for finding in baseline:
                baseline_severity[finding.key] = max(
                    finding.severity,
                    baseline_severity.get(finding.key, FindingSeverity.NONE),
                )
            transition_findings = [
                TransitionFinding(change, finding) for finding in current
            ]
            findings.extend(transition_findings)
            introduced.extend(
                finding
                for finding in transition_findings
                if baseline_severity.get(finding.finding.key, FindingSeverity.NONE)
                < finding.finding.severity
            )
    changes.sort(key=lambda item: (LAYER_ORDER[item.layer], item.path.as_posix()))
    findings = _dedupe_transition_findings(findings)
    introduced = _dedupe_transition_findings(introduced)
    return merge_base, changes, findings, introduced


def _dedupe_transition_findings(
    findings: list[TransitionFinding],
) -> list[TransitionFinding]:
    """Deduplicate only identical findings from the same exact transition."""

    unique = {finding.identity: finding for finding in findings}
    return sorted(
        unique.values(),
        key=lambda item: (
            LAYER_ORDER[item.change.layer],
            item.change.path.as_posix(),
            item.finding.line,
            item.finding.kind,
            item.finding.name,
            item.finding.message,
        ),
    )


def _emit(
    *,
    output_format: Literal["text", "json"],
    payload: dict[str, JsonValue],
    text_lines: list[str],
    summary: str,
    exit_code: Literal[0, 1, 2],
) -> int:
    """Serialize one command result and return its stable exit code."""

    if output_format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for line in text_lines:
            print(line)
        print(summary, file=sys.stderr)
    return exit_code


def _error_result(*, output_format: Literal["text", "json"], message: str) -> int:
    """Serialize a handled operational error."""

    return _emit(
        output_format=output_format,
        payload={"status": "error", "error": message},
        text_lines=[],
        summary=message,
        exit_code=2,
    )


def _direct_audit(args: argparse.Namespace) -> int:
    """Run the direct-path audit with the shared output contract."""

    output_format: Literal["text", "json"] = args.format
    paths: list[str] = args.paths
    if not paths:
        return _error_result(
            output_format=output_format,
            message="paths are required unless --git-base is set",
        )
    files = _iter_python_files([Path(value).resolve() for value in paths])
    if not files:
        return _error_result(
            output_format=output_format,
            message="No Python files found.",
        )
    root = Path.cwd().resolve()
    findings: list[Finding] = []
    try:
        for path in files:
            findings.extend(
                audit_file(
                    path=path,
                    min_module_chars=args.min_module_chars,
                    min_symbol_chars=args.min_symbol_chars,
                    check_module_overview=args.check_module_overview,
                )
            )
    except AuditError as exc:
        return _error_result(output_format=output_format, message=str(exc))
    exit_code: Literal[0, 1] = 1 if findings else 0
    return _emit(
        output_format=output_format,
        payload={
            "status": "failed" if findings else "passed",
            "mode": "direct",
            "files": [_display_path(path, root) for path in files],
            "findings": [finding.as_json(root=root) for finding in findings],
        },
        text_lines=[finding.render(root=root) for finding in findings],
        summary=(
            f"{len(findings)} finding(s) across {len(files)} file(s)."
            if findings
            else f"No findings in {len(files)} file(s)."
        ),
        exit_code=exit_code,
    )


def _ratchet_audit(args: argparse.Namespace) -> int:
    """Run the selected Git-state ratchet with the shared output contract."""

    output_format: Literal["text", "json"] = args.format
    try:
        repo = _git_root(Path.cwd())
        base = _verify_commit(repo, args.git_base)
        merge_base, changes, findings, introduced = _evaluate_layers(
            repo=repo,
            base=base,
            mode=args.diff_mode,
            package_root=Path(args.package_root),
            min_module_chars=args.min_module_chars,
            min_symbol_chars=args.min_symbol_chars,
            check_module_overview=args.check_module_overview,
        )
    except AuditError as exc:
        message = str(exc)
        if "rev-parse --show-toplevel" in message:
            message = "current directory is not in a Git repository"
        return _error_result(output_format=output_format, message=message)
    exit_code: Literal[0, 1] = 1 if introduced else 0
    return _emit(
        output_format=output_format,
        payload={
            "status": "failed" if introduced else "passed",
            "mode": args.diff_mode,
            "base": base,
            "merge_base": merge_base,
            "changed_files": [change.as_json() for change in changes],
            "findings": [finding.as_json(root=repo) for finding in findings],
            "new_findings": [finding.as_json(root=repo) for finding in introduced],
        },
        text_lines=[
            f"[{finding.change.layer}] {finding.finding.render(root=repo)}"
            for finding in introduced
        ],
        summary=(
            f"Docstring ratchet: {len(introduced)} new finding(s); "
            f"{len(findings)} total finding(s) across {len(changes)} transition file(s)."
        ),
        exit_code=exit_code,
    )


def main() -> int:
    """Parse arguments and run a direct audit or Git-state ratchet."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Python file or directory to audit")
    parser.add_argument(
        "--min-module-chars",
        type=int,
        default=80,
        help="Minimum normalized character length for module docstrings",
    )
    parser.add_argument(
        "--min-symbol-chars",
        type=int,
        default=40,
        help="Minimum normalized character length for symbol and field docstrings",
    )
    parser.add_argument(
        "--check-module-overview",
        action="store_true",
        help="Flag module docstrings lacking a contents-and-responsibility overview",
    )
    parser.add_argument(
        "--git-base",
        help="Enable the changed-file ratchet against this Git commit or ref",
    )
    parser.add_argument(
        "--diff-mode",
        choices=("committed", "staged", "unstaged", "all"),
        default="all",
        help="Git transition to audit; all evaluates each transition independently",
    )
    parser.add_argument(
        "--package-root",
        default="aria_nbv/aria_nbv",
        help="Repo-relative package root included by the Git ratchet",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text)",
    )
    args = parser.parse_args()
    return _ratchet_audit(args) if args.git_base else _direct_audit(args)


if __name__ == "__main__":
    raise SystemExit(main())
