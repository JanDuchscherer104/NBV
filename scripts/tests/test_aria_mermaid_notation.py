"""Adversarial coverage of exact-label Mermaid notation validation."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("notation_check", ROOT / "tools/mermaid/scripts/aria_mermaid_notation.py")
assert SPEC is not None and SPEC.loader is not None
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class NotationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = {"symbols.rl.budget": "b_t", "symbols.rl.action_mask": r"m_{t,i}^{\mathrm{act}}", "equations.demo": "a=b"}

    def test_exact_symbol(self) -> None:
        self.assertEqual(CHECK.check_math('%% aria-math: symbols.rl.budget\nA["$$b_t$$"]', self.records), [])

    def test_exact_equation(self) -> None:
        self.assertEqual(CHECK.check_math('%% aria-math: equations.demo\nA["$$a=b$$"]', self.records), [])

    def test_every_block_not_merely_manifest_occurrence(self) -> None:
        text = '%% aria-math: symbols.rl.budget\nA["$$b_t$$"]\nB["$$invented$$"]'
        self.assertIn("unbound", " ".join(CHECK.check_math(text, self.records)))

    def test_unknown_key(self) -> None:
        self.assertIn("unknown canonical key", " ".join(CHECK.check_math('%% aria-math: symbols.nope\nA["$$b_t$$"]', self.records)))

    def test_changed_index(self) -> None:
        self.assertIn("differs", " ".join(CHECK.check_math('%% aria-math: symbols.rl.budget\nA["$$b_{t+1}$$"]', self.records)))

    def test_extra_expression_rejected(self) -> None:
        self.assertTrue(CHECK.check_math('%% aria-math: symbols.rl.budget\nA["$$b_t+1$$"]', self.records))

    def test_extra_block_rejected(self) -> None:
        self.assertTrue(CHECK.check_math('%% aria-math: symbols.rl.budget\nA["$$b_t$$ $$x$$"]', self.records))

    def test_unused_binding(self) -> None:
        self.assertTrue(CHECK.check_math('%% aria-math: symbols.rl.budget\nA["plain"]', self.records))
        self.assertTrue(CHECK.check_math('%% aria-math: symbols.rl.budget', self.records))

    def test_multiline_math_fails(self) -> None:
        self.assertTrue(CHECK.check_math('%% aria-math: symbols.rl.budget\nA["$$b_t\n$$"]', self.records))

    def test_multiple_math_blocks(self) -> None:
        text = '%% aria-math: symbols.rl.budget equations.demo\nA["$$b_t$$<br/>$$a=b$$"]'
        self.assertEqual(CHECK.check_math(text, self.records), [])

    def test_frontmatter_and_comments_not_math(self) -> None:
        text = '---\nconfig:\n  title: "$$ignored$$"\n---\n%% comment $$ignored$$\n%% aria-math: symbols.rl.budget\nA["$$b_t$$"]'
        self.assertEqual(CHECK.check_math(text, self.records), [])

    def read(self, text: str) -> dict[str, str]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "notation.yml"
            path.write_text(text, encoding="utf-8")
            return CHECK.read_projection(path)

    def test_generated_projection(self) -> None:
        records = self.read("symbols:\n  x:\n    tex: 'x''_t'\n    typst: '#symb.x'\nequations:\n  x:\n    tex: 'x=y'\n")
        self.assertEqual(records, {"symbols.x": "x'_t", "equations.x": "x=y"})

    def test_duplicate_key_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate record"):
            self.read("symbols:\n  x:\n    tex: 'x'\n  x:\n    tex: 'y'\n")

    def test_duplicate_tex_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate TeX"):
            self.read("symbols:\n  x:\n    tex: 'x'\n    tex: 'y'\n")

    def test_missing_and_unsupported_tex_fail(self) -> None:
        for text in ("symbols:\n  x:\n    tex: null\n", "symbols:\n  x:\n    tex: |\n      x\n", "symbols:\n  x:\n    description: x\n", "symbols:\n  x:\n    tex: ''\n", ""):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.read(text)


if __name__ == "__main__":
    unittest.main()
