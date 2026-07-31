#!/usr/bin/env python3
"""Hermetic contract tests for the optional Graphify Markdown projection."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_graphify_projection as projection  # noqa: E402
from build_graphify_projection import (  # noqa: E402
    ProjectionConfig,
    ProjectionError,
    build_projection,
)

REPOSITORY = "JanDuchscherer104/ARIA-NBV"
GITHUB = f"https://github.com/{REPOSITORY}"


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


class FakeRunner:
    """Delegate Git to the fixture repo and fake Typst's compiled evidence."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.call_cwds: list[Path] = []
        self.citations: list[dict[str, object]] = []
        self.links: list[dict[str, object]] = []

    def __call__(
        self, argv: list[str] | tuple[str, ...], *, cwd: Path
    ) -> subprocess.CompletedProcess[str]:
        command = tuple(str(part) for part in argv)
        self.calls.append(command)
        self.call_cwds.append(cwd)
        if command[0] == "git":
            return subprocess.run(
                command, cwd=cwd, check=False, capture_output=True, text=True
            )
        if command[0] != "typst":
            raise AssertionError(f"unexpected executable: {command[0]}")
        if command[1] == "query":
            rows = {
                "cite": self.citations,
                "link": self.links,
                "heading": [{"body": "Introduction", "level": 1}],
            }[command[3]]
            return subprocess.CompletedProcess(command, 0, json.dumps(rows), "")
        if command[1] == "compile":
            Path(command[3]).write_bytes(b"%PDF fixture\n")
            return subprocess.CompletedProcess(command, 0, "", "")
        raise AssertionError(f"unexpected typst command: {command}")


