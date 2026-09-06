"""Direct Typst-name authoring; copied notation and pseudocode fail closed."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/mermaid/scripts'))
import aria_mermaid_owners as owner


class OwnerReferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = {'symbols.rl.budget': 'b_t', 'equations.demo.eq': 'y=x+1'}
        self.owners = {'#symb.rl.budget': 'symbols.rl.budget', '#eqs.demo.eq': 'equations.demo.eq'}

    def source(self, body: str) -> str:
        return f'flowchart TB\n{owner.OWNERS}\n{owner.ARCHITECTURE}\n{body}\n'

    def compile(self, body: str) -> str:
        return owner.compile_source(self.source(body), self.records, self.owners)[0]

    def test_direct_symbol(self) -> None:
        text = self.compile('A["<b>Budget</b>$$#symb.rl.budget$$"]:::input')
        self.assertIn('%% aria-math: symbols.rl.budget', text)
        self.assertIn('$$b_t$$', text)
        self.assertNotIn('#symb', text)

    def test_direct_equation(self) -> None:
        text = self.compile('A["<b>Update</b>$$#eqs.demo.eq$$"]:::compute')
        self.assertIn('$$y=x+1$$', text)
        self.assertIn('%% aria-math: equations.demo.eq', text)

    def test_multiple_references_one_node(self) -> None:
        self.compile('A["<b>State</b>$$#symb.rl.budget$$ $$#symb.rl.budget$$"]:::data')

    def test_reference_on_edge(self) -> None:
        text = self.compile('A["<b>Budget</b>$$#symb.rl.budget$$"]:::input\nB["<b>Update</b>$$#eqs.demo.eq$$"]:::compute\nA -->|"$$#symb.rl.budget$$"| B')
        self.assertIn('A -->|"$$b_t$$"| B', text)

    def test_registry_change_propagates_without_source_edit(self) -> None:
        body = 'A["<b>Budget</b>$$#symb.rl.budget$$"]:::input'
        self.assertIn('$$b_t$$', self.compile(body))
        self.records['symbols.rl.budget'] = r'\beta_t'
        self.assertIn(r'$$\\beta_t$$', self.compile(body))

    def test_deterministic_source_and_dependency_order(self) -> None:
        source = self.source('A["<b>Update</b>$$#eqs.demo.eq$$ $$#symb.rl.budget$$"]:::compute')
        first = owner.compile_source(source, self.records, self.owners)
        self.assertEqual(first, owner.compile_source(source, self.records, self.owners))
        self.assertEqual(first[1], sorted(self.owners))

    def test_handwritten_math_rejected(self) -> None:
        for expression in ('b_t', '#symb.rl.budget+1', '#symb.rl.budget_{t+1}', '#symb.rl.budget #symb.rl.budget', '#eqs.demo.eq[0]', '#symb.rl.budget()', r'\sum_i #symb.rl.budget'):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                self.compile(f'A["<b>Budget</b>$${expression}$$"]:::input')

    def test_unregistered_owner(self) -> None:
        with self.assertRaisesRegex(ValueError, 'unregistered'):
            self.compile('A["<b>State</b>$$#symb.rl.invented$$"]:::input')

    def test_pseudocode_not_an_escape_hatch(self) -> None:
        with self.assertRaisesRegex(ValueError, 'pseudocode'):
            self.compile('A["<b>State</b><code>f(x)</code>$$#eqs.demo.eq$$"]:::compute')

    def test_process_cannot_only_name_its_output(self) -> None:
        with self.assertRaisesRegex(ValueError, 'equation or computation'):
            self.compile('A["<b>Update</b>$$#symb.rl.budget$$"]:::compute')

    def test_binding_modes_cannot_be_mixed(self) -> None:
        for directive in ('%% aria-math: symbols.rl.budget', '%% aria-compute: equations.demo.eq', owner.STRICT):
            with self.subTest(directive=directive), self.assertRaises(ValueError):
                self.compile(directive+'\nA["<b>State</b>$$#symb.rl.budget$$"]:::input')

    def test_multiline_math_and_reference_outside_math_rejected(self) -> None:
        for text in ('A["<b>State</b>$$#symb.rl.budget\n$$"]:::input', 'A["<b>State</b>#symb.rl.budget"]:::input'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.compile(text)

    def test_frontmatter_preserved_byte_zero(self) -> None:
        source = '---\nconfig:\n  theme: base\n---\n'+self.source('A["<b>Budget</b>$$#symb.rl.budget$$"]:::input')
        result, _ = owner.compile_source(source, self.records, self.owners)
        self.assertTrue(result.startswith('---\nconfig:\n  theme: base\n---\n'))

    def test_math_in_frontmatter_rejected(self) -> None:
        with self.assertRaises(ValueError):
            owner.compile_source('---\ntitle: "$$b_t$$"\n---\n'+self.source(''), self.records, self.owners)

    def fixture(self, directory: Path, field: str = '#symb.rl.budget') -> Path:
        path = directory / 'notation.yml'
        path.write_text(f"symbols:\n  rl.budget:\n    tex: 'b_t'\n    typst: '{field}'\nequations:\n", encoding='utf-8')
        return path

    def test_real_typst_field_resolved_and_corruption_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records, owners = owner.read_owners(self.fixture(root))
            self.assertEqual(owners, {'#symb.rl.budget': 'symbols.rl.budget'})
            for bad in ('#eqs.rl.budget', '#symb.rl.other', 'symb.rl.budget', '#symb.rl.budget()'):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    owner.read_owners(self.fixture(root, bad))

    def test_missing_owner_field_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.fixture(Path(tmp))
            path.write_text("symbols:\n  rl.budget:\n    tex: 'b_t'\nequations:\n")
            with self.assertRaisesRegex(ValueError, 'missing Typst'):
                owner.read_owners(path)

    def test_cannot_overwrite_authored_source_or_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); projection = self.fixture(root); source = root / 'source.mmd'
            original = self.source('A["<b>Budget</b>$$#symb.rl.budget$$"]:::input')
            source.write_text(original)
            for output in (source, projection):
                process = subprocess.run([sys.executable, owner.__file__, str(source), '--notation', str(projection), '--output', str(output)], capture_output=True, text=True)
                self.assertNotEqual(process.returncode, 0)
                self.assertIn('cannot overwrite', process.stderr)
            self.assertEqual(source.read_text(), original)


class ProjectionContentTests(unittest.TestCase):
    """Regression sentinels for previously abbreviated canonical projections."""
    def setUp(self) -> None:
        self.records, _ = owner.read_owners(ROOT / 'docs/notation.yml')

    def test_three_pools_keep_their_membership_sets(self) -> None:
        text = self.records['equations.scene.candidate_query_pools']
        self.assertEqual(text.count(r'\operatorname{Pool}'), 3)
        self.assertIn(r'\cap\operatorname{Frustum}', text)
        self.assertEqual(text.count(r'\in'), 3)

    def test_doubleq_keeps_terminal_and_empty_support_cases(self) -> None:
        text = self.records['equations.rl.qh_doubleq_index']
        for token in (r'\begin{cases}', 'h>1', 'd_t=0', r'\varnothing', r'\theta^-', r'\text{otherwise}'):
            self.assertIn(token, text)

    def test_masked_selection_preserves_state_target_and_requested_horizon(self) -> None:
        self.assertIn(r'Q_{h,\theta,e}(s_t,i)', self.records['equations.rl.qh_masked_argmax'])

    def test_fusion_keeps_elementwise_product(self) -> None:
        self.assertIn(r'\odot', self.records['equations.model.qh_feature_fusion'])
        self.assertIn(r'\odot', self.records['equations.model.qh_state_fusion_controls'])


if __name__ == '__main__':
    unittest.main()
