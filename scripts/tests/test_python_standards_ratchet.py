#!/usr/bin/env python3
"""Focused tests for Python docstring ownership and Git-state ratcheting."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import TypeAlias, cast

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / ".agents/skills/python-standards/scripts/audit_docstrings.py"
PACKAGE = Path("aria_nbv/aria_nbv")
GOOD_MODULE = (
    '"""Provide a sufficiently descriptive test module for ratchet verification.\n\n'
    'This module owns small public fixtures used only by the focused tests.\n"""\n\n'
)
GOOD_CLASS = 'class Payload:\n    """Represent a documented public payload for focused audit tests."""\n\n'
ACTIVE_OWNER_ROOTS = (
    ".agents/skills/",
    ".agents/references/",
    ".agents/plugins/",
    ".github/",
    ".codex/",
    "scripts/",
    "plugins/",
)
EXCLUDED_OWNER_ROOTS = (
    ".agents/memory/history/",
    ".agents/memory/transcripts/",
    ".agents/archive/",
    ".agents/specs/",
    ".omx/",
    "docs/archive/",
)


def _json_object(text: str) -> dict[str, JsonValue]:
    raw: object = json.loads(text)
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise AssertionError(f"expected JSON object, got {type(raw).__name__}")
    return cast(dict[str, JsonValue], raw)


def _array(payload: dict[str, JsonValue], key: str) -> list[JsonValue]:
    value = payload[key]
    if not isinstance(value, list):
        raise TypeError(f"expected {key} to be an array")
    return value


def _object(value: JsonValue) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise TypeError("expected JSON object item")
    return value


def _string(payload: dict[str, JsonValue], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str):
        raise TypeError(f"expected {key} to be a string")
    return value


def _stale_owner_paths(root: Path, alias: str) -> list[str]:
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        capture_output=True,
        check=True,
    ).stdout
    stale: list[str] = []
    for raw_path_bytes in tracked.split(b"\0"):
        if not raw_path_bytes:
            continue
        raw_path = os.fsdecode(raw_path_bytes)
        path = Path(raw_path)
        if raw_path.startswith(EXCLUDED_OWNER_ROOTS):
            continue
        if not (
            path.name == "AGENTS.md"
            or raw_path == "Makefile"
            or raw_path.startswith(ACTIVE_OWNER_ROOTS)
        ):
            continue
        absolute_path = root / path
        if not absolute_path.is_file():
            continue
        try:
            text = absolute_path.read_text(encoding="utf-8")
        except UnicodeError:
            continue
        if alias in text:
            stale.append(path.as_posix())
    return stale


class ActiveOwnershipTest(unittest.TestCase):
    """Protect the single owner across cached and untracked active surfaces."""

    def test_python_standards_is_the_only_active_owner(self) -> None:
        alias = "python-" + "docstrings"
        self.assertTrue((ROOT / ".agents/skills/python-standards/SKILL.md").is_file())
        self.assertFalse((ROOT / ".agents/skills" / alias).exists())
        self.assertEqual(_stale_owner_paths(ROOT, alias), [])

    def test_active_owner_scan_preserves_newline_in_alias_path(self) -> None:
        alias = "python-" + "docstrings"
        with tempfile.TemporaryDirectory() as tempdir:
            repo = Path(tempdir)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            hostile = repo / ".agents/skills" / f"legacy\n{alias}.md"
            hostile.parent.mkdir(parents=True)
            hostile.write_text(f"route: {alias}\n", encoding="utf-8")

            self.assertEqual(
                _stale_owner_paths(repo, alias),
                [hostile.relative_to(repo).as_posix()],
            )


