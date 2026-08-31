#!/usr/bin/env python3
"""Regression tests for inherited Git-environment isolation."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from git_env_contract import (  # noqa: E402
    GIT_ENV_OVERRIDES,
    environment_without_inherited_git_overrides,
    inherited_git_override_names,
)

ADVERSARIAL_GIT_ENV = {
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_KEY_0",
    "GIT_CONFIG_NOSYSTEM",
    "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_SYSTEM",
    "GIT_CONFIG_VALUE_0",
    "GIT_DIR",
    "GIT_INDEX_FILE",
    "GIT_NAMESPACE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_OBJECT_DIRECTORY_RELATIVE",
    "GIT_WORK_TREE",
}


def _poisoned_env(guard: Path) -> dict[str, str]:
    """Route every relevant Git override at the isolated guard repository."""
    return {
        "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(guard / ".git/objects"),
        "GIT_COMMON_DIR": str(guard / ".git"),
        "GIT_CONFIG": str(guard / ".git/config"),
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_GLOBAL": str(guard / ".git/config"),
        "GIT_CONFIG_KEY_0": "core.bare",
        "GIT_CONFIG_NOSYSTEM": "0",
        "GIT_CONFIG_PARAMETERS": "'core.bare'='true'",
        "GIT_CONFIG_SYSTEM": str(guard / ".git/config"),
        "GIT_CONFIG_VALUE_0": "true",
        "GIT_DIR": str(guard / ".git"),
        "GIT_INDEX_FILE": str(guard / "poisoned-index"),
        "GIT_NAMESPACE": "poisoned",
        "GIT_OBJECT_DIRECTORY": str(guard / ".git/objects"),
        "GIT_OBJECT_DIRECTORY_RELATIVE": "objects",
        "GIT_WORK_TREE": str(guard),
    }


class GitEnvironmentContractTests(unittest.TestCase):
    def test_contract_removes_routing_but_preserves_nonrouting_variables(self) -> None:
        routing = inherited_git_override_names(
            {key: "poison" for key in ADVERSARIAL_GIT_ENV}
        )
        self.assertTrue(GIT_ENV_OVERRIDES <= routing)
        self.assertNotIn("GIT_CEILING_DIRECTORIES", routing)
        self.assertNotIn("GIT_DISCOVERY_ACROSS_FILESYSTEM", routing)
        cleaned = environment_without_inherited_git_overrides(
            {
                "GIT_DIR": "poisoned",
                "GIT_CEILING_DIRECTORIES": "/workspace",
                "GIT_DISCOVERY_ACROSS_FILESYSTEM": "1",
            }
        )
        self.assertNotIn("GIT_DIR", cleaned)
        self.assertEqual(cleaned["GIT_CEILING_DIRECTORIES"], "/workspace")
        self.assertEqual(cleaned["GIT_DISCOVERY_ACROSS_FILESYSTEM"], "1")
        self.assertEqual(cleaned["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(cleaned["GIT_CONFIG_GLOBAL"], os.devnull)

    def test_clean_boundary_cannot_mutate_guard_repository(self) -> None:
        clean_env = os.environ.copy()
        for variable in inherited_git_override_names(clean_env):
            clean_env.pop(variable, None)
        with tempfile.TemporaryDirectory(prefix="git-env-guard-") as tmp:
            guard = Path(tmp) / "guard"
            subprocess.run(
                ["git", "init", "-q", "-b", "guard", str(guard)],
                check=True,
                env=clean_env,
            )
            subprocess.run(
                ["git", "-C", str(guard), "config", "--local", "core.bare", "true"],
                check=True,
                env=clean_env,
            )
            match = re.search(
                r"^GIT_ENV_CLEAN := (?P<command>.+)$",
                (REPO_ROOT / "Makefile").read_text(encoding="utf-8"),
                re.MULTILINE,
            )
            self.assertIsNotNone(match)
            assert match is not None
            child = Path(tmp) / "child"
            child.mkdir()
            result = subprocess.run(
                [
                    *shlex.split(match.group("command")),
                    "git",
                    "-C",
                    str(child),
                    "init",
                    "-q",
                    "-b",
                    "probe",
                ],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
                env=clean_env | _poisoned_env(guard),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            value = subprocess.run(
                ["git", "-C", str(guard), "config", "--local", "--get", "core.bare"],
                check=True,
                capture_output=True,
                text=True,
                env=clean_env,
            ).stdout.strip()
            self.assertEqual(value, "true")

    def test_clean_git_env_fails_closed_when_contract_execution_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="git-env-wrapper-failure-") as tmp:
            fixture_dir = Path(tmp)
            wrapper = fixture_dir / "clean_git_env.sh"
            wrapper.write_bytes((REPO_ROOT / "scripts/clean_git_env.sh").read_bytes())
            wrapper.chmod(wrapper.stat().st_mode | 0o100)
            (fixture_dir / "git_env_contract.py").write_text(
                "raise SystemExit(23)\n", encoding="utf-8"
            )
            marker = fixture_dir / "payload-ran"
            result = subprocess.run(
                [
                    str(wrapper),
                    sys.executable,
                    "-c",
                    f"open({str(marker)!r}, 'w').close()",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(marker.exists())

    def test_git_boundary_removes_newline_containing_variable_atomically(self) -> None:
        poisoned_name = "GIT_BAD\nGIT_OK"
        self.assertNotIn(
            poisoned_name,
            environment_without_inherited_git_overrides(
                {"PATH": os.environ["PATH"], poisoned_name: "poisoned"}
            ),
        )
        result = subprocess.run(
            [
                str(REPO_ROOT / "scripts/clean_git_env.sh"),
                sys.executable,
                "-c",
                f"import os; raise SystemExit({poisoned_name!r} in os.environ)",
            ],
            check=False,
            capture_output=True,
            text=True,
            env=os.environ | {poisoned_name: "poisoned"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
