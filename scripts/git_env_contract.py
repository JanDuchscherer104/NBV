#!/usr/bin/env python3
"""Shared contract for inherited Git environment overrides."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping

GIT_ENV_OVERRIDES = frozenset(
    {
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_COMMON_DIR",
        "GIT_CONFIG",
        "GIT_CONFIG_COUNT",
        "GIT_CONFIG_PARAMETERS",
        "GIT_CONFIG_SYSTEM",
        "GIT_DIR",
        "GIT_INDEX_FILE",
        "GIT_NAMESPACE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_OBJECT_DIRECTORY_RELATIVE",
        "GIT_WORK_TREE",
    }
)


def inherited_git_override_names(
    environ: Mapping[str, str] | None = None,
) -> frozenset[str]:
    """Return inherited variables that redirect Git's local repository state."""
    source = os.environ if environ is None else environ
    return frozenset(
        key
        for key in source
        if key in GIT_ENV_OVERRIDES
        or key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))
        or (key.startswith("GIT_") and "\n" in key)
    )


def environment_without_inherited_git_overrides(
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Copy ``environ`` without variables governed by the Git boundary."""
    source = os.environ if environ is None else environ
    override_names = inherited_git_override_names(source)
    cleaned = {key: value for key, value in source.items() if key not in override_names}
    cleaned["GIT_CONFIG_NOSYSTEM"] = "1"
    cleaned["GIT_CONFIG_GLOBAL"] = os.devnull
    return cleaned


if __name__ == "__main__":
    if sys.argv[1:2] != ["--exec"] or len(sys.argv) < 3:
        raise SystemExit("usage: git_env_contract.py --exec COMMAND [ARG ...]")
    command = sys.argv[2:]
    os.execvpe(command[0], command, environment_without_inherited_git_overrides())
