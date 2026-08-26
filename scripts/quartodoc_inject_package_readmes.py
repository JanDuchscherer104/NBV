#!/usr/bin/env python3
"""Project package README guides into generated Quartodoc package pages.

Quartodoc owns the package docstring and public-symbol inventory.  This script
adds the corresponding user-facing package README as a marker-bounded guide,
without making ``docs/reference`` a second authored documentation surface.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
from collections.abc import Iterable
from pathlib import Path

try:  # Direct execution puts ``scripts/`` on sys.path; pytest imports the package.
    from quartodoc_expand_config import PACKAGE_ROOT, REPO_ROOT, discover_modules
except ModuleNotFoundError:  # pragma: no cover - exercised by the pytest import path.
    from scripts.quartodoc_expand_config import (
        PACKAGE_ROOT,
        REPO_ROOT,
        discover_modules,
    )

DOCS_ROOT = REPO_ROOT / "docs"
REFERENCE_DIR = DOCS_ROOT / "reference"

_API_SECTION = re.compile(
    r"^## (?:Attributes|Classes|Functions|Modules)$", re.MULTILINE
)
_GUIDE_BLOCK = re.compile(
    r"\n*<!-- quartodoc-package-readme: [^\n]+ -->\n.*?"
    r"<!-- /quartodoc-package-readme -->\n*",
    re.DOTALL,
)
_MARKDOWN_LINK = re.compile(
    r"(?P<prefix>!?(?:\[[^\]]*\])\()"
    r"(?P<destination><[^>]+>|[^\s)]+)"
    r"(?P<suffix>(?:\s+[^)]*)?\))"
)
_GITHUB_MERMAID_FENCE = re.compile(r"^```mermaid[ \t]*$", re.MULTILINE)


def _relative_destination(destination: Path, page: Path) -> str:
    """Return the Quarto-page-relative link for a file beneath ``docs``."""
    return os.path.relpath(destination, start=page.parent).replace(os.sep, "/")


def _package_readme_destination(destination: Path, *, package_root: Path) -> str | None:
    """Return the generated page name when a README targets another package."""
    if destination.name != "README.md":
        return None
    try:
        module_name = ".".join(destination.parent.relative_to(package_root).parts)
    except ValueError:
        return None
    return f"{module_name}.qmd" if module_name else None


def _rewrite_local_links(
    text: str, *, readme: Path, page: Path, docs_root: Path, package_root: Path
) -> str:
    """Make README-local links resolve from a generated reference page.

    Quarto expands an include as if its content had been pasted into the parent
    page.  Package READMEs therefore need their local documentation and package
    README links rewritten from the README directory to ``docs/reference``.
    Unknown local links fail closed so a new README cannot silently publish a
    broken reference-page link.
    """

    def replace(match: re.Match[str]) -> str:
        raw_destination = match.group("destination")
        bracketed = raw_destination.startswith("<") and raw_destination.endswith(">")
        destination = raw_destination[1:-1] if bracketed else raw_destination
        if destination.startswith(("#", "/", "http://", "https://", "mailto:")):
            return match.group(0)

        path_text, separator, fragment = destination.partition("#")
        resolved = (readme.parent / path_text).resolve()
        try:
            resolved.relative_to(docs_root)
        except ValueError:
            package_page = _package_readme_destination(
                resolved, package_root=package_root
            )
            if package_page is None:
                raise ValueError(
                    f"{readme}: unsupported local link {destination!r}; "
                    "link to docs content or another package README."
                )
            rewritten = package_page
        else:
            rewritten = _relative_destination(resolved, page)

        if separator:
            rewritten = f"{rewritten}#{fragment}"
        if bracketed:
            rewritten = f"<{rewritten}>"
        return f"{match.group('prefix')}{rewritten}{match.group('suffix')}"

    return _MARKDOWN_LINK.sub(replace, text)


def _without_leading_title(text: str, *, readme: Path) -> str:
    """Remove the README H1 because its reference page already has one."""
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.strip():
            if not line.startswith("# "):
                raise ValueError(
                    f"{readme}: package README must begin with one H1 title."
                )
            remainder = lines[index + 1 :]
            while remainder and not remainder[0].strip():
                remainder.pop(0)
            return "".join(remainder).rstrip() + "\n"
    raise ValueError(f"{readme}: package README is empty.")


def _quarto_readme_syntax(text: str) -> str:
    """Adapt GitHub-compatible README constructs to executable Quarto syntax.

    Package READMEs use GitHub's `````mermaid`` fence so diagrams render on
    GitHub.  Quarto activates its Mermaid renderer only for `````{mermaid}``
    executable cells; normalize just that fence while retaining the README as
    the authored, GitHub-facing source.
    """
    return _GITHUB_MERMAID_FENCE.sub("```{mermaid}", text)


