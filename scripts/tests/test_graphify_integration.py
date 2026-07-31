#!/usr/bin/env python3
"""Focused regression checks for the Graphify integration contract."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

SCRIPT = Path(__file__).resolve().parents[1] / "check_graphify_integration.py"
SPEC = importlib.util.spec_from_file_location("check_graphify_integration", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
integration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(integration)
PACKAGE_SOURCE = "aria_nbv/aria_nbv/__init__.py"


def _raises_message(function, *args: object) -> str:
    try:
        function(*args)
    except RuntimeError as exc:
        return str(exc)
    raise AssertionError("expected RuntimeError")


def test_manifest_contracts() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        missing = _raises_message(integration._load_manifest, root / "missing.json")
        assert "manifest is unavailable" in missing

        malformed = root / "manifest.json"
        malformed.write_text("[", encoding="utf-8")
        malformed_message = _raises_message(integration._load_manifest, malformed)
        assert "malformed JSON" in malformed_message

        malformed.write_text("[]", encoding="utf-8")
        object_message = _raises_message(integration._load_manifest, malformed)
        assert "must be a JSON object" in object_message

        malformed.write_text(
            json.dumps({"aria_nbv/aria_nbv/model.py": {}}), encoding="utf-8"
        )
        assert integration._load_manifest(malformed) == {
            "aria_nbv/aria_nbv/model.py": {}
        }


def test_structural_inclusion_exclusion() -> None:
    assert integration._validate_structural_manifest({PACKAGE_SOURCE: {}}) == 1

    forbidden = _raises_message(
        integration._validate_structural_manifest,
        {
            PACKAGE_SOURCE: {},
            "docs/_inv/inventory.json": {},
            "docs/index_files/libs/file.js": {},
        },
    )
    assert "forbidden Graphify structural sources" in forbidden
    assert "docs/_inv/inventory.json" in forbidden
    assert "docs/index_files/libs/file.js" in forbidden

    missing = _raises_message(
        integration._validate_structural_manifest,
        {"docs/index.qmd": {}},
    )
    assert "missing required Graphify structural source" in missing

    for path in (
        "/tmp/file.py",
        "./aria_nbv/aria_nbv/__init__.py",
        r"aria_nbv\aria_nbv\__init__.py",
        "",
        ".",
        "..",
        "aria_nbv//aria_nbv/__init__.py",
        "aria_nbv/./aria_nbv/__init__.py",
        "aria_nbv/../aria_nbv/__init__.py",
    ):
        message = _raises_message(
            integration._validate_structural_manifest, {PACKAGE_SOURCE: {}, path: {}}
        )
        assert "non-canonical repo-relative paths" in message

    outside = _raises_message(
        integration._validate_structural_manifest,
        {PACKAGE_SOURCE: {}, "scripts/graphify_refresh.py": {}},
    )
    assert "outside allowed structural surfaces" in outside
    assert "scripts/graphify_refresh.py" in outside

    nonexistent = _raises_message(
        integration._validate_structural_manifest,
        {PACKAGE_SOURCE: {}, "docs/does/not/exist.qmd": {}},
    )
    assert "nonexistent repo paths" in nonexistent


def test_extract_command_contract() -> None:
    captured: list[list[str]] = []

    class _Completed:
        stderr = ""

    def _run(command: list[str], **kwargs: object) -> _Completed:
        captured.append(command)
        out = Path(command[-1]) / "graphify-out"
        out.mkdir(parents=True)
        (out / "manifest.json").write_text(
            json.dumps({PACKAGE_SOURCE: {}}), encoding="utf-8"
        )
        assert kwargs["cwd"] == integration.ROOT
        assert kwargs["check"] is True
        assert kwargs["text"] is True
        assert kwargs["capture_output"] is True
        return _Completed()

    original_run = integration.subprocess.run
    try:
        integration.subprocess.run = _run
        with tempfile.TemporaryDirectory() as directory:
            assert integration._extract_structural_manifest(Path(directory)) == {
                PACKAGE_SOURCE: {}
            }
    finally:
        integration.subprocess.run = original_run

    assert captured == [
        [
            "graphify",
            "extract",
            ".",
            "--code-only",
            "--no-cluster",
            "--out",
            captured[0][-1],
        ]
    ]


def test_version_mismatch_diagnostic() -> None:
    original_expected = getattr(integration, "_expected_version")
    original_found = getattr(integration, "_graphify_version")
    try:
        setattr(integration, "_expected_version", lambda: "0.9.20")
        setattr(integration, "_graphify_version", lambda: "0.9.19")
        message = _raises_message(integration._check_graphify_version)
    finally:
        setattr(integration, "_expected_version", original_expected)
        setattr(integration, "_graphify_version", original_found)

    assert "Graphify 0.9.20 is required" in message
    assert "found 0.9.19" in message


def test_extract_failure_diagnostic() -> None:
    def _run(*_: object, **__: object) -> object:
        raise subprocess.CalledProcessError(
            returncode=2,
            cmd=["graphify", "extract"],
            stderr="manifest write failed",
        )

    original_run = integration.subprocess.run
    try:
        integration.subprocess.run = _run
        with tempfile.TemporaryDirectory() as directory:
            message = _raises_message(
                integration._extract_structural_manifest, Path(directory)
            )
    finally:
        integration.subprocess.run = original_run

    assert "Graphify code-only extraction failed" in message
    assert "manifest write failed" in message


def test_semantic_policy_requires_reinclude_rules() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for path in (
            "docs/index.qmd",
            "docs/contents/topic.qmd",
            "docs/typst/thesis/main.typ",
            "docs/literature/source.md",
            "docs/figures/diagrams/overview.svg",
            ".agents/references/source_order.md",
        ):
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("", encoding="utf-8")

        rules = {
            "*",
            "**",
            "graphify-out/",
            "graphify-out/**",
            "docs/_build/",
            "docs/_extensions/",
            "docs/_inv/",
            "docs/_generated/",
            "docs/_site/",
            "docs/*_files/",
            "docs/**/*_files/",
            "!docs/",
            "!docs/index.qmd",
            "!docs/contents/",
            "!docs/contents/**",
            "!docs/typst/",
            "!docs/typst/thesis/",
            "!docs/typst/thesis/**",
            "!docs/literature/",
            "!docs/literature/*.md",
            "!docs/literature/*.qmd",
            "!docs/literature/*.jsonl",
            "!docs/figures/",
            "!docs/figures/diagrams/",
            "!docs/figures/diagrams/**/*.svg",
            "!.agents/",
            "!.agents/references/",
            "!.agents/references/*.md",
        }
        policy = root / ".graphifyignore"
        policy.write_text("\n".join(sorted(rules)), encoding="utf-8")

        original_root = integration.ROOT
        try:
            integration.ROOT = root
            integration._validate_semantic_policy()
            policy.write_text(
                "\n".join(sorted(rules - {"!docs/contents/**"})), encoding="utf-8"
            )
            message = _raises_message(integration._validate_semantic_policy)
        finally:
            integration.ROOT = original_root

    assert "missing semantic-source Graphify reinclude rules" in message
    assert "Quarto docs: !docs/contents/**" in message


def test_default_ci_keeps_graphify_integration_opt_in() -> None:
    makefile = (integration.ROOT / "Makefile").read_text(encoding="utf-8")
    ci_line = next(line for line in makefile.splitlines() if line.startswith("ci:"))
    graphify_line = next(
        line for line in makefile.splitlines() if line.startswith("graphify-ci:")
    )

    assert "graphify-integration-self-test" not in ci_line
    assert "graphify-skill-self-test" not in ci_line
    assert "graphify-integration-self-test" in graphify_line
    assert "graphify-skill-self-test" in graphify_line


def test_default_hook_install_keeps_graphify_dispatch_opt_in() -> None:
    makefile = (integration.ROOT / "Makefile").read_text(encoding="utf-8")
    install_hooks_line = next(
        line for line in makefile.splitlines() if line.startswith("install-hooks:")
    )
    graphify_hook_line = next(
        line
        for line in makefile.splitlines()
        if line.startswith("install-graphify-git-hook:")
    )
    normal_hook_recipe = makefile.split("install-git-hooks:", 1)[1].split(
        "\ninstall-graphify-git-hook:", 1
    )[0]
    graphify_hook_recipe = makefile.split("install-graphify-git-hook:", 1)[1].split(
        "\ninstall-hooks:", 1
    )[0]

    assert "install-graphify-git-hook" not in install_hooks_line
    assert '[ "$$name" = post-commit ] && continue' in normal_hook_recipe
    assert "post-commit" in graphify_hook_line
    assert "scripts/git_hooks/post-commit" in graphify_hook_recipe


def main() -> None:
    test_manifest_contracts()
    test_structural_inclusion_exclusion()
    test_extract_command_contract()
    test_version_mismatch_diagnostic()
    test_extract_failure_diagnostic()
    test_semantic_policy_requires_reinclude_rules()
    test_default_ci_keeps_graphify_integration_opt_in()
    test_default_hook_install_keeps_graphify_dispatch_opt_in()


if __name__ == "__main__":
    main()
