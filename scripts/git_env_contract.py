#!/usr/bin/env python3
"""Shared contract for inherited Git environment overrides."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping

GIT_ENV_OVERRIDES = frozenset(
    {
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_CEILING_DIRECTORIES",
        "GIT_COMMON_DIR",
        "GIT_CONFIG",
        "GIT_CONFIG_COUNT",
        "GIT_CONFIG_GLOBAL",
        "GIT_CONFIG_NOSYSTEM",
        "GIT_CONFIG_PARAMETERS",
        "GIT_CONFIG_SYSTEM",
        "GIT_DIR",
        "GIT_DISCOVERY_ACROSS_FILESYSTEM",
        "GIT_INDEX_FILE",
        "GIT_NAMESPACE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_OBJECT_DIRECTORY_RELATIVE",
        "GIT_WORK_TREE",
    }
)
GIT_ENV_OVERRIDE_PREFIXES = ("GIT_",)


def inherited_git_override_names(
    environ: Mapping[str, str] | None = None,
) -> frozenset[str]:
    """Return every inherited Git variable plus known routing overrides."""
    source = os.environ if environ is None else environ
    return frozenset(
        GIT_ENV_OVERRIDES
        | {
            key
            for key in source
            if any(key.startswith(prefix) for prefix in GIT_ENV_OVERRIDE_PREFIXES)
        }
    )


def environment_without_inherited_git_overrides(
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Copy ``environ`` without variables governed by the Git boundary."""
    source = os.environ if environ is None else environ
    override_names = inherited_git_override_names(source)
    return {key: value for key, value in source.items() if key not in override_names}


if __name__ == "__main__":
    if sys.argv[1:2] != ["--exec"] or len(sys.argv) < 3:
        raise SystemExit("usage: git_env_contract.py --exec COMMAND [ARG ...]")
    command = sys.argv[2:]
    os.execvpe(command[0], command, environment_without_inherited_git_overrides())
