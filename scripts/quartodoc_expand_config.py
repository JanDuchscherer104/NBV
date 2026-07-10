#!/usr/bin/env python3
"""Expand ARIA-NBV Quartodoc config from the importable package tree."""

from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "aria_nbv" / "aria_nbv"
DEFAULT_CONFIG = REPO_ROOT / "docs" / "_quarto.yml"

EXCLUDED_ROOTS = {
    "app",
    "data",
    "interpretability",
    "rerun_inspector",
    "rl",
    "streamlit_app",
}
EXCLUDED_PREFIXES = {
    "vin.experimental",
}


def is_importable_module(path: Path) -> bool:
    return path.suffix == ".py" and path.name != "__init__.py"


def module_name_from_file(path: Path) -> str:
    rel = path.relative_to(PACKAGE_ROOT).with_suffix("")
    return ".".join(rel.parts)


def module_name_from_package(path: Path) -> str:
    rel = path.relative_to(PACKAGE_ROOT)
    return ".".join(rel.parts)


def is_excluded(module_name: str) -> bool:
    parts = module_name.split(".")
    if not module_name or parts[0] in EXCLUDED_ROOTS:
        return True
    if any(part.startswith("_") for part in parts):
        return True
    return any(
        module_name == prefix or module_name.startswith(f"{prefix}.")
        for prefix in EXCLUDED_PREFIXES
    )


def discover_modules() -> list[tuple[str, bool]]:
    modules: dict[str, bool] = {}

    for init_file in PACKAGE_ROOT.rglob("__init__.py"):
        package_dir = init_file.parent
        if package_dir == PACKAGE_ROOT:
            continue
        module_name = module_name_from_package(package_dir)
        if not is_excluded(module_name):
            modules[module_name] = True

    for py_file in PACKAGE_ROOT.rglob("*.py"):
        if not is_importable_module(py_file):
            continue
        module_name = module_name_from_file(py_file)
        if not is_excluded(module_name):
            modules.setdefault(module_name, False)

    return sorted(modules.items())


def content_entry(module_name: str, is_package: bool) -> dict[str, Any]:
    return {
        "name": module_name,
        "include_imports": is_package,
    }


def expanded_config(
    config: dict[str, Any], modules: list[tuple[str, bool]]
) -> dict[str, Any]:
    result = copy.deepcopy(config)
    quartodoc = result["quartodoc"]
    sections = quartodoc.get("sections") or []
    stable = next(
        (
            section
            for section in sections
            if section.get("title") == "Stable Package Surface"
        ),
        None,
    )
    if stable is None:
        raise SystemExit("No Quartodoc section titled 'Stable Package Surface' found.")

    stable["contents"] = [
        content_entry(module_name, is_package) for module_name, is_package in modules
    ]
    quartodoc["sections"] = [stable]
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Input Quarto config path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write expanded config to this path.",
    )
    parser.add_argument(
        "--print-modules",
        action="store_true",
        help="Print discovered module names, one per line.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    modules = discover_modules()

    if args.print_modules:
        for module_name, _is_package in modules:
            print(module_name)

    if args.output is None:
        return

    with args.config.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    config = expanded_config(config, modules)

    with args.output.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False)


if __name__ == "__main__":
    main()