class Fixture:
    """Create the smallest repository that exercises every retained owner."""

    def __init__(self, root: Path) -> None:
        self.root = root
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        _git(root, "config", "user.email", "projection@example.invalid")
        _git(root, "config", "user.name", "Projection Test")
        self.write("src/model.py", "class Model:\n    pass\n")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "code"], cwd=root, check=True)
        self.code_oid = _git(root, "rev-parse", "HEAD")
        _git(root, "tag", "v1.0.0", self.code_oid)

        self.write(
            "docs/typst/shared/style.typ",
            (
                f'#let aria-github-repo = "{REPOSITORY}"\n'
                '#let _aria-code-ref() = sys.inputs.at("aria-code-ref", default: "main")\n'
                "#let gh(path, body: none, ref: none, line: none, end: none) = none\n"
                '#let gh-wip(path, body: none, ref: "main", line: none, end: none) = none\n'
                '#let gh-symbol(symbol, body: none, language: "python") = none\n'
            ),
        )
        self.write(
            "docs/typst/thesis/main.typ",
            '#include "sections/a.typ"\n#include "sections/b.typ"\n',
        )
        self.write(
            "docs/typst/thesis/sections/a.typ",
            (
                "= Introduction\n@PaperA\n"
                f'#gh("src/model.py", ref: "{self.code_oid}", line: 1, end: 2)\n'
                f'#gh("src/model.py", ref: "{self.code_oid}", line: 1, end: 2)\n'
                '#gh-wip("src/model.py", ref: "main", line: 1)\n'
                "// @Ignored\n```typst\n@AlsoIgnored\n```\n"
            ),
        )
        self.write("docs/typst/thesis/sections/b.typ", "@QhPaper\n")
        self.write("docs/typst/thesis/inactive.typ", "@Inactive\n")
        self.write(
            "docs/references.bib",
            "@misc{PaperA, title={{Complex, Nested} Title}, eprint={2406.10224v2}}\n",
        )
        self.write(
            "docs/references-qh.bib",
            "@article{QhPaper, doi={10.1609/AAAI.V34I04.5784}}\n",
        )
        rows = [
            {
                "title": "Paper A",
                "arxiv_id": "2406.10224",
                "tex_dir": "paper-a",
                "pdf_file": "paper-a.pdf",
            },
            {
                "title": "QH Paper",
                "doi": "https://doi.org/10.1609/aaai.v34i04.5784",
            },
            {"title": "Title-only Paper A", "pdf_file": "missing.pdf"},
        ]
        self.write(
            "docs/literature/sources.jsonl",
            "".join(json.dumps(row) + "\n" for row in rows),
        )
        self.write("docs/literature/tex-src/paper-a/main.tex", "PRIVATE TEX\n")
        self.write_bytes("docs/literature/pdf/paper-a.pdf", b"PRIVATE PDF\n")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "owners"], cwd=root, check=True)

        self.runner = FakeRunner()
        self.runner.citations = [{"key": "PaperA"}, {"key": "QhPaper"}]
        blob = f"{GITHUB}/blob/{self.code_oid}/src/model.py#L1-L2"
        self.runner.links = [
            {"dest": blob},
            {"dest": blob},
            {"dest": f"{GITHUB}/blob/main/src/model.py#L1"},
            {"dest": "https://example.invalid/outside"},
        ]

    def write(self, relative: str, content: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def write_bytes(self, relative: str, content: bytes) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def config(self, **overrides: object) -> ProjectionConfig:
        values: dict[str, object] = {
            "repo_root": self.root,
            "thesis_root": Path("docs/typst/thesis/main.typ"),
            "style_path": Path("docs/typst/shared/style.typ"),
            "bibliography_paths": (
                Path("docs/references.bib"),
                Path("docs/references-qh.bib"),
            ),
            "manifest_path": Path("docs/literature/sources.jsonl"),
            "tex_root": Path("docs/literature/tex-src"),
            "pdf_root": Path("docs/literature/pdf"),
            "output_path": Path("graphify-input"),
            "aria_code_ref": self.code_oid,
            "aria_code_ref_source": "cli",
        }
        values.update(overrides)
        return ProjectionConfig(**values)


class ProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.fixture = Fixture(Path(temp.name))

    def build(self, *, check: bool = True, **overrides: object):
        return build_projection(
            self.fixture.config(**overrides),
            runner=self.fixture.runner,
            check=check,
        )

    @staticmethod
    def rendered(result: object) -> str:
        files = getattr(result, "files")
        return "\n".join(files[path] for path in sorted(files))

    def test_same_inputs_render_identical_timestamp_free_relative_files(self) -> None:
        first = self.build()
        second = self.build()
        self.assertEqual(first.files, second.files)
        rendered = self.rendered(first)
        self.assertNotIn(str(self.fixture.root), rendered)
        self.assertNotRegex(rendered, r"20\d\d-\d\d-\d\d[T ]")

    def test_owner_links_leave_projection_while_identity_links_stay_inside(
        self,
    ) -> None:
        result = self.build()
        thesis_page = next(
            body
            for body in result.files.values()
            if body.startswith("# thesis-source:docs/typst/thesis/sections/a.typ\n")
        )

        self.assertIn(
            "../../docs/typst/thesis/sections/a.typ",
            thesis_page,
        )
        self.assertRegex(thesis_page, r"\]\(\.\./citations/[^)]+\.md\)")

    def test_check_mode_leaves_existing_output_and_debris_unchanged(self) -> None:
        output = self.fixture.root / "graphify-input"
        output.mkdir()
        sentinel = output / "sentinel.md"
        sentinel.write_text("keep\n", encoding="utf-8")
        backup = self.fixture.root / ".graphify-input.backup"
        backup.mkdir()
        result = self.build(check=True)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")
        self.assertTrue(backup.exists())
        self.assertRegex("\n".join(result.warnings), r"backup|debris")

    def test_output_outside_repository_or_overlapping_owner_is_rejected(self) -> None:
        for output in (Path("../outside"), Path("docs/typst")):
            with self.subTest(output=output):
                with self.assertRaisesRegex(ProjectionError, r"outside|overlap|owner"):
                    self.build(output_path=output)

    def test_runner_uses_only_git_and_typst_and_one_code_ref(self) -> None:
        self.build()
        self.assertEqual(
            {call[0] for call in self.fixture.runner.calls}, {"git", "typst"}
        )
        typst_calls = [call for call in self.fixture.runner.calls if call[0] == "typst"]
        self.assertEqual(len(typst_calls), 4)
        for call in typst_calls:
            self.assertEqual(call.count(f"aria-code-ref={self.fixture.code_oid}"), 1)
        with self.assertRaisesRegex(AssertionError, "unexpected executable"):
            self.fixture.runner(["curl"], cwd=self.fixture.root)

    def test_typst_commands_share_owner_root_entry_and_code_ref(self) -> None:
        self.build()
        typst_invocations = [
            (call, cwd)
            for call, cwd in zip(
                self.fixture.runner.calls,
                self.fixture.runner.call_cwds,
                strict=True,
            )
            if call[0] == "typst"
        ]
        self.assertEqual(len(typst_invocations), 4)
        for call, cwd in typst_invocations:
            self.assertEqual(cwd, self.fixture.root / "docs")
            self.assertEqual(call[2], "typst/thesis/main.typ")
            self.assertEqual(call[call.index("--root") + 1], ".")
            self.assertEqual(
                call[call.index("--input") + 1],
                f"aria-code-ref={self.fixture.code_oid}",
            )

    def test_dynamic_include_fails_while_inactive_comments_and_raw_are_ignored(
        self,
    ) -> None:
        baseline = self.rendered(self.build())
        self.assertNotIn("Inactive", baseline)
        self.assertNotIn("Ignored", baseline)
        self.fixture.write(
            "docs/typst/thesis/main.typ",
            '#let part = "sections/a.typ"\n#include part\n',
        )
        with self.assertRaisesRegex(ProjectionError, r"dynamic|main\.typ"):
            self.build()

    def test_parent_relative_literal_include_normalizes_within_repository(self) -> None:
        self.fixture.write("docs/typst/shared/appendix.typ", "@AppendixPaper\n")
        self.fixture.write(
            "docs/typst/thesis/main.typ",
            '#include "sections/a.typ"\n#include "sections/b.typ"\n'
            '#include "../shared/appendix.typ"\n',
        )
        self.fixture.write(
            "docs/references.bib",
            "@misc{PaperA, eprint={2406.10224v2}}\n"
            "@misc{AppendixPaper, title={Appendix}}\n",
        )
        self.fixture.runner.citations.append({"key": "AppendixPaper"})

        rendered = self.rendered(self.build())

        self.assertIn(
            "# thesis-source:docs/typst/shared/appendix.typ",
            rendered,
        )
        self.assertIn("# citation:AppendixPaper", rendered)

    def test_parent_relative_literal_include_cannot_escape_repository(self) -> None:
        self.fixture.write(
            "docs/typst/thesis/main.typ",
            '#include "../../../../outside.typ"\n',
        )

        with self.assertRaisesRegex(ProjectionError, r"include escapes repository"):
            self.build()

    def test_duplicate_bibliography_key_fails(self) -> None:
        self.fixture.write(
            "docs/references-qh.bib",
            "@article{PaperA, doi={10.1/duplicate}}\n",
        )
        with self.assertRaisesRegex(
            ProjectionError, r"duplicate.*PaperA|PaperA.*duplicate"
        ):
            self.build()

    def test_compiled_citation_missing_from_bibliographies_fails(self) -> None:
        self.fixture.runner.citations.append({"key": "Missing"})
        with self.assertRaisesRegex(
            ProjectionError, r"Missing.*bibliograph|bibliograph.*Missing"
        ):
            self.build()

    def test_compiled_typst_label_wrapper_normalizes_to_bare_bibtex_key(self) -> None:
        self.fixture.runner.citations[0] = {"key": "<PaperA>"}

        rendered = self.rendered(self.build())

        self.assertIn("# citation:PaperA", rendered)
        self.assertNotIn("# citation:<PaperA>", rendered)

    def test_identity_only_join_uses_arxiv_then_doi_and_keeps_title_only_unmatched(
        self,
    ) -> None:
        rendered = self.rendered(self.build())
        self.assertIn("literature:arxiv:2406.10224", rendered)
        self.assertIn("literature:doi:10.1609/aaai.v34i04.5784", rendered)
        self.assertRegex(
            rendered,
            r"Title-only Paper A[\s\S]*unmatched|unmatched[\s\S]*Title-only Paper A",
        )

    def test_conflicting_identity_signals_fail_instead_of_fuzzy_joining(self) -> None:
        rows = [
            {"title": "By arXiv", "arxiv_id": "2406.10224"},
            {"title": "By DOI", "doi": "10.1/other"},
        ]
        self.fixture.write(
            "docs/literature/sources.jsonl",
            "".join(json.dumps(row) + "\n" for row in rows),
        )
        self.fixture.write(
            "docs/references.bib",
            "@misc{PaperA, eprint={2406.10224}, doi={10.1/other}}\n",
        )
        with self.assertRaisesRegex(ProjectionError, r"conflict|ambiguous"):
            self.build()

    def test_code_target_identity_includes_ref_oid_path_and_range_once(self) -> None:
        result = self.build()
        identity = (
            f"code-target:{REPOSITORY}@{self.fixture.code_oid}"
            f"[{self.fixture.code_oid}]:src/model.py:1-2"
        )
        pages = [
            body for body in result.files.values() if body.startswith(f"# {identity}\n")
        ]
        self.assertEqual(len(pages), 1)

    def test_final_gh_with_mutable_main_ref_is_rejected(self) -> None:
        section = self.fixture.root / "docs/typst/thesis/sections/a.typ"
        section.write_text(
            section.read_text(encoding="utf-8").replace(
                f'ref: "{self.fixture.code_oid}"', 'ref: "main"'
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            ProjectionError, r"main.*final|mutable.*gh|gh.*mutable"
        ):
            self.build()

    def test_asset_proxies_record_lexical_present_and_missing_without_content(
        self,
    ) -> None:
        rendered = self.rendered(self.build())
        self.assertIn("# tex-root:docs/literature/tex-src/paper-a", rendered)
        self.assertIn("# pdf:docs/literature/pdf/paper-a.pdf", rendered)
        self.assertIn("status: present", rendered)
        self.assertIn("status: missing-local", rendered)
        self.assertNotIn("PRIVATE TEX", rendered)
        self.assertNotIn("PRIVATE PDF", rendered)

    def test_pdf_symlink_does_not_leak_realpath_or_target_bytes(self) -> None:
        outside = self.fixture.root.parent / "outside.pdf"
        outside.write_bytes(b"OUTSIDE SECRET")
        pdf = self.fixture.root / "docs/literature/pdf/paper-a.pdf"
        pdf.unlink()
        pdf.symlink_to(outside)
        rendered = self.rendered(self.build())
        self.assertNotIn(str(outside), rendered)
        self.assertNotIn("OUTSIDE SECRET", rendered)

    def test_absolute_or_escaping_manifest_asset_path_is_rejected(self) -> None:
        for tex_dir in ("/tmp/escape", "../escape"):
            with self.subTest(tex_dir=tex_dir):
                self.fixture.write(
                    "docs/literature/sources.jsonl",
                    json.dumps({"title": "Escape", "tex_dir": tex_dir}) + "\n",
                )
                with self.assertRaisesRegex(
                    ProjectionError, r"asset|absolute|escape|outside"
                ):
                    self.build()

    def test_normal_build_removes_stale_debris_and_replaces_old_output(self) -> None:
        output = self.fixture.root / "graphify-input"
        output.mkdir()
        old = output / "old.md"
        old.write_text("old\n", encoding="utf-8")
        temp = self.fixture.root / ".graphify-input.tmp"
        backup = self.fixture.root / ".graphify-input.backup"
        temp.mkdir()
        backup.mkdir()
        result = self.build(check=False)
        self.assertFalse(old.exists())
        self.assertFalse(temp.exists())
        self.assertFalse(backup.exists())
        self.assertTrue(result.files)

    def test_failed_swap_restores_the_previous_output(self) -> None:
        output = self.fixture.root / "graphify-input"
        output.mkdir()
        old = output / "old.md"
        old.write_text("old\n", encoding="utf-8")
        real_replace = projection._replace_path
        calls = 0

        def fail_install(source: Path, destination: Path) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated install failure")
            real_replace(source, destination)

        with mock.patch.object(projection, "_replace_path", side_effect=fail_install):
            with self.assertRaises(ProjectionError):
                build_projection(
                    self.fixture.config(), runner=self.fixture.runner, check=False
                )
        self.assertEqual(old.read_text(encoding="utf-8"), "old\n")


if __name__ == "__main__":
    unittest.main()
