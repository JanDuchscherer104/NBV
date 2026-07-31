#!/usr/bin/env python3
"""Select causal CI tiers and validate their aggregate result."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from fnmatch import fnmatchcase
import json
from pathlib import Path
import sys
import tomllib
from typing import Any, Mapping, Sequence

CONFIG_PATH = Path(".github/ci-impact.toml")
REQUIRED_TIERS = (
    "governance",
    "scientific",
    "package",
    "documentation",
    "graphify",
)
SUCCESS = "success"
SKIPPED = "skipped"


@dataclass(frozen=True)
class TierPolicy:
    """Path patterns that causally select one validation tier."""

    include: tuple[str, ...]
    exclude: tuple[str, ...] = ()

    def matches(self, path: str) -> bool:
        """Return whether ``path`` is included and not explicitly excluded."""
        return any(fnmatchcase(path, pattern) for pattern in self.include) and not any(
            fnmatchcase(path, pattern) for pattern in self.exclude
        )


@dataclass(frozen=True)
class ImpactPolicy:
    """Checked-in path and label policy for causal CI selection."""

    tiers: tuple[str, ...]
    full_paths: tuple[str, ...]
    labels: Mapping[str, frozenset[str]]
    tier_policy: Mapping[str, TierPolicy]

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> ImpactPolicy:
        """Load and validate the versioned TOML policy at ``path``."""
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as error:
            raise ValueError(f"cannot load CI impact policy {path}: {error}") from error

        root_keys = {"version", "tiers", "labels", "full", "tier"}
        if set(raw) != root_keys:
            raise ValueError(f"CI impact policy root keys must be exactly {root_keys}")
        if type(raw.get("version")) is not int or raw["version"] != 1:
            raise ValueError("CI impact policy version must be 1")
        tiers = _string_tuple(raw.get("tiers"), "tiers")
        if tiers != REQUIRED_TIERS:
            raise ValueError(f"tiers must be exactly {REQUIRED_TIERS!r}")

        full = _table(raw.get("full"), "full")
        if set(full) != {"paths"}:
            raise ValueError("full keys must be exactly {'paths'}")
        full_paths = _string_tuple(full.get("paths"), "full.paths")
        if not full_paths:
            raise ValueError("full.paths must not be empty")

        labels_raw = _table(raw.get("labels"), "labels")
        if set(labels_raw) != {"ci:full"}:
            raise ValueError("ci:full must be the only configured CI label")
        labels = {
            name: frozenset(_string_tuple(value, f"labels.{name}"))
            for name, value in labels_raw.items()
        }
        if labels["ci:full"] != frozenset(tiers):
            raise ValueError("ci:full must add every CI tier")

        tier_raw = _table(raw.get("tier"), "tier")
        if set(tier_raw) != set(tiers):
            raise ValueError("tier tables must exactly match the declared tiers")
        tier_policy: dict[str, TierPolicy] = {}
        for tier in tiers:
            table = _table(tier_raw[tier], f"tier.{tier}")
            unknown_keys = set(table) - {"include", "exclude"}
            if unknown_keys:
                raise ValueError(
                    f"tier.{tier} has unknown keys: {sorted(unknown_keys)}"
                )
            include = _string_tuple(table.get("include"), f"tier.{tier}.include")
            if not include:
                raise ValueError(f"tier.{tier}.include must not be empty")
            exclude = _string_tuple(table.get("exclude", []), f"tier.{tier}.exclude")
            tier_policy[tier] = TierPolicy(include=include, exclude=exclude)

        return cls(
            tiers=tiers,
            full_paths=full_paths,
            labels=labels,
            tier_policy=tier_policy,
        )

    def select(self, paths: Sequence[str], labels: Sequence[str] = ()) -> set[str]:
        """Select the union of path- and additive label-implied tiers.

        Any unknown path fails closed to every tier. Unknown labels are inert.
        """
        selected = {
            tier for label in labels for tier in self.labels.get(label, frozenset())
        }
        for path in paths:
            _validate_repo_path(path)
            if any(fnmatchcase(path, pattern) for pattern in self.full_paths):
                return set(self.tiers)
            matched = {
                tier
                for tier, policy in self.tier_policy.items()
                if policy.matches(path)
            }
            if not matched:
                return set(self.tiers)
            selected.update(matched)
        return selected


def _table(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{name} must be a TOML table")
    return value


def _string_tuple(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise ValueError(f"{name} must be a list of non-empty strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{name} must not contain duplicates")
    return tuple(value)


def _validate_repo_path(path: str) -> None:
    if not path or path.startswith(("/", "../")) or "/../" in path or "\\" in path:
        raise ValueError(f"invalid repository-relative path: {path!r}")


def parse_nul_paths(raw: bytes) -> list[str]:
    """Decode a NUL-delimited path stream produced by ``git diff -z``."""
    if not raw:
        return []
    if not raw.endswith(b"\0"):
        raise ValueError("expected a NUL-terminated path list")
    paths = [item.decode("utf-8") for item in raw[:-1].split(b"\0")]
    if any(not path for path in paths):
        raise ValueError("path list contains an empty entry")
    return paths


def parse_labels_json(raw: str) -> list[str]:
    """Decode the pull-request label names passed through a JSON environment value."""
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid labels JSON: {error}") from error
    if not isinstance(value, list) or not all(
        isinstance(label, str) for label in value
    ):
        raise ValueError("labels JSON must be a list of strings")
    return value


def aggregate_succeeds(
    selected: Mapping[str, bool],
    results: Mapping[str, str],
    *,
    impact_result: str,
    tiers: Sequence[str] = REQUIRED_TIERS,
) -> bool:
    """Return whether all selected jobs passed and unselected jobs safely skipped."""
    if impact_result != SUCCESS:
        return False
    if set(selected) != set(tiers) or set(results) != set(tiers):
        return False
    for tier in tiers:
        result = results[tier]
        if result not in {SUCCESS, SKIPPED}:
            return False
        if selected[tier] and result != SUCCESS:
            return False
    return True


def _parse_selected_json(raw: str, tiers: Sequence[str]) -> dict[str, bool]:
    value = _parse_json_object(raw, "selected")
    selected: dict[str, bool] = {}
    for key, item in value.items():
        if isinstance(item, bool):
            selected[key] = item
        elif item in {"true", "false"}:
            selected[key] = item == "true"
        else:
            raise ValueError(f"selected.{key} must be a boolean")
    if set(selected) != set(tiers):
        raise ValueError("selected results must contain every configured tier")
    return selected


def _parse_results_json(raw: str, tiers: Sequence[str]) -> dict[str, str]:
    value = _parse_json_object(raw, "results")
    if not all(isinstance(item, str) for item in value.values()):
        raise ValueError("job results must be strings")
    if set(value) != set(tiers):
        raise ValueError("job results must contain every configured tier")
    return {key: str(item) for key, item in value.items()}


def _parse_json_object(raw: str, name: str) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid {name} JSON: {error}") from error
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{name} JSON must be an object")
    return value


def _write_outputs(selected: set[str], policy: ImpactPolicy, output_path: Path) -> None:
    with output_path.open("a", encoding="utf-8") as output:
        for tier in policy.tiers:
            output.write(f"{tier}={str(tier in selected).lower()}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--full", action="store_true", help="select every tier")
    parser.add_argument(
        "--labels-json",
        default="[]",
        help="pull-request label names encoded as JSON",
    )
    parser.add_argument(
        "--github-output",
        type=Path,
        help="append GitHub Actions step outputs to this file",
    )
    parser.add_argument(
        "--check-aggregate",
        action="store_true",
        help="validate CI_SELECTED_JSON and CI_RESULTS_JSON",
    )
    args = parser.parse_args()

    try:
        policy = ImpactPolicy.load(args.config)
        if args.check_aggregate:
            selected_results = _parse_selected_json(
                _required_env("CI_SELECTED_JSON"), policy.tiers
            )
            results = _parse_results_json(
                _required_env("CI_RESULTS_JSON"), policy.tiers
            )
            if not aggregate_succeeds(
                selected_results,
                results,
                impact_result=_required_env("CI_IMPACT_RESULT"),
                tiers=policy.tiers,
            ):
                print("aggregate CI contract failed", file=sys.stderr)
                return 1
            print("aggregate CI contract passed")
            return 0

        labels = parse_labels_json(args.labels_json)
        selected_tiers = (
            set(policy.tiers)
            if args.full
            else policy.select(parse_nul_paths(sys.stdin.buffer.read()), labels)
        )
    except (UnicodeDecodeError, ValueError) as error:
        parser.error(str(error))

    if args.github_output is not None:
        _write_outputs(selected_tiers, policy, args.github_output)
    print("selected CI tiers: " + ", ".join(sorted(selected_tiers)))
    return 0


def _required_env(name: str) -> str:
    import os

    value = os.environ.get(name)
    if value is None:
        raise ValueError(f"missing required environment variable {name}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
