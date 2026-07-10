#!/usr/bin/env python3
"""Finalize generated Quartodoc reference navigation for ARIA-NBV."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

DEFAULT_SIDEBAR = (
    Path(__file__).resolve().parents[1] / "docs" / "reference" / "_sidebar.yml"
)
REFERENCE_PREFIX = "reference/"


def module_name_from_page(page: str) -> str | None:
    if not page.startswith(REFERENCE_PREFIX) or not page.endswith(".qmd"):
        return None
    stem = page.removeprefix(REFERENCE_PREFIX).removesuffix(".qmd")
    if stem == "index" or stem.startswith("_"):
        return None
    return stem


def page_from_entry(entry: Any) -> str | None:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        file_value = entry.get("file")
        if isinstance(file_value, str):
            return file_value
    return None


def insert_module(root: dict[str, Any], module_name: str) -> None:
    node = root
    parts = module_name.split(".")
    prefix_parts: list[str] = []
    for part in parts:
        prefix_parts.append(part)
        children = node.setdefault("children", {})
        node = children.setdefault(
            part,
            {
                "text": part,
                "module": ".".join(prefix_parts),
                "children": {},
            },
        )


def render_node(node: dict[str, Any]) -> dict[str, Any]:
    module_name = node["module"]
    entry: dict[str, Any] = {
        "text": node["text"],
        "file": f"{REFERENCE_PREFIX}{module_name}.qmd",
    }
    children = node.get("children") or {}
    if children:
        entry["contents"] = [render_node(children[name]) for name in sorted(children)]
    return entry


def nested_contents(entries: list[Any]) -> list[Any]:
    leading_entries: list[Any] = []
    tree: dict[str, Any] = {"children": {}}

    for entry in entries:
        page = page_from_entry(entry)
        module_name = module_name_from_page(page) if page is not None else None
        if module_name is None:
            leading_entries.append(entry)
            continue
        insert_module(tree, module_name)

    module_entries = [
        render_node(tree["children"][name]) for name in sorted(tree["children"])
    ]
    return leading_entries + module_entries


def write_api_index(path: Path, contents: list[Any]) -> None:
    index_path = path.with_name("_api_index.md")
    top_level_entries = [
        entry
        for entry in contents
        if isinstance(entry, dict)
        and isinstance(entry.get("text"), str)
        and isinstance(entry.get("file"), str)
    ]
    lines = [
        "## Stable Package Surface",
        "",
        "Generated from the importable `aria_nbv` package topology. Nested",
        "sidebar entries follow dotted module paths; package pages document",
        "their public reexports, while leaf module pages document local symbols.",
        "",
    ]
    for entry in top_level_entries:
        page = entry["file"].removeprefix(REFERENCE_PREFIX)
        lines.append(f"- [{entry['text']}]({page})")
    lines.append("")
    index_path.write_text("\n".join(lines), encoding="utf-8")


def nest_sidebar(path: Path) -> None:
    with path.open("r", encoding="utf-8") as f:
        sidebar_config = yaml.safe_load(f)

    sidebars = sidebar_config.get("website", {}).get("sidebar", [])
    for sidebar in sidebars:
        if sidebar.get("id") != "reference":
            continue
        for entry in sidebar.get("contents", []):
            if not isinstance(entry, dict):
                continue
            if entry.get("section") == "Stable Package Surface":
                entry["contents"] = nested_contents(entry.get("contents", []))
                write_api_index(path, entry["contents"])
                with path.open("w", encoding="utf-8") as f:
                    yaml.safe_dump(sidebar_config, f, sort_keys=False)
                return

    raise SystemExit(
        "No reference sidebar section titled 'Stable Package Surface' found."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "sidebar",
        nargs="?",
        type=Path,
        default=DEFAULT_SIDEBAR,
        help="Quartodoc-generated sidebar file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    nest_sidebar(args.sidebar)


if __name__ == "__main__":
    main()
