"""Guard ordinary tensor annotations across active source and documentation tooling."""

from __future__ import annotations

from pathlib import Path

TEXT_SUFFIXES = {".lock", ".lua", ".md", ".py", ".qmd", ".sh", ".toml", ".yaml", ".yml"}


def test_active_surfaces_omit_external_tensor_typing_dependency() -> None:
    """Keep the removed annotation package out of maintained runtime and docs surfaces."""

    repo = Path(__file__).resolve().parents[2]
    roots = (
        repo / "AGENTS.md",
        repo / "aria_nbv" / "AGENTS.md",
        repo / "aria_nbv" / "aria_nbv",
        repo / "aria_nbv" / "tests",
        repo / "aria_nbv" / "pyproject.toml",
        repo / "aria_nbv" / "uv.lock",
        repo / "docs",
        repo / "scripts",
        repo / ".agents" / "skills",
        repo / ".agents" / "references",
        repo / ".agents" / "memory" / "state",
    )
    forbidden = "jax" + "typing"
    offenders: list[str] = []
    for root in roots:
        paths = (root,) if root.is_file() else root.rglob("*")
        for path in paths:
            if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
                continue
            if forbidden in path.read_text(encoding="utf-8", errors="ignore").lower():
                offenders.append(path.relative_to(repo).as_posix())
    assert not offenders