class RatchetTest(unittest.TestCase):
    """Exercise each predecessor-to-successor Git transition."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)
        self._git("init", "-q")
        self._git("config", "user.email", "ratchet@example.invalid")
        self._git("config", "user.name", "Ratchet Test")
        self.package = self.repo / PACKAGE
        self.package.mkdir(parents=True)
        self._write("legacy.py", "value = 1\n")
        self._write("clean.py", GOOD_MODULE)
        self._git("add", ".")
        self._git("commit", "-qm", "baseline")
        self.base = self._git("rev-parse", "HEAD").stdout.strip()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.repo,
            text=True,
            capture_output=True,
            check=True,
        )

    def _write(self, name: str, source: str) -> None:
        (self.package / name).write_text(source, encoding="utf-8")

    def _run(
        self, mode: str = "all", base: str | None = None
    ) -> tuple[int, dict[str, JsonValue], str]:
        result = subprocess.run(
            [
                "python3",
                str(AUDIT),
                "--git-base",
                base or self.base,
                "--diff-mode",
                mode,
                "--format",
                "json",
            ],
            cwd=self.repo,
            text=True,
            capture_output=True,
            check=False,
        )
        return result.returncode, _json_object(result.stdout), result.stderr

    def test_added_file_has_no_baseline(self) -> None:
        self._write("added.py", "def undocumented():\n    return None\n")
        code, payload, stderr = self._run("unstaged")
        self.assertEqual((code, stderr), (1, ""))
        change = _object(_array(payload, "changed_files")[0])
        self.assertEqual(_string(change, "path"), "aria_nbv/aria_nbv/added.py")
        self.assertIsNone(change["baseline_path"])
        self.assertEqual(_string(change, "layer"), "unstaged")
        self.assertEqual(_string(change, "state"), "index->worktree")
        self.assertEqual(len(_array(payload, "new_findings")), 2)

    def test_staged_paths_preserve_newlines_and_tabs(self) -> None:
        names = ("line\nbreak.py", "tab\tname.py")
        for name in names:
            self._write(name, "def undocumented():\n    return None\n")
        self._git("add", ".")

        code, payload, stderr = self._run("staged")

        self.assertEqual((code, stderr), (1, ""))
        changes = [_object(value) for value in _array(payload, "changed_files")]
        self.assertEqual(
            {_string(change, "path") for change in changes},
            {f"{PACKAGE.as_posix()}/{name}" for name in names},
        )
        self.assertEqual(len(_array(payload, "new_findings")), 4)

    @unittest.skipUnless(os.name == "posix", "raw-byte filenames require POSIX")
    def test_untracked_and_staged_paths_preserve_non_utf8_bytes(self) -> None:
        raw_relatives = {
            os.fsencode(PACKAGE.as_posix()) + suffix
            for suffix in (b"/raw-\xfe.py", b"/raw-\xff.py")
        }
        for raw_relative in raw_relatives:
            raw_absolute = os.fsencode(self.repo) + b"/" + raw_relative
            with open(raw_absolute, "wb") as source_file:
                source_file.write(b"def undocumented():\n    return None\n")

        for mode in ("unstaged", "staged"):
            with self.subTest(mode=mode):
                if mode == "staged":
                    self._git("add", ".")
                code, payload, stderr = self._run(mode)
                self.assertEqual((code, stderr), (1, ""))
                changes = [_object(value) for value in _array(payload, "changed_files")]
                self.assertEqual(
                    {os.fsencode(_string(change, "path")) for change in changes},
                    raw_relatives,
                )
                self.assertEqual(len(_array(payload, "new_findings")), 4)

    def test_committed_uses_one_merge_base_for_paths_and_content(self) -> None:
        self._git("branch", "feature", self.base)
        self._git("checkout", "-qb", "upstream", self.base)
        self._write("legacy.py", GOOD_MODULE)
        self._git("add", ".")
        self._git("commit", "-qm", "fix upstream debt")
        upstream = self._git("rev-parse", "HEAD").stdout.strip()
        self._git("checkout", "-q", "feature")
        self._write("legacy.py", "value = 2\n")
        self._git("add", ".")
        self._git("commit", "-qm", "modify feature legacy")
        code, payload, _ = self._run("committed", upstream)
        self.assertEqual(code, 0)
        self.assertEqual(_string(payload, "merge_base"), self.base)
        self.assertEqual(_array(payload, "new_findings"), [])

    def test_committed_detects_new_finding_at_head(self) -> None:
        self._write("clean.py", GOOD_MODULE + "def committed():\n    return None\n")
        self._git("add", ".")
        self._git("commit", "-qm", "introduce committed finding")
        code, payload, _ = self._run("committed")
        self.assertEqual(code, 1)
        finding = _object(_array(payload, "new_findings")[0])
        self.assertEqual(
            (_string(finding, "layer"), _string(finding, "name")),
            ("committed", "committed"),
        )

    def test_staged_compares_head_to_index(self) -> None:
        self._write("clean.py", GOOD_MODULE + "def staged():\n    return None\n")
        self._git("add", str(PACKAGE / "clean.py"))
        code, payload, _ = self._run("staged")
        self.assertEqual(code, 1)
        finding = _object(_array(payload, "new_findings")[0])
        self.assertEqual(_string(finding, "name"), "staged")
        self.assertEqual(_string(finding, "state"), "HEAD->index")

    def test_staged_does_not_require_base_to_share_history(self) -> None:
        empty_tree = self._git("hash-object", "-t", "tree", "/dev/null").stdout.strip()
        unrelated = self._git(
            "commit-tree", empty_tree, "-m", "unrelated"
        ).stdout.strip()
        self._write("clean.py", GOOD_MODULE + "def staged():\n    return None\n")
        self._git("add", str(PACKAGE / "clean.py"))
        code, payload, _ = self._run("staged", unrelated)
        self.assertEqual(code, 1)
        self.assertIsNone(payload["merge_base"])

    def test_unstaged_compares_index_to_worktree(self) -> None:
        self._write("clean.py", GOOD_MODULE + "def indexed():\n    return None\n")
        self._git("add", str(PACKAGE / "clean.py"))
        self._write("clean.py", GOOD_MODULE + "def worktree():\n    return None\n")
        code, payload, _ = self._run("unstaged")
        self.assertEqual(code, 1)
        finding = _object(_array(payload, "new_findings")[0])
        self.assertEqual(_string(finding, "name"), "worktree")
        self.assertEqual(_string(finding, "state"), "index->worktree")

    def test_all_cannot_hide_bad_staged_snapshot_with_restoration(self) -> None:
        bad = GOOD_MODULE + "def staged_regression():\n    return None\n"
        self._write("clean.py", bad)
        self._git("add", str(PACKAGE / "clean.py"))
        self._write("clean.py", GOOD_MODULE)
        code, payload, _ = self._run("all")
        self.assertEqual(code, 1)
        findings = [_object(value) for value in _array(payload, "new_findings")]
        self.assertEqual(
            [(_string(item, "layer"), _string(item, "name")) for item in findings],
            [("staged", "staged_regression")],
        )

    def test_unchanged_legacy_debt_is_not_new_per_layer(self) -> None:
        self._write("legacy.py", "value = 2\n")
        self._git("add", str(PACKAGE / "legacy.py"))
        self._write("legacy.py", "value = 3\n")
        code, payload, _ = self._run("all")
        self.assertEqual(code, 0)
        self.assertEqual(len(_array(payload, "findings")), 2)
        self.assertEqual(_array(payload, "new_findings"), [])

    def test_edited_short_docstring_remains_legacy_debt(self) -> None:
        self._write("short.py", GOOD_MODULE + 'def legacy():\n    """Tiny."""\n')
        self._git("add", ".")
        self._git("commit", "-qm", "add short legacy docstring")
        base = self._git("rev-parse", "HEAD").stdout.strip()
        self._write("short.py", GOOD_MODULE + 'def legacy():\n    """Still tiny."""\n')
        code, payload, _ = self._run("unstaged", base)
        self.assertEqual(code, 0)
        self.assertEqual(len(_array(payload, "findings")), 1)
        self.assertEqual(_array(payload, "new_findings"), [])

    def test_missing_docstring_improved_to_short_is_not_new_debt(self) -> None:
        self._write("improved.py", GOOD_MODULE + "def legacy():\n    return None\n")
        self._git("add", ".")
        self._git("commit", "-qm", "add missing legacy docstring")
        base = self._git("rev-parse", "HEAD").stdout.strip()
        self._write(
            "improved.py",
            GOOD_MODULE + 'def legacy():\n    """Still short."""\n',
        )

        code, payload, _ = self._run("unstaged", base)

        self.assertEqual(code, 0)
        self.assertEqual(len(_array(payload, "findings")), 1)
        self.assertEqual(_array(payload, "new_findings"), [])

    def test_short_docstring_degraded_to_missing_is_new_debt(self) -> None:
        self._write(
            "degraded.py",
            GOOD_MODULE + 'def legacy():\n    """Still short."""\n',
        )
        self._git("add", ".")
        self._git("commit", "-qm", "add short legacy docstring")
        base = self._git("rev-parse", "HEAD").stdout.strip()
        self._write("degraded.py", GOOD_MODULE + "def legacy():\n    return None\n")

        code, payload, _ = self._run("unstaged", base)

        self.assertEqual(code, 1)
        findings = [_object(value) for value in _array(payload, "new_findings")]
        self.assertEqual(len(findings), 1)
        self.assertEqual(_string(findings[0], "name"), "legacy")
        self.assertEqual(_string(findings[0], "message"), "missing docstring")

    def test_in_package_rename_preserves_legacy_ancestry(self) -> None:
        self._git("mv", str(PACKAGE / "legacy.py"), str(PACKAGE / "renamed.py"))
        code, payload, _ = self._run("staged")
        self.assertEqual(code, 0)
        change = _object(_array(payload, "changed_files")[0])
        self.assertEqual(change["baseline_path"], "aria_nbv/aria_nbv/legacy.py")
        self.assertEqual(_array(payload, "new_findings"), [])

    def test_deleted_package_path_is_not_audit_target(self) -> None:
        self._git("rm", str(PACKAGE / "clean.py"))
        code, payload, _ = self._run("staged")
        self.assertEqual(code, 0)
        self.assertEqual(_array(payload, "changed_files"), [])

    def test_rename_from_outside_package_has_no_baseline(self) -> None:
        outside = self.repo / "outside.py"
        outside.write_text("value = 1\n", encoding="utf-8")
        self._git("add", "outside.py")
        self._git("commit", "-qm", "add outside source")
        self._git("mv", "outside.py", str(PACKAGE / "imported.py"))
        code, payload, _ = self._run("staged", self.base)
        self.assertEqual(code, 1)
        change = _object(_array(payload, "changed_files")[0])
        self.assertIsNone(change["baseline_path"])
        self.assertEqual(len(_array(payload, "new_findings")), 1)

    def test_copy_from_outside_package_has_no_baseline(self) -> None:
        outside = self.repo / "outside.py"
        outside.write_text("outside_only_value = 1729\n", encoding="utf-8")
        self._git("add", "outside.py")
        self._git("commit", "-qm", "add outside source")
        self._write("copied.py", outside.read_text(encoding="utf-8"))
        self._git("add", str(PACKAGE / "copied.py"))
        code, payload, _ = self._run("staged", self.base)
        self.assertEqual(code, 1)
        change = _object(_array(payload, "changed_files")[0])
        self.assertIsNone(change["baseline_path"])

    def test_copy_within_package_also_has_no_baseline(self) -> None:
        source = self.package / "legacy.py"
        self._write("copied_legacy.py", source.read_text(encoding="utf-8"))
        self._git("add", str(PACKAGE / "copied_legacy.py"))
        code, payload, _ = self._run("staged")
        self.assertEqual(code, 1)
        change = _object(_array(payload, "changed_files")[0])
        self.assertIsNone(change["baseline_path"])
        self.assertEqual(len(_array(payload, "new_findings")), 1)

    def test_invalid_base_is_machine_readable(self) -> None:
        code, payload, stderr = self._run(base="not-a-real-ref")
        self.assertEqual((code, stderr), (2, ""))
        self.assertEqual(_string(payload, "status"), "error")
        self.assertIn("invalid Git base", _string(payload, "error"))

    def test_clean_no_change_behavior(self) -> None:
        code, payload, stderr = self._run()
        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(_string(payload, "status"), "passed")
        self.assertEqual(_array(payload, "changed_files"), [])

    def test_field_debt_is_ratcheted(self) -> None:
        legacy_field = GOOD_MODULE + GOOD_CLASS + "    score: float\n"
        self._write("fields.py", legacy_field)
        self._git("add", ".")
        self._git("commit", "-qm", "add legacy field debt")
        base = self._git("rev-parse", "HEAD").stdout.strip()
        self._write("fields.py", legacy_field + "    _cache: int\n")
        code, payload, _ = self._run("unstaged", base)
        self.assertEqual(code, 0)
        self.assertEqual(_array(payload, "new_findings"), [])
        self._write("fields.py", legacy_field + "    label: str\n")
        code, payload, _ = self._run("unstaged", base)
        self.assertEqual(code, 1)
        finding = _object(_array(payload, "new_findings")[0])
        self.assertEqual(
            (_string(finding, "kind"), _string(finding, "name")),
            ("field", "Payload.label"),
        )

    def test_ratchet_parse_and_blob_read_failures_are_json(self) -> None:
        self._write("broken.py", "def broken(:\n")
        self._git("add", str(PACKAGE / "broken.py"))
        code, payload, stderr = self._run("staged")
        self.assertEqual((code, stderr), (1, ""))
        finding = _object(_array(payload, "new_findings")[0])
        self.assertEqual(_string(finding, "kind"), "file")
        self._git("reset", "-q", "HEAD", "--", str(PACKAGE / "broken.py"))
        (self.package / "broken.py").write_bytes(b"\xff\xfe")
        self._git("add", str(PACKAGE / "broken.py"))
        code, payload, stderr = self._run("staged")
        self.assertEqual((code, stderr), (2, ""))
        self.assertEqual(_string(payload, "status"), "error")


class DirectAuditContractTest(unittest.TestCase):
    """Verify direct JSON and handled-error exit contracts."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _run(self, *args: str) -> tuple[int, dict[str, JsonValue], str]:
        result = subprocess.run(
            ["python3", str(AUDIT), *args, "--format", "json"],
            cwd=self.cwd,
            text=True,
            capture_output=True,
            check=False,
        )
        return result.returncode, _json_object(result.stdout), result.stderr

    def test_clean_direct_audit_and_adjacent_field_doc(self) -> None:
        path = self.cwd / "clean.py"
        path.write_text(
            GOOD_MODULE
            + GOOD_CLASS
            + "    score: float\n"
            + '    """Normalized public score used by downstream consumers."""\n'
            + "    _cache: int\n",
            encoding="utf-8",
        )
        code, payload, stderr = self._run(str(path))
        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(_string(payload, "status"), "passed")

    def test_direct_findings_and_parse_failure_exit_one(self) -> None:
        missing = self.cwd / "missing.py"
        missing.write_text(
            GOOD_MODULE + GOOD_CLASS + "    score: float\n", encoding="utf-8"
        )
        code, payload, stderr = self._run(str(missing))
        self.assertEqual((code, stderr), (1, ""))
        finding = _object(_array(payload, "findings")[0])
        self.assertEqual(_string(finding, "kind"), "field")
        broken = self.cwd / "broken.py"
        broken.write_text("def broken(:\n", encoding="utf-8")
        code, payload, _ = self._run(str(broken))
        self.assertEqual(code, 1)
        parse_finding = _object(_array(payload, "findings")[0])
        self.assertEqual(_string(parse_finding, "kind"), "file")

    def test_direct_missing_path_and_read_failure_exit_two(self) -> None:
        code, payload, stderr = self._run()
        self.assertEqual((code, stderr), (2, ""))
        self.assertEqual(_string(payload, "status"), "error")
        code, payload, _ = self._run("absent.py")
        self.assertEqual(code, 2)
        invalid_utf8 = self.cwd / "invalid.py"
        invalid_utf8.write_bytes(b"\xff\xfe")
        code, payload, _ = self._run(str(invalid_utf8))
        self.assertEqual(code, 2)
        self.assertIn("could not read", _string(payload, "error"))

    def test_not_in_git_is_json_error(self) -> None:
        code, payload, stderr = self._run("--git-base", "HEAD")
        self.assertEqual((code, stderr), (2, ""))
        self.assertEqual(
            _string(payload, "error"), "current directory is not in a Git repository"
        )


if __name__ == "__main__":
    unittest.main()
