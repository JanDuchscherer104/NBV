"""Regression tests for package README insertion into Quartodoc pages."""

from pathlib import Path

from scripts.quartodoc_expand_config import PACKAGE_ROOT, discover_modules
from scripts.quartodoc_inject_package_readmes import (
    REFERENCE_DIR,
    _guide_block,
    inject_package_readmes,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_inject_package_readmes_preserves_api_content_and_rewrites_links(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    package_root = repo_root / "aria_nbv" / "aria_nbv"
    reference_dir = repo_root / "docs" / "reference"
    vin_readme = package_root / "vin" / "README.md"
    _write(
        vin_readme,
        "# VIN\n\n"
        "A package guide with a [method](../../../docs/typst/method.typ) and "
        "![diagram](../../../docs/figures/diagram.svg).\n\n"
        "See the [other package](../other/README.md).\n\n"
        "```mermaid\n"
        "flowchart LR\n"
        "  A --> B\n"
        "```\n\n"
        "```python\n"
        "print('unchanged')\n"
        "```\n\n"
        "## Usage\n\n"
        "Use it.\n",
    )
    _write(package_root / "other" / "README.md", "# Other\n\nOther guide.\n")
    page = reference_dir / "vin.qmd"
    _write(
        page,
        "# vin { #aria_nbv.vin }\n\n"
        "`vin`\n\n"
        "Package docstring survives.\n\n"
        "## Attributes\n\n"
        "Generated API inventory survives.\n",
    )

    modules = [("vin", True), ("other", True)]
    assert inject_package_readmes(
        modules=modules,
        package_root=package_root,
        reference_dir=reference_dir,
    ) == [page]

    rendered_source = page.read_text(encoding="utf-8")
    assert "Package docstring survives." in rendered_source
    assert "Generated API inventory survives." in rendered_source
    assert "# VIN\n" not in rendered_source
    assert rendered_source.index("## Package guide") < rendered_source.index(
        "## Attributes"
    )
    assert "../typst/method.typ" in rendered_source
    assert "../figures/diagram.svg" in rendered_source
    assert "other.qmd" in rendered_source
    assert "```{mermaid}\nflowchart LR" in rendered_source
    assert "```mermaid" not in rendered_source
    assert "```python\nprint('unchanged')" in rendered_source

    assert not inject_package_readmes(
        modules=modules,
        package_root=package_root,
        reference_dir=reference_dir,
    )


def test_inject_package_readmes_respects_incremental_filter(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    package_root = repo_root / "aria_nbv" / "aria_nbv"
    reference_dir = repo_root / "docs" / "reference"
    modules = [("vin", True), ("other", True)]
    for module_name in ("vin", "other"):
        _write(package_root / module_name / "README.md", f"# {module_name}\n\nGuide.\n")
        _write(
            reference_dir / f"{module_name}.qmd",
            f"# {module_name}\n\n## Classes\n\nGenerated.\n",
        )

    assert inject_package_readmes(
        modules=modules,
        package_root=package_root,
        reference_dir=reference_dir,
        filters=("vin",),
    ) == [reference_dir / "vin.qmd"]
    assert "quartodoc-package-readme" in (reference_dir / "vin.qmd").read_text(
        encoding="utf-8"
    )
    assert "quartodoc-package-readme" not in (reference_dir / "other.qmd").read_text(
        encoding="utf-8"
    )


def test_current_public_package_readmes_are_projectable() -> None:
    """Every README on the generated API surface has supported local links."""
    projected_modules: list[str] = []
    for module_name, is_package in discover_modules():
        readme = PACKAGE_ROOT.joinpath(*module_name.split(".")) / "README.md"
        if not is_package or not readme.is_file():
            continue
        guide = _guide_block(
            module_name,
            readme=readme,
            page=REFERENCE_DIR / f"{module_name}.qmd",
            docs_root=REFERENCE_DIR.parent,
            package_root=PACKAGE_ROOT,
        )
        assert "## Package guide" in guide
        projected_modules.append(module_name)

    assert projected_modules == [
        "configs",
        "data_handling",
        "data_handling.ase_efm",
        "data_handling.vin_store",
        "lightning",
        "oracle",
        "oracle.pipelines",
        "reporting",
        "rollouts",
        "rollouts.replay",
        "rri_metrics",
        "targets",
        "vin",
    ]
