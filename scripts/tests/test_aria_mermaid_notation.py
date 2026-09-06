"""Exact canonical-label checks and adversarial architecture-coverage tests."""
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
        self.assertEqual(self.read("symbols:\n  x:\n    tex: 'x''_t'\n    typst: '#symb.x'\nequations:\n  x:\n    tex: 'x=y'\n"), {"symbols.x": "x'_t", "equations.x": "x=y"})

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


class ArchitectureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = {"symbols.state": "s", "equations.step": "s'=T(s,a)"}

    def errors(self, source: str) -> list[str]:
        return CHECK.check_math(source, self.records) + CHECK.check_architecture(source, self.records)

    def test_symbolic_data_and_sourced_computation(self) -> None:
        source = '%% aria-math: symbols.state\nS["<b>State</b>$$s$$"]:::data\n%% aria-compute: equations.step\nT["<b>Transition</b><code>Step(state, action)</code>"]:::compute\nS --> T'
        self.assertEqual(self.errors(source), [])

    def test_registered_equation_counts_as_computation(self) -> None:
        source = '%% aria-math: equations.step\nT["<b>Transition</b>$$s\'=T(s,a)$$"]:::compute'
        self.assertEqual(self.errors(source), [])

    def test_prose_only_compute_fails(self) -> None:
        self.assertIn("needs an equation or computation", " ".join(self.errors('A["<b>Attention</b>"]:::compute')))

    def test_symbol_alone_in_compute_fails(self) -> None:
        self.assertTrue(self.errors('%% aria-math: symbols.state\nA["<b>State update</b>$$s$$"]:::compute'))

    def test_title_only_data_and_output_fail(self) -> None:
        for role in ("data", "input", "output"):
            with self.subTest(role=role):
                self.assertTrue(self.errors(f'A["<b>Scene</b>"]:::{role}'))

    def test_prose_in_code_not_a_computation(self) -> None:
        self.assertTrue(self.errors('%% aria-compute: equations.step\nA["<b>Update</b><code>refresh scene memory</code>"]:::compute'))

    def test_code_requires_equation_owner(self) -> None:
        self.assertTrue(self.errors('A["<b>Update</b><code>Step(state)</code>"]:::compute'))
        self.assertTrue(self.errors('%% aria-compute: equations.missing\nA["<b>Update</b><code>Step(state)</code>"]:::compute'))
        self.assertTrue(self.errors('%% aria-compute: symbols.state\nA["<b>Update</b><code>Step(state)</code>"]:::compute'))

    def test_owner_cannot_be_attached_elsewhere(self) -> None:
        self.assertTrue(self.errors('%% aria-compute: equations.step\nA --> B\nB["<b>Step</b><code>Step(state)</code>"]:::compute'))
        self.assertTrue(self.errors('%% aria-compute: equations.step'))

    def test_pipeline_is_valid_computational_form(self) -> None:
        self.assertEqual(self.errors('%% aria-compute: equations.step\nA["<b>Encoder</b><code>Linear → GELU → LayerNorm</code>"]:::compute'), [])

    def test_tex_cannot_hide_in_code(self) -> None:
        self.assertTrue(self.errors(r'''%% aria-compute: equations.step
A["<b>Update</b><code>Step(\invented{x})</code>"]:::compute'''))

    def test_status_is_explicit_and_terminal(self) -> None:
        self.assertEqual(self.errors('A["<b>Harmful aliasing</b>"]:::status'), [])
        self.assertTrue(self.errors('A["<b>Harmful aliasing</b>"]:::status\nA --> B'))
        self.assertTrue(self.errors('\n'.join(f'{n}["<b>Outcome</b>"]:::status' for n in 'ABC')))

    def test_untyped_or_unsupported_node_cannot_escape(self) -> None:
        for source in ('A["<b>Update</b>"]', 'A("<b>Update</b>"):::compute', 'A["<b>Update</b>"]:::unknown', 'A["<b>Update</b>"]\nclass A compute;'):
            with self.subTest(source=source):
                self.assertTrue(self.errors(source))

    def test_body_prose_rejected_even_with_valid_symbol(self) -> None:
        self.assertTrue(self.errors('%% aria-math: symbols.state\nA["<b>State</b>$$s$$<br/>all modalities are present"]:::data'))

    def test_edge_data_is_exact_and_qualifiers_stay_short(self) -> None:
        node = '%% aria-math: symbols.state\nA["<b>State</b>$$s$$"]:::data\n'
        self.assertEqual(self.errors(node+'%% aria-math: symbols.state\nA -->|"$$s$$"| B'), [])
        self.assertTrue(self.errors(node+'A -->|"This is all the possible future state data"| B'))

    def test_duplicate_nodes_rejected(self) -> None:
        source = 'A["<b>Outcome</b>"]:::status\nA["<b>Outcome</b>"]:::status'
        self.assertTrue(self.errors(source))


if __name__ == "__main__":
    unittest.main()