def _guide_block(
    module_name: str, *, readme: Path, page: Path, docs_root: Path, package_root: Path
) -> str:
    """Return the marker-bounded README guide to insert into one package page."""
    readme_text = _without_leading_title(
        readme.read_text(encoding="utf-8"), readme=readme
    )
    guide = _rewrite_local_links(
        readme_text,
        readme=readme,
        page=page,
        docs_root=docs_root,
        package_root=package_root,
    )
    guide = _quarto_readme_syntax(guide)
    return (
        f"<!-- quartodoc-package-readme: aria_nbv.{module_name} -->\n"
        "## Package guide\n\n"
        f"{guide.rstrip()}\n"
        "<!-- /quartodoc-package-readme -->\n"
    )


def inject_package_readmes(
    *,
    modules: Iterable[tuple[str, bool]],
    package_root: Path = PACKAGE_ROOT,
    reference_dir: Path = REFERENCE_DIR,
    filters: Iterable[str] = (),
) -> list[Path]:
    """Inject README guides for generated package pages and return changed pages.

    Args:
        modules: Quartodoc-discovered module names with their package flag.
        package_root: Root containing the importable ``aria_nbv`` package.
        reference_dir: Directory containing generated Quartodoc pages.
        filters: Optional Quartodoc-style glob filters for incremental builds.
    """
    patterns = tuple(filters)
    docs_root = reference_dir.parent
    changed: list[Path] = []
    for module_name, is_package in modules:
        if not is_package or (
            patterns
            and not any(
                fnmatch.fnmatchcase(module_name, pattern) for pattern in patterns
            )
        ):
            continue
        package_dir = package_root.joinpath(*module_name.split("."))
        readme = package_dir / "README.md"
        page = reference_dir / f"{module_name}.qmd"
        if not readme.is_file() or not page.is_file():
            continue

        original = page.read_text(encoding="utf-8")
        page_without_guide = _GUIDE_BLOCK.sub("\n", original).rstrip() + "\n"
        guide = _guide_block(
            module_name,
            readme=readme,
            page=page,
            docs_root=docs_root,
            package_root=package_root,
        )
        anchor = _API_SECTION.search(page_without_guide)
        if anchor is None:
            updated = f"{page_without_guide.rstrip()}\n\n{guide}"
        else:
            updated = (
                f"{page_without_guide[: anchor.start()].rstrip()}\n\n"
                f"{guide}\n{page_without_guide[anchor.start() :]}"
            )
        if updated != original:
            page.write_text(updated, encoding="utf-8")
            changed.append(page)
    return changed


def parse_args() -> argparse.Namespace:
    """Parse incremental-generation options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--filter",
        action="append",
        default=[],
        help="Apply a Quartodoc module glob; repeat for multiple filters.",
    )
    return parser.parse_args()


def main() -> None:
    """Inject package guides after Quartodoc has generated its package pages."""
    args = parse_args()
    changed = inject_package_readmes(modules=discover_modules(), filters=args.filter)
    print(f"Injected package README guides into {len(changed)} reference page(s).")


if __name__ == "__main__":
    main()
